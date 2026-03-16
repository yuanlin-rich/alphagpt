# times.py 文档

> 源文件路径: `times.py`

---

## 1. 文件概述

`times.py` 是 AlphaGPT 项目的核心模块，实现了一个基于强化学习的 **Alpha 因子自动挖掘系统**。该文件通过 GPT 风格的自回归模型（`AlphaGPT`）自动生成量化交易因子公式，并使用策略梯度（REINFORCE）算法以回测收益作为奖励信号来优化模型。

核心职责：
- 定义 GPU 加速的时序算子（delay, delta, zscore, decay_linear）
- 构建基于 Transformer 的因子公式生成模型（AlphaGPT）
- 实现金融数据获取与特征工程引擎（DataEngine）
- 实现公式求解、回测评估与强化学习训练（DeepQuantMiner）
- 提供样本外严格回测及可视化（final_reality_check）

---

## 2. 类与函数说明

### 2.1 常量

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `TS_TOKEN` | `'20af39742f...'` | Tushare 数据接口的 API Token |
| `INDEX_CODE` | `'511260.SH'` | 目标标的代码（国泰黄金 ETF） |
| `START_DATE` | `'20150101'` | 训练数据起始日期 |
| `END_DATE` | `'20240101'` | 训练数据结束日期 |
| `TEST_END_DATE` | `'20250101'` | 测试数据结束日期 |
| `BATCH_SIZE` | `1024` | 每批次生成的公式数量 |
| `TRAIN_ITERATIONS` | `400` | 强化学习训练迭代次数 |
| `MAX_SEQ_LEN` | `8` | 生成公式的最大 token 长度 |
| `COST_RATE` | `0.0005` | 双边交易成本（万五） |
| `DATA_CACHE_PATH` | `'data_cache_final.parquet'` | 数据缓存文件路径 |
| `DEVICE` | `torch.device(...)` | 自动检测的计算设备 |
| `FEATURES` | `['RET', 'RET5', 'VOL_CHG', 'V_RET', 'TREND']` | 5 个基础特征名称 |
| `VOCAB` | `FEATURES + OPS名称列表` | 完整词表（5 个特征 + 11 个算子） |
| `VOCAB_SIZE` | `16` | 词表大小 |
| `OP_FUNC_MAP` | `dict` | 算子 ID -> 可调用函数的映射 |
| `OP_ARITY_MAP` | `dict` | 算子 ID -> 参数个数的映射 |

#### `OPS_CONFIG` 算子配置列表

| 算子名 | 函数签名 | 元数 | 说明 |
|--------|----------|------|------|
| `ADD` | `(x, y) -> x + y` | 2 | 加法 |
| `SUB` | `(x, y) -> x - y` | 2 | 减法 |
| `MUL` | `(x, y) -> x * y` | 2 | 乘法 |
| `DIV` | `(x, y) -> x / (y + eps)` | 2 | 保护除法 |
| `NEG` | `(x) -> -x` | 1 | 取负 |
| `ABS` | `(x) -> abs(x)` | 1 | 绝对值 |
| `SIGN` | `(x) -> sign(x)` | 1 | 符号函数 |
| `DELTA5` | `(x) -> x - delay(x, 5)` | 1 | 5 日变化量 |
| `MA20` | `(x) -> decay_linear(x, 20)` | 1 | 20 日线性衰减加权均值 |
| `STD20` | `(x) -> zscore(x, 20)` | 1 | 20 日 Z-Score |
| `TS_RANK20` | `(x) -> zscore(x, 20)` | 1 | 20 日近似排名（与 STD20 实现相同） |

---

### 2.2 TorchScript 加速函数

#### `_ts_delay(x, d)`

时序延迟算子。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | `torch.Tensor` | 形状 `[B, T]`，输入时序数据 |
| `d` | `int` | 延迟天数 |

| 返回值 | 类型 | 说明 |
|--------|------|------|
| 延迟后的张量 | `torch.Tensor` | 形状 `[B, T]`，前 d 个位置填零 |

---

#### `_ts_delta(x, d)`

时序差分算子。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | `torch.Tensor` | 形状 `[B, T]`，输入时序数据 |
| `d` | `int` | 差分天数 |

| 返回值 | 类型 | 说明 |
|--------|------|------|
| 差分后的张量 | `torch.Tensor` | `x - delay(x, d)` |

---

#### `_ts_zscore(x, d)`

滚动窗口 Z-Score 标准化。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | `torch.Tensor` | 形状 `[B, T]`，输入时序数据 |
| `d` | `int` | 滚动窗口长度 |

