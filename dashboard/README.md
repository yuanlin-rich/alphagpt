# MemeAlpha Commander Dashboard 功能说明

本目录提供一个用 Streamlit 构建的监控与控制面板，用于观察加密量化交易机器人（“MemeAlpha Bot”）的账户状态、持仓表现、市场概览，并提供紧急停机信号与日志查看能力。

## 目录结构
- dashboard/app.py —— 页面与交互逻辑（Streamlit UI）
- dashboard/data_service.py —— 数据访问与服务封装（Postgres、Solana RPC、本地文件）
- dashboard/visualizer.py —— 可视化组件（Plotly 图表）

## 总体功能
- 钱包余额展示与控制面板（刷新、紧急停止）
- 顶部核心指标：持仓数量、总投入、未实现盈亏、当前策略信息
- 标签页：持仓视图、市场扫描（快照）、系统日志尾部查看
- 自动刷新选项以便周期性更新数据

## 关键模块与职责

### 1) 页面与交互：app.py
- 页面配置（深色主题布局）：dashboard/app.py:7-12
- 自定义样式（metric 卡片等）：dashboard/app.py:14-24
- 服务实例缓存（避免重复初始化）：dashboard/app.py:26-30
- 侧边栏
  - 钱包状态（SOL 余额）：从服务层获取并展示，dashboard/app.py:35-39
  - 控制面板：
    - 刷新数据按钮触发整页重绘：dashboard/app.py:41-43
    - 紧急停止按钮写入本地信号文件 STOP_SIGNAL：dashboard/app.py:45-48
- 顶部指标（四列）：dashboard/app.py:50-71
  - Open Positions：当前持仓数量/允许上限，dashboard/app.py:55,58-60
  - Total Invested：按 portfolio_df['initial_cost_sol'] 汇总，dashboard/app.py:56,61
  - Unrealized PnL (Est)：按 (amount_held * highest_price).sum - total_invested 估算，dashboard/app.py:63-68
  - Active Strategy：展示固定标签（AlphaGPT-v1）并以策略 JSON 作为帮助说明，dashboard/app.py:70
- 标签页：dashboard/app.py:72-106
  - Portfolio
    - 表格列：symbol, entry_price, highest_price, amount_held, pnl_pct, is_moonbag，dashboard/app.py:78-85
    - 图表：持仓收益率分布柱状图（plot_pnl_distribution），dashboard/app.py:87-89
  - Market Scanner
    - 图表：流动性-成交量气泡散点图（气泡大小为 FDV，log 坐标），dashboard/app.py:92-97
    - 表格：市场概览快照，dashboard/app.py:94,96
  - Logs
    - 日志尾部 20 行，dashboard/app.py:100-106
- 自动刷新：勾选后每 30s 触发 rerun，dashboard/app.py:108-111

### 2) 数据服务：data_service.py
- 环境加载：dotenv，dashboard/data_service.py:9
- 初始化：
  - Postgres 连接（SQLAlchemy）：由 DB_USER、DB_PASSWORD、DB_HOST、DB_NAME 构建引擎，dashboard/data_service.py:13-18
  - Solana RPC 客户端：QUICKNODE_RPC_URL，dashboard/data_service.py:18-19
  - 钱包地址解析：从 SOLANA_PRIVATE_KEY 解析（支持字节数组 JSON 或 base58 字符串），dashboard/data_service.py:22-33
- 钱包余额：按 lamports/1e9 转换展示 SOL，dashboard/data_service.py:34-39
- 持仓加载：从本地 portfolio_state.json 构建 DataFrame，并计算 pnl_pct（(highest_price - entry_price)/entry_price），dashboard/data_service.py:41-52
- 策略信息：读取 best_meme_strategy.json，失败时返回默认说明，dashboard/data_service.py:55-60
- 市场概览：从数据库 ohlcv 与 tokens 关联，选取最新时间的快照并按流动性降序，dashboard/data_service.py:62-74
- 日志尾部：读取 strategy.log 并返回最后 n 行，dashboard/data_service.py:76-82

### 3) 可视化：visualizer.py
- 持仓收益率分布：按 pnl_pct 颜色区分（正绿负红），柱状图，dashboard/visualizer.py:5-23
- 市场散点图：x=liquidity, y=volume, size=fdv, color=symbol，log_x/log_y，dashboard/visualizer.py:25-40

## 数据来源与依赖
- 数据库（Postgres）：
  - 环境变量：DB_USER、DB_PASSWORD、DB_HOST、DB_NAME
  - 表：ohlcv、tokens（用于市场概览快照）
