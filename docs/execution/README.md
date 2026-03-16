# Execution 模块文档

## 1. 模块概述

`execution` 模块是 AlphaGPT 项目的**链上交易执行层**，负责在 Solana 区块链上完成代币的买入和卖出操作。该模块通过 Jupiter 聚合器获取最优交易报价和交换路由，再经由 QuickNode RPC 节点将签名后的交易广播到 Solana 网络并等待确认。

核心能力包括：

- **配置管理**：从环境变量加载 RPC 节点地址和钱包私钥，集中管理滑点、优先级等交易参数。
- **DEX 聚合报价**：对接 Jupiter V6 API，获取 token 交换报价并构造交换交易。
- **交易签名与广播**：对 Jupiter 返回的交易进行本地签名，通过 Solana RPC 发送并确认。
- **买卖交易编排**：封装完整的买入（SOL -> Token）和卖出（Token -> SOL）流程，包含余额检查、报价获取、签名、发送等全链路逻辑。
- **链上数据查询**：查询 SOL 余额、代币余额、代币精度等链上信息。

---

## 2. 文件说明

| 文件 | 用途 | 关键内容 |
|------|------|----------|
| `config.py` | 全局配置 | 定义 `ExecutionConfig` 类，从 `.env` 文件加载 RPC URL、钱包私钥，派生钱包地址；定义默认滑点（200 bps）、优先级等级、SOL/USDC 的 Mint 地址常量。 |
| `jupiter.py` | Jupiter 聚合器客户端 | 封装 `JupiterAggregator` 类，通过 Jupiter V6 REST API 获取交换报价（`get_quote`）、构造交换交易（`get_swap_tx`），以及对交易进行反序列化和签名（`deserialize_and_sign`）。 |
| `rpc_handler.py` | Solana RPC 通信层 | 封装 `QuickNodeClient` 类，基于 `solana-py` 的 `AsyncClient` 与 Solana 节点交互，提供余额查询（`get_balance`）、交易发送与确认（`send_and_confirm`）等功能。 |
| `trader.py` | 交易编排器（核心入口） | 定义 `SolanaTrader` 类，组合 `QuickNodeClient` 和 `JupiterAggregator`，提供完整的 `buy()` 和 `sell()` 方法，实现从余额检查到交易确认的端到端交易流程。 |
| `utils.py` | 工具函数 | 提供 `get_mint_decimals()` 函数，用于查询指定代币的精度（decimals），SOL 直接返回 9，其他代币通过 RPC 链上查询获取。 |

---

## 3. 架构图

```
+-----------------------------------------------------------------------+
|                        execution 模块                                  |
|                                                                       |
|  +--------------------+                                               |
|  |    config.py       |   (环境变量 / .env)                            |
|  |  ExecutionConfig   |<----- QUICKNODE_RPC_URL                       |
|  |   - RPC_URL        |<----- SOLANA_PRIVATE_KEY                      |
|  |   - PAYER_KEYPAIR  |                                               |
|  |   - WALLET_ADDRESS |                                               |
|  |   - SLIPPAGE_BPS   |                                               |
|  |   - SOL/USDC MINT  |                                               |
|  +--------+-----------+                                               |
|           |                                                           |
|           | (被所有其他模块导入)                                         |
|           |                                                           |
|  +--------v-----------+       +------------------------+              |
|  |  rpc_handler.py    |       |    jupiter.py          |              |
|  |  QuickNodeClient   |       |  JupiterAggregator     |              |
|  |   - get_balance()  |       |   - get_quote()        |              |
|  |   - send_and_      |       |   - get_swap_tx()      |              |
|  |     confirm()      |       |   - deserialize_and_   |              |
|  |   - close()        |       |     sign()             |              |
|  +--------+-----------+       |   - close()            |              |
|           |                   +----------+-------------+              |
|           |                              |                            |
|           +-------------+----------------+                            |
|                         |                                             |
|                +--------v--------+                                    |
|                |   trader.py     |                                    |
|                |  SolanaTrader   |                                    |
|                |   - buy()       |                                    |
|                |   - sell()      |                                    |
|                |   - close()     |                                    |
|                +-----------------+                                    |
|                                                                       |
|  +------------------+                                                 |
|  |    utils.py      |  (独立工具，不被模块内其他文件引用)                  |
|  | get_mint_decimals|                                                 |
|  +------------------+                                                 |
+-----------------------------------------------------------------------+

调用流程（以买入为例）:

  SolanaTrader.buy()
       |
       |---> QuickNodeClient.get_balance()      # 检查 SOL 余额
       |
       |---> JupiterAggregator.get_quote()       # 获取交换报价
       |
       |---> JupiterAggregator.get_swap_tx()     # 获取待签名交易
       |
       |---> JupiterAggregator.deserialize_and_sign()  # 反序列化 + 签名
       |
       +---> QuickNodeClient.send_and_confirm()  # 发送交易并等待确认

外部服务依赖:

  Jupiter V6 API  <----->  jupiter.py
  (quote-api.jup.ag/v6)

  Solana RPC Node  <----->  rpc_handler.py
  (QuickNode)
```

