# data_pipeline 模块文档

## 1. 模块概述

`data_pipeline` 是 AlphaGPT 项目的数据采集与处理模块，负责从链上数据源（Birdeye、DexScreener）自动发现并拉取 Solana 链上的热门代币信息及其历史 OHLCV（开高低收量）K 线数据，经过筛选和清洗后存入 PostgreSQL/TimescaleDB 数据库，为下游的量化因子计算和策略回测提供标准化的数据基础。

核心工作流程：
1. 通过 Birdeye API 获取热门代币列表
2. 根据流动性（liquidity）和完全稀释估值（FDV）进行筛选过滤
3. 将合格代币元信息写入数据库 `tokens` 表
4. 异步并发拉取每个代币的历史 OHLCV 数据
5. 批量写入数据库 `ohlcv` 表（支持 TimescaleDB 超表）
6. 提供数据清洗和基础量化因子计算能力（对数收益率、波动率、量能冲击、趋势方向）

---

## 2. 文件说明

| 文件 | 用途 | 核心内容 |
|------|------|----------|
| `config.py` | 全局配置中心 | 定义 `Config` 类，集中管理数据库连接参数、Birdeye API 密钥、链名称、K 线周期、筛选阈值（最小流动性/FDV）、并发数、历史天数等配置项。通过 `dotenv` 从环境变量加载敏感信息。 |
| `data_manager.py` | 数据管线编排器 | 定义 `DataManager` 类，作为整个 pipeline 的总调度器。组合 `DBManager`、`BirdeyeProvider`、`DexScreenerProvider`，实现 `pipeline_sync_daily()` 方法完成"发现代币 -> 筛选 -> 入库 -> 拉取K线 -> 批量写入"的完整流水线。 |
| `db_manager.py` | 数据库管理层 | 定义 `DBManager` 类，封装 PostgreSQL（asyncpg）连接池管理、表结构初始化（tokens/ohlcv 表 + TimescaleDB 超表）、代币 upsert、OHLCV 批量写入等数据库操作。 |
| `fetcher.py` | 旧版数据抓取器（独立实现） | 定义 `BirdeyeFetcher` 类，直接通过 Birdeye API 获取热门代币和历史 K 线。该文件是早期实现，功能已被 `providers/birdeye.py` 取代，但仍保留在代码库中。 |
| `processor.py` | 数据清洗与因子计算 | 定义 `DataProcessor` 类，提供静态方法：`clean_ohlcv()` 负责去重、排序、缺失值填充、过滤零价格；`add_basic_factors()` 计算对数收益率、已实现波动率、量能冲击比、价格趋势方向等基础量化因子。 |
| `run_pipeline.py` | 入口脚本 | pipeline 的启动入口。校验 API Key 是否存在，实例化 `DataManager` 并依次调用初始化、执行管线、关闭连接。通过 `asyncio.run()` 驱动整个异步流程。 |

---

## 3. 架构图

```
+------------------------------------------------------------------+
|                        run_pipeline.py                            |
|                     (入口: asyncio.run)                           |
|                            |                                      |
|                            v                                      |
|  +--------------------------------------------------------+      |
|  |                   DataManager                           |      |
|  |               (data_manager.py)                         |      |
|  |                                                         |      |
|  |  pipeline_sync_daily()                                  |      |
|  |    |                                                    |      |
|  |    |  1. 发现代币    2. 筛选      3. 入库              |      |
|  |    |  4. 拉取K线     5. 批量写入                       |      |
|  |    |                                                    |      |
|  |    +--------+------------------+                        |      |
|  |             |                  |                         |      |
|  |             v                  v                         |      |
|  |  +------------------+  +---------------+                |      |
|  |  | BirdeyeProvider  |  | DBManager     |                |      |
|  |  | (providers/)     |  | (db_manager)  |                |      |
|  |  +------------------+  +---------------+                |      |
|  |  | get_trending_    |  | connect()     |                |      |
|  |  |   tokens()       |  | init_schema() |                |      |
|  |  | get_token_       |  | upsert_       |                |      |
|  |  |   history()      |  |   tokens()    |                |      |
|  |  +--------+---------+  | batch_insert_ |                |      |
|  |           |             |   ohlcv()     |                |      |
|  |           |             +-------+-------+                |      |
|  |           |                     |                        |      |
|  +-----------|---------------------|-----------------------+      |
|              |                     |                              |
|              v                     v                              |
|      +--------------+      +----------------+                    |
|      | Birdeye API  |      | PostgreSQL /   |                    |
|      | (HTTP REST)  |      | TimescaleDB    |                    |
|      +--------------+      +----------------+                    |
|                                                                  |
|  +----------------------------------------------------------+   |
|  |                 独立工具组件                               |   |
|  |                                                           |   |
|  |  +-------------------+    +---------------------+         |   |
|  |  | BirdeyeFetcher    |    | DataProcessor       |         |   |
|  |  | (fetcher.py)      |    | (processor.py)      |         |   |
|  |  | [旧版/备用]       |    |                     |         |   |
|  |  | get_trending_     |    | clean_ohlcv()       |         |   |
|  |  |   tokens()        |    | add_basic_factors() |         |   |
|  |  | get_token_        |    +---------------------+         |   |
|  |  |   history()       |                                    |   |
|  |  +-------------------+                                    |   |
|  +----------------------------------------------------------+   |
+------------------------------------------------------------------+

调用关系:
  run_pipeline.py
       |
       +---> DataManager.initialize()
       |         |---> DBManager.connect()
       |         +---> DBManager.init_schema()
       |
       +---> DataManager.pipeline_sync_daily()
       |         |---> BirdeyeProvider.get_trending_tokens()
       |         |---> Config (筛选阈值)
       |         |---> DBManager.upsert_tokens()
       |         |---> BirdeyeProvider.get_token_history()  [并发批次]
       |         +---> DBManager.batch_insert_ohlcv()
       |
       +---> DataManager.close()
                 +---> DBManager.close()

配置流向:
  .env 文件 --> dotenv --> Config 类 --> 所有模块读取
```

