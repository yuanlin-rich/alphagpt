# run_pipeline.py 文档

## 1. 文件概述

`run_pipeline.py` 是 `data_pipeline` 模块的入口脚本，负责启动和执行完整的数据同步管道。它是一个轻量级的启动器，执行前置校验（API KEY 检查）后，初始化 `DataManager` 并调用其管道方法完成数据同步。该文件支持直接以脚本方式运行（`python -m data_pipeline.run_pipeline`），也可被其他模块作为函数调用。

## 2. 类与函数说明

### 函数：`async main()`

- **用途**：数据管道的异步入口函数，编排初始化、执行、清理的完整生命周期。
- **参数**：无
- **返回值**：`None`
- **详细逻辑**：
  1. 检查 `Config.BIRDEYE_API_KEY` 是否为空，若为空则记录错误并直接返回
  2. 创建 `DataManager` 实例
  3. 在 `try` 块中：
     - 调用 `manager.initialize()` 初始化数据库连接和表结构
     - 调用 `manager.pipeline_sync_daily()` 执行完整的日级数据同步
  4. 在 `except` 块中：捕获所有异常，使用 `logger.exception()` 记录完整堆栈
  5. 在 `finally` 块中：确保调用 `manager.close()` 关闭数据库连接

### 模块级入口

```python
if __name__ == "__main__":
    asyncio.run(main())
```

- 当脚本被直接执行时，使用 `asyncio.run()` 启动事件循环并运行 `main()` 协程。

## 3. 调用关系图

```
+-----------------------------------------------------------+
|                     run_pipeline.py                         |
+-----------------------------------------------------------+
|                                                           |
|  main()                                                   |
|    |                                                      |
|    |-- [前置检查] Config.BIRDEYE_API_KEY 是否存在?          |
|    |   +-- 不存在: logger.error() -> return                |
|    |                                                      |
|    |-- DataManager()  实例化                               |
|    |                                                      |
|    |-- try:                                               |
|    |   |-- manager.initialize()                           |
|    |   |   |-- db.connect()                               |
|    |   |   +-- db.init_schema()                           |
|    |   |                                                  |
|    |   +-- manager.pipeline_sync_daily()                  |
|    |       |-- birdeye.get_trending_tokens()              |
|    |       |-- [过滤]                                     |
|    |       |-- db.upsert_tokens()                         |
|    |       |-- birdeye.get_token_history() x N            |
|    |       +-- db.batch_insert_ohlcv() x M               |
|    |                                                      |
|    |-- except:                                            |
|    |   +-- logger.exception("Pipeline crashed")           |
|    |                                                      |
|    +-- finally:                                           |
|        +-- manager.close()                                |
|            +-- db.close()                                 |
|                                                           |
|  if __name__ == "__main__":                               |
|    +-- asyncio.run(main())                                |
+-----------------------------------------------------------+

调用链路 (完整管道):
  run_pipeline.main()
       |
       v
  DataManager.initialize()
       |
       v
  DataManager.pipeline_sync_daily()
       |
       +---> BirdeyeProvider.get_trending_tokens()
       |         |
       |         v
       |     Birdeye API  /defi/token_trending
       |
       +---> DBManager.upsert_tokens()
       |         |
       |         v
       |     PostgreSQL  tokens 表
       |
       +---> BirdeyeProvider.get_token_history()  (并发)
       |         |
       |         v
       |     Birdeye API  /defi/ohlcv
       |
       +---> DBManager.batch_insert_ohlcv()  (批量)
                 |
                 v
             PostgreSQL  ohlcv 表
```

## 4. 依赖关系

### 外部第三方依赖

| 模块 | 用途 |
|------|------|
| `asyncio` | 标准库，事件循环管理（`asyncio.run`） |
| `loguru` | 日志记录 |

### 内部模块依赖

| 模块 | 导入对象 | 用途 |
|------|----------|------|
| `.data_manager` | `DataManager` | 数据管道的核心编排器 |
| `.config` | `Config` | 读取 `BIRDEYE_API_KEY` 进行前置校验 |

## 5. 代码逻辑流程

```
程序启动 (python -m data_pipeline.run_pipeline)
  |
  v
asyncio.run(main())
  |
  v
[前置校验] Config.BIRDEYE_API_KEY 是否非空?
  |-- 为空:
  |   |-- logger.error("BIRDEYE_API_KEY is missing in .env")
  |   +-- 提前返回, 管道不执行
  |
  +-- 非空: 继续执行
  |
  v
创建 DataManager 实例
  |-- 内部创建 DBManager, BirdeyeProvider, DexScreenerProvider
  |
  v
[try 块]
  |
  |-- manager.initialize()
  |   |-- 建立 PostgreSQL 连接池
  |   +-- 创建/确认 tokens 表和 ohlcv 表
  |
  +-- manager.pipeline_sync_daily()
      |-- 获取趋势代币列表
      |-- 按流动性/FDV 过滤
      |-- 代币信息写入数据库
      |-- 批量并发拉取 OHLCV 数据
      +-- 批量写入 K线数据到数据库
  |
  v
[except 块] 捕获任何异常
  +-- logger.exception() 输出完整错误堆栈
  |
  v
[finally 块] 无论成功或失败都执行
  +-- manager.close()
      +-- 关闭数据库连接池, 释放资源
  |
  v
程序结束
```

> **健壮性设计**：
> - API KEY 缺失时快速失败，避免后续无意义的数据库连接和 API 调用
> - `try/except/finally` 三段式确保异常被记录且资源被正确释放
> - `logger.exception()` 会自动输出异常的完整堆栈信息，便于问题排查
