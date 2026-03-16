# execution/utils.py 文档

## 1. 文件概述

`utils.py` 是 execution 模块的工具函数集合，目前包含一个用于查询 Solana 链上代币精度（decimals）的异步辅助函数。该函数通过 RPC 调用获取代币 Mint 账户的元数据，解析出其小数位数（decimals），可用于将代币原始数量（raw amount）与人类可读数量之间进行转换。

## 2. 类与函数说明

### 函数：`get_mint_decimals`

```python
async def get_mint_decimals(mint_str: str, client: AsyncClient) -> int
```

- **参数**：
  - `mint_str` (`str`)：代币的 Mint 地址字符串
  - `client` (`AsyncClient`)：已初始化的 Solana 异步 RPC 客户端实例
- **返回值**：`int` 类型的小数位数
- **用途**：查询指定代币的精度（decimals）。用于在代币原始单位和可读单位之间转换（例如 SOL 的精度为 9，即 1 SOL = 10^9 lamports）

#### 返回值逻辑

| 情况 | 返回值 |
|---|---|
| `mint_str` 等于 `ExecutionConfig.SOL_MINT` | 直接返回 `9`（SOL 的已知精度） |
| RPC 查询成功且账户存在 | 返回解析到的实际 `decimals` 值 |
| RPC 查询返回 `None`（账户不存在） | 返回默认值 `6` |
| 发生任何异常 | 返回默认值 `6` |

**注意**：默认值 `6` 的选择是因为 Solana 链上大多数 SPL 代币（包括 USDC、USDT）使用 6 位精度。

## 3. 调用关系图

```
+--------------------------------------------------+
|                   utils.py                       |
|--------------------------------------------------|
|                                                  |
|  get_mint_decimals(mint_str, client)             |
|     │                                            |
|     ├─ [快速路径] mint_str == SOL_MINT?           |
|     │     └─ 是 → 直接返回 9                      |
|     │                                            |
|     ├─ Pubkey.from_string(mint_str)              |
|     │                                            |
|     ├─ client.get_account_info(pubkey)           |
|     │     └─ resp.value is None → 返回 6         |
|     │                                            |
|     └─ client.get_account_info_json_parsed(pubkey)|
|           └─ 解析 parsed['info']['decimals']      |
|              └─ 返回 int(decimals)                |
|                                                  |
|     [异常] → 返回 6                               |
+--------------------------------------------------+

外部调用关系：

  ExecutionConfig.SOL_MINT
      │
      v
  get_mint_decimals() <── 可由 trader.py 或其他模块调用
      │                    （当前代码中未见直接调用，
      │                     但作为工具函数对外暴露）
      v
  AsyncClient (solana RPC)
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|---|---|
| `solana.rpc.async_api` (`AsyncClient`) | Solana 异步 RPC 客户端，类型注解及传入参数 |
| `solders.pubkey` (`Pubkey`) | Solana 公钥类型，将 Mint 地址字符串转换为 `Pubkey` 对象 |

### 内部模块依赖

| 模块 | 导入内容 | 用途 |
|---|---|---|
| `execution.config` | `ExecutionConfig` | 获取 `SOL_MINT` 常量，用于快速判断是否为 SOL 原生代币 |

## 5. 代码逻辑流程

```
调用 get_mint_decimals(mint_str, client)
    │
    ├─ 1. 快速路径检查
    │     └─ mint_str == ExecutionConfig.SOL_MINT ?
    │         ├─ 是 → 直接返回 9（SOL 精度为 9 位，无需 RPC 调用）
    │         └─ 否 → 继续
    │
    ├─ 2. 将字符串转换为 Pubkey 对象
    │     └─ pubkey = Pubkey.from_string(mint_str)
    │
    ├─ 3. 第一次 RPC 查询：get_account_info(pubkey)
    │     └─ 目的：检查账户是否存在
    │         └─ resp.value is None → 返回默认值 6
    │
    ├─ 4. 第二次 RPC 查询：get_account_info_json_parsed(pubkey)
    │     └─ 获取已解析的账户数据
    │         └─ 从 parsed['info']['decimals'] 提取精度值
    │
    ├─ 5. 返回 int(decimals)
    │
    └─ [异常处理]
        └─ 捕获所有异常 → 返回默认值 6
```

**设计说明**：

- 该函数采用了"快速路径"优化，对于已知的 SOL 代币直接返回精度值 `9`，避免不必要的 RPC 调用。
- 函数进行了两次 RPC 调用：第一次 `get_account_info` 仅用于检查账户是否存在，第二次 `get_account_info_json_parsed` 获取解析后的账户数据。这种分步设计确保了在账户不存在时能够安全返回默认值。
- 默认返回值 `6` 是一种安全的降级策略，因为 Solana 生态中大部分主流代币采用 6 位精度。
