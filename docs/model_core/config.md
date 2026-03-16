# config.py 文档

## 1. 文件概述

`config.py` 是 AlphaGPT 项目的全局配置模块，定义了模型训练、数据加载、回测等各环节所需的核心超参数和常量。所有配置以类属性的方式集中管理在 `ModelConfig` 类中，便于项目各模块统一引用。

该文件的设计理念是"单一配置源"，其他模块通过 `from .config import ModelConfig` 导入后直接使用类属性，无需实例化。

---

## 2. 类与函数说明

### 2.1 `ModelConfig`

全局配置类。所有属性均为类级别属性（class attributes），无需实例化即可使用。

**类属性：**

| 属性 | 类型 | 值 | 说明 |
|------|------|-----|------|
| `DEVICE` | `torch.device` | `cuda`（如果可用）或 `cpu` | 运算设备。启动时自动检测 CUDA 可用性 |
| `DB_URL` | str | `postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}` | PostgreSQL 数据库连接字符串。通过环境变量动态构建 |
| `BATCH_SIZE` | int | `8192` | 训练批大小 |
| `TRAIN_STEPS` | int | `1000` | 训练总步数 |
| `MAX_FORMULA_LEN` | int | `12` | 因子公式的最大 token 长度 |
| `TRADE_SIZE_USD` | float | `1000.0` | 每笔交易金额（美元） |
| `MIN_LIQUIDITY` | float | `5000.0` | 最低流动性阈值（美元），低于此值视为无法交易 |
| `BASE_FEE` | float | `0.005` | 基础交易费率（0.5%），包含 Swap + Gas + Jito Tip |
| `INPUT_DIM` | int | `6` | 输入特征维度（特征数量） |

### 2.2 `DB_URL` 环境变量配置

`DB_URL` 通过以下环境变量动态构建，均带有默认值：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `DB_USER` | `postgres` | 数据库用户名 |
| `DB_PASSWORD` | `password` | 数据库密码 |
| `DB_HOST` | `localhost` | 数据库主机地址 |
| `DB_NAME` | `crypto_quant` | 数据库名称 |

最终格式：`postgresql://user:password@host:5432/dbname`

---

## 3. 调用关系图

```
+---------------------+
|    ModelConfig      |
+---------------------+
| DEVICE              |
| DB_URL              |
| BATCH_SIZE          |
| TRAIN_STEPS         |
| MAX_FORMULA_LEN     |
| TRADE_SIZE_USD      |
| MIN_LIQUIDITY       |
| BASE_FEE            |
| INPUT_DIM           |
+---------------------+

--- 被以下模块引用 ---

  config.py
       |
       +---> alphagpt.py     使用 ModelConfig.MAX_FORMULA_LEN
       |                      (位置嵌入维度)
       |
       +---> data_loader.py  使用 ModelConfig.DB_URL
       |                      (数据库连接)
       |                     使用 ModelConfig.DEVICE
       |                      (张量设备)
       |
       +---> engine.py       可能使用 BATCH_SIZE, TRAIN_STEPS 等训练参数
       |
       +---> vm.py           可能使用 INPUT_DIM 等维度参数

--- config.py 本身不依赖其他内部模块 ---
```

---

## 4. 依赖关系

### 4.1 外部第三方依赖

| 模块 | 导入方式 | 用途 |
|------|----------|------|
| `torch` | `import torch` | 用于 `torch.device()` 和 `torch.cuda.is_available()` 检测计算设备 |
| `os` | `import os` | 用于 `os.getenv()` 读取环境变量构建数据库连接字符串 |

### 4.2 内部模块依赖

无。`config.py` 是一个纯配置文件，不依赖项目内任何其他模块。它是依赖关系图的叶节点（被依赖方）。

---

## 5. 代码逻辑流程

### 5.1 模块加载时的执行流程

`config.py` 的所有逻辑在模块导入时（import time）立即执行：

```
模块被 import
  |
  v
Step 1: DEVICE 初始化
  +-- 调用 torch.cuda.is_available()
  +-- 如果 CUDA 可用: DEVICE = torch.device("cuda")
  +-- 否则:         DEVICE = torch.device("cpu")
  |
  v
Step 2: DB_URL 构建
  +-- 读取环境变量 DB_USER   (默认: "postgres")
  +-- 读取环境变量 DB_PASSWORD (默认: "password")
  +-- 读取环境变量 DB_HOST    (默认: "localhost")
  +-- 读取环境变量 DB_NAME    (默认: "crypto_quant")
  +-- 拼接为 PostgreSQL 连接字符串
  |
  v
Step 3: 其他常量直接赋值
  BATCH_SIZE = 8192
  TRAIN_STEPS = 1000
  MAX_FORMULA_LEN = 12
  TRADE_SIZE_USD = 1000.0
  MIN_LIQUIDITY = 5000.0
  BASE_FEE = 0.005
  INPUT_DIM = 6
  |
  v
配置就绪，可被其他模块引用
```

### 5.2 使用方式示例

```python
from model_core.config import ModelConfig

# 直接使用类属性，无需实例化
device = ModelConfig.DEVICE
max_len = ModelConfig.MAX_FORMULA_LEN
```

### 5.3 注意事项

1. **DEVICE 在导入时确定**：一旦模块被加载，`DEVICE` 值即固定。如果需要在运行时动态切换设备，需另行处理。
2. **DB_URL 包含明文默认密码**：在生产环境中应确保通过环境变量覆盖 `DB_PASSWORD`，避免使用默认值。
3. **MIN_LIQUIDITY 的双重定义**：`config.py` 中 `MIN_LIQUIDITY = 5000.0`，而 `backtest.py` 中 `MemeBacktest.min_liq = 500000.0`，两者数值不同，需注意使用场景的区别。
4. **BASE_FEE 的双重定义**：`config.py` 中为 `0.005`（0.5%），`backtest.py` 中为 `0.0060`（0.6%），同样存在差异。