---

## 4. 依赖关系

### 4.1 模块内部依赖

```
config.py        <-- jupiter.py       (导入 ExecutionConfig)
config.py        <-- rpc_handler.py   (导入 ExecutionConfig)
config.py        <-- trader.py        (导入 ExecutionConfig)
config.py        <-- utils.py         (导入 ExecutionConfig)

rpc_handler.py   <-- trader.py        (导入 QuickNodeClient)
jupiter.py       <-- trader.py        (导入 JupiterAggregator)
```

> 注意：`utils.py` 定义的 `get_mint_decimals()` 当前未被模块内其他文件直接调用，推测为预留给上层模块使用的工具函数。

### 4.2 AlphaGPT 项目内部依赖

`execution` 模块**不依赖**项目中的其他模块（如 `data_pipeline`、`model_core`、`strategy_manager`、`dashboard` 等）。它是一个**自包含的底层执行层**，仅被上层模块调用。

### 4.3 外部第三方依赖

| 包名 | 用途 | 使用位置 |
|------|------|----------|
| `python-dotenv` | 从 `.env` 文件加载环境变量 | `config.py` |
| `solders` | Solana 原生数据结构（`Keypair`、`Pubkey`、`VersionedTransaction`） | `config.py`、`jupiter.py`、`trader.py`、`utils.py` |
| `solana` (solana-py) | Solana RPC 异步客户端（`AsyncClient`）、类型定义（`TokenAccountOpts`、`Confirmed`） | `rpc_handler.py`、`trader.py`、`utils.py` |
| `aiohttp` | 异步 HTTP 客户端，用于调用 Jupiter REST API | `jupiter.py` |
| `loguru` | 结构化日志 | `jupiter.py`、`rpc_handler.py`、`trader.py` |
| `base58` | Base58 编解码（导入但未直接使用，为 `solders` 的间接依赖） | `config.py` |
| `base64` | Base64 解码 Jupiter 返回的交易字节 | `jupiter.py` |
| `json` | JSON 解析（私钥备选格式 / HTTP 响应） | `config.py`、`jupiter.py` |
| `asyncio` | Python 异步运行时 | `trader.py`（测试入口） |
| `os` | 读取环境变量 | `config.py` |

---

## 5. 关键类/函数

### 5.1 `ExecutionConfig`（config.py）

全局配置类，所有属性为**类级别属性**，无需实例化即可使用。

| 属性 | 类型 | 说明 |
|------|------|------|
| `RPC_URL` | `str` | Solana RPC 节点地址，从环境变量 `QUICKNODE_RPC_URL` 读取 |
| `PAYER_KEYPAIR` | `Keypair` | 钱包密钥对，从环境变量 `SOLANA_PRIVATE_KEY` 读取，支持 Base58 字符串或 JSON 字节数组两种格式 |
| `WALLET_ADDRESS` | `str` | 钱包公钥地址（由 `PAYER_KEYPAIR` 派生） |
| `DEFAULT_SLIPPAGE_BPS` | `int` | 默认滑点容差，值为 `200`（即 2%） |
| `PRIORITY_LEVEL` | `str` | 交易优先级等级，值为 `"High"` |
| `SOL_MINT` | `str` | SOL 原生代币的 Mint 地址 |
| `USDC_MINT` | `str` | USDC 代币的 Mint 地址 |

