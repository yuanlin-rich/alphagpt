# AlphaGPT 项目文档

## 项目概述

AlphaGPT 是一个基于强化学习的加密货币量化因子挖掘与自动交易系统，专注于 Solana 链上 Meme 币生态。系统的核心理念不是"预测模型"，而是一个"自动因子公式编写系统"——通过 Transformer 模型生成波兰表示法（Polish Notation）因子公式，经回测奖励评估后，将表现优秀的因子公式输入链上执行模块进行实盘交易。

**核心流程：** 数据采集 → 特征工程 → 公式生成 → 回测评估 → 风险过滤 → 链上执行 → 仓位管理/仪表盘监控

## 目录结构

```
alphagpt/
├── dashboard/              # Web 仪表盘（Streamlit）
│   ├── app.py              # 仪表盘主应用入口
│   ├── data_service.py     # 数据服务层
│   └── visualizer.py       # 可视化工具
│
├── data_pipeline/          # 数据管道
│   ├── config.py           # 全局配置中心
│   ├── data_manager.py     # 管道编排器
│   ├── db_manager.py       # 数据库管理层（asyncpg）
│   ├── fetcher.py          # 遗留数据获取器
│   ├── processor.py        # 数据清洗与因子计算
│   ├── run_pipeline.py     # 管道入口脚本
│   └── providers/          # 数据提供者子模块
│       ├── base.py         # 抽象基类 DataProvider
│       ├── birdeye.py      # Birdeye API 提供者
│       └── dexscreener.py  # DexScreener API 提供者
│
├── execution/              # 交易执行模块
│   ├── config.py           # 执行配置
│   ├── jupiter.py          # Jupiter DEX 聚合器
│   ├── rpc_handler.py      # Solana RPC 通信
│   ├── trader.py           # 交易编排器
│   └── utils.py            # 工具函数
│
├── lord/                   # 实验模块
│   └── experiment.py       # LoRD 正则化实验
│
├── model_core/             # AI/ML 核心模块
│   ├── alphagpt.py         # AlphaGPT Transformer 模型
│   ├── backtest.py         # 回测引擎
│   ├── config.py           # 模型配置
│   ├── data_loader.py      # 数据加载器
│   ├── engine.py           # 策略引擎（训练主循环）
│   ├── factors.py          # 因子工程
│   ├── ops.py              # 算子定义
│   └── vm.py               # 栈式虚拟机（公式执行）
│
├── strategy_manager/       # 策略管理模块
│   ├── __init__.py         # 包初始化
│   ├── config.py           # 策略超参数
│   ├── portfolio.py        # 仓位管理
│   ├── risk.py             # 风险控制
│   └── runner.py           # 策略运行器（核心循环）
│
├── times.py                # 独立研究脚本（A 股因子挖掘）
├── requirements.txt        # 核心依赖
└── requirements-optional.txt  # 可选依赖
```

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AlphaGPT 系统架构                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │  Birdeye API  │    │ DexScreener  │    │    Solana RPC (QuickNode)│  │
│  └──────┬───────┘    └──────┬───────┘    └────────────┬─────────────┘  │
│         │                   │                          │                │
│         ▼                   ▼                          │                │
│  ┌──────────────────────────────────┐                  │                │
│  │      data_pipeline               │                  │                │
│  │  ┌──────────┐  ┌─────────────┐  │                  │                │
│  │  │providers/ │  │ processor   │  │                  │                │
│  │  │ birdeye   │  │ (因子计算)   │  │                  │                │
│  │  │ dexscreen │  └─────────────┘  │                  │                │
│  │  └──────────┘  ┌─────────────┐  │                  │                │
│  │                │ db_manager   │  │                  │                │
│  │                │ (asyncpg)    │  │                  │                │
│  │                └──────┬──────┘  │                  │                │
│  └───────────────────────┼─────────┘                  │                │
│                          │                             │                │
│                          ▼                             │                │
│                 ┌─────────────────┐                    │                │
│                 │   PostgreSQL /   │                    │                │
│                 │   TimescaleDB   │                    │                │
│                 └────────┬────────┘                    │                │
│                          │                             │                │
│                          ▼                             │                │
│  ┌──────────────────────────────────┐                  │                │
│  │        model_core                │                  │                │
│  │  ┌──────────┐  ┌─────────────┐  │                  │                │
│  │  │data_loader│  │  factors    │  │                  │                │
│  │  └────┬─────┘  │ (特征工程)   │  │                  │                │
│  │       │        └─────────────┘  │                  │                │
│  │       ▼                         │                  │                │
│  │  ┌──────────┐  ┌─────────────┐  │                  │                │
│  │  │ alphagpt  │──│    vm       │  │                  │                │
│  │  │(Transformer)│ │ (栈式虚拟机) │  │                  │                │
│  │  └────┬─────┘  └─────────────┘  │                  │                │
│  │       │        ┌─────────────┐  │                  │                │
│  │       ├───────▶│  backtest   │  │                  │                │
│  │       │        │ (回测评估)   │  │                  │                │
│  │       ▼        └─────────────┘  │                  │                │
│  │  ┌──────────┐                   │                  │                │
│  │  │  engine   │ (REINFORCE 训练) │                  │                │
│  │  └────┬─────┘                   │                  │                │
│  └───────┼─────────────────────────┘                  │                │
│          │ best_meme_strategy.json                     │                │
│          ▼                                             │                │
│  ┌──────────────────────────────────┐                  │                │
│  │     strategy_manager             │                  │                │
│  │  ┌──────────┐  ┌─────────────┐  │                  │                │
│  │  │  runner   │──│   risk      │  │                  │                │
│  │  │ (策略循环) │  │ (风险控制)   │  │                  │                │
│  │  └────┬─────┘  └─────────────┘  │                  │                │
│  │       │        ┌─────────────┐  │                  │                │
│  │       ├───────▶│  portfolio   │  │                  │                │
│  │       │        │ (仓位管理)   │  │                  │                │
│  └───────┼────────┴─────────────┘  │                  │                │
│          │                          ▼                  │                │
│          │                 ┌──────────────────────┐    │                │
│          │                 │    execution          │    │                │
│          └────────────────▶│  ┌────────┐          │    │                │
│                            │  │ trader  │──┐      │    │                │
│                            │  └────────┘  │      │    │                │
│                            │  ┌────────┐  │      │    │                │
│                            │  │jupiter  │◀─┘      │◀───┘                │
│                            │  └────┬───┘         │                     │
│                            │       │  ┌────────┐ │                     │
│                            │       └─▶│rpc_hdlr│ │                     │
│                            │          └────────┘ │                     │
│                            └──────────────────────┘                     │
│                                       │                                │
│                                       ▼                                │
│                              Jupiter DEX API                           │
│                                                                         │
│  ┌──────────────────────────────────┐                                  │
│  │        dashboard                 │◀─── PostgreSQL + JSON files      │
│  │  Streamlit 实时监控仪表盘         │                                  │
│  └──────────────────────────────────┘                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 模块关系与数据流

