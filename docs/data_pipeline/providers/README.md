# Providers -- 数据供应商模块

## 1. 模块概述

`data_pipeline/providers/` 是 AlphaGPT 数据管道的**数据采集层**，负责从外部链上数据 API（Birdeye、DexScreener）异步获取 Solana 链上代币的行情与元数据。

该子模块采用经典的 **策略模式（Strategy Pattern）**：通过一个抽象基类 `DataProvider` 定义统一的数据获取接口，再由具体提供商类（`BirdeyeProvider`、`DexScreenerProvider`）各自实现底层 HTTP 请求逻辑。上层调用者只需面向 `DataProvider` 接口编程，即可在不同数据源之间无缝切换，实现了数据源的可插拔和可扩展。

核心能力包括：

- **获取趋势代币列表** -- 拉取当前热门 / 排名靠前的 Solana 代币基础信息（地址、符号、名称、流动性、FDV 等）。
- **获取代币历史 K 线** -- 根据代币地址和天数范围，拉取 OHLCV（开高低收量）历史数据。
- **批量获取代币详情**（DexScreener 特有）-- 按批次查询多个代币的交易对详情，筛选最优流动性交易对。

---

## 2. 文件说明

| 文件 | 用途 | 关键内容 |
|------|------|----------|
| `base.py` | 抽象基类定义 | 定义 `DataProvider` ABC，声明 `get_trending_tokens` 和 `get_token_history` 两个抽象异步方法，作为所有数据提供商的统一接口契约。 |
| `birdeye.py` | Birdeye API 提供商 | 实现 `BirdeyeProvider`，通过 Birdeye 公开 API 获取趋势代币和 OHLCV K 线历史数据。支持信号量并发控制、429 限速自动重试。 |
| `dexscreener.py` | DexScreener API 提供商 | 实现 `DexScreenerProvider`，通过 DexScreener API 批量查询代币交易对详情。`get_trending_tokens` 和 `get_token_history` 目前为占位实现（返回空列表），核心功能为 `get_token_details_batch`。 |

---

## 3. 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    上层调用者 (data_pipeline)                     │
│           面向 DataProvider 接口编程，按 Config 选择数据源          │
└────────────────────────┬────────────────────────────────────────┘
                         │ 调用
                         ▼
        ┌────────────────────────────────────┐
        │      DataProvider (ABC)             │   base.py
        │  ┌───────────────────────────────┐  │
        │  │ + get_trending_tokens(limit)  │  │   抽象方法
        │  │ + get_token_history(session,  │  │   抽象方法
        │  │       address, days)          │  │
        │  └───────────────────────────────┘  │
        └──────────┬─────────────┬────────────┘
                   │  继承        │  继承
          ┌────────▼──────┐  ┌───▼──────────────┐
          │ BirdeyeProvider│  │DexScreenerProvider│
          │  (birdeye.py)  │  │ (dexscreener.py)  │
          ├────────────────┤  ├───────────────────┤
          │ base_url       │  │ base_url          │
          │ headers        │  ├───────────────────┤
          │ semaphore      │  │ get_trending_     │
          ├────────────────┤  │   tokens()  [桩]  │
          │ get_trending_  │  │ get_token_        │
          │   tokens()     │  │   history() [桩]  │
          │ get_token_     │  │ get_token_details │
          │   history()    │  │   _batch()  [核心]│
          └───────┬────────┘  └────────┬──────────┘
                  │                     │
                  ▼                     ▼
        ┌──────────────┐      ┌──────────────────┐
        │  Birdeye API │      │ DexScreener API  │
        │ public-api.  │      │ api.dexscreener. │
        │ birdeye.so   │      │ com              │
        └──────────────┘      └──────────────────┘

  ─── 内部依赖 ───

  birdeye.py ──imports──▶ base.py   (DataProvider)
  birdeye.py ──imports──▶ ../config.py (Config)

  dexscreener.py ──imports──▶ base.py   (DataProvider)
  dexscreener.py ──imports──▶ ../config.py (Config)
