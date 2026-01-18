# Q-Trader自动化交易系统

基于天勤量化API (TqSdk) 开发的自动化交易程序，支持配置文件管理、行情订阅、指令执行、数据持久化、RESTful API和Vue管理界面。

## 功能特性

- **配置管理**: 支持YAML配置文件，可配置天勤账号、交易参数、风控参数等
- **行情订阅**: 支持订阅分钟K线行情数据
- **订单扫描**: 自动扫描CSV格式的交易指令文件并执行
- **风控模块**: 支持单日最大报单次数、撤单次数、单笔最大手数等风控参数
- **数据持久化**: 使用SQLite存储账户、持仓、成交、委托单等数据
- **RESTful API**: 提供完整的API接口，支持账户、持仓、成交、委托单查询及手动报单
- **WebSocket实时推送**: 支持实时推送账户、持仓、成交、委托单等数据更新
- **Vue管理界面**: (待开发) 基于Vue 3 + Vite的前端管理界面

## 项目结构

```
py-trade/
├── config/
│   ├── config.yaml           # 主配置文件
│   └── config.example.yaml   # 配置文件示例
├── src/
│   ├── main.py               # 主程序入口
│   ├── config_loader.py      # 配置加载器
│   ├── trading_engine.py     # 交易引擎核心
│   ├── order_scanner.py      # 订单文件扫描器
│   ├── risk_control.py       # 风控模块
│   ├── database.py           # 数据库操作
│   ├── models.py             # 数据模型
│   ├── api/
│   │   ├── app.py            # FastAPI应用
│   │   ├── routes/           # API路由
│   │   └── schemas.py        # API数据模型
│   └── utils/                # 工具模块
├── data/
│   ├── orders/               # 交易指令文件目录
│   └── logs/                 # 日志目录
├── storage/
│   └── trading.db            # SQLite数据库
└── requirements.txt          # Python依赖
```

## 快速开始

### 1. 安装依赖

```bash
conda activate mypy
pip install -r requirements.txt
```

### 2. 配置文件

复制示例配置文件并修改：

```bash
cp config/config.example.yaml config/config.yaml
```

编辑 `config/config.yaml`，填入您的天勤账号信息：

```yaml
tianqin:
  username: "your_username"
  password: "your_password"
```

### 3. 运行程序

```bash
python -m src.main
```

### 4. 访问API

程序启动后，可以访问：

- API文档: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws

## 交易指令CSV文件格式

在 `data/orders/` 目录下放置CSV文件，格式如下：

```csv
实盘账户,合约代码,交易所代码,开平类型,买卖方向,手数,价格,报单时间
SHFE.rb2505,SHFE,OPEN,BUY,5,0,09:30:00
SHFE.ag2505,SHFE,CLOSE,SELL,3,4500,
```

字段说明：
- **实盘账户**: 完整合约代码（如 SHFE.rb2505）
- **合约代码**: 交易所代码（如 SHFE）
- **交易所代码**: 开平类型（OPEN=开仓, CLOSE=平仓, CLOSETODAY=平今）
- **开平类型**: 买卖方向（BUY=买, SELL=卖）
- **买卖方向**: 手数
- **手数**: 价格（0=使用对手价，否则为限价）
- **价格**: 报单时间（格式HH:MM:SS，空则不限制）

## API接口

### 账户相关
- `GET /api/account` - 获取账户信息
- `GET /api/account/all` - 获取所有账户信息

### 持仓相关
- `GET /api/position` - 获取持仓列表
- `GET /api/position/{symbol}` - 获取指定合约持仓

### 成交相关
- `GET /api/trade` - 获取成交记录
- `GET /api/trade/{trade_id}` - 获取指定成交详情
- `GET /api/trade/order/{order_id}` - 获取指定委托单的成交记录

### 委托单相关
- `GET /api/order` - 获取委托单列表
- `GET /api/order/{order_id}` - 获取指定委托单详情
- `POST /api/order` - 手动报单
- `DELETE /api/order/{order_id}` - 撤销委托单

### K线数据
- `GET /api/kline` - 获取K线数据
- `GET /api/kline/{symbol}` - 获取指定合约K线数据

### 系统控制
- `GET /api/system/status` - 获取系统状态
- `POST /api/system/connect` - 连接到交易系统
- `POST /api/system/disconnect` - 断开连接
- `POST /api/system/pause` - 暂停交易
- `POST /api/system/resume` - 恢复交易

## WebSocket消息格式

### 连接

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
```

### 消息类型

- `account_update` - 账户信息更新
- `position_update` - 持仓信息更新
- `trade_update` - 新成交记录
- `order_update` - 委托单状态更新
- `kline_update` - K线数据更新
- `system_status` - 系统状态变化

### 消息格式

```json
{
  "type": "account_update",
  "data": {
    "account_id": "xxx",
    "balance": 100000.00,
    "available": 95000.00,
    ...
  },
  "timestamp": "2025-01-10T10:30:00"
}
```

## 配置说明

### 账户类型

支持三种账户类型：

1. **kq** - 快期模拟账户（默认）
2. **sim** - 本地模拟账户
3. **account** - 实盘账户（需配置交易账户信息）

### 风控参数

- `max_daily_orders` - 单日最大报单次数
- `max_daily_cancels` - 单日最大撤单次数
- `max_order_volume` - 单笔最大报单手数

### 行情订阅

- `subscribe_symbols` - 订阅的合约列表
- `kline_duration` - K线周期（秒），60=1分钟

## 开发计划

- [x] 项目基础搭建
- [x] 配置文件支持
- [x] 日志系统
- [x] 数据库和ORM模型
- [x] 交易引擎核心
- [x] 订单文件扫描器
- [x] 风控模块
- [x] RESTful API
- [x] WebSocket实时推送
- [x] Vue前端管理界面
- [ ] 单元测试
- [ ] 部署文档

## 前端管理界面

前端管理界面位于 `web/` 目录，使用 Vue 3 + Vite + Element Plus 开发。

### 前端功能

- **总览页面**: 显示账户概览、盈亏统计、风控信息和最近成交
- **账户管理**: 查看详细账户信息和资产状况
- **持仓管理**: 实时查看和管理持仓
- **成交记录**: 查看历史成交记录
- **委托单管理**: 手动报单、撤单、查看委托单状态
- **K线图表**: 使用 ECharts 展示K线走势图
- **系统控制**: 连接/断开交易系统、暂停/恢复交易

### 前端启动

```bash
cd web
npm install
npm run dev
```

访问 http://localhost:3000

### 前端技术栈

- **框架**: Vue 3 + TypeScript
- **构建工具**: Vite
- **UI组件**: Element Plus
- **图表**: ECharts
- **状态管理**: Pinia
- **路由**: Vue Router
- **HTTP客户端**: Axios
- **WebSocket**: 原生WebSocket

## 许可证

MIT License
