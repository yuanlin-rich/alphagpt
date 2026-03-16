# strategy_manager 模块文档

## 1. 模块概述

`strategy_manager` 是 AlphaGPT 系统的**策略执行核心模块**，负责将 AI 模型的推理信号转化为实际的链上交易操作。该模块实现了一个完整的 Solana Meme 币自动化交易策略，涵盖以下核心能力：

- **策略信号生成**：基于 StackVM 虚拟机执行进化策略公式，对代币进行评分排序
- **仓位管理**：跟踪所有持仓状态（入场价、持仓量、最高价等），并持久化到本地 JSON 文件
- **风险控制**：流动性检查、蜜罐（Honeypot）检测、仓位大小计算
- **交易执行**：通过 Jupiter 聚合器和 Solana 链上交易完成买卖操作
- **止盈止损**：支持固定止损、分批止盈（Moonbag）、追踪止损（Trailing Stop）、AI 信号退出等多种退出策略

整个模块以异步事件循环驱动，每 60 秒执行一次完整的扫描-监控-交易周期，每 15 分钟同步一次数据管线。

---

## 2. 文件说明

### `__init__.py`

模块初始化文件，当前为空。仅作为 Python 包标识。

### `config.py`

策略参数配置类，集中定义所有可调节的交易策略超参数。

| 参数名 | 默认值 | 含义 |
|---|---|---|
| `MAX_OPEN_POSITIONS` | 3 | 最大同时持仓数量 |
| `ENTRY_AMOUNT_SOL` | 2.0 | 每笔建仓投入的 SOL 数量 |
| `STOP_LOSS_PCT` | -0.05 | 止损触发阈值（-5%） |
| `TAKE_PROFIT_Target1` | 0.10 | 第一止盈目标（+10%） |
| `TP_Target1_Ratio` | 0.5 | 到达第一止盈目标时卖出的仓位比例（50%） |
| `TRAILING_ACTIVATION` | 0.05 | 追踪止损激活阈值（盈利超过 5% 时启用） |
| `TRAILING_DROP` | 0.03 | 追踪止损回撤触发阈值（从最高点回落 3%） |
| `BUY_THRESHOLD` | 0.85 | AI 评分高于此值时触发买入 |
| `SELL_THRESHOLD` | 0.45 | AI 评分低于此值时触发卖出 |

### `portfolio.py`

仓位管理模块，包含 `Position` 数据类和 `PortfolioManager` 仓位管理器。

- **`Position`**：使用 `@dataclass` 定义的持仓数据结构，字段包括代币地址、代号、入场价格、入场时间、持仓数量、初始成本（SOL）、历史最高价、是否已进入 Moonbag 状态。
- **`PortfolioManager`**：管理所有活跃持仓，提供增删改查接口，并通过 JSON 文件实现状态持久化，确保程序重启后仓位数据不丢失。

### `risk.py`

风险引擎模块，在建仓前执行安全检查。

- **流动性检查**：拒绝流动性低于 $5,000 的代币
- **蜜罐检测**：通过 Jupiter 聚合器模拟卖出报价，验证代币是否可正常卖出（防止买入后无法卖出的蜜罐代币）
- **仓位大小计算**：根据钱包余额判断是否有足够资金建仓（至少保留 0.1 SOL 作为 Gas 费）

### `runner.py`

策略主运行器，是整个模块的**核心入口与调度中心**，协调数据管线、AI 推理、风控和交易执行的完整流程。

主要功能：
- 加载进化策略公式（`best_meme_strategy.json`）
- 定时同步数据管线（每 15 分钟）
- 构建代币地址到特征张量索引的映射
- 监控现有持仓并执行止盈/止损/追踪止损/AI 信号退出
- 扫描新的入场机会并执行买入
- 通过 Jupiter 报价获取实时价格
- 统一的初始化与优雅关闭流程

---

## 3. 架构图

