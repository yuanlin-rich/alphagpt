# data_loader.py 文档

## 1. 文件概述

`data_loader.py` 是 AlphaGPT 项目的数据加载模块，负责从 PostgreSQL 数据库中加载加密货币 OHLCV（开高低收量）行情数据，并将其转换为 PyTorch 张量格式供模型训练使用。该模块的核心职责包括：

- 连接 PostgreSQL 数据库并查询原始行情数据
- 将 SQL 查询结果通过 Pandas 透视（pivot）转换为时间序列矩阵
- 调用 `FeatureEngineer` 计算衍生特征（因子输入）
- 计算目标收益率（两期远期对数收益率）
- 缓存所有数据为 GPU/CPU 张量，供后续训练和回测使用

---

## 2. 类与函数说明

### 2.1 `CryptoDataLoader`

加密货币数据加载器，封装了从数据库到张量的完整 ETL 管道。

**构造函数参数：** 无

**实例属性：**

| 属性 | 类型 | 初始值 | 说明 |
|------|------|--------|------|
| `engine` | `sqlalchemy.Engine` | `create_engine(ModelConfig.DB_URL)` | SQLAlchemy 数据库引擎 |
| `feat_tensor` | `Tensor \| None` | `None` | 特征张量缓存，调用 `load_data()` 后填充 |
| `raw_data_cache` | `dict[str, Tensor] \| None` | `None` | 原始数据张量字典缓存 |
| `target_ret` | `Tensor \| None` | `None` | 目标收益率张量缓存 |

**方法：**

#### `load_data(limit_tokens=500) -> None`

从数据库加载数据并处理为张量，就地存储到实例属性中。

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit_tokens` | int | `500` | 加载的 token（代币）数量上限 |

**返回值：** 无（数据存储到 `self.feat_tensor`、`self.raw_data_cache`、`self.target_ret`）

**异常：**

| 异常类型 | 条件 | 说明 |
|----------|------|------|
| `ValueError` | `addrs` 为空 | 数据库中未查询到任何 token 地址 |

**内部函数：**

#### `to_tensor(col) -> Tensor`（局部函数，定义在 `load_data` 内部）

将 DataFrame 的指定列转换为透视后的 PyTorch 张量。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `col` | str | DataFrame 中的列名（如 `'open'`, `'close'` 等） |

**返回值：** 形状 `(N, T)` 的张量，N 为 token 数量，T 为时间步数

**处理步骤：**
1. 以 `time` 为行索引、`address` 为列索引，对指定列进行透视（pivot）
2. 前向填充缺失值（`ffill`），剩余缺失值填 0
3. 转置（`.values.T`）使形状变为 `(N, T)`
4. 转换为 `float32` 张量并放到 `ModelConfig.DEVICE` 上

---

## 3. 调用关系图

```
+--------------------------------------+
|          CryptoDataLoader            |
+--------------------------------------+
| engine:         sqlalchemy.Engine     |
| feat_tensor:    Tensor | None        |
| raw_data_cache: dict | None          |
| target_ret:     Tensor | None        |
+--------------------------------------+
|                                      |
| load_data(limit_tokens=500)          |
|   |                                  |
|   +-- SQL Query 1: 查询 tokens 表    |
|   |     获取 token 地址列表           |
|   |                                  |
|   +-- SQL Query 2: 查询 ohlcv 表     |
|   |     获取行情数据                  |
|   |                                  |
|   +-- to_tensor(col)  [局部函数]     |
|   |     DataFrame -> pivot -> Tensor  |
|   |     (对 7 列分别调用)             |
|   |                                  |
|   +-- FeatureEngineer.compute_features(raw_data_cache)
|   |     计算 6 维衍生特征             |
|   |                                  |
|   +-- 目标收益率计算                  |
|         log(open[t+2] / open[t+1])   |
+--------------------------------------+

--- 与其他模块的交互 ---

  data_loader.py
       |
       +-- from .config import ModelConfig  --> config.py
       |     使用: DB_URL (数据库连接)
       |     使用: DEVICE (张量设备)
       |
       +-- from .factors import FeatureEngineer --> factors.py
       |     调用: FeatureEngineer.compute_features()
       |     (计算 RET, 流动性评分, 买卖压力, FOMO, 偏差, 成交量等特征)
       |
       +-- import sqlalchemy
       |     调用: create_engine(), 执行 SQL 查询
       |
       +-- import pandas
             调用: read_sql(), pivot(), fillna()

--- 被其他模块调用 ---

  engine.py
       |
       +-- loader = CryptoDataLoader()
       +-- loader.load_data()
       +-- 使用 loader.feat_tensor, loader.raw_data_cache, loader.target_ret
