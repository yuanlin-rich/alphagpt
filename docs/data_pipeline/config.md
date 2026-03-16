# config.py 文档

## 1. 文件概述

`config.py` 是 `data_pipeline` 模块的全局配置文件，负责集中管理数据管道所需的所有配置参数。它通过环境变量（`.env` 文件）加载敏感信息（数据库凭证、API 密钥），并提供默认值作为兜底。所有配置项以类属性的形式暴露，供模块中的其他组件直接引用。

## 2. 类与函数说明

### 模块级行为

| 行为 | 说明 |
|------|------|
| `load_dotenv()` | 在模块导入时自动执行，将项目根目录下 `.env` 文件中的键值对加载为环境变量 |

### 类：`Config`

纯配置类，不包含任何方法，所有属性均为类级别属性（class attribute）。

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `DB_USER` | `str` | `"postgres"` | PostgreSQL 数据库用户名，从环境变量 `DB_USER` 读取 |
| `DB_PASSWORD` | `str` | `"password"` | 数据库密码，从环境变量 `DB_PASSWORD` 读取 |
| `DB_HOST` | `str` | `"localhost"` | 数据库主机地址，从环境变量 `DB_HOST` 读取 |
| `DB_PORT` | `str` | `"5432"` | 数据库端口号，从环境变量 `DB_PORT` 读取 |
| `DB_NAME` | `str` | `"crypto_quant"` | 数据库名称，从环境变量 `DB_NAME` 读取 |
| `DB_DSN` | `str` | 由上述字段拼接 | PostgreSQL 连接字符串，格式：`postgresql://USER:PASS@HOST:PORT/DBNAME` |
| `CHAIN` | `str` | `"solana"` | 目标区块链，当前固定为 Solana |
| `TIMEFRAME` | `str` | `"1m"` | K线时间粒度，支持 `1m`（1分钟）和 `15min`（15分钟） |
| `MIN_LIQUIDITY_USD` | `float` | `500000.0` | 最小流动性阈值（美元），低于此值的代币将被过滤 |
| `MIN_FDV` | `float` | `10000000.0` | 最小全稀释估值（FDV），低于此值的代币将被过滤 |
| `MAX_FDV` | `float` | `inf` | 最大全稀释估值，默认不设上限 |
| `BIRDEYE_API_KEY` | `str` | `""` | Birdeye API 密钥，从环境变量读取 |
| `BIRDEYE_IS_PAID` | `bool` | `True` | 是否为 Birdeye 付费用户（影响请求限制数量） |
| `USE_DEXSCREENER` | `bool` | `False` | 是否启用 DexScreener 数据源 |
| `CONCURRENCY` | `int` | `20` | 异步并发请求数上限 |
| `HISTORY_DAYS` | `int` | `7` | 获取历史数据的天数范围 |

## 3. 调用关系图

```
+------------------+
|   .env 文件       |
+--------+---------+
         |
    load_dotenv()
         |
         v
+------------------+          被以下模块引用:
|   Config (类)     | <------+------+--------+--------+
|                  |         |      |        |        |
| DB_USER          |   data_manager  db_manager  fetcher  run_pipeline
| DB_PASSWORD      |         |      |        |        |
| DB_HOST          |   providers/   providers/
| DB_PORT          |   birdeye.py   dexscreener.py
| DB_NAME          |
| DB_DSN           |
| CHAIN            |
| TIMEFRAME        |
| MIN_LIQUIDITY_USD|
| MIN_FDV          |
| MAX_FDV          |
| BIRDEYE_API_KEY  |
| BIRDEYE_IS_PAID  |
| USE_DEXSCREENER  |
| CONCURRENCY      |
| HISTORY_DAYS     |
+------------------+
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `os` | 标准库，读取环境变量 |
| `dotenv` (`python-dotenv`) | 从 `.env` 文件加载环境变量 |

### 内部模块依赖

无。`config.py` 是基础配置模块，不依赖项目内其他模块。

## 5. 代码逻辑流程

1. **加载环境变量**：模块被 import 时立即调用 `load_dotenv()`，将 `.env` 文件中的变量注入到 `os.environ` 中。
2. **定义 Config 类**：在类定义阶段（非实例化阶段），所有类属性通过 `os.getenv()` 求值。每个配置项都提供了合理的默认值，确保在缺失 `.env` 文件时系统仍可在开发环境运行。
3. **拼接 DB_DSN**：使用 f-string 将数据库的 user、password、host、port、name 拼接成完整的 PostgreSQL DSN 连接字符串。
4. **静态配置**：其他业务参数（链名称、时间粒度、筛选阈值、并发数等）以硬编码或环境变量形式设置。

> **注意**：由于所有属性都是类级别属性，在 Python 解释器加载模块时就会被求值（eager evaluation）。若环境变量在运行时发生变化，需重新 import 该模块才能生效。
