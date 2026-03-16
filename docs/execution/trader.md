# execution/trader.py 文档

## 1. 文件概述

`trader.py` 是 execution 模块的核心交易引擎，定义了 `SolanaTrader` 类。该类整合了 `QuickNodeClient`（RPC 通信）和 `JupiterAggregator`（DEX 聚合），提供完整的链上代币买入（buy）和卖出（sell）流程。它是 execution 模块的最高层抽象，其他模块或上层应用只需调用 `buy/sell` 方法即可完成一笔完整的代币交换交易，无需关心报价获取、交易构建、签名、发送等底层细节。

文件末尾包含一个简单的测试入口（`__main__`），用于验证卖出流程。

## 2. 类与函数说明

### 类：`SolanaTrader`

Solana 链上交易的高层封装，协调 RPC 客户端与 Jupiter 聚合器完成买卖操作。

#### 构造方法

```python
def __init__(self)
```

- **参数**：无
- **行为**：
  - 创建 `QuickNodeClient` 实例 → `self.rpc`
  - 创建 `JupiterAggregator` 实例 → `self.jup`
  - 设置运行标志 `self.is_running = True`
  - 设置 SPL Token Program ID → `self.TOKEN_PROGRAM_ID`（`TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`）

#### 方法：`buy`

```python
async def buy(self, token_address: str, amount_sol: float, slippage_bps=500) -> bool
```

- **参数**：
  - `token_address` (`str`)：目标代币的 Mint 地址
  - `amount_sol` (`float`)：用于购买的 SOL 数量
  - `slippage_bps` (`int`, 默认 `500`)：滑点容忍度（基点，即 5%）
- **返回值**：`True` 表示购买成功；`False` 表示失败
- **用途**：使用指定数量的 SOL 购买目标代币。流程包括：余额检查 → 获取报价 → 构建交易 → 签名 → 发送并确认

#### 方法：`sell`

```python
async def sell(self, token_address: str, percentage: float = 1.0, slippage_bps=500) -> bool
```

- **参数**：
  - `token_address` (`str`)：要卖出的代币 Mint 地址
  - `percentage` (`float`, 默认 `1.0`)：卖出比例，`1.0` 表示全部卖出，`0.5` 表示卖出 50%
  - `slippage_bps` (`int`, 默认 `500`)：滑点容忍度（基点，即 5%）
- **返回值**：`True` 表示卖出成功；`False` 表示失败
- **用途**：按指定比例卖出持有的代币换回 SOL。流程包括：查询代币余额 → 计算卖出数量 → 获取报价 → 构建交易 → 签名 → 发送并确认

#### 方法：`close`

```python
async def close(self)
```

- **参数**：无
- **返回值**：无
- **用途**：关闭 RPC 客户端和 Jupiter 聚合器的连接，释放所有网络资源

### 测试函数（`__main__` 块）

```python
async def test_run()
```

- **用途**：当文件作为脚本直接运行时执行的测试函数
- **行为**：创建 `SolanaTrader` 实例，尝试以 50% 比例卖出 BONK 代币（`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`），然后关闭连接

### 常量

| 常量 | 值 | 说明 |
|---|---|---|
| `TOKEN_PROGRAM_ID` | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | SPL Token 标准程序的 Program ID，用于查询代币账户 |
| `BONK_ADDRESS`（测试用） | `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263` | BONK 代币地址，仅在测试代码中使用 |

## 3. 调用关系图

