# strategy_manager/portfolio.py 文档

## 1. 文件概述

`portfolio.py` 负责**持仓管理**，是策略管理模块的核心数据层。该文件定义了两个关键组件：

- **`Position`** 数据类：描述单个持仓的完整信息（代币地址、入场价、数量、成本等）。
- **`PortfolioManager`** 管理类：提供持仓的增、删、改、查操作，并通过 JSON 文件实现状态持久化，确保程序重启后仓位信息不丢失。

---

## 2. 类与函数说明

### 数据类：`Position`

使用 `@dataclass` 装饰器定义，表示单个代币的持仓信息。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `token_address` | `str` | 必填 | 代币的链上合约地址 |
| `symbol` | `str` | 必填 | 代币符号（如 `"Meme_Ab3c"`） |
| `entry_price` | `float` | 必填 | 入场价格（SOL 计价） |
| `entry_time` | `float` | 必填 | 入场时间戳（Unix timestamp） |
| `amount_held` | `float` | 必填 | 当前持有的代币数量（Token 原始单位） |
| `initial_cost_sol` | `float` | 必填 | 初始投入的 SOL 数量 |
| `highest_price` | `float` | 必填 | 持仓期间的最高价格，用于计算追踪止损的回撤幅度 |
| `is_moonbag` | `bool` | `False` | 是否已执行过 Moonbag 止盈（即已卖出部分仓位回本，剩余仓位让利润奔跑） |

---

### 类：`PortfolioManager`

管理所有活跃持仓的生命周期，提供状态持久化能力。

#### `__init__(self, state_file="portfolio_state.json")`

- **参数**：
  - `state_file` (`str`)：持久化文件路径，默认为 `"portfolio_state.json"`
- **行为**：初始化空的 `positions` 字典，并调用 `load_state()` 从磁盘恢复之前的仓位数据。

#### `add_position(self, token, symbol, price, amount, cost_sol)`

- **参数**：
  - `token` (`str`)：代币地址，作为 `positions` 字典的键
  - `symbol` (`str`)：代币符号
  - `price` (`float`)：入场价格
  - `amount` (`float`)：购入的代币数量
  - `cost_sol` (`float`)：花费的 SOL 数量
- **返回值**：无
- **行为**：创建新的 `Position` 对象（`entry_time` 取当前时间，`highest_price` 初始化为入场价），存入 `positions` 字典，调用 `save_state()` 持久化，并记录日志。

#### `update_price(self, token, current_price)`

- **参数**：
  - `token` (`str`)：代币地址
  - `current_price` (`float`)：当前市场价格
- **返回值**：无
- **行为**：若当前价格高于已记录的最高价（`highest_price`），则更新之。用于追踪止损时计算回撤幅度。更新后自动保存状态。

#### `update_holding(self, token, new_amount)`

- **参数**：
  - `token` (`str`)：代币地址
  - `new_amount` (`float`)：新的持有数量
- **返回值**：无
- **行为**：更新指定仓位的持有数量。若新数量 <= 0，则自动删除该仓位。更新后自动保存状态。

#### `close_position(self, token)`

- **参数**：
  - `token` (`str`)：代币地址
- **返回值**：无
- **行为**：从 `positions` 字典中删除指定仓位，记录日志，保存状态。

#### `get_open_count(self)`

- **参数**：无
- **返回值**：`int` —— 当前活跃仓位的数量
- **行为**：返回 `positions` 字典的长度。

#### `save_state(self)`

- **参数**：无
- **返回值**：无
- **行为**：将 `positions` 字典中的所有 `Position` 对象转为字典（通过 `dataclasses.asdict`），序列化为 JSON 写入 `state_file`。

#### `load_state(self)`

- **参数**：无
- **返回值**：无
- **行为**：从 `state_file` 读取 JSON 数据，反序列化为 `Position` 对象填充到 `positions` 字典。若文件不存在，则初始化为空字典。

---

