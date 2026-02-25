# strategy_manager 模块说明

本模块围绕“实盘执行管理”构建，负责在训练得到的最佳策略公式驱动下，完成数据同步、打分入场、持仓监控、风控与交易执行闭环（以 Solana 生态为例，集成 Jupiter 聚合器和本地回测假设）。

组成文件：
- config.py：策略参数（仓位上限、分批止盈、追踪止损、买卖阈值等）
- portfolio.py：持仓状态管理（持久化到 JSON）
- risk.py：风控引擎（流动性门槛、可卖出性检测、仓位 sizing）
- runner.py：策略主循环（调度 data_pipeline、加载特征、执行 VM、调用交易）
- __init__.py：包初始化（空）

## 策略参数（config.py）
- MAX_OPEN_POSITIONS=3：最多同时持有 3 个标的（strategy_manager/config.py:2）
- ENTRY_AMOUNT_SOL=2.0：每次入场消耗 2 SOL（strategy_manager/config.py:3）
- STOP_LOSS_PCT=-0.05：止损线 -5%（strategy_manager/config.py:4）
- TAKE_PROFIT_Target1=0.10 & TP_Target1_Ratio=0.5：盈利达 10% 卖出 50% 做“回本包”（strategy_manager/config.py:5-6）
- TRAILING_ACTIVATION=0.05 & TRAILING_DROP=0.03：最高浮盈>5%后，回撤超过 3% 触发追踪止损（strategy_manager/config.py:7-8）
- BUY_THRESHOLD=0.85 & SELL_THRESHOLD=0.45：策略得分阈值（入场/平仓）（strategy_manager/config.py:9-10）

## 持仓管理（portfolio.py）
- Position 数据类：记录 token_address、symbol、entry_price/time、amount_held、initial_cost_sol、highest_price、is_moonbag（strategy_manager/portfolio.py:7-17）。
- PortfolioManager：
  - add_position/update_price/update_holding/close_position（strategy_manager/portfolio.py:24-55）。
  - get_open_count（返回持仓数量）（strategy_manager/portfolio.py:57-58）。
  - 状态持久化到 portfolio_state.json（strategy_manager/portfolio.py:60-72）。

## 风控引擎（risk.py）
- 依赖 execution.jupiter.JupiterAggregator 做“可卖出”模拟（防 Honeypot），strategy_manager/risk.py:2。
- check_safety(token, liquidity_usd)：
  - 先检查流动性阈值（< $5k 拒绝），再通过 Jupiter 报价验证是否可从 token 卖到 SOL（strategy_manager/risk.py:10-28）。
- calculate_position_size(wallet_balance_sol)：简单按固定手数（不足余额则返回 0）（strategy_manager/risk.py:30-36）。
- close()：关闭 Jupiter 客户端（strategy_manager/risk.py:38-39）。

## 策略主循环（runner.py）
- 依赖组件：
  - DataManager（同步与拉取候选/行情，strategy_manager/runner.py:19）
  - PortfolioManager（持仓状态，strategy_manager/runner.py:20）
  - RiskEngine（风控，strategy_manager/runner.py:21）
  - SolanaTrader（交易执行，strategy_manager/runner.py:22）
  - StackVM（策略公式执行），CryptoDataLoader（特征/原始数据），strategy_manager/runner.py:23-26。
- 策略文件加载：best_meme_strategy.json（来自 model_core/engine 训练输出），兼容旧结构（strategy_manager/runner.py:29-37）。
- initialize()：初始化数据管线与查询钱包余额（strategy_manager/runner.py:39-43）。
- run_loop()：
  1) 每 15 分钟同步一次 data_pipeline（pipeline_sync_daily），strategy_manager/runner.py:51-55。
  2) 重新加载数据（limit_tokens=300），重建 token→索引映射（按 ohlcv 记录数排序 top300），strategy_manager/runner.py:56-88。
  3) 监控已持仓：止损、到达回本包、追踪止损、AI 出场（阈值 SELL_THRESHOLD），strategy_manager/runner.py:89-129。
  4) 若持仓未满则扫描入场：
     - 用 VM 执行公式输出 logits→sigmoid 得分，按得分排序；过滤已持仓与低分（<BUY_THRESHOLD）；检查最新流动性；通过 RiskEngine.check_safety；合格则下单（strategy_manager/runner.py:130-170）。
  5) 每轮循环节奏：目标每分钟 1 次（考虑数据加载时间，最少 sleep 10s），strategy_manager/runner.py:66-69。
- 交易执行：
  - 买入：通过 Jupiter 报价估算 outAmount，记录持仓数量与 SOL 成本（strategy_manager/runner.py:171-213）。
  - 卖出：调用 trader.sell，按比例减仓或清仓；小额残留（价值很小）直接关闭仓位（strategy_manager/runner.py:214-231）。
- 实时价格：通过 Jupiter 以“1 Token→SOL”的报价推导价格（strategy_manager/runner.py:249-270）。
- 优雅关闭：关闭数据管线、交易客户端与风控（strategy_manager/runner.py:272-277）。

## 运行
- 前置：
  - 已训练产出 best_meme_strategy.json（model_core/engine.py）。
  - 已配置 execution 层（JupiterAggregator、SolanaTrader、RPC 等）与数据库连接。
- 启动：
  ```
  python strategy_manager/runner.py
  ```
  终止：Ctrl+C 后自动调用 shutdown()。

## 注意事项
- runner 每 15 分钟触发一次 data_pipeline 拉取/入库；数据库需可用且有足够历史以生成特征。
- 交易相关依赖 execution.* 未在本模块内定义，请确保相应模块可用且配置正确（RPC、私钥、Jupiter API 等）。
- Portfolio 使用本地 JSON 持久化，适合单实例；多实例/分布式需改造。
- 入场/出场阈值与手数为示例参数，需根据实际风险偏好与交易成本调整。