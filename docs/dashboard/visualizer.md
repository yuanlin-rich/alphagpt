# dashboard/visualizer.py 文档

## 1. 文件概述

`visualizer.py` 是 Dashboard 模块的可视化层，专门负责图表的创建与渲染。该文件基于 **Plotly** 库，提供了两个独立的图表绘制函数：

- `plot_pnl_distribution` -- 绘制投资组合各持仓的盈亏百分比柱状图
- `plot_market_scatter` -- 绘制市场代币的流动性-成交量散点图（气泡大小表示 FDV）

所有图表均使用 `plotly_dark` 暗色主题，与仪表盘的深色 UI 风格保持一致。

## 2. 类与函数说明

### 函数

#### `plot_pnl_distribution(portfolio_df: pd.DataFrame) -> go.Figure`

- **参数**:
  - `portfolio_df` (`pd.DataFrame`): 投资组合数据，必须包含以下列：
    - `symbol` (`str`): 代币符号，用作 X 轴标签
    - `pnl_pct` (`float`): 盈亏百分比，用作 Y 轴数值
- **返回值**: `plotly.graph_objects.Figure` -- Plotly 图表对象
- **用途**: 绘制一个柱状图，展示每个持仓代币的盈亏百分比。盈利（pnl_pct > 0）的柱子为绿色（`#00FF00`），亏损（pnl_pct <= 0）的柱子为红色（`#FF0000`）。
- **空数据处理**: 若 `portfolio_df` 为空，直接返回一个空的 `go.Figure()` 对象。
- **图表配置**:
  - 标题: "Current Positions PnL %"
  - Y 轴格式: 百分比（`.2%`）
  - 主题: `plotly_dark`
  - 边距: `l=20, r=20, t=40, b=20`（紧凑布局）

#### `plot_market_scatter(market_df: pd.DataFrame) -> go.Figure`

- **参数**:
  - `market_df` (`pd.DataFrame`): 市场概览数据，必须包含以下列：
    - `liquidity` (`float`): 流动性，用作 X 轴（对数坐标）
    - `volume` (`float`): 成交量，用作 Y 轴（对数坐标）
    - `fdv` (`float`): 完全稀释估值，用作气泡大小
    - `symbol` (`str`): 代币符号，用作颜色区分和悬浮标签
- **返回值**: `plotly.graph_objects.Figure` -- Plotly 图表对象
- **用途**: 绘制一个散点图（气泡图），展示市场中各代币的流动性与成交量关系，气泡大小反映 FDV（完全稀释估值）。X 轴和 Y 轴均采用对数坐标，适合展示数量级差异较大的金融数据。
- **空数据处理**: 若 `market_df` 为空，直接返回一个空的 `go.Figure()` 对象。
- **图表配置**:
  - 标题: "Market Liquidity vs Volume (Bubble Size = FDV)"
  - X 轴: 对数坐标 (`log_x=True`)
  - Y 轴: 对数坐标 (`log_y=True`)
  - 颜色: 按 `symbol` 区分
  - 悬浮标签: 显示 `symbol`
  - 主题: `plotly_dark`

## 3. 调用关系图

```
visualizer.py (本文件内部无互相调用关系)
  |
  |-- plot_pnl_distribution(portfolio_df)
  |     |-- go.Figure(go.Bar(...))          使用 plotly.graph_objects
  |     +-- fig.update_layout(...)
  |
  +-- plot_market_scatter(market_df)
        +-- px.scatter(...)                 使用 plotly.express


与其他模块的交互:

  +-------------+                      +----------------+
  |   app.py    |                      | visualizer.py  |
  |             |  portfolio_df        |                |
  |  Tab1 ------+--------------------> | plot_pnl_      |
  |             |                      |  distribution()|---> go.Figure
  |             |  market_df           |                |
  |  Tab2 ------+--------------------> | plot_market_   |
  |             |                      |  scatter()     |---> go.Figure
  +-------------+                      +----------------+

  +-------------------+    portfolio_df
  | data_service.py   | ---------------+
  | load_portfolio()  |                |
  +-------------------+                v
                                  +---------+
  +-------------------+           | app.py  |    调用    +----------------+
  | data_service.py   | -------> |         | ---------> | visualizer.py  |
  | get_market_       |  market  |         |            +----------------+
  |   overview()      |   _df    +---------+
  +-------------------+
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 导入方式 | 用途 |
|------|---------|------|
| `plotly.express` | `import plotly.express as px` | 高级图表 API，用于快速创建散点图 (`px.scatter`) |
| `plotly.graph_objects` | `import plotly.graph_objects as go` | 底层图表 API，用于创建柱状图 (`go.Bar`) 和空图表 (`go.Figure`) |
| `pandas` | `import pandas as pd` | 类型提示/数据操作（函数参数为 `pd.DataFrame`） |

### 内部模块依赖

无。`visualizer.py` 是一个纯函数式的工具模块，不依赖项目内任何其他模块。它被 `app.py` 单向调用。

## 5. 代码逻辑流程

### `plot_pnl_distribution` 流程

```
输入: portfolio_df (DataFrame)
  |
  v
检查 portfolio_df 是否为空
  |-- 为空 --> 返回空 go.Figure()
  |
  +-- 非空 --> 继续
        |
        v
      根据 pnl_pct 值生成颜色列表:
        对每个持仓:
          pnl_pct > 0  --> 绿色 (#00FF00)
          pnl_pct <= 0 --> 红色 (#FF0000)
        |
        v
      创建 go.Bar 柱状图:
        x = portfolio_df['symbol']   (代币名称)
        y = portfolio_df['pnl_pct']  (盈亏百分比)
        marker_color = colors        (红绿配色)
        |
        v
      更新图表布局:
        - 标题: "Current Positions PnL %"
        - Y 轴百分比格式 (.2%)
        - 暗色主题 (plotly_dark)
        - 紧凑边距
        |
        v
      返回 fig (go.Figure)
```

### `plot_market_scatter` 流程

```
输入: market_df (DataFrame)
  |
  v
检查 market_df 是否为空
  |-- 为空 --> 返回空 go.Figure()
  |
  +-- 非空 --> 继续
        |
        v
      调用 px.scatter() 创建散点图:
        x = "liquidity"     (流动性 - 对数坐标)
        y = "volume"        (成交量 - 对数坐标)
        size = "fdv"        (气泡大小 = 完全稀释估值)
        color = "symbol"    (按代币符号着色)
        hover_name = "symbol" (悬浮显示代币名)
        log_x = True        (X 轴对数)
        log_y = True        (Y 轴对数)
        template = "plotly_dark" (暗色主题)
        |
        v
      返回 fig (go.Figure)
```
