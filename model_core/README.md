# model_core 模块说明

本模块实现了“AlphaGPT”候选表达式生成-评估-学习的核心：
- 从数据库加载多币种分钟级 OHLCV 数据，构造横截面特征张量
- 使用策略语言的“栈机 VM”执行由模型生成的公式（后缀式 token 序列）
- 通过简化回测评分（流动性约束、滑点/手续费、风控）为公式打分
- 以策略分数为奖励，使用策略模型 AlphaGPT 进行策略表达式搜索/优化（含 LoRD 低秩正则）

目录：
- config.py：运行与市场参数（设备、训练步数、公式长度等）
- data_loader.py：从 Postgres 读取 tokens/ohlcv，并生成特征与目标
- factors.py：因子工程（基础/进阶）
- ops.py：可用运算符集合（JIT 优化的时序/门控等）
- vm.py：基于栈的虚拟机执行器
- alphagpt.py：模型定义（LoopedTransformer + MTPHead + LoRD/Rank 监控）
- backtest.py：极简 Meme 策略回测打分器
- engine.py：训练引擎，将以上组件串联

## 配置（config.py）
- DEVICE：自动选择 cuda/cpu（model_core/config.py:5）
- DB_URL：从环境变量构造 Postgres DSN（model_core/config.py:6）
- BATCH_SIZE/TRAIN_STEPS/MAX_FORMULA_LEN：训练批次与长度（model_core/config.py:7-9）
- TRADE_SIZE_USD/MIN_LIQUIDITY/BASE_FEE：交易成本假设（model_core/config.py:10-12）
- INPUT_DIM：特征维度（与 FeatureEngineer 一致）（model_core/config.py:13）

## 数据加载与特征（data_loader.py, factors.py）
- 从 tokens 取前 N 个地址（limit_tokens，可调），再从 ohlcv 提取所需字段（model_core/data_loader.py:14-29）。
- 将每个字段透视为 [Token×Time]，前向填充缺失，转为 GPU 张量（model_core/data_loader.py:30-41）。
- FeatureEngineer.compute_features 产出 6 维特征（RET、流动性评分、买卖强度、FOMO、偏离度、log(volume)）（model_core/factors.py:156-191）。
- 目标收益 target_ret：未来两步对一前步的对数收益 log(P[t+2]/P[t+1])（末两列置零）（model_core/data_loader.py:44-49）。
- AdvancedFactorEngineer 提供更丰富的 12 维特征（未在主流程中使用）（model_core/factors.py:93-153）。

## 运算符与 VM（ops.py, vm.py）
- OPS_CONFIG：定义了算子名、函数、元数（arity）（model_core/ops.py:25-38），含加减乘除、取绝对、符号、门控、跳变、衰减、延迟、窗口最大等。
- TorchScript 实现的基础时序与复合算子以提升执行效率：
  - _ts_delay：时序延迟（model_core/ops.py:3-7）
  - _op_gate：条件门（model_core/ops.py:9-13）
  - _op_jump：异常跳变检测（z>3）（model_core/ops.py:14-20）
  - _op_decay：指数衰减型组合（model_core/ops.py:21-24）
- StackVM：
  - 以 FeatureEngineer.INPUT_DIM 为特征 token 起始；其后 token 映射到算子（model_core/vm.py:6-9）。
  - execute(formula_tokens, feat_tensor)：按后缀式栈机执行；入栈特征，按元数出栈、计算、入栈；NaN/Inf 做 nan_to_num 处理；若栈不平衡或非法 token 返回 None（model_core/vm.py:11-37）。

## 模型（alphagpt.py）
- AlphaGPT：
  - 词表：特征符号 + 运算符名（model_core/alphagpt.py:225-229）。
  - 嵌入：token_emb + pos_emb（长度 MAX_FORMULA_LEN+1）（model_core/alphagpt.py:231-234）。
  - LoopedTransformer（两层、每层 3 次循环、4 头、自注意 + SwiGLU FFN + RMSNorm + QK-Norm 注意力在层内部）（model_core/alphagpt.py:235-243, 167-203）。
  - 输出：MTPHead 将最后时序位置嵌入映射到词表分布，另带 value head（model_core/alphagpt.py:248-271）。
- 正则与监控：
  - NewtonSchulzLowRankDecay：对匹配关键词的 2D 权重矩阵执行 Newton-Schulz 迭代并衰减（model_core/alphagpt.py:8-68）。
  - StableRankMonitor：计算目标权重的稳定秩用于跟踪（model_core/alphagpt.py:70-96）。

## 回测打分（backtest.py）
- MemeBacktest.evaluate(factors, raw_data, target_ret)（model_core/backtest.py:9-29）：
  - signal=σ(factors)，阈值 0.85 建仓；仅在流动性高于 min_liq 时允许持仓（model_core/backtest.py:10-14）。
  - 冲击滑点≈trade_size/liquidity 上限 5%，单边成本=base_fee+impact；换手=|pos−prev_pos|；净 PnL = 持仓收益 − 交易成本（model_core/backtest.py:15-23）。
  - 以累计收益减去大回撤惩罚为分数；若交易次数少于 5 次则给惩罚（model_core/backtest.py:24-28）。
  - 返回：中位数分数（跨币种聚合）与平均累计收益（model_core/backtest.py:28-29）。

## 训练引擎（engine.py）
- AlphaEngine：
  - 初始化：加载数据→构建 AlphaGPT 与优化器→可选启用 LoRD 正则与稳定秩监控→创建 StackVM 与回测器（model_core/engine.py:12-51）。
  - 训练循环：
    - 自回归生成 MAX_FORMULA_LEN 个 token（Categorical 采样）（model_core/engine.py:74-83）。
    - 用 VM 执行获得横截面因子；非法/退化信号设负奖励（-5/-2）（model_core/engine.py:90-98）。
    - 用回测器评估得分，维护全局最优与公式（model_core/engine.py:100-107）。
    - REINFORCE 风格策略梯度：advantage 标准化后对所有时间步累加 −logπ·adv，反向传播更新参数（model_core/engine.py:108-121）。
    - 若启用 LoRD：每步执行低秩衰减（model_core/engine.py:122-125）；每 100 步记录稳定秩（model_core/engine.py:130-134）。
  - 产物：best_meme_strategy.json（最优公式 token 列表）、training_history.json（训练过程曲线）（model_core/engine.py:141-148）。

## 入口与使用方法
- 脚本入口：model_core/engine.py:155-157（__main__ 里实例化 AlphaEngine 并调用 train）
- 训练入口方法：AlphaEngine.train 在 model_core/engine.py:59

- 确保 data_pipeline 已将 tokens/ohlcv 写入数据库，设置好环境变量（DB_USER/DB_PASSWORD/DB_HOST/DB_NAME）。
- 运行训练：
  ```
  python -m model_core.engine
  ```
  或在模块内：
  ```
  python model_core/engine.py
  ```
- 可在 AlphaEngine 构造参数中切换 LoRD 相关超参（engine.py:12-21），或在 config.py 中修改 BATCH_SIZE、TRAIN_STEPS、MAX_FORMULA_LEN 等。

## 注意事项
- 数据依赖数据库可用；若 tokens 为空 load_data 会抛错（model_core/data_loader.py:21）。
- 生成的公式是基于特征与运算符的后缀表达式，需经 VM 可执行且非退化，才会获得有效奖励。
- 回测逻辑为简化版、偏保守（高流动性门槛、较高基础费率）；仅用于相对比较与搜索引导，不代表真实可交易绩效。