---

## 4. 依赖关系

### 4.1 内部模块依赖（data_pipeline 内部）

```
run_pipeline.py
  |- data_manager.DataManager
  |- config.Config

data_manager.py
  |- config.Config
  |- db_manager.DBManager
  |- providers.birdeye.BirdeyeProvider
  |- providers.dexscreener.DexScreenerProvider

db_manager.py
  |- config.Config

fetcher.py
  |- config.Config

processor.py
  |- (无内部依赖，独立工具类)
```

### 4.2 对 alphagpt 其他模块的依赖

当前 `data_pipeline` 模块**不依赖** alphagpt 项目中的其他模块，是一个相对独立的数据层子系统。

### 4.3 外部第三方依赖

| 包名 | 用途 | 使用位置 |
|------|------|----------|
| `asyncpg` | PostgreSQL 异步驱动，连接池管理与高性能批量写入 | `db_manager.py` |
| `aiohttp` | 异步 HTTP 客户端，调用 Birdeye/DexScreener REST API | `data_manager.py`, `fetcher.py`, `providers/` |
| `python-dotenv` | 从 `.env` 文件加载环境变量 | `config.py` |
| `loguru` | 结构化日志记录 | `data_manager.py`, `db_manager.py`, `fetcher.py`, `processor.py`, `run_pipeline.py` |
| `pandas` | DataFrame 数据结构，用于数据清洗和因子计算 | `fetcher.py`, `processor.py` |
| `numpy` | 数值计算（对数、滚动窗口统计） | `processor.py` |

### 4.4 标准库依赖

| 模块 | 用途 |
|------|------|
| `asyncio` | 异步事件循环与并发控制（Semaphore） |
| `os` | 读取环境变量 |
| `datetime` | 时间戳转换与时间范围计算 |
| `abc` | 抽象基类定义（`providers/base.py`） |

---

## 5. 关键类/函数

### 5.1 `Config` 类 (`config.py`)

全局配置类，所有属性为类变量，无需实例化即可访问。

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `DB_USER` | `str` | `"postgres"` | 数据库用户名（环境变量 `DB_USER`） |
| `DB_PASSWORD` | `str` | `"password"` | 数据库密码（环境变量 `DB_PASSWORD`） |
| `DB_HOST` | `str` | `"localhost"` | 数据库主机地址 |
| `DB_PORT` | `str` | `"5432"` | 数据库端口 |
| `DB_NAME` | `str` | `"crypto_quant"` | 数据库名称 |
| `DB_DSN` | `str` | 自动拼接 | PostgreSQL 连接字符串 |
| `CHAIN` | `str` | `"solana"` | 目标区块链 |
| `TIMEFRAME` | `str` | `"1m"` | K 线周期（支持 `1m`、`15min`） |
| `MIN_LIQUIDITY_USD` | `float` | `500000.0` | 最小流动性过滤阈值（美元） |
| `MIN_FDV` | `float` | `10000000.0` | 最小完全稀释估值（美元） |
| `MAX_FDV` | `float` | `inf` | 最大 FDV 上限，用于剔除超大盘代币 |
| `BIRDEYE_API_KEY` | `str` | `""` | Birdeye API 密钥（环境变量） |
| `BIRDEYE_IS_PAID` | `bool` | `True` | 是否为付费账户（影响请求数量上限） |
| `USE_DEXSCREENER` | `bool` | `False` | 是否启用 DexScreener 数据源 |
| `CONCURRENCY` | `int` | `20` | 异步并发请求数 |
| `HISTORY_DAYS` | `int` | `7` | 拉取历史数据的天数 |

---

### 5.2 `DataManager` 类 (`data_manager.py`)

