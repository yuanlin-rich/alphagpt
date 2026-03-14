# AlphaGPT 目录文档

本目录包含 AlphaGPT 项目的模块架构文档，自动生成于 `docs/yuanlin/` 目录树。

## 文档结构

每个工程目录在 `docs/yuanlin/` 下都有对应的镜像目录，包含 `ARCHITECTURE.md` 文件：

```
docs/yuanlin/
├── ARCHITECTURE_OVERVIEW.md    # 项目整体架构总览
├── ARCHITECTURE.md             # 根目录文档
├── dashboard/                  # 仪表板模块文档
├── data_pipeline/              # 数据管道文档
├── execution/                  # 交易执行文档
├── model_core/                 # 模型核心文档
├── strategy_manager/           # 策略管理文档
├── lord/                       # 实验模块文档
├── assets/                     # 资源目录文档
└── paper/                      # 论文目录文档
```

## 文档内容

每个 `ARCHITECTURE.md` 文件包含：

1. **概述** - 模块功能简介
2. **文件结构** - 目录下的文件列表
3. **关键文件说明** - Python 文件分析（类、函数、常量）
4. **依赖关系** - 内部和外部依赖
5. **架构图** - 文本描述的模块架构
6. **数据流** - 处理流程说明
7. **使用示例** - 代码使用示例
8. **注意事项** - 重要提示

## 生成脚本

文档由 `generate_directory_docs.py` 脚本自动生成：

```bash
python generate_directory_docs.py
```

### 脚本功能

- 递归遍历项目目录（排除 `.git`, `__pycache__`, `docs` 等）
- 分析 Python 文件的 AST（抽象语法树）
- 提取类、函数、常量、导入关系
- 生成 Markdown 格式文档
- 在 `docs/yuanlin` 创建镜像目录结构

### 重新生成

当项目代码变更时，重新运行脚本更新文档：

```bash
cd /path/to/alphagpt
python generate_directory_docs.py
```

## 注意事项

1. 文档基于代码静态分析生成，部分描述可能需要人工验证
2. 文档中的"无文档字符串"表示原代码缺少 docstring
3. 架构图和数据流描述基于目录名称和常见模式，可能不完全准确
4. 依赖关系分析仅基于 `import` 语句

## 维护

如需改进文档生成逻辑，编辑 `generate_directory_docs.py` 脚本：

- `PythonFileAnalyzer` 类 - Python 文件分析
- `DirectoryAnalyzer` 类 - 目录分析和文档生成
- `generate_root_overview()` 函数 - 项目总览文档

## 项目架构总览

详细的项目架构说明见 [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)。

---

*文档最后更新: 2026-03-14*