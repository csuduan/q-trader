"""
Socket通讯工具模块

提供Socket服务器和客户端实现，用于Trader和Manager之间的通信。

V2版本（推荐）:
- SocketServer V2: 标准协议服务器，支持健康检查、统计信息
- SocketClient V2: 标准协议客户端，支持自动重连、心跳检测

工具类:
- BackoffStrategy: 退避策略，用于重连间隔计算
- HealthChecker: 健康检查器
- RequestHandlerRegistry: 请求处理器注册表
"""

# 协议相关
from src.utils.ipc.protocol import (
    MessageBody,
    MessageProtocol,
    MessageType,
    create_error,
    create_heartbeat,
    create_push,
    create_request,
    create_response,
)

# V1版本（向后兼容）
from src.utils.ipc.socket_client import SocketClient as SocketClientV1
from src.utils.ipc.socket_client_v2 import SocketClient
from src.utils.ipc.socket_server import SocketServer as SocketServerV1
from src.utils.ipc.socket_server import request

# V2版本（推荐）
from src.utils.ipc.socket_server_v2 import SocketServer
from src.utils.ipc.socket_server_v2 import request as request_v2

# 工具类
from src.utils.ipc.utils import (
    BackoffStrategy,
    HealthChecker,
    RequestHandlerRegistry,
    generate_request_id,
)

__all__ = [
    # V1版本（向后兼容）
    "SocketClientV1",
    "SocketServerV1",
    "request",
    # V2版本（推荐）
    "SocketClient",
    "SocketServer",
    "request_v2",
    # 协议相关
    "MessageType",
    "MessageBody",
    "MessageProtocol",
    "create_request",
    "create_response",
    "create_heartbeat",
    "create_push",
    "create_error",
    # 工具类
    "BackoffStrategy",
    "HealthChecker",
    "RequestHandlerRegistry",
    "generate_request_id",
]
