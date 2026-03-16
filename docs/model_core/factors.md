# factors.py 文档

> 源码路径: `model_core/factors.py`

---

## 1. 文件概述

`factors.py` 是 AlphaGPT 项目的**因子工程模块**，负责将原始的 OHLCV（开盘价、最高价、最低价、收盘价、成交量）及链上数据（流动性、FDV）转换为可供模型和虚拟机使用的因子特征张量。该文件定义了三个核心组件：

- **`RMSNormFactor`**: 基于均方根的因子归一化层（PyTorch `nn.Module`）
- **`MemeIndicators`**: 静态工具类，包含多种针对 Meme 币特征设计的技术指标计算方法
- **`AdvancedFactorEngineer`**: 高级因子工程类，生成 12 维特征空间
- **`FeatureEngineer`**: 基础因子工程类，生成 6 维特征空间（当前训练流水线的实际入口）

该模块是数据层与模型层之间的桥梁，所有原始数据在进入 StackVM 虚拟机之前都需要经过此模块的特征工程处理。

---

## 2. 类与函数说明

### 2.1 类 `RMSNormFactor(nn.Module)`

基于 Root Mean Square 的因子归一化层。

#### `__init__(self, d_model, eps=1e-6)`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `d_model` | `int` | - | 归一化维度大小 |
| `eps` | `float` | `1e-6` | 防止除零的小常数 |

**可学习参数：**
- `self.weight`: `nn.Parameter`，形状 `(d_model,)`，初始化为全 1

#### `forward(self, x)`

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | `torch.Tensor` | 输入张量 |

- **返回值**: `torch.Tensor`，归一化后的张量
- **计算公式**: `(x / RMS(x)) * weight`，其中 `RMS(x) = sqrt(mean(x^2) + eps)`

---

### 2.2 类 `MemeIndicators`

纯静态工具类，无需实例化。包含针对 Meme 币市场特征设计的技术指标。所有方法均操作 `torch.Tensor`，维度约定为 `[tokens, time_steps]`。

#### 2.2.1 `liquidity_health(liquidity, fdv)` (staticmethod)

**流动性健康度**指标。衡量流动性与完全稀释估值的比率。

| 参数 | 类型 | 说明 |
|------|------|------|
| `liquidity` | `torch.Tensor` | 流动性张量 `[N, T]` |
| `fdv` | `torch.Tensor` | 完全稀释估值张量 `[N, T]` |

- **返回值**: `torch.Tensor`，范围 `[0.0, 1.0]`
- **计算**: `clamp(liquidity / (fdv + 1e-6) * 4.0, 0, 1)`

#### 2.2.2 `buy_sell_imbalance(close, open_, high, low)` (staticmethod)

**买卖力量失衡**指标。通过 K 线实体与影线的比例衡量多空力量。

| 参数 | 类型 | 说明 |
|------|------|------|
| `close` | `torch.Tensor` | 收盘价 `[N, T]` |
| `open_` | `torch.Tensor` | 开盘价 `[N, T]` |
| `high` | `torch.Tensor` | 最高价 `[N, T]` |
| `low` | `torch.Tensor` | 最低价 `[N, T]` |

- **返回值**: `torch.Tensor`，范围 `(-1.0, 1.0)`（经 `tanh` 压缩）
- **计算**: `tanh((close - open) / (high - low + 1e-9) * 3.0)`

#### 2.2.3 `fomo_acceleration(volume, window=5)` (staticmethod)

**FOMO 加速度**指标。衡量成交量变化的加速度（二阶导数）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `volume` | `torch.Tensor` | - | 成交量 `[N, T]` |
| `window` | `int` | `5` | 未直接使用（保留参数） |

- **返回值**: `torch.Tensor`，范围 `[-5.0, 5.0]`（经 `clamp` 截断）
- **计算**: 成交量变化率的差分（加速度）

#### 2.2.4 `pump_deviation(close, window=20)` (staticmethod)

**泵升偏离度**指标。衡量当前价格偏离移动平均线的程度。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `close` | `torch.Tensor` | - | 收盘价 `[N, T]` |
| `window` | `int` | `20` | 移动平均窗口 |

- **返回值**: `torch.Tensor`，`(close - MA) / (MA + 1e-9)`
- **实现细节**: 使用零填充 + `unfold` 实现滑动窗口均值

#### 2.2.5 `volatility_clustering(close, window=10)` (staticmethod)

**波动率聚类**指标。检测波动率是否存在时间聚类效应。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `close` | `torch.Tensor` | - | 收盘价 `[N, T]` |
| `window` | `int` | `10` | 波动率计算窗口 |

- **返回值**: `torch.Tensor`，`sqrt(mean(log_return^2) + 1e-9)`
- **计算**: 对数收益率平方的滑动窗口均值开根号（即已实现波动率的近似）

