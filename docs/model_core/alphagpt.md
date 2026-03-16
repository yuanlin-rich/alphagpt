# alphagpt.py 文档

## 1. 文件概述

`alphagpt.py` 是 AlphaGPT 项目的核心模型定义文件，负责构建整个神经网络架构。该文件实现了一个基于 **Looped Transformer** 的序列生成模型，用于自动生成量化交易因子公式。模型融合了多项现代深度学习技术：

- **RMSNorm**（Root Mean Square Normalization）替代传统 LayerNorm
- **QKNorm**（Query-Key Normalization）稳定注意力机制
- **SwiGLU** 激活函数替代标准 FFN
- **MTPHead**（Multi-Task Pooling Head）实现多任务学习
- **Looped Transformer** 在每层内进行循环（recurrent）精炼处理
- **Newton-Schulz Low-Rank Decay** 正则化方法
- **Stable Rank Monitor** 用于监控参数矩阵的有效秩

---

## 2. 类与函数说明

### 2.1 `NewtonSchulzLowRankDecay`

基于 Newton-Schulz 迭代的低秩衰减正则化器。通过迭代逼近参数矩阵的正交分量，对注意力相关参数施加低秩结构约束，避免显式 SVD 分解的高计算开销。

**构造函数参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `named_parameters` | iterator | - | 模型的 `named_parameters()` 迭代器 |
| `decay_rate` | float | `1e-3` | 低秩衰减强度 |
| `num_iterations` | int | `5` | Newton-Schulz 迭代次数 |
| `target_keywords` | list[str] \| None | `None`（默认为 `["qk_norm", "attention"]`） | 匹配的参数名关键字列表 |

**实例属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `decay_rate` | float | 衰减率 |
| `num_iterations` | int | 迭代次数 |
| `target_keywords` | list[str] | 目标参数名关键字 |
| `params_to_decay` | list[tuple] | 筛选后需要衰减的 `(name, param)` 列表，仅含 2D 且 `requires_grad=True` 的参数 |

**方法：**

#### `step()`
- **装饰器：** `@torch.no_grad()`
- **返回值：** 无（就地修改参数）
- **用途：** 对每个目标参数执行 Newton-Schulz 迭代，计算其正交近似矩阵 Y，然后从原参数中减去 `decay_rate * Y`，实现低秩正则化。
- **算法步骤：** 将参数转为 float32 -> 如果行数 > 列数则转置 -> 按谱范数归一化 -> 执行 N-S 迭代 `Y_{k+1} = 0.5 * Y_k * (3I - Y_k^T * Y_k)` -> 反转置 -> 从权重中减去衰减项

---

### 2.2 `StableRankMonitor`

监控模型参数矩阵的稳定秩（Stable Rank），用于诊断模型训练过程中参数的低秩退化情况。

**构造函数参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | nn.Module | - | 待监控的 PyTorch 模型 |
| `target_keywords` | list[str] \| None | `None`（默认为 `["q_proj", "k_proj", "attention"]`） | 目标参数名关键字 |

**实例属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `model` | nn.Module | 被监控的模型 |
| `target_keywords` | list[str] | 目标参数名关键字 |
| `history` | list[float] | 历史稳定秩记录 |

**方法：**

#### `compute() -> float`
- **装饰器：** `@torch.no_grad()`
- **返回值：** `float` -- 目标参数的平均稳定秩
- **用途：** 遍历模型所有 2D 参数，对名称匹配关键字的参数计算稳定秩 `||W||_F^2 / ||W||_2^2`（即 Frobenius 范数的平方除以最大奇异值的平方），返回平均值并记录到 `history`。

---

### 2.3 `RMSNorm(nn.Module)`

Root Mean Square 层归一化。相比标准 LayerNorm，RMSNorm 不做中心化（减均值），仅做缩放，计算更高效。

**构造函数参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `d_model` | int | - | 特征维度 |
| `eps` | float | `1e-6` | 数值稳定性的极小值 |

**可学习参数：**

| 参数 | 形状 | 说明 |
|------|------|------|
| `weight` | `(d_model,)` | 缩放因子，初始化为全 1 |

**方法：**

#### `forward(x) -> Tensor`
- **参数：** `x` -- 输入张量，最后一维大小为 `d_model`
- **返回值：** 归一化后的张量，形状不变
- **计算：** `rms = sqrt(mean(x^2, dim=-1) + eps)`，输出 `(x / rms) * weight`

---

### 2.4 `QKNorm(nn.Module)`

