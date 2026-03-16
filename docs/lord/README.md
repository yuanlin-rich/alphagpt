# lord/experiment 模块文档

## 1. 模块概述

`lord/experiment` 模块是 alphagpt 项目中的一个独立实验模块，用于研究 **低秩衰减（Low-Rank Decay）** 正则化方法对 Transformer 模型 **Grokking 现象** 的影响。

Grokking 是指神经网络在训练集上早已过拟合之后，经过大量额外训练步骤后突然在验证集上实现泛化的现象。该模块以 **模加法（Modular Addition）** 任务（`(a + b) mod 113`）作为实验平台，对比研究两种权重衰减策略：

- **L2 权重衰减（Baseline）**：标准的 AdamW 权重衰减
- **Newton-Schulz 低秩衰减（LowRank）**：基于 Newton-Schulz 迭代的正交投影衰减方法，仅作用于注意力层的 Q/K 投影矩阵

模块提供两种实验模式：
1. **相图实验（Phase Diagram）**：在不同训练数据比例和衰减强度的网格上运行，生成泛化能力的相图热力图
2. **机制分析（Mechanism Analysis）**：深入对比两种方法在单次训练中的行为差异，包括验证准确率曲线、稳定秩演化、奇异值谱和注意力模式可视化

---

## 2. 文件说明

| 文件 | 用途 | 关键内容 |
|------|------|----------|
| `experiment.py` | 模块唯一源文件，包含全部实验逻辑 | Newton-Schulz 低秩衰减优化器、Transformer 模型定义（含 RMSNorm、多头注意力、MLP）、模加法数据集、训练循环、相图实验、机制分析可视化 |

### 文件内部组织结构

`experiment.py` 包含以下主要组成部分：

- **正则化器**：`NewtonSchulzLowRankDecay` 类 -- 核心创新，通过 Newton-Schulz 迭代将权重矩阵向正交矩阵方向衰减
- **模型配置**：`ModelConfig` 数据类 -- 定义模型超参数
- **模型组件**：`RMSNorm`、`Attention`、`Transformer` -- 完整的小型 Transformer 架构
- **数据集**：`ModularAdditionDataset` -- 模加法任务的 PyTorch Dataset 实现
- **工具函数**：`get_stable_rank` -- 计算 Q/K 权重矩阵的稳定秩
- **训练逻辑**：`train_run` -- 单次训练运行的核心函数
- **实验入口**：`run_phase_diagram`、`run_mechanism_analysis` -- 两种实验模式的顶层编排函数
- **CLI 入口**：`__main__` 块 -- 使用 argparse 解析命令行参数

---

## 3. 架构图

```
+------------------------------------------------------------------+
|                      experiment.py                                |
|                                                                   |
|  +--------------------------+   +-----------------------------+   |
|  |     CLI 入口 (__main__)   |   |      ModelConfig (数据类)    |   |
|  |  argparse 参数解析        |   |  vocab_size, dim, depth,    |   |
|  |  --mode: phase_diagram   |   |  heads, mlp_dim, use_qk_norm|   |
|  |        / mechanism       |   +-----------------------------+   |
|  +------+--------+----------+               |                     |
|         |        |                          | 配置                |
|         v        v                          v                     |
|  +------+--+ +---+------------------+  +----+-----+              |
|  | run_    | | run_mechanism_       |  |Transformer|              |
|  | phase_  | | analysis()           |  +----+------+              |
|  | diagram | |                      |       |                     |
|  | ()      | | - 训练L2与LowRank模型 |       | 包含                |
|  +----+----+ | - 绘制5类分析图表     |  +----+------+------+      |
|       |      +----------+-----------+  |    |      |      |      |
|       |                 |              v    v      v      v      |
|       |                 |         Embed  Attn  RMSNorm  MLP     |
|       v                 v              |                         |
|  +----+-----------------+----+         v                         |
|  |       train_run()         |   +----------+                    |
|  | - 构建模型与优化器          |   | Attention|                    |
|  | - 选择 L2 或 LowRank 衰减  |   | - q/k/v/o_proj              |
|  | - 训练循环 + 验证评估       |   | - QK Norm (可选)             |
|  | - 提前停止 (acc>0.99)      |   +----------+                    |
|  +---+-------------------+---+                                   |
|      |                   |                                       |
|      v                   v                                       |
|  +---+--------+  +------+-----------------------+                |
|  | AdamW      |  | NewtonSchulzLowRankDecay     |                |
|  | (标准L2)    |  | - Newton-Schulz 正交迭代      |                |
|  +------------+  | - 仅作用于 2D 参数             |                |
|                  | - 目标: q_proj, k_proj 权重    |                |
|                  +-------------------------------+                |
|                                                                   |
|  +--------------------+   +----------------------------+          |
|  | ModularAddition    |   | get_stable_rank()          |          |
|  | Dataset            |   | - SVD 计算稳定秩            |          |
|  | (a+b) mod p        |   | - 目标: q_proj, k_proj     |          |
|  +--------------------+   +----------------------------+          |
+------------------------------------------------------------------+

调用关系:
  __main__
    |
    +---> run_phase_diagram()
    |       |
    |       +---> train_run() x N  (遍历 fractions x decay_rates 网格)
    |       +---> matplotlib 绘制热力图
    |
    +---> run_mechanism_analysis()
            |
            +---> train_run() x 2  (L2 + LowRank 各一次)
            +---> get_stable_rank() (在 train_run 内部调用)
            +---> matplotlib/seaborn 绘制分析图表
```

