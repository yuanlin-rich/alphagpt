# strategy_manager/runner.py 文档

## 1. 文件概述

`runner.py` 是整个 `strategy_manager` 模块的**核心调度引擎**，也是 AlphaGPT 交易机器人的主运行入口。`StrategyRunner` 类整合了数据管道、AI 推理引擎、风控系统、持仓管理和链上交易执行等所有子系统，以异步事件循环的方式持续运行：

1. 定期同步链上数据（每 15 分钟）。
2. 监控已有持仓并根据止盈止损规则自动卖出。
3. 扫描市场寻找新的入场机会（AI 评分 + 风控过滤）。
4. 执行链上买入/卖出交易。

该文件同时提供 `__main__` 入口，可直接运行启动实盘交易。

---

## 2. 类与函数说明

### 类：`StrategyRunner`

主策略运行器，协调所有子系统完成自动化交易闭环。

---

#### `__init__(self)`

- **参数**：无
- **返回值**：无
- **行为**：
  - 初始化各子系统实例：
    - `self.data_mgr` = `DataManager()` —— 数据管道管理器
    - `self.portfolio` = `PortfolioManager()` —— 持仓管理
    - `self.risk` = `RiskEngine()` —— 风控引擎
    - `self.trader` = `SolanaTrader()` —— 链上交易执行器
    - `self.vm` = `StackVM()` —— AI 模型推理虚拟机
    - `self.loader` = `CryptoDataLoader()` —— 特征数据加载器
  - 初始化辅助变量：
    - `self.token_map` (`dict`)：`{address: tensor_index}` 映射表，用于快速查找代币在特征张量中的位置
    - `self.last_scan_time` (`float`)：上次数据同步时间戳，初始为 0
  - 加载策略公式：从 `best_meme_strategy.json` 文件读取 AI 策略公式。兼容两种格式：直接为列表或字典中的 `"formula"` 键。若文件不存在，输出 CRITICAL 日志并退出程序。

---

#### `async initialize(self)`

- **参数**：无
- **返回值**：无
- **行为**：
  - 调用 `self.data_mgr.initialize()` 初始化数据管道（建立数据库连接等）。
  - 查询当前钱包 SOL 余额并记录日志。

---

#### `async run_loop(self)`

- **参数**：无
- **返回值**：无（无限循环，不会主动返回）
- **行为**：主事件循环，约每 60 秒执行一个完整周期：
  1. **数据同步**：若距上次同步超过 900 秒（15 分钟），调用 `data_mgr.pipeline_sync_daily()` 拉取最新链上数据。
  2. **加载特征**：调用 `loader.load_data(limit_tokens=300)` 加载前 300 个代币的特征数据。
  3. **构建映射**：调用 `_build_token_mapping()` 建立代币地址到张量索引的映射。
  4. **监控持仓**：调用 `monitor_positions()` 检查所有持仓的止盈止损状态。
  5. **扫描入场**：若持仓数量未达上限，调用 `scan_for_entries()` 寻找新机会。
  6. **休眠**：计算已用时间，休眠至凑满约 60 秒一个周期（最少休眠 10 秒）。
  7. **异常处理**：若循环中出现任何异常，记录异常日志后休眠 30 秒继续。

---

#### `async _build_token_mapping(self)`

- **参数**：无
- **返回值**：无
- **行为**：
  - 通过 SQL 查询 `ohlcv` 表，获取数据量最多的前 300 个代币地址。
  - 构建 `self.token_map = {address: index}` 字典，使代币地址与特征张量的行索引一一对应。
  - 使用 `pandas.read_sql()` 执行查询，数据库连接来自 `self.loader.engine`。

---

#### `async monitor_positions(self)`

- **参数**：无
- **返回值**：无
- **行为**：遍历所有活跃持仓，对每个仓位执行以下检查（按优先级从高到低）：

  1. **获取实时价格**：调用 `_fetch_live_price_sol()` 获取当前 SOL 计价价格。价格 <= 0 则跳过。
  2. **更新最高价**：调用 `portfolio.update_price()` 记录历史最高价。
  3. **计算盈亏比** `pnl_pct = (current - entry) / entry`。
  4. **止损检查**：若 `pnl_pct <= STOP_LOSS_PCT`（-5%），全仓卖出。
  5. **Moonbag 止盈**：若尚未执行过 Moonbag 且 `pnl_pct >= TAKE_PROFIT_Target1`（+10%），卖出 50% 仓位，标记 `is_moonbag = True`。
  6. **追踪止损**：若最大涨幅 > `TRAILING_ACTIVATION`（5%）且从最高点回撤 > `TRAILING_DROP`（3%），全仓卖出。
  7. **AI 信号退出**：对非 Moonbag 仓位，运行 AI 推理，若得分 < `SELL_THRESHOLD`（0.45），全仓卖出。

