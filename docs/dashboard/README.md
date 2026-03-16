# Dashboard 模块文档

## 1. 模块概述

`dashboard` 模块是 AlphaGPT 项目的实时监控仪表盘，基于 **Streamlit** 构建。它为用户提供一个 Web 界面，用于：

- 实时展示 Solana 钱包余额
- 查看当前持仓组合（Portfolio）及其盈亏分布
- 浏览数据库中最新的市场行情快照（流动性、交易量、FDV 等）
- 查看系统运行日志（尾部读取）
- 提供紧急停止（EMERGENCY STOP）控制功能，通过写入 `STOP_SIGNAL` 文件向交易进程发送终止信号
- 支持 30 秒自动刷新机制

该模块是一个纯展示与控制层，不包含任何交易逻辑或策略计算，它通过读取本地 JSON 文件、PostgreSQL 数据库和 Solana RPC 节点来获取数据，并借助 Plotly 进行交互式图表渲染。

---

## 2. 文件说明

| 文件 | 用途 | 关键内容 |
|------|------|----------|
| `app.py` | Streamlit 应用主入口 | 页面布局、侧边栏（钱包余额 / 控制面板）、四列指标卡片、三个 Tab（Portfolio / Market Scanner / Logs）、自动刷新逻辑 |
| `data_service.py` | 数据服务层 | `DashboardService` 类，负责连接 PostgreSQL 数据库、Solana RPC，读取 portfolio_state.json / best_meme_strategy.json / strategy.log，提供所有数据查询方法 |
| `visualizer.py` | 可视化层 | 两个 Plotly 图表生成函数：持仓盈亏柱状图 (`plot_pnl_distribution`) 和市场流动性-交易量散点图 (`plot_market_scatter`) |

---

## 3. 架构图

```
+------------------------------------------------------------------+
|                         app.py (Streamlit)                       |
|                        应用主入口 / UI 层                          |
|                                                                  |
|  +------------------+  +------------------+  +-----------------+ |
|  |    Sidebar       |  |   Metrics Row    |  |     Tabs        | |
|  | - Wallet Balance |  | - Open Positions |  | - Portfolio     | |
|  | - Refresh Button |  | - Total Invested |  | - Market Scanner| |
|  | - EMERGENCY STOP |  | - Unrealized PnL |  | - Logs          | |
|  +--------+---------+  | - Active Strategy|  +----+-----+------+ |
|           |             +--------+---------+       |     |        |
|           |                      |                 |     |        |
+-----------+----------------------+-----------------+-----+--------+
            |                      |                 |     |
            v                      v                 v     v
+------------------------------------------------------------------+
|                    data_service.py                                |
|                  DashboardService 类                               |
|                                                                  |
|  +---------------------+  +-------------------+  +-------------+ |
|  | get_wallet_balance() |  | load_portfolio()  |  | get_market_ | |
|  | (Solana RPC)         |  | (JSON 文件)        |  | overview()  | |
|  +---------------------+  +-------------------+  | (PostgreSQL)| |
|                            | load_strategy_    |  +-------------+ |
|                            |   info() (JSON)   |                  |
|                            +-------------------+  +-------------+ |
|                            | get_recent_logs() |  | _get_wallet_| |
|                            | (日志文件)         |  |  address()  | |
|                            +-------------------+  +-------------+ |
+------------------------------------------------------------------+
            |                                            |
            v                                            v
+------------------------------------------------------------------+
|                      visualizer.py                               |
|                     可视化图表层                                    |
|                                                                  |
|  +---------------------------+  +------------------------------+ |
|  | plot_pnl_distribution()   |  | plot_market_scatter()        | |
|  | 持仓盈亏百分比柱状图        |  | 流动性 vs 交易量散点图        | |
|  | (portfolio_df -> Figure)  |  | (market_df -> Figure)        | |
|  +---------------------------+  +------------------------------+ |
+------------------------------------------------------------------+

调用关系总结:

  app.py
    |
    +---> DashboardService()           # 实例化数据服务
    |       |
    |       +---> get_wallet_balance()  # Sidebar 钱包余额
    |       +---> load_portfolio()      # Tab1 + Metrics
    |       +---> get_market_overview() # Tab2
    |       +---> load_strategy_info()  # Metrics
    |       +---> get_recent_logs()     # Tab3
    |
    +---> plot_pnl_distribution()       # Tab1 图表
    +---> plot_market_scatter()         # Tab2 图表

外部数据源:

  [PostgreSQL]  <--- get_market_overview() (ohlcv + tokens 表)
  [Solana RPC]  <--- get_wallet_balance() / _get_wallet_address()
  [JSON 文件]   <--- load_portfolio()  (portfolio_state.json)
                <--- load_strategy_info() (best_meme_strategy.json)
  [日志文件]    <--- get_recent_logs() (strategy.log)
  [信号文件]    <--- EMERGENCY STOP 写入 STOP_SIGNAL 文件
```

---

## 4. 依赖关系

### 4.1 内部模块依赖

Dashboard 模块**不直接导入**其他 alphagpt 子模块（如 `data_pipeline`、`execution`、`model_core`、`strategy_manager` 等）。它通过以下间接方式与系统其他部分交互：

| 交互方式 | 说明 |
|----------|------|
| `portfolio_state.json` | 由交易执行模块写入，dashboard 读取当前持仓状态 |
| `best_meme_strategy.json` | 由策略/模型模块写入，dashboard 读取当前策略信息 |
| `strategy.log` | 由系统各模块写入的日志文件，dashboard 尾部读取展示 |
| `STOP_SIGNAL` 文件 | dashboard 写入，交易执行模块检测并终止 |
| PostgreSQL 数据库 (`ohlcv` / `tokens` 表) | 由 data_pipeline 模块写入，dashboard 查询读取 |