#### 2.2.6 `momentum_reversal(close, window=5)` (staticmethod)

**动量反转**指标。检测动量方向发生反转的时间点。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `close` | `torch.Tensor` | - | 收盘价 `[N, T]` |
| `window` | `int` | `5` | 动量累积窗口 |

- **返回值**: `torch.Tensor`，值为 `0.0` 或 `1.0`（二值信号）
- **计算**: 当前窗口动量与前一期动量符号相反时为 `1.0`

#### 2.2.7 `relative_strength(close, high, low, window=14)` (staticmethod)

**相对强弱**指标（类 RSI）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `close` | `torch.Tensor` | - | 收盘价 `[N, T]` |
| `high` | `torch.Tensor` | - | 最高价 `[N, T]` |
| `low` | `torch.Tensor` | - | 最低价 `[N, T]` |
| `window` | `int` | `14` | RSI 计算窗口 |

- **返回值**: `torch.Tensor`，范围 `[-1.0, 1.0]`（归一化后的 RSI）
- **计算**: 标准 RSI 公式，最后归一化为 `(RSI - 50) / 50`

---

### 2.3 类 `AdvancedFactorEngineer`

高级特征工程类，生成 12 维特征空间。

#### `__init__(self)`

初始化 `self.rms_norm = RMSNormFactor(1)` 归一化层。

#### `robust_norm(self, t)`

**鲁棒归一化**方法。使用中位数绝对偏差（MAD）替代标准差，对异常值更鲁棒。

| 参数 | 类型 | 说明 |
|------|------|------|
| `t` | `torch.Tensor` | 输入张量 `[N, T]` |

- **返回值**: `torch.Tensor`，范围 `[-5.0, 5.0]`
- **计算**: `clamp((t - median) / (MAD + 1e-6), -5, 5)`

#### `compute_advanced_features(self, raw_dict)`

计算 12 维高级特征向量。

| 参数 | 类型 | 说明 |
|------|------|------|
| `raw_dict` | `dict[str, torch.Tensor]` | 原始数据字典，键为 `close/open/high/low/volume/liquidity/fdv` |

- **返回值**: `torch.Tensor`，形状 `[N, 12, T]`

**12 维特征列表：**

| 维度 | 因子名称 | 归一化方式 |
|------|----------|------------|
| 0 | 对数收益率 (ret) | robust_norm |
| 1 | 流动性健康度 (liq_score) | 原始 [0,1] |
| 2 | 买卖压力 (pressure) | 原始 tanh |
| 3 | FOMO 加速度 (fomo) | robust_norm |
| 4 | 泵升偏离度 (dev) | robust_norm |
| 5 | 对数成交量 (log_vol) | robust_norm |
| 6 | 波动率聚类 (vol_cluster) | robust_norm |
| 7 | 动量反转 (momentum_rev) | 原始 {0,1} |
| 8 | 相对强弱 (rel_strength) | robust_norm |
| 9 | 高低价振幅 (hl_range) | robust_norm |
| 10 | 收盘价在区间中的位置 (close_pos) | 原始 [0,1] |
| 11 | 成交量趋势 (vol_trend) | robust_norm |

---

### 2.4 类 `FeatureEngineer`

基础特征工程类（当前训练流水线实际使用的版本），生成 6 维特征空间。

#### 常量 `INPUT_DIM = 6`

特征维度数，被 `vm.py` 中的 `StackVM` 用作特征偏移量。

#### `compute_features(raw_dict)` (staticmethod)

计算 6 维基础特征向量。

| 参数 | 类型 | 说明 |
|------|------|------|
| `raw_dict` | `dict[str, torch.Tensor]` | 原始数据字典 |

- **返回值**: `torch.Tensor`，形状 `[N, 6, T]`

**6 维特征列表：**

| 维度 | 因子名称 | 归一化方式 |
|------|----------|------------|
| 0 | 对数收益率 (ret) | robust_norm（内嵌函数） |
| 1 | 流动性健康度 (liq_score) | 原始 [0,1] |
| 2 | 买卖压力 (pressure) | 原始 tanh |
| 3 | FOMO 加速度 (fomo) | robust_norm |
| 4 | 泵升偏离度 (dev) | robust_norm |
| 5 | 对数成交量 (log_vol) | robust_norm |

**内嵌函数 `robust_norm(t)`**: 与 `AdvancedFactorEngineer.robust_norm()` 逻辑相同，使用 MAD 进行鲁棒归一化。

---

## 3. 调用关系图

### 文件内部调用关系

