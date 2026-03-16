# ops.py 文档

> 源码路径: `model_core/ops.py`

---

## 1. 文件概述

`ops.py` 是 AlphaGPT 项目的**运算符定义模块**，定义了 StackVM 虚拟机可以使用的全部运算操作。该文件的核心内容是：

- 4 个基于 `@torch.jit.script` 编译优化的辅助函数（时序延迟、条件门控、跳变检测、衰减）
- 1 个全局常量 `OPS_CONFIG`（运算符配置列表），定义了 12 种运算符的名称、实现函数和参数数量

该模块是 AlphaGPT 因子表达式语言的**指令集定义**，相当于虚拟机的"ISA（指令集架构）"。`StackVM` 和 `AlphaGPT` 模型均依赖此模块确定词汇表和执行逻辑。

---

## 2. 类与函数说明

### 2.1 JIT 编译函数

以下函数均使用 `@torch.jit.script` 装饰器进行 TorchScript 编译，以获得更优的运行时性能。所有函数操作的张量维度约定为 `[N, T]`（N 为 token 数，T 为时间步数）。

#### 2.1.1 `_ts_delay(x: torch.Tensor, d: int) -> torch.Tensor`

**时序延迟**函数。将时间序列向右平移 `d` 步，左侧补零。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | `torch.Tensor` | 输入张量 `[N, T]` |
| `d` | `int` | 延迟步数 |

- **返回值**: `torch.Tensor`，形状 `[N, T]`
- **逻辑**: 当 `d=0` 直接返回 `x`；否则左侧拼接 `d` 列零向量，右侧截去 `d` 列
- **示例**: `_ts_delay([1,2,3,4,5], 2)` -> `[0,0,1,2,3]`

#### 2.1.2 `_op_gate(condition: torch.Tensor, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor`

**条件门控**运算。根据 condition 的正负选择 x 或 y。

| 参数 | 类型 | 说明 |
|------|------|------|
| `condition` | `torch.Tensor` | 条件张量 `[N, T]` |
| `x` | `torch.Tensor` | condition > 0 时的输出 `[N, T]` |
| `y` | `torch.Tensor` | condition <= 0 时的输出 `[N, T]` |

- **返回值**: `torch.Tensor`，形状 `[N, T]`
- **计算**: `mask * x + (1 - mask) * y`，其中 `mask = (condition > 0).float()`

#### 2.1.3 `_op_jump(x: torch.Tensor) -> torch.Tensor`

**跳变检测**运算。检测时间序列中超过 3 个标准差的异常跳升。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | `torch.Tensor` | 输入张量 `[N, T]` |

- **返回值**: `torch.Tensor`，形状 `[N, T]`，非负值
- **计算**: 先对每行进行 z-score 标准化，然后 `relu(z - 3.0)`，只保留超过 3 sigma 的正向偏离

#### 2.1.4 `_op_decay(x: torch.Tensor) -> torch.Tensor`

**衰减加权**运算。对当前值及最近两期的延迟值进行指数衰减加权求和。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | `torch.Tensor` | 输入张量 `[N, T]` |

- **返回值**: `torch.Tensor`，形状 `[N, T]`
- **计算**: `x + 0.8 * delay(x, 1) + 0.6 * delay(x, 2)`
- **权重**: `[1.0, 0.8, 0.6]` 的衰减序列

---

### 2.2 常量 `OPS_CONFIG`

**运算符配置列表**，类型为 `list[tuple[str, callable, int]]`。每个元素是一个三元组 `(名称, 函数, 参数数量)`。

| 索引 | 名称 | 函数 | 参数数量 | 说明 |
|------|------|------|---------|------|
| 0 | `ADD` | `lambda x, y: x + y` | 2 | 逐元素加法 |
| 1 | `SUB` | `lambda x, y: x - y` | 2 | 逐元素减法 |
| 2 | `MUL` | `lambda x, y: x * y` | 2 | 逐元素乘法 |
| 3 | `DIV` | `lambda x, y: x / (y + 1e-6)` | 2 | 安全除法（防除零） |
| 4 | `NEG` | `lambda x: -x` | 1 | 取负 |
| 5 | `ABS` | `torch.abs` | 1 | 绝对值 |
| 6 | `SIGN` | `torch.sign` | 1 | 符号函数 |
| 7 | `GATE` | `_op_gate` | 3 | 条件门控（三元操作） |
| 8 | `JUMP` | `_op_jump` | 1 | 跳变检测 |
| 9 | `DECAY` | `_op_decay` | 1 | 衰减加权 |
| 10 | `DELAY1` | `lambda x: _ts_delay(x, 1)` | 1 | 延迟 1 步 |
| 11 | `MAX3` | `lambda x: max(x, max(delay(x,1), delay(x,2)))` | 1 | 最近 3 步最大值 |

