# data_pipeline 模块说明

本模块用于按日同步链上代币的元数据与 OHLCV K线到本地 PostgreSQL/TimescaleDB 数据库（当前聚焦 Solana）。它由配置、数据提供方、数据库管理、流程编排和数据处理五部分组成。

- 配置：data_pipeline/config.py:6
- 数据库管理：data_pipeline/db_manager.py:5
- 数据提供方（Birdeye / DexScreener）：data_pipeline/providers/
- 管道编排：data_pipeline/data_manager.py:9
- 入口：data_pipeline/run_pipeline.py:6
- 数据处理工具（可选）：data_pipeline/processor.py:5

## 目录结构

- config.py：环境变量与运行参数配置（数据库、时间粒度、过滤阈值、并发等）
- db_manager.py：Postgres/Timescale 表结构初始化、批量写入与 token upsert
- data_manager.py：日常同步任务的编排（发现 → 过滤 → 入库 → 拉取 K 线 → 批量写入）
- providers/
  - base.py：数据提供方的抽象接口
  - birdeye.py：基于 Birdeye Public API 的实现（热度与 OHLCV）
  - dexscreener.py：DexScreener 的批量详情（当前未在主流程中使用）
- processor.py：OHLCV 的清洗与基础因子计算（当前主流程未调用）
- run_pipeline.py：命令式入口脚本

## 配置

见 data_pipeline/config.py:6

- 数据库连接（支持 .env 覆盖）
  - DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME
  - 组合生成 DSN：Config.DB_DSN（postgresql://...）
- 链与时间粒度
  - CHAIN = "solana"
  - TIMEFRAME = "1m"（也支持 15min）
- 过滤阈值（候选代币）
  - MIN_LIQUIDITY_USD = 500000.0
  - MIN_FDV = 10000000.0
  - MAX_FDV = inf（用于剔除超大市值代币，关注早期成长）
- 数据源配置
  - BIRDEYE_API_KEY（必需，来自 .env）
  - BIRDEYE_IS_PAID = True（影响拉取数量）
  - USE_DEXSCREENER = False（当前未启用）
- 并发与历史范围
  - CONCURRENCY = 20（BirdeyeProvider 内部使用信号量限流）
  - HISTORY_DAYS = 7（K 线历史窗口）

## 数据库设计与管理

见 data_pipeline/db_manager.py:5

- 初始化连接池：connect()（db_manager.py:9-12）
- 关闭连接池：close()（db_manager.py:14-16）
- 表结构初始化：init_schema()（db_manager.py:18-55）
  - tokens 表：address 主键，symbol/name/decimals/chain，last_updated 默认 NOW()
  - ohlcv 表：time+address 复合主键，含 open/high/low/close/volume/liquidity/fdv/source
  - 尝试创建 Timescale Hypertable：create_hypertable('ohlcv', 'time')（若无扩展则捕获并警告）
  - 辅助索引：idx_ohlcv_address（address）
- token upsert：upsert_tokens()（db_manager.py:55-64）
  - 使用 INSERT ... ON CONFLICT 按 address 更新 symbol 与 last_updated
- 批量写入 OHLCV：batch_insert_ohlcv()（db_manager.py:66-80）
  - 使用 asyncpg.copy_records_to_table 提升导入性能
  - 忽略 UniqueViolation（复合主键去重）并记录错误

## 数据提供方接口与实现

抽象接口：data_pipeline/providers/base.py:3

- get_trending_tokens(limit)
- get_token_history(session, address, days)

### BirdeyeProvider

见 data_pipeline/providers/birdeye.py:8

- 基础设置
  - base_url = https://public-api.birdeye.so（birdeye.py:10）
  - 头部携带 X-API-KEY（来自 Config）（birdeye.py:11-14）
  - 并发控制：asyncio.Semaphore(Config.CONCURRENCY)（birdeye.py:15）
- 热度发现：get_trending_tokens(limit)（birdeye.py:17-49）
  - 解析返回字段：address/symbol/name/decimals/liquidity/fdv
  - 非 200 状态或异常时返回空列表并记录日志
