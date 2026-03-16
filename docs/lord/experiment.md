# experiment.py 文档

> 源文件路径: `lord/experiment.py`

---

## 1. 文件概述

`experiment.py` 是一个独立的实验脚本，用于研究 **Newton-Schulz 低秩正则化（Low-Rank Decay）** 对 Transformer 模型 **Grokking 现象** 的影响。文件以模运算（Modular Addition）作为实验任务，对比了传统 L2 权重衰减与低秩衰减两种正则化方式在泛化速度、注意力矩阵有效秩和奇异值谱等方面的差异。

核心职责：
- 定义一个小型 Transformer 模型（含 RMSNorm、Multi-Head Attention、MLP）
- 实现基于 Newton-Schulz 迭代的低秩正则化优化器
- 提供模运算数据集（ModularAdditionDataset）
- 支持两种实验模式：相图实验（Phase Diagram）和机制分析（Mechanism Analysis）
- 自动生成可视化结果图

---

## 2. 类与函数说明

### 2.1 类

#### `NewtonSchulzLowRankDecay`

低秩正则化优化器，通过 Newton-Schulz 迭代将权重矩阵向其最近的正交矩阵方向衰减，从而降低权重矩阵的有效秩。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__(self, named_parameters, decay_rate, num_iterations, target_keywords)` | `named_parameters`: 模型的命名参数迭代器；`decay_rate`: 衰减率，默认 `1e-3`；`num_iterations`: Newton-Schulz 迭代次数，默认 `5`；`target_keywords`: 目标参数名关键词列表（如 `["q_proj", "k_proj"]`），为 `None` 时作用于所有 2D 参数 | 无 | 初始化时筛选需要衰减的二维参数 |
| `step(self)` | 无 | 无 | 对每个目标参数执行一步低秩衰减：先通过 Newton-Schulz 迭代近似计算矩阵的正交极因子 Y，然后执行 `W -= decay_rate * Y` |

**内部属性：**
- `self.params_to_decay`: 需要进行低秩衰减的参数列表（仅包含 2D、且匹配关键词的 `requires_grad=True` 参数）

---

#### `ModelConfig`（dataclass）

模型超参数配置。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `vocab_size` | `int` | `114` | 词表大小（通常设置为素数 p+1） |
| `dim` | `int` | `128` | 嵌入维度 |
| `depth` | `int` | `2` | Transformer 层数 |
| `heads` | `int` | `4` | 注意力头数 |
| `mlp_dim` | `int` | `512` | MLP 中间层维度 |
| `use_qk_norm` | `bool` | `True` | 是否对 Q/K 使用 RMSNorm |

---

#### `RMSNorm(nn.Module)`

Root Mean Square 归一化层。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__(self, dim)` | `dim`: 特征维度 | 无 | 初始化缩放因子 `scale = dim^0.5` 和可学习参数 `g` |
| `forward(self, x)` | `x`: 输入张量 | 归一化后的张量 | 执行 `F.normalize(x, dim=-1) * scale * g` |

---

#### `Attention(nn.Module)`

多头自注意力模块，支持可选的 QK 归一化。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__(self, config)` | `config`: `ModelConfig` 实例 | 无 | 初始化 Q/K/V/O 投影层及可选的 QK RMSNorm |
| `forward(self, x)` | `x`: 形状 `[B, T, C]` 的输入张量 | 形状 `[B, T, C]` 的输出张量 | 标准多头注意力：Q/K/V 投影 -> 可选 QK norm -> 缩放点积注意力 -> O 投影 |

**内部属性：**
- `self.num_heads`, `self.head_dim`, `self.scale`: 注意力计算参数
- `self.q_proj`, `self.k_proj`, `self.v_proj`, `self.o_proj`: 线性投影层
- `self.q_norm`, `self.k_norm`: QK 归一化层（条件创建）

---

#### `Transformer(nn.Module)`

小型 Transformer 语言模型，用于模运算分类任务。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__(self, config)` | `config`: `ModelConfig` 实例 | 无 | 构建嵌入层、位置编码、多层 Transformer Block（含 RMSNorm + Attention + MLP）、最终层归一化和分类头 |
| `forward(self, x)` | `x`: 形状 `[B, T]` 的 token ID 张量 | 形状 `[B, vocab_size]` 的 logits 张量 | 嵌入 -> 位置编码 -> Transformer 各层 -> 最终 norm -> 取最后一个位置的表示 -> lm_head 输出分类 logits |

