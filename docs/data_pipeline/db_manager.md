# db_manager.py 文档

## 1. 文件概述

`db_manager.py` 是 `data_pipeline` 模块的数据库管理层，封装了与 PostgreSQL（可选 TimescaleDB 扩展）数据库的所有交互逻辑。它负责管理连接池、初始化数据表结构、执行代币信息的 upsert 操作以及 OHLCV K线数据的高性能批量写入。该模块使用 `asyncpg` 异步驱动，与整个管道的异步架构保持一致。

## 2. 类与函数说明

### 类：`DBManager`

数据库操作的核心管理类，封装了连接池管理和所有数据库 CRUD 操作。

#### `__init__(self)`

- **用途**：初始化 DBManager 实例。
- **参数**：无
- **内部属性**：
  - `self.pool` — `asyncpg.Pool | None`，数据库连接池，初始为 `None`

#### `async connect(self)`

- **用途**：创建 asyncpg 连接池，连接到 PostgreSQL 数据库。
- **参数**：无
- **返回值**：`None`
- **行为**：若连接池尚未建立（`self.pool is None`），使用 `Config.DB_DSN` 创建连接池，并记录日志。具有幂等性 -- 多次调用不会重复创建连接池。

#### `async close(self)`

- **用途**：关闭数据库连接池。
- **参数**：无
- **返回值**：`None`
- **行为**：若连接池存在则关闭。

#### `async init_schema(self)`

- **用途**：初始化数据库表结构，包括建表、建索引、可选的 TimescaleDB 超表转换。
- **参数**：无
- **返回值**：`None`
- **创建的表结构**：
  - **`tokens` 表**：
    | 字段 | 类型 | 说明 |
    |------|------|------|
    | `address` | `TEXT PRIMARY KEY` | 代币合约地址 |
    | `symbol` | `TEXT` | 代币符号 |
    | `name` | `TEXT` | 代币名称 |
    | `decimals` | `INT` | 精度位数 |
    | `chain` | `TEXT` | 所属区块链 |
    | `last_updated` | `TIMESTAMP` | 最后更新时间，默认 `NOW()` |
  - **`ohlcv` 表**：
    | 字段 | 类型 | 说明 |
    |------|------|------|
    | `time` | `TIMESTAMP NOT NULL` | K线时间（联合主键之一） |
    | `address` | `TEXT NOT NULL` | 代币地址（联合主键之一） |
    | `open` | `DOUBLE PRECISION` | 开盘价 |
    | `high` | `DOUBLE PRECISION` | 最高价 |
    | `low` | `DOUBLE PRECISION` | 最低价 |
    | `close` | `DOUBLE PRECISION` | 收盘价 |
    | `volume` | `DOUBLE PRECISION` | 成交量 |
    | `liquidity` | `DOUBLE PRECISION` | 流动性 |
    | `fdv` | `DOUBLE PRECISION` | 全稀释估值 |
    | `source` | `TEXT` | 数据来源标识 |
  - **索引**：`idx_ohlcv_address` — 在 `ohlcv` 表的 `address` 列上创建索引
  - **TimescaleDB**：尝试将 `ohlcv` 转换为 Hypertable（按 `time` 分区），若 TimescaleDB 扩展不可用则降级为普通 PostgreSQL 表

#### `async upsert_tokens(self, tokens)`

- **用途**：批量插入或更新代币信息到 `tokens` 表。
- **参数**：
  - `tokens` — `list[tuple]`，每个元组格式为 `(address, symbol, name, decimals, chain)`
- **返回值**：`None`
- **行为**：使用 `INSERT ... ON CONFLICT DO UPDATE` 语义，若地址已存在则更新 `symbol` 和 `last_updated`。若传入空列表则直接返回。

#### `async batch_insert_ohlcv(self, records)`