---

### 5.2 `JupiterAggregator`（jupiter.py）

Jupiter DEX 聚合器客户端，封装与 Jupiter V6 API 的交互。所有网络方法均为 `async`。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__()` | - | - | 初始化基础 URL (`https://quote-api.jup.ag/v6`)，会话延迟创建 |
| `get_quote()` | `input_mint: str`, `output_mint: str`, `amount_integer: int`, `slippage_bps: int = None` | `dict \| None` | 调用 Jupiter `/quote` 接口获取交换报价。`amount_integer` 为最小单位的数量（如 lamports）。返回完整报价 JSON 或失败时返回 `None` |
| `get_swap_tx()` | `quote_response: dict` | `str \| None` | 调用 Jupiter `/swap` 接口，传入报价数据，返回 Base64 编码的待签名交易字符串，失败返回 `None` |
| `deserialize_and_sign()` | `b64_tx_str: str` | `VersionedTransaction` | **静态方法**。将 Base64 交易字符串反序列化为 `VersionedTransaction`，使用 `PAYER_KEYPAIR` 签名后返回已签名交易 |
| `close()` | - | - | 关闭底层 `aiohttp` 会话 |

---

### 5.3 `QuickNodeClient`（rpc_handler.py）

Solana RPC 通信客户端，基于 `solana-py` 的 `AsyncClient`。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__()` | - | - | 创建 `AsyncClient` 连接到 `ExecutionConfig.RPC_URL`，commitment 级别为 `Confirmed` |
| `get_balance()` | - | `float` | 查询钱包的 SOL 余额，返回值单位为 SOL（已从 lamports 转换）。出错返回 `0.0` |
| `get_token_balance()` | `mint_address: str` | - | **尚未实现**（函数体为 `pass`） |
| `send_and_confirm()` | `txn: VersionedTransaction`, `max_retries: int = 3` | `str \| None` | 发送已签名交易到链上并等待确认。成功返回交易签名字符串，失败返回 `None`。日志中输出 Solscan 链接 |
| `close()` | - | - | 关闭 RPC 客户端连接 |

---

### 5.4 `SolanaTrader`（trader.py）

**交易执行的核心入口类**，组合 `QuickNodeClient` 和 `JupiterAggregator`，提供高级别的买卖接口。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__()` | - | - | 初始化 RPC 客户端和 Jupiter 聚合器实例，设置 `TOKEN_PROGRAM_ID` |
| `buy()` | `token_address: str`, `amount_sol: float`, `slippage_bps: int = 500` | `bool` | **买入代币**。用指定数量的 SOL 购买目标代币。流程：检查 SOL 余额（需预留 0.02 SOL 作为 gas）-> 获取报价 -> 构造交易 -> 签名 -> 发送确认。成功返回 `True` |
| `sell()` | `token_address: str`, `percentage: float = 1.0`, `slippage_bps: int = 500` | `bool` | **卖出代币**。按百分比卖出持仓代币换回 SOL。流程：通过 RPC 查询代币账户余额 -> 计算卖出数量 -> 获取报价 -> 构造交易 -> 签名 -> 发送确认。`percentage=1.0` 表示全部卖出 |
| `close()` | - | - | 关闭 RPC 和 Jupiter 客户端的连接 |

**注意事项**：
- `buy()` 和 `sell()` 的默认滑点为 `500` bps（5%），高于 `ExecutionConfig` 中的默认值 `200` bps（2%），这是为了在实际交易中提供更大的滑点容差。
- `sell()` 方法通过 `get_token_accounts_by_owner_json_parsed` 查询代币余额，而非使用 `QuickNodeClient.get_token_balance()`（该方法尚未实现）。

---

### 5.5 `get_mint_decimals()`（utils.py）

| 参数 | 类型 | 说明 |
|------|------|------|
| `mint_str` | `str` | 代币的 Mint 地址 |
| `client` | `AsyncClient` | Solana RPC 异步客户端实例 |
| **返回值** | `int` | 代币的精度（decimals）。SOL 返回 `9`；其他代币通过链上查询获取；查询失败时默认返回 `6`（与 USDC 等主流稳定币一致） |
