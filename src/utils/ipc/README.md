# IPC Socket 模块

高性能异步 Socket 通信模块，支持 Unix Domain Socket 和 TCP Socket。

## 版本说明

- **V1 版本** (`socket_client.py`, `socket_server.py`): 原始实现，向后兼容
- **V2 版本** (`socket_client_v2.py`, `socket_server_v2.py`): 推荐版本，功能更完善

## 快速开始

### V2 服务器端

```python
import asyncio
from src.utils.ipc import SocketServer, request

# 创建服务器
server = SocketServer(
    socket_path="/tmp/test.sock",
    account_id="test_account",
    enable_health_check=True,
    health_check_interval=30.0
)

# 方式1: 使用装饰器注册处理器
@request("echo")
async def handle_echo(data: dict) -> dict:
    return {"echo": data}

server.register_handler("echo", handle_echo)

# 方式2: 直接注册处理器
async def handle_add(data: dict) -> dict:
    a = data.get("a", 0)
    b = data.get("b", 0)
    return {"result": a + b}

server.register_handler("add", handle_add)

# 启动服务器
async def main():
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### V2 客户端

```python
import asyncio
from src.utils.ipc import SocketClient

async def main():
    # 创建客户端
    client = SocketClient(
        socket_path="/tmp/test.sock",
        account_id="test_account",
        auto_reconnect=True,           # 启用自动重连
        reconnect_interval=3.0,          # 重连间隔
        max_reconnect_attempts=0,      # 0表示无限重试
        heartbeat_interval=30.0,       # 心跳间隔
        request_timeout=10.0           # 请求超时
    )

    # 设置推送处理器
    @client.on_push("notification")
    async def handle_notification(push_type: str, data: dict):
        print(f"Received notification: {data}")

    # 设置回调
    client.set_connect_callback(lambda: print("Connected!"))
    client.set_disconnect_callback(lambda: print("Disconnected!"))

    # 连接服务器
    connected = await client.connect(max_retries=5)
    if not connected:
        print("Failed to connect")
        return

    # 发送请求
    response = await client.request("echo", {"message": "hello"})
    print(f"Echo response: {response}")

    response = await client.request("add", {"a": 10, "b": 20})
    print(f"Add response: {response}")

    # 健康检查
    healthy = await client.health_check()
    print(f"Health check: {healthy}")

    # 获取统计信息
    stats = client.get_stats()
    print(f"Client stats: {stats}")

    # 断开连接
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## 特性

### V2 版本特性

- **标准协议**: 统一的 MessageBody 格式，支持请求-响应、推送、心跳等消息类型
- **自动重连**: 带退避策略的自动重连机制
- **心跳检测**: 双向心跳保活，支持健康检查
- **请求-响应**: 完整的异步请求-响应模式，支持超时控制
- **推送消息**: 支持服务器向客户端推送消息
- **统计信息**: 连接数、消息数等统计信息
- **完善的错误处理**: 详细的日志记录和异常处理

### 工具类

#### BackoffStrategy - 退避策略

```python
from src.utils.ipc.utils import BackoffStrategy

# 创建退避策略
backoff = BackoffStrategy(
    initial_delay=0.5,    # 初始延迟
    max_delay=15.0,       # 最大延迟
    multiplier=1.5        # 增长倍数
)

# 获取延迟
delay = backoff.get_delay()

# 重置
backoff.reset()
```

#### HealthChecker - 健康检查器

```python
from src.utils.ipc.utils import HealthChecker

# 创建健康检查器
checker = HealthChecker(
    interval=5.0,    # 检查间隔
    timeout=3.0      # 超时时间
)

# 执行检查
healthy = await checker.check(heartbeat_func)
```

#### RequestHandlerRegistry - 处理器注册表

```python
from src.utils.ipc.utils import RequestHandlerRegistry

# 创建注册表
registry = RequestHandlerRegistry()

# 注册处理器
@registry.register("echo")
async def handle_echo(data):
    return {"echo": data}

# 获取处理器
handler = registry.get_handler("echo")
```

## 架构

```
src/utils/ipc/
├── __init__.py          # 模块导出
├── protocol.py          # 消息协议定义
├── utils.py             # 工具类
├── socket_client.py     # V1 客户端（向后兼容）
├── socket_server.py     # V1 服务器（向后兼容）
├── socket_client_v2.py  # V2 客户端（推荐）
└── socket_server_v2.py  # V2 服务器（推荐）
```

## 迁移指南

从 V1 迁移到 V2：

```python
# V1 版本
from src.utils.ipc import SocketClient, SocketServer

client = SocketClient(socket_path, account_id)

# V2 版本（新）
from src.utils.ipc import SocketClient, SocketServer

client = SocketClient(
    socket_path,
    account_id,
    auto_reconnect=True,  # 新增
    heartbeat_interval=30.0  # 新增
)
```

V2 版本保持向后兼容，V1 版本仍可正常使用。
