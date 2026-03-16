# vm.py 文档

> 源码路径: `model_core/vm.py`

---

## 1. 文件概述

`vm.py` 是 AlphaGPT 项目的**栈式虚拟机模块**，实现了一个基于栈的公式执行引擎 `StackVM`。该虚拟机负责将模型生成的 token 序列（整数列表）解释执行为张量运算，最终输出一个因子信号张量。

核心职责：
- 将 token 序列分为**特征引用指令**和**运算符指令**两类
- 使用操作数栈执行后缀表达式风格的计算
- 处理运算过程中的异常值（NaN、Inf）
- 对非法公式（栈不平衡、token 越界、运行时错误）返回 `None`

`StackVM` 是训练引擎（`AlphaEngine`）与因子公式之间的桥梁，将离散的 token 序列转化为可回测的连续信号。

---

## 2. 类与函数说明

### 2.1 类 `StackVM`

基于栈的虚拟机，执行由整数 token 组成的因子公式。

#### 2.1.1 `__init__(self)`

**构造函数**，初始化 token 到运算符的映射表。

**内部属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.feat_offset` | `int` | 特征维度数（值为 `FeatureEngineer.INPUT_DIM = 6`），同时也是运算符 token 的起始编号 |
| `self.op_map` | `dict[int, callable]` | token 到运算函数的映射，键为 `feat_offset + i`，值为 `OPS_CONFIG[i][1]` |
| `self.arity_map` | `dict[int, int]` | token 到参数数量的映射，键为 `feat_offset + i`，值为 `OPS_CONFIG[i][2]` |

**Token 编码方案：**

```
Token 0 ~ 5  (< feat_offset):  特征引用，对应 feat_tensor 的第 0~5 个特征维度
Token 6 ~ 17 (>= feat_offset): 运算符，对应 OPS_CONFIG 中的 12 种运算
```

#### 2.1.2 `execute(self, formula_tokens, feat_tensor)`

**公式执行方法**，核心函数。

| 参数 | 类型 | 说明 |
|------|------|------|
| `formula_tokens` | `list[int]` | 公式 token 序列，每个元素为整数 |
| `feat_tensor` | `torch.Tensor` | 特征张量，形状 `[N, INPUT_DIM, T]` |

- **返回值**: `torch.Tensor`（形状 `[N, T]`）或 `None`

**返回 `None` 的情况：**

| 条件 | 说明 |
|------|------|
| `len(stack) < arity` | 栈中操作数不够执行当前运算符 |
| `token not in op_map` 且 `token >= feat_offset` | 未知 token，既不是特征也不是运算符 |
| `len(stack) != 1`（执行结束时） | 公式执行完毕后栈中不恰好剩余 1 个元素 |
| 任何运行时异常 | 被外层 `try/except` 捕获 |

**NaN/Inf 处理：**
运算结果中包含 NaN 或 Inf 时，使用 `torch.nan_to_num(res, nan=0.0, posinf=1.0, neginf=-1.0)` 进行替换，不会导致执行失败。

---

## 3. 调用关系图

### 文件内部调用关系

```
+-------------------------------------------------------------------+
|                           vm.py                                   |
|                                                                   |
|  StackVM                                                          |
|  +-------------------------------------------------------------+ |
|  | __init__()                                                   | |
|  |   +---> FeatureEngineer.INPUT_DIM   [factors.py]             | |
|  |   +---> OPS_CONFIG[i][1]            [ops.py] 提取函数         | |
|  |   +---> OPS_CONFIG[i][2]            [ops.py] 提取参数数量     | |
|  +-------------------------------------------------------------+ |
|  | execute(formula_tokens, feat_tensor)                         | |
|  |   |                                                          | |
|  |   +---> FOR token in formula_tokens:                         | |
|  |   |       |                                                  | |
|  |   |       +---> IF token < feat_offset:                      | |
|  |   |       |       stack.append(feat_tensor[:, token, :])     | |
|  |   |       |                                                  | |
|  |   |       +---> ELIF token in op_map:                        | |
|  |   |       |       args = stack.pop() * arity 次               | |
|  |   |       |       res = op_map[token](*args)                 | |
|  |   |       |       nan_to_num(res) if needed                  | |
|  |   |       |       stack.append(res)                          | |
|  |   |       |                                                  | |
|  |   |       +---> ELSE: return None                            | |
|  |   |                                                          | |
|  |   +---> IF len(stack) == 1: return stack[0]                  | |
|  |   +---> ELSE: return None                                    | |
|  +-------------------------------------------------------------+ |
+-------------------------------------------------------------------+
```

### 与其他模块的交互

```
+-------------+     +-----------+     +------------+
| factors.py  |---->|  vm.py    |<----| ops.py     |
| Feature     |     |  StackVM  |     | OPS_CONFIG |
| Engineer    |     +-----+-----+     +------------+
| .INPUT_DIM  |           |
+-------------+           |
                          | execute() 被调用
                          |
                    +-----v--------+
                    |  engine.py   |
                    |  AlphaEngine |
                    |  .train()    |
                    +--------------+