模块内部依赖关系：

```
app.py --imports--> data_service.py  (DashboardService)
app.py --imports--> visualizer.py    (plot_pnl_distribution, plot_market_scatter)
```

`data_service.py` 和 `visualizer.py` 之间没有直接依赖。

### 4.2 外部第三方依赖

| 包名 | 使用位置 | 用途 |
|------|----------|------|
| `streamlit` | `app.py` | Web 应用框架，提供 UI 组件、布局、缓存、自动刷新 |
| `pandas` | `app.py`, `data_service.py`, `visualizer.py` | DataFrame 数据处理 |
| `plotly` (`plotly.express`, `plotly.graph_objects`) | `visualizer.py` | 交互式图表生成 |
| `sqlalchemy` | `data_service.py` | 数据库连接引擎（PostgreSQL） |
| `python-dotenv` (`dotenv`) | `data_service.py` | 从 `.env` 文件加载环境变量 |
| `solders` (`solders.pubkey`, `solders.keypair`) | `data_service.py` | Solana 公钥/密钥对解析 |
| `solana` (`solana.rpc.api`) | `data_service.py` | Solana RPC 客户端，查询链上余额 |

### 4.3 环境变量

| 变量名 | 默认值 | 用途 |
|--------|--------|------|
| `DB_USER` | `postgres` | PostgreSQL 用户名 |
| `DB_PASSWORD` | `password` | PostgreSQL 密码 |
| `DB_HOST` | `localhost` | PostgreSQL 主机地址 |
| `DB_NAME` | `crypto_quant` | PostgreSQL 数据库名 |
| `QUICKNODE_RPC_URL` | `https://api.mainnet-beta.solana.com` | Solana RPC 节点地址 |
| `SOLANA_PRIVATE_KEY` | `""` | Solana 私钥（支持 JSON 数组或 Base58 字符串格式） |

---

## 5. 关键类/函数

### 5.1 `DashboardService` 类（data_service.py）

数据服务核心类，在 `app.py` 中通过 `@st.cache_resource` 缓存为单例。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__(self)` | 无 | - | 初始化 PostgreSQL 连接引擎 (`sqlalchemy.engine`)、Solana RPC 客户端 (`solana.rpc.api.Client`)、解析钱包地址 |
| `_get_wallet_address(self)` | 无 | `str` | 从环境变量 `SOLANA_PRIVATE_KEY` 解析 Solana 钱包公钥地址；支持 JSON 数组和 Base58 两种私钥格式；失败时返回 `"Unknown"` |
| `get_wallet_balance(self)` | 无 | `float` | 通过 Solana RPC 查询钱包 SOL 余额（lamports 转换为 SOL，除以 1e9）；失败返回 `0.0` |
| `load_portfolio(self)` | 无 | `pd.DataFrame` | 读取 `portfolio_state.json`，解析为 DataFrame；自动计算 `pnl_pct` 列 `(highest_price - entry_price) / entry_price`；文件不存在时返回空 DataFrame |
| `load_strategy_info(self)` | 无 | `dict` | 读取 `best_meme_strategy.json` 返回策略配置字典；文件不存在或解析失败时返回 `{"formula": "Not Trained Yet"}` |
| `get_market_overview(self, limit=50)` | `limit: int` -- 返回记录数上限，默认 50 | `pd.DataFrame` | 从 PostgreSQL 查询最新时间点的 OHLCV 数据（关联 `tokens` 表获取 symbol），按 liquidity 降序排列；包含列：`symbol`, `address`, `close`, `volume`, `liquidity`, `fdv`, `time` |
| `get_recent_logs(self, n=50)` | `n: int` -- 读取的日志行数，默认 50 | `list[str]` | 读取 `strategy.log` 文件的最后 n 行；文件不存在时返回空列表 |

### 5.2 可视化函数（visualizer.py）

| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `plot_pnl_distribution(portfolio_df)` | `portfolio_df: pd.DataFrame` -- 持仓数据，需包含 `symbol` 和 `pnl_pct` 列 | `go.Figure` | 生成持仓盈亏百分比柱状图；盈利为绿色 (`#00FF00`)，亏损为红色 (`#FF0000`)；使用 `plotly_dark` 主题 |
| `plot_market_scatter(market_df)` | `market_df: pd.DataFrame` -- 市场数据，需包含 `liquidity`, `volume`, `fdv`, `symbol` 列 | `go.Figure` | 生成市场流动性 vs 交易量对数散点图；气泡大小表示 FDV，颜色区分 token；使用 `plotly_dark` 主题 |

### 5.3 app.py 关键函数与机制

| 函数/机制 | 说明 |
|-----------|------|
| `get_service()` | 被 `@st.cache_resource` 装饰的工厂函数，返回 `DashboardService` 单例实例，确保数据库连接和 RPC 客户端在多次页面刷新间复用 |
| EMERGENCY STOP | 点击按钮后向当前工作目录写入 `STOP_SIGNAL` 文件（内容为 `"STOP"`），交易执行进程在下一个循环检测到该文件后终止 |
| Auto-Refresh | 通过 `st.checkbox` 控制的自动刷新机制，启用时每 30 秒调用 `st.rerun()` 重新执行整个脚本 |
| 页面布局 | 4 列指标卡片（持仓数 / 总投入 / 未实现盈亏 / 活跃策略）+ 3 个 Tab（Portfolio / Market Scanner / Logs） |