| 返回值 | 类型 | 说明 |
|--------|------|------|
| 标准化后的张量 | `torch.Tensor` | `(x - rolling_mean) / rolling_std` |

---

#### `_ts_decay_linear(x, d)`

线性衰减加权移动平均。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | `torch.Tensor` | 形状 `[B, T]`，输入时序数据 |
| `d` | `int` | 窗口长度 |

| 返回值 | 类型 | 说明 |
|--------|------|------|
| 加权平均张量 | `torch.Tensor` | 使用线性递增权重 `[1, 2, ..., d]` 归一化后加权 |

---

### 2.3 类

#### `AlphaGPT(nn.Module)`

基于 Transformer 的因子公式生成模型，采用 Actor-Critic 架构。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__(self, d_model=64, n_head=4, n_layer=2)` | `d_model`: 嵌入维度；`n_head`: 注意力头数；`n_layer`: Transformer 层数 | 无 | 初始化 token 嵌入、位置嵌入、Transformer Encoder（因果掩码）、LayerNorm、Actor 头和 Critic 头 |
| `forward(self, idx)` | `idx`: 形状 `[B, T]` 的 token ID 序列 | `(logits, value)` 元组：`logits` 形状 `[B, VOCAB_SIZE]`；`value` 形状 `[B, 1]` | 取序列最后一个位置的隐状态，分别通过 Actor 和 Critic 头输出 |

**架构细节：**
- Token 嵌入 + 可学习位置嵌入（长度 `MAX_SEQ_LEN + 1`）
- 使用 `nn.TransformerEncoder` + 因果掩码（`generate_square_subsequent_mask`）
- Actor 头输出词表上的 logits（用于策略采样）
- Critic 头输出标量值估计（当前代码中未在训练中使用）

---

#### `DataEngine`

金融数据获取与特征工程引擎。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__(self)` | 无 | 无 | 初始化 Tushare Pro API 连接 |
| `load(self)` | 无 | `self`（支持链式调用） | 加载或缓存金融数据，计算特征并移至 GPU |

**`load()` 生成的属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.dates` | `pd.DatetimeIndex` | 交易日期序列 |
| `self.feat_data` | `torch.Tensor` | 形状 `[5, T]` 的特征张量（RET, RET5, VOL_CHG, V_RET, TREND） |
| `self.target_oto_ret` | `torch.Tensor` | 形状 `[T]` 的 Open-to-Open 收益率（t+1开盘买 -> t+2开盘卖） |
| `self.raw_open` | `torch.Tensor` | 原始开盘价序列 |
| `self.raw_close` | `torch.Tensor` | 原始收盘价序列 |
| `self.split_idx` | `int` | 训练/测试数据分割索引（80% 处） |

**特征工程细节：**
- `RET`: 日收益率 `(close[t] - close[t-1]) / close[t-1]`
- `RET5`: 5 日收益率
- `VOL_CHG`: 成交量相对 20 日均量的变化率
- `V_RET`: 量价因子 `ret * (vol_chg + 1)`
- `TREND`: 趋势因子 `close / MA60 - 1`
- 所有特征经过 Robust Normalization：`(x - median) / MAD`，并裁剪到 `[-5, 5]`

---

#### `DeepQuantMiner`

Alpha 因子挖掘器，整合公式生成、回测评估和强化学习训练。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__(self, engine)` | `engine`: `DataEngine` 实例 | 无 | 初始化 AlphaGPT 模型、AdamW 优化器和最优公式追踪器 |
| `get_strict_mask(self, open_slots, step)` | `open_slots`: 形状 `[B]` 的整数张量，表示波兰表达式中剩余待填充的槽位数；`step`: 当前生成步 | 形状 `[B, VOCAB_SIZE]` 的掩码张量 | 生成严格的动作掩码，确保生成合法的波兰表示法（Polish Notation）表达式树 |
| `solve_one(self, tokens)` | `tokens`: token ID 列表 | `torch.Tensor` 或 `None` | 将一个 token 序列解析为因子值序列（反向波兰式解析） |
| `solve_batch(self, token_seqs)` | `token_seqs`: 形状 `[B, L]` 的 token 张量 | `(results, valid_mask)` 元组 | 批量求解因子值 |
| `backtest(self, factors)` | `factors`: 形状 `[B, T]` 的因子值张量 | 形状 `[B]` 的奖励张量 | 在训练集上回测每个因子并返回 Sortino Ratio 作为奖励 |
| `train(self)` | 无 | 无 | 执行 REINFORCE 强化学习训练循环 |
| `decode(self, tokens=None)` | `tokens`: token ID 列表（默认使用 `self.best_formula_tokens`） | `str` | 将 token 序列解码为人类可读的公式字符串 |

