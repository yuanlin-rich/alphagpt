# model_core 模块文档

## 1. 模块概述

`model_core` 是 AlphaGPT 项目的核心计算模块，实现了一套完整的**基于强化学习的量化因子挖掘系统**，专注于加密货币（Meme 币）领域的 Alpha 信号发现。

该模块的核心思想是：使用一个基于 Transformer 架构的生成模型（AlphaGPT）来自动生成因子公式（由特征标识符和算子组成的 token 序列），然后通过栈式虚拟机（StackVM）执行这些公式以计算因子值，最后通过回测引擎评估因子的实际交易表现，并将回测得分作为强化学习的奖励信号反馈给模型进行策略梯度优化。

整体工作流程如下：

1. **数据加载**：从 PostgreSQL 数据库中加载加密货币 OHLCV 及流动性数据
2. **特征工程**：基于原始数据计算多维度因子特征（收益率、流动性评分、买卖压力、FOMO 加速度等）
3. **公式生成**：AlphaGPT 模型自回归地生成因子公式 token 序列
4. **公式执行**：StackVM 虚拟机解释执行公式，将特征数据通过算子组合为最终因子值
5. **回测评估**：MemeBacktest 引擎模拟交易，考虑流动性约束、滑点和手续费
6. **策略梯度训练**：使用 REINFORCE 算法，以回测得分作为奖励优化模型参数

---

## 2. 文件说明

### `config.py`
**全局配置中心**。定义 `ModelConfig` 类，集中管理所有超参数和环境配置：
- 设备选择（CUDA/CPU 自动检测）
- 数据库连接 URL（通过环境变量配置 PostgreSQL 连接）
- 训练参数：批量大小（8192）、训练步数（1000）、最大公式长度（12）
- 交易参数：交易规模（$1000）、最低流动性阈值（$5000）、基础费率（0.5%）
- 模型参数：输入特征维度（6）

### `factors.py`
**特征工程模块**。包含三个核心组件：
- **`RMSNormFactor`**：用于因子归一化的 RMSNorm 层
- **`MemeIndicators`**：Meme 币专用技术指标集合，包括流动性健康度、买卖不平衡度、FOMO 加速度、泵价偏离度、波动率聚类、动量反转、相对强弱等 7 个指标
- **`FeatureEngineer`**：基础特征工程类，将原始 OHLCV 数据转化为 6 维标准化特征张量
- **`AdvancedFactorEngineer`**：高级特征工程类，将原始数据转化为 12 维特征空间（包含基础因子和高级因子）

### `ops.py`
**算子定义模块**。定义了因子公式中可用的所有运算算子：
- **基础算术算子**：ADD、SUB、MUL、DIV（二元）；NEG、ABS、SIGN（一元）
- **时序算子**：DELAY1（延迟 1 期）、DECAY（指数衰减加权）、MAX3（3 期最大值）
- **条件算子**：GATE（条件门控，三元）
- **检测算子**：JUMP（跳跃检测，Z-score > 3）
- 包含 JIT 编译的辅助函数 `_ts_delay`、`_op_gate`、`_op_jump`、`_op_decay`

每个算子以 `(名称, 函数, 参数数量)` 三元组的形式注册在 `OPS_CONFIG` 列表中。

### `vm.py`
**栈式虚拟机**。`StackVM` 类负责解释执行因子公式 token 序列：
- token 值小于 `feat_offset`（6）的被视为特征索引，直接从特征张量中取出对应特征
- token 值大于等于 `feat_offset` 的被视为算子索引，从栈中弹出对应数量的操作数执行运算
- 执行过程中自动处理 NaN/Inf 异常值
- 执行成功返回一个形状为 `[N_tokens, T]` 的张量；执行失败（栈不平衡、参数不足等）返回 `None`

