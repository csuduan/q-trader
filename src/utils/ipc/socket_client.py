"""
Socket客户端 (Manager端)
用于在独立模式下与Trader子进程通信
"""

import asyncio
import inspect
import json
import struct
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)
HandlerType = Callable[[str, Any], None] | Callable[[str, Any], Awaitable[None]]


class SocketClient:
    """
    Unix Domain Socket 客户端 (Manager端)

    在独立模式下，TraderProxy作为Socket客户端，
    连接到Trader子进程的Socket服务器。

    职责：
    1. 连接到Trader Socket服务器
    2. 发送查询请求（request-response模式）
    3. 接收推送消息（账户/订单/成交/持仓/tick更新）
    """

    def __init__(
        self, socket_path: str, account_id: str, on_data_callback: HandlerType | None = None
    ):
        """
        初始化Socket客户端

        Args:
            socket_path: Socket文件路径
            account_id: 账户ID
            on_data_callback: 数据回调函数 (account_id: str, data_type: str, data: dict) -> None
        """
        self.socket_path = socket_path
        self.account_id = account_id
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.on_data_callback: HandlerType | None = on_data_callback

        # 请求-响应相关
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._receiving_task: Optional[asyncio.Task] = None

        # 重连相关
        self._auto_reconnect = True
        self._reconnect_interval = 3  # 重连间隔（秒）
        self._max_reconnect_attempts = 0  # 0表示无限重连
        self._reconnect_task: Optional[asyncio.Task] = None
        self._connection_closed_by_server = False  # 标记连接是否被服务端关闭

        # 连接断开回调
        self._on_disconnect_callback: Optional[Callable[[], None]] = None

        logger.info(f"[Manager-{account_id}] Socket客户端初始化: {socket_path}")

    async def connect(self, retry_interval: int = 3, max_retries: int = 30) -> bool:
        """
        连接到Trader

        Args:
            retry_interval: 重试间隔（秒）
            max_retries: 最大重试次数

        Returns:
            是否连接成功
        """
        for i in range(max_retries):
            try:
                self.reader, self.writer = await asyncio.open_unix_connection(self.socket_path)
                self.connected = True
                logger.info(f"[Trade Proxy-{self.account_id}] 已连接到Trader: {self.socket_path}")

                # 等待注册确认消息
                register_msg = await self._receive_message()
                if register_msg and register_msg.get("type") == "register":
                    registered_account_id = register_msg.get("data", {}).get("account_id")
                    if registered_account_id == self.account_id:
                        logger.info(f"[Trade Proxy-{self.account_id}] 连接注册成功")    
                        # 启动消息接收循环
                        self._receiving_task = asyncio.create_task(self._receiving_loop())
                        return True
                    else:
                        logger.warning(
                            f"[Trade Proxy-{self.account_id}] 注册account_id不匹配: {registered_account_id}"
                        )
                        return False

                return True

            except FileNotFoundError:
                logger.debug(
                    f"[Manager-{self.account_id}] Socket文件不存在，将在{retry_interval}秒后重试 "
                    f"({i+1}/{max_retries})"
                )
                await asyncio.sleep(retry_interval)
            except Exception as e:
                logger.error(f"[Manager-{self.account_id}] 连接Trader失败: {e}")
                await asyncio.sleep(retry_interval)

        logger.error(f"[Manager-{self.account_id}] 连接Trader失败，已达到最大重试次数")
        return False

    async def disconnect(self) -> None:
        """断开连接"""
        self.connected = False

        # 停止接收任务
        if self._receiving_task:
            self._receiving_task.cancel()
            try:
                await self._receiving_task
            except asyncio.CancelledError:
                pass
            self._receiving_task = None

        # 取消所有等待的请求
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(ConnectionError("连接已断开"))
        self._pending_requests.clear()

        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass

        logger.info(f"[Manager-{self.account_id}] 已断开Trader连接")

    async def request(
        self, request_type: str, data: Dict[str, Any], timeout: float = 10.0
    ) -> Optional[Dict[str, Any]]:
        """
        发送请求到Trader并等待响应（request-response模式）

        所有请求都使用此方法，包括：
        - 查询请求: get_account, get_orders, get_trades, get_positions, etc.
        - 交易请求: order_req, cancel_req

        Args:
            request_type: 请求类型
            data: 请求参数
            timeout: 超时时间（秒）

        Returns:
            响应数据，失败返回None
        """
        if not self.connected or not self.writer:
            logger.warning(f"[Manager-{self.account_id}] 未连接到Trader")
            return None

        # 生成请求ID
        request_id = str(uuid.uuid4())

        # 创建Future等待响应
        future: asyncio.Future[Dict[str, Any]] = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            # 发送请求
            message = {"type": request_type, "request_id": request_id, "data": data}

            # 序列化为JSON
            json_bytes = json.dumps(message, ensure_ascii=False).encode("utf-8")
            length = len(json_bytes)

            # 发送：4字节长度 + JSON内容
            self.writer.write(struct.pack(">I", length))
            self.writer.write(json_bytes)
            await self.writer.drain()

            # 等待响应
            response = await asyncio.wait_for(future, timeout=timeout)
            if request_type != "ping":
                logger.info(f"[Trade Proxy-{self.account_id}] 请求成功: {request_type}")
            return response

        except asyncio.TimeoutError:
            logger.warning(f"[Manager-{self.account_id}] 请求超时: {request_type}")
            self._pending_requests.pop(request_id, None)
            return None
        except Exception as e:
            logger.exception(f"[Manager-{self.account_id}] 请求失败: {request_type}, {e}")
            self._pending_requests.pop(request_id, None)
            return None

    async def _receiving_loop(self) -> None:
        """消息接收循环"""
        while self.connected:
            try:
                message = await self._receive_message()
                if not message:
                    logger.info(f"[Manager-{self.account_id}] Trader关闭了连接")
                    break

                await self._handle_message(message)

            except asyncio.IncompleteReadError:
                logger.info(f"[Manager-{self.account_id}] Trader关闭了连接 (IncompleteReadError)")
                break
            except ConnectionResetError:
                logger.warning(f"[Manager-{self.account_id}] 连接被重置 (ConnectionResetError)")
                break
            except ConnectionAbortedError:
                logger.warning(f"[Manager-{self.account_id}] 连接被中止 (ConnectionAbortedError)")
                break
            except Exception as e:
                logger.error(f"[Manager-{self.account_id}] 接收消息时出错: {e}")
                break

        # 连接断开，更新状态
        was_connected = self.connected
        self.connected = False

        # 通知连接断开
        if was_connected:
            asyncio.create_task(self._notify_disconnection())

        # 如果启用了自动重连，并且连接是被服务端关闭的，触发重连
        if self._auto_reconnect and self._connection_closed_by_server:
            logger.info(f"[Manager-{self.account_id}] 检测到连接断开，将尝试自动重连")
            # 重连循环会在单独的task中处理

    async def _receive_message(self) -> Optional[Dict[str, Any]]:
        """
        接收消息

        消息格式：
        - 4字节长度前缀（Big Endian）
        - JSON内容

        Returns:
            消息字典，失败返回None
        """
        if self.reader is None:
            logger.error(f"[Manager-{self.account_id}] StreamReader 未初始化")
            return None

        try:
            # 读取4字节长度前缀
            length_bytes = await self.reader.readexactly(4)
            length = struct.unpack(">I", length_bytes)[0]

            # 读取JSON内容
            json_bytes = await self.reader.readexactly(length)
            message: Dict[str, Any] = json.loads(json_bytes.decode("utf-8"))  # type: ignore[no-any-return]

            return message

        except asyncio.IncompleteReadError:
            return None
        except Exception as e:
            logger.error(f"[Manager-{self.account_id}] 接收消息失败: {e}")
            return None

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """
        处理接收到的消息

        Args:
            message: 消息内容
        """
        message_type = message.get("type")
        if message_type is None:
            logger.warning(f"[Manager-{self.account_id}] 消息中缺少 'type' 字段")
            return

        # 检查是否是响应消息
        if message_type == "response":
            # 响应消息
            request_id = message.get("request_id")
            if not request_id:
                logger.error(f"响应消息缺少request_id，{message}")
                return
            # 这是响应消息
            future = self._pending_requests.pop(request_id, None)
            if future and not future.done():
                # data 可能为 None，需要处理
                status = message.get("status")
                message = message.get("message") or ""
                if status == "error":
                    future.set_exception(Exception(f"请求失败:{message}"))
                else:
                    future.set_result(message.get("data") or {})
            return
        else:
            # 这是推送消息
            data = message.get("data", {})
            # 调用注册的处理器
            handler = self.on_data_callback
            if handler:
                try:
                    if inspect.iscoroutinefunction(handler):
                        await handler(message_type, data)
                    else:
                        handler(message_type, data)
                except Exception as e:
                    logger.error(
                        f"[Manager-{self.account_id}] 处理消息 [{message_type}] 时出错: {e}"
                    )
            else:
                logger.warning(f"[Manager-{self.account_id}] 未注册的消息类型: {message_type}")

    def is_connected(self) -> bool:
        """
        检查是否连接到Trader

        Returns:
            是否连接
        """
        # 检查连接状态并验证writer是否仍然有效
        if not self.connected or not self.writer:
            return False
        # 检查writer是否已关闭
        if self.writer.is_closing():
            return False
        return True

    def set_disconnect_callback(self, callback: Callable[[], None]) -> None:
        """
        设置连接断开回调

        Args:
            callback: 连接断开时的回调函数
        """
        self._on_disconnect_callback = callback

    async def _notify_disconnection(self) -> None:
        """通知连接已断开"""
        # 标记连接被服务端关闭
        self._connection_closed_by_server = True

        if self._on_disconnect_callback:
            try:
                if asyncio.iscoroutinefunction(self._on_disconnect_callback):
                    await self._on_disconnect_callback()
                else:
                    self._on_disconnect_callback()
            except Exception as e:
                logger.error(f"[Manager-{self.account_id}] 执行断开回调时出错: {e}")

    async def _reconnect_loop(self) -> None:
        """
        自动重连循环

        当连接断开时，自动尝试重新连接
        """
        attempt = 0

        while self._auto_reconnect:
            if self.is_connected():
                # 连接正常，等待一段时间后再次检查
                await asyncio.sleep(1)
                continue

            # 检查是否达到最大重连次数
            if self._max_reconnect_attempts > 0 and attempt >= self._max_reconnect_attempts:
                logger.error(
                    f"[Manager-{self.account_id}] 重连失败，已达到最大重连次数 "
                    f"({self._max_reconnect_attempts})"
                )
                break

            attempt += 1
            logger.info(
                f"[Manager-{self.account_id}] 尝试重新连接... ({attempt}/"
                f"{self._max_reconnect_attempts if self._max_reconnect_attempts > 0 else '∞'})"
            )

            try:
                # 尝试连接
                success = await self.connect(
                    retry_interval=self._reconnect_interval,
                    max_retries=1  # 每次重连只尝试一次
                )

                if success:
                    logger.info(f"[Manager-{self.account_id}] 重连成功")
                    attempt = 0  # 重置重连计数
                    # 通知重连成功
                    self._connection_closed_by_server = False
                else:
                    logger.warning(f"[Manager-{self.account_id}] 重连失败，将在{self._reconnect_interval}秒后重试")
                    await asyncio.sleep(self._reconnect_interval)

            except Exception as e:
                logger.error(f"[Manager-{self.account_id}] 重连时出错: {e}")
                await asyncio.sleep(self._reconnect_interval)

    def start_auto_reconnect(self) -> None:
        """启动自动重连"""
        if self._reconnect_task is None or self._reconnect_task.done():
            self._auto_reconnect = True
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())
            logger.info(f"[Manager-{self.account_id}] 已启动自动重连")

    def stop_auto_reconnect(self) -> None:
        """停止自动重连"""
        self._auto_reconnect = False
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            logger.info(f"[Manager-{self.account_id}] 已停止自动重连")
