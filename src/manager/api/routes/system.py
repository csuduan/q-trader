"""
系统控制API路由
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, Request

from src.manager.api.dependencies import get_trading_manager
from src.manager.api.responses import error_response, success_response
from src.manager.api.schemas import SystemStatusRes
from src.manager.api.websocket_manager import websocket_manager
from src.models.object import AccountData
from src.models.po import JobPo
from src.utils.logger import get_logger
from src.manager.core.trading_manager import TradingManager


logger = get_logger(__name__)

router = APIRouter(prefix="/api/system", tags=["系统"])


@router.get("/status")
async def get_system_status(
    account_id: Optional[str] = Query(None, description="账户ID（多账号模式）"),
    trading_manager: TradingManager = Depends(get_trading_manager),
):
    """
    获取系统状态

    返回交易引擎的当前状态
    - **account_id**: 可选，指定账户ID（多账号模式）
    """
    trader = trading_manager.get_trader(account_id)

    if not trader:
        # trader未初始化（可能是禁用账户），返回默认状态
        return success_response(
            data={
                "account_id": account_id,
                "paused": False,
                "running": False
            },
            message="获取成功"
        )

    engine_status = trader.get_status()
    return success_response(data=engine_status, message="获取成功")


@router.get("/risk-control")
async def get_risk_control_status(
    account_id: Optional[str] = Query(None, description="账户ID（多账号模式）"),
    trading_manager:TradingManager=Depends(get_trading_manager),
):
    """
    获取风控状态

    返回风控模块的当前状态和配置
    - **account_id**: 可选，指定账户ID（多账号模式）
    """
    account:AccountData = await trading_manager.get_account(account_id) 
    return success_response(data=account.risk_status, message="获取成功")


@router.put("/risk-control")
async def update_risk_control(
    max_daily_orders: Optional[int] = Body(default=None),
    max_daily_cancels: Optional[int] = Body(default=None),
    max_order_volume: Optional[int] = Body(default=None),
    max_split_volume: Optional[int] = Body(default=None),
    order_timeout: Optional[int] = Body(default=None),
    account_id: Optional[str] = Body(None, description="账户ID（多账号模式）"),
    trading_manager=Depends(get_trading_manager),
):
    """
    更新风控参数

    - **account_id**: 可选，指定账户ID（多账号模式）
    - **max_daily_orders**: 单日最大报单次数
    - **max_daily_cancels**: 单日最大撤单次数
    - **max_order_volume**: 单笔最大报单手数
    - **max_split_volume**: 单笔最大拆单手数
    - **order_timeout**: 报单超时时间（秒）
    """
    trader = trading_manager.get_trader(account_id)
    if not trader:
        return error_response(code=404, message=f"账户 [{account_id}] 不存在")

    # 更新风控参数
    await trader.update_risk_control(
        max_daily_orders=max_daily_orders,
        max_daily_cancels=max_daily_cancels,
        max_order_volume=max_order_volume,
        max_split_volume=max_split_volume,
        order_timeout=order_timeout,
    )

    # 获取更新后的账户信息
    account = await trading_manager.get_account(account_id)
    return success_response(data=account.risk_status, message="风控参数已更新")


@router.put("/alert-wechat")
async def update_alert_wechat(
    alert_wechat: bool = Body(..., description="是否启用微信告警"),
    account_id: Optional[str] = Body(None, description="账户ID（多账号模式）"),
    trading_manager=Depends(get_trading_manager),
):
    """
    更新微信告警配置

    - **account_id**: 可选，指定账户ID（多账号模式）
    - **alert_wechat**: 是否启用微信告警
    """
    import yaml
    from pathlib import Path

    trader = trading_manager.get_trader(account_id)
    if not trader:
        return error_response(code=404, message=f"账户 [{account_id}] 不存在")

    # 更新配置文件
    account_config = trading_manager.account_configs_map.get(account_id)
    if not account_config:
        return error_response(code=404, message=f"账户配置 [{account_id}] 不存在")

    # 更新配置对象
    account_config.alert_wechat = alert_wechat

    # 保存到配置文件
    config_path = Path(account_config.paths.config if hasattr(account_config, 'paths') and account_config.paths else "./config") / f"account-{account_id}.yaml"
    if not config_path.exists():
        # 尝试从配置目录查找
        from src.utils.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        config_dir = config_loader.config_dir
        config_path = config_dir / f"account-{account_id}.yaml"

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        config_data["alert_wechat"] = alert_wechat

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f, allow_unicode=True)

        logger.info(f"账户 [{account_id}] 微信告警配置已更新: {alert_wechat}")
        return success_response(data={"alert_wechat": alert_wechat}, message="微信告警配置已更新")
    else:
        return error_response(code=404, message=f"配置文件不存在: {config_path}")


@router.get("/alert-wechat")
async def get_alert_wechat(
    account_id: Optional[str] = Query(None, description="账户ID（多账号模式）"),
    trading_manager=Depends(get_trading_manager),
):
    """
    获取微信告警配置

    - **account_id**: 可选，指定账户ID（多账号模式）
    """
    account_config = trading_manager.account_configs_map.get(account_id)
    if not account_config:
        return error_response(code=404, message=f"账户配置 [{account_id}] 不存在")

    return success_response(data={"alert_wechat": account_config.alert_wechat}, message="获取成功")


@router.post("/connect")
async def connect_system(
    account_id: Optional[str] = Body(None, description="账户ID（多账号模式）"),
    trading_manager=Depends(get_trading_manager),
):
    """
    连接到交易系统

    建立与交易接口的连接
    - **account_id**: 可选，指定账户ID（多账号模式）
    """
    trader = trading_manager.get_trader(account_id)

    if not trader:
        return error_response(code=404, message=f"账户 [{account_id}] 不存在")

    success = await trader.connect_gateway()

    if success:
        return success_response(data={"connected": True}, message="连接成功")
    else:
        return error_response(code=500, message="连接失败")


@router.post("/disconnect")
async def disconnect_system(
    account_id: Optional[str] = Body(None, description="账户ID（多账号模式）"),
    trading_manager=Depends(get_trading_manager),
):
    """
    断开交易系统连接

    关闭与交易接口的连接
    - **account_id**: 可选，指定账户ID（多账号模式）
    """
    trader = trading_manager.get_trader(account_id)

    if not trader:
        return error_response(code=404, message=f"账户 [{account_id}] 不存在")

    await trader.disconnect_gateway()
    return success_response(data={"connected": False}, message="已断开连接")


@router.post("/disconnect/gateway")
async def disconnect_gateway(
    account_id: Optional[str] = Body(None, description="账户ID（多账号模式）"),
    trading_manager=Depends(get_trading_manager),
):
    """
    断开网关连接

    只断开网关连接，不停止trader进程
    - **account_id**: 可选，指定账户ID（多账号模式）
    """
    trader = trading_manager.get_trader(account_id)

    if not trader:
        return error_response(code=404, message=f"账户 [{account_id}] 不存在")

    await trader.disconnect_gateway()
    return success_response(data={"gateway_connected": False}, message="已断开网关连接")


@router.post("/trader/start")
async def start_trader(
    account_id: Optional[str] = Body(None, description="账户ID（多账号模式）"),
    trading_manager=Depends(get_trading_manager),
):
    """
    启动账户Trader

    启动指定账户的Trader进程
    - **account_id**: 可选，指定账户ID（多账号模式）
    """
    success = await trading_manager.start_trader(account_id)

    if success:
        return success_response(data={"running": True}, message="Trader已启动")
    else:
        return error_response(code=500, message="Trader启动失败")


@router.post("/trader/stop")
async def stop_trader(
    account_id: Optional[str] = Body(None, description="账户ID（多账号模式）"),
    trading_manager=Depends(get_trading_manager),
):
    """
    停止账户Trader

    停止指定账户的Trader进程
    - **account_id**: 可选，指定账户ID（多账号模式）
    """
    success = await trading_manager.stop_trader(account_id)

    if success:
        return success_response(data={"running": False}, message="Trader已停止")
    else:
        return error_response(code=500, message="Trader停止失败")


@router.get("/trader/status")
async def get_trader_status(
    account_id: Optional[str] = Query(None, description="账户ID（多账号模式）"),
    trading_manager=Depends(get_trading_manager),
):
    """
    获取Trader状态

    返回指定账户Trader的运行状态
    - **account_id**: 可选，指定账户ID（多账号模式）
    """
    trader = trading_manager.get_trader(account_id)

    if not trader:
        # trader不存在（可能是禁用账户），返回默认状态
        return success_response(
            data={
                "account_id": account_id,
                "running": False,
                "alive": False,
                "created_process": False,
                "pid": None,
                "start_time": None,
                "last_heartbeat": None,
                "restart_count": 0,
                "socket_path": None
            },
            message="获取成功"
        )

    status = trader.get_status()
    return success_response(data=status, message="获取成功")


@router.post("/pause")
async def pause_trading(
    account_id: Optional[str] = Body(None, description="账户ID（多账号模式）"),
    trading_manager=Depends(get_trading_manager),
):
    """
    暂停交易

    暂停自动交易功能，手动下单仍然可用
    - **account_id**: 可选，指定账户ID（多账号模式）
    """
    trader = trading_manager.get_trader(account_id)

    if not trader:
        return error_response(code=404, message=f"账户 [{account_id}] 不存在")

    await trader.pause_trading()
    return success_response(data={"paused": True}, message="交易已暂停")


@router.post("/resume")
async def resume_trading(
    account_id: Optional[str] = Body(None, description="账户ID（多账号模式）"),
    trading_manager=Depends(get_trading_manager),
):
    """
    恢复交易

    恢复自动交易功能
    - **account_id**: 可选，指定账户ID（多账号模式）
    """
    trader = trading_manager.get_trader(account_id)

    if not trader:
        return error_response(code=404, message=f"账户 [{account_id}] 不存在")

    await trader.resume_trading()
    return success_response(data={"paused": False}, message="交易已恢复")


@router.post("/log-monitoring/start")
async def start_log_monitoring(request: Request):
    """
    启动日志监控服务

    启动后，服务端会开始监控日志文件并向订阅了日志的WebSocket客户端推送日志
    """
    if websocket_manager.is_log_monitoring_enabled():
        return success_response(data={"enabled": True}, message="日志监控服务已在运行")

    log_watcher = request.app.state.log_watcher
    if log_watcher:
        log_watcher.start()
        websocket_manager.enable_log_monitoring()

    return success_response(data={"enabled": True}, message="日志监控服务已启动")


@router.post("/log-monitoring/stop")
async def stop_log_monitoring(request: Request):
    """
    停止日志监控服务

    停止后，服务端将不再向WebSocket客户端推送日志
    """
    if not websocket_manager.is_log_monitoring_enabled():
        return success_response(data={"enabled": False}, message="日志监控服务未在运行")

    log_watcher = request.app.state.log_watcher
    if log_watcher:
        log_watcher.stop()
        websocket_manager.disable_log_monitoring()

    return success_response(data={"enabled": False}, message="日志监控服务已停止")


@router.get("/log-monitoring/status")
async def get_log_monitoring_status():
    """
    获取日志监控服务状态

    返回日志监控服务是否正在运行
    """
    enabled = websocket_manager.is_log_monitoring_enabled()
    return success_response(data={"enabled": enabled}, message="获取成功")