```
+-------------------------------------------------------------------+
|                       strategy_manager                            |
|                                                                   |
|  +-------------------------------------------------------------+ |
|  |                     StrategyRunner (runner.py)                | |
|  |                     [核心调度中心]                              | |
|  |                                                               | |
|  |   run_loop() ─── 60s 主循环                                   | |
|  |       |                                                       | |
|  |       +---> pipeline_sync_daily() ─── 每15分钟同步数据         | |
|  |       |         |                                             | |
|  |       |         v                                             | |
|  |       |    [DataManager]  (data_pipeline)                     | |
|  |       |                                                       | |
|  |       +---> _build_token_mapping()                            | |
|  |       |         |                                             | |
|  |       |         v                                             | |
|  |       |    [CryptoDataLoader]  (model_core)                   | |
|  |       |                                                       | |
|  |       +---> monitor_positions()                               | |
|  |       |         |                                             | |
|  |       |         +---> _fetch_live_price_sol()                 | |
|  |       |         |         |                                   | |
|  |       |         |         v                                   | |
|  |       |         |    [JupiterAggregator]  (execution)         | |
|  |       |         |                                             | |
|  |       |         +---> StopLoss / Moonbag TP / TrailingStop    | |
|  |       |         |         |                                   | |
|  |       |         |         v                                   | |
|  |       |         |    _execute_sell()                          | |
|  |       |         |         |                                   | |
|  |       |         |         v                                   | |
|  |       |         |    [SolanaTrader]  (execution)              | |
|  |       |         |                                             | |
|  |       |         +---> _run_inference() ──> AI信号退出          | |
|  |       |                   |                                   | |
|  |       |                   v                                   | |
|  |       |              [StackVM]  (model_core)                  | |
|  |       |                                                       | |
|  |       +---> scan_for_entries()                                | |
|  |                 |                                             | |
|  |                 +---> StackVM.execute() ── 批量推理评分        | |
|  |                 |                                             | |
|  |                 +---> RiskEngine.check_safety()               | |
|  |                 |         |                                   | |
|  |                 |         v                                   | |
|  |                 |    +------------------+                     | |
|  |                 |    | RiskEngine       |                     | |
|  |                 |    | (risk.py)        |                     | |
|  |                 |    |  - 流动性检查     |                     | |
|  |                 |    |  - 蜜罐检测      |                     | |
|  |                 |    |  - 仓位大小计算   |                     | |
|  |                 |    +------------------+                     | |
|  |                 |                                             | |
|  |                 +---> _execute_buy()                          | |
|  |                           |                                   | |
|  |                           v                                   | |
|  |                  +--------------------+                       | |
|  |                  | PortfolioManager   |                       | |
|  |                  | (portfolio.py)     |                       | |
|  |                  |  - 仓位增删改查     |                       | |
|  |                  |  - JSON 持久化     |                       | |
|  |                  +--------------------+                       | |
|  |                                                               | |
|  +-------------------------------------------------------------+ |
|                                                                   |
|  +-------------------+                                            |
|  | StrategyConfig    |  <--- 被 StrategyRunner 和 RiskEngine 引用  |
|  | (config.py)       |                                            |
|  +-------------------+                                            |
+-------------------------------------------------------------------+
```

**组件调用关系简图：**

```
StrategyRunner
    |
    +---> PortfolioManager    (仓位状态管理)
    +---> RiskEngine          (风险检查)
    |        +---> StrategyConfig      (策略参数)
    |        +---> JupiterAggregator   (蜜罐检测报价)
    +---> StrategyConfig      (策略参数)
    +---> DataManager         (数据同步)
    +---> CryptoDataLoader    (特征数据加载)
    +---> StackVM             (策略公式执行)
    +---> SolanaTrader        (链上交易执行)
```

---

## 4. 依赖关系

### 内部模块依赖（alphagpt 项目内）