---

## 4. 依赖关系

### 4.1 内部模块依赖

`lord/experiment.py` 是一个 **完全自包含** 的模块，不依赖 alphagpt 项目中的任何其他模块（如 `model_core`、`data_pipeline`、`strategy_manager`、`execution`、`dashboard` 等）。所有模型定义、数据集、训练逻辑均在文件内部实现。

### 4.2 外部第三方依赖

| 依赖包 | 导入方式 | 用途 |
|--------|---------|------|
| `numpy` | `import numpy as np` | 数值计算，存储实验结果矩阵 |
| `matplotlib` | `import matplotlib.pyplot as plt` | 绘制相图热力图、训练曲线、奇异值谱等可视化图表 |
| `tqdm` | `from tqdm import tqdm` | 训练进度条显示 |
| `torch` | `import torch` | 深度学习框架核心，张量运算、自动微分 |
| `torch.nn` | `import torch.nn as nn` | 神经网络模块定义（Linear、Embedding、ModuleList 等） |
| `torch.nn.functional` | `import torch.nn.functional as F` | 函数式接口（cross_entropy、normalize、softmax） |
| `torch.utils.data` | `from torch.utils.data import Dataset, DataLoader` | 数据集与数据加载器 |
| `seaborn` | `import seaborn as sns` | 高级统计可视化，用于注意力模式热力图 |

### 4.3 Python 标准库依赖

| 模块 | 用途 |
|------|------|
| `math` | 已导入但未直接使用 |
| `argparse` | 命令行参数解析 |
| `random` | 数据集随机打乱 |
| `copy` | 已导入但未直接使用 |
| `itertools` | 已导入但未直接使用 |
| `dataclasses` | `@dataclass` 装饰器，用于 `ModelConfig` |

---

## 5. 关键类/函数

### 5.1 类

#### `NewtonSchulzLowRankDecay`

核心正则化器。通过 Newton-Schulz 迭代计算权重矩阵的正交近似，然后将权重向该正交方向衰减，从而隐式地降低权重矩阵的有效秩。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `named_parameters` | Iterator | -- | 模型的 `named_parameters()` 迭代器 |
| `decay_rate` | float | `1e-3` | 衰减步长，控制每步向正交矩阵方向移动的幅度 |
| `num_iterations` | int | `5` | Newton-Schulz 迭代次数，越多则正交近似越精确 |
| `target_keywords` | list[str] / None | `None` | 目标参数的关键字过滤列表（如 `["q_proj", "k_proj"]`），仅匹配的 2D 参数会被衰减 |

**核心方法**：
- `step()` -- 无梯度操作，对每个目标参数执行 Newton-Schulz 正交迭代后执行 `W -= decay_rate * Y`

---

#### `ModelConfig`

模型超参数配置的数据类。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `vocab_size` | int | `114` | 词表大小（113 个数字 + 1 个等号 token） |
| `dim` | int | `128` | 模型隐藏维度 |
| `depth` | int | `2` | Transformer 层数 |
| `heads` | int | `4` | 注意力头数 |
| `mlp_dim` | int | `512` | MLP 中间层维度 |
| `use_qk_norm` | bool | `True` | 是否对 Q/K 向量应用 RMSNorm |

---

#### `RMSNorm(nn.Module)`

Root Mean Square 层归一化。

| 参数 | 类型 | 说明 |
|------|------|------|
| `dim` | int | 归一化的维度大小 |

**前向传播**：`F.normalize(x, dim=-1) * scale * g`，其中 `scale = dim ** 0.5`，`g` 为可学习缩放参数。

---

#### `Attention(nn.Module)`

多头自注意力模块，支持可选的 QK 归一化。

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `ModelConfig` | 模型配置对象 |