---

#### `async scan_for_entries(self)`

- **参数**：无
- **返回值**：无
- **行为**：
  1. 使用 `self.vm.execute()` 对全部代币特征张量执行策略公式推理。
  2. 取最新时间步的信号值，经 Sigmoid 函数转为 0~1 概率分数。
  3. 按分数从高到低排序遍历。
  4. 对每个高分代币（分数 >= `BUY_THRESHOLD` 即 0.85）：
     - 跳过已持仓的代币。
     - 从缓存获取流动性数据。
     - 调用 `risk.check_safety()` 进行安全检查。
     - 通过检查后调用 `_execute_buy()` 执行买入。
     - 若持仓数达到上限（`MAX_OPEN_POSITIONS`），终止扫描。

---

#### `async _execute_buy(self, token_addr, score)`

- **参数**：
  - `token_addr` (`str`)：目标代币地址
  - `score` (`float`)：AI 评分（仅用于日志记录）
- **返回值**：无
- **行为**：
  1. 查询钱包余额，通过 `risk.calculate_position_size()` 计算下单金额。
  2. 将 SOL 金额转为 lamports（乘以 1e9）。
  3. 通过 Jupiter 获取报价（SOL -> 目标代币）。
  4. 调用 `trader.buy()` 执行链上买入交易。
  5. 交易成功后，根据报价的 `outAmount` 估算获得的代币数量。
  6. 获取代币精度（`get_mint_decimals`），计算 UI 层面的代币数量和入场价格。
  7. 调用 `portfolio.add_position()` 记录新仓位。

---

#### `async _execute_sell(self, token_addr, ratio, reason)`

- **参数**：
  - `token_addr` (`str`)：代币地址
  - `ratio` (`float`)：卖出比例（0.0 ~ 1.0，如 0.5 表示卖出一半）
  - `reason` (`str`)：卖出原因标签（`"StopLoss"`, `"Moonbag"`, `"TrailingStop"`, `"AI_Signal"`）
- **返回值**：无
- **行为**：
  1. 调用 `trader.sell()` 执行链上卖出交易。
  2. 交易成功后计算剩余数量 `new_amount = amount_held * (1.0 - ratio)`。
  3. 若卖出比例 > 98% 或剩余价值极小（< 0.001 SOL），调用 `close_position()` 完全平仓。
  4. 否则调用 `update_holding()` 更新剩余持有量。

---

#### `async _run_inference(self, token_addr)`

- **参数**：
  - `token_addr` (`str`)：代币地址
- **返回值**：`float` —— AI 评分（0~1），若无法推理则返回 `-1`
- **行为**：
  1. 从 `token_map` 获取代币对应的张量索引。若不在映射中，返回 -1。
  2. 提取该代币的特征张量（2D），增加 batch 维度变为 `[1, F, T]`。
  3. 调用 `vm.execute()` 执行策略公式推理，获得 `[1, Time]` 输出。
  4. 取最新时间步的 logit 值，经 Sigmoid 转为概率分数返回。

---

#### `async _fetch_live_price_sol(self, token_addr)`

- **参数**：
  - `token_addr` (`str`)：代币地址
- **返回值**：`float` —— 代币的 SOL 计价价格，失败时返回 `0.0`
- **行为**：
  1. 获取代币精度（`get_mint_decimals`）。
  2. 计算 1 个完整代币的最小单位数量（`10 ** decimals`）。
  3. 通过 Jupiter 询价：1 个完整代币能兑换多少 SOL。
  4. 将输出的 lamports 数量转为 SOL（除以 1e9）返回。
  5. 任何异常返回 `0.0`。

---

#### `async shutdown(self)`

- **参数**：无
- **返回值**：无
- **行为**：有序关闭所有子系统，释放资源：
  1. `data_mgr.close()` —— 关闭数据管道连接
  2. `trader.close()` —— 关闭交易执行器
  3. `risk.close()` —— 关闭风控引擎的 HTTP 会话

---

### 模块级代码：`__main__` 入口

```python
if __name__ == "__main__":
    runner = StrategyRunner()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(runner.initialize())
        loop.run_until_complete(runner.run_loop())
    except KeyboardInterrupt:
        loop.run_until_complete(runner.shutdown())
```

- 创建 `StrategyRunner` 实例。
- 获取异步事件循环，先执行 `initialize()` 初始化，再进入 `run_loop()` 主循环。
- 捕获 `KeyboardInterrupt`（Ctrl+C），优雅关闭所有连接。

---

## 3. 调用关系图

