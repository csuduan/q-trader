"""
策略管理器
负责策略实例化、启动/停止管理、事件路由、参数加载
"""

import csv
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, List

from src.app_context import get_app_context
from src.models.object import Direction, Offset
from src.utils.event_engine import EventEngine, EventTypes
from src.utils.logger import get_logger

from src.trader.strategy.base_strategy import BaseStrategy
from src.utils.config_loader import StrategyConfig
from src.trader.core.trading_engine import TradingEngine

ctx = get_app_context()


logger = get_logger(__name__)

# 全局CSV缓存：{csv_path: {strategy_id: params_dict}}
_csv_cache: Dict[str, Dict[str, dict]] = {}


def load_csv_file(csv_path: str) -> Dict[str, dict]:
    """加载CSV文件到缓存"""
    if csv_path in _csv_cache:
        return _csv_cache[csv_path]

    result = {}
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                strategy_id = row.get("strategy_id", "")
                if strategy_id:
                    result[strategy_id] = row
        _csv_cache[csv_path] = result
        logger.info(f"加载CSV参数文件: {csv_path}, 共 {len(result)} 个策略")
        return result
    except FileNotFoundError:
        logger.warning(f"参数文件不存在: {csv_path}")
        return {}
    except Exception as e:
        logger.error(f"加载CSV参数失败: {e}", exc_info=True)
        return {}


def load_strategy_params(config: StrategyConfig, strategy_id: str) -> dict:
    """
    加载策略参数

    Args:
        yaml_config: 从YAML加载的策略配置
        strategy_id: 策略ID

    Returns:
        dict: 合并后的策略参数
    """
    # 从YAML配置复制参数
    params={}
    params_file = config.params_file
    if not params_file:
        return {}

    # 处理变量替换（如 {date} 替换为当前日期YYYYMMDD）
    today_str = datetime.now().strftime("%Y%m%d")
    params_file = params_file.replace("{date}", today_str)

    # 构建完整路径
    app_config = get_app_context().get_config()
    csv_path = os.path.join(app_config.paths.params, params_file)

    # 加载CSV参数
    csv_data = load_csv_file(csv_path)
    csv_params = csv_data.get(strategy_id, {})
    if not csv_params:
        return {}

    # CSV参数直接覆盖
    for key, value in csv_params.items():
        if value:
            params[key] = value
    config.params = params
    return params


