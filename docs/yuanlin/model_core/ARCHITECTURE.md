# model_core 模块文档

## 概述
模型核心模块，包含AlphaGPT模型、因子工程和训练引擎。

## 文件结构
```
├── alphagpt.py
├── backtest.py
├── config.py
├── data_loader.py
├── engine.py
├── factors.py
├── ops.py
└── vm.py
```

## 关键文件说明
### alphagpt.py
- **主要类**:
  - `NewtonSchulzLowRankDecay`: Low-Rank Decay (LoRD) using Newton-Schulz iteration.

A more efficient regularization method that targets low-rank structure
in attention and key parameters. Uses Newton-Schulz iteration to compute
the minimum singular vectors without explicit SVD.

Args:
    named_parameters: Model's named parameters
    decay_rate: Strength of low-rank decay
    num_iterations: Number of Newton-Schulz iterations (default: 5)
    target_keywords: If specified, only decay parameters matching these keywords
  - `StableRankMonitor`: Monitor the effective rank (stable rank) of model parameters.
  - `RMSNorm`: Root Mean Square Layer Normalization
  - `QKNorm`: Query-Key Normalization for Attention
  - `SwiGLU`: Swish GLU activation function
  - `MTPHead`: Multi-Task Pooling Head for multi-objective learning
  - `LoopedTransformerLayer`: Looped Transformer Layer - recurrent processing within a layer
  - `LoopedTransformer`: Looped Transformer Encoder with multiple loop iterations
  - `AlphaGPT`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串
  - `step()`: Apply Newton-Schulz low-rank decay to attention parameters.
  - `__init__()`: 无文档字符串
  - `compute()`: Compute average stable rank of target parameters.
  - `__init__()`: 无文档字符串
  - `forward()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `forward()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `forward()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `forward()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `forward()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `forward()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `forward()`: 无文档字符串
- **重要常量**:
  - `X`: W.float()
  - `X`: X / norm
  - `Y`: X
  - `I`: torch.eye(X.shape[-1], device=X.device, dtype=X.dtype)
  - `W`: param.detach().float()
  - `S`: torch.linalg.svdvals(W)
  - `X`: X.T
  - `A`: Y.T @ Y
  - `Y`: 0.5 * Y @ (3.0 * I - A)
  - `Y`: Y.T

### backtest.py
- **主要类**:
  - `MemeBacktest`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串
  - `evaluate()`: 无文档字符串

### config.py
- **主要类**:
  - `ModelConfig`: 无文档字符串
- **重要常量**:
  - `DEVICE`: torch.device('cuda' if torch.cuda.is_available() else 'cpu')
  - `DB_URL`: f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'password')}@{os.getenv('DB_HOST', 'localhost')}:5432/{os.getenv('DB_NAME', 'crypto_quant')}"
  - `BATCH_SIZE`: 8192
  - `TRAIN_STEPS`: 1000
  - `MAX_FORMULA_LEN`: 12
  - `TRADE_SIZE_USD`: 1000.0
  - `MIN_LIQUIDITY`: 5000.0
  - `BASE_FEE`: 0.005
  - `INPUT_DIM`: 6

### data_loader.py
- **主要类**:
  - `CryptoDataLoader`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串
  - `load_data()`: 无文档字符串
  - `to_tensor()`: 无文档字符串

### engine.py
- **主要类**:
  - `AlphaEngine`: 无文档字符串
- **关键函数**:
  - `__init__()`: Initialize AlphaGPT training engine.

Args:
    use_lord_regularization: Enable Low-Rank Decay (LoRD) regularization
    lord_decay_rate: Strength of LoRD regularization
    lord_num_iterations: Number of Newton-Schulz iterations per step
  - `train()`: 无文档字符串

