# execution/config.py 文档

## 1. 文件概述

`config.py` 是 execution 模块的配置中心，负责从环境变量中加载 Solana 链上交易所需的全部关键配置参数。该文件定义了 `ExecutionConfig` 类，包含 RPC 节点地址、钱包密钥对、钱包地址、默认滑点、优先级费用等级以及常用代币的 Mint 地址等。模块加载时会自动读取 `.env` 文件并完成密钥解析，确保其他模块在 import 时即可直接使用这些配置常量。

## 2. 类与函数说明

### 类：`ExecutionConfig`

一个纯配置类（无实例方法），所有属性均为类级别属性，作为项目全局配置的集中存取点。

#### 类属性

| 属性名 | 类型 | 说明 |
|---|---|---|
| `RPC_URL` | `str` | Solana RPC 节点地址，从环境变量 `QUICKNODE_RPC_URL` 读取，若未设置则使用占位符 `"填入RPC地址"` |
| `_PRIV_KEY_STR` | `str` | 私钥字符串（内部变量），从环境变量 `SOLANA_PRIVATE_KEY` 读取。若为空则抛出 `ValueError` |
| `PAYER_KEYPAIR` | `Keypair` | Solana 钱包密钥对对象。首先尝试以 Base58 格式解析私钥字符串；若失败则尝试以 JSON 数组格式（字节数组）解析 |
| `WALLET_ADDRESS` | `str` | 钱包公钥地址字符串，由 `PAYER_KEYPAIR.pubkey()` 自动导出 |
| `DEFAULT_SLIPPAGE_BPS` | `int` | 默认交易滑点，单位为基点（bps），默认值 `200`（即 2%） |
| `PRIORITY_LEVEL` | `str` | 交易优先级费用等级，默认值 `"High"` |
| `SOL_MINT` | `str` | SOL 原生代币的 Mint 地址：`So11111111111111111111111111111111111111112` |
| `USDC_MINT` | `str` | USDC 稳定币的 Mint 地址：`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |

### 顶层语句

| 语句 | 说明 |
|---|---|
| `load_dotenv()` | 在模块导入时立即调用，将 `.env` 文件中的键值对注入到当前进程的环境变量中 |

## 3. 调用关系图

```
.env 文件
   |
   v
load_dotenv()          <-- 加载环境变量
   |
   v
+----------------------------------------------+
|           ExecutionConfig (类)                |
|----------------------------------------------|
| os.getenv("QUICKNODE_RPC_URL") --> RPC_URL   |
| os.getenv("SOLANA_PRIVATE_KEY") --> _PRIV_KEY|
|   |                                          |
|   +---> Keypair.from_base58_string()         |
|   |       (失败时)                            |
|   +---> json.loads() + Keypair.from_bytes()  |
|   |                                          |
|   +---> PAYER_KEYPAIR.pubkey()               |
|         --> WALLET_ADDRESS                   |
+----------------------------------------------+
         |
         | 被以下模块引用：
         v
   jupiter.py   (JupiterAggregator)
   rpc_handler.py (QuickNodeClient)
   trader.py     (SolanaTrader)
   utils.py      (get_mint_decimals)
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|---|---|
| `os` | 读取环境变量 |
| `dotenv` (`load_dotenv`) | 从 `.env` 文件加载环境变量 |
| `solders.keypair` (`Keypair`) | 构建 Solana 钱包密钥对 |
| `base58` | 已导入但未在当前文件中直接使用（可能为保留或兼容用途） |
| `json` | 当 Base58 解析失败时，用于将 JSON 字符串转换为字节数组 |

### 内部模块依赖

无。`config.py` 是 execution 模块的底层配置文件，不依赖项目内其他模块。

## 5. 代码逻辑流程

```
模块被 import
    │
    ├─ 1. 调用 load_dotenv() 加载 .env 文件
    │
    ├─ 2. 从环境变量读取 RPC_URL
    │     └─ 若 QUICKNODE_RPC_URL 不存在，使用默认占位符
    │
    ├─ 3. 从环境变量读取 _PRIV_KEY_STR
    │     └─ 若为空字符串 → 抛出 ValueError，终止程序
    │
    ├─ 4. 解析密钥对 PAYER_KEYPAIR
    │     ├─ 尝试 Keypair.from_base58_string() 解析
    │     │     └─ 成功 → 得到 PAYER_KEYPAIR
    │     └─ 捕获异常 → 用 json.loads() 将字符串解析为列表
    │           └─ 调用 Keypair.from_bytes() 解析字节数组
    │
    ├─ 5. 从 PAYER_KEYPAIR 导出公钥 → WALLET_ADDRESS
    │
    └─ 6. 设置交易常量
          ├─ DEFAULT_SLIPPAGE_BPS = 200
          ├─ PRIORITY_LEVEL = "High"
          ├─ SOL_MINT = "So1111...112"
          └─ USDC_MINT = "EPjFWdd...t1v"
```

整个流程在模块加载阶段（`import` 时）同步执行。若 `SOLANA_PRIVATE_KEY` 环境变量缺失，程序将在 import 阶段直接报错退出，这是一种"快速失败"（fail-fast）的设计策略，确保不会在后续交易环节才发现密钥缺失的问题。
