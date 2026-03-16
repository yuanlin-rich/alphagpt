# dashboard/data_service.py 文档

## 1. 文件概述

`data_service.py` 是 Dashboard 模块的数据服务层，定义了 `DashboardService` 类，封装了所有数据获取逻辑。该文件负责：

- 连接 PostgreSQL 数据库（通过 SQLAlchemy）
- 连接 Solana 区块链 RPC 节点（通过 solana-py）
- 从本地 JSON 文件加载投资组合状态和策略配置
- 从数据库查询市场概览数据
- 读取系统日志文件

该类是 `app.py` 与底层数据源之间的桥梁，实现了数据访问的统一抽象。

## 2. 类与函数说明

### 类: `DashboardService`

数据服务核心类，在初始化时建立数据库连接和 Solana RPC 连接。

#### `__init__(self)`

- **参数**: 无
- **用途**: 初始化数据服务，完成以下操作：
  1. 从环境变量读取数据库连接参数（`DB_USER`、`DB_PASSWORD`、`DB_HOST`、`DB_NAME`），有默认值
  2. 使用 SQLAlchemy 创建 PostgreSQL 数据库引擎 (`self.engine`)
  3. 从环境变量读取 Solana RPC URL（`QUICKNODE_RPC_URL`），默认值为 Solana 主网公共节点
  4. 创建 Solana RPC 客户端 (`self.rpc`)
  5. 调用 `_get_wallet_address()` 获取钱包地址 (`self.wallet_addr`)

#### `_get_wallet_address(self) -> str`

- **参数**: 无
- **返回值**: `str` -- 钱包公钥地址字符串，失败时返回 `"Unknown"`
- **用途**: 从环境变量 `SOLANA_PRIVATE_KEY` 解析钱包公钥地址。支持两种私钥格式：
  - JSON 数组格式（包含 `[` 字符时），使用 `Keypair.from_bytes()` 解析
  - Base58 字符串格式，使用 `Keypair.from_base58_string()` 解析
- **注意**: 该方法为内部方法（以 `_` 开头），仅在 `__init__` 中调用。`Keypair` 是在函数内部延迟导入的。

#### `get_wallet_balance(self) -> float`

- **参数**: 无
- **返回值**: `float` -- 钱包 SOL 余额（单位：SOL），失败时返回 `0.0`
- **用途**: 通过 Solana RPC 调用 `get_balance` 查询当前钱包的 SOL 余额。原始返回值单位为 lamport（1 SOL = 10^9 lamport），除以 `1e9` 转换为 SOL。

#### `load_portfolio(self) -> pd.DataFrame`

- **参数**: 无
- **返回值**: `pd.DataFrame` -- 投资组合数据，包含各持仓的详细信息；文件不存在或为空时返回空 DataFrame
- **用途**: 从本地文件 `portfolio_state.json` 加载投资组合状态。加载后：
  1. 将 JSON 对象的 values 转换为 DataFrame
  2. 若包含 `highest_price` 和 `entry_price` 列，计算 `pnl_pct`（盈亏百分比）= `(highest_price - entry_price) / entry_price`
- **异常处理**: 捕获 `FileNotFoundError`，返回空 DataFrame

#### `load_strategy_info(self) -> dict`

- **参数**: 无
- **返回值**: `dict` -- 策略配置信息；文件不存在或 JSON 解析失败时返回 `{"formula": "Not Trained Yet"}`
- **用途**: 从本地文件 `best_meme_strategy.json` 加载策略配置数据
- **异常处理**: 捕获 `FileNotFoundError` 和 `json.JSONDecodeError`

#### `get_market_overview(self, limit=50) -> pd.DataFrame`

- **参数**:
  - `limit` (`int`, 默认 `50`): 返回的最大记录数
- **返回值**: `pd.DataFrame` -- 市场概览数据（symbol, address, close, volume, liquidity, fdv, time）；查询失败时返回空 DataFrame
- **用途**: 从 PostgreSQL 数据库查询最新时间点的 OHLCV 数据，关联 `tokens` 表获取代币符号，按流动性降序排列
- **SQL 查询逻辑**:
  ```sql
  SELECT t.symbol, o.address, o.close, o.volume, o.liquidity, o.fdv, o.time
  FROM ohlcv o
  JOIN tokens t ON o.address = t.address
  WHERE o.time = (SELECT MAX(time) FROM ohlcv)
  ORDER BY o.liquidity DESC
  LIMIT {limit}
  ```

#### `get_recent_logs(self, n=50) -> list[str]`

- **参数**:
  - `n` (`int`, 默认 `50`): 返回的最近日志行数
- **返回值**: `list[str]` -- 日志文件最后 n 行的列表；文件不存在时返回空列表
- **用途**: 读取本地 `strategy.log` 文件的最后 n 行，用于在仪表盘展示系统运行日志

### 顶层调用

| 语句 | 说明 |
|------|------|
| `load_dotenv()` | 在模块加载时从 `.env` 文件读取环境变量 |

## 3. 调用关系图

