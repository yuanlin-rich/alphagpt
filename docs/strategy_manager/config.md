# strategy_manager/config.py 文档

## 1. 文件概述

`config.py` 是策略管理模块的**配置中心**，定义了 `StrategyConfig` 类。该类以类属性（类常量）的形式集中管理交易策略运行时所需的全部参数，包括仓位控制、止盈止损阈值、追踪止损参数以及 AI 信号阈值等。整个 `strategy_manager` 模块的其他组件（`portfolio.py`、`risk.py`、`runner.py`）均依赖此配置来驱动交易决策。

---

## 2. 类与函数说明

### 类：`StrategyConfig`

纯配置类，不包含任何方法，所有属性均为类级别常量。

| 常量名 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `MAX_OPEN_POSITIONS` | `int` | `3` | 允许同时持有的最大仓位数。当已持仓数量达到此值时，`StrategyRunner` 将跳过新的入场扫描。 |
| `ENTRY_AMOUNT_SOL` | `float` | `2.0` | 每次建仓投入的 SOL 数量。`RiskEngine.calculate_position_size()` 以此为基准计算实际下单量。 |
| `STOP_LOSS_PCT` | `float` | `-0.05` | 止损百分比阈值（-5%）。当持仓盈亏比低于此值时触发止损卖出。 |
| `TAKE_PROFIT_Target1` | `float` | `0.10` | 第一目标止盈百分比（+10%）。达到此涨幅时执行 Moonbag 策略，即卖出部分仓位、保留剩余仓位让利润奔跑。 |
| `TP_Target1_Ratio` | `float` | `0.5` | 第一目标止盈时的卖出比例（50%）。触发 Moonbag 止盈时卖出持仓的 50%。 |
| `TRAILING_ACTIVATION` | `float` | `0.05` | 追踪止损激活阈值（+5%）。当持仓从入场价的最大涨幅超过此值时，追踪止损机制被激活。 |
| `TRAILING_DROP` | `float` | `0.03` | 追踪止损回撤阈值（3%）。追踪止损激活后，若价格从最高点回撤超过此比例，则触发卖出。 |
| `BUY_THRESHOLD` | `float` | `0.85` | AI 买入信号阈值。`StackVM` 模型输出经 Sigmoid 转换后的概率分数需大于等于此值才考虑入场。 |
| `SELL_THRESHOLD` | `float` | `0.45` | AI 卖出信号阈值。对于非 Moonbag 仓位，若 AI 推理分数低于此值则触发 AI 信号卖出。 |

---

## 3. 调用关系图

```
+---------------------------------------------+
|           strategy_manager/config.py         |
|                                              |
|            StrategyConfig (类常量)            |
+----+----------------+--------------+---------+
     |                |              |
     v                v              v
 risk.py         runner.py      runner.py
 RiskEngine      monitor_       scan_for_
 .__init__()     positions()    entries()
 .calculate_     (读取止损/     (读取 BUY_
  position_       止盈/追踪      THRESHOLD)
  size()          参数)
```

**被引用情况：**

- `risk.py` —— `RiskEngine.__init__()` 创建 `StrategyConfig()` 实例，`calculate_position_size()` 读取 `ENTRY_AMOUNT_SOL`。
- `runner.py` —— `StrategyRunner.monitor_positions()` 读取 `STOP_LOSS_PCT`、`TAKE_PROFIT_Target1`、`TP_Target1_Ratio`、`TRAILING_ACTIVATION`、`TRAILING_DROP`、`SELL_THRESHOLD`；`scan_for_entries()` 读取 `BUY_THRESHOLD`、`MAX_OPEN_POSITIONS`；`run_loop()` 读取 `MAX_OPEN_POSITIONS`。

---

## 4. 依赖关系

### 内部模块依赖

无。`config.py` 是叶子节点，不依赖项目内其他任何模块。

### 外部第三方依赖

无。该文件未导入任何第三方库。

---

## 5. 代码逻辑流程

`config.py` 不包含运行时逻辑，仅作为静态配置定义文件。其执行流程如下：

1. Python 解释器在 `import` 时加载该模块。
2. 解析 `StrategyConfig` 类定义，将 9 个类属性绑定到类对象上。
3. 其他模块通过 `StrategyConfig.XXX`（直接访问类属性）或 `StrategyConfig().XXX`（实例化后访问）来读取配置值。
4. 当前设计中所有参数为硬编码常量。若需要动态配置，可考虑改为从环境变量或配置文件加载。

```
模块加载
  |
  v
定义 StrategyConfig 类
  |
  v
绑定 9 个类常量
  (MAX_OPEN_POSITIONS, ENTRY_AMOUNT_SOL,
   STOP_LOSS_PCT, TAKE_PROFIT_Target1,
   TP_Target1_Ratio, TRAILING_ACTIVATION,
   TRAILING_DROP, BUY_THRESHOLD, SELL_THRESHOLD)
  |
  v
等待被其他模块 import 引用
```
