# execution/rpc_handler.py 文档

## 1. 文件概述

`rpc_handler.py` 封装了与 Solana 区块链 RPC 节点（QuickNode）的底层通信逻辑。该文件定义了 `QuickNodeClient` 类，提供查询 SOL 余额、查询代币余额、发送并确认交易等核心链上操作。所有方法均采用异步（async）设计，基于 `solana-py` 的 `AsyncClient` 实现，并使用 `Confirmed` 承诺级别以确保数据可靠性。

## 2. 类与函数说明

### 类：`QuickNodeClient`

Solana RPC 客户端封装类，负责与 QuickNode 提供的 RPC 节点进行交互。

#### 构造方法

```python
def __init__(self)
```

- **参数**：无
- **行为**：使用 `ExecutionConfig.RPC_URL` 和 `Confirmed` 承诺级别创建 `AsyncClient` 实例，赋值给 `self.client`

#### 方法：`get_balance`

```python
async def get_balance(self) -> float
```

- **参数**：无
- **返回值**：`float` 类型的 SOL 余额（已从 lamports 转换为 SOL，即除以 `1e9`）
- **异常处理**：捕获所有异常，记录错误日志并返回 `0.0`
- **用途**：查询配置中钱包地址的 SOL 原生代币余额

#### 方法：`get_token_balance`

```python
async def get_token_balance(self, mint_address: str)
```

- **参数**：
  - `mint_address` (`str`)：代币的 Mint 地址
- **返回值**：无（当前为占位实现，函数体为 `pass`）
- **用途**：预留接口，用于查询指定 SPL 代币的余额。当前尚未实现

#### 方法：`send_and_confirm`

```python
async def send_and_confirm(self, txn, max_retries=3) -> str | None
```

- **参数**：
  - `txn`：已签名的 Solana 交易对象（`VersionedTransaction`）
  - `max_retries` (`int`, 默认 `3`)：最大重试次数（注意：当前代码中未实际使用此参数进行重试逻辑）
- **返回值**：成功时返回交易签名字符串；失败时返回 `None`
- **用途**：将签名后的交易发送到 Solana 网络，等待链上确认，并返回交易签名。成功时会输出 Solscan 浏览器链接
- **异常处理**：捕获所有异常，记录错误日志并返回 `None`

#### 方法：`close`

```python
async def close(self)
```

- **参数**：无
- **返回值**：无
- **用途**：关闭 RPC 客户端连接，释放网络资源

## 3. 调用关系图

```
+-------------------------------------------------------+
|               QuickNodeClient                         |
|-------------------------------------------------------|
|                                                       |
|  __init__()                                           |
|     └─ AsyncClient(RPC_URL, commitment=Confirmed)     |
|                                                       |
|  get_balance()                                        |
|     └─ self.client.get_balance(PAYER_KEYPAIR.pubkey())|
|        └─ resp.value / 1e9 → SOL 余额                 |
|                                                       |
|  get_token_balance(mint_address)                      |
|     └─ (未实现，pass)                                  |
|                                                       |
|  send_and_confirm(txn)                                |
|     ├─ self.client.send_transaction(txn)              |
|     └─ self.client.confirm_transaction(sig)           |
|        └─ 返回交易签名字符串                            |
|                                                       |
|  close()                                              |
|     └─ self.client.close()                            |
+-------------------------------------------------------+

外部调用关系：
  trader.py (SolanaTrader)
      │
      ├─ self.rpc = QuickNodeClient()
      ├─ self.rpc.get_balance()         [buy 方法中检查余额]
      ├─ self.rpc.send_and_confirm(txn) [buy/sell 方法中提交交易]
      ├─ self.rpc.client.get_token_accounts_by_owner_json_parsed()
      │                                 [sell 方法中直接访问底层 client]
      └─ self.rpc.close()              [资源清理]
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|---|---|
| `solana.rpc.async_api` (`AsyncClient`) | Solana 异步 RPC 客户端，用于与链上节点通信 |
| `solana.rpc.commitment` (`Confirmed`) | 交易承诺级别枚举，`Confirmed` 表示交易已被超多数验证者确认 |
| `loguru` (`logger`) | 结构化日志记录，包括 `info`、`error`、`success` 级别 |

### 内部模块依赖

| 模块 | 导入内容 | 用途 |
|---|---|---|
| `execution.config` | `ExecutionConfig` | 获取 `RPC_URL`（节点地址）和 `PAYER_KEYPAIR`（钱包密钥对） |

## 5. 代码逻辑流程

### 查询余额流程 (`get_balance`)

```
调用 get_balance()
    │
    ├─ 1. 通过 RPC 调用 get_balance()
    │     └─ 传入 PAYER_KEYPAIR.pubkey() 作为查询地址
    │
    ├─ 2. 将返回的 lamports 值除以 1e9 转换为 SOL
    │
    └─ 返回 float 类型余额
        （异常时返回 0.0）
```

### 发送并确认交易流程 (`send_and_confirm`)

```
调用 send_and_confirm(txn, max_retries=3)
    │
    ├─ 1. 调用 self.client.send_transaction(txn, opts=None)
    │     └─ 将签名交易提交到 Solana 网络
    │
    ├─ 2. 记录交易签名信息日志
    │
    ├─ 3. 调用 self.client.confirm_transaction(signature.value)
    │     └─ 等待链上确认交易
    │
    ├─ 4. 记录成功日志（含 Solscan 链接）
    │
    └─ 返回签名字符串（str）
        （异常时记录错误日志，返回 None）
```

### 关闭连接流程 (`close`)

```
调用 close()
    │
    └─ 调用 self.client.close()
        └─ 关闭底层 HTTP 连接
```

**注意事项**：`send_and_confirm` 方法声明了 `max_retries` 参数但当前代码中并未实现重试逻辑。这可能是为后续扩展预留的接口。此外，`get_token_balance` 方法当前为空实现（`pass`），实际的代币余额查询在 `trader.py` 的 `sell` 方法中直接通过 `self.rpc.client` 完成。