| 被引用模块 | 引用来源 | 引用内容 |
|---|---|---|
| `data_pipeline.data_manager` | `runner.py` | `DataManager` — 数据管线管理器，负责数据同步 |
| `model_core.vm` | `runner.py` | `StackVM` — 栈式虚拟机，执行进化策略公式 |
| `model_core.data_loader` | `runner.py` | `CryptoDataLoader` — 加密货币特征数据加载器 |
| `execution.trader` | `runner.py` | `SolanaTrader` — Solana 链上交易执行器 |
| `execution.utils` | `runner.py` | `get_mint_decimals` — 获取代币精度的工具函数 |
| `execution.jupiter` | `risk.py` | `JupiterAggregator` — Jupiter DEX 聚合器（用于报价和蜜罐检测） |

### 模块内部依赖

```
runner.py  ---->  config.py     (StrategyConfig)
runner.py  ---->  portfolio.py  (PortfolioManager)
runner.py  ---->  risk.py       (RiskEngine)
risk.py    ---->  config.py     (StrategyConfig)
```

### 外部第三方依赖

| 库名 | 使用位置 | 用途 |
|---|---|---|
| `loguru` | `portfolio.py`, `risk.py`, `runner.py` | 结构化日志输出 |
| `torch` (PyTorch) | `runner.py` | 张量运算、sigmoid 激活函数、AI 推理 |
| `pandas` | `runner.py` | SQL 查询结果处理（`pd.read_sql`） |
| `asyncio` | `runner.py` | 异步事件循环驱动 |

### 标准库依赖

| 库名 | 使用位置 | 用途 |
|---|---|---|
| `json` | `portfolio.py`, `runner.py` | JSON 序列化/反序列化（仓位持久化、策略公式加载） |
| `time` | `portfolio.py`, `runner.py` | 时间戳记录、循环计时 |
| `dataclasses` | `portfolio.py` | `@dataclass` 装饰器和 `asdict` 转换 |
| `typing` | `portfolio.py` | 类型注解（`Dict`） |

---

## 5. 关键类/函数

### `StrategyConfig`（config.py）

策略参数配置类，所有参数以类变量形式定义，无需实例化即可通过 `StrategyConfig.XXX` 访问。

```python
class StrategyConfig:
    MAX_OPEN_POSITIONS = 3        # 最大持仓数
    ENTRY_AMOUNT_SOL = 2.0        # 单笔建仓金额 (SOL)
    STOP_LOSS_PCT = -0.05         # 止损百分比
    TAKE_PROFIT_Target1 = 0.10    # 第一止盈目标
    TP_Target1_Ratio = 0.5        # 止盈卖出比例
    TRAILING_ACTIVATION = 0.05    # 追踪止损激活阈值
    TRAILING_DROP = 0.03          # 追踪止损回撤阈值
    BUY_THRESHOLD = 0.85          # 买入信号阈值
    SELL_THRESHOLD = 0.45         # 卖出信号阈值
```

---

### `Position`（portfolio.py）

持仓数据类（`@dataclass`），表示单个代币的持仓状态。

| 字段 | 类型 | 说明 |
|---|---|---|
| `token_address` | `str` | 代币合约地址 |
| `symbol` | `str` | 代币符号 |
| `entry_price` | `float` | 入场价格（SOL 计价） |
| `entry_time` | `float` | 入场时间戳（Unix timestamp） |
| `amount_held` | `float` | 当前持仓数量（Token 单位） |
| `initial_cost_sol` | `float` | 初始投入 SOL |
| `highest_price` | `float` | 历史最高价（用于计算追踪止损回撤） |
| `is_moonbag` | `bool` | 是否已触发 Moonbag 止盈（默认 `False`） |

---

### `PortfolioManager`（portfolio.py）

仓位管理器，管理所有活跃持仓的生命周期。