```

---

## 4. 依赖关系

### 4.1 外部第三方依赖

| 模块 | 导入方式 | 用途 |
|------|----------|------|
| `pandas` | `import pandas as pd` | 数据处理：SQL 查询结果读取（`read_sql`）、数据透视（`pivot`）、缺失值填充（`fillna`） |
| `torch` | `import torch` | 张量转换：将 NumPy 数组转为 PyTorch 张量，张量运算（`roll`、`log`） |
| `sqlalchemy` | `import sqlalchemy` | 数据库引擎：通过 `create_engine` 创建 PostgreSQL 连接引擎 |

### 4.2 内部模块依赖

| 模块 | 导入方式 | 使用的符号 | 用途 |
|------|----------|------------|------|
| `model_core.config` | `from .config import ModelConfig` | `ModelConfig.DB_URL`, `ModelConfig.DEVICE` | 获取数据库连接字符串和计算设备 |
| `model_core.factors` | `from .factors import FeatureEngineer` | `FeatureEngineer.compute_features()` | 基于原始数据计算 6 维衍生特征 |

---

## 5. 代码逻辑流程

### 5.1 `load_data()` 完整执行流程

```
调用: loader.load_data(limit_tokens=500)
  |
  v
Step 1: 查询 Token 地址
  +-- SQL: SELECT address FROM tokens LIMIT 500
  +-- 结果: addrs = ['addr1', 'addr2', ...]
  +-- 如果 addrs 为空: 抛出 ValueError("No tokens found.")
  |
  v
Step 2: 查询 OHLCV 行情数据
  +-- 构建 IN 子句: WHERE address IN ('addr1','addr2',...)
  +-- SQL: SELECT time, address, open, high, low, close,
  |        volume, liquidity, fdv
  |        FROM ohlcv
  |        WHERE address IN (...)
  |        ORDER BY time ASC
  +-- 结果: df (DataFrame)
  |
  v
Step 3: 数据转换为张量字典
  +-- 对每一列 (open, high, low, close, volume, liquidity, fdv):
  |     +-- df.pivot(index='time', columns='address', values=col)
  |     +-- 前向填充 (ffill) + 零值填充
  |     +-- 转置为 (N_tokens, T_timesteps) 形状
  |     +-- 转为 float32 张量, 放到 DEVICE 上
  +-- 存储到 self.raw_data_cache = {
  |     'open': Tensor, 'high': Tensor, 'low': Tensor,
  |     'close': Tensor, 'volume': Tensor,
  |     'liquidity': Tensor, 'fdv': Tensor
  |   }
  |
  v
Step 4: 计算衍生特征
  +-- self.feat_tensor = FeatureEngineer.compute_features(self.raw_data_cache)
  |   (内部计算 6 维特征: 对数收益率, 流动性评分, 买卖压力, FOMO 加速度, 泵偏差, 对数成交量)
  +-- feat_tensor 形状: (N, 6, T)
  |
  v
Step 5: 计算目标收益率
  +-- op = raw_data_cache['open']       -- 开盘价 [N, T]
  +-- t1 = roll(op, -1, dims=1)         -- 未来第1期开盘价
  +-- t2 = roll(op, -2, dims=1)         -- 未来第2期开盘价
  +-- target_ret = log(t2 / (t1 + eps)) -- 两期远期对数收益率
  +-- target_ret[:, -2:] = 0.0          -- 最后2个时间步无未来数据，置零
  +-- 存储到 self.target_ret [N, T]
  |
  v
Step 6: 打印确认信息
  +-- "Data Ready. Shape: {feat_tensor.shape}"
  |
  v
完成. 数据已缓存到:
  self.feat_tensor     -- 特征张量
  self.raw_data_cache  -- 原始数据字典
  self.target_ret      -- 目标收益率
```

### 5.2 数据格式说明

#### 数据库表结构（推断）

**`tokens` 表：**

| 列名 | 说明 |
|------|------|
| `address` | Token 合约地址（唯一标识） |

**`ohlcv` 表：**

| 列名 | 说明 |
|------|------|
| `time` | 时间戳 |
| `address` | Token 合约地址 |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量 |
| `liquidity` | 流动性（美元） |
| `fdv` | 完全稀释估值（Fully Diluted Valuation） |

#### 张量形状

| 张量 | 形状 | 说明 |
|------|------|------|
| `raw_data_cache[key]` | `(N, T)` | N=token 数量, T=时间步数 |
| `feat_tensor` | `(N, 6, T)` | 6 维衍生特征 |
| `target_ret` | `(N, T)` | 目标收益率 |

### 5.3 目标收益率计算说明

目标收益率使用两期远期对数收益率，而非简单的单期收益率：

```
target_ret[i, t] = log( open[i, t+2] / open[i, t+1] )
```

这意味着模型预测的是从 t+1 期到 t+2 期的价格变动，而非当前到下一期。这种设计避免了"前视偏差"（look-ahead bias），因为在时间 t 决策时，t+1 的开盘价已经确定（可以在 t+1 开盘时执行交易），而收益来自 t+1 到 t+2 的价格变化。

最后两个时间步的目标收益率被置为 0，因为无法计算未来数据。
