# engine.py 文档

> 源码路径: `model_core/engine.py`

---

## 1. 文件概述

`engine.py` 是 AlphaGPT 项目的**训练引擎核心模块**。它将数据加载、模型构建、强化学习训练循环、公式执行与回测评估等环节串联成一个完整的训练流水线。该文件定义了 `AlphaEngine` 类，负责：

- 初始化数据加载器（`CryptoDataLoader`）并加载链上 OHLCV 数据
- 构建 AlphaGPT 模型并配置优化器（AdamW）
- 可选地启用 Low-Rank Decay (LoRD) 正则化以及稳定秩监控
- 使用 REINFORCE 策略梯度算法训练模型，自动采样公式 token 序列
- 通过 StackVM 虚拟机执行公式，使用 MemeBacktest 进行回测评分
- 记录训练历史并保存最优策略公式

该文件同时包含 `__main__` 入口，可直接运行以启动训练。

---

## 2. 类与函数说明

### 2.1 类 `AlphaEngine`

训练引擎的主类，封装了整个 Alpha 因子挖掘的训练流程。

#### 2.1.1 `__init__(self, use_lord_regularization=True, lord_decay_rate=1e-3, lord_num_iterations=5)`

**构造函数**，初始化引擎所有组件。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_lord_regularization` | `bool` | `True` | 是否启用 Low-Rank Decay (LoRD) 正则化 |
| `lord_decay_rate` | `float` | `1e-3` | LoRD 正则化强度 |
| `lord_num_iterations` | `int` | `5` | Newton-Schulz 迭代次数 |

**内部初始化的属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.loader` | `CryptoDataLoader` | 数据加载器实例，初始化后立即调用 `load_data()` |
| `self.model` | `AlphaGPT` | AlphaGPT 模型，自动迁移到配置设备 |
| `self.opt` | `torch.optim.AdamW` | AdamW 优化器，学习率 `1e-3` |
| `self.use_lord` | `bool` | LoRD 开关标志 |
| `self.lord_opt` | `NewtonSchulzLowRankDecay` 或 `None` | LoRD 正则化器 |
| `self.rank_monitor` | `StableRankMonitor` 或 `None` | 稳定秩监控器 |
| `self.vm` | `StackVM` | 公式执行虚拟机 |
| `self.bt` | `MemeBacktest` | 回测评估器 |
| `self.best_score` | `float` | 当前最佳分数，初始为 `-inf` |
| `self.best_formula` | `list` 或 `None` | 当前最佳公式 token 列表 |
| `self.training_history` | `dict` | 训练历史记录字典，包含 `step`、`avg_reward`、`best_score`、`stable_rank` 四个列表 |

#### 2.1.2 `train(self)`

**核心训练方法**，执行完整的 REINFORCE 策略梯度训练循环。

- **参数**: 无
- **返回值**: 无（副作用：保存文件、打印结果）

**训练流程详细说明：**

1. 对每个训练步（共 `ModelConfig.TRAIN_STEPS` 步）：
   - 创建批量输入张量 `inp`（全零，shape `[BATCH_SIZE, 1]`）
   - 自回归采样 `MAX_FORMULA_LEN` 个 token：每一步通过模型获取 logits，构建 Categorical 分布并采样 action
   - 对批次中每个样本：
     - 使用 `StackVM.execute()` 执行公式
     - 执行失败返回 `None` 奖励 `-5.0`，标准差过低奖励 `-2.0`
     - 成功则使用 `MemeBacktest.evaluate()` 获取评分
   - 计算优势函数（标准化奖励）
   - 计算 REINFORCE 策略梯度损失
   - 执行梯度更新（AdamW）
   - 可选执行 LoRD 正则化步
   - 每 100 步计算并记录稳定秩
2. 训练结束后保存 `best_meme_strategy.json` 和 `training_history.json`

### 2.2 `__main__` 入口

```python
if __name__ == "__main__":
    eng = AlphaEngine(use_lord_regularization=True)
    eng.train()
```

直接运行该文件时，创建启用 LoRD 的引擎实例并启动训练。

---

## 3. 调用关系图

```
+-------------------------------------------------------------------+
|                         engine.py                                 |
|                                                                   |
|  AlphaEngine                                                      |
|  +-------------------------------------------------------------+ |
|  | __init__()                                                   | |
|  |   |                                                          | |
|  |   +---> CryptoDataLoader()          [data_loader.py]         | |
|  |   |       +---> .load_data()                                 | |
|  |   +---> AlphaGPT()                  [alphagpt.py]            | |
|  |   +---> torch.optim.AdamW()         [PyTorch]                | |
|  |   +---> NewtonSchulzLowRankDecay()  [alphagpt.py]            | |
|  |   +---> StableRankMonitor()         [alphagpt.py]            | |
|  |   +---> StackVM()                   [vm.py]                  | |
|  |   +---> MemeBacktest()              [backtest.py]            | |
|  +-------------------------------------------------------------+ |
|  | train()                                                      | |
|  |   |                                                          | |
|  |   +---> self.model(inp)             AlphaGPT.forward()       | |
|  |   |       返回 (logits, value, task_probs)                    | |
|  |   +---> Categorical(logits).sample() [torch.distributions]   | |
|  |   +---> self.vm.execute(formula, feat_tensor)  [vm.py]       | |
|  |   +---> self.bt.evaluate(res, raw_data, target_ret)          | |
|  |   |                                  [backtest.py]           | |
|  |   +---> self.opt.step()             AdamW 优化器更新           | |
|  |   +---> self.lord_opt.step()        LoRD 正则化步              | |
|  |   +---> self.rank_monitor.compute() 稳定秩计算                 | |
|  |   +---> json.dump(...)              保存最佳公式与训练历史      | |
|  +-------------------------------------------------------------+ |
+-------------------------------------------------------------------+
```

