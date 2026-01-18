"""
WebSocket管理模块
"""
import asyncio
import json
from datetime import datetime
from typing import Set

from fastapi import WebSocket

from src.utils.logger import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.log_subscribers: Set[WebSocket] = set()
        self.log_monitoring_enabled = False

    async def connect(self, websocket: WebSocket):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket连接已建立，当前连接数: {len(self.active_connections)}")

    def subscribe_logs(self, websocket: WebSocket):
        """订阅日志"""
        self.log_subscribers.add(websocket)
        logger.info(f"客户端订阅日志，当前订阅数: {len(self.log_subscribers)}")

    def unsubscribe_logs(self, websocket: WebSocket):
        """取消订阅日志"""
        self.log_subscribers.discard(websocket)
        logger.info(f"客户端取消订阅日志，当前订阅数: {len(self.log_subscribers)}")

    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        self.active_connections.discard(websocket)
        if websocket in self.log_subscribers:
            self.log_subscribers.discard(websocket)
            logger.info(f"客户端断开连接，从日志订阅列表移除，当前订阅数: {len(self.log_subscribers)}")
        logger.info(f"WebSocket连接已断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        if not self.active_connections:
            return

        message_str = json.dumps(message, ensure_ascii=False)
        disconnected = set()

        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"发送消息失败: {e}")
                disconnected.add(connection)

        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_account(self, account_data: dict) -> None:
        """广播账户信息更新"""
        await self.broadcast({
            "type": "account_update",
            "data": account_data,
            "timestamp": datetime.now().isoformat(),
        })

    async def broadcast_position(self, position_data: dict) -> None:
        """广播持仓信息更新"""
        await self.broadcast({
            "type": "position_update",
            "data": position_data,
            "timestamp": datetime.now().isoformat(),
        })

    async def broadcast_trade(self, trade_data: dict) -> None:
        """广播新成交记录"""
        await self.broadcast({
            "type": "trade_update",
            "data": trade_data,
            "timestamp": datetime.now().isoformat(),
        })

    async def broadcast_order(self, order_data: dict) -> None:
        """广播委托单状态更新"""
        await self.broadcast({
            "type": "order_update",
            "data": order_data,
            "timestamp": datetime.now().isoformat(),
        })

    async def broadcast_quote(self, quote_data: dict) -> None:
        """广播行情更新"""
        await self.broadcast({
            "type": "quote_update",
            "data": quote_data,
            "timestamp": datetime.now().isoformat(),
        })

    async def broadcast_log(self, log_data: dict) -> None:
        """广播日志更新（仅在日志监听服务启动时发送给订阅了日志的客户端）"""
        if not self.log_monitoring_enabled or not self.log_subscribers:
            return

        message = {
            "type": "log_update",
            "data": log_data,
            "timestamp": datetime.now().isoformat(),
        }
        message_str = json.dumps(message, ensure_ascii=False)
        disconnected = set()

        for connection in self.log_subscribers:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"发送日志失败: {e}")
                disconnected.add(connection)

        # 清理断开的连接
        for connection in disconnected:
            self.log_subscribers.discard(connection)
            self.disconnect(connection)

    def enable_log_monitoring(self) -> None:
        """启用日志监控"""
        if not self.log_monitoring_enabled:
            self.log_monitoring_enabled = True
            logger.info("日志监控服务已启用")

    def disable_log_monitoring(self) -> None:
        """禁用日志监控"""
        if self.log_monitoring_enabled:
            self.log_monitoring_enabled = False
            logger.info("日志监控服务已禁用")

    def is_log_monitoring_enabled(self) -> bool:
        """检查日志监控是否启用"""
        return self.log_monitoring_enabled


# 创建全局实例
websocket_manager = WebSocketManager()
