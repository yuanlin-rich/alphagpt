# dashboard/app.py 文档

## 1. 文件概述

`app.py` 是 AlphaGPT 项目 Dashboard 模块的主入口文件，基于 **Streamlit** 框架构建了一个名为 "MemeAlpha Commander" 的 Web 仪表盘应用。该文件负责：

- 页面布局与样式配置
- 侧边栏中展示钱包余额和控制面板（刷新数据、紧急停止）
- 顶部指标卡片展示持仓数量、总投入、未实现盈亏、当前策略
- 三个标签页分别呈现投资组合明细与图表、市场扫描数据、系统日志
- 自动刷新机制（30 秒间隔）

## 2. 类与函数说明

### 函数

#### `get_service() -> DashboardService`

- **装饰器**: `@st.cache_resource` -- 使用 Streamlit 缓存机制，确保整个应用生命周期内只实例化一次 `DashboardService`。
- **参数**: 无
- **返回值**: `DashboardService` 实例
- **用途**: 作为工厂函数，提供全局共享的数据服务对象，避免重复建立数据库连接和 RPC 连接。

### 顶层常量/变量

| 名称 | 类型 | 说明 |
|------|------|------|
| `svc` | `DashboardService` | 由 `get_service()` 返回的全局服务实例 |
| `col1, col2, col3, col4` | Streamlit column 对象 | 顶部 4 列布局容器 |
| `portfolio_df` | `pd.DataFrame` | 从 `portfolio_state.json` 加载的投资组合数据 |
| `market_df` | `pd.DataFrame` | 从数据库加载的市场概览数据 |
| `strategy_data` | `dict` | 从 `best_meme_strategy.json` 加载的策略信息 |
| `open_positions` | `int` | 当前持仓数量 |
| `total_invested` | `float` | 持仓总投入 SOL |
| `tab1, tab2, tab3` | Streamlit tab 对象 | 分别对应 "Portfolio"、"Market Scanner"、"Logs" 三个标签页 |

### 页面区块逻辑

#### 侧边栏 (Sidebar)

- 显示 SOL 钱包余额（调用 `svc.get_wallet_balance()`）
- "Refresh Data" 按钮：触发 `st.rerun()` 重载整个页面
- "EMERGENCY STOP" 按钮：写入 `STOP_SIGNAL` 文件，通知交易进程在下一个周期终止

#### Tab1 - Portfolio

- 当 `portfolio_df` 非空时，格式化展示持仓表格（symbol、entry_price、highest_price、amount_held、pnl_pct、is_moonbag）
- 调用 `plot_pnl_distribution(portfolio_df)` 绘制盈亏柱状图
- 当无持仓时显示提示信息

#### Tab2 - Market Scanner

- 当 `market_df` 非空时，调用 `plot_market_scatter(market_df)` 绘制流动性-成交量散点图
- 同时以表格形式展示市场数据
- 无数据时显示警告

#### Tab3 - Logs

- 调用 `svc.get_recent_logs(20)` 获取最近 20 行日志
- 以代码块形式展示

#### 自动刷新

- 页面底部有一个复选框 "Auto-Refresh (30s)"，默认勾选
- 勾选时每 30 秒自动调用 `st.rerun()` 刷新

## 3. 调用关系图

```
app.py
  |
  |-- get_service()
  |     |
  |     +-- DashboardService()          [data_service.py]
  |
  |-- svc.get_wallet_balance()          [data_service.py]
  |
  |-- svc.load_portfolio()              [data_service.py]
  |     |
  |     +-- portfolio_df --> plot_pnl_distribution()   [visualizer.py]
  |
  |-- svc.get_market_overview()         [data_service.py]
  |     |
  |     +-- market_df --> plot_market_scatter()         [visualizer.py]
  |
  |-- svc.load_strategy_info()          [data_service.py]
  |
  |-- svc.get_recent_logs(20)           [data_service.py]
  |
  +-- time.sleep() / st.rerun()         [自动刷新逻辑]


模块间交互:

  +-------------+       数据请求        +-------------------+
  |   app.py    | --------------------> | data_service.py   |
  | (Streamlit  |                       | (DashboardService) |
  |  前端页面)  |                       +-------------------+
  +------+------+                              |
         |                                     |-- PostgreSQL (ohlcv, tokens)
         |       图表渲染                       |-- portfolio_state.json
         +--------------------> +-----------+  |-- best_meme_strategy.json
                                |visualizer |  |-- strategy.log
                                |   .py     |  |-- Solana RPC
                                +-----------+
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `streamlit` (`st`) | Web 仪表盘框架，提供页面布局、组件、缓存等能力 |
| `pandas` (`pd`) | 数据处理（DataFrame 操作） |
| `time` | `time.sleep()` 用于自动刷新等待间隔 |

### 内部模块依赖

| 模块 | 导入内容 | 用途 |
|------|---------|------|
| `data_service` | `DashboardService` | 数据获取服务类 |
| `visualizer` | `plot_pnl_distribution`, `plot_market_scatter` | 图表绘制函数 |

## 5. 代码逻辑流程

```
启动 Streamlit 应用
      |
      v
1. 页面配置 (set_page_config) + 自定义 CSS 注入
      |
      v
2. 初始化 DashboardService (带缓存)
      |
      v
3. 渲染侧边栏
   |-- 显示钱包 SOL 余额
   |-- "Refresh Data" 按钮 --> 点击则 st.rerun()
   +-- "EMERGENCY STOP" 按钮 --> 点击则写 STOP_SIGNAL 文件
      |
      v
4. 加载数据
   |-- svc.load_portfolio()       --> portfolio_df
   |-- svc.get_market_overview()  --> market_df
   +-- svc.load_strategy_info()   --> strategy_data
      |
      v
5. 渲染顶部 4 列指标卡片
   |-- Open Positions (持仓数/5)
   |-- Total Invested (总投入 SOL)
   |-- Unrealized PnL (未实现盈亏估算)
   +-- Active Strategy (当前策略名称)
      |
      v
6. 渲染 3 个标签页
   |-- Tab1 "Portfolio":
   |     |-- 格式化持仓表格
   |     +-- 调用 plot_pnl_distribution() 绘制 PnL 柱状图
   |
   |-- Tab2 "Market Scanner":
   |     |-- 调用 plot_market_scatter() 绘制散点图
   |     +-- 展示市场数据表格
   |
   +-- Tab3 "Logs":
         +-- 调用 svc.get_recent_logs(20) 展示最近日志
      |
      v
7. 自动刷新逻辑
   |-- time.sleep(1)  (短暂等待)
   +-- 若 "Auto-Refresh" 勾选 --> sleep(30) --> st.rerun()
```