```

---

## 4. 依赖关系

### 4.1 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `torch` | 张量操作（`torch.isnan`、`torch.isinf`、`torch.nan_to_num`） |

### 4.2 内部模块依赖

| 模块 | 导入对象 | 用途 |
|------|----------|------|
| `.ops` | `OPS_CONFIG` | 获取运算符列表（名称、函数、参数数量） |
| `.factors` | `FeatureEngineer` | 获取 `INPUT_DIM` 常量，用于区分特征 token 和运算符 token |

### 4.3 被其他模块依赖

| 依赖方模块 | 导入对象 | 用途 |
|-----------|----------|------|
| `engine.py` | `StackVM` | 在训练循环中执行采样出的公式 |

---

## 5. 代码逻辑流程

### 5.1 StackVM 初始化流程

```
StackVM.__init__()
    |
    v
读取 FeatureEngineer.INPUT_DIM = 6
    |  feat_offset = 6
    |
    v
遍历 OPS_CONFIG (12 个运算符):
    |
    +---> op_map = {
    |       6: ADD函数,   7: SUB函数,   8: MUL函数,
    |       9: DIV函数,  10: NEG函数,  11: ABS函数,
    |      12: SIGN函数, 13: GATE函数, 14: JUMP函数,
    |      15: DECAY函数, 16: DELAY1函数, 17: MAX3函数
    |     }
    |
    +---> arity_map = {
            6: 2, 7: 2, 8: 2, 9: 2,     (二元运算)
           10: 1, 11: 1, 12: 1,          (一元运算)
           13: 3,                         (三元运算)
           14: 1, 15: 1, 16: 1, 17: 1    (一元运算)
          }
```

### 5.2 execute() 执行流程

```
execute(formula_tokens, feat_tensor)
    |
    v
初始化空栈 stack = []
    |
    v
FOR each token in formula_tokens:
    |
    +---> token = int(token)   <-- 确保为整数
    |
    +---> [分支1] token < 6 (特征引用)
    |       |
    |       v
    |     stack.push( feat_tensor[:, token, :] )
    |     即将第 token 维特征的时间序列压栈
    |     形状: [N, T]
    |
    +---> [分支2] token in op_map (运算符)
    |       |
    |       v
    |     arity = arity_map[token]
    |       |
    |       v
    |     检查 len(stack) >= arity ?
    |       |                    |
    |       v (不够)             v (够)
    |     return None         从栈顶弹出 arity 个参数
    |                           |
    |                           v
    |                         args.reverse()  <-- 恢复正确的参数顺序
    |                           |
    |                           v
    |                         res = func(*args)
    |                           |
    |                           v
    |                         检查 NaN/Inf ?
    |                           |          |
    |                           v (有)     v (无)
    |                         nan_to_num   |
    |                           |          |
    |                           +----+-----+
    |                                |
    |                                v
    |                         stack.push(res)
    |
    +---> [分支3] 未知 token
            |
            v
          return None
    |
    v
执行完毕，检查栈状态:
    |
    +---> len(stack) == 1 ?
    |       |            |
    |       v (是)       v (否)
    |     return        return None
    |     stack[0]
    |
    v
若任何步骤抛出异常 -> except: return None
```

### 5.3 执行示例

假设 `INPUT_DIM = 6`，公式 token 序列为 `[0, 1, 6]`：

```
步骤 1: token=0 (< 6, 特征引用)
  stack: [feat[:, 0, :]]     <-- 压入第 0 维特征 (对数收益率)

步骤 2: token=1 (< 6, 特征引用)
  stack: [feat[:, 0, :], feat[:, 1, :]]  <-- 压入第 1 维特征 (流动性)

步骤 3: token=6 (运算符 ADD, arity=2)
  弹出 2 个操作数: y=feat[:, 1, :], x=feat[:, 0, :]
  计算: res = x + y
  stack: [res]               <-- 结果压栈

执行结束: len(stack)==1, 返回 res  <-- 形状 [N, T]
```

### 5.4 错误处理策略

`execute()` 采用**宽容执行、严格验证**的策略：

1. **运算级宽容**: NaN/Inf 不终止执行，而是替换为安全值 (0.0/1.0/-1.0)
2. **结构级严格**: 栈不平衡（操作数不足或剩余多余值）直接返回 `None`
3. **全局兜底**: 外层 `try/except` 捕获所有未预见的异常，返回 `None`

这种设计配合训练引擎中的奖励机制（`None` -> 惩罚 -5.0），使得模型在训练过程中自然地学会生成语法正确、栈平衡的公式。
