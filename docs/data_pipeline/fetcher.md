# fetcher.py 文档

## 1. 文件概述

`fetcher.py` 是 `data_pipeline` 模块中一个独立的数据获取器实现，提供了直接调用 Birdeye API 获取趋势代币列表和历史 OHLCV K线数据的能力。该文件定义了 `BirdeyeFetcher` 类，它与 `providers/birdeye.py` 中的 `BirdeyeProvider` 功能类似，但实现方式略有不同（例如信号量并发限制为 5 而非从 Config 读取，返回格式不含 `liquidity`/`fdv`/`source` 字段等），可视为早期版本或轻量级替代实现。

> **注意**：在当前的主管道 (`data_manager.py` / `run_pipeline.py`) 中，实际使用的是 `providers/birdeye.py` 中的 `BirdeyeProvider`，而非本文件的 `BirdeyeFetcher`。

## 2. 类与函数说明

### 类：`BirdeyeFetcher`

Birdeye API 的直接封装类，提供异步的代币发现和历史数据获取功能。

#### `__init__(self)`

- **用途**：初始化 fetcher 实例，设置 API 请求头和并发信号量。
- **参数**：无
- **内部属性**：
  - `self.headers` — `dict`，HTTP 请求头，包含 `X-API-KEY`（来自 `Config.BIRDEYE_API_KEY`）和 `accept: application/json`
  - `self.semaphore` — `asyncio.Semaphore(5)`，并发控制信号量，限制同时最多 5 个请求

#### `async get_trending_tokens(self, limit=100)`

- **用途**：获取 Birdeye 平台上的趋势代币列表。
- **参数**：
  - `limit` — `int`，默认 `100`，获取的代币数量上限
- **返回值**：`list[dict]` — 代币信息列表，每个字典包含代币原始数据；失败时返回空列表 `[]`
- **行为**：
  - 构造 Birdeye `/defi/token_trending` API 的 URL（含排序和分页参数）
  - 创建 aiohttp 会话发起 GET 请求
  - 解析返回 JSON 中的 `data.tokens` 字段
  - HTTP 非 200 或异常时返回空列表并记录错误日志

#### `async get_token_history(self, session, address, days=30)`

- **用途**：获取指定代币的 OHLCV 历史 K线数据。
- **参数**：
  - `session` — `aiohttp.ClientSession`，复用的 HTTP 会话对象
  - `address` — `str`，代币合约地址
  - `days` — `int`，默认 `30`，获取过去多少天的数据
- **返回值**：`list[tuple] | None`
  - 成功时返回元组列表，每个元组格式为 `(datetime, address, open, high, low, close, volume, 0.0)`
  - 失败或无数据时返回 `None`
- **行为**：
  - 计算 `time_from` 和 `time_to` 的 UNIX 时间戳
  - 通过信号量控制并发，调用 Birdeye `/defi/ohlcv` API
  - 解析返回的 K线条目，将 UNIX 时间转为 `datetime` 对象
  - 遇到 HTTP 429（频率限制）时等待 2 秒后递归重试
  - 其他错误返回 `None`

## 3. 调用关系图

```
+-----------------------------------------------------------+
|                     BirdeyeFetcher                         |
+-----------------------------------------------------------+
|                                                           |
|  __init__()                                               |
|    |-- Config.BIRDEYE_API_KEY -> self.headers              |
|    +-- asyncio.Semaphore(5)   -> self.semaphore            |
|                                                           |
|  get_trending_tokens(limit)                               |
|    |-- 构造 URL: Config.BASE_URL + /defi/token_trending    |
|    |-- aiohttp.ClientSession(headers=self.headers)         |
|    +-- session.get(url) -> 解析 JSON                       |
|                                                           |
|  get_token_history(session, address, days)                 |
|    |-- 计算时间范围 (time_from, time_to)                    |
|    |-- 构造 URL: Config.BASE_URL + /defi/ohlcv             |
|    |-- self.semaphore 并发控制                              |
|    |-- session.get(url, params) -> 解析 JSON               |
|    +-- HTTP 429 -> sleep(2) -> 递归重试                     |
+-----------------------------------------------------------+

注意: 本文件引用了 Config.BASE_URL，但该属性在当前 config.py
      中并未定义。实际主管道使用 providers/birdeye.py 中的
      BirdeyeProvider（self.base_url 硬编码为 Birdeye URL）。
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `aiohttp` | 异步 HTTP 客户端 |
| `asyncio` | 标准库，异步编程（`Semaphore`） |
| `datetime` | 标准库，时间戳转换（`datetime`、`timedelta`） |
| `pandas` | 数据处理库（已 import 但未在代码中使用） |
| `loguru` | 日志记录 |

### 内部模块依赖

| 模块 | 导入对象 | 用途 |
|------|----------|------|
| `.config` | `Config` | 获取 `BIRDEYE_API_KEY`、`BASE_URL`、`TIMEFRAME` 等配置 |

## 5. 代码逻辑流程

### get_trending_tokens 流程

```
get_trending_tokens(limit)
  |
  v
构造 URL: {BASE_URL}/defi/token_trending?sort_by=rank&sort_type=asc&offset=0&limit={limit}
  |
  v
创建 aiohttp 会话 (携带 API KEY)
  |
  v
发起 GET 请求
  |-- 200: 解析 data.tokens -> 返回代币列表
  |-- 非200: 记录错误 -> 返回 []
  +-- 异常: 记录错误 -> 返回 []
```

### get_token_history 流程

```
get_token_history(session, address, days)
  |
  v
计算时间范围:
  time_to   = now() 的 UNIX 时间戳
  time_from = (now() - days天) 的 UNIX 时间戳
  |
  v
构造参数: address, type=TIMEFRAME, time_from, time_to
  |
  v
获取信号量 (最多5个并发)
  |
  v
发起 GET 请求 -> {BASE_URL}/defi/ohlcv
  |
  |-- 200:
  |   |-- 解析 data.items
  |   |-- 无数据: 返回 None
  |   +-- 有数据: 遍历每条记录
  |       |-- unixTime -> datetime
  |       +-- 构造元组 (dt, address, o, h, l, c, v, 0.0)
  |       返回 formatted 列表
  |
  |-- 429 (频率限制):
  |   |-- 日志警告
  |   |-- sleep(2秒)
  |   +-- 递归调用自身重试
  |
  |-- 其他状态码:
  |   +-- 日志警告 -> 返回 None
  |
  +-- 异常:
      +-- 日志错误 -> 返回 None
```

> **与 BirdeyeProvider 的区别**：
> - `BirdeyeFetcher` 信号量硬编码为 5，`BirdeyeProvider` 使用 `Config.CONCURRENCY`（默认 20）
> - `BirdeyeFetcher` 默认获取 30 天数据，`BirdeyeProvider` 默认使用 `Config.HISTORY_DAYS`（7 天）
> - `BirdeyeFetcher` 返回的元组仅 8 个字段，`BirdeyeProvider` 返回 10 个字段（多了 `liquidity`、`fdv`、`source`）
> - `BirdeyeFetcher` 引用 `Config.BASE_URL`（未定义），`BirdeyeProvider` 使用实例属性 `self.base_url`