class StrategyManager:
    """策略管理器"""

    def __init__(self, strategies_config: Dict[str, StrategyConfig], trading_engine:TradingEngine):
        self.strategies_configs: Dict[str, StrategyConfig] = strategies_config
        self.strategies: Dict[str, BaseStrategy] = {}
        self.trading_engine:TradingEngine = trading_engine
        self.subscribed_symbols: set = set()
        # 订单ID -> 策略ID 的映射关系
        self.order_strategy_map: Dict[str, str] = {}
        self.event_engine: Optional[EventEngine] = None

    async def start(self) -> bool:
        """
        启动策略管理器

        Returns:
            bool: 初始化是否成功
        """
        try:
            self.event_engine = ctx.get_event_engine()
            # 加载并实例化策略
            self._load_strategies()
            # 注册事件到 EventEngine
            self._register_events()
            # 启动所有策略
            self.start_all()
            logger.info("策略管理器初始化完成")
            return True

        except Exception as e:
            logger.exception(f"策略管理器初始化失败: {e}")
            return False

    def _load_strategies(self) -> None:
        """从配置加载并实例化策略"""
        from src.trader.strategy import get_strategy_class

        for name, config in self.strategies_configs.items():
            if not config.enabled:
                logger.info(f"策略 {name} 未启用，跳过")
                continue

            strategy_type = config.type
            strategy_class = get_strategy_class(strategy_type)
            if strategy_class is None:
                logger.warning(f"未找到策略类: {strategy_type}")
                continue

            # 加载参数（YAML默认参数 + CSV覆盖）
            load_strategy_params(config, name)

            # 创建策略实例
            try:
                strategy = strategy_class(name,config)
                strategy.strategy_manager = self
                self.strategies[name] = strategy
                logger.info(f"添加策略: {name}")

                # 按需订阅合约行情
                symbol = config.params.get("symbol", "")
                if symbol:
                    self.subscribe_symbol(symbol)
            except Exception as e:
                logger.exception(f"创建策略 {name} 失败: {e}", exc_info=True)

    def _register_events(self) -> None:
        """注册策略事件到 EventEngine"""
        if not self.event_engine:
            logger.warning("EventEngine 未设置，跳过事件注册")
            return

        # 行情事件 - 分发给所有活跃策略
        self.event_engine.register(
            EventTypes.TICK_UPDATE, lambda data: self._dispatch_market_event("on_tick", data)
        )
        self.event_engine.register(
            EventTypes.KLINE_UPDATE, lambda data: self._dispatch_market_event("on_bar", data)
        )
        # 订单/成交事件 - 分发给对应策略
        self.event_engine.register(
            EventTypes.ORDER_UPDATE, lambda data: self._dispatch_order_event("on_order", data)
        )
        self.event_engine.register(
            EventTypes.TRADE_UPDATE, lambda data: self._dispatch_order_event("on_trade", data)
        )

        logger.info("策略事件已注册到EventEngine")

    def _extract_order_id(self, data: Any) -> Optional[str]:
        """从数据中提取订单ID"""
        if isinstance(data, dict):
            return data.get("order_id")
        elif hasattr(data, "order_id"):
            return data.order_id
        return None

    def _dispatch_market_event(self, method: str, data: Any) -> None:
        """
        分发行情事件到所有活跃策略

        Args:
            method: 策略方法名
            data: 事件数据
        """
        for name, strategy in self.strategies.items():
            if strategy.active:
                try:
                    getattr(strategy, method)(data)
                except Exception as e:
                    logger.exception(f"策略 {name} {method} 失败: {e}")

    def _dispatch_order_event(self, method: str, data: Any) -> None:
        """
        分发订单/成交事件到对应策略

        Args:
            method: 策略方法名
            data: 事件数据
        """
        order_id = self._extract_order_id(data)
        if not order_id:
            return

        strategy_id = self.order_strategy_map.get(order_id)
        if not strategy_id or strategy_id not in self.strategies:
            return

        strategy = self.strategies[strategy_id]
        if strategy.active:
            try:
                getattr(strategy, method)(data)
            except Exception as e:
                logger.exception(f"策略 {strategy_id} {method} 失败: {e}")

    def _dispatch_event(self, method: str, data: Any) -> None:
        """
        分发事件到策略（保留用于向后兼容）

        - 行情事件（on_tick, on_bar）：分发给所有活跃策略
        - 订单/成交事件（on_order, on_trade）：根据订单ID分发给对应策略
        """
        if method in ("on_order", "on_trade"):
            self._dispatch_order_event(method, data)
        else:
            self._dispatch_market_event(method, data)

    def start_strategy(self, name: str) -> bool:
        """启动策略"""
        if name not in self.strategies:
            return False
        return self.strategies[name].start()

    def stop_strategy(self, name: str) -> bool:
        """停止策略"""
        if name not in self.strategies:
            return False
        return self.strategies[name].stop()

    def start_all(self) -> None:
        """启动所有已启用的策略"""
        for strategy in self.strategies.values():
            if strategy.enabled:
                strategy.start()

    def stop_all(self) -> None:
        """停止所有策略"""
        for strategy in self.strategies.values():
            strategy.stop()

    def reset_all_for_new_day(self) -> None:
        """重置所有策略（开盘前调用）"""
        for strategy in self.strategies.values():
            if hasattr(strategy, "reset_for_new_day"):
                strategy.init()
        logger.info("所有策略已重置")

    def subscribe_symbol(self, symbol: str) -> bool:
        """订阅合约行情（按需订阅）"""
        if symbol in self.subscribed_symbols:
            return True
        if not self.trading_engine:
            return False

        result = self.trading_engine.subscribe_symbol(symbol)
        if result:
            self.subscribed_symbols.add(symbol)
            logger.info(f"订阅合约行情: {symbol}")
        return result

    def get_status(self) -> list:
        """获取所有策略状态"""
        return [
            {"strategy_id": s.strategy_id, "active": s.active, "config": s.config}
            for s in self.strategies.values()
        ]

    # ==================== 交易接口 ====================

    def _insert_order(
        self,
        strategy_id: str,
        symbol: str,
        direction: Direction,
        volume: int,
        price: Optional[float],
        offset: Offset,
    ) -> Optional[str]:
        """
        插入订单通用方法

        Args:
            strategy_id: 策略ID
            symbol: 合约代码
            direction: 方向
            volume: 手数
            price: 价格（None为市价）
            offset: 开平标识

        Returns:
            委托单ID
        """
        if not self.trading_engine:
            logger.warning(f"TradingEngine 未设置，无法执行下单")
            return None

        try:
            order_id = self.trading_engine.insert_order(
                symbol=symbol,
                direction=direction.value,
                offset=offset.value,
                volume=volume,
                price=price or 0,
            )
            if order_id:
                # 记录订单与策略的映射关系
                self.order_strategy_map[order_id] = strategy_id
                logger.info(
                    f"策略 [{strategy_id}] {direction.value} {volume}手 @{price or '市价'} -> 订单ID: {order_id}"
                )
            return order_id
        except Exception as e:
            logger.error(f"策略 [{strategy_id}] 下单失败: {e}")
            return None

    def buy(
        self,
        strategy_id: str,
        symbol: str,
        volume: int,
        price: Optional[float] = None,
        offset: Offset = Offset.OPEN,
    ) -> Optional[str]:
        """
        买入 - 通过 TradingEngine

        Args:
            strategy_id: 策略ID
            symbol: 合约代码
            volume: 手数
            price: 价格（None为市价）
            offset: 开平标识

        Returns:
            委托单ID
        """
        return self._insert_order(strategy_id, symbol, Direction.BUY, volume, price, offset)

    def sell(
        self,
        strategy_id: str,
        symbol: str,
        volume: int,
        price: Optional[float] = None,
        offset: Offset = Offset.CLOSE,
    ) -> Optional[str]:
        """
        卖出 - 通过 TradingEngine

        Args:
            strategy_id: 策略ID
            symbol: 合约代码
            volume: 手数
            price: 价格（None为市价）
            offset: 开平标识

        Returns:
            委托单ID
        """
        return self._insert_order(strategy_id, symbol, Direction.SELL, volume, price, offset)

    def cancel_order(self, strategy_id: str, order_id: str) -> bool:
        """
        撤单 - 通过 TradingEngine

        Args:
            strategy_id: 策略ID
            order_id: 订单ID

        Returns:
            是否成功
        """
        if not self.trading_engine:
            logger.warning(f"TradingEngine 未设置，无法执行撤单")
            return False

        # 验证订单是否属于该策略
        mapped_strategy_id = self.order_strategy_map.get(order_id)
        if mapped_strategy_id and mapped_strategy_id != strategy_id:
            logger.warning(
                f"订单 {order_id} 属于策略 {mapped_strategy_id}，策略 {strategy_id} 无法撤销"
            )
            return False

        try:
            success = self.trading_engine.cancel_order(order_id)
            if success:
                logger.info(f"策略 [{strategy_id}] 撤单成功: {order_id}")
            return success
        except Exception as e:
            logger.error(f"策略 [{strategy_id}] 撤单失败: {e}")
            return False

    def cleanup_order_mapping(self, order_id: str) -> None:
        """清理订单映射（订单完成或取消后调用）"""
        self.order_strategy_map.pop(order_id, None)