- 区块链 RPC（Solana）：
  - QUICKNODE_RPC_URL（RPC 地址）
  - SOLANA_PRIVATE_KEY（私钥；解析后用于获取钱包地址）
- 本地文件：
  - portfolio_state.json（持仓状态）
  - best_meme_strategy.json（策略信息）
  - strategy.log（运行日志）

- 主要第三方依赖：
  - streamlit、pandas、plotly（express/graph_objects）、sqlalchemy、python-dotenv
  - solders、solana-py（钱包与 RPC）

## 使用方式（示例）
- 在项目根目录下运行：
  - `pip install -r requirements.txt`
  - `streamlit run dashboard/app.py`
- 浏览器访问：`http://localhost:8501`
- 若页面右上角出现“Sign in/Share/Deploy”，这是 Streamlit Cloud 的登录入口，本地使用可忽略，不需要输入邮箱

## 独立运行与费用说明
- 本地运行不需要注册任何账号即可启动；UI 会渲染，但无外部数据时页面显示空或默认值
- 想“完整运行”，推荐配置：
  - Solana RPC 服务（QuickNode/Helius/Alchemy 等）：通常有免费层，稳定高配需付费
  - Postgres 数据库（本地免费；云端如 Neon/Supabase/Railway/Render 等通常有免费层）
  - 行情/聚合 API（如 Birdeye/Jupiter，取决于数据管道）：常见有免费 API Key，更高用量付费
  - Streamlit Cloud（仅当要在线托管）：通常有免费层，团队/企业版付费

## 环境变量模板（.env）
- 最小可运行（无需账号，部分数据为空）：
```
# .env (minimal, no accounts)
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_NAME=crypto_quant

QUICKNODE_RPC_URL=https://api.mainnet-beta.solana.com

# 留空则钱包显示 Unknown，余额为 0.0
SOLANA_PRIVATE_KEY=
```
- 推荐“完整运行”（需稳定 RPC/数据库，通常有免费层）：
```
# .env (recommended)
DB_USER=your_user
DB_PASSWORD=your_password
DB_HOST=your_db_host_or_ip
DB_NAME=crypto_quant

# 任一稳定 RPC 服务商（QuickNode/Helius/Alchemy 等）
QUICKNODE_RPC_URL=https://your-solana-rpc.example.com/<your_key>

# 私钥（仅用于解析地址与查询余额；请使用测试/只读钱包）
# 支持两种格式：base58 字符串，或字节数组 JSON（示例二选一）
SOLANA_PRIVATE_KEY=Base58PrivateKeyHere
# 或：
# SOLANA_PRIVATE_KEY=[1,2,3,...]
```

## 本地演示示例文件
- portfolio_state.json（对象结构；键可用代币地址或自定义 ID）：
```
{
  "So11111111111111111111111111111111111111112": {
    "symbol": "TEST",
    "entry_price": 0.0001,
    "highest_price": 0.00012,
    "amount_held": 10000,
    "initial_cost_sol": 0.5,
    "is_moonbag": false
  },
  "MintAddressOrId-2": {
    "symbol": "DEMO",
    "entry_price": 0.002,
    "highest_price": 0.0018,
    "amount_held": 2000,
    "initial_cost_sol": 0.3,
    "is_moonbag": true
  }
}
```
说明：必需字段为 symbol、entry_price、highest_price、amount_held、initial_cost_sol、is_moonbag；pnl_pct 在运行时自动计算

- best_meme_strategy.json：
```
{
  "name": "AlphaGPT-v1",
  "formula": "demo_formula_v1",
  "notes": "Demo strategy for local dashboard preview only."
}
```

- strategy.log（纯文本，用于 Logs 标签页）：
```
2026-02-26T09:00:01Z INFO Starting scan cycle...
2026-02-26T09:00:03Z INFO Fetched 50 tokens snapshot.
2026-02-26T09:00:05Z WARN Liquidity below threshold for DEMO.
2026-02-26T09:00:10Z INFO Cycle complete.
```

## 下载/查看本地示例文件
- [.env](../.env)
- [portfolio_state.json](../portfolio_state.json)
- [best_meme_strategy.json](../best_meme_strategy.json)
- [strategy.log](../strategy.log)

> 说明：以上为本地文件的相对链接；在 IDE 或 GitHub 查看器中可直接点击打开。Streamlit 页面本身不提供文件下载。

## Postgres 表结构示例（最小）
> 满足 Market Scanner 所需查询（dashboard/data_service.py:62-74）

