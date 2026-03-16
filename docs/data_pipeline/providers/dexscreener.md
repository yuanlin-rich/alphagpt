# dexscreener.py -- DexScreener 数据提供者

> 文件路径: `data_pipeline/providers/dexscreener.py`

---

## 1. 文件概述

`dexscreener.py` 实现了基于 [DexScreener](https://dexscreener.com) API 的数据提供者 `DexScreenerProvider`。DexScreener 是一个多链 DEX 聚合分析平台，本模块通过其公开 API 获取代币交易对的详细信息。

核心职责：
- 封装 DexScreener API 的 HTTP 调用细节
- 提供批量查询代币详情的能力（`get_token_details_batch`）
- 从多个交易对中筛选出流动性最高的最优交易对数据
- 将 API 返回的原始数据转换为项目内部统一的字典格式

**当前状态说明：**
- `get_trending_tokens` 和 `get_token_history` 方法目前返回空列表，属于**桩实现（stub）**，尚未接入实际 API 逻辑。
- 该提供者的核心功能集中在 `get_token_details_batch` 方法上，用于批量获取代币的流动性和 FDV 等详细信息。

---

## 2. 类与函数说明

### 类: `DexScreenerProvider(DataProvider)`

继承自 `DataProvider` 抽象基类，实现了 DexScreener API 的具体数据获取逻辑。

#### 方法: `__init__(self)`

| 属性   | 说明                                       |
| ------ | ------------------------------------------ |
| 类型   | 构造方法                                   |
| 参数   | 无（除 `self`）                            |
| 返回值 | 无                                         |
| 用途   | 初始化 DexScreener API 的基础 URL          |

初始化的实例属性：

| 属性名         | 类型   | 说明                                                      |
| -------------- | ------ | --------------------------------------------------------- |
| `self.base_url` | `str` | DexScreener API 基础地址：`https://api.dexscreener.com/latest/dex` |

---

#### 方法: `async get_trending_tokens(self, limit=50)`

| 属性     | 说明                                           |
| -------- | ---------------------------------------------- |
| 类型     | 异步方法（实现父类抽象方法）                   |
| 参数     | `limit: int` -- 返回数量上限，默认 50          |
| 返回值   | `list` -- 当前固定返回空列表 `[]`              |
| 用途     | **桩实现**，预留接口以便将来接入 DexScreener 热门代币数据 |

> 注意：方法内部构建了 URL `https://api.dexscreener.com/latest/dex/tokens/solana`，但并未发起实际请求，直接返回空列表。

---

#### 方法: `async get_token_details_batch(self, session, addresses)`

| 属性     | 说明                                                           |
| -------- | -------------------------------------------------------------- |
| 类型     | 异步方法（**非父类抽象方法**，为本类独有）                     |
| 参数     | `session` -- `aiohttp.ClientSession` 实例，用于复用 HTTP 连接  |
|          | `addresses: list[str]` -- 需要查询的代币地址列表               |
| 返回值   | `list[dict]` -- 代币详情字典列表                               |
| API 端点 | `GET /latest/dex/tokens/{逗号分隔的地址}`                      |
| 用途     | 批量查询代币的交易对信息，从中筛选流动性最高的交易对数据       |

返回的每个字典包含以下字段：

| 字段名      | 类型    | 说明                        | 备注            |
| ----------- | ------- | --------------------------- | --------------- |
| `address`   | `str`   | 代币链上地址（baseToken）   |                 |
| `symbol`    | `str`   | 代币符号                    |                 |
| `name`      | `str`   | 代币名称                    |                 |
| `liquidity` | `float` | 流动性（USD）               |                 |
| `fdv`       | `float` | 完全稀释估值（USD）         | 默认值为 `0`    |
| `decimals`  | `int`   | 代币精度                    | 固定为 `6`      |

**关键逻辑：分块请求 + 最优交易对筛选**

- 将地址列表按 `chunk_size=30` 分块，避免单次请求 URL 过长
- 对于每个代币地址，可能存在多个交易对（pairs），方法会筛选出 `chainId` 为 `Config.CHAIN`（默认 `"solana"`）且流动性最高的交易对作为代表

---

#### 方法: `async get_token_history(self, session, address, days)`

| 属性     | 说明                                           |
| -------- | ---------------------------------------------- |
| 类型     | 异步方法（实现父类抽象方法）                   |
| 参数     | `session` -- `aiohttp.ClientSession` 实例      |
|          | `address: str` -- 代币链上地址                 |
|          | `days: int` -- 获取历史数据的天数              |
| 返回值   | `list` -- 当前固定返回空列表 `[]`              |
| 用途     | **桩实现**，预留接口以便将来接入 DexScreener 历史数据 |

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
|         DexScreenerProvider                   |
|-----------------------------------------------|
|                                               |
|  __init__()                                   |
|    +-- 初始化 base_url                        |
|                                               |
|  get_trending_tokens(limit)                   |
|    +-- [桩实现] 直接返回 []                   |
|                                               |
|  get_token_details_batch(session, addresses)  |
|    |-- 将 addresses 按 30 个一组分块          |
|    |-- 循环每个分块:                          |
|    |     |-- 拼接地址为逗号分隔字符串         |
|    |     |-- GET /latest/dex/tokens/{addrs}   |
|    |     |-- 解析 pairs 列表                  |
|    |     |-- 按 chainId 过滤 (Config.CHAIN)   |
|    |     +-- 按 liquidity 筛选最优 pair       |
|    +-- 返回 valid_data 列表                   |
|                                               |
|  get_token_history(session, address, days)    |
|    +-- [桩实现] 直接返回 []                   |
+-----------------------------------------------+
         |                    |
         v                    v
+----------------+    +---------------------+
| aiohttp        |    | DexScreener API     |
| (HTTP 客户端)  |    | (外部 REST API)     |
+----------------+    +---------------------+
```

### 文件间交互

```
base.py  <----继承----  dexscreener.py
                            |
                            |-- 导入 --> config.py (Config 类)
                            |-- 导入 --> base.py (DataProvider 类)
```

### 与 BirdeyeProvider 的协作关系

```
+-------------------+                +------------------------+
| BirdeyeProvider   |                | DexScreenerProvider    |
|-------------------|                |------------------------|
| get_trending_     | -- 获取地址 -> | get_token_details_     |
|   tokens()        |   列表         |   batch()              |
+-------------------+                +------------------------+
        |                                      |
        v                                      v
   热门代币列表                        代币详情（流动性、FDV等）
```

在典型的数据管道流程中，`BirdeyeProvider` 负责获取热门代币列表和历史数据，而 `DexScreenerProvider` 可作为补充数据源提供代币的流动性和 FDV 详情。

---

## 4. 依赖关系

### 外部第三方依赖

| 模块     | 导入内容 | 用途                                            |
| -------- | -------- | ----------------------------------------------- |
| `aiohttp` | `aiohttp` | 异步 HTTP 客户端，用于调用 DexScreener REST API |
| `loguru`  | `logger`  | 日志记录，输出错误信息                          |

### 标准库依赖

无。

### 内部模块依赖

| 模块                           | 导入内容       | 用途                             |
| ------------------------------ | -------------- | -------------------------------- |
| `data_pipeline.providers.base` | `DataProvider` | 继承抽象基类                     |
| `data_pipeline.config`         | `Config`       | 读取项目配置（链标识等）         |

使用到的 Config 配置项：

| 配置项          | 默认值      | 在本文件中的用途                        |
| --------------- | ----------- | --------------------------------------- |
| `Config.CHAIN`  | `"solana"`  | 过滤交易对时匹配的链标识               |

---

## 5. 代码逻辑流程

### 5.1 获取热门代币 (`get_trending_tokens`) -- 桩实现

```
开始
  |
  v
构建 URL (未使用): https://api.dexscreener.com/latest/dex/tokens/solana
  |
  v
直接返回空列表 []
  |
  v
结束
```

> 此方法当前为桩实现，仅满足抽象基类的接口要求。

### 5.2 批量获取代币详情 (`get_token_details_batch`)

```
开始
  |
  v
初始化空列表 valid_data = []
设定分块大小 chunk_size = 30
  |
  v
将 addresses 按 30 个一组分块
  |
  v
[循环] 对每个分块 chunk:
  |
  +-- 将 chunk 中的地址用逗号拼接成字符串 addr_str
  |
  +-- 构建 URL: {base_url}/tokens/{addr_str}
  |
  +-- 发送 GET 请求
  |     |
  |     +-- HTTP 200 成功
  |     |     |
  |     |     v
  |     |   解析 JSON: 获取 pairs 列表
  |     |     |
  |     |     v
  |     |   [循环] 对每个 pair:
  |     |     |
  |     |     +-- 检查 chainId == Config.CHAIN ?
  |     |     |     |
  |     |     |     +-- 否 -> 跳过 (continue)
  |     |     |     |
  |     |     |     +-- 是 -> 继续处理
  |     |     |
  |     |     +-- 提取 baseToken.address 和 liquidity
  |     |     |
  |     |     +-- 该地址是否已在 best_pairs 中？
  |     |           |
  |     |           +-- 不在 -> 添加到 best_pairs
  |     |           |
  |     |           +-- 在且新 liquidity 更大 -> 更新 best_pairs
  |     |           |
  |     |           +-- 在且新 liquidity 更小 -> 跳过
  |     |     |
  |     |     v
  |     |   将 best_pairs.values() 追加到 valid_data
  |     |
  |     +-- 异常捕获
  |           |
  |           v
  |         记录错误日志，继续处理下一个分块
  |
  v
返回 valid_data
  |
  v
结束
```

### 5.3 获取代币历史数据 (`get_token_history`) -- 桩实现

```
开始
  |
  v
直接返回空列表 []
  |
  v
结束
```

> 此方法当前为桩实现，仅满足抽象基类的接口要求。

**关键设计要点：**

1. **分块请求策略**：DexScreener API 支持在单个请求中查询多个代币（地址以逗号分隔），但为避免 URL 过长或请求超时，每次最多查询 30 个地址。

2. **最优交易对筛选**：一个代币可能在多个 DEX 上有交易对。方法通过 `best_pairs` 字典，以代币地址为键，仅保留流动性（`liquidity`）最高的交易对信息，确保返回的数据质量最优。

3. **链过滤**：通过 `Config.CHAIN` 配置（默认 `"solana"`）过滤交易对，确保只处理目标链上的数据。

4. **无并发控制**：与 `BirdeyeProvider` 不同，`DexScreenerProvider` 未使用信号量进行并发控制。这是因为 `get_token_details_batch` 使用顺序循环处理分块，而非并发请求。

5. **decimals 硬编码**：代币精度固定为 `6`（Solana 上 SPL 代币的常见默认值），DexScreener API 不直接提供此字段。