Query-Key 归一化模块，对注意力机制中的 Q 和 K 独立进行 L2 归一化并乘以可学习缩放因子，防止注意力得分爆炸。

**构造函数参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `d_model` | int | - | 每个注意力头的特征维度 |
| `eps` | float | `1e-6` | 数值稳定性的极小值 |

**可学习参数：**

| 参数 | 形状 | 说明 |
|------|------|------|
| `scale` | `(1, 1, 1, d_model)` | 缩放因子，初始化为 `d_model^{-0.5}` |

**方法：**

#### `forward(q, k) -> tuple[Tensor, Tensor]`
- **参数：** `q` -- Query 张量；`k` -- Key 张量
- **返回值：** `(q_norm * scale, k_norm * scale)` -- 归一化并缩放后的 Q 和 K
- **计算：** 对 Q 和 K 的最后一维做 L2 归一化后乘以 `scale`

---

### 2.5 `SwiGLU(nn.Module)`

Swish GLU（Gated Linear Unit）激活函数模块，用于替代标准的 ReLU FFN，在大语言模型中被广泛验证具有更好的表达能力。

**构造函数参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `d_in` | int | 输入/输出维度 |
| `d_ff` | int | 前馈网络隐藏层维度 |

**子模块：**

| 模块 | 类型 | 说明 |
|------|------|------|
| `w` | `nn.Linear(d_in, d_ff * 2)` | 投影层，输出同时包含值和门控信号 |
| `fc` | `nn.Linear(d_ff, d_in)` | 输出投影层 |

**方法：**

#### `forward(x) -> Tensor`
- **参数：** `x` -- 形状 `(..., d_in)` 的输入张量
- **返回值：** 形状 `(..., d_in)` 的输出张量
- **计算：** `w(x)` 分为两半 `(x_val, gate)` -> `x_val * silu(gate)` -> `fc(...)`

---

### 2.6 `MTPHead(nn.Module)`

Multi-Task Pooling Head，多任务池化输出头。包含多个独立的任务头和一个动态路由器，实现多目标学习的加权融合。

**构造函数参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `d_model` | int | - | 输入特征维度 |
| `vocab_size` | int | - | 词汇表大小（输出维度） |
| `num_tasks` | int | `3` | 任务数量 |

**子模块与可学习参数：**

| 名称 | 类型 | 说明 |
|------|------|------|
| `task_heads` | `nn.ModuleList[nn.Linear]` | `num_tasks` 个独立的线性输出头 |
| `task_weights` | `nn.Parameter` | 形状 `(num_tasks,)`，初始化为均匀权重 |
| `task_router` | `nn.Sequential` | 任务路由器：`Linear(d_model, d_model//2) -> ReLU -> Linear(d_model//2, num_tasks)` |

**方法：**

#### `forward(x) -> tuple[Tensor, Tensor]`
- **参数：** `x` -- 形状 `(B, d_model)` 的输入张量（通常是序列最后一个位置的 embedding）
- **返回值：** `(weighted, task_probs)`
  - `weighted` -- 形状 `(B, vocab_size)`，各任务输出的加权融合结果
  - `task_probs` -- 形状 `(B, num_tasks)`，经 softmax 的任务路由概率
- **计算：** 路由器生成任务概率 -> 每个任务头独立产生 logits -> 按概率加权求和

---

### 2.7 `LoopedTransformerLayer(nn.Module)`

循环 Transformer 层，在单层内进行多次迭代（loop）的自注意力 + FFN 处理，实现递归精炼。

**构造函数参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `d_model` | int | - | 模型特征维度 |
| `nhead` | int | - | 注意力头数 |
| `dim_feedforward` | int | - | 前馈网络隐藏层维度 |
| `num_loops` | int | `3` | 层内循环迭代次数 |
| `dropout` | float | `0.1` | Dropout 比率 |

**子模块：**

| 模块 | 类型 | 说明 |
|------|------|------|
| `qk_norm` | `QKNorm` | Q-K 归一化（注意：当前 forward 中未显式使用） |
| `attention` | `nn.MultiheadAttention` | 多头自注意力（batch_first=True） |
| `norm1` | `RMSNorm` | 第一层 RMSNorm（用于注意力前） |
| `norm2` | `RMSNorm` | 第二层 RMSNorm（用于 FFN 前） |
| `ffn` | `SwiGLU` | SwiGLU 前馈网络 |
| `dropout` | `nn.Dropout` | Dropout 层 |

**方法：**