### 与其他模块的交互

```
                    +-------------+
                    | config.py   |
                    | ModelConfig |
                    +------+------+
                           |
          +----------------+----------------+
          |                |                |
+---------v----+  +--------v-------+  +-----v--------+
| data_loader  |  |   alphagpt.py  |  |  engine.py   |
| .py          |  |  AlphaGPT      |  |  AlphaEngine |
| CryptoData   |  |  LoRD / Monitor|  +-----+--------+
| Loader       |  +----------------+        |
+--------------+                            |
                            +---------------+---------------+
                            |                               |
                      +-----v------+                 +------v-----+
                      |   vm.py    |                 | backtest.py|
                      |  StackVM   |                 | MemeBack   |
                      +-----+------+                 | test       |
                            |                        +------------+
                      +-----v------+
                      |  ops.py    |
                      | OPS_CONFIG |
                      +------------+
```

---

## 4. 依赖关系

### 4.1 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `torch` | 张量运算、自动微分、优化器 |
| `torch.distributions.Categorical` | 构建离散分布用于策略采样 |
| `tqdm` | 训练进度条显示 |
| `json` | JSON 序列化，保存最佳公式和训练历史 |

### 4.2 内部模块依赖（alphagpt 项目内）

| 模块 | 导入对象 | 用途 |
|------|----------|------|
| `.config` | `ModelConfig` | 全局配置（设备、批大小、训练步数、公式最大长度等） |
| `.data_loader` | `CryptoDataLoader` | 从数据库加载加密货币 OHLCV 数据并计算特征张量 |
| `.alphagpt` | `AlphaGPT` | Transformer 模型，用于生成公式 token 序列 |
| `.alphagpt` | `NewtonSchulzLowRankDecay` | 基于 Newton-Schulz 迭代的低秩衰减正则化 |
| `.alphagpt` | `StableRankMonitor` | 监控模型参数的稳定秩 |
| `.vm` | `StackVM` | 基于栈的虚拟机，执行 token 序列形式的因子公式 |
| `.backtest` | `MemeBacktest` | Meme 币回测评估器，计算策略的适应度分数 |

---

## 5. 代码逻辑流程

### 5.1 初始化流程

```
AlphaEngine.__init__()
    |
    v
加载数据: CryptoDataLoader().load_data()
    |  从 PostgreSQL 读取 OHLCV 数据
    |  计算 6 维特征张量 feat_tensor
    |  计算目标收益率 target_ret
    |
    v
构建模型: AlphaGPT().to(DEVICE)
    |
    v
配置优化器: AdamW(lr=1e-3)
    |
    v
[如果启用 LoRD]
    +---> 构建 NewtonSchulzLowRankDecay (目标关键词: q_proj, k_proj, attention, qk_norm)
    +---> 构建 StableRankMonitor (目标关键词: q_proj, k_proj)
    |
    v
构建辅助模块: StackVM() + MemeBacktest()
    |
    v
初始化记录变量: best_score=-inf, best_formula=None, training_history={}
```

### 5.2 训练循环流程

```
train()
    |
    v
FOR step in range(TRAIN_STEPS=1000):
    |
    +---> 创建零初始输入 inp: [BATCH_SIZE, 1]
    |
    +---> FOR t in range(MAX_FORMULA_LEN=12):  <-- 自回归采样
    |       |
    |       +---> logits, _, _ = model(inp)    <-- AlphaGPT 前向传播
    |       +---> dist = Categorical(logits)
    |       +---> action = dist.sample()       <-- 采样 token
    |       +---> 记录 log_prob, 拼接 action 到 inp
    |
    +---> 构建 seqs: [BATCH_SIZE, MAX_FORMULA_LEN]
    |
    +---> FOR i in range(BATCH_SIZE):          <-- 逐样本评估
    |       |
    |       +---> formula = seqs[i].tolist()
    |       +---> res = vm.execute(formula, feat_tensor)
    |       |
    |       +---> IF res is None:     奖励 = -5.0  (执行失败)
    |       +---> IF res.std() < 1e-4: 奖励 = -2.0  (无差异信号)
    |       +---> ELSE:
    |       |       score, ret = bt.evaluate(res, raw_data, target_ret)
    |       |       奖励 = score
    |       |       IF score > best_score: 更新最佳公式
    |
    +---> 计算优势: adv = (rewards - mean) / (std + 1e-5)
    |
    +---> 计算策略梯度损失: loss = mean(-log_prob * adv)
    |
    +---> opt.zero_grad() -> loss.backward() -> opt.step()
    |
    +---> [LoRD] lord_opt.step()   <-- 低秩衰减正则化
    |
    +---> [每100步] rank_monitor.compute()  <-- 计算稳定秩
    |
    +---> 更新进度条 & 记录 training_history
    |
    v
保存 best_meme_strategy.json   <-- 最佳公式
保存 training_history.json     <-- 训练历史
打印最终结果
```

### 5.3 奖励设计

| 情况 | 奖励值 | 说明 |
|------|--------|------|
| 公式执行失败 (`res is None`) | -5.0 | 语法错误或栈不平衡 |
| 信号无差异 (`res.std() < 1e-4`) | -2.0 | 生成的因子没有区分度 |
| 正常执行 | `bt.evaluate()` 返回的 `score` | 基于回测的适应度评分 |