### `alphagpt.py`
**核心模型定义**。包含 AlphaGPT 模型及其所有子组件：
- **`RMSNorm`**：Root Mean Square 层归一化，替代标准 LayerNorm
- **`QKNorm`**：Query-Key 归一化，对注意力机制中的 Q 和 K 做 L2 归一化并应用可学习缩放
- **`SwiGLU`**：Swish GLU 激活函数，替代标准 FFN 中的 ReLU
- **`MTPHead`**：多任务池化头，包含任务路由器和多个任务头的加权组合输出
- **`LoopedTransformerLayer`**：循环 Transformer 层，在单层内进行多次（默认 3 次）循环精炼
- **`LoopedTransformer`**：由多个 LoopedTransformerLayer 组成的编码器
- **`AlphaGPT`**：主模型类，将上述组件组装为完整的 token 序列生成模型
- **`NewtonSchulzLowRankDecay`**：基于 Newton-Schulz 迭代的低秩衰减（LoRD）正则化器
- **`StableRankMonitor`**：稳定秩监控器，用于追踪模型参数的有效秩

### `data_loader.py`
**数据加载模块**。`CryptoDataLoader` 类负责：
- 通过 SQLAlchemy 连接 PostgreSQL 数据库
- 加载指定数量 token 的 OHLCV + 流动性 + FDV 数据
- 将 DataFrame 透视（pivot）为张量格式 `[N_tokens, T]`
- 调用 `FeatureEngineer` 计算特征张量
- 计算目标收益率（基于未来两期开盘价的对数收益率）

### `backtest.py`
**回测引擎**。`MemeBacktest` 类实现了面向 Meme 币的简化回测逻辑：
- 基于因子值生成交易信号（sigmoid 阈值 > 0.85）
- 流动性过滤：低于最低流动性阈值的标的不交易
- 滑点模型：基础费率 + 冲击滑点（与交易规模/流动性成正比，上限 5%）
- 计算毛收益、净收益（扣除交易成本）
- 惩罚大亏损（单期亏损 > 5% 惩罚 2 分）和低活跃度（< 5 次交易惩罚 -10 分）
- 最终得分取中位数，提高对异常值的鲁棒性

### `engine.py`
**训练引擎**。`AlphaEngine` 类是整个系统的编排中心：
- 初始化数据加载器、模型、优化器、LoRD 正则化器、虚拟机和回测引擎
- 实现完整的 REINFORCE 策略梯度训练循环
- 每步生成 `BATCH_SIZE`（8192）条公式，通过 VM 执行和回测评估获取奖励
- 对奖励进行标准化处理（减均值除标准差）后计算策略梯度
- 可选启用 LoRD 正则化和稳定秩监控
- 记录训练历史，保存最优公式和训练日志

---

## 3. 架构图

