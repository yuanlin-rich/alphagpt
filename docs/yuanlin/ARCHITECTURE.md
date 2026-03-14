# AlphaGPT (Root Directory) 模块文档

## 概述
AlphaGPT项目根目录，包含整个加密量化系统的入口和配置。

## 文件结构
```
├── assets/
├── dashboard/
├── data_pipeline/
├── execution/
├── lord/
├── model_core/
├── paper/
├── strategy_manager/
├── generate_directory_docs.py
├── times.py
└── CATREADME.md
└── LICENSE
└── README.md
└── requirements-optional.txt
└── requirements.txt
```

## 关键文件说明
### generate_directory_docs.py
- **主要类**:
  - `PythonFileAnalyzer`: Analyzes Python files to extract structure and dependencies.
  - `DirectoryAnalyzer`: Analyzes a directory and generates documentation.
- **关键函数**:
  - `should_exclude()`: Check if a path should be excluded from processing.
  - `create_mirror_directories()`: Create mirror directory structure in docs/yuanlin.
  - `main()`: Main function to generate directory documentation.
  - `generate_root_overview()`: Generate root overview document with project-wide architecture.
  - `__init__()`: 无文档字符串
  - `analyze()`: Parse Python file and extract information.
  - `_extract_imports()`: Extract import statements from AST.
  - `_extract_classes()`: Extract class definitions from AST.
  - `_extract_functions()`: Extract function definitions from AST.
  - `_extract_constants()`: Extract constant assignments (uppercase variables) from AST.
  - `__init__()`: 无文档字符串
  - `analyze_directory()`: Analyze the directory structure and Python files.
  - `generate_documentation()`: Generate Markdown documentation for the directory.
  - `_generate_overview()`: Generate overview section based on directory analysis.
  - `_generate_file_tree()`: Generate ASCII file tree representation.
  - `_generate_file_descriptions()`: Generate descriptions for each Python file.
  - `_generate_dependencies()`: Generate dependency analysis.
  - `_generate_architecture_diagram()`: Generate text-based architecture diagram.
  - `_generate_data_flow()`: Generate data flow description.
  - `_generate_usage_examples()`: Generate usage examples based on actual code.
  - `_generate_notes()`: Generate important notes for the directory.
- **重要常量**:
  - `PROJECT_ROOT`: Path(__file__).parent
  - `DOCS_ROOT`: PROJECT_ROOT / 'docs' / 'yuanlin'
  - `EXCLUDE_DIRS`: {'.git', '__pycache__', 'venv', '.venv', 'env', 'node_modules', 'docs', 'tests', 'test', '__pycache__', '.idea', '.vscode'}
  - `PYTHON_EXTENSIONS`: {'.py'}

### times.py
- **主要类**:
  - `AlphaGPT`: 无文档字符串
  - `DataEngine`: 无文档字符串
  - `DeepQuantMiner`: 无文档字符串
- **关键函数**:
  - `_ts_delay()`: 无文档字符串
  - `_ts_delta()`: 无文档字符串
  - `_ts_zscore()`: 无文档字符串
  - `_ts_decay_linear()`: 无文档字符串
  - `final_reality_check()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `forward()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `load()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `get_strict_mask()`: 无文档字符串
  - `solve_one()`: 无文档字符串
  - `solve_batch()`: 无文档字符串
  - `backtest()`: 无文档字符串
  - `train()`: 无文档字符串
  - `decode()`: 无文档字符串
  - `robust_norm()`: 无文档字符串
  - `_parse()`: 无文档字符串
- **重要常量**:
  - `TS_TOKEN`: '20af39742f461b1edc79ff0aec09c8940265babe0c6733e7bf358078'
  - `INDEX_CODE`: '511260.SH'
  - `START_DATE`: '20150101'
  - `END_DATE`: '20240101'
  - `TEST_END_DATE`: '20250101'
  - `BATCH_SIZE`: 1024
  - `TRAIN_ITERATIONS`: 400
  - `MAX_SEQ_LEN`: 8
  - `COST_RATE`: 0.0005
  - `DATA_CACHE_PATH`: 'data_cache_final.parquet'
  - `DEVICE`: torch.device('cuda' if torch.cuda.is_available() else 'cpu')
  - `OPS_CONFIG`: [('ADD', lambda x, y: x + y, 2), ('SUB', lambda x, y: x - y, 2), ('MUL', lambda x, y: x * y, 2), ('DIV', lambda x, y: x / (y + 1e-06 * torch.sign(y)), 2), ('NEG', lambda x: -x, 1), ('ABS', lambda x: torch.abs(x), 1), ('SIGN', lambda x: torch.sign(x), 1), ('DELTA5', lambda x: _ts_delta(x, 5), 1), ('MA20', lambda x: _ts_decay_linear(x, 20), 1), ('STD20', lambda x: _ts_zscore(x, 20), 1), ('TS_RANK20', lambda x: _ts_zscore(x, 20), 1)]
  - `FEATURES`: ['RET', 'RET5', 'VOL_CHG', 'V_RET', 'TREND']
  - `VOCAB`: FEATURES + [cfg[0] for cfg in OPS_CONFIG]
  - `VOCAB_SIZE`: len(VOCAB)
  - `OP_FUNC_MAP`: {i + len(FEATURES): cfg[1] for i, cfg in enumerate(OPS_CONFIG)}
  - `OP_ARITY_MAP`: {i + len(FEATURES): cfg[2] for i, cfg in enumerate(OPS_CONFIG)}
  - `B`: open_slots.shape[0]
  - `B`: token_seqs.shape[0]
  - `B`: BATCH_SIZE


## 依赖关系
- **外部依赖**:
  - `ast`
  - `math`
  - `matplotlib`
  - `numpy`
  - `os`
  - `pandas`
  - `pathlib`
  - `re`
  - `sys`
  - `textwrap`
  - `torch`
  - `tqdm`
  - `tushare`
  - `typing`


## 架构图
```
AlphaGPT 整体架构
    ├── dashboard/ (仪表板)
    ├── data_pipeline/ (数据管道)
    ├── execution/ (交易执行)
    ├── model_core/ (模型核心)
    ├── strategy_manager/ (策略管理)
    └── lord/ (实验模块)

系统流程:
数据管道 → 模型核心 → 策略管理 → 交易执行 → 仪表板监控
```

## 数据流
数据流分析待补充。


## 使用示例
```python
# 使用 PythonFileAnalyzer 类
from alphagpt.generate_directory_docs import PythonFileAnalyzer

instance = PythonFileAnalyzer()
# 调用方法...
```
```python
# 使用 AlphaGPT 类
from alphagpt.times import AlphaGPT

instance = AlphaGPT()
# 调用方法...
```

## 注意事项
无特殊注意事项。

