# dashboard 模块文档

## 概述
Streamlit仪表板模块，提供实时交易监控和控制系统界面。

## 文件结构
```
├── app.py
├── data_service.py
└── visualizer.py
```

## 关键文件说明
### app.py
- **关键函数**:
  - `get_service()`: 无文档字符串

### data_service.py
- **主要类**:
  - `DashboardService`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串
  - `_get_wallet_address()`: 无文档字符串
  - `get_wallet_balance()`: 无文档字符串
  - `load_portfolio()`: 无文档字符串
  - `load_strategy_info()`: 无文档字符串
  - `get_market_overview()`: 无文档字符串
  - `get_recent_logs()`: 无文档字符串

### visualizer.py
- **关键函数**:
  - `plot_pnl_distribution()`: 无文档字符串
  - `plot_market_scatter()`: 无文档字符串


## 依赖关系
- **外部依赖**:
  - `data_service`
  - `dotenv`
  - `json`
  - `os`
  - `pandas`
  - `plotly`
  - `solana`
  - `solders`
  - `sqlalchemy`
  - `streamlit`
  - `time`
  - `visualizer`


## 架构图
```
Streamlit Dashboard
    ├── app.py (主界面)
    ├── data_service.py (数据服务)
    └── visualizer.py (可视化组件)

数据流向:
外部数据源 → data_service → app.py → visualizer.py → 用户界面
```

## 数据流
1. 从数据库加载投资组合数据
2. 获取市场概览信息
3. 处理并可视化数据
4. 提供用户控制界面
5. 实时更新显示

## 使用示例
```python
# 使用 DashboardService 类
from dashboard.data_service import DashboardService

instance = DashboardService()
# 调用方法...
```

## 注意事项
- 需要Streamlit环境运行
- 依赖数据管道模块提供数据
- 包含紧急停止功能