**Token 编码规则**：在 StackVM 中，特征 token 编号为 `0` 到 `INPUT_DIM-1`（即 0-5），运算符 token 编号为 `INPUT_DIM` 到 `INPUT_DIM + len(OPS_CONFIG) - 1`（即 6-17）。

---

## 3. 调用关系图

### 文件内部调用关系

```
+-------------------------------------------------------------------+
|                          ops.py                                   |
|                                                                   |
|  _ts_delay(x, d)  <---------+------+------+                      |
|     |                        |      |      |                      |
|     |  被以下函数/lambda调用:  |      |      |                      |
|     |                        |      |      |                      |
|  _op_decay(x) ---------------+      |      |                      |
|     调用 _ts_delay(x,1)             |      |                      |
|     调用 _ts_delay(x,2)             |      |                      |
|                                     |      |                      |
|  OPS_CONFIG['DELAY1'] lambda --------+      |                      |
|     调用 _ts_delay(x,1)                    |                      |
|                                            |                      |
|  OPS_CONFIG['MAX3'] lambda -----------------+                      |
|     调用 _ts_delay(x,1)                                           |
|     调用 _ts_delay(x,2)                                           |
|                                                                   |
|  _op_gate(condition, x, y)  <--- OPS_CONFIG['GATE']              |
|                                                                   |
|  _op_jump(x)                <--- OPS_CONFIG['JUMP']              |
|                                                                   |
|  OPS_CONFIG = [12 个运算符元组]                                     |
|     引用以上所有函数及 torch.abs, torch.sign                        |
+-------------------------------------------------------------------+
```

### 与其他模块的交互

```
                +------------+
                |  ops.py    |
                | OPS_CONFIG |
                +-----+------+
                      |
          +-----------+-----------+
          |                       |
    +-----v------+         +-----v--------+
    |   vm.py    |         | alphagpt.py  |
    |  StackVM   |         |  AlphaGPT    |
    |  读取函数   |         |  读取名称    |
    |  和参数数量 |         |  构建词汇表  |
    +------------+         +--------------+
```

---

## 4. 依赖关系

### 4.1 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `torch` | 张量运算、`torch.jit.script` JIT 编译、`torch.abs`、`torch.sign`、`torch.relu`、`torch.cat` 等 |

### 4.2 内部模块依赖

该文件**没有**导入其他内部模块，是一个完全独立的叶子模块。

### 4.3 被其他模块依赖

| 依赖方模块 | 导入对象 | 用途 |
|-----------|----------|------|
| `vm.py` | `OPS_CONFIG` | 构建运算符映射表（函数 + 参数数量） |
| `alphagpt.py` | `OPS_CONFIG` | 提取运算符名称列表构建模型词汇表 |

---

## 5. 代码逻辑流程

### 5.1 模块加载时的执行流程

```
模块被 import
    |
    v
1. @torch.jit.script 编译 _ts_delay()
    |
    v
2. @torch.jit.script 编译 _op_gate()
    |
    v
3. @torch.jit.script 编译 _op_jump()
    |
    v
4. @torch.jit.script 编译 _op_decay()
    |  注意: _op_decay 内部调用 _ts_delay，
    |  由于两者都被 JIT 编译，调用链会被优化
    |
    v
5. 构建 OPS_CONFIG 列表
    |  - 12 个 (名称, 函数, 参数数量) 元组
    |  - lambda 函数在此时创建（捕获 JIT 函数的引用）
    |
    v
模块加载完毕，OPS_CONFIG 可被外部使用
```

### 5.2 运算符分类

按功能可将 12 个运算符分为四类：

```
+-----------------------+-------------------+
| 类别                  | 运算符            |
+-----------------------+-------------------+
| 算术运算 (4个, 2元)   | ADD, SUB, MUL, DIV|
+-----------------------+-------------------+
| 一元变换 (3个, 1元)   | NEG, ABS, SIGN    |
+-----------------------+-------------------+
| 时序运算 (3个, 1元)   | DECAY, DELAY1,    |
|                       | MAX3              |
+-----------------------+-------------------+
| 特殊运算 (2个)        | GATE (3元),       |
|                       | JUMP (1元)        |
+-----------------------+-------------------+
```

### 5.3 _op_decay 的衰减权重示意

```
时间轴:  ... t-2    t-1    t
权重:        0.6    0.8    1.0

output[t] = 1.0 * x[t] + 0.8 * x[t-1] + 0.6 * x[t-2]
```

这是一种简化的指数移动平均，近期数据权重更高，用于平滑因子信号。