**关键属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.engine` | `DataEngine` | 数据引擎 |
| `self.model` | `AlphaGPT` | 公式生成模型 |
| `self.opt` | `torch.optim.AdamW` | 优化器（lr=3e-4, weight_decay=1e-5） |
| `self.best_sharpe` | `float` | 训练过程中遇到的最佳 Sortino Ratio |
| `self.best_formula_tokens` | `list` 或 `None` | 最优公式的 token 序列 |

---

### 2.4 独立函数

#### `final_reality_check(miner, engine)`

对训练得到的最佳公式进行样本外（Out-of-Sample）严格回测与可视化。

| 参数 | 类型 | 说明 |
|------|------|------|
| `miner` | `DeepQuantMiner` | 训练完成的因子挖掘器 |
| `engine` | `DataEngine` | 数据引擎 |

| 返回值 | 说明 |
|--------|------|
| 无 | 打印回测统计指标并保存图表到 `strategy_performance.png` |

**输出指标：**
- 年化收益率（Ann. Return）
- 年化波动率（Ann. Volatility）
- 夏普比率（Sharpe Ratio，无风险利率 2%）
- 最大回撤（Max Drawdown）
- 卡尔玛比率（Calmar Ratio）

---

## 3. 调用关系图

```
main (__name__ == "__main__")
  |
  +-- DataEngine()
  |     +-- __init__()  -->  ts.pro_api(TS_TOKEN)
  |     +-- load()
  |           +-- [缓存不存在] pro.fund_daily() / pro.index_daily()
  |           +-- 特征工程: ret, ret5, vol_chg, v_ret, trend
  |           +-- robust_norm()  [内嵌函数, x5]
  |           +-- 构建 feat_data, target_oto_ret
  |
  +-- DeepQuantMiner(engine)
  |     +-- __init__()
  |     |     +-- AlphaGPT()
  |     |           +-- nn.Embedding, nn.TransformerEncoder, ...
  |     |
  |     +-- train()
  |     |     |
  |     |     +-- [循环 TRAIN_ITERATIONS 次]
  |     |     |   |
  |     |     |   +-- [生成阶段: 循环 MAX_SEQ_LEN 步]
  |     |     |   |     +-- AlphaGPT.forward(curr_inp)
  |     |     |   |     +-- get_strict_mask(open_slots, step)
  |     |     |   |     +-- Categorical.sample()
  |     |     |   |
  |     |     |   +-- [评估阶段]
  |     |     |   |     +-- solve_batch(seqs)
  |     |     |   |     |     +-- solve_one(tokens)  x B
  |     |     |   |     |           +-- OP_FUNC_MAP[t](args)
  |     |     |   |     |                 +-- _ts_delay / _ts_delta
  |     |     |   |     |                 +-- _ts_zscore / _ts_decay_linear
  |     |     |   |     +-- backtest(factors)
  |     |     |   |
  |     |     |   +-- [更新阶段]
  |     |     |         +-- REINFORCE loss 计算
  |     |     |         +-- optimizer.step()
  |     |
  |     +-- decode()  [用于输出最优公式]
  |
  +-- final_reality_check(miner, engine)
        +-- miner.decode()
        +-- miner.solve_one(best_formula_tokens)
        +-- 样本外回测计算
        +-- matplotlib 绘图
        +-- 保存 strategy_performance.png
```

**外部服务交互：**

```
times.py  --[Tushare API]--> Tushare 数据服务器
          --[文件 I/O]--> data_cache_final.parquet (本地缓存)
          --[文件 I/O]--> strategy_performance.png (输出图表)
```

---

## 4. 依赖关系

### 4.1 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `tushare` (`ts`) | 获取中国 A 股/ETF/指数的金融数据 |
| `pandas` (`pd`) | 数据处理（DataFrame、rolling、pct_change 等） |
| `numpy` (`np`) | 数值计算（收益率、统计量、回测） |
| `torch` | 核心深度学习框架 |
| `torch.nn` | 神经网络模块（Embedding, TransformerEncoder 等） |
| `torch.nn.functional` (`F`) | 函数式接口 |
| `torch.distributions.Categorical` | 策略梯度采样 |
| `torch.jit.script` | TorchScript JIT 编译加速 |
| `tqdm` | 训练进度条 |
| `matplotlib.pyplot` (`plt`) | 回测结果可视化 |

### 4.2 Python 标准库依赖

| 模块 | 用途 |
|------|------|
| `os` | 文件缓存存在性检查 |
| `math` | 已导入但未直接使用 |

### 4.3 内部模块依赖

无。本文件为独立可执行脚本，不引用 alphagpt 项目中的其他模块。

---

## 5. 代码逻辑流程

### 5.1 主入口流程

```
1. 创建 DataEngine 实例并加载数据
2. 创建 DeepQuantMiner 实例
3. 执行强化学习训练 (miner.train())
4. 执行样本外回测 (final_reality_check())
```

### 5.2 数据加载流程 (`DataEngine.load`)

```
1. 检查本地缓存文件是否存在:
   [存在] --> 直接读取 parquet
   [不存在] --> 通过 Tushare API 获取:
     a. 尝试 fund_daily (ETF 类)
     b. 失败则 fallback 到 index_daily (指数类)
     c. 按日期排序后保存 parquet 缓存