#### `forward(x, mask=None, is_causal=False) -> Tensor`
- **参数：**
  - `x` -- 形状 `(B, T, d_model)` 的输入张量
  - `mask` -- 可选的注意力掩码
  - `is_causal` -- 是否为因果（自回归）掩码
- **返回值：** 形状 `(B, T, d_model)` 的输出张量
- **计算：** 重复 `num_loops` 次：`RMSNorm -> MultiheadAttention + 残差 -> RMSNorm -> SwiGLU + 残差`

---

### 2.8 `LoopedTransformer(nn.Module)`

循环 Transformer 编码器，由多个 `LoopedTransformerLayer` 堆叠而成。

**构造函数参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `d_model` | int | - | 模型特征维度 |
| `nhead` | int | - | 注意力头数 |
| `num_layers` | int | - | 层数 |
| `dim_feedforward` | int | - | 前馈网络隐藏层维度 |
| `num_loops` | int | `3` | 每层的循环次数 |
| `dropout` | float | `0.1` | Dropout 比率 |

**子模块：**

| 模块 | 类型 | 说明 |
|------|------|------|
| `layers` | `nn.ModuleList[LoopedTransformerLayer]` | `num_layers` 个循环 Transformer 层 |

**方法：**

#### `forward(x, mask=None, is_causal=False) -> Tensor`
- **参数/返回值：** 同 `LoopedTransformerLayer.forward()`
- **计算：** 按顺序通过每个 layer

---

### 2.9 `AlphaGPT(nn.Module)`

项目核心模型类。组合以上所有组件，构建一个完整的因子公式生成模型。输入为 token 索引序列（因子名称或操作符的编码），输出为下一个 token 的 logits、价值评估和任务概率。

**构造函数参数：** 无（所有超参数硬编码）

**实例属性与子模块：**

| 名称 | 类型 | 说明 |
|------|------|------|
| `d_model` | int | 模型维度，硬编码为 `64` |
| `features_list` | list[str] | 特征名列表：`['RET', 'VOL', 'V_CHG', 'PV', 'TREND']` |
| `ops_list` | list[str] | 操作符名列表，从 `OPS_CONFIG` 中提取 |
| `vocab` | list[str] | 完整词汇表 = `features_list + ops_list` |
| `vocab_size` | int | 词汇表大小 |
| `token_emb` | `nn.Embedding` | Token 嵌入层，`(vocab_size, 64)` |
| `pos_emb` | `nn.Parameter` | 可学习位置嵌入，形状 `(1, MAX_FORMULA_LEN+1, 64)` |
| `blocks` | `LoopedTransformer` | 主干网络，2 层、4 头、FFN 维度 128、3 次循环 |
| `ln_f` | `RMSNorm` | 最终层归一化 |
| `mtp_head` | `MTPHead` | 多任务输出头，3 个任务 |
| `head_critic` | `nn.Linear` | 价值评估头，`Linear(64, 1)` |

**方法：**

#### `forward(idx) -> tuple[Tensor, Tensor, Tensor]`
- **参数：** `idx` -- 形状 `(B, T)` 的 token 索引张量
- **返回值：** `(logits, value, task_probs)`
  - `logits` -- 形状 `(B, vocab_size)`，下一个 token 的预测概率分布
  - `value` -- 形状 `(B, 1)`，当前序列的价值评估
  - `task_probs` -- 形状 `(B, num_tasks)`，任务路由概率
- **计算流程：**
  1. Token 嵌入 + 位置嵌入
  2. 生成因果掩码（上三角掩码）
  3. 通过 LoopedTransformer 处理
  4. RMSNorm 最终归一化
  5. 取最后一个时间步的 embedding
  6. 分别送入 MTPHead 和 Critic Head

---

## 3. 调用关系图