数据管线总调度器，协调数据提供者和数据库管理器完成端到端的数据采集流程。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__()` | 无 | 无 | 初始化 `DBManager`、`BirdeyeProvider`、`DexScreenerProvider` 实例 |
| `initialize()` | 无 | `None` | 建立数据库连接并初始化表结构 |
| `close()` | 无 | `None` | 关闭数据库连接池 |
| `pipeline_sync_daily()` | 无 | `None` | 执行完整的每日数据同步管线：发现代币 -> 筛选 -> 入库 -> 拉取K线 -> 批量写入。付费账户拉取 500 个候选代币，免费账户 100 个。以 batch_size=20 的批次并发请求 OHLCV 数据。 |

---

### 5.3 `DBManager` 类 (`db_manager.py`)

数据库访问层，基于 `asyncpg` 连接池封装所有数据库操作。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `connect()` | 无 | `None` | 创建 asyncpg 连接池（使用 `Config.DB_DSN`） |
| `close()` | 无 | `None` | 关闭连接池 |
| `init_schema()` | 无 | `None` | 创建 `tokens` 表（address 主键）和 `ohlcv` 表（time+address 复合主键）。尝试将 ohlcv 转换为 TimescaleDB 超表；若扩展不存在则降级为普通表。创建 address 索引。 |
| `upsert_tokens(tokens)` | `tokens`: `list[tuple]`，每个元素为 `(address, symbol, name, decimals, chain)` | `None` | 批量插入/更新代币信息。冲突时更新 symbol 和 last_updated 时间戳。 |
| `batch_insert_ohlcv(records)` | `records`: `list[tuple]`，每个元素为 `(time, address, open, high, low, close, volume, liquidity, fdv, source)` | `None` | 使用 `copy_records_to_table` 高性能批量写入 OHLCV 数据。自动忽略重复记录（UniqueViolationError）。 |

**数据库表结构：**

```sql
-- tokens 表
CREATE TABLE tokens (
    address TEXT PRIMARY KEY,
    symbol TEXT,
    name TEXT,
    decimals INT,
    chain TEXT,
    last_updated TIMESTAMP DEFAULT NOW()
);

-- ohlcv 表（可选 TimescaleDB 超表）
CREATE TABLE ohlcv (
    time TIMESTAMP NOT NULL,
    address TEXT NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    liquidity DOUBLE PRECISION,
    fdv DOUBLE PRECISION,
    source TEXT,
    PRIMARY KEY (time, address)
);
```

---

### 5.4 `BirdeyeFetcher` 类 (`fetcher.py`)

> 注意：这是早期独立实现的抓取器，当前主流程已使用 `providers/birdeye.py` 中的 `BirdeyeProvider`。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `get_trending_tokens(limit)` | `limit`: `int`，默认 `100` | `list[dict]` | 获取 Birdeye 热门代币列表 |
| `get_token_history(session, address, days)` | `session`: `aiohttp.ClientSession`；`address`: `str`；`days`: `int`，默认 `30` | `list[tuple] \| None` | 获取指定代币的历史 OHLCV 数据。内置信号量限流（5 并发），遇到 429 状态码自动等待 2 秒后重试。返回 8 元素 tuple 列表。 |

---

### 5.5 `DataProcessor` 类 (`processor.py`)

数据清洗与量化因子计算工具类，所有方法均为静态方法。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `clean_ohlcv(df)` | `df`: `pandas.DataFrame`，包含 `time`, `address`, `open`, `high`, `low`, `close`, `volume` 列 | `DataFrame` | 数据清洗：去重（保留最新）、按时间排序、前向填充 close、用 close 填充其余价格缺失值、volume 缺失填 0、过滤价格接近零的记录（< 1e-15） |
| `add_basic_factors(df)` | `df`: `pandas.DataFrame`，需包含 `close` 和 `volume` 列 | `DataFrame` | 计算并添加以下因子列：`log_ret`（对数收益率）、`volatility`（20 周期已实现波动率）、`vol_shock`（量能冲击比 = 当前成交量/20周期均量）、`trend`（价格趋势方向，+1/-1，基于 60 周期均线） |

**因子计算公式：**

```
log_ret    = ln(close_t / close_{t-1})
volatility = std(log_ret, window=20)
vol_shock  = volume_t / (MA(volume, 20) + 1e-6)
trend      = +1 if close > MA(close, 60) else -1
```

---

### 5.6 `main()` 函数 (`run_pipeline.py`)

| 参数 | 返回值 | 说明 |
|------|--------|------|
| 无 | `None` | Pipeline 入口函数。检查 `BIRDEYE_API_KEY` 是否配置，创建 `DataManager` 实例，依次调用 `initialize()` 和 `pipeline_sync_daily()`，异常时记录日志，最终确保关闭数据库连接。通过 `asyncio.run(main())` 启动。 |

**使用方式：**

```bash
python -m data_pipeline.run_pipeline
```
