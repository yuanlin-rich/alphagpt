# strategy_manager 模块文档

## 概述
策略管理模块，负责实时扫描、风控和投资组合管理。

## 文件结构
```
├── __init__.py
├── config.py
├── portfolio.py
├── risk.py
└── runner.py
```

## 关键文件说明
### config.py
- **主要类**:
  - `StrategyConfig`: 无文档字符串
- **重要常量**:
  - `MAX_OPEN_POSITIONS`: 3
  - `ENTRY_AMOUNT_SOL`: 2.0
  - `STOP_LOSS_PCT`: -0.05
  - `TRAILING_ACTIVATION`: 0.05
  - `TRAILING_DROP`: 0.03
  - `BUY_THRESHOLD`: 0.85
  - `SELL_THRESHOLD`: 0.45

### portfolio.py
- **主要类**:
  - `Position`: 无文档字符串
  - `PortfolioManager`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串
  - `add_position()`: 无文档字符串
  - `update_price()`: 无文档字符串
  - `update_holding()`: 无文档字符串
  - `close_position()`: 无文档字符串
  - `get_open_count()`: 无文档字符串
  - `save_state()`: 无文档字符串
  - `load_state()`: 无文档字符串

### risk.py
- **主要类**:
  - `RiskEngine`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串
  - `calculate_position_size()`: 无文档字符串

### runner.py
- **主要类**:
  - `StrategyRunner`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串

### __init__.py


## 依赖关系
- **内部依赖**:
  - `data_pipeline`
  - `execution`
  - `model_core`
- **外部依赖**:
  - `asyncio`
  - `config`
  - `dataclasses`
  - `json`
  - `loguru`
  - `pandas`
  - `portfolio`
  - `risk`
  - `time`
  - `torch`
  - `typing`


## 架构图
```
策略管理器
    ├── runner.py (策略运行器)
    ├── portfolio.py (投资组合)
    ├── risk.py (风控模块)
    └── config.py (配置)

工作流程:
市场数据 → runner → risk → portfolio → 交易决策
```

## 数据流
1. 实时扫描市场机会
2. 应用风控规则过滤
3. 管理投资组合头寸
4. 运行策略逻辑
5. 生成交易决策

## 使用示例
```python
# 使用 StrategyConfig 类
from strategy_manager.config import StrategyConfig

instance = StrategyConfig()
# 调用方法...
```
```python
# 使用 Position 类
from strategy_manager.portfolio import Position

instance = Position()
# 调用方法...
```
```python
# 使用 RiskEngine 类
from strategy_manager.risk import RiskEngine

instance = RiskEngine()
# 调用方法...
```
```python
# 使用 StrategyRunner 类
from strategy_manager.runner import StrategyRunner

instance = StrategyRunner()
# 调用方法...
```

## 注意事项
- 实时运行需要稳定环境
- 风控规则需谨慎配置
- 投资组合管理是关键