**内部组件**：`q_proj`、`k_proj`、`v_proj`、`o_proj`（均为无偏置 Linear），以及可选的 `q_norm`、`k_norm`（RMSNorm）。

**前向传播**：标准缩放点积注意力，输入形状 `(B, T, C)`，输出同形。

---

#### `Transformer(nn.Module)`

完整的小型 Transformer 模型，用于序列到分类任务。

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `ModelConfig` | 模型配置对象 |

**结构**：Token Embedding + 可学习位置编码（最大长度 3） -> N 层 [RMSNorm -> Attention -> RMSNorm -> MLP]（残差连接） -> RMSNorm -> Linear Head。

**前向传播**：输入 `(B, T)` 的 token id 张量，输出 `(B, vocab_size)` 的 logits（取最后一个位置的表示进行分类）。

---

#### `ModularAdditionDataset(Dataset)`

模加法任务数据集。生成所有 `(a, b, p, (a+b) mod p)` 组合并按比例划分训练/验证集。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `p` | int | `113` | 模数（素数） |
| `split` | str | `'train'` | 数据划分，`'train'` 或 `'val'` |
| `train_frac` | float | `0.5` | 训练集占比 |
| `seed` | int | `42` | 随机种子，保证可复现 |

**返回**：`(torch.tensor([a, b, p]), torch.tensor((a+b) % p))`

---

### 5.2 函数

#### `get_stable_rank(model) -> float`

计算模型中所有 Q/K 投影矩阵的平均稳定秩。

- **稳定秩定义**：`||W||_F^2 / ||W||_2^2 = sum(sigma_i^2) / max(sigma_i)^2`
- **目标参数**：名称中包含 `q_proj` 或 `k_proj` 的参数
- **返回值**：所有目标参数稳定秩的算术平均值

---

#### `train_run(args, train_frac, decay_type, decay_val, device) -> (float, dict, nn.Module)`

单次训练运行的核心函数。

| 参数 | 类型 | 说明 |
|------|------|------|
| `args` | `argparse.Namespace` | 命令行参数，需包含 `steps` |
| `train_frac` | float | 训练数据比例 |
| `decay_type` | str | 衰减类型，`'L2'` 或 `'LowRank'` |
| `decay_val` | float | 衰减强度 |
| `device` | str | 计算设备（`'cuda'` 或 `'cpu'`） |

**返回值**：
- `max_val_acc` (float) -- 训练过程中的最高验证准确率
- `history` (dict) -- 包含 `step`、`val_acc`、`rank` 三个列表的训练历史
- `model` (nn.Module) -- 训练后的模型

**行为细节**：
- 每 200 步评估一次验证集
- 连续 2 次验证准确率超过 0.99 时提前停止
- L2 模式：所有参数使用相同的 weight_decay
- LowRank 模式：Q/K 参数使用 NewtonSchulzLowRankDecay，其他参数使用 0.1 的温和 L2 衰减

---

#### `run_phase_diagram(args) -> None`

相图实验。在 6 个训练数据比例 `[0.3, 0.4, 0.5, 0.6, 0.7, 0.8]` 和 6 个衰减强度 `[1e-4, 5e-4, 1e-3, 5e-3, 1e-2, 5e-2]` 的 6x6 网格上分别运行 L2 和 LowRank 方法。

- **输出**：`phase_diagram.png` -- 包含两个并排热力图（L2 vs LowRank），颜色编码最终验证准确率
- **注意**：运行时自动将步数设为 2500

---

#### `run_mechanism_analysis(args) -> None`

机制分析实验。以 `train_frac=0.5` 训练两个模型（L2 使用 `decay_val=0.1`，LowRank 使用 `decay_val=0.005`），然后生成综合分析图表。

- **输出**：`mechanism_analysis.png` -- 包含 5 个子图：
  1. Grokking 速度对比（验证准确率 vs 步数）
  2. QK 权重的有效秩演化
  3. Q 投影矩阵的归一化奇异值谱（对数刻度）
  4. L2 模型的注意力模式热力图（token-token 交互）
  5. LowRank 模型的注意力模式热力图

---

### 5.3 命令行接口

```bash
python lord/experiment.py [--mode {phase_diagram,mechanism}] [--steps STEPS] [--device DEVICE]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--mode` | `mechanism` | 实验模式：`phase_diagram`（相图）或 `mechanism`（机制分析） |
| `--steps` | `4000` | 每次训练运行的最大步数 |
| `--device` | 自动检测 | 计算设备，默认有 CUDA 用 `cuda`，否则 `cpu` |