2. 数据清洗:
   - 对 open/high/low/close/vol 列做数值转换
   - 前向填充 + 后向填充处理缺失值

3. 特征工程 (5 个特征):
   RET     = (close[t] - close[t-1]) / close[t-1]
   RET5    = 5日收益率
   VOL_CHG = vol / MA20(vol) - 1
   V_RET   = RET * (VOL_CHG + 1)
   TREND   = close / MA60(close) - 1

4. Robust Normalization:
   每个特征 -> (x - median) / MAD -> clip(-5, 5)

5. 构建回测目标:
   target_oto_ret[t] = (open[t+2] - open[t+1]) / open[t+1]
   (代表 t 日信号触发, t+1 日开盘买入, t+2 日开盘卖出的收益)

6. 训练/测试分割: 80% / 20%
```

### 5.3 强化学习训练流程 (`DeepQuantMiner.train`)

```
每个迭代:

  [第一阶段: 公式生成]
  1. 初始化 open_slots = 1 (波兰表示法的根节点需要 1 个表达式)
  2. 逐步生成 MAX_SEQ_LEN=8 个 token:
     a. AlphaGPT 输出当前序列的 logits
     b. get_strict_mask 计算合法动作掩码:
        - 已完成的序列只能选 padding
        - 剩余步数不够时必须选特征 (叶节点)
        - 否则可选特征或算子
     c. 从掩码后的分布中采样一个 action
     d. 更新 open_slots:
        - 选特征: open_slots -= 1 (填充一个槽位)
        - 选算子: open_slots += (arity - 1) (消耗1个槽位, 产生arity个新槽位)

  [第二阶段: 公式评估]
  3. solve_batch 批量求解:
     对每个 token 序列, 用反向解析法执行:
     - 从右向左遍历 token
     - 特征 token -> 压入栈
     - 算子 token -> 弹出 arity 个操作数, 执行运算, 结果压栈
     - 最终栈顶元素即为因子值序列

  4. backtest 回测评估:
     对每个有效因子:
     a. signal = tanh(factor)
     b. position = sign(signal)
     c. turnover = |pos[t] - pos[t-1]|
     d. pnl = position * target_ret - turnover * COST_RATE
     e. 计算 Sortino Ratio (使用下行风险)
     f. 施加惩罚:
        - 均值为负: reward = -2
        - 过度交易 (turnover > 0.5): reward -= 1
        - 全空仓: reward = -2
     g. 裁剪到 [-3, 5]

  [第三阶段: 策略更新]
  5. 计算 REINFORCE loss:
     advantage = reward - mean(reward)
     loss = -mean(sum(log_prob) * advantage)
  6. 反向传播并更新模型参数
  7. 追踪全局最优公式
```

### 5.4 样本外回测流程 (`final_reality_check`)

```
1. 解码最优公式为可读字符串

2. 用 solve_one 计算全量因子值

3. 提取测试集 (后 20%) 数据:
   - 因子值、Open-to-Open 收益率、日期

4. 生成交易信号:
   signal = tanh(factor)
   position = sign(signal)  (多/空/不持仓)

5. 计算净 PnL:
   daily_ret = position * target_ret - turnover * COST_RATE

6. 统计指标:
   - 累计权益曲线: equity = cumprod(1 + daily_ret)
   - 年化收益率: equity[-1]^(252/N) - 1
   - 年化波动率: std(daily_ret) * sqrt(252)
   - 夏普比率: (ann_ret - 0.02) / vol
   - 最大回撤: max(1 - equity / cummax(equity))
   - 卡尔玛比率: ann_ret / max_dd

7. 绘图:
   - 策略权益曲线 vs 基准 (Buy & Hold)
   - 保存到 strategy_performance.png
```
