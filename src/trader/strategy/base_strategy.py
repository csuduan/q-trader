"""
策略基类
定义策略的接口和基本功能
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.models.object import (
    BarData,
    Offset,
    OrderData,
    TickData,
    TradeData,
)
from src.trader.order_cmd import OrderCmd
from src.utils.logger import get_logger
from src.utils.config_loader import StrategyConfig
import pandas as pd

if TYPE_CHECKING:
    from src.trader.core.strategy_manager import StrategyManager

logger = get_logger(__name__)


class BaseStrategyParams(BaseModel):
    """策略公共参数"""
    symbol: str = "IM2603"
    bar: str = "M1"
    volume_per_trade: int = 1
    slippage: float = 0.0
    max_position: int = 1
    take_profit_pct: float = 0.0
    stop_loss_pct: float = 0.0
    external_signal: bool = False
    overnight: bool = False
    force_exit_time: str = "14:55:00"

    

class BaseSignal(BaseModel):
    """策略信号基类"""
    side: int = 0  # 信号方向: 1多头, -1空头, 0无信号
    entry_price: float = 0.0  # 开仓价格
    entry_time: Optional[datetime] = None  # 开仓时间
    entry_volume: int = 0  # 开仓目标手数
    exit_price: float = 0.0  # 平仓价格
    exit_time: Optional[datetime] = None  # 平仓时间
    exit_reason: str = ""  # 平仓原因
    # 真实入场信息
    entry_order_id: Optional[str] = None  # 开仓订单信息
    exit_order_id: Optional[str] = None  # 平仓订单信息
    pos_volume: int = 0  # 持仓手数
    pos_price: Optional[float] = None  # 持仓均价


class BaseStrategy:
    """策略基类"""

    # 订阅bar列表（格式："symbol-interval"）
    def __init__(self, strategy_id: str,strategy_config:StrategyConfig):
        self.strategy_id = strategy_id
        self.config: StrategyConfig = strategy_config
        self.inited: bool = False
        self.enabled: bool = True
        self.bar_subscriptions: List[str] = []
        # 策略管理器引用
        self.strategy_manager: Optional["StrategyManager"] = None
        # 参数模型（子类覆盖）
        self.params: BaseStrategyParams = BaseStrategyParams()
        # 信号（子类可以设置自己的信号类型）
        self.signal: Optional[BaseSignal] = None
        # 暂停状态
        self.opening_paused: bool = False
        self.closing_paused: bool = False

    def init(self,) -> bool:
        """策略初始化"""
        logger.info(f"策略 [{self.strategy_id}] 初始化...")
        self.inited = True
        return True

    def get_params(self) -> dict:
        """获取策略参数"""
        return self.params.model_dump() if self.params else {}
    
    def get_signal(self) -> dict:
        """获取当前信号"""
        return self.signal.model_dump() if self.signal else {}

    def update_params(self, params: Dict[str, Any]) -> None:
        """
        更新策略参数（只更新内存，不写入文件）

        Args:
            params: 要更新的参数字典
        """
        for key, value in params.items():
            if hasattr(self.params, key):
                setattr(self.params, key, value)
            else:
                logger.warning(f"策略 [{self.strategy_id}] 参数 {key} 不存在")

        logger.info(f"策略 [{self.strategy_id}] 参数已更新: {params}")

    def update_signal(self, signal: Dict[str, Any]) -> None:
        """
        更新策略信号（只更新内存，不写入文件）

        Args:
            signal: 要更新的信号字典
        """
        if not self.signal:
            self.signal = BaseSignal()

        for key, value in signal.items():
            if hasattr(self.signal, key):
                setattr(self.signal, key, value)

        logger.info(f"策略 [{self.strategy_id}] 信号已更新: side={self.signal.side}")

    def get_trading_status(self) -> str:
        """是否正在交易中(开仓中，平仓中)"""
        return ""

    def start(self) -> bool:
        """启动策略"""
        if not self.inited:
            self.init()
        self.enabled = True
        logger.info(f"策略 [{self.strategy_id}] 启动")
        return True

    def stop(self) -> bool:
        """停止策略"""
        self.enabled = False
        logger.info(f"策略 [{self.strategy_id}] 停止")
        return True

    # ==================== 事件回调 ====================
    def on_tick(self, tick: TickData):
        """Tick行情回调"""
        pass

    def on_bar(self, bar: BarData):
        """Bar行情回调"""
        pass

    def on_cmd_update(self,order_cmd:OrderCmd):
        """订单状态回调"""
        pass

    def on_order(self, order: OrderData):
        """订单状态回调"""
        pass

    def on_trade(self, trade: TradeData):
        """成交回调"""
        pass
    

    # ==================== 交易接口 ====================
    def send_order_cmd(self,order_cmd:OrderCmd):
        """发送报单指令"""
        order_cmd.source = f"策略-{self.strategy_id}"
        self.strategy_manager.send_order_cmd(self.strategy_id,order_cmd)
    
    def cancel_order_cmd(self,order_cmd:OrderCmd):
        """取消报单指令"""
        self.strategy_manager.cancel_order_cmd(self.strategy_id,order_cmd)

    def pause_opening(self) -> None:
        """暂停开仓"""
        self.opening_paused = True
        logger.info(f"策略 [{self.strategy_id}] 暂停开仓")

    def resume_opening(self) -> None:
        """恢复开仓"""
        self.opening_paused = False
        logger.info(f"策略 [{self.strategy_id}] 恢复开仓")

    def pause_closing(self) -> None:
        """暂停平仓"""
        self.closing_paused = True
        logger.info(f"策略 [{self.strategy_id}] 暂停平仓")

    def resume_closing(self) -> None:
        """恢复平仓"""
        self.closing_paused = False
        logger.info(f"策略 [{self.strategy_id}] 恢复平仓")

    def enable(self) -> None:
        """启用策略"""
        self.enabled = True
        logger.info(f"策略 [{self.strategy_id}] 已启用")

    def disable(self) -> None:
        """禁用策略"""
        self.enabled = False
        logger.info(f"策略 [{self.strategy_id}] 已禁用")
