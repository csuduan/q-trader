# 系统初始化

## 概述

`src/init_sys.py` 用于初始化系统数据库和参数。首次部署或需要重置系统时，请运行此脚本。

## 使用方法

### 1. 使用默认配置初始化

```bash
python -m src.init_sys
```

这会：
- 从 `./config/config.yaml` 读取配置
- 使用配置文件中的数据库路径（`config.paths.database`）
- 重建所有数据库表
- 从配置文件导入定时任务到数据库
- 从配置文件初始化风控参数到数据库

### 2. 指定配置文件

```bash
python -m src.init_sys /path/to/config.yaml
```

### 3. 指定数据库路径

```bash
python -m src.init_sys /path/to/config.yaml /path/to/database.db
```

## 初始化内容

### 1. 数据库表重建

系统会删除并重新创建所有数据库表，包括：
- accounts (账户信息)
- positions (持仓信息)
- trades (成交记录)
- orders (委托单)
- jobs (定时任务配置)
- system_params (系统参数)
- alarms (告警信息)
- quotes (行情数据)
- rotation_instructions (换仓指令)
- switchPos_import (订单文件记录)

**注意：此操作会删除所有现有数据，请谨慎使用！**

### 2. 定时任务初始化

从 `config.yaml` 的 `scheduler.jobs` 部分读取定时任务配置，并导入到 `jobs` 表中。

包括以下类型的任务：
- 连接任务（盘前自动连接）
- 断开连接任务（盘后自动断开）
- 换仓任务（开盘后自动换仓）
- 订单扫描任务（扫描换仓文件）
- 导出任务（收盘后处理）
- 系统任务（清理旧告警等）

### 3. 风控参数初始化

从 `config.yaml` 的 `risk_control` 部分读取风控参数，并导入到 `system_params` 表中。

参数包括：
- `risk_control.max_daily_orders`: 每日最大报单数量
- `risk_control.max_daily_cancels`: 每日最大撤单数量
- `risk_control.max_order_volume`: 单次最大报单手数
- `risk_control.max_split_volume`: 最大拆单手数
- `risk_control.order_timeout`: 报单超时时间（秒）

## 正常启动

系统正常启动时，不再从 config.yaml 同步风控参数和定时任务，而是从数据库加载：

1. **风控参数**：TradingEngine 在连接到 TqSdk 后自动从 `system_params` 表加载风控配置
2. **定时任务**：TaskScheduler 从 `jobs` 表加载任务配置

**重要**：如果数据库中没有风控参数，系统会使用 config.yaml 中的默认值并记录警告日志。因此首次部署后，务必运行 `python -m src.init_sys` 初始化数据库参数。

## 修改系统参数

### 通过API修改

系统提供 RESTful API 来管理系统参数：

```bash
# 获取所有系统参数
GET /api/system-params

# 获取指定分组参数
GET /api/system-params/group/risk_control

# 获取单个参数
GET /api/system-params/risk_control.max_daily_orders

# 更新参数
PUT /api/system-params/risk_control.max_daily_orders
Body: {"param_value": "2000"}
```

### 修改风控参数

修改风控参数后，系统会自动使用新值：

```bash
# 修改每日最大报单次数
curl -X PUT http://localhost:8000/api/system-params/risk_control.max_daily_orders \
  -H "Content-Type: application/json" \
  -d '{"param_value": "2000"}'
```

修改后的参数在下次报单时自动生效，无需重启系统。

### 修改定时任务

定时任务存储在 `jobs` 表中，可以通过以下方式修改：

1. **直接修改数据库**：更新 `jobs` 表中的 `enabled`、`cron_expression` 等字段
2. **通过API修改**：如果有提供相关API
3. **重新初始化系统**：运行 `python -m src.init_sys` 会从 config.yaml 重新初始化所有任务

**注意**：系统启动时不会从 config.yaml 覆盖数据库中已存在的任务，只会创建缺失的任务。

## 注意事项

1. **首次部署**：必须运行 `python -m src.init_sys` 初始化系统
2. **重置系统**：运行初始化脚本会删除所有数据，请先备份
3. **配置文件同步**：
   - 系统启动时不会从 config.yaml 覆盖数据库中的现有数据
   - config.yaml 仅在数据库中不存在对应记录时才被使用
   - 需要重新初始化系统（`python -m src.init_sys`）才能强制从 config.yaml 同步
4. **运行时修改**：建议通过 API 修改参数，而不是直接修改数据库
5. **参数验证**：风控参数必须为正整数，否则系统会使用默认值

## 示例流程

### 首次部署

```bash
# 1. 复制配置文件
cp config/config.example.yaml config/config.yaml

# 2. 修改配置文件
vim config/config.yaml

# 3. 初始化系统（创建数据库表并导入参数和任务）
python -m src.init_sys

# 4. 启动系统（自动从数据库加载风控参数和任务）
python -m src.main
```

### 修改风控参数

```bash
# 运行时通过API修改（无需重启）
curl -X PUT http://localhost:8000/api/system-params/risk_control.max_daily_orders \
  -H "Content-Type: application/json" \
  -d '{"param_value": "2000"}'

# 验证修改
curl http://localhost:8000/api/system-params/risk_control.max_daily_orders
```

### 修改定时任务

方法1：通过数据库修改（无需重启）
```bash
# 暂停某个任务
sqlite3 storage/trading.db "UPDATE jobs SET enabled = 0 WHERE job_id = 'pre_market_connect';"

# 修改cron表达式
sqlite3 storage/trading.db "UPDATE jobs SET cron_expression = '50 8 * * *' WHERE job_id = 'pre_market_connect';"
```

方法2：通过API修改（如果提供相关接口）

方法3：重新初始化系统（强制从config.yaml同步）
```bash
# 1. 修改 config.yaml
vim config/config.yaml
# 2. 运行初始化（会删除所有数据！）
python -m src.init_sys
# 3. 重启系统
python -m src.main
```

### 更新风控参数

系统启动时会自动从数据库加载风控参数，无需重启即可通过API修改并立即生效：

```bash
# 通过API修改（推荐）
curl -X PUT http://localhost:8000/api/system-params/risk_control.max_daily_orders \
  -H "Content-Type: application/json" \
  -d '{"param_value": "2000"}'
```

修改参数后，下次报单时会自动使用新值。

**注意**：如果需要立即重新加载风控配置，可以调用 TradingEngine 的 `reload_risk_control_config()` 方法。

## 故障排查

### 数据库未初始化

如果启动时提示缺少参数，请运行：

```bash
python -m src.init_sys
```

### 参数不生效

检查数据库中的参数值：

```bash
sqlite3 storage/trading.db "SELECT param_key, param_value FROM system_params WHERE group='risk_control';"
```

如果参数值不正确，通过API更新或重新初始化系统。