**结构细节：**
- 每一层包含 `norm1 -> attn`（残差连接）和 `norm2 -> mlp`（残差连接）
- MLP 使用 SiLU 激活函数
- 位置编码为固定长度 3（对应输入的三个 token：操作数 i、操作数 j、等号符号 p）
- `lm_head` 仅取序列最后一个位置的输出进行分类

---

#### `ModularAdditionDataset(Dataset)`

模运算数据集，生成 `(i + j) % p` 的所有样本，并按指定比例划分训练/验证集。

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `__init__(self, p, split, train_frac, seed)` | `p`: 素数，默认 `113`；`split`: `'train'` 或 `'val'`；`train_frac`: 训练数据比例，默认 `0.5`；`seed`: 随机种子，默认 `42` | 无 | 枚举所有 `p*p` 个样本 `(i, j, p, (i+j)%p)`，随机打乱后按比例分割 |
| `__len__(self)` | 无 | `int` | 返回数据集大小 |
| `__getitem__(self, idx)` | `idx`: 索引 | `(Tensor[3], Tensor[1])` | 返回输入 `[i, j, p]` 和目标 `(i+j)%p` |

---

### 2.2 函数

#### `get_stable_rank(model)`

计算模型中 Q/K 投影矩阵的平均稳定秩（Stable Rank）。

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | `Transformer` | 待分析的模型 |

| 返回值 | 类型 | 说明 |
|--------|------|------|
| 平均稳定秩 | `float` | 所有 Q/K 投影矩阵的稳定秩的平均值。稳定秩 = `||W||_F^2 / ||W||_2^2`，值越小说明矩阵越趋向低秩 |

---

#### `train_run(args, train_frac, decay_type, decay_val, device)`

执行一次完整的训练运行。

| 参数 | 类型 | 说明 |
|------|------|------|
| `args` | `argparse.Namespace` | 命令行参数（含 `steps`） |
| `train_frac` | `float` | 训练数据比例 |
| `decay_type` | `str` | `'L2'` 或 `'LowRank'` |
| `decay_val` | `float` | 衰减强度 |
| `device` | `str` | 计算设备（`'cuda'` 或 `'cpu'`） |

| 返回值 | 类型 | 说明 |
|--------|------|------|
| `max_val_acc` | `float` | 训练过程中的最高验证准确率 |
| `history` | `dict` | 包含 `step`、`val_acc`、`rank` 三个列表的训练历史 |
| `model` | `Transformer` | 训练后的模型 |

**逻辑要点：**
- `decay_type='L2'` 时使用标准 AdamW（全局 weight_decay）
- `decay_type='LowRank'` 时：AdamW 仅对非 Q/K 参数施加 L2 衰减，Q/K 参数由 `NewtonSchulzLowRankDecay` 处理
- 每 200 步评估验证集准确率和稳定秩
- 支持早停：连续两次验证准确率超过 99% 则终止

---

#### `run_phase_diagram(args)`

运行相图实验，系统地扫描不同训练数据比例和衰减强度的组合。

| 参数 | 类型 | 说明 |
|------|------|------|
| `args` | `argparse.Namespace` | 命令行参数 |

| 返回值 | 说明 |
|--------|------|
| 无 | 将结果保存为 `phase_diagram.png` |

**扫描范围：**
- 训练数据比例：`[0.3, 0.4, 0.5, 0.6, 0.7, 0.8]`
- 衰减强度：`[1e-4, 5e-4, 1e-3, 5e-3, 1e-2, 5e-2]`
- L2 的衰减强度会乘以 10 进行尺度对齐

---

#### `run_mechanism_analysis(args)`

运行机制分析实验，对比 L2 与 LowRank 衰减在固定配置下的详细表现。

| 参数 | 类型 | 说明 |
|------|------|------|
| `args` | `argparse.Namespace` | 命令行参数 |