```
+========================================================================+
|                      strategy_manager/runner.py                        |
|                                                                        |
|  StrategyRunner                                                        |
|  +------------------------------------------------------------------+  |
|  |                                                                  |  |
|  |  __init__()                                                      |  |
|  |    |-- DataManager()              <-- data_pipeline/data_manager |  |
|  |    |-- PortfolioManager()         <-- strategy_manager/portfolio |  |
|  |    |-- RiskEngine()               <-- strategy_manager/risk      |  |
|  |    |-- SolanaTrader()             <-- execution/trader           |  |
|  |    |-- StackVM()                  <-- model_core/vm              |  |
|  |    |-- CryptoDataLoader()         <-- model_core/data_loader     |  |
|  |    +-- 加载 best_meme_strategy.json                              |  |
|  |                                                                  |  |
|  |  initialize()                                                    |  |
|  |    |-- data_mgr.initialize()                                     |  |
|  |    +-- trader.rpc.get_balance()                                  |  |
|  |                                                                  |  |
|  |  run_loop()  [主循环, ~60s/周期]                                  |  |
|  |    |-- data_mgr.pipeline_sync_daily()  (每15分钟)                |  |
|  |    |-- loader.load_data()                                        |  |
|  |    |-- _build_token_mapping()                                    |  |
|  |    |-- monitor_positions()                                       |  |
|  |    +-- scan_for_entries()                                        |  |
|  |                                                                  |  |
|  |  _build_token_mapping()                                          |  |
|  |    +-- pd.read_sql() via loader.engine                           |  |
|  |                                                                  |  |
|  |  monitor_positions()                                             |  |
|  |    |-- _fetch_live_price_sol()                                   |  |
|  |    |-- portfolio.update_price()                                  |  |
|  |    |-- _execute_sell()  (止损/止盈/追踪止损)                      |  |
|  |    +-- _run_inference() --> _execute_sell()  (AI信号退出)         |  |
|  |                                                                  |  |
|  |  scan_for_entries()                                              |  |
|  |    |-- vm.execute()                                              |  |
|  |    |-- torch.sigmoid()                                           |  |
|  |    |-- risk.check_safety()                                       |  |
|  |    +-- _execute_buy()                                            |  |
|  |                                                                  |  |
|  |  _execute_buy()                                                  |  |
|  |    |-- trader.rpc.get_balance()                                  |  |
|  |    |-- risk.calculate_position_size()                            |  |
|  |    |-- trader.jup.get_quote()                                    |  |
|  |    |-- trader.buy()                                              |  |
|  |    |-- get_mint_decimals()        <-- execution/utils            |  |
|  |    +-- portfolio.add_position()                                  |  |
|  |                                                                  |  |
|  |  _execute_sell()                                                 |  |
|  |    |-- trader.sell()                                             |  |
|  |    |-- portfolio.close_position()                                |  |
|  |    +-- portfolio.update_holding()                                |  |
|  |                                                                  |  |
|  |  _run_inference()                                                |  |
|  |    |-- vm.execute()                                              |  |
|  |    +-- torch.sigmoid()                                           |  |
|  |                                                                  |  |
|  |  _fetch_live_price_sol()                                         |  |
|  |    |-- get_mint_decimals()                                       |  |
|  |    +-- trader.jup.get_quote()                                    |  |
|  |                                                                  |  |
|  |  shutdown()                                                      |  |
|  |    |-- data_mgr.close()                                          |  |
|  |    |-- trader.close()                                            |  |
|  |    +-- risk.close()                                              |  |
|  +------------------------------------------------------------------+  |
+========================================================================+
```

### 与外部模块的交互关系

```
+------------------+     +--------------------+     +------------------+
| data_pipeline/   |     | strategy_manager/  |     | execution/       |
| data_manager     |<----|   runner.py         |---->| trader           |
| (数据同步)        |     |   (核心调度)        |     | (链上交易)        |
+------------------+     +----+----+----+-----+     +------------------+
                              |    |    |                    |
                    +---------+    |    +--------+           |
                    v              v             v           v
             +----------+  +-----------+  +-----------+ +----------+
             | model_   |  | strategy_ |  | strategy_ | | execution|
             | core/    |  | manager/  |  | manager/  | | /utils   |
             | vm +     |  | portfolio |  | risk      | | (精度)   |
             | loader   |  | (持仓)    |  | (风控)    | +----------+
             | (AI推理) |  +-----------+  +-----------+
             +----------+
```

---

## 4. 依赖关系

### 内部模块依赖

| 模块 | 导入内容 | 用途 |
|---|---|---|
| `data_pipeline.data_manager` | `DataManager` | 链上数据的同步与管理 |
| `model_core.vm` | `StackVM` | AI 策略公式的推理执行虚拟机 |
| `model_core.data_loader` | `CryptoDataLoader` | 加密货币特征数据加载与预处理 |
| `execution.trader` | `SolanaTrader` | Solana 链上交易执行（买入/卖出） |
| `execution.utils` | `get_mint_decimals` | 获取 SPL Token 的精度（decimals） |
| `strategy_manager.config` | `StrategyConfig` | 策略参数配置（阈值、仓位大小等） |
| `strategy_manager.portfolio` | `PortfolioManager` | 持仓的增删改查与状态持久化 |
| `strategy_manager.risk` | `RiskEngine` | 交易前的安全检查与仓位计算 |