## 3. 调用关系图

```
+----------------------------------------------------------+
|                strategy_manager/portfolio.py              |
|                                                          |
|  Position (dataclass)                                    |
|     ^                                                    |
|     | 创建实例                                            |
|     |                                                    |
|  PortfolioManager                                        |
|  +----------------------------------------------------+  |
|  | __init__()                                         |  |
|  |   +---> load_state() ---> [读取 JSON 文件]         |  |
|  |                                                    |  |
|  | add_position()                                     |  |
|  |   +---> Position(...)  创建新仓位                   |  |
|  |   +---> save_state() ---> [写入 JSON 文件]         |  |
|  |                                                    |  |
|  | update_price()                                     |  |
|  |   +---> save_state()                               |  |
|  |                                                    |  |
|  | update_holding()                                   |  |
|  |   +---> save_state()                               |  |
|  |                                                    |  |
|  | close_position()                                   |  |
|  |   +---> save_state()                               |  |
|  |                                                    |  |
|  | get_open_count()  (纯查询，无副作用)                |  |
|  +----------------------------------------------------+  |
+----------------------------------------------------------+
           |
           | 被外部调用
           v
+----------------------------+
| strategy_manager/runner.py |
| StrategyRunner             |
|   - add_position()         |
|   - update_price()         |
|   - update_holding()       |
|   - close_position()       |
|   - get_open_count()       |
|   - save_state()           |
|   - positions (直接访问)    |
+----------------------------+
```

---

## 4. 依赖关系

### 内部模块依赖

无。`portfolio.py` 不依赖 `alphagpt` 项目内的其他模块。

### 外部第三方依赖

| 模块 | 用途 |
|---|---|
| `json` (标准库) | 状态文件的序列化与反序列化 |
| `time` (标准库) | 获取当前时间戳（`time.time()`），用于记录入场时间 |
| `dataclasses` (标准库) | `@dataclass` 装饰器和 `asdict` 函数，用于定义 `Position` 数据类 |
| `typing` (标准库) | `Dict` 类型注解 |
| `loguru` (第三方) | 结构化日志记录 |

---

## 5. 代码逻辑流程

### 初始化流程

```
PortfolioManager.__init__()
  |
  v
设置 state_file 路径 (默认 "portfolio_state.json")
  |
  v
初始化 positions = {} (空字典)
  |
  v
调用 load_state()
  |
  +---> 尝试打开 state_file
  |       |
  |       +---> 文件存在：解析 JSON，逐条构建 Position 对象填入 positions
  |       |
  |       +---> 文件不存在 (FileNotFoundError)：positions 保持空字典
  |
  v
初始化完毕，Portfolio 就绪
```

### 交易流程中的持仓管理

```
买入成功后:
  add_position(token, symbol, price, amount, cost_sol)
    |
    v
  创建 Position 对象 (entry_time=当前时间, highest_price=入场价)
    |
    v
  存入 positions[token]  -->  save_state()  -->  写入 JSON 文件
    |
    v
  记录日志 "[+] Position Added: ..."

监控过程中:
  update_price(token, current_price)
    |
    +---> 若 current_price > highest_price: 更新 highest_price
    +---> save_state()

部分卖出后:
  update_holding(token, new_amount)
    |
    +---> 更新 amount_held
    +---> 若 new_amount <= 0: 删除仓位
    +---> save_state()

完全平仓:
  close_position(token)
    |
    +---> 从 positions 字典中删除
    +---> save_state()
    +---> 记录日志 "[+] Position Closed: ..."
```

### 状态持久化机制

每次对 `positions` 字典的修改操作（`add_position`、`update_price`、`update_holding`、`close_position`）都会立即触发 `save_state()`，将完整的仓位快照写入 JSON 文件。这种「写穿」策略确保了即使程序异常退出，已记录的最新仓位状态也不会丢失。启动时通过 `load_state()` 恢复，实现了简单但可靠的持久化方案。