```

---

## 4. 依赖关系

### 4.1 内部模块依赖

| 源文件 | 导入的内部模块 | 使用的符号 | 说明 |
|--------|---------------|-----------|------|
| `birdeye.py` | `data_pipeline.providers.base` | `DataProvider` | 继承抽象基类 |
| `birdeye.py` | `data_pipeline.config` | `Config` | 读取 `BIRDEYE_API_KEY`、`CONCURRENCY`、`HISTORY_DAYS`、`TIMEFRAME` |
| `dexscreener.py` | `data_pipeline.providers.base` | `DataProvider` | 继承抽象基类 |
| `dexscreener.py` | `data_pipeline.config` | `Config` | 读取 `CHAIN`（用于过滤 Solana 交易对） |
| `base.py` | _(无)_ | -- | 仅依赖 Python 标准库 `abc` |

### 4.2 外部第三方依赖

| 包名 | 使用位置 | 用途 |
|------|---------|------|
| `aiohttp` | `birdeye.py`, `dexscreener.py` | 异步 HTTP 客户端，用于调用外部 REST API |
| `loguru` | `birdeye.py`, `dexscreener.py` | 结构化日志记录（`logger.error` / `logger.warning`） |

### 4.3 Python 标准库依赖

| 模块 | 使用位置 | 用途 |
|------|---------|------|
| `abc` (ABC, abstractmethod) | `base.py` | 定义抽象基类 |
| `asyncio` | `birdeye.py` | `Semaphore` 并发控制、`sleep` 限速重试 |
| `datetime` (datetime, timedelta) | `birdeye.py` | 计算历史数据的起止时间戳 |

---

## 5. 关键类/函数

### 5.1 `DataProvider`（base.py）

抽象基类，定义所有数据提供商必须实现的接口契约。

| 方法 | 签名 | 说明 |
|------|------|------|
| `get_trending_tokens` | `async get_trending_tokens(self, limit: int) -> list` | 获取当前热门代币列表。`limit` 控制返回数量。 |
| `get_token_history` | `async get_token_history(self, session, address: str, days: int) -> list` | 获取指定代币的历史 K 线数据。`session` 为外部传入的 `aiohttp.ClientSession`，`address` 为代币合约地址，`days` 为回溯天数。 |

---

### 5.2 `BirdeyeProvider`（birdeye.py）

Birdeye API 的完整实现，是当前项目的**主力数据源**。

#### 构造函数

```python
def __init__(self):
```

初始化以下实例属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.base_url` | `str` | API 基础 URL：`https://public-api.birdeye.so` |
| `self.headers` | `dict` | HTTP 请求头，包含 `X-API-KEY`（来自 `Config.BIRDEYE_API_KEY`）和 `accept: application/json` |
| `self.semaphore` | `asyncio.Semaphore` | 并发信号量，上限为 `Config.CONCURRENCY`（默认 20），用于限制同时发出的 API 请求数 |

#### 方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `get_trending_tokens` | `async get_trending_tokens(self, limit=100) -> list[dict]` | 调用 `/defi/token_trending` 接口，按 rank 升序获取趋势代币。返回字典列表，每个字典包含 `address`、`symbol`、`name`、`decimals`、`liquidity`、`fdv` 字段。请求失败时记录日志并返回空列表。 |
| `get_token_history` | `async get_token_history(self, session, address, days=Config.HISTORY_DAYS) -> list[tuple]` | 调用 `/defi/ohlcv` 接口获取 OHLCV K 线数据。使用信号量控制并发。返回元组列表，每个元组包含 10 个元素：`(time, address, open, high, low, close, volume, liquidity, fdv, source)`。遇到 HTTP 429（限速）时自动等待 2 秒后递归重试。 |

**返回元组字段说明（`get_token_history`）：**

| 索引 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 0 | time | `datetime` | K 线时间（由 UNIX 时间戳转换） |
| 1 | address | `str` | 代币合约地址 |
| 2 | open | `float` | 开盘价 |
| 3 | high | `float` | 最高价 |
| 4 | low | `float` | 最低价 |
| 5 | close | `float` | 收盘价 |
| 6 | volume | `float` | 成交量 |
| 7 | liquidity | `float` | 流动性（当前固定为 `0.0`） |
| 8 | fdv | `float` | 完全稀释估值（当前固定为 `0.0`） |
| 9 | source | `str` | 数据来源标记：`"birdeye"` |

---

### 5.3 `DexScreenerProvider`（dexscreener.py）

DexScreener API 的实现，目前作为**辅助数据源**，核心功能为批量查询代币交易对详情。

#### 构造函数

```python
def __init__(self):
```

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.base_url` | `str` | API 基础 URL：`https://api.dexscreener.com/latest/dex` |

#### 方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `get_trending_tokens` | `async get_trending_tokens(self, limit=50) -> list` | **占位实现**，当前直接返回空列表 `[]`。 |
| `get_token_history` | `async get_token_history(self, session, address, days) -> list` | **占位实现**，当前直接返回空列表 `[]`。 |
| `get_token_details_batch` | `async get_token_details_batch(self, session, addresses) -> list[dict]` | **核心方法**（非接口方法）。将地址列表按 30 个一组分批，调用 `/tokens/{addresses}` 接口查询交易对信息。对同一代币的多个交易对，筛选出 `Config.CHAIN`（默认 `"solana"`）链上流动性最高的交易对。返回字典列表，每个字典包含 `address`、`symbol`、`name`、`liquidity`、`fdv`、`decimals` 字段。 |

**`get_token_details_batch` 处理逻辑：**

1. 将输入的 `addresses` 列表按 `chunk_size=30` 分块。
2. 对每个分块，将地址用逗号拼接后请求 DexScreener API。
3. 从返回的 `pairs` 中过滤 `chainId == Config.CHAIN` 的交易对。
4. 对同一 `baseToken.address`，保留流动性（`liquidity.usd`）最高的交易对信息。
5. 汇总所有分块的结果后返回。
