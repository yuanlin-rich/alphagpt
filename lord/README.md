# lord 模块说明

本模块用于研究与可视化：在小型 Transformer 上，针对模加任务（(i+j) mod p），比较“标准 L2 权重衰减”与“低秩（Low-Rank）衰减”的训练动态与效果（包含相图与机制分析）。

仅包含一个脚本：lord/experiment.py:1，用命令行参数选择两类实验并输出图像文件。

## 功能概览

- 低秩衰减（Newton-Schulz 近似）：lord/experiment.py:18-58
- 模型配置与结构（Transformer + 多头注意力，RMSNorm，SiLU MLP）：lord/experiment.py:60-136
- 模加数据集（序列 [i, j, p] → 标签 (i+j)%p）：lord/experiment.py:138-149
- 训练与度量（验证准确率、Q/K 稳定秩）：lord/experiment.py:150-236
- 相图实验（数据占比 × 衰减强度 网格搜索）：lord/experiment.py:238-273（输出 phase_diagram.png）
- 机制分析（单次详细训练 + 多种可视化）：lord/experiment.py:275-363（输出 mechanism_analysis.png）
- 命令行入口：lord/experiment.py:365-380

## 低秩（Low-Rank）衰减机制

类：NewtonSchulzLowRankDecay（lord/experiment.py:18）

- 目标参数筛选：仅作用于二维参数（权重矩阵），并可按关键词过滤（默认针对 q_proj/k_proj），lord/experiment.py:25-31。
- Newton-Schulz 迭代：对权重矩阵 X 进行归一化后，迭代 Y = 0.5 · Y · (3I − YᵀY)，使 Y 逐步逼近“近似正交”的方向，lord/experiment.py:44-53。
- 更新方式：对原权重执行原地减法 W.sub_(decay_rate · Y)，lord/experiment.py:57。直观地讲，它鼓励 Q/K 投影权重向低秩/更结构化的子空间收缩。

与标准 L2 的关系：
- L2 衰减（基线）：对所有参数统一施加 weight_decay，lord/experiment.py:165-169。
- 低秩衰减（本方法）：对非 Q/K 仍保留轻微 L2（0.1），对 Q/K 不施 L2，而额外施加上述低秩迭代更新，lord/experiment.py:170-181。

## 模型结构与数据集

- 配置：ModelConfig（lord/experiment.py:60-67）
  - vocab_size（默认 114）、dim（128）、depth（2）、heads（4）、mlp_dim（512）、use_qk_norm（True）。
- 归一化：RMSNorm（lord/experiment.py:68-75），使用 F.normalize 并学习缩放参数 g。
- 注意力：Attention（lord/experiment.py:76-107）
  - 线性投影 q/k/v/o，均不含偏置，head_dim=dim/heads，softmax 注意力。
  - 若 use_qk_norm=True，则对 q、k 进行 RMSNorm 归一化，lord/experiment.py:88-99。
- 主干：Transformer（lord/experiment.py:108-136）
  - token embedding + 位置编码（长度 3，lord/experiment.py:113），残差堆叠注意力与 MLP。
  - 输出：仅取最后一个位置的表示并线性到 vocab（lm_head），lord/experiment.py:136。
- 数据集：ModularAdditionDataset（lord/experiment.py:138-149）
  - p=113；样本为三元序列 [i, j, p]，标签为 (i+j)%p；按 train_frac 划分训练/验证。

## 训练流程与度量

- 训练入口：train_run（lord/experiment.py:160-236）
  - 优化器：AdamW，基线使用统一 L2；本方法对 Q/K 停用 L2 并额外施加低秩衰减，lord/experiment.py:165-181。
  - 评估：每 200 步计算一次验证准确率与“稳定秩（Stable Rank）”，lord/experiment.py:210-227。
    - 稳定秩：对 q_proj/k_proj 的奇异值 S，stable_rank = ||S||² / max(S)²，lord/experiment.py:150-158。
  - 早停：验证准确率 > 0.99 连续两次则提前结束，lord/experiment.py:229-234。

## 实验模式

1) 相图（Phase Diagram）：run_phase_diagram（lord/experiment.py:238-273）
   - 网格：训练数据占比（0.3~0.8） × 衰减强度（1e−4~5e−2，对 L2 额外 ×10），lord/experiment.py:240-255。
   - 输出：两幅热图（L2 与 LowRank 的验证准确率），保存为 phase_diagram.png，lord/experiment.py:257-273。

2) 机制分析（Mechanism Analysis）：run_mechanism_analysis（lord/experiment.py:275-363）
   - 训练：分别跑基线（L2）与本方法（LowRank），lord/experiment.py:279-283。
   - 可视化：
     - 验证准确率随步数（Grokking Speed），lord/experiment.py:289-297。
     - Q/K 稳定秩演化，lord/experiment.py:298-305。
     - 第一层 q_proj 的奇异值谱（归一化，对数刻度），lord/experiment.py:306-320。
     - 头 0 的注意力模式热力图（“Noisy” vs “Structured” 标注），lord/experiment.py:322-359。
   - 输出：mechanism_analysis.png，lord/experiment.py:361-363。

## 使用方法

- 直接运行脚本：
  - mechanism（默认）：
    ```
    python lord/experiment.py --mode mechanism --steps 4000
    ```
  - 相图：
    ```
    python lord/experiment.py --mode phase_diagram --steps 2500
    ```
- 或以模块方式运行（若 Python 版本支持隐式命名空间包）：
  ```
  python -m lord.experiment --mode mechanism
  ```

参数说明：
- --mode：phase_diagram 或 mechanism（默认 mechanism），lord/experiment.py:367-369。
- --steps：单次训练步数（默认 4000；相图模式内部会降到 2500），lord/experiment.py:369, 377。
- --device：cuda 或 cpu（默认自动探测），lord/experiment.py:370。

## 依赖与环境

- 主要依赖：PyTorch、NumPy、matplotlib、seaborn、tqdm。
- 建议使用带 GPU 的环境（可显著加速）。
- 运行会在当前目录生成图像文件（phase_diagram.png、mechanism_analysis.png）。

## 备注

- 该模块为独立实验脚本，未与数据管线（data_pipeline）直接集成。
- 图表标题中的“Noisy/Structured”为作者在代码中用于区分两种注意力模式的命名，具体效果以训练结果为准。