```
DashboardService
  |
  |-- __init__()
  |     |-- sqlalchemy.create_engine()     --> self.engine (PostgreSQL)
  |     |-- Client(rpc_url)                --> self.rpc (Solana RPC)
  |     +-- _get_wallet_address()          --> self.wallet_addr
  |           |
  |           +-- Keypair.from_bytes() 或 Keypair.from_base58_string()
  |                   (延迟导入 solders.keypair.Keypair)
  |
  |-- get_wallet_balance()
  |     +-- self.rpc.get_balance(Pubkey)
  |
  |-- load_portfolio()
  |     +-- 读取 portfolio_state.json --> pd.DataFrame
  |
  |-- load_strategy_info()
  |     +-- 读取 best_meme_strategy.json --> dict
  |
  |-- get_market_overview(limit)
  |     +-- pd.read_sql(query, self.engine)  --> 查询 ohlcv + tokens 表
  |
  +-- get_recent_logs(n)
        +-- 读取 strategy.log --> list[str]


外部数据源交互:

  +-------------------+
  | DashboardService  |
  +--------+----------+
           |
     +-----+-----+-----+-----+-----+
     |           |           |       |
     v           v           v       v
 PostgreSQL   Solana     .json     .log
 (ohlcv,     RPC Node   文件       文件
  tokens)    (余额查询)  (组合/策略) (日志)
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `json` | JSON 文件的读取与解析 |
| `os` | 环境变量读取 (`os.getenv`)、文件存在性检查 (`os.path.exists`) |
| `pandas` (`pd`) | 数据处理，将查询结果和 JSON 数据转为 DataFrame |
| `sqlalchemy` | 创建 PostgreSQL 数据库连接引擎 |
| `dotenv` (`load_dotenv`) | 从 `.env` 文件加载环境变量 |
| `solders.pubkey` (`Pubkey`) | Solana 公钥对象，用于 RPC 调用 |
| `solders.keypair` (`Keypair`) | Solana 密钥对对象（延迟导入），用于从私钥派生公钥 |
| `solana.rpc.api` (`Client`) | Solana RPC 客户端，用于链上查询 |

### 内部模块依赖

无直接的项目内部模块依赖。该文件作为数据层，被 `app.py` 调用。

### 环境变量依赖

| 变量名 | 默认值 | 用途 |
|--------|--------|------|
| `DB_USER` | `"postgres"` | 数据库用户名 |
| `DB_PASSWORD` | `"password"` | 数据库密码 |
| `DB_HOST` | `"localhost"` | 数据库主机地址 |
| `DB_NAME` | `"crypto_quant"` | 数据库名称 |
| `QUICKNODE_RPC_URL` | `"https://api.mainnet-beta.solana.com"` | Solana RPC 端点 URL |
| `SOLANA_PRIVATE_KEY` | `""` | Solana 钱包私钥（JSON 数组或 Base58 格式） |

### 文件依赖

| 文件 | 用途 | 必须存在 |
|------|------|---------|
| `.env` | 环境变量配置 | 否（有默认值） |
| `portfolio_state.json` | 投资组合状态数据 | 否（缺失时返回空 DataFrame） |
| `best_meme_strategy.json` | 策略配置 | 否（缺失时返回默认 dict） |
| `strategy.log` | 系统运行日志 | 否（缺失时返回空列表） |

## 5. 代码逻辑流程

```
模块加载
  |
  v
load_dotenv()  -- 读取 .env 环境变量
  |
  v
DashboardService.__init__() 被调用 (由 app.py 触发)
  |
  +---> 读取 DB_USER / DB_PASSWORD / DB_HOST / DB_NAME 环境变量
  |         |
  |         v
  |     sqlalchemy.create_engine("postgresql://...")  --> self.engine
  |
  +---> 读取 QUICKNODE_RPC_URL 环境变量
  |         |
  |         v
  |     Client(rpc_url)  --> self.rpc
  |
  +---> _get_wallet_address()
            |
            +---> 读取 SOLANA_PRIVATE_KEY 环境变量
            |         |
            |         v
            |     判断私钥格式:
            |       - 含 "[" --> Keypair.from_bytes(json.loads(pk_str))
            |       - 否则   --> Keypair.from_base58_string(pk_str)
            |         |
            |         v
            |     返回 str(kp.pubkey())
            |
            +---> 异常 --> 返回 "Unknown"

后续各方法独立按需调用:

get_wallet_balance():
  Pubkey.from_string(wallet_addr) --> rpc.get_balance() --> value / 1e9

load_portfolio():
  打开 portfolio_state.json --> json.load()
    --> pd.DataFrame(data.values())
    --> 计算 pnl_pct = (highest_price - entry_price) / entry_price

load_strategy_info():
  打开 best_meme_strategy.json --> json.load() --> 返回 dict

get_market_overview(limit):
  构造 SQL (JOIN ohlcv + tokens, 最新时间, 按 liquidity 降序)
    --> pd.read_sql(query, engine) --> 返回 DataFrame

get_recent_logs(n):
  检查 strategy.log 是否存在
    --> 读取全部行 --> 返回最后 n 行
```
