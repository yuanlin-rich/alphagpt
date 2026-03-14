# BirdeyeProvider 模块文档

## 概述
`BirdeyeProvider` 是 AlphaGPT 项目中的数据提供者类，专门用于从 **Birdeye**（加密货币数据平台）获取市场数据。该类继承自 `DataProvider` 基类，使用异步 HTTP 客户端与 Birdeye 公共 API 交互，为项目提供实时市场数据和历史价格数据。

## 文件位置
- 源代码: `data_pipeline/providers/birdeye.py`
- 文档: `docs/yuanlin/data_pipeline/providers/birdeye.md`

## 类定义

### BirdeyeProvider
继承自 `DataProvider`（位于 `data_pipeline.providers.base`），使用异步 HTTP 客户端（`aiohttp`）与 Birdeye 公共 API 交互。

**初始化方法**:
```python
def __init__(self):
    self.base_url = "https://public-api.birdeye.so"
    self.headers = {
        "X-API-KEY": Config.BIRDEYE_API_KEY,
        "accept": "application/json"
    }
    self.semaphore = asyncio.Semaphore(Config.CONCURRENCY)
```

**配置参数**:
- `base_url`: Birdeye 公共 API 基础地址
- `headers`: 请求头，包含 API 密钥
- `semaphore`: 异步信号量，用于控制并发请求数

## 核心功能

### 1. 获取趋势代币（`get_trending_tokens`）

**方法签名**:
```python
async def get_trending_tokens(self, limit=100)
```

**功能描述**:
获取当前市场上按排名排序的热门代币列表。

**API 端点**:
- `/defi/token_trending`

**请求参数**:
- `sort_by`: "rank"（按排名排序）
- `sort_type`: "asc"（升序）
- `offset`: "0"
- `limit`: 指定返回数量（默认 100）

**返回数据**:
返回一个字典列表，每个字典包含以下字段:
- `address`: 代币合约地址
- `symbol`: 代币符号
- `name`: 代币名称
- `decimals`: 小数位数
- `liquidity`: 流动性
- `fdv`: 完全稀释估值

**错误处理**:
- HTTP 状态码非 200 时记录错误并返回空列表
- 异常发生时记录异常信息并返回空列表

### 2. 获取代币历史 OHLCV 数据（`get_token_history`）

**方法签名**:
```python
async def get_token_history(self, session, address, days=Config.HISTORY_DAYS)
```

**功能描述**:
获取指定代币地址在给定时间范围内的 K 线数据（开盘、最高、最低、收盘、成交量）。

**API 端点**:
- `/defi/ohlcv`

**请求参数**:
- `address`: 代币合约地址
- `type`: 时间框架（从 `Config.TIMEFRAME` 获取）
- `time_from`: 开始时间戳
- `time_to`: 结束时间戳

**时间范围计算**:
```python
time_to = int(datetime.now().timestamp())
time_from = int((datetime.now() - timedelta(days=days)).timestamp())
```

**数据处理**:
将原始数据转换为统一的元组格式：
```python
(
    datetime.fromtimestamp(item['unixTime']),  # 时间
    address,                                   # 代币地址
    float(item['o']),                          # 开盘价
    float(item['h']),                          # 最高价
    float(item['l']),                          # 最低价
    float(item['c']),                          # 收盘价
    float(item['v']),                          # 成交量
    0.0,                                       # 流动性（占位符）
    0.0,                                       # FDV（占位符）
    'birdeye'                                  # 数据来源标记
)
```

**错误处理**:
- HTTP 429（速率限制）: 等待 2 秒后递归重试
- 其他错误: 返回空列表
- 异常: 记录错误信息并返回空列表

## 技术特点

### 异步并发控制
- 使用 `asyncio.Semaphore` 限制同时请求数，防止过度并发
- 并发数由 `Config.CONCURRENCY` 配置控制

### 配置驱动
- API 密钥: `Config.BIRDEYE_API_KEY`
- 并发数: `Config.CONCURRENCY`
- 历史天数: `Config.HISTORY_DAYS`
- 时间框架: `Config.TIMEFRAME`

### 日志记录
- 使用 `loguru` 记录错误和警告信息
- 详细记录 API 错误、网络异常等信息

### 异常处理
- 对网络错误、API 错误等有完备的异常捕获
- 降级处理：返回空列表而不是抛出异常
- 自动重试机制：针对速率限制进行智能重试

## 在数据管道中的角色

### 数据源提供者
`BirdeyeProvider` 作为 AlphaGPT 项目的关键数据源之一，提供：
1. **实时市场数据**: 热门代币列表，用于代币筛选和趋势分析
2. **历史价格数据**: OHLCV 数据，用于回测、因子计算和技术分析

### 数据集成
- 与其他数据提供者（如 `DexScreenerProvider`）协同工作
- 提供标准化的数据格式，便于后续处理和分析
- 支持多数据源融合，提高数据质量和可靠性

### 应用场景
1. **代币筛选**: 基于趋势代币列表进行初步筛选
2. **回测系统**: 提供历史价格数据用于策略回测
3. **因子计算**: 基于价格数据计算技术指标和量化因子
4. **市场监控**: 实时监控代币价格和流动性变化

## 依赖关系

### 内部依赖
- `data_pipeline.providers.base.DataProvider`: 基类
- `data_pipeline.config.Config`: 配置管理

### 外部依赖
- `aiohttp`: 异步 HTTP 客户端
- `asyncio`: 异步编程框架
- `datetime`: 日期时间处理
- `loguru`: 日志记录

## 使用示例

### 获取趋势代币
```python
from data_pipeline.providers.birdeye import BirdeyeProvider

async def example_trending():
    provider = BirdeyeProvider()
    trending_tokens = await provider.get_trending_tokens(limit=50)
    for token in trending_tokens:
        print(f"{token['symbol']} ({token['name']}): {token['address']}")
```

### 获取代币历史数据
```python
from data_pipeline.providers.birdeye import BirdeyeProvider
import aiohttp

async def example_history():
    provider = BirdeyeProvider()
    async with aiohttp.ClientSession(headers=provider.headers) as session:
        address = "0x...代币地址..."
        history_data = await provider.get_token_history(session, address, days=30)
        for data_point in history_data:
            timestamp, addr, open_price, high, low, close, volume, _, _, source = data_point
            print(f"{timestamp}: {close} USD")
```

## 注意事项

### API 限制
- Birdeye API 可能有速率限制，合理配置 `Config.CONCURRENCY`
- 建议使用有效的 API 密钥以获得更好的服务

### 数据质量
- 部分代币可能缺少某些字段（如 `symbol`, `name`），代码中已做默认值处理
- 历史数据的时间框架应与策略需求匹配

### 错误处理
- 在网络不稳定的环境中，建议增加重试机制
- 对于关键数据，建议实现数据验证和清洗逻辑

## 版本历史
- 初始版本：提供基本的趋势代币和历史数据获取功能
- 待优化：增加更多数据字段、改进错误处理、添加缓存机制

---

**文档更新日期**: 2026-03-14
**维护者**: AlphaGPT 开发团队
**相关文档**: [ARCHITECTURE.md](./ARCHITECTURE.md)