```
+------------------------------------------------------------------+
|                         AlphaEngine (engine.py)                  |
|                      [ 训练编排 / REINFORCE ]                     |
+------------------------------------------------------------------+
        |               |              |              |
        v               v              v              v
+---------------+ +-----------+ +-----------+ +----------------+
| CryptoData-   | | AlphaGPT  | | StackVM   | | MemeBacktest   |
| Loader        | | (模型)     | | (虚拟机)   | | (回测引擎)      |
| data_loader.py| | alphagpt.py| | vm.py     | | backtest.py    |
+---------------+ +-----------+ +-----------+ +----------------+
        |               |              |
        v               |              v
+---------------+       |       +-----------+
| FeatureEngi-  |       |       | OPS_CONFIG|
| neer          |       |       | ops.py    |
| factors.py    |       |       +-----------+
+---------------+       |              ^
        ^               |              |
        |               v              |
        |        +-------------+       |
        |        | ModelConfig |-------+
        |        | config.py   |
        |        +-------------+
        |               ^
        +---------------+

+------------------------------------------------------------------+
|                  AlphaGPT 模型内部结构 (alphagpt.py)               |
+------------------------------------------------------------------+
|                                                                  |
|  输入 token 序列                                                  |
|       |                                                          |
|       v                                                          |
|  [Token Embedding + Positional Embedding]                        |
|       |                                                          |
|       v                                                          |
|  +------------------------------------------------------------+  |
|  | LoopedTransformer (num_layers=2)                           |  |
|  |  +------------------------------------------------------+  |  |
|  |  | LoopedTransformerLayer (num_loops=3)                  |  |  |
|  |  |  +---> RMSNorm --> MultiheadAttention (QKNorm) --+   |  |  |
|  |  |  |         (残差连接)                     <-------+   |  |  |
|  |  |  +---> RMSNorm --> SwiGLU FFN ---------------+       |  |  |
|  |  |  |         (残差连接)                  <------+       |  |  |
|  |  |  +--- 循环 num_loops 次 ---                          |  |  |
|  |  +------------------------------------------------------+  |  |
|  +------------------------------------------------------------+  |
|       |                                                          |
|       v                                                          |
|  [RMSNorm] --> 取最后位置 embedding                               |
|       |                      |                                   |
|       v                      v                                   |
|  [MTPHead]            [head_critic]                              |
|  (多任务池化头)          (价值头)                                   |
|       |                      |                                   |
|       v                      v                                   |
|    logits               value (标量)                              |
|  (词表概率分布)                                                    |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
|                  数据流与调用关系                                    |
+------------------------------------------------------------------+
|                                                                  |
|  PostgreSQL DB                                                   |
|       |                                                          |
|       v                                                          |
|  CryptoDataLoader.load_data()                                    |
|       |                                                          |
|       +---> raw_data_cache {open,high,low,close,volume,          |
|       |                     liquidity,fdv}                       |
|       |         |                                                |
|       |         v                                                |
|       |    FeatureEngineer.compute_features()                    |
|       |         |                                                |
|       |         v                                                |
|       |    feat_tensor [N_tokens, 6, T]                          |
|       |                                                          |
|       +---> target_ret [N_tokens, T]                             |
|                                                                  |
|  训练循环中:                                                      |
|    AlphaGPT.forward(inp) --> logits --> Categorical采样           |
|         --> 生成 formula token 序列                                |
|              |                                                   |
|              v                                                   |
|    StackVM.execute(formula, feat_tensor) --> factor值             |
|              |                                                   |
|              v                                                   |
|    MemeBacktest.evaluate(factor, raw_data, target_ret) --> score  |
|              |                                                   |
|              v                                                   |
|    REINFORCE: loss = -log_prob * advantage                       |
|              |                                                   |
|              v                                                   |
|    AdamW.step() + LoRD.step() --> 更新模型参数                     |
+------------------------------------------------------------------+
```

---

## 4. 依赖关系

### 4.1 内部模块依赖

下表展示 `model_core` 内部各文件之间的导入关系：

| 文件 | 导入的内部模块 | 说明 |
|------|---------------|------|
| `config.py` | 无 | 基础配置，无内部依赖 |
| `ops.py` | 无 | 算子定义，无内部依赖 |
| `factors.py` | 无 | 特征工程，无内部依赖（纯 PyTorch 计算） |
| `vm.py` | `ops.OPS_CONFIG`, `factors.FeatureEngineer` | 依赖算子配置和特征维度常量 |
| `alphagpt.py` | `config.ModelConfig`, `ops.OPS_CONFIG` | 依赖配置参数和算子列表构建词表 |
| `data_loader.py` | `config.ModelConfig`, `factors.FeatureEngineer` | 依赖配置和特征工程 |
| `backtest.py` | 无 | 回测引擎，无内部依赖 |
| `engine.py` | `config.ModelConfig`, `data_loader.CryptoDataLoader`, `alphagpt.AlphaGPT`, `alphagpt.NewtonSchulzLowRankDecay`, `alphagpt.StableRankMonitor`, `vm.StackVM`, `backtest.MemeBacktest` | 编排中心，依赖所有其他模块 |

### 4.2 外部第三方依赖

| 依赖库 | 使用位置 | 用途 |
|--------|---------|------|
| `torch` | 全部文件 | PyTorch 深度学习框架，提供张量计算、神经网络、JIT 编译、自动微分等核心功能 |
| `torch.nn` | `alphagpt.py`, `factors.py` | 神经网络模块定义（Linear、Embedding、MultiheadAttention、ModuleList 等） |
| `torch.nn.functional` | `alphagpt.py` | 函数式 API（softmax、silu、normalize 等） |
| `torch.distributions` | `engine.py` | 分类分布（Categorical），用于策略梯度采样 |
| `torch.jit` | `ops.py` | TorchScript JIT 编译，优化算子执行性能 |
| `pandas` | `data_loader.py` | 数据读取与透视操作（read_sql、pivot） |
| `sqlalchemy` | `data_loader.py` | 数据库 ORM 引擎，连接 PostgreSQL |
| `tqdm` | `engine.py` | 训练进度条显示 |
| `json` | `engine.py` | 保存最优公式和训练历史 |
| `os` | `config.py` | 读取环境变量（数据库连接配置） |

---

## 5. 关键类/函数

### 5.1 `AlphaGPT` (alphagpt.py)

**核心生成模型**，基于 Looped Transformer 架构的因子公式生成器。

```python
class AlphaGPT(nn.Module):
    def __init__(self)
    def forward(self, idx) -> Tuple[logits, value, task_probs]
```

| 属性/参数 | 类型 | 说明 |
|-----------|------|------|
| `d_model` | `int` | 模型隐藏维度，固定为 64 |
| `features_list` | `list` | 特征名称列表：`['RET', 'VOL', 'V_CHG', 'PV', 'TREND']` |
| `ops_list` | `list` | 从 `OPS_CONFIG` 提取的算子名称列表 |
| `vocab_size` | `int` | 词表大小 = 特征数 + 算子数 |
| `forward(idx)` | - | 输入 `idx: [B, T]` token 索引，返回 `(logits: [B, vocab_size], value: [B, 1], task_probs: [B, num_tasks])` |

---

### 5.2 `LoopedTransformerLayer` / `LoopedTransformer` (alphagpt.py)

**循环 Transformer 层**，在单层内对输入进行多次迭代精炼。

```python
class LoopedTransformerLayer(nn.Module):
    def __init__(self, d_model, nhead, dim_feedforward, num_loops=3, dropout=0.1)
    def forward(self, x, mask=None, is_causal=False) -> Tensor

class LoopedTransformer(nn.Module):
    def __init__(self, d_model, nhead, num_layers, dim_feedforward, num_loops=3, dropout=0.1)
    def forward(self, x, mask=None, is_causal=False) -> Tensor
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `d_model` | `int` | 模型维度 |
| `nhead` | `int` | 注意力头数 |
| `num_layers` | `int` | Transformer 层数 |
| `dim_feedforward` | `int` | 前馈网络隐藏层维度 |
| `num_loops` | `int` | 每层内循环次数（默认 3） |
| `dropout` | `float` | Dropout 比率 |

---

### 5.3 `MTPHead` (alphagpt.py)

**多任务池化头**，支持多目标学习，通过路由器动态加权多个任务头的输出。

```python
class MTPHead(nn.Module):
    def __init__(self, d_model, vocab_size, num_tasks=3)
    def forward(self, x) -> Tuple[weighted_output, task_probs]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `d_model` | `int` | 输入特征维度 |
| `vocab_size` | `int` | 每个任务头的输出维度 |
| `num_tasks` | `int` | 任务头数量（默认 3） |

---

### 5.4 `NewtonSchulzLowRankDecay` (alphagpt.py)

**基于 Newton-Schulz 迭代的低秩衰减正则化器**。不需要显式 SVD 分解，通过迭代近似计算最小奇异向量方向，对注意力相关参数施加低秩结构约束。

```python
class NewtonSchulzLowRankDecay:
    def __init__(self, named_parameters, decay_rate=1e-3, num_iterations=5, target_keywords=None)
    def step(self)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `named_parameters` | `iterator` | 模型的命名参数迭代器 |
| `decay_rate` | `float` | 低秩衰减强度（默认 1e-3） |
| `num_iterations` | `int` | Newton-Schulz 迭代次数（默认 5） |
| `target_keywords` | `list[str]` | 目标参数名关键字（默认 `["qk_norm", "attention"]`） |

---

### 5.5 `StableRankMonitor` (alphagpt.py)

**稳定秩监控器**。计算目标参数的稳定秩（Frobenius 范数的平方 / 谱范数的平方），用于监控模型参数的有效秩变化。

```python
class StableRankMonitor:
    def __init__(self, model, target_keywords=None)
    def compute(self) -> float