### 核心数据流

```
Birdeye/DexScreener API
        │
        ▼
  data_pipeline ──────▶ PostgreSQL
        │                   │
        │                   ▼
        │             model_core
        │           (因子公式生成+回测)
        │                   │
        │                   ▼
        │         best_meme_strategy.json
        │                   │
        │                   ▼
        │          strategy_manager
        │         (信号生成+风险控制)
        │                   │
        │                   ▼
        │            execution
        │          (链上交易执行)
        │                   │
        ▼                   ▼
    dashboard ◀──── portfolio_state.json
  (实时监控)         strategy.log
```

### 模块间依赖关系

| 模块 | 依赖的内部模块 | 说明 |
|------|---------------|------|
| `data_pipeline` | 无 | 独立的数据采集层 |
| `model_core` | 无（通过 PostgreSQL 间接获取数据） | 独立的模型训练层 |
| `execution` | 无 | 独立的链上执行层 |
| `strategy_manager` | `data_pipeline`, `model_core`, `execution` | 核心编排层，串联所有模块 |
| `dashboard` | 无（通过 PostgreSQL 和共享文件间接获取数据） | 独立的监控层 |
| `lord` | 无 | 独立的实验研究模块 |

> `strategy_manager` 是唯一直接依赖其他模块的核心模块，充当系统的编排中枢。

