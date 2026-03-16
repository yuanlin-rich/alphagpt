# backtest.py 文档

## 1. 文件概述

`backtest.py` 是 AlphaGPT 项目的回测引擎模块，负责对模型生成的交易因子进行模拟回测评估。该文件实现了一个面向 **Meme 币（高波动加密货币）** 的回测框架，核心功能包括：

- 基于因子信号生成仓位
- 考虑流动性过滤、滑点冲击、交易费用
- 计算净 PnL（盈亏）并评估策略表现
- 通过复合评分机制（累计收益 - 大幅回撤惩罚 - 低活跃度惩罚）输出最终适应度分数

该模块完全基于 PyTorch 张量运算实现，支持 GPU 加速和自动微分，使其可以直接作为强化学习训练循环中的奖励函数。

---

## 2. 类与函数说明

### 2.1 `MemeBacktest`

Meme 币交易策略回测器。

**构造函数参数：** 无

**实例属性（常量）：**

| 属性 | 类型 | 值 | 说明 |
|------|------|-----|------|
| `trade_size` | float | `1000.0` | 每笔交易金额（美元） |
| `min_liq` | float | `500000.0` | 最低流动性阈值（美元），低于此值的标的被过滤 |
| `base_fee` | float | `0.0060` | 基础交易费率（0.6%，包含 Swap + Gas + 其他费用） |

**方法：**

#### `evaluate(factors, raw_data, target_ret) -> tuple[Tensor, float]`

执行完整的回测评估流程。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `factors` | Tensor | 形状 `(N, T)` 的因子值张量，N 为标的数量，T 为时间步数 |
| `raw_data` | dict[str, Tensor] | 原始市场数据字典，必须包含 `'liquidity'` 键 |
| `target_ret` | Tensor | 形状 `(N, T)` 的目标收益率张量（未来收益） |

**返回值：**

| 返回值 | 类型 | 说明 |
|--------|------|------|
| `final_fitness` | Tensor (标量) | 所有标的评分的中位数，作为策略的最终适应度 |
| `cum_ret_mean` | float | 所有标的累计收益的平均值（Python float） |

---

## 3. 调用关系图

```
+----------------------------------+
|          MemeBacktest            |
+----------------------------------+
| trade_size = 1000.0              |
| min_liq    = 500000.0            |
| base_fee   = 0.0060              |
+----------------------------------+
|                                  |
| evaluate(factors, raw_data,      |
|          target_ret)             |
|   |                              |
|   +-- torch.sigmoid(factors)     |  <-- 信号归一化到 [0,1]
|   +-- 流动性过滤 (is_safe)       |
|   +-- 仓位生成 (signal > 0.85)   |
|   +-- 冲击滑点计算               |
|   +-- 换手率计算 (turnover)      |
|   +-- 交易成本计算 (tx_cost)     |
|   +-- 净盈亏 (net_pnl)          |
|   +-- 评分 (score)              |
|   +-- 最终适应度 (median)        |
+----------------------------------+

--- 与其他模块的交互 ---

  backtest.py 不直接 import 其他内部模块。

  它被 engine.py (训练引擎) 和 vm.py (虚拟机) 等模块调用：

  engine.py / vm.py
       |
       +-- MemeBacktest.evaluate(factors, raw_data, target_ret)
       |       ^                    ^                ^
       |       |                    |                |
       |    因子计算结果         data_loader        data_loader
       |    (vm.py 执行)        提供的原始数据     提供的目标收益
       v
    得到 fitness 用于训练奖励
```

---

## 4. 依赖关系

### 4.1 外部第三方依赖

| 模块 | 导入方式 | 用途 |
|------|----------|------|
| `torch` | `import torch` | PyTorch 核心库，所有张量运算均基于此 |

### 4.2 内部模块依赖

无。`backtest.py` 不导入任何项目内部模块，是一个完全独立的功能模块。

---

## 5. 代码逻辑流程

### 5.1 `evaluate()` 方法的完整执行流程

```
输入:
  factors    [N, T]  -- 模型生成的因子值
  raw_data   dict    -- 包含 'liquidity' 等原始数据
  target_ret [N, T]  -- 未来收益率

Step 1: 信号生成
  |
  +-- signal = sigmoid(factors)          -- 将因子值映射到 [0, 1]
  +-- is_safe = (liquidity > 500000)     -- 流动性安全过滤
  +-- position = (signal > 0.85) * is_safe  -- 仅在高信号 + 高流动性时持仓
  |
  v
Step 2: 交易成本计算
  |
  +-- impact_slippage = trade_size / (liquidity + eps)  -- 市场冲击
  +-- impact_slippage = clamp(impact_slippage, 0, 0.05) -- 上限 5%
  +-- total_slippage = base_fee + impact_slippage        -- 总滑点
  |
  v
Step 3: 换手率计算
  |
  +-- prev_pos = roll(position, 1)       -- 上一时间步的仓位
  +-- prev_pos[:, 0] = 0                 -- 第一步无历史仓位
  +-- turnover = |position - prev_pos|   -- 仓位变化的绝对值
  |
  v
Step 4: 净盈亏计算
  |
  +-- tx_cost = turnover * total_slippage  -- 交易成本 = 换手 * 滑点
  +-- gross_pnl = position * target_ret    -- 毛盈亏 = 仓位 * 收益率
  +-- net_pnl = gross_pnl - tx_cost        -- 净盈亏 = 毛盈亏 - 成本
  |
  v
Step 5: 评分计算
  |
  +-- cum_ret = net_pnl.sum(dim=1)         -- 每个标的的累计收益 [N]
  +-- big_drawdowns = count(net_pnl < -5%) -- 大幅亏损次数 [N]
  +-- score = cum_ret - big_drawdowns * 2   -- 惩罚大回撤
  |
  v
Step 6: 活跃度过滤
  |
  +-- activity = position.sum(dim=1)       -- 每个标的的持仓时间步数
  +-- if activity < 5: score = -10         -- 过于不活跃的策略直接惩罚
  |
  v
Step 7: 最终输出
  |
  +-- final_fitness = median(score)        -- 取中位数（鲁棒评估）
  +-- cum_ret_mean = mean(cum_ret)         -- 平均累计收益（辅助指标）
  |
  v
返回: (final_fitness, cum_ret_mean)
```

### 5.2 关键设计决策说明

1. **sigmoid 阈值 0.85**：仅在高置信度时开仓，避免噪声信号导致频繁交易。
2. **流动性过滤**：Meme 币流动性差异极大，低流动性标的无法实际交易。
3. **冲击滑点模型**：`trade_size / liquidity` 简化但有效地建模了市场冲击。
4. **中位数评分**：使用 `median` 而非 `mean`，对极端异常值更鲁棒。
5. **活跃度惩罚**：防止模型学到"不交易"的退化策略。
6. **大回撤惩罚**：`big_drawdowns * 2` 显著惩罚单步亏损超过 5% 的情况，鼓励风险控制。