```
+-------------------------------+
|          AlphaGPT             |
+-------------------------------+
| token_emb: nn.Embedding       |
| pos_emb:   nn.Parameter       |
|                               |
| blocks: LoopedTransformer ----|---+
|                               |   |
| ln_f:   RMSNorm               |   |
| mtp_head: MTPHead             |   |
| head_critic: nn.Linear        |   |
+-------------------------------+   |
        |                           |
        v                           v
+-------------------------------+   +-------------------------------+
|      LoopedTransformer        |   |       LoopedTransformerLayer  |
+-------------------------------+   +-------------------------------+
| layers: [LoopedTransformerLayer]  | qk_norm:   QKNorm             |
|   for layer in layers:            | attention: nn.MultiheadAttn   |
|       x = layer(x, mask)         | norm1:     RMSNorm            |
+-------------------------------+   | norm2:     RMSNorm            |
                                    | ffn:       SwiGLU             |
                                    | dropout:   nn.Dropout         |
                                    +-------------------------------+
                                         |           |
                                         v           v
                                    +---------+  +--------+
                                    | RMSNorm |  | SwiGLU |
                                    +---------+  +--------+
                                    | QKNorm  |
                                    +---------+

+-------------------------------+
|          MTPHead              |
+-------------------------------+
| task_router -> softmax        |
| task_heads[0..2] -> stack     |
| -> 加权融合                    |
+-------------------------------+

--- 与其他模块的交互 ---

  alphagpt.py
       |
       +-- from .config import ModelConfig      --> config.py (使用 MAX_FORMULA_LEN)
       |
       +-- from .ops import OPS_CONFIG          --> ops.py   (使用操作符名构建词汇表)

--- 独立工具类 ---

  NewtonSchulzLowRankDecay    (接收模型 named_parameters，外部调用 step())
  StableRankMonitor           (接收模型实例，外部调用 compute())
```

---

## 4. 依赖关系

### 4.1 外部第三方依赖

| 模块 | 导入方式 | 用途 |
|------|----------|------|
| `torch` | `import torch` | PyTorch 核心库，张量运算 |
| `torch.nn` | `import torch.nn as nn` | 神经网络模块基类和标准层 |
| `torch.nn.functional` | `import torch.nn.functional as F` | 函数式 API（softmax, normalize, silu 等） |

### 4.2 内部模块依赖

| 模块 | 导入方式 | 使用的符号 | 用途 |
|------|----------|------------|------|
| `model_core.config` | `from .config import ModelConfig` | `ModelConfig.MAX_FORMULA_LEN` | 获取公式最大长度配置，用于位置嵌入的维度 |
| `model_core.ops` | `from .ops import OPS_CONFIG` | `OPS_CONFIG` | 获取操作符配置列表，构建模型词汇表 |

---

## 5. 代码逻辑流程

### 5.1 AlphaGPT 前向传播流程

```
输入: idx [B, T] (token 索引序列)
  |
  v
Token Embedding + Position Embedding
  x = token_emb(idx) + pos_emb[:, :T, :]
  |
  v
生成因果掩码 (上三角矩阵)
  mask = generate_square_subsequent_mask(T)
  |
  v
LoopedTransformer 处理
  for each LoopedTransformerLayer:
    for loop in range(num_loops=3):    <-- 层内循环精炼
      x_norm = RMSNorm(x)
      attn_out = MultiheadAttention(x_norm, x_norm, x_norm, mask)
      x = x + Dropout(attn_out)        <-- 残差连接
      x_norm = RMSNorm(x)
      ffn_out = SwiGLU(x_norm)
      x = x + Dropout(ffn_out)         <-- 残差连接
  |
  v
最终 RMSNorm
  x = ln_f(x)
  |
  v
取最后时间步 embedding
  last_emb = x[:, -1, :]
  |
  v
+-- MTPHead(last_emb) --> (logits, task_probs)
|     |
|     +-- task_router(last_emb) -> softmax -> task_probs
|     +-- task_heads[i](last_emb) for i in range(3) -> stack -> 加权求和
|
+-- head_critic(last_emb) --> value
  |
  v
输出: (logits [B, vocab_size], value [B, 1], task_probs [B, 3])
```

### 5.2 Newton-Schulz Low-Rank Decay 流程

```
初始化:
  遍历 named_parameters，筛选 2D + requires_grad + 名称含关键字的参数

step() 每步执行:
  for each (name, W) in params_to_decay:
    X = W.float()
    if rows > cols: X = X.T (转置以提高效率)
    X = X / (||X|| + eps)               <-- 谱范数归一化
    Y = X; I = identity
    for _ in range(num_iterations):     <-- Newton-Schulz 迭代
      A = Y^T @ Y
      Y = 0.5 * Y @ (3I - A)
    if transposed: Y = Y.T
    W -= decay_rate * Y                 <-- 就地低秩衰减
```

### 5.3 Stable Rank 计算流程

```
compute():
  ranks = []
  for name, param in model.named_parameters():
    if param is 2D and name matches keywords:
      S = svdvals(param)                <-- 奇异值分解
      stable_rank = ||S||^2 / S[0]^2   <-- Frobenius^2 / spectral^2
      ranks.append(stable_rank)
  avg_rank = mean(ranks)
  history.append(avg_rank)
  return avg_rank
```
