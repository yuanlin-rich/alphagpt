# base.py -- 数据提供者抽象基类

> 文件路径: `data_pipeline/providers/base.py`

---

## 1. 文件概述

`base.py` 是 `data_pipeline/providers` 子模块的基础文件，定义了数据提供者（DataProvider）的**抽象基类**。该类使用 Python 的 `abc` 模块声明了所有数据提供者必须实现的接口契约，确保不同数据源（如 Birdeye、DexScreener）具有统一的方法签名。

核心职责：
- 定义数据提供者的统一接口规范
- 强制子类实现 `get_trending_tokens` 和 `get_token_history` 两个异步方法
- 作为多态调用的类型基础，使上层调用者可以无差别地使用不同数据源

---

## 2. 类与函数说明

### 类: `DataProvider(ABC)`

抽象基类，继承自 `abc.ABC`。所有具体的数据提供者（如 `BirdeyeProvider`、`DexScreenerProvider`）都必须继承此类并实现其抽象方法。

#### 方法: `async get_trending_tokens(self, limit: int)`

| 属性     | 说明                                           |
| -------- | ---------------------------------------------- |
| 装饰器   | `@abstractmethod`                              |
| 类型     | 异步抽象方法                                   |
| 参数     | `limit: int` -- 返回的热门代币数量上限         |
| 返回值   | 由子类定义，通常为代币信息字典的列表 `list[dict]` |
| 用途     | 获取当前热门/趋势代币列表                      |

#### 方法: `async get_token_history(self, session, address: str, days: int)`

| 属性     | 说明                                                        |
| -------- | ----------------------------------------------------------- |
| 装饰器   | `@abstractmethod`                                           |
| 类型     | 异步抽象方法                                                |
| 参数     | `session` -- aiohttp 的 ClientSession 实例，用于复用 HTTP 连接 |
|          | `address: str` -- 代币的链上地址                            |
|          | `days: int` -- 获取历史数据的天数                           |
| 返回值   | 由子类定义，通常为 OHLCV 数据元组的列表 `list[tuple]`       |
| 用途     | 获取指定代币在给定时间范围内的历史价格数据                  |

---

## 3. 调用关系图

```
+------------------------------------------+
|           abc (标准库)                    |
|  ABC, abstractmethod                     |
+------------------------------------------+
                  |
                  | 继承
                  v
+------------------------------------------+
|         DataProvider (ABC)               |
|------------------------------------------|
| + get_trending_tokens(limit) [abstract]  |
| + get_token_history(session,             |
|       address, days)        [abstract]   |
+------------------------------------------+
          ^                ^
          |                |
          | 继承           | 继承
          |                |
+-----------------+  +---------------------+
| BirdeyeProvider |  | DexScreenerProvider |
| (birdeye.py)    |  | (dexscreener.py)   |
+-----------------+  +---------------------+
```

- `BirdeyeProvider`（定义在 `birdeye.py`）继承 `DataProvider` 并实现全部抽象方法
- `DexScreenerProvider`（定义在 `dexscreener.py`）继承 `DataProvider` 并实现全部抽象方法

---

## 4. 依赖关系

### 外部第三方依赖

无。

### 内部模块依赖

无。

### 标准库依赖

| 模块  | 导入内容             | 用途               |
| ----- | -------------------- | ------------------ |
| `abc` | `ABC`, `abstractmethod` | 定义抽象基类和抽象方法 |

---

## 5. 代码逻辑流程

`base.py` 本身不包含可执行的业务逻辑，其代码流程极为简洁：

```
1. 从标准库 abc 导入 ABC 和 abstractmethod
        |
        v
2. 定义 DataProvider 类，继承 ABC
        |
        v
3. 声明抽象方法 get_trending_tokens(limit)
   - 方法体为 pass（由子类实现）
        |
        v
4. 声明抽象方法 get_token_history(session, address, days)
   - 方法体为 pass（由子类实现）
```

**关键设计决策：**

- 两个方法均为 `async` 异步方法，表明整个数据管道采用异步 I/O 架构，适用于高并发的 API 请求场景。
- 使用 `@abstractmethod` 装饰器确保子类必须实现这些方法，否则在实例化时会抛出 `TypeError`。
- `get_token_history` 接受外部传入的 `session` 参数，支持 HTTP 会话复用，有利于在批量请求时提升性能。