### 外部依赖概览

| 类别 | 依赖 | 用途 |
|------|------|------|
| 深度学习 | `torch` | Transformer 模型训练/推理 |
| 数据处理 | `pandas`, `numpy` | 时序数据处理、因子计算 |
| 数据库 | `sqlalchemy`, `asyncpg`, `psycopg2-binary` | PostgreSQL 交互 |
| 异步网络 | `aiohttp` | API 数据获取 |
| 区块链 | `solders`, `solana`, `base58` | Solana 链上交互 |
| 仪表盘 | `streamlit`, `plotly` | Web 监控界面 |
| 工具类 | `python-dotenv`, `loguru`, `tqdm` | 配置/日志/进度 |

## 完整文档索引

### dashboard/ — Web 仪表盘

| 文档 | 对应源码 | 描述 |
|------|---------|------|
| [README.md](./dashboard/README.md) | — | 模块总览：架构、依赖、核心 API |
| [app.md](./dashboard/app.md) | `dashboard/app.py` | Streamlit 主应用入口，页面布局与自动刷新 |
| [data_service.md](./dashboard/data_service.md) | `dashboard/data_service.py` | 数据服务层，封装 PostgreSQL/Solana RPC/JSON/日志访问 |
| [visualizer.md](./dashboard/visualizer.md) | `dashboard/visualizer.py` | Plotly 可视化工具，PnL 分布图与市场散点图 |

### data_pipeline/ — 数据管道

| 文档 | 对应源码 | 描述 |
|------|---------|------|
| [README.md](./data_pipeline/README.md) | — | 模块总览：架构、依赖、核心 API |
| [config.md](./data_pipeline/config.md) | `data_pipeline/config.py` | 全局配置中心（DB、API Key、过滤阈值、并发参数） |
| [data_manager.md](./data_pipeline/data_manager.md) | `data_pipeline/data_manager.py` | 管道编排器，组合 DBManager 与 Providers |
| [db_manager.md](./data_pipeline/db_manager.md) | `data_pipeline/db_manager.py` | 数据库管理层，asyncpg 连接池、建表、upsert、批量插入 |
| [fetcher.md](./data_pipeline/fetcher.md) | `data_pipeline/fetcher.py` | 遗留 Birdeye 数据获取器（已被 providers/ 取代） |
| [processor.md](./data_pipeline/processor.md) | `data_pipeline/processor.py` | 数据清洗与量化因子计算（对数收益率、波动率、量价冲击、趋势） |
| [run_pipeline.md](./data_pipeline/run_pipeline.md) | `data_pipeline/run_pipeline.py` | 管道入口脚本 |

### data_pipeline/providers/ — 数据提供者

| 文档 | 对应源码 | 描述 |
|------|---------|------|
| [README.md](./data_pipeline/providers/README.md) | — | 子模块总览：策略模式、继承关系 |
| [base.md](./data_pipeline/providers/base.md) | `providers/base.py` | `DataProvider` 抽象基类，定义统一接口 |
| [birdeye.md](./data_pipeline/providers/birdeye.md) | `providers/birdeye.py` | Birdeye API 提供者，趋势代币 + OHLCV 历史数据 |
| [dexscreener.md](./data_pipeline/providers/dexscreener.md) | `providers/dexscreener.py` | DexScreener API 提供者，批量代币详情查询 |

### execution/ — 交易执行

