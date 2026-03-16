# execution/jupiter.py 文档

## 1. 文件概述

`jupiter.py` 封装了与 [Jupiter Aggregator](https://jup.ag) DEX 聚合器 V6 API 的交互逻辑。Jupiter 是 Solana 链上最大的去中心化交易聚合协议，能够自动寻找最优的代币兑换路径。本文件定义了 `JupiterAggregator` 类，提供获取报价（quote）、构建交换交易（swap transaction）、反序列化并签名交易等核心功能。所有网络请求均采用异步（async）方式，通过 `aiohttp` 实现高效的 HTTP 通信。

## 2. 类与函数说明

### 类：`JupiterAggregator`

Jupiter DEX 聚合器的 API 客户端封装类。

#### 构造方法

```python
def __init__(self)
```

- **参数**：无
- **行为**：设置 Jupiter V6 API 的基础 URL（`https://quote-api.jup.ag/v6`），初始化 `session` 为 `None`（延迟创建）

#### 方法：`_get_session`

```python
async def _get_session(self) -> aiohttp.ClientSession
```

- **参数**：无
- **返回值**：`aiohttp.ClientSession` 实例
- **用途**：惰性创建并缓存 HTTP 会话。如果 `self.session` 为 `None`，则创建新的 `ClientSession`；否则复用已有会话
- **访问级别**：私有方法（以 `_` 开头）

#### 方法：`get_quote`

```python
async def get_quote(self, input_mint, output_mint, amount_integer, slippage_bps=None) -> dict | None
```

- **参数**：
  - `input_mint` (`str`)：输入代币的 Mint 地址
  - `output_mint` (`str`)：输出代币的 Mint 地址
  - `amount_integer` (`int`)：输入数量（最小单位，如 lamports）
  - `slippage_bps` (`int`, 可选)：滑点容忍度（基点）。若未指定，使用 `ExecutionConfig.DEFAULT_SLIPPAGE_BPS`
- **返回值**：成功时返回 Jupiter 报价 JSON 字典；失败时返回 `None`
- **用途**：向 Jupiter `/quote` API 请求代币兑换报价，包含最优路由信息

#### 方法：`get_swap_tx`

```python
async def get_swap_tx(self, quote_response) -> str | None
```

- **参数**：
  - `quote_response` (`dict`)：由 `get_quote` 返回的报价数据
- **返回值**：成功时返回 Base64 编码的交易字符串；失败时返回 `None`
- **用途**：根据报价数据请求 Jupiter `/swap` API 生成可发送的 Solana 交易。请求中包含用户公钥、自动计算单位价格和优先费用

#### 方法：`close`

```python
async def close(self)
```

- **参数**：无
- **返回值**：无
- **用途**：关闭 aiohttp 会话，释放网络连接资源

#### 静态方法：`deserialize_and_sign`

```python
@staticmethod
def deserialize_and_sign(b64_tx_str) -> VersionedTransaction
```

- **参数**：
  - `b64_tx_str` (`str`)：Base64 编码的交易字符串
- **返回值**：签名后的 `VersionedTransaction` 对象
- **异常**：签名失败时记录错误日志并重新抛出异常
- **用途**：将 Base64 编码的交易解码、反序列化为 `VersionedTransaction`，使用配置中的密钥对进行签名，然后用签名重新组装交易

## 3. 调用关系图

```
+-----------------------------------------------------+
|              JupiterAggregator                       |
|-----------------------------------------------------|
|                                                     |
|  __init__()                                         |
|     |                                               |
|     v                                               |
|  _get_session() <--- [惰性创建 aiohttp 会话]         |
|     ^       ^                                       |
|     |       |                                       |
|  get_quote()   get_swap_tx()                        |
|     |              |                                |
|     |              |                                |
|     v              v                                |
|  Jupiter V6 /quote API    Jupiter V6 /swap API      |
|                                                     |
|  deserialize_and_sign()  [静态方法, 独立调用]          |
|     |                                               |
|     +---> base64.b64decode()                        |
|     +---> VersionedTransaction.from_bytes()         |
|     +---> ExecutionConfig.PAYER_KEYPAIR.sign_message|
|     +---> VersionedTransaction.populate()           |
|                                                     |
|  close() ---> session.close()                       |
+-----------------------------------------------------+

外部调用关系：
  trader.py (SolanaTrader)
      |
      +---> jup.get_quote()
      +---> jup.get_swap_tx()
      +---> JupiterAggregator.deserialize_and_sign()
      +---> jup.close()
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|---|---|
| `aiohttp` | 异步 HTTP 客户端，用于与 Jupiter API 通信 |
| `base64` | 解码 Base64 编码的交易数据 |
| `json` | JSON 处理（已导入，由 aiohttp 内部使用） |
| `loguru` (`logger`) | 结构化日志记录 |
| `solders.transaction` (`VersionedTransaction`) | Solana 版本化交易的反序列化、签名与重组 |

### 内部模块依赖

| 模块 | 导入内容 | 用途 |
|---|---|---|
| `execution.config` | `ExecutionConfig` | 获取 `DEFAULT_SLIPPAGE_BPS`、`WALLET_ADDRESS`、`PAYER_KEYPAIR` |

## 5. 代码逻辑流程

### 获取报价流程 (`get_quote`)

```
调用 get_quote(input_mint, output_mint, amount, slippage)
    │
    ├─ 1. 调用 _get_session() 获取/创建 HTTP 会话
    │
    ├─ 2. 确定滑点：使用传入值或默认 ExecutionConfig.DEFAULT_SLIPPAGE_BPS
    │
    ├─ 3. 构建请求参数
    │     ├─ inputMint, outputMint, amount, slippageBps
    │     ├─ onlyDirectRoutes = false（允许多跳路由）
    │     └─ asLegacyTransaction = false（使用 VersionedTransaction）
    │
    ├─ 4. GET 请求 Jupiter /quote API
    │     ├─ HTTP 200 → 返回 JSON 报价数据
    │     └─ 非 200 → 记录错误日志，返回 None
    │
    └─ 返回报价字典 或 None
```

### 构建交换交易流程 (`get_swap_tx`)

```
调用 get_swap_tx(quote_response)
    │
    ├─ 1. 调用 _get_session() 获取 HTTP 会话
    │
    ├─ 2. 构建请求体
    │     ├─ quoteResponse：传入的报价数据
    │     ├─ userPublicKey：ExecutionConfig.WALLET_ADDRESS
    │     ├─ wrapAndUnwrapSol = True（自动处理 SOL 包装）
    │     ├─ computeUnitPriceMicroLamports = "auto"
    │     └─ prioritizationFeeLamports = "auto"
    │
    ├─ 3. POST 请求 Jupiter /swap API
    │     ├─ HTTP 200 → 从响应中提取 swapTransaction 字段
    │     └─ 非 200 → 记录错误日志，返回 None
    │
    └─ 返回 Base64 交易字符串 或 None
```

### 签名流程 (`deserialize_and_sign`)

```
调用 deserialize_and_sign(b64_tx_str)
    │
    ├─ 1. Base64 解码 → 得到交易原始字节
    │
    ├─ 2. VersionedTransaction.from_bytes() → 反序列化为交易对象
    │
    ├─ 3. 使用 PAYER_KEYPAIR 对交易消息签名
    │     └─ sign_message(txn.message.to_bytes())
    │
    ├─ 4. VersionedTransaction.populate() → 用签名重组交易
    │
    └─ 返回签名后的 VersionedTransaction
        （失败时记录日志并抛出异常）
```
