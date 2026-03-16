# birdeye.py -- Birdeye 数据提供者

> 文件路径: `data_pipeline/providers/birdeye.py`

---

## 1. 文件概述

`birdeye.py` 实现了基于 [Birdeye](https://birdeye.so) API 的数据提供者 `BirdeyeProvider`。Birdeye 是 Solana 生态中主流的 DeFi 数据聚合平台，本模块通过其公开 API 获取以下数据：

- **热门代币列表**：获取当前 Solana 链上的趋势代币排名
- **代币历史 OHLCV 数据**：获取指定代币的历史价格（开盘、最高、最低、收盘）和成交量数据

核心职责：
- 封装 Birdeye API 的 HTTP 调用细节
- 将 API 返回的原始 JSON 数据转换为项目内部统一的数据格式
- 通过信号量（Semaphore）控制并发请求数，避免触发 API 限流
- 处理 HTTP 429（限流）错误的自动重试逻辑

---

## 2. 类与函数说明

### 类: `BirdeyeProvider(DataProvider)`

继承自 `DataProvider` 抽象基类，实现了 Birdeye API 的具体数据获取逻辑。

#### 方法: `__init__(self)`

| 属性   | 说明                                       |
| ------ | ------------------------------------------ |
| 类型   | 构造方法                                   |
| 参数   | 无（除 `self`）                            |
| 返回值 | 无                                         |
| 用途   | 初始化 Birdeye API 的基础 URL、请求头和并发控制信号量 |

初始化的实例属性：

| 属性名         | 类型                  | 说明                                           |
| -------------- | --------------------- | ---------------------------------------------- |
| `self.base_url` | `str`                | Birdeye API 基础地址：`https://public-api.birdeye.so` |
| `self.headers`  | `dict`               | HTTP 请求头，包含 API Key (`X-API-KEY`) 和 `accept` 头 |
| `self.semaphore` | `asyncio.Semaphore` | 并发控制信号量，最大并发数由 `Config.CONCURRENCY` 决定（默认 20） |

---

#### 方法: `async get_trending_tokens(self, limit=100)`

| 属性     | 说明                                                           |
| -------- | -------------------------------------------------------------- |
| 类型     | 异步方法（实现父类抽象方法）                                   |
| 参数     | `limit: int` -- 返回的热门代币数量上限，默认 100               |
| 返回值   | `list[dict]` -- 代币信息字典列表；请求失败时返回空列表 `[]`    |
| API 端点 | `GET /defi/token_trending`                                     |
| 用途     | 从 Birdeye 获取 Solana 链上的热门代币排名列表                  |

返回的每个字典包含以下字段：

| 字段名      | 类型    | 说明                        | 默认值      |
| ----------- | ------- | --------------------------- | ----------- |
| `address`   | `str`   | 代币链上地址                | （必须存在）|
| `symbol`    | `str`   | 代币符号                    | `'UNKNOWN'` |
| `name`      | `str`   | 代币名称                    | `'UNKNOWN'` |
| `decimals`  | `int`   | 代币精度                    | `6`         |
| `liquidity` | `float` | 流动性（USD）               | `0`         |
| `fdv`       | `float` | 完全稀释估值（USD）         | `0`         |

---

#### 方法: `async get_token_history(self, session, address, days=Config.HISTORY_DAYS)`

| 属性     | 说明                                                                     |
| -------- | ------------------------------------------------------------------------ |
| 类型     | 异步方法（实现父类抽象方法）                                             |
| 参数     | `session` -- `aiohttp.ClientSession` 实例，用于复用 HTTP 连接            |
|          | `address: str` -- 代币链上地址                                           |
|          | `days: int` -- 获取历史数据的天数，默认为 `Config.HISTORY_DAYS`（7 天）  |
| 返回值   | `list[tuple]` -- OHLCV 数据元组列表；请求失败或无数据时返回空列表 `[]`   |
| API 端点 | `GET /defi/ohlcv`                                                        |
| 用途     | 获取指定代币在给定时间范围内的历史 OHLCV（K线）数据                      |

返回的每个元组结构如下（按索引顺序）：

| 索引 | 字段        | 类型       | 说明                          |
| ---- | ----------- | ---------- | ----------------------------- |
| 0    | `time`      | `datetime` | K线时间戳                     |
| 1    | `address`   | `str`      | 代币链上地址                  |
| 2    | `open`      | `float`    | 开盘价                        |
| 3    | `high`      | `float`    | 最高价                        |
| 4    | `low`       | `float`    | 最低价                        |
| 5    | `close`     | `float`    | 收盘价                        |
| 6    | `volume`    | `float`    | 成交量                        |
| 7    | `liquidity` | `float`    | 流动性（固定为 `0.0`）        |
| 8    | `fdv`       | `float`    | 完全稀释估值（固定为 `0.0`）  |
| 9    | `source`    | `str`      | 数据来源标识，固定为 `'birdeye'` |

---

## 3. 调用关系图

```
+--------------------+       +---------------------+
|   外部调用者        |       |  data_pipeline/     |
|  (pipeline 主模块)  |       |  config.py          |
+--------------------+       +---------------------+
         |                       |
         | 调用                   | 读取配置
         v                       v
+-----------------------------------------------+
|           BirdeyeProvider                     |
|-----------------------------------------------|
|                                               |
|  __init__()                                   |
|    |-- 读取 Config.BIRDEYE_API_KEY            |
|    |-- 读取 Config.CONCURRENCY                |
|    +-- 初始化 base_url, headers, semaphore    |
|                                               |
|  get_trending_tokens(limit)                   |
|    |-- 创建 aiohttp.ClientSession             |
|    |-- GET /defi/token_trending               |
|    |-- 解析 JSON -> 构建 dict 列表            |
|    +-- 异常处理 -> 返回 [] 或 results         |
|                                               |
|  get_token_history(session, address, days)    |
|    |-- 计算时间范围 (time_from, time_to)      |
|    |-- 获取 semaphore 锁                      |
|    |-- GET /defi/ohlcv                        |
|    |-- 解析 JSON -> 构建 tuple 列表           |
|    |-- 429 状态码 -> sleep(2) -> 递归重试     |
|    +-- 异常处理 -> 返回 [] 或 formatted       |
+-----------------------------------------------+
         |                    |
         v                    v
+----------------+    +------------------+
| aiohttp        |    | Birdeye API      |
| (HTTP 客户端)  |    | (外部 REST API)  |
+----------------+    +------------------+
```

### 文件间交互

```
base.py  <----继承----  birdeye.py
                            |
                            |-- 导入 --> config.py (Config 类)
                            |-- 导入 --> base.py (DataProvider 类)
```

---

## 4. 依赖关系

### 外部第三方依赖

| 模块     | 导入内容 | 用途                                       |
| -------- | -------- | ------------------------------------------ |
| `aiohttp` | `aiohttp` | 异步 HTTP 客户端，用于调用 Birdeye REST API |
| `loguru`  | `logger`  | 日志记录，输出错误和警告信息               |

### 标准库依赖

| 模块       | 导入内容                 | 用途                                       |
| ---------- | ------------------------ | ------------------------------------------ |
| `asyncio`  | `asyncio`                | 异步编程支持，提供 `Semaphore` 并发控制    |
| `datetime` | `datetime`, `timedelta`  | 时间计算，确定历史数据的时间范围           |

### 内部模块依赖

| 模块                           | 导入内容       | 用途                             |
| ------------------------------ | -------------- | -------------------------------- |
| `data_pipeline.config`         | `Config`       | 读取项目配置（API Key、并发数等）|
| `data_pipeline.providers.base` | `DataProvider` | 继承抽象基类                     |

使用到的 Config 配置项：

| 配置项                  | 默认值  | 在本文件中的用途                      |
| ----------------------- | ------- | ------------------------------------- |
| `Config.BIRDEYE_API_KEY` | `""`   | Birdeye API 认证密钥                  |
| `Config.CONCURRENCY`     | `20`   | 最大并发请求数（Semaphore 初始值）    |
| `Config.HISTORY_DAYS`    | `7`    | 默认获取历史数据的天数                |
| `Config.TIMEFRAME`       | `"1m"` | K线时间粒度（如 `"1m"`, `"15min"`）   |

---

## 5. 代码逻辑流程

### 5.1 获取热门代币 (`get_trending_tokens`)

```
开始
  |
  v
构建请求 URL: /defi/token_trending
构建请求参数: sort_by=rank, sort_type=asc, offset=0, limit=<limit>
  |
  v
创建新的 aiohttp.ClientSession（携带 API Key 请求头）
  |
  v
发送 GET 请求
  |
  +-- HTTP 200 成功
  |     |
  |     v
  |   解析 JSON: data -> data.tokens
  |     |
  |     v
  |   遍历每个代币，提取字段:
  |   address, symbol, name, decimals, liquidity, fdv
  |   （缺失字段使用默认值）
  |     |
  |     v
  |   返回 results 列表
  |
  +-- HTTP 非 200
  |     |
  |     v
  |   记录错误日志 -> 返回空列表 []
  |
  +-- 异常捕获
        |
        v
      记录异常日志 -> 返回空列表 []
```

### 5.2 获取代币历史数据 (`get_token_history`)

```
开始
  |
  v
计算时间范围:
  time_to   = 当前时间戳 (Unix)
  time_from = 当前时间 - days 天 (Unix)
  |
  v
构建请求 URL: /defi/ohlcv
构建请求参数: address, type=<TIMEFRAME>, time_from, time_to
  |
  v
获取 semaphore 锁（控制并发数不超过 Config.CONCURRENCY）
  |
  v
使用传入的 session 发送 GET 请求
  |
  +-- HTTP 200 成功
  |     |
  |     v
  |   解析 JSON: data -> data.items
  |     |
  |     +-- items 为空 -> 返回空列表 []
  |     |
  |     +-- items 非空
  |           |
  |           v
  |         遍历每条记录，构建 tuple:
  |         (datetime, address, open, high, low, close,
  |          volume, 0.0, 0.0, 'birdeye')
  |           |
  |           v
  |         返回 formatted 列表
  |
  +-- HTTP 429 (限流)
  |     |
  |     v
  |   记录警告日志
  |   等待 2 秒 (asyncio.sleep)
  |   递归调用 self.get_token_history() 重试
  |
  +-- HTTP 其他状态码
  |     |
  |     v
  |   返回空列表 []
  |
  +-- 异常捕获
        |
        v
      记录错误日志 -> 返回空列表 []
```

**关键设计要点：**

1. **并发控制**：`get_token_history` 使用 `asyncio.Semaphore` 限制同时进行的请求数量，防止大量并发请求导致 API 限流。注意 `get_trending_tokens` 没有使用信号量，因为它是单次请求。

2. **会话管理差异**：`get_trending_tokens` 自行创建并管理 `aiohttp.ClientSession`（包含 API Key 请求头），而 `get_token_history` 接收外部传入的 `session`，便于在批量获取多个代币历史数据时复用连接。

3. **429 限流重试**：当收到 HTTP 429 时，方法会等待 2 秒后**递归调用自身**进行重试。注意：当前实现没有最大重试次数限制，如果 API 持续返回 429，可能导致无限递归。

4. **数据格式化**：OHLCV 数据以元组列表的形式返回，其中 `liquidity` 和 `fdv` 固定为 `0.0`，这些字段在 OHLCV 接口中不可用，可能由其他逻辑填充。
