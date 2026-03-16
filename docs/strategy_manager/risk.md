# strategy_manager/risk.py 文档

## 1. 文件概述

`risk.py` 实现了**风险控制引擎**，负责在交易执行前对目标代币进行安全性检查和仓位大小计算。其核心职责包括：

1. **流动性过滤**：拒绝流动性过低的代币，避免滑点过大或无法退出的风险。
2. **蜜罐检测**：通过 Jupiter DEX 聚合器模拟卖出操作，验证代币是否可以正常卖出（排除"蜜罐"合约）。
3. **仓位计算**：根据钱包余额和策略配置决定实际下单金额。

`RiskEngine` 作为独立的风控层，被 `StrategyRunner` 在每次入场前调用，起到交易"门卫"的作用。

---

## 2. 类与函数说明

### 类：`RiskEngine`

风险控制引擎，封装了安全检查与仓位计算逻辑。

#### `__init__(self)`

- **参数**：无
- **返回值**：无
- **行为**：
  - 创建 `StrategyConfig()` 实例，获取策略配置参数。
  - 创建 `JupiterAggregator()` 实例，用于通过 Jupiter DEX 进行卖出路径验证。

#### `async check_safety(self, token_address, liquidity_usd)`

- **参数**：
  - `token_address` (`str`)：待检查的代币合约地址
  - `liquidity_usd` (`float`)：该代币当前的流动性（以 USD 计）
- **返回值**：`bool` —— `True` 表示安全可交易，`False` 表示存在风险应跳过
- **行为**：
  1. **流动性检查**：若 `liquidity_usd < 5000`，记录警告日志并返回 `False`。
  2. **卖出路径验证**：调用 Jupiter 的 `get_quote()` 模拟将 1,000,000 个最小单位（lamports）的目标代币兑换为 SOL（Wrapped SOL 地址：`So111...112`），滑点容忍度设为 1000 bps（10%）。若无法获取报价，说明代币可能是蜜罐合约，返回 `False`。
  3. 若以上检查均通过，返回 `True`。

#### `calculate_position_size(self, wallet_balance_sol)`

- **参数**：
  - `wallet_balance_sol` (`float`)：当前钱包的 SOL 余额
- **返回值**：`float` —— 建议的下单金额（SOL），若余额不足则返回 `0.0`
- **行为**：
  1. 从配置获取 `ENTRY_AMOUNT_SOL`（默认 2.0 SOL）。
  2. 检查钱包余额是否满足 `size + 0.1` SOL（预留 0.1 SOL 作为 Gas 费）。
  3. 余额充足返回 `size`，不足返回 `0.0`。

#### `async close(self)`

- **参数**：无
- **返回值**：无
- **行为**：关闭内部的 `JupiterAggregator` HTTP 会话，释放网络资源。在程序退出时由 `StrategyRunner.shutdown()` 调用。

---

## 3. 调用关系图

```
+--------------------------------------------------+
|            strategy_manager/risk.py               |
|                                                   |
|  RiskEngine                                       |
|  +-----------------------------------------+      |
|  | __init__()                              |      |
|  |   +---> StrategyConfig()                |      |  <-- config.py
|  |   +---> JupiterAggregator()             |      |  <-- execution/jupiter.py
|  |                                         |      |
|  | check_safety(token_address, liq_usd)    |      |
|  |   +---> 流动性阈值判断                   |      |
|  |   +---> self.jup.get_quote()            |      |  --> Jupiter DEX API
|  |         (模拟卖出，蜜罐检测)              |      |
|  |                                         |      |
|  | calculate_position_size(balance)         |      |
|  |   +---> self.config.ENTRY_AMOUNT_SOL    |      |  <-- config.py
|  |                                         |      |
|  | close()                                 |      |
|  |   +---> self.jup.close()               |      |
|  +-----------------------------------------+      |
+--------------------------------------------------+
          |                    ^
          | 被调用              | 调用
          v                    |
+-----------------------------+--------------------+
| strategy_manager/runner.py                       |
| StrategyRunner                                   |
|   scan_for_entries() --> risk.check_safety()      |
|   _execute_buy()     --> risk.calculate_...()     |
|   shutdown()         --> risk.close()             |
+--------------------------------------------------+
```

---

## 4. 依赖关系

### 内部模块依赖

| 模块 | 导入内容 | 用途 |
|---|---|---|
| `strategy_manager.config` | `StrategyConfig` | 获取 `ENTRY_AMOUNT_SOL` 等策略配置参数 |
| `execution.jupiter` | `JupiterAggregator` | 通过 Jupiter DEX 聚合器进行报价查询，验证代币可卖出性 |

### 外部第三方依赖

| 模块 | 用途 |
|---|---|
| `loguru` (第三方) | 结构化日志记录（警告信息输出） |

---

## 5. 代码逻辑流程

### check_safety 安全检查流程

```
check_safety(token_address, liquidity_usd)
  |
  v
[流动性检查] liquidity_usd < 5000 ?
  |                    |
  | Yes                | No
  v                    v
返回 False          [蜜罐检测]
(流动性过低)         调用 Jupiter get_quote()
                     模拟卖出: token -> SOL
                     amount = 1,000,000 (最小单位)
                     slippage = 1000 bps (10%)
                       |
                       v
                    获取到报价?
                     |          |
                     | No       | Yes
                     v          v
                  返回 False   返回 True
                  (可能蜜罐)   (安全通过)

  * 任何异常 (Exception) 均返回 False (保守策略)
```

### calculate_position_size 仓位计算流程

```
calculate_position_size(wallet_balance_sol)
  |
  v
size = ENTRY_AMOUNT_SOL (默认 2.0 SOL)
  |
  v
wallet_balance_sol < size + 0.1 ?
  |                |
  | Yes            | No
  v                v
返回 0.0          返回 size (2.0 SOL)
(余额不足)        (执行标准仓位)
```

### 设计要点

- **保守原则**：任何检查环节出现异常或不确定性，一律返回 `False` 或 `0.0`，宁可错过交易机会也不冒险。
- **Gas 预留**：仓位计算时额外预留 0.1 SOL 作为后续交易的 Gas 费用，避免因余额不足导致后续操作失败。
- **蜜罐检测原理**：通过 Jupiter 聚合器查询代币到 SOL 的兑换报价。如果一个代币无法获取卖出报价，说明该代币很可能是蜜罐合约（只允许买入不允许卖出），应当规避。