| 方法 | 参数 | 说明 |
|---|---|---|
| `__init__(state_file)` | `state_file: str = "portfolio_state.json"` | 初始化并从文件加载历史仓位 |
| `add_position(token, symbol, price, amount, cost_sol)` | 代币地址、符号、价格、数量、成本 | 新增持仓并持久化 |
| `update_price(token, current_price)` | 代币地址、当前价格 | 更新最高价（仅当 current_price > highest_price） |
| `update_holding(token, new_amount)` | 代币地址、新持仓量 | 更新持仓数量；若 <= 0 则自动删除该仓位 |
| `close_position(token)` | 代币地址 | 完全平仓，删除持仓记录 |
| `get_open_count()` | 无 | 返回当前持仓数量 |
| `save_state()` | 无 | 将所有仓位序列化为 JSON 并写入文件 |
| `load_state()` | 无 | 从 JSON 文件加载仓位；文件不存在时初始化为空 |

---

### `RiskEngine`（risk.py）

风险引擎，在建仓前执行安全验证。

| 方法 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `__init__()` | 无 | — | 初始化 StrategyConfig 和 JupiterAggregator |
| `check_safety(token_address, liquidity_usd)` | 代币地址、流动性（USD） | `bool` | 异步方法。检查流动性是否 >= $5,000，并通过 Jupiter 模拟卖出报价验证非蜜罐。两项均通过返回 `True` |
| `calculate_position_size(wallet_balance_sol)` | 钱包 SOL 余额 | `float` | 计算建仓大小。若余额不足（< ENTRY_AMOUNT_SOL + 0.1）返回 0.0，否则返回 `ENTRY_AMOUNT_SOL` |
| `close()` | 无 | — | 异步方法。关闭 JupiterAggregator 连接 |

---

### `StrategyRunner`（runner.py）

策略主运行器，整个模块的核心调度类。

**构造与生命周期方法：**

| 方法 | 说明 |
|---|---|
| `__init__()` | 初始化所有子组件（DataManager、PortfolioManager、RiskEngine、SolanaTrader、StackVM、CryptoDataLoader）；加载策略公式文件 `best_meme_strategy.json` |
| `initialize()` | 异步初始化数据管线、查询钱包余额 |
| `run_loop()` | 异步主循环。每 60 秒一个周期：同步数据 -> 构建映射 -> 监控持仓 -> 扫描入场 |
| `shutdown()` | 优雅关闭，依次关闭 DataManager、SolanaTrader、RiskEngine |

**核心业务方法：**

| 方法 | 说明 |
|---|---|
| `_build_token_mapping()` | 从数据库查询 Top 300 代币地址，构建 `{address: tensor_index}` 映射表 |
| `monitor_positions()` | 遍历所有持仓，获取实时价格，依次检查：止损 -> Moonbag 止盈 -> 追踪止损 -> AI 信号退出 |
| `scan_for_entries()` | 使用 StackVM 执行策略公式进行批量推理，对 Top 300 代币评分排序，依次对高分代币执行风控检查和买入 |
| `_execute_buy(token_addr, score)` | 检查余额 -> 获取 Jupiter 报价 -> 执行链上买入 -> 记录仓位 |
| `_execute_sell(token_addr, ratio, reason)` | 按比例卖出 -> 更新/删除仓位。支持部分卖出（Moonbag）和全仓卖出 |
| `_run_inference(token_addr)` | 对单个代币执行 AI 推理，返回 0~1 的评分（sigmoid 输出）；映射失败返回 -1 |
| `_fetch_live_price_sol(token_addr)` | 通过 Jupiter 报价获取代币的实时 SOL 价格（1 Token -> ? SOL）；失败返回 0.0 |

**退出策略执行优先级（`monitor_positions` 内）：**

1. **止损**（Stop Loss）：PnL <= -5% 时全仓卖出
2. **Moonbag 止盈**：PnL >= +10% 且未触发过 Moonbag 时，卖出 50%，剩余让利润奔跑
3. **追踪止损**（Trailing Stop）：盈利超过 5% 后激活，从最高点回撤超过 3% 时全仓卖出
4. **AI 信号退出**：非 Moonbag 仓位，AI 评分低于 0.45 时全仓卖出