### 外部第三方依赖

| 模块 | 用途 |
|---|---|
| `asyncio` (标准库) | 异步事件循环，驱动整个策略运行 |
| `torch` (PyTorch) | 张量操作（`sigmoid`、`unsqueeze`、`argsort`），AI 推理核心 |
| `json` (标准库) | 读取策略公式文件 `best_meme_strategy.json` |
| `time` (标准库) | 计时器，控制循环周期和数据同步间隔 |
| `loguru` (第三方) | 结构化日志记录 |
| `pandas` (第三方) | 执行 SQL 查询构建代币地址映射（`pd.read_sql`） |

---

## 5. 代码逻辑流程

### 整体生命周期

```
程序启动 (__main__)
  |
  v
StrategyRunner.__init__()
  |-- 初始化 6 个子系统
  |-- 加载 best_meme_strategy.json (策略公式)
  |      若文件不存在 -> CRITICAL 日志 -> exit(1)
  |
  v
initialize()
  |-- data_mgr.initialize()
  |-- 查询并记录钱包余额
  |
  v
run_loop() [无限循环]
  |
  +---> [每个周期 ~60s]
  |       |
  |       v
  |     距上次同步 > 15 分钟 ?
  |       |Yes                |No
  |       v                   |
  |     pipeline_sync_daily() |
  |       |                   |
  |       +---<---<---<---<---+
  |       |
  |       v
  |     loader.load_data(limit_tokens=300)
  |       |
  |       v
  |     _build_token_mapping()
  |       |
  |       v
  |     monitor_positions()  ---------> (见下方详细流程)
  |       |
  |       v
  |     持仓数 < MAX_OPEN_POSITIONS ?
  |       |Yes               |No
  |       v                  v
  |     scan_for_entries()   记录日志 "Max positions reached"
  |       |                  |
  |       +---<---<---<------+
  |       |
  |       v
  |     计算休眠时间 = max(10, 60 - elapsed)
  |     asyncio.sleep(休眠时间)
  |       |
  +---<---+ (循环继续)

KeyboardInterrupt (Ctrl+C)
  |
  v
shutdown()
  |-- data_mgr.close()
  |-- trader.close()
  |-- risk.close()
  |
  v
程序退出
```

### monitor_positions 持仓监控流程

```
遍历每个持仓 (token_addr, pos)
  |
  v
获取实时价格 _fetch_live_price_sol()
  |
  +---> price <= 0 ? --> 跳过该仓位
  |
  v
更新最高价 portfolio.update_price()
  |
  v
计算 pnl_pct = (current - entry) / entry
  |
  v
[优先级1] pnl_pct <= -5% (STOP_LOSS) ?
  |Yes --> 全仓卖出 (ratio=1.0, reason="StopLoss") --> continue
  |No
  v
[优先级2] 未 Moonbag 且 pnl_pct >= +10% (TP_Target1) ?
  |Yes --> 卖出50% (ratio=0.5, reason="Moonbag")
  |        标记 is_moonbag=True --> continue
  |No
  v
[优先级3] 最大涨幅 > 5% 且 从高点回撤 > 3% (TRAILING) ?
  |Yes --> 全仓卖出 (ratio=1.0, reason="TrailingStop") --> continue
  |No
  v
[优先级4] 非 Moonbag 仓位的 AI 信号检查
  _run_inference() --> score
  score != -1 且 score < 0.45 ?
  |Yes --> 全仓卖出 (ratio=1.0, reason="AI_Signal")
  |No  --> 保持持仓
```

### scan_for_entries 入场扫描流程

```
vm.execute(formula, feat_tensor)  -->  raw_signals
  |
  v
raw_signals 为 None ? --> 返回
  |No
  v
取最新时间步信号: raw_signals[:, -1]
  |
  v
Sigmoid 转换为概率 scores (0~1)
  |
  v
按分数降序排列 sorted_indices
  |
  v
遍历 sorted_indices:
  |
  v
score < BUY_THRESHOLD (0.85) ? --> break (后续分数更低，无需继续)
  |No
  v
索引转地址 idx_to_addr.get(idx)
  |
  +---> 地址不存在 ? --> continue
  |
  +---> 已持仓 ? --> continue
  |
  v
获取流动性 liq_usd
  |
  v
risk.check_safety(token_addr, liq_usd)
  |
  +---> 不安全 ? --> continue
  |
  v
_execute_buy(token_addr, score)
  |
  v
持仓数 >= MAX_OPEN_POSITIONS ? --> break
  |No --> 继续遍历
```