### factors.py
- **主要类**:
  - `RMSNormFactor`: RMSNorm for factor normalization
  - `MemeIndicators`: 无文档字符串
  - `AdvancedFactorEngineer`: Advanced feature engineering with multiple factor types
  - `FeatureEngineer`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串
  - `forward()`: 无文档字符串
  - `liquidity_health()`: 无文档字符串
  - `buy_sell_imbalance()`: 无文档字符串
  - `fomo_acceleration()`: 无文档字符串
  - `pump_deviation()`: 无文档字符串
  - `volatility_clustering()`: Detect volatility clustering patterns
  - `momentum_reversal()`: Capture momentum reversal signals
  - `relative_strength()`: RSI-like indicator for strength detection
  - `__init__()`: 无文档字符串
  - `robust_norm()`: Robust normalization using median absolute deviation
  - `compute_advanced_features()`: Compute 12-dimensional feature space with advanced factors
  - `compute_features()`: 无文档字符串
  - `robust_norm()`: 无文档字符串
- **重要常量**:
  - `INPUT_DIM`: 6

### ops.py
- **关键函数**:
  - `_ts_delay()`: 无文档字符串
  - `_op_gate()`: 无文档字符串
  - `_op_jump()`: 无文档字符串
  - `_op_decay()`: 无文档字符串
- **重要常量**:
  - `OPS_CONFIG`: [('ADD', lambda x, y: x + y, 2), ('SUB', lambda x, y: x - y, 2), ('MUL', lambda x, y: x * y, 2), ('DIV', lambda x, y: x / (y + 1e-06), 2), ('NEG', lambda x: -x, 1), ('ABS', torch.abs, 1), ('SIGN', torch.sign, 1), ('GATE', _op_gate, 3), ('JUMP', _op_jump, 1), ('DECAY', _op_decay, 1), ('DELAY1', lambda x: _ts_delay(x, 1), 1), ('MAX3', lambda x: torch.max(x, torch.max(_ts_delay(x, 1), _ts_delay(x, 2))), 1)]

### vm.py
- **主要类**:
  - `StackVM`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串
  - `execute()`: 无文档字符串


## 依赖关系
- **外部依赖**:
  - `alphagpt`
  - `backtest`
  - `config`
  - `data_loader`
  - `factors`
  - `json`
  - `ops`
  - `os`
  - `pandas`
  - `sqlalchemy`
  - `torch`
  - `tqdm`
  - `vm`


## 架构图
```
模型核心架构
    ├── alphagpt.py (主模型)
    ├── factors.py (因子工程)
    ├── vm.py (栈虚拟机)
    ├── engine.py (训练引擎)
    └── backtest.py (回测系统)

处理流程:
原始数据 → factors → alphagpt → vm → 交易信号
```

## 数据流
1. 加载历史市场数据
2. 计算因子矩阵
3. 运行AlphaGPT模型预测
4. 使用栈虚拟机执行公式
5. 生成交易信号和权重

## 使用示例
```python
# 使用 NewtonSchulzLowRankDecay 类
from model_core.alphagpt import NewtonSchulzLowRankDecay

instance = NewtonSchulzLowRankDecay()
# 调用方法...
```
```python
# 使用 MemeBacktest 类
from model_core.backtest import MemeBacktest

instance = MemeBacktest()
# 调用方法...
```
```python
# 使用 ModelConfig 类
from model_core.config import ModelConfig

instance = ModelConfig()
# 调用方法...
```
```python
# 使用 CryptoDataLoader 类
from model_core.data_loader import CryptoDataLoader

instance = CryptoDataLoader()
# 调用方法...
```
```python
# 使用 AlphaEngine 类
from model_core.engine import AlphaEngine

instance = AlphaEngine()
# 调用方法...
```
```python
# 使用 RMSNormFactor 类
from model_core.factors import RMSNormFactor

instance = RMSNormFactor()
# 调用方法...
```
```python
# 使用 StackVM 类
from model_core.vm import StackVM

instance = StackVM()
# 调用方法...
```

## 注意事项
- 需要大量历史数据训练
- 因子计算可能较耗时
- 模型需要定期重新训练