```
+---------------------------------------------------------------+
|                      SolanaTrader                             |
|---------------------------------------------------------------|
|                                                               |
|  __init__()                                                   |
|     ├─ QuickNodeClient()  → self.rpc                          |
|     ├─ JupiterAggregator() → self.jup                         |
|     └─ Pubkey.from_string() → self.TOKEN_PROGRAM_ID           |
|                                                               |
|  buy(token_address, amount_sol, slippage_bps)                 |
|     ├─ self.rpc.get_balance()          [余额检查]              |
|     ├─ self.jup.get_quote()            [获取报价]              |
|     ├─ self.jup.get_swap_tx()          [构建交易]              |
|     ├─ self.jup.deserialize_and_sign() [签名交易]              |
|     └─ self.rpc.send_and_confirm()     [发送并确认]            |
|                                                               |
|  sell(token_address, percentage, slippage_bps)                |
|     ├─ self.rpc.client                                        |
|     │   .get_token_accounts_by_owner_json_parsed()            |
|     │                                  [查询代币余额]          |
|     ├─ self.jup.get_quote()            [获取报价]              |
|     ├─ self.jup.get_swap_tx()          [构建交易]              |
|     ├─ self.jup.deserialize_and_sign() [签名交易]              |
|     └─ self.rpc.send_and_confirm()     [发送并确认]            |
|                                                               |
|  close()                                                      |
|     ├─ self.rpc.close()                                       |
|     └─ self.jup.close()                                       |
+---------------------------------------------------------------+

模块间交互关系：

  config.py ──────────────────────────────────┐
      │                                       │
      v                                       v
  rpc_handler.py (QuickNodeClient)    jupiter.py (JupiterAggregator)
      ^                                       ^
      │                                       │
      └──────── trader.py (SolanaTrader) ─────┘
                    │
                    v
              外部调用者（上层模块/命令行）
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|---|---|
| `asyncio` | 异步事件循环，用于测试入口的 `asyncio.run()` |
| `loguru` (`logger`) | 结构化日志记录（info、warning、error、success） |
| `solders.pubkey` (`Pubkey`) | Solana 公钥类型，用于构造 TOKEN_PROGRAM_ID 和地址解析 |
| `solana.rpc.types` (`TokenAccountOpts`) | 代币账户查询选项，用于按 mint 和 program_id 过滤代币账户 |

### 内部模块依赖

| 模块 | 导入内容 | 用途 |
|---|---|---|
| `execution.config` | `ExecutionConfig` | 获取 `SOL_MINT`（SOL 代币地址）、`WALLET_ADDRESS`（钱包地址） |
| `execution.rpc_handler` | `QuickNodeClient` | RPC 节点通信：余额查询、交易发送与确认 |
| `execution.jupiter` | `JupiterAggregator` | Jupiter DEX 聚合：报价获取、交易构建、交易签名 |

## 5. 代码逻辑流程

### 买入流程 (`buy`)

```
调用 buy(token_address, amount_sol, slippage_bps=500)
    │
    ├─ 1. 记录日志：执行买入操作
    │
    ├─ 2. 查询 SOL 余额
    │     └─ rpc.get_balance()
    │
    ├─ 3. 余额检查
    │     └─ 若 balance < amount_sol + 0.02（预留手续费）
    │         → 记录警告日志，返回 False
    │
    ├─ 4. 将 SOL 数量转换为 lamports
    │     └─ amount_lamports = int(amount_sol * 1e9)
    │
    ├─ 5. 获取 Jupiter 报价
    │     └─ jup.get_quote(SOL_MINT → token_address, amount_lamports)
    │         └─ 无报价 → 返回 False
    │
    ├─ 6. 记录预计输出数量
    │
    ├─ 7. 获取交换交易
    │     └─ jup.get_swap_tx(quote)
    │         └─ 失败 → 返回 False
    │
    ├─ 8. 反序列化并签名交易
    │     └─ jup.deserialize_and_sign(b64_tx)
    │         └─ 异常 → 记录错误，返回 False
    │
    ├─ 9. 发送并确认交易
    │     └─ rpc.send_and_confirm(txn)
    │         ├─ 成功 → 记录成功日志，返回 True
    │         └─ 失败 → 返回 False
    │
    └─ 返回 True 或 False
```

### 卖出流程 (`sell`)

```
调用 sell(token_address, percentage=1.0, slippage_bps=500)
    │
    ├─ 1. 记录日志：执行卖出操作
    │
    ├─ 2. 查询代币余额
    │     ├─ 构造 wallet_pubkey 和 mint_pubkey
    │     ├─ 创建 TokenAccountOpts（按 program_id 和 mint 过滤）
    │     ├─ 调用 rpc.client.get_token_accounts_by_owner_json_parsed()
    │     └─ 遍历返回结果，累加 raw_balance
    │
    ├─ 3. 余额检查
    │     ├─ raw_balance == 0 → 记录警告，返回 False
    │     └─ 计算 sell_amount = int(raw_balance * percentage)
    │         └─ sell_amount == 0 → 记录警告，返回 False
    │
    ├─ 4. 获取 Jupiter 报价
    │     └─ jup.get_quote(token_address → SOL_MINT, sell_amount)
    │         └─ 无报价 → 返回 False
    │
    ├─ 5. 获取交换交易
    │     └─ jup.get_swap_tx(quote)
    │         └─ 失败 → 返回 False
    │
    ├─ 6. 反序列化、签名、发送并确认交易
    │     ├─ jup.deserialize_and_sign(b64_tx)
    │     └─ rpc.send_and_confirm(txn)
    │         ├─ 成功 → 记录成功日志，返回 True
    │         └─ 异常 → 记录错误，返回 False
    │
    └─ 返回 True 或 False
```

### 资源清理流程 (`close`)

```
调用 close()
    │
    ├─ await self.rpc.close()  → 关闭 RPC 连接
    └─ await self.jup.close()  → 关闭 HTTP 会话
```

### 测试入口 (`__main__`)

```
直接运行 trader.py
    │
    ├─ 定义 test_run() 异步函数
    │     ├─ 创建 SolanaTrader
    │     ├─ 以 50% 比例卖出 BONK 代币
    │     └─ 关闭 trader
    │
    └─ asyncio.run(test_run())
        └─ KeyboardInterrupt → 静默退出
```