```

---

### 5.6 `RMSNorm` / `QKNorm` / `SwiGLU` (alphagpt.py)

**模型子组件**：

| 类 | 说明 |
|----|------|
| `RMSNorm(d_model, eps)` | Root Mean Square 归一化层，替代 LayerNorm |
| `QKNorm(d_model, eps)` | Query-Key 归一化，对 Q/K 做 L2 归一化后乘以可学习缩放因子 |
| `SwiGLU(d_in, d_ff)` | Swish-Gated Linear Unit 激活函数，用于替代标准 ReLU FFN |

---

### 5.7 `StackVM` (vm.py)

**栈式虚拟机**，负责将 token 序列解释执行为因子张量。

```python
class StackVM:
    def __init__(self)
    def execute(self, formula_tokens, feat_tensor) -> Optional[Tensor]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `formula_tokens` | `list[int]` | 因子公式 token 序列 |
| `feat_tensor` | `Tensor` | 特征张量，形状 `[N_tokens, INPUT_DIM, T]` |
| 返回值 | `Tensor` 或 `None` | 成功返回 `[N_tokens, T]` 因子值张量；失败返回 `None` |

**执行逻辑**：
- token < `feat_offset`(6)：从 `feat_tensor` 中取对应维度的特征压入栈
- token >= `feat_offset`：查找对应算子，弹出所需操作数执行运算，结果压入栈
- 最终栈中恰好剩余 1 个元素时返回该元素，否则返回 `None`

---

### 5.8 `OPS_CONFIG` (ops.py)

**算子注册表**，`list[tuple]` 类型，每个元素为 `(名称, 函数, 参数数量)`。

| 算子名 | 参数数 | 功能 |
|--------|--------|------|
| `ADD` | 2 | 逐元素加法 |
| `SUB` | 2 | 逐元素减法 |
| `MUL` | 2 | 逐元素乘法 |
| `DIV` | 2 | 安全除法（分母加 1e-6） |
| `NEG` | 1 | 取负 |
| `ABS` | 1 | 取绝对值 |
| `SIGN` | 1 | 取符号 |
| `GATE` | 3 | 条件门控：condition > 0 选 x，否则选 y |
| `JUMP` | 1 | 跳跃检测：Z-score 超过 3 的部分 |
| `DECAY` | 1 | 指数衰减加权：x + 0.8*delay(x,1) + 0.6*delay(x,2) |
| `DELAY1` | 1 | 延迟 1 期 |
| `MAX3` | 1 | 最近 3 期最大值 |

**JIT 编译辅助函数**：
- `_ts_delay(x, d)` -- 时间序列延迟
- `_op_gate(condition, x, y)` -- 门控操作
- `_op_jump(x)` -- 跳跃检测
- `_op_decay(x)` -- 衰减加权

---

### 5.9 `MemeIndicators` / `FeatureEngineer` / `AdvancedFactorEngineer` (factors.py)

**特征工程组件**：

#### `MemeIndicators`（静态方法集合）

| 方法 | 参数 | 说明 |
|------|------|------|
| `liquidity_health(liquidity, fdv)` | 流动性、FDV | 流动性健康度，liquidity/fdv 比值归一化到 [0,1] |
| `buy_sell_imbalance(close, open_, high, low)` | OHLC | 买卖不平衡度，基于 K 线实体与振幅之比 |
| `fomo_acceleration(volume, window=5)` | 成交量 | FOMO 加速度，成交量变化率的二阶差分 |
| `pump_deviation(close, window=20)` | 收盘价 | 泵价偏离度，当前价格偏离移动均线的比率 |
| `volatility_clustering(close, window=10)` | 收盘价 | 波动率聚类，收益率平方的移动平均开方 |
| `momentum_reversal(close, window=5)` | 收盘价 | 动量反转信号，检测动量方向翻转 |
| `relative_strength(close, high, low, window=14)` | 价格数据 | 类 RSI 相对强弱指标，归一化到 [-1,1] |

#### `FeatureEngineer`

```python
class FeatureEngineer:
    INPUT_DIM = 6
    @staticmethod
    def compute_features(raw_dict) -> Tensor  # 返回 [N, 6, T]
```

计算 6 维特征：收益率、流动性评分、买卖压力、FOMO 加速度、泵价偏离、对数成交量。使用基于 MAD（中位数绝对偏差）的鲁棒归一化。

#### `AdvancedFactorEngineer`

```python
class AdvancedFactorEngineer:
    def __init__(self)
    def robust_norm(self, t) -> Tensor
    def compute_advanced_features(self, raw_dict) -> Tensor  # 返回 [N, 12, T]
```

