# data_pipeline 模块文档

## 概述
数据管道模块，负责从外部API获取、处理和存储市场数据。

## 文件结构
```
├── providers/
├── config.py
├── data_manager.py
├── db_manager.py
├── fetcher.py
├── processor.py
└── run_pipeline.py
```

## 关键文件说明
### config.py
- **主要类**:
  - `Config`: 无文档字符串
- **重要常量**:
  - `DB_USER`: os.getenv('DB_USER', 'postgres')
  - `DB_PASSWORD`: os.getenv('DB_PASSWORD', 'password')
  - `DB_HOST`: os.getenv('DB_HOST', 'localhost')
  - `DB_PORT`: os.getenv('DB_PORT', '5432')
  - `DB_NAME`: os.getenv('DB_NAME', 'crypto_quant')
  - `DB_DSN`: f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
  - `CHAIN`: 'solana'
  - `TIMEFRAME`: '1m'
  - `MIN_LIQUIDITY_USD`: 500000.0
  - `MIN_FDV`: 10000000.0
  - `MAX_FDV`: float('inf')
  - `BIRDEYE_API_KEY`: os.getenv('BIRDEYE_API_KEY', '')
  - `BIRDEYE_IS_PAID`: True
  - `USE_DEXSCREENER`: False
  - `CONCURRENCY`: 20
  - `HISTORY_DAYS`: 7

### data_manager.py
- **主要类**:
  - `DataManager`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串

### db_manager.py
- **主要类**:
  - `DBManager`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串

### fetcher.py
- **主要类**:
  - `BirdeyeFetcher`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串

### processor.py
- **主要类**:
  - `DataProcessor`: 无文档字符串
- **关键函数**:
  - `clean_ohlcv()`: 无文档字符串
  - `add_basic_factors()`: 无文档字符串

### run_pipeline.py


## 依赖关系
- **外部依赖**:
  - `aiohttp`
  - `asyncio`
  - `asyncpg`
  - `config`
  - `data_manager`
  - `datetime`
  - `db_manager`
  - `dotenv`
  - `loguru`
  - `numpy`
  - `os`
  - `pandas`
  - `providers`


## 架构图
```
数据管道架构
    ├── run_pipeline.py (主运行器)
    ├── fetcher.py (数据获取)
    ├── processor.py (数据处理)
    ├── db_manager.py (数据库管理)
    └── providers/ (数据提供商)
        ├── base.py (抽象基类)
        ├── birdeye.py (Birdeye API)
        └── dexscreener.py (DexScreener API)

数据流向:
外部API → fetcher → processor → db_manager → 数据库
```

## 数据流
1. 从多个数据提供商获取实时市场数据
2. 清洗和标准化数据格式
3. 计算技术指标和因子
4. 存储到数据库供其他模块使用
5. 定期更新数据保持新鲜度

## 使用示例
```python
# 使用 Config 类
from data_pipeline.config import Config

instance = Config()
# 调用方法...
```
```python
# 使用 DataManager 类
from data_pipeline.data_manager import DataManager

instance = DataManager()
# 调用方法...
```
```python
# 使用 DBManager 类
from data_pipeline.db_manager import DBManager

instance = DBManager()
# 调用方法...
```
```python
# 使用 BirdeyeFetcher 类
from data_pipeline.fetcher import BirdeyeFetcher

instance = BirdeyeFetcher()
# 调用方法...
```
```python
# 使用 DataProcessor 类
from data_pipeline.processor import DataProcessor

instance = DataProcessor()
# 调用方法...
```

## 注意事项
- 需要配置API密钥
- 依赖外部数据提供商
- 数据库连接需要正确配置