```
+-------------------------------------------------------------------+
|                        factors.py                                 |
|                                                                   |
|  RMSNormFactor                                                    |
|  +---> forward(x)           被 AdvancedFactorEngineer 使用         |
|                                                                   |
|  MemeIndicators (静态方法集合)                                      |
|  +---> liquidity_health()  <---+                                  |
|  +---> buy_sell_imbalance() <--+                                  |
|  +---> fomo_acceleration()  <--+-- FeatureEngineer.compute_       |
|  +---> pump_deviation()     <--+   features() 调用                |
|  +---> volatility_clustering() <-+                                |
|  +---> momentum_reversal()   <---+-- AdvancedFactorEngineer.      |
|  +---> relative_strength()   <---+   compute_advanced_features()  |
|                                                                   |
|  AdvancedFactorEngineer                                           |
|  +---> __init__()                                                 |
|  |       +---> RMSNormFactor(1)                                   |
|  +---> robust_norm(t)                                             |
|  +---> compute_advanced_features(raw_dict)                        |
|          +---> MemeIndicators.*() (多个静态方法)                     |
|          +---> self.robust_norm() (多次调用)                        |
|                                                                   |
|  FeatureEngineer                                                  |
|  +---> compute_features(raw_dict)   [staticmethod]                |
|          +---> MemeIndicators.liquidity_health()                  |
|          +---> MemeIndicators.buy_sell_imbalance()                 |
|          +---> MemeIndicators.fomo_acceleration()                  |
|          +---> MemeIndicators.pump_deviation()                     |
|          +---> robust_norm() (内嵌函数)                             |
+-------------------------------------------------------------------+
```

### 与其他模块的交互

```
+----------------+       +------------------+       +-----------+
| data_loader.py |------>|   factors.py     |<------| vm.py     |
| CryptoData     |       |  FeatureEngineer |       | StackVM   |
| Loader         |       |  .compute_       |       | 读取      |
| 调用 compute_  |       |  features()      |       | INPUT_DIM |
| features()     |       +------------------+       +-----------+
+----------------+
```

---

## 4. 依赖关系

### 4.1 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `torch` | 张量运算（数学计算、滑动窗口、clamp、tanh 等） |
| `torch.nn` | `nn.Module`（`RMSNormFactor`）、`nn.Parameter` |

### 4.2 内部模块依赖

该文件**没有**导入其他内部模块，是一个相对独立的叶子模块。

### 4.3 被其他模块依赖

| 依赖方模块 | 导入对象 | 用途 |
|-----------|----------|------|
| `data_loader.py` | `FeatureEngineer` | 调用 `compute_features()` 生成特征张量 |
| `vm.py` | `FeatureEngineer` | 读取 `INPUT_DIM` 常量用于 token 偏移量计算 |

---

## 5. 代码逻辑流程

### 5.1 FeatureEngineer.compute_features() 流程（当前主流水线使用）

```
输入: raw_dict = {close, open, high, low, volume, liquidity, fdv}
         |
         v
1. 计算对数收益率: ret = log(close / roll(close, 1))
         |
         v
2. 计算流动性健康度: liq_score = clamp(liq/fdv * 4, 0, 1)
         |
         v
3. 计算买卖压力: pressure = tanh((close-open)/(high-low) * 3)
         |
         v
4. 计算 FOMO 加速度: fomo = 成交量变化率的二阶差分
         |
         v
5. 计算泵升偏离度: dev = (close - MA20) / MA20
         |
         v
6. 计算对数成交量: log_vol = log1p(volume)
         |
         v
7. 对需要归一化的因子应用 robust_norm():
   - 计算每行中位数 median
   - 计算中位数绝对偏差 MAD
   - norm = clamp((x - median) / (MAD + 1e-6), -5, 5)
         |
         v
8. stack 6 个因子 -> 输出: [N, 6, T]
```

### 5.2 AdvancedFactorEngineer.compute_advanced_features() 流程

```
输入: raw_dict = {close, open, high, low, volume, liquidity, fdv}
         |
         v
1. 计算基础 6 因子 (同 FeatureEngineer)
         |
         v
2. 额外计算高级因子:
   - volatility_clustering: 已实现波动率 (滑动窗口 10)
   - momentum_reversal: 动量反转信号 (窗口 5)
   - relative_strength: RSI 类指标 (窗口 14)
   - hl_range: (high - low) / close
   - close_pos: (close - low) / (high - low)
   - vol_trend: 成交量变化率
         |
         v
3. 对需要归一化的因子应用 robust_norm()
         |
         v
4. stack 12 个因子 -> 输出: [N, 12, T]
```

### 5.3 滑动窗口计算模式

该文件中多个指标使用统一的滑动窗口计算模式：

```
1. 零填充: pad = zeros([N, window-1])
2. 拼接: x_padded = cat([pad, x], dim=1)
3. 展开: windows = x_padded.unfold(1, window, 1)
4. 聚合: result = windows.mean(dim=-1)  或 .sum(dim=-1)
```

这确保了输出张量与输入张量在时间维度上形状一致，且早期时间步使用零填充而非 NaN。