计算 12 维特征空间，在基础 6 维之上增加：波动率聚类、动量反转、相对强弱、高低振幅、收盘位置、成交量趋势。

---

### 5.10 `CryptoDataLoader` (data_loader.py)

**数据加载器**，从 PostgreSQL 加载加密货币市场数据。

```python
class CryptoDataLoader:
    def __init__(self)
    def load_data(self, limit_tokens=500) -> None
```

| 属性 | 类型 | 说明 |
|------|------|------|
| `engine` | `sqlalchemy.Engine` | 数据库引擎实例 |
| `feat_tensor` | `Tensor` | 计算后的特征张量 `[N, 6, T]` |
| `raw_data_cache` | `dict[str, Tensor]` | 原始数据缓存，键为 `open/high/low/close/volume/liquidity/fdv` |
| `target_ret` | `Tensor` | 目标收益率 `[N, T]`，基于未来两期开盘价对数收益率 |
| `limit_tokens` | `int` | 加载的 token（币种）数量上限（默认 500） |

---

### 5.11 `MemeBacktest` (backtest.py)

**Meme 币回测引擎**，评估因子值的实际交易表现。

```python
class MemeBacktest:
    def __init__(self)
    def evaluate(self, factors, raw_data, target_ret) -> Tuple[final_fitness, cum_ret_mean]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `factors` | `Tensor` | 因子值张量 `[N, T]` |
| `raw_data` | `dict` | 原始市场数据字典（需包含 `liquidity` 键） |
| `target_ret` | `Tensor` | 目标收益率 `[N, T]` |
| 返回值 | `tuple` | `(final_fitness: Tensor标量, cum_ret_mean: float)` |

**评估流程**：
1. `sigmoid(factors)` 生成信号，阈值 > 0.85 产生买入仓位
2. 流动性过滤：`liquidity > min_liq`（$500,000）
3. 计算滑点：`base_fee(0.6%) + impact_slippage`（上限 5%）
4. 计算换手成本：`|position_change| * total_slippage`
5. 净收益 = 毛收益 - 交易成本
6. 评分 = 累计收益 - 大亏损惩罚 - 低活跃度惩罚
7. 取中位数作为最终适应度

---

### 5.12 `AlphaEngine` (engine.py)

**训练引擎**，整个系统的编排中心。

```python
class AlphaEngine:
    def __init__(self, use_lord_regularization=True, lord_decay_rate=1e-3, lord_num_iterations=5)
    def train(self) -> None
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `use_lord_regularization` | `bool` | 是否启用 LoRD 正则化（默认 True） |
| `lord_decay_rate` | `float` | LoRD 衰减强度（默认 1e-3） |
| `lord_num_iterations` | `int` | Newton-Schulz 迭代次数（默认 5） |

**`train()` 方法执行流程**：
1. 生成 `BATCH_SIZE` 条初始 token 序列
2. 自回归生成 `MAX_FORMULA_LEN` 长度的公式
3. 对每条公式通过 StackVM 执行并回测评估
4. 使用 REINFORCE 策略梯度更新模型
5. 可选应用 LoRD 正则化和稳定秩监控
6. 训练完成后保存最优公式至 `best_meme_strategy.json`，训练历史至 `training_history.json`

---

### 5.13 `ModelConfig` (config.py)

**全局配置类**，所有参数为类属性（静态配置）。

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `DEVICE` | `torch.device` | 自动检测 | 计算设备（cuda/cpu） |
| `DB_URL` | `str` | 环境变量拼接 | PostgreSQL 连接字符串 |
| `BATCH_SIZE` | `int` | 8192 | 每步生成的公式数量 |
| `TRAIN_STEPS` | `int` | 1000 | 总训练步数 |
| `MAX_FORMULA_LEN` | `int` | 12 | 公式最大 token 长度 |
| `TRADE_SIZE_USD` | `float` | 1000.0 | 单笔交易规模（美元） |
| `MIN_LIQUIDITY` | `float` | 5000.0 | 最低流动性阈值（美元） |
| `BASE_FEE` | `float` | 0.005 | 基础费率（含 Swap + Gas + Jito Tip） |
| `INPUT_DIM` | `int` | 6 | 输入特征维度 |
