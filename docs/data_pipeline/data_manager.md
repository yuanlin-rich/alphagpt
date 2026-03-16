# data_manager.py 文档

## 1. 文件概述

`data_manager.py` 是 `data_pipeline` 模块的核心编排器（orchestrator），负责协调数据获取、过滤、入库的完整流水线流程。它组合了 `DBManager`（数据库管理）、`BirdeyeProvider`（Birdeye 数据源）和 `DexScreenerProvider`（DexScreener 数据源）三个组件，实现了"发现趋势代币 -> 过滤 -> 入库代币信息 -> 批量拉取 OHLCV K线 -> 批量写入数据库"的完整数据同步管道。

## 2. 类与函数说明

### 类：`DataManager`

数据管道的主控类，封装了完整的日级数据同步逻辑。

#### `__init__(self)`

- **用途**：初始化 DataManager 实例，创建数据库管理器和数据提供者实例。
- **参数**：无
- **内部属性**：
  - `self.db` — `DBManager` 实例，用于数据库操作
  - `self.birdeye` — `BirdeyeProvider` 实例，Birdeye API 数据提供者
  - `self.dexscreener` — `DexScreenerProvider` 实例，DexScreener API 数据提供者

#### `async initialize(self)`

- **用途**：初始化数据库连接和表结构。
- **参数**：无
- **返回值**：`None`
- **行为**：依次调用 `self.db.connect()` 建立数据库连接池，再调用 `self.db.init_schema()` 创建/确认数据库表结构。

#### `async close(self)`

- **用途**：关闭数据库连接池，释放资源。
- **参数**：无
- **返回值**：`None`

#### `async pipeline_sync_daily(self)`

- **用途**：执行完整的日级数据同步管道，是核心业务方法。
- **参数**：无
- **返回值**：`None`
- **详细逻辑**：
  1. 从 Birdeye 获取趋势代币列表（付费用户最多 500 个，免费用户最多 100 个）
  2. 按流动性（`MIN_LIQUIDITY_USD`）、全稀释估值（`MIN_FDV` ~ `MAX_FDV`）进行过滤
  3. 将通过筛选的代币信息 upsert 到数据库 `tokens` 表
  4. 对每个代币创建异步任务获取 OHLCV 历史数据
  5. 分批（每批 20 个）并发执行 API 请求，将结果批量写入数据库 `ohlcv` 表

## 3. 调用关系图

```
+--------------------------------------------------------------+
|                     DataManager                               |
+--------------------------------------------------------------+
|                                                              |
|  __init__()                                                  |
|    |-- DBManager()            -> self.db                     |
|    |-- BirdeyeProvider()      -> self.birdeye                |
|    +-- DexScreenerProvider()  -> self.dexscreener            |
|                                                              |
|  initialize()                                                |
|    |-- self.db.connect()                                     |
|    +-- self.db.init_schema()                                 |
|                                                              |
|  close()                                                     |
|    +-- self.db.close()                                       |
|                                                              |
|  pipeline_sync_daily()                                       |
|    |-- self.birdeye.get_trending_tokens(limit)               |
|    |-- [过滤逻辑: liquidity / fdv 阈值]                       |
|    |-- self.db.upsert_tokens(db_tokens)                      |
|    |-- aiohttp.ClientSession(headers=...)                    |
|    |   |                                                     |
|    |   +-- self.birdeye.get_token_history(session, addr)     |
|    |       (并发, 每批 batch_size=20)                         |
|    |                                                         |
|    +-- self.db.batch_insert_ohlcv(records) [每批写入]         |
+--------------------------------------------------------------+

外部模块交互:
  config.py -----> Config.BIRDEYE_IS_PAID, Config.MIN_LIQUIDITY_USD,
                   Config.MIN_FDV, Config.MAX_FDV, Config.CHAIN
  db_manager.py -> DBManager
  providers/birdeye.py -----> BirdeyeProvider
  providers/dexscreener.py -> DexScreenerProvider
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `asyncio` | 标准库，异步编程支持（`asyncio.gather`） |
| `aiohttp` | 异步 HTTP 客户端，创建会话用于 API 请求 |
| `loguru` | 高级日志库，提供 `logger.info`、`logger.warning`、`logger.success` |

### 内部模块依赖

| 模块 | 导入对象 | 用途 |
|------|----------|------|
| `.config` | `Config` | 读取筛选阈值、付费状态、区块链名称等配置 |
| `.db_manager` | `DBManager` | 数据库连接、表操作 |
| `.providers.birdeye` | `BirdeyeProvider` | Birdeye API 数据获取 |
| `.providers.dexscreener` | `DexScreenerProvider` | DexScreener API 数据获取（当前未在管道中使用） |

## 5. 代码逻辑流程

```
开始
  |
  v
[Step 1] 获取趋势代币
  |-- 根据 Config.BIRDEYE_IS_PAID 确定 limit (500 或 100)
  |-- 调用 birdeye.get_trending_tokens(limit)
  |-- 记录日志: 原始候选数量
  |
  v
[Step 2] 过滤代币
  |-- 遍历候选列表
  |   |-- 检查 liquidity >= MIN_LIQUIDITY_USD
  |   |-- 检查 fdv >= MIN_FDV
  |   +-- 检查 fdv <= MAX_FDV (剔除巨型代币)
  |-- 记录日志: 过滤后数量
  |-- 若无代币通过过滤, 记录 warning 并返回
  |
  v
[Step 3] 代币信息入库
  |-- 构造 (address, symbol, name, decimals, chain) 元组列表
  +-- 调用 db.upsert_tokens() 写入/更新 tokens 表
  |
  v
[Step 4] 获取 OHLCV 历史数据
  |-- 创建 aiohttp 会话 (复用 birdeye.headers)
  |-- 为每个代币创建 get_token_history() 协程任务
  |-- 按 batch_size=20 分批执行:
  |   |-- asyncio.gather(*batch) 并发拉取
  |   |-- 展平结果列表
  |   |-- 调用 db.batch_insert_ohlcv(records) 批量写入
  |   +-- 记录日志: 当前批次进度和写入蜡烛数
  |
  v
[完成] 记录总蜡烛数
```

> **注意**：虽然 `DexScreenerProvider` 在构造函数中被实例化，但在当前的 `pipeline_sync_daily` 方法中并未使用，推测是为后续扩展预留的备选数据源。