- **用途**：高性能批量写入 OHLCV K线数据到 `ohlcv` 表。
- **参数**：
  - `records` — `list[tuple]`，每个元组包含 `(time, address, open, high, low, close, volume, liquidity, fdv, source)`
- **返回值**：`None`
- **行为**：使用 `asyncpg` 的 `copy_records_to_table` 方法（基于 PostgreSQL COPY 协议）实现高速批量写入，超时时间 60 秒。遇到主键重复（`UniqueViolationError`）时静默忽略；其他异常记录错误日志。若传入空列表则直接返回。

## 3. 调用关系图

```
+-----------------------------------------------------------+
|                       DBManager                            |
+-----------------------------------------------------------+
|                                                           |
|  __init__()                                               |
|    +-- self.pool = None                                   |
|                                                           |
|  connect()                                                |
|    +-- asyncpg.create_pool(dsn=Config.DB_DSN)             |
|                                                           |
|  close()                                                  |
|    +-- self.pool.close()                                  |
|                                                           |
|  init_schema()                                            |
|    |-- pool.acquire() -> conn                             |
|    |-- conn.execute(CREATE TABLE tokens ...)              |
|    |-- conn.execute(CREATE TABLE ohlcv ...)               |
|    |-- conn.execute(create_hypertable ...)  [可选]         |
|    +-- conn.execute(CREATE INDEX ...)                     |
|                                                           |
|  upsert_tokens(tokens)                                    |
|    |-- pool.acquire() -> conn                             |
|    +-- conn.executemany(INSERT ... ON CONFLICT ...)       |
|                                                           |
|  batch_insert_ohlcv(records)                              |
|    |-- pool.acquire() -> conn                             |
|    +-- conn.copy_records_to_table('ohlcv', ...)           |
+-----------------------------------------------------------+

被调用方:
  data_manager.py -> DataManager
    |-- initialize() 调用 connect(), init_schema()
    |-- pipeline_sync_daily() 调用 upsert_tokens(), batch_insert_ohlcv()
    +-- close() 调用 close()
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `asyncpg` | PostgreSQL 异步驱动，提供连接池、SQL执行、COPY 批量写入 |
| `loguru` | 日志记录 |

### 内部模块依赖

| 模块 | 导入对象 | 用途 |
|------|----------|------|
| `.config` | `Config` | 获取数据库 DSN 连接字符串 (`Config.DB_DSN`) |

## 5. 代码逻辑流程

### 连接与初始化流程

```
connect()
  |-- 检查 self.pool 是否为 None
  |   |-- 是: 调用 asyncpg.create_pool(dsn) 创建连接池
  |   +-- 否: 跳过 (幂等)
  v
init_schema()
  |-- 从连接池获取一个连接
  |-- 执行 CREATE TABLE IF NOT EXISTS tokens (...)
  |-- 执行 CREATE TABLE IF NOT EXISTS ohlcv (...)
  |-- 尝试 create_hypertable('ohlcv', 'time')
  |   |-- 成功: 日志记录 "Converted to Hypertable"
  |   +-- 失败: 降级警告 "TimescaleDB not found"
  +-- 执行 CREATE INDEX IF NOT EXISTS idx_ohlcv_address
```

### 数据写入流程

```
upsert_tokens(tokens)
  |-- 空列表检查 -> 提前返回
  |-- 获取连接
  +-- executemany: INSERT ... ON CONFLICT(address) DO UPDATE
      (更新 symbol 和 last_updated)

batch_insert_ohlcv(records)
  |-- 空列表检查 -> 提前返回
  |-- 获取连接
  +-- copy_records_to_table('ohlcv', records, columns=[...], timeout=60)
      |-- 成功: 正常返回
      |-- UniqueViolationError: 静默忽略 (重复数据)
      +-- 其他异常: 记录错误日志
```

> **设计亮点**：使用 `copy_records_to_table` 而非逐条 INSERT，利用 PostgreSQL COPY 协议实现高吞吐写入，特别适合大量 K线数据的批量入库场景。