| 返回值 | 说明 |
|--------|------|
| 无 | 将结果保存为 `mechanism_analysis.png` |

**可视化内容（2x4 网格）：**
1. Grokking 速度对比（验证准确率曲线）
2. QK 有效秩演化
3. Q 权重的奇异值谱对比（对数尺度）
4. L2 模型的注意力热力图
5. LowRank 模型的注意力热力图

**内部嵌套函数：**
- `get_svd(model)`: 提取第一层 Q 投影权重的归一化奇异值谱
- `plot_attn(model, ax, title)`: 可视化第一层第 0 号注意力头对所有 token 的注意力矩阵

---

### 2.3 常量

文件未定义模块级常量（超参数封装在 `ModelConfig` dataclass 以及命令行参数中）。

模块级设置：
- `sns.set_theme(style="whitegrid")`: 设置 seaborn 绘图主题

---

## 3. 调用关系图

```
main (__name__ == "__main__")
  |
  +-- argparse.ArgumentParser  (解析 --mode, --steps, --device)
  |
  +-- [mode == 'phase_diagram']
  |     |
  |     +-- run_phase_diagram(args)
  |           |
  |           +-- train_run(args, frac, 'L2', rate*10, device)    x N
  |           |     |
  |           |     +-- ModelConfig()
  |           |     +-- Transformer(config)
  |           |     |     +-- RMSNorm(dim)            x (depth*2 + 1)
  |           |     |     +-- Attention(config)       x depth
  |           |     |           +-- RMSNorm(dim)      (q_norm, k_norm)
  |           |     |
  |           |     +-- torch.optim.AdamW(...)
  |           |     +-- ModularAdditionDataset(...)   x 2 (train, val)
  |           |     +-- DataLoader(...)               x 2
  |           |     +-- get_stable_rank(model)        (每200步)
  |           |
  |           +-- train_run(args, frac, 'LowRank', rate, device)  x N
  |           |     |
  |           |     +-- (同上, 额外创建:)
  |           |     +-- NewtonSchulzLowRankDecay(...)
  |           |           +-- step()                  (每训练步)
  |           |
  |           +-- matplotlib (生成 phase_diagram.png)
  |
  +-- [mode == 'mechanism']
        |
        +-- run_mechanism_analysis(args)
              |
              +-- train_run(args, 0.5, 'L2', 0.1, device)
              +-- train_run(args, 0.5, 'LowRank', 0.005, device)
              |
              +-- get_svd(model_l2)     [内嵌函数]
              +-- get_svd(model_lr)     [内嵌函数]
              +-- plot_attn(model_l2, ...) [内嵌函数]
              +-- plot_attn(model_lr, ...) [内嵌函数]
              |
              +-- matplotlib (生成 mechanism_analysis.png)
```

**与外部模块的交互：**

本文件为独立实验脚本，不依赖 alphagpt 项目中的其他模块。它是一个自包含的研究实验。

---

## 4. 依赖关系

### 4.1 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `numpy` (`np`) | 存储相图实验结果矩阵 |
| `matplotlib.pyplot` (`plt`) | 绘制所有可视化图表 |
| `tqdm` | 训练进度条 |
| `torch` | 核心深度学习框架 |
| `torch.nn` | 神经网络模块（Linear, Embedding, ModuleList 等） |
| `torch.nn.functional` (`F`) | 函数式接口（normalize, cross_entropy, softmax 等） |
| `torch.utils.data` | Dataset 和 DataLoader |
| `seaborn` (`sns`) | 热力图绘制及主题设置 |

### 4.2 Python 标准库依赖

| 模块 | 用途 |
|------|------|
| `math` | 已导入但未直接使用 |
| `argparse` | 命令行参数解析 |
| `random` | 数据集随机打乱 |
| `copy` | 已导入但未直接使用 |
| `itertools` | 已导入但未直接使用 |
| `dataclasses.dataclass` | `ModelConfig` 数据类装饰器 |

### 4.3 内部模块依赖

无。本文件为独立实验脚本，不引用 alphagpt 项目中的其他模块。

---