| 文档 | 对应源码 | 描述 |
|------|---------|------|
| [README.md](./execution/README.md) | — | 模块总览：架构、依赖、核心 API |
| [config.md](./execution/config.md) | `execution/config.py` | 执行配置（RPC URL、钱包密钥、滑点、Mint 地址） |
| [jupiter.md](./execution/jupiter.md) | `execution/jupiter.py` | Jupiter V6 DEX 聚合器客户端（报价 + Swap） |
| [rpc_handler.md](./execution/rpc_handler.md) | `execution/rpc_handler.py` | QuickNode RPC 通信（余额、发送交易、确认） |
| [trader.md](./execution/trader.md) | `execution/trader.py` | 交易编排器，组合 RPC + Jupiter 的买卖全链路 |
| [utils.md](./execution/utils.md) | `execution/utils.py` | 工具函数（代币精度查询） |

### lord/ — 实验模块

| 文档 | 对应源码 | 描述 |
|------|---------|------|
| [README.md](./lord/README.md) | — | 模块总览：LoRD 正则化实验 |
| [experiment.md](./lord/experiment.md) | `lord/experiment.py` | Newton-Schulz 低秩正则化对 Grokking 的消融实验 |

### model_core/ — AI/ML 核心

| 文档 | 对应源码 | 描述 |
|------|---------|------|
| [README.md](./model_core/README.md) | — | 模块总览：架构、依赖、核心 API |
| [alphagpt.md](./model_core/alphagpt.md) | `model_core/alphagpt.py` | AlphaGPT Transformer 模型（LoopedTransformer、MTPHead、优化器） |
| [backtest.md](./model_core/backtest.md) | `model_core/backtest.py` | Meme 币回测引擎（信号→交易→评分） |
| [config.md](./model_core/config.md) | `model_core/config.py` | 模型配置（维度、序列长度、DB URL） |
| [data_loader.md](./model_core/data_loader.md) | `model_core/data_loader.py` | 数据加载器（PostgreSQL → 张量 + 特征工程） |
| [engine.md](./model_core/engine.md) | `model_core/engine.py` | 策略引擎（REINFORCE 训练主循环） |
| [factors.md](./model_core/factors.md) | `model_core/factors.py` | 因子工程（MemeIndicators、6/12 维特征空间） |
| [ops.md](./model_core/ops.md) | `model_core/ops.py` | 算子定义（12 个 JIT 编译运算符） |
| [vm.md](./model_core/vm.md) | `model_core/vm.py` | 栈式虚拟机（波兰表示法公式执行） |

### strategy_manager/ — 策略管理

| 文档 | 对应源码 | 描述 |
|------|---------|------|
| [README.md](./strategy_manager/README.md) | — | 模块总览：架构、依赖、核心 API |
| [config.md](./strategy_manager/config.md) | `strategy_manager/config.py` | 策略超参数（仓位上限、止损止盈、AI 信号阈值） |
| [portfolio.md](./strategy_manager/portfolio.md) | `strategy_manager/portfolio.py` | 仓位管理（Position 数据类 + JSON 持久化） |
| [risk.md](./strategy_manager/risk.md) | `strategy_manager/risk.py` | 风险控制（流动性检查、蜜罐检测、仓位计算） |
| [runner.md](./strategy_manager/runner.md) | `strategy_manager/runner.py` | 策略运行器（60s 主循环、4 级退出策略、入场扫描） |

### 根目录文件

| 文档 | 对应源码 | 描述 |
|------|---------|------|
| [times.md](./times.md) | `times.py` | 独立研究脚本：A 股 ETF 因子挖掘 + REINFORCE 训练 + 样本外回测 |

## 环境要求

- **Python**: 3.10+（推荐 3.11）
- **数据库**: PostgreSQL / TimescaleDB
- **外部 API**: Birdeye API Key, QuickNode RPC URL
- **区块链**: Solana 钱包私钥（用于交易执行）
- **环境变量**: 通过 `.env` 文件配置（`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`, `QUICKNODE_RPC_URL`, `SOLANA_PRIVATE_KEY`, `BIRDEYE_API_KEY` 等）
