# processor.py 文档

## 1. 文件概述

`processor.py` 是 `data_pipeline` 模块的数据处理层，负责对原始 OHLCV K线数据进行清洗和特征工程。它提供了两个核心静态方法：一个用于数据清洗（去重、缺失值填充、异常值剔除），另一个用于计算量化因子（对数收益率、波动率、量能冲击、趋势信号）。该模块是数据从"原始"到"可供模型使用"的关键转换环节。

## 2. 类与函数说明

### 类：`DataProcessor`

数据处理工具类，所有方法均为静态方法（`@staticmethod`），无需实例化即可使用。

#### `@staticmethod clean_ohlcv(df)`

- **用途**：清洗原始 OHLCV 数据，处理重复记录、缺失值和极端异常值。
- **参数**：
  - `df` — `pandas.DataFrame`，包含原始 OHLCV 数据，需包含列：`time`, `address`, `open`, `high`, `low`, `close`, `volume`
- **返回值**：`pandas.DataFrame` — 清洗后的 DataFrame
- **处理步骤**：
  1. 空 DataFrame 检查，若为空直接返回
  2. 按 `(time, address)` 去重，保留最后一条
  3. 按 `time` 列升序排列
  4. `close` 列使用前向填充（`ffill`）
  5. `open`、`high`、`low` 列用 `close` 值填充缺失
  6. `volume` 列缺失值填充为 0
  7. 剔除 `close` 价格极小（<= 1e-15）的异常记录

#### `@staticmethod add_basic_factors(df)`

- **用途**：基于清洗后的 OHLCV 数据计算基础量化因子。
- **参数**：
  - `df` — `pandas.DataFrame`，清洗后的 OHLCV 数据，必须包含 `close` 和 `volume` 列
- **返回值**：`pandas.DataFrame` — 添加了新因子列的 DataFrame
- **新增列**：

  | 列名 | 计算公式 | 说明 |
  |------|----------|------|
  | `log_ret` | `ln(close_t / close_{t-1})` | 对数收益率 |
  | `volatility` | `rolling(20).std(log_ret)` | 20 期滚动已实现波动率 |
  | `vol_shock` | `volume / (rolling(20).mean(volume) + 1e-6)` | 量能冲击因子（当前成交量与 20 期均值之比） |
  | `trend` | `1 if close > MA(60) else -1` | 趋势信号（基于 60 期移动平均线） |

- **后处理**：将 `inf` 和 `-inf` 替换为 `NaN`，再将所有 `NaN` 填充为 `0`

## 3. 调用关系图

```
+-----------------------------------------------------------+
|                     DataProcessor                          |
+-----------------------------------------------------------+
|                                                           |
|  clean_ohlcv(df) [静态方法]                                |
|    |-- df.drop_duplicates(subset=['time','address'])       |
|    |-- df.sort_values('time')                             |
|    |-- df['close'].ffill()                                |
|    |-- df[['open','high','low']].fillna(close)            |
|    |-- df['volume'].fillna(0)                             |
|    +-- df[df['close'] > 1e-15]  过滤极端值                 |
|                                                           |
|  add_basic_factors(df) [静态方法]                           |
|    |-- log_ret = log(close / close.shift(1))              |
|    |-- volatility = log_ret.rolling(20).std()             |
|    |-- vol_shock = volume / volume.rolling(20).mean()     |
|    |-- trend = where(close > MA60, 1, -1)                 |
|    +-- replace([inf, -inf], NaN).fillna(0)                |
+-----------------------------------------------------------+

典型调用链 (外部):
  raw_df  -->  DataProcessor.clean_ohlcv(df)
                      |
                      v
              cleaned_df  -->  DataProcessor.add_basic_factors(df)
                                      |
                                      v
                              factor_df (可供模型使用)
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `pandas` | 数据处理核心库，DataFrame 操作 |
| `numpy` | 数值计算（`np.log`、`np.where`、`np.inf`、`np.nan`） |
| `loguru` | 日志记录（已 import 但当前代码中未使用） |

### 内部模块依赖

无。`processor.py` 是纯数据处理模块，不依赖项目内其他模块。

## 5. 代码逻辑流程

### clean_ohlcv 数据清洗流程

```
输入: 原始 OHLCV DataFrame
  |
  v
[检查] DataFrame 是否为空?
  |-- 是: 直接返回空 DataFrame
  +-- 否: 继续
  |
  v
[去重] 按 (time, address) 组合去重, 保留最后一条记录
  |
  v
[排序] 按 time 列升序排列
  |
  v
[填充 close] 使用前向填充 (ffill)
  |-- 逻辑: 若某时刻收盘价缺失, 使用前一个有效收盘价
  |
  v
[填充 open/high/low] 用 close 列的值替代缺失值
  |-- 逻辑: 若无 OHLC 中某些值, 以收盘价作为近似
  |
  v
[填充 volume] 缺失值替换为 0
  |
  v
[过滤] 剔除 close <= 1e-15 的记录
  |-- 逻辑: 极小价格通常是数据错误或无意义数据
  |
  v
输出: 清洗后的 DataFrame
```

### add_basic_factors 因子计算流程

```
输入: 清洗后的 OHLCV DataFrame
  |
  v
[计算对数收益率]
  log_ret = ln(close_t / close_{t-1})
  |-- 衡量每期价格变化的百分比 (连续复合)
  |
  v
[计算已实现波动率]
  volatility = rolling(20期).std(log_ret)
  |-- 过去 20 个周期的收益标准差, 反映短期风险
  |
  v
[计算量能冲击]
  vol_ma = rolling(20期).mean(volume) + 1e-6  (避免除零)
  vol_shock = volume / vol_ma
  |-- > 1 表示放量, < 1 表示缩量
  |
  v
[计算趋势信号]
  ma_long = rolling(60期).mean(close)
  trend = 1 (close > ma_long) 或 -1 (close <= ma_long)
  |-- 基于 60 期均线的多空方向判断
  |
  v
[数值修正]
  将 inf / -inf 替换为 NaN
  将所有 NaN 填充为 0
  |-- 确保下游模型不会遇到无穷大或缺失值
  |
  v
输出: 带因子列的 DataFrame
```

> **设计说明**：`1e-6` 的小量加到 `vol_ma` 上是为了防止在成交量长时间为 0 的代币上发生除零错误。`1e-15` 的价格阈值用于剔除本质上无交易价值的数据点。