## 5. 代码逻辑流程

### 5.1 主入口流程

```
1. 解析命令行参数:
   --mode: 'phase_diagram' 或 'mechanism' (默认 'mechanism')
   --steps: 每次训练的步数 (默认 4000)
   --device: 计算设备 (自动检测 cuda/cpu)

2. 根据 mode 分支:
   [phase_diagram] --> run_phase_diagram()
   [mechanism]     --> run_mechanism_analysis()
```

### 5.2 单次训练流程 (`train_run`)

```
1. 创建模型:
   ModelConfig(vocab_size=114, use_qk_norm=True)
   Transformer(config) -> 移至指定设备

2. 配置优化器:
   [L2 模式]
     - AdamW(全部参数, weight_decay=decay_val)
   [LowRank 模式]
     - 将参数分为两组: Q/K 参数 和 其余参数
     - AdamW(其余参数 weight_decay=0.1, Q/K参数 weight_decay=0.0)
     - 创建 NewtonSchulzLowRankDecay(Q/K 参数)

3. 准备数据:
   ModularAdditionDataset(p=113, train/val)
   DataLoader(train: batch=512, val: batch=1024)

4. 训练循环 (共 args.steps 步):
   a. 取一个 mini-batch (循环迭代器)
   b. 前向传播 -> cross_entropy 损失
   c. 反向传播 -> AdamW.step()
   d. [LowRank 模式] -> NewtonSchulzLowRankDecay.step()
   e. 每 200 步:
      - 评估验证集准确率
      - 计算 Q/K 权重的稳定秩
      - 记录历史
      - 若连续 2 次准确率 > 99% 则早停

5. 返回: (最高验证准确率, 训练历史, 模型)
```

### 5.3 Newton-Schulz 低秩衰减 (`NewtonSchulzLowRankDecay.step`)

```
对每个目标权重矩阵 W:
  1. 转换为 float32
  2. 若行数 > 列数, 转置
  3. 归一化: X = W / ||W||
  4. Newton-Schulz 迭代 (5次):
     Y = 0.5 * Y * (3I - Y^T * Y)
     该迭代收敛至 X 的正交极因子 (最近正交矩阵)
  5. 若转置过, 转回
  6. 更新: W -= decay_rate * Y

效果: 将 W 向最近正交矩阵方向推动,
      降低小奇异值, 使权重趋向低秩结构
```

### 5.4 相图实验流程 (`run_phase_diagram`)

```
1. 定义扫描网格:
   训练比例: [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
   衰减强度: [1e-4, 5e-4, 1e-3, 5e-3, 1e-2, 5e-2]
   每次训练 2500 步

2. 双重循环:
   对每个 (比例, 强度) 组合:
     a. train_run(..., 'L2', rate*10)  -> 记录最终准确率
     b. train_run(..., 'LowRank', rate) -> 记录最终准确率

3. 绘制两张热力图 (L2 vs LowRank):
   X 轴: 衰减强度
   Y 轴: 训练数据比例
   颜色: 最终验证准确率 (0~1)

4. 保存为 phase_diagram.png
```

### 5.5 机制分析流程 (`run_mechanism_analysis`)

```
1. 训练两个模型:
   L2 模型:      train_run(frac=0.5, decay='L2', val=0.1)
   LowRank 模型: train_run(frac=0.5, decay='LowRank', val=0.005)

2. 生成 2x4 可视化面板:
   [0,0] 验证准确率曲线对比 (Grokking 速度)
   [0,1] QK 有效秩随训练步数的变化
   [0,2:] Q 权重奇异值谱 (归一化, 对数尺度)
   [1,0:2] L2 模型的注意力热力图 (113x113)
   [1,2:4] LowRank 模型的注意力热力图 (113x113)

3. 注意力热力图的生成过程:
   a. 用所有 0~112 的 token 作为输入
   b. 通过嵌入层 + 位置编码 + 第一层 norm
   c. 计算 Q, K (经 QK norm)
   d. 取第 0 号头, 计算 (Q @ K^T) / sqrt(head_dim)
   e. softmax 后绘制热力图

4. 保存为 mechanism_analysis.png
```
