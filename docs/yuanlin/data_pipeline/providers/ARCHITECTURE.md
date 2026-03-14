# providers 模块文档

## 概述
providers目录，包含相关功能模块。

## 文件结构
```
├── base.py
├── birdeye.py
└── dexscreener.py
```

## 关键文件说明
### base.py
- **主要类**:
  - `DataProvider`: 无文档字符串

### birdeye.py
- **主要类**:
  - `BirdeyeProvider`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串
- **详细文档**: 请参考 [birdeye.md](./birdeye.md) 查看完整文档

### dexscreener.py
- **主要类**:
  - `DexScreenerProvider`: 无文档字符串
- **关键函数**:
  - `__init__()`: 无文档字符串


## 依赖关系
- **外部依赖**:
  - `abc`
  - `aiohttp`
  - `asyncio`
  - `base`
  - `config`
  - `datetime`
  - `loguru`


## 架构图
```
providers 模块架构
(详细架构待补充)
```

## 数据流
数据流分析待补充。


## 使用示例
```python
# 使用 DataProvider 类
from providers.base import DataProvider

instance = DataProvider()
# 调用方法...
```
```python
# 使用 BirdeyeProvider 类
from providers.birdeye import BirdeyeProvider

instance = BirdeyeProvider()
# 调用方法...
```
```python
# 使用 DexScreenerProvider 类
from providers.dexscreener import DexScreenerProvider

instance = DexScreenerProvider()
# 调用方法...
```

## 注意事项
无特殊注意事项。