- K 线拉取：get_token_history(session, address, days)（birdeye.py:51-94）
  - 以 Config.TIMEFRAME 粒度请求 [time_from, time_to]
  - 将返回 items 格式化为批量插入记录（含 source='birdeye'）
  - 429 限流：等待 2 秒后递归重试（birdeye.py:86-89）

### DexScreenerProvider（辅助，当前未用于主流程）

见 data_pipeline/providers/dexscreener.py:6

- get_token_details_batch(session, addresses)（dexscreener.py:14-48）
  - 以 30 个地址为一批请求，筛选目标链（Config.CHAIN）
  - 为每个 baseToken 选择最高 liquidity 的交易对作为代表
- get_trending_tokens / get_token_history（占位，未实现实际拉取）

## 管道编排（每日同步）

见 data_pipeline/data_manager.py:9

pipeline_sync_daily()（data_manager.py:22-70）执行以下步骤：

1) 发现候选代币（Step 1）
   - 调整 limit：付费 500，否则 100（data_manager.py:24）
   - 使用 BirdeyeProvider.get_trending_tokens（data_manager.py:25）
2) 过滤（流动性与 FDV）（data_manager.py:29-38）
   - liq < MIN_LIQUIDITY_USD → 剔除
   - fdv < MIN_FDV 或 fdv > MAX_FDV → 剔除
3) 写入/更新 tokens（data_manager.py:46-48）
   - upsert_tokens：address/symbol/name/decimals/chain
4) 拉取 OHLCV（Step 4）（data_manager.py:49-69）
   - 复用 Birdeye 的 session；为每个代币创建任务（data_manager.py:51-55）
   - 分批 gather，batch_size=20（data_manager.py:56-63）
   - 扁平化结果并批量写入 ohlcv（data_manager.py:65-67）
5) 汇总日志与完成（data_manager.py:70）

## 运行说明

入口脚本：data_pipeline/run_pipeline.py:6

前置条件：
- PostgreSQL 可用；如需 Hypertable 功能，安装 TimescaleDB 扩展（非必需）
- .env 设置 BIRDEYE_API_KEY 与数据库连接参数

示例 .env（请勿提交到版本库）：

```
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=crypto_quant
BIRDEYE_API_KEY=your_birdeye_key
```

运行（以模块方式）：

```
python -m data_pipeline.run_pipeline
```

- 若未设置 BIRDEYE_API_KEY，脚本会直接报错并退出（run_pipeline.py:7-9）

## 数据清洗与因子（可选工具）

见 data_pipeline/processor.py:5

- clean_ohlcv(df)（processor.py:6-21）
  - 去重（time,address）、时间排序、OHLCV 缺失补全、过滤极小价格
- add_basic_factors(df)（processor.py:23-42）
  - 日志收益、历史波动率（20 窗）、成交量冲击（相对 20 均值）、价格趋势（60 均线比较）

当前主流程未调用该模块，可用于下游研究或 ETL 后置处理。

## 日志与错误处理

- loguru 统一日志输出（各模块 logger.*）
- Birdeye 429 限流有重试逻辑（birdeye.py:86-89）
- 批量写入忽略唯一键冲突（db_manager.py:77-78）并记录其他异常（db_manager.py:79-80）

## 其他说明

- fetcher.py（BirdeyeFetcher）为早期/备用实现，使用 Config.BASE_URL（当前 Config 未定义该字段）；该类未被 DataManager 使用。
- DexScreenerProvider 主要提供批量详情能力，当前管道未启用。

## 关键代码引用

- 配置：data_pipeline/config.py:6-22
- DB 连接与建表：data_pipeline/db_manager.py:9-55
- 批量写入：data_pipeline/db_manager.py:66-80
- DataManager 流程：data_pipeline/data_manager.py:22-70
- Birdeye 热度与 K 线：data_pipeline/providers/birdeye.py:17-49, 51-94
- DexScreener 批量详情：data_pipeline/providers/dexscreener.py:14-48
- 入口：data_pipeline/run_pipeline.py:6-22
- 清洗与因子：data_pipeline/processor.py:6-21, 23-42

## 安全与合规

- API Key 请通过 .env 提供并避免提交到版本库。
- 注意第三方 API 的速率限制与使用条款。
- 如启用 TimescaleDB，请确保数据库具备相应扩展并有权限执行 create_hypertable。