```sql
-- tokens：代币基础信息
CREATE TABLE IF NOT EXISTS tokens (
  address TEXT PRIMARY KEY,
  symbol  TEXT NOT NULL,
  name    TEXT
);

-- ohlcv：行情快照（含扩展字段供仪表盘使用）
CREATE TABLE IF NOT EXISTS ohlcv (
  id        BIGSERIAL PRIMARY KEY,
  address   TEXT NOT NULL REFERENCES tokens(address),
  time      TIMESTAMPTZ NOT NULL,
  open      DOUBLE PRECISION,
  high      DOUBLE PRECISION,
  low       DOUBLE PRECISION,
  close     DOUBLE PRECISION NOT NULL,
  volume    DOUBLE PRECISION,
  liquidity DOUBLE PRECISION,
  fdv       DOUBLE PRECISION
);

-- 索引以支持最新快照与按流动性排序
CREATE INDEX IF NOT EXISTS idx_ohlcv_time ON ohlcv(time);
CREATE INDEX IF NOT EXISTS idx_ohlcv_addr_time ON ohlcv(address, time DESC);
```

示例插入（演示数据）：
```sql
INSERT INTO tokens (address, symbol, name)
VALUES ('MintAddressOrId-2', 'DEMO', 'Demo Token')
ON CONFLICT DO NOTHING;

INSERT INTO ohlcv (address, time, close, volume, liquidity, fdv)
VALUES ('MintAddressOrId-2', NOW(), 0.0018, 100000.0, 500000.0, 1500000.0);
```

## 常见问题排查（FAQ）
- 本地运行提示输入邮箱：这是 Streamlit Cloud 登录入口。使用 `streamlit run dashboard/app.py` 本地运行即可，无需登录；忽略网页右上角的 Sign in/Share/Deploy。
- 端口 8501 被占用：改用 `streamlit run dashboard/app.py --server.port 8502` 或关闭占用该端口的进程。
- ModuleNotFoundError: solders/solana：确保已安装并顺序正确（先 `pip install solders`，再 `pip install solana`）；确认 Python 版本 ≥3.10 且使用的是同一虚拟环境（`pip list` 检查）。
- 安装 psycopg2 报错：优先使用 `psycopg2-binary`（已在 requirements.txt 中），先 `python -m pip install --upgrade pip` 后再安装；若仍失败，使用预编译轮子或改用本地 Postgres 客户端库。
- Market 页面为空：数据库未连接或无数据。检查 .env 的 DB_* 值、确保表结构存在（见上文 SQL），并插入至少一条最新快照数据。
- Portfolio 页面报错/为空：`portfolio_state.json` 缺少必需字段或路径不对。确保使用示例结构并在仓库根目录放置该文件。
- Logs 页面为空：`strategy.log` 不存在或路径错误。将日志文件放在仓库根目录（与 dashboard 同级）。
- 钱包地址显示 Unknown / 余额为 0.0：未设置或设置了无效的 `SOLANA_PRIVATE_KEY`；RPC 不可达或限流。设置有效私钥（base58 或 JSON 数组）并提供稳定的 `QUICKNODE_RPC_URL`。
- 环境变量未生效：确保 `.env` 位于仓库根目录且从根目录执行 `streamlit run`；python-dotenv 会自动加载。
- 自动刷新导致频繁重跑：取消勾选 “Auto-Refresh (30s)” 以避免周期性 rerun。

## 已生成的本地模板文件（项目根目录）
- .env
- portfolio_state.json
- best_meme_strategy.json
- strategy.log

## 启动步骤（本地预览）
- 保证上述模板文件位于项目根目录（与 dashboard 同级）
- 安装依赖并启动：
  - `pip install -r requirements.txt`
  - `streamlit run dashboard/app.py`
- 浏览器访问 `http://localhost:8501`
- 避免点击页面右上角的“Sign in/Share/Deploy”，本地预览无需登录

## 注意事项
- 相对路径：请在仓库根目录执行，否则可能找不到 portfolio_state.json 等文件
- 环境变量缺失或数据源不可达时，页面会显示空状态或默认值（例如余额 0.0、钱包地址 Unknown）
- STOP_SIGNAL 文件仅作为信号，需要后台运行的主循环逻辑主动检测并响应
- 机密信息：请妥善保管 SOLANA_PRIVATE_KEY，避免泄露；建议使用测试/只读钱包
- 市场概览依赖数据库最新快照（ohlcv/tokens），若数据管道未运行则该页提示无数据

## 文件清单
- dashboard/app.py
- dashboard/data_service.py
- dashboard/visualizer.py
- dashboard/.gitkeep
