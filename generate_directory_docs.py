#!/usr/bin/env python3
"""
Directory Documentation Generator for AlphaGPT
Recursively traverses project directories and generates ARCHITECTURE.md files
in docs/yuanlin mirror directory structure.
"""

import os
import ast
import sys
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
import textwrap

# Configuration
PROJECT_ROOT = Path(__file__).parent
DOCS_ROOT = PROJECT_ROOT / "docs" / "yuanlin"

# Directories to exclude from traversal
EXCLUDE_DIRS = {
    '.git', '__pycache__', 'venv', '.venv', 'env', 'node_modules',
    'docs', 'tests', 'test', '__pycache__', '.idea', '.vscode'
}

# File extensions to analyze
PYTHON_EXTENSIONS = {'.py'}

def should_exclude(path: Path) -> bool:
    """Check if a path should be excluded from processing."""
    # Check if any excluded directory name appears in path parts
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True

    # Exclude hidden files/directories starting with .
    if any(part.startswith('.') for part in path.parts):
        return True

    # Exclude the docs/yuanlin directory itself to prevent recursion
    if 'docs' in path.parts and 'yuanlin' in path.parts:
        # Check if this is the docs/yuanlin directory or its subdirectories
        docs_index = path.parts.index('docs') if 'docs' in path.parts else -1
        if docs_index != -1 and docs_index + 1 < len(path.parts):
            if path.parts[docs_index + 1] == 'yuanlin':
                return True

    return False

def create_mirror_directories(project_dir: Path, docs_dir: Path) -> None:
    """
    Create mirror directory structure in docs/yuanlin.
    """
    for root, dirs, files in os.walk(project_dir):
        root_path = Path(root)

        # Filter out excluded directories
        dirs[:] = [d for d in dirs if not should_exclude(root_path / d)]

        # Calculate corresponding docs directory
        rel_path = root_path.relative_to(project_dir)
        mirror_dir = docs_dir / rel_path

        # Create mirror directory if it doesn't exist
        if not mirror_dir.exists():
            mirror_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created mirror directory: {mirror_dir}")

class PythonFileAnalyzer:
    """Analyzes Python files to extract structure and dependencies."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.content = filepath.read_text(encoding='utf-8')
        self.tree = None
        self.imports = []
        self.classes = []
        self.functions = []
        self.constants = []

    def analyze(self):
        """Parse Python file and extract information."""
        try:
            self.tree = ast.parse(self.content)
            self._extract_imports()
            self._extract_classes()
            self._extract_functions()
            self._extract_constants()
        except SyntaxError as e:
            print(f"Syntax error in {self.filepath}: {e}")

    def _extract_imports(self):
        """Extract import statements from AST."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports.append({
                        'module': alias.name,
                        'alias': alias.asname,
                        'type': 'import'
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    self.imports.append({
                        'module': module,
                        'name': alias.name,
                        'alias': alias.asname,
                        'type': 'from_import'
                    })

    def _extract_classes(self):
        """Extract class definitions from AST."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                # Get class methods
                methods = []
                for child in node.body:
                    if isinstance(child, ast.FunctionDef):
                        methods.append(child.name)

                # Get class decorators
                decorators = []
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name):
                        decorators.append(decorator.id)
                    elif isinstance(decorator, ast.Attribute):
                        decorators.append(ast.unparse(decorator))

                self.classes.append({
                    'name': node.name,
                    'methods': methods,
                    'decorators': decorators,
                    'docstring': ast.get_docstring(node)
                })

    def _extract_functions(self):
        """Extract function definitions from AST."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                # Skip methods (they're captured in class analysis)
                if any(isinstance(parent, ast.ClassDef) for parent in ast.walk(node)):
                    continue

                # Get function arguments
                args = []
                if node.args.args:
                    for arg in node.args.args:
                        args.append(arg.arg)

                # Get decorators
                decorators = []
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name):
                        decorators.append(decorator.id)
                    elif isinstance(decorator, ast.Attribute):
                        decorators.append(ast.unparse(decorator))

                self.functions.append({
                    'name': node.name,
                    'args': args,
                    'decorators': decorators,
                    'docstring': ast.get_docstring(node)
                })

    def _extract_constants(self):
        """Extract constant assignments (uppercase variables) from AST."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        try:
                            value = ast.unparse(node.value) if hasattr(ast, 'unparse') else repr(node.value)
                            self.constants.append({
                                'name': target.id,
                                'value': value
                            })
                        except:
                            pass

class DirectoryAnalyzer:
    """Analyzes a directory and generates documentation."""

    def __init__(self, project_dir: Path, docs_dir: Path):
        self.project_dir = project_dir
        self.docs_dir = docs_dir
        self.python_files = []
        self.other_files = []
        self.subdirectories = []

    def analyze_directory(self):
        """Analyze the directory structure and Python files."""
        # Get all files and subdirectories
        for item in self.project_dir.iterdir():
            if should_exclude(item):
                continue

            if item.is_dir():
                self.subdirectories.append(item.name)
            elif item.is_file():
                if item.suffix in PYTHON_EXTENSIONS:
                    self.python_files.append(item)
                else:
                    self.other_files.append(item)

    def generate_documentation(self) -> str:
        """Generate Markdown documentation for the directory."""
        # Get directory name for title
        dir_name = self.project_dir.name
        if self.project_dir == PROJECT_ROOT:
            dir_name = "AlphaGPT (Root Directory)"

        # Analyze Python files
        python_analyses = []
        for py_file in self.python_files:
            analyzer = PythonFileAnalyzer(py_file)
            analyzer.analyze()
            python_analyses.append((py_file.name, analyzer))

        # Generate documentation
        doc = f"""# {dir_name} 模块文档

## 概述
{self._generate_overview(python_analyses)}

## 文件结构
```
{self._generate_file_tree()}
```

## 关键文件说明
{self._generate_file_descriptions(python_analyses)}

## 依赖关系
{self._generate_dependencies(python_analyses)}

## 架构图
```
{self._generate_architecture_diagram(python_analyses)}
```

## 数据流
{self._generate_data_flow(python_analyses)}

## 使用示例
{self._generate_usage_examples(python_analyses)}

## 注意事项
{self._generate_notes()}
"""
        return doc

    def _generate_overview(self, python_analyses: List[Tuple[str, PythonFileAnalyzer]]) -> str:
        """Generate overview section based on directory analysis."""
        # Determine directory type based on name and content
        dir_name = self.project_dir.name.lower()

        if dir_name == "dashboard":
            return "Streamlit仪表板模块，提供实时交易监控和控制系统界面。"
        elif dir_name == "data_pipeline":
            return "数据管道模块，负责从外部API获取、处理和存储市场数据。"
        elif dir_name == "execution":
            return "交易执行模块，处理Solana链上交易和Jupiter路由。"
        elif dir_name == "model_core":
            return "模型核心模块，包含AlphaGPT模型、因子工程和训练引擎。"
        elif dir_name == "strategy_manager":
            return "策略管理模块，负责实时扫描、风控和投资组合管理。"
        elif dir_name == "lord":
            return "实验性模块，包含LoRD（Layer-wise Relevance Decomposition）等高级正则化方法。"
        elif self.project_dir == PROJECT_ROOT:
            return "AlphaGPT项目根目录，包含整个加密量化系统的入口和配置。"
        else:
            return f"{self.project_dir.name}目录，包含相关功能模块。"

    def _generate_file_tree(self) -> str:
        """Generate ASCII file tree representation."""
        tree_lines = []

        # Add subdirectories
        for subdir in sorted(self.subdirectories):
            tree_lines.append(f"├── {subdir}/")

        # Add Python files
        for py_file in sorted(self.python_files, key=lambda x: x.name):
            tree_lines.append(f"├── {py_file.name}")

        # Add other files
        for other_file in sorted(self.other_files, key=lambda x: x.name):
            tree_lines.append(f"└── {other_file.name}")

        if tree_lines:
            # Make the last line use └──
            if len(tree_lines) > 1:
                tree_lines[-1] = tree_lines[-1].replace('├──', '└──')

        return "\n".join(tree_lines) if tree_lines else "(空目录)"

    def _generate_file_descriptions(self, python_analyses: List[Tuple[str, PythonFileAnalyzer]]) -> str:
        """Generate descriptions for each Python file."""
        if not python_analyses:
            return "本目录没有Python文件。\n"

        descriptions = []
        for filename, analyzer in python_analyses:
            desc = f"### {filename}\n"

            if analyzer.classes:
                desc += "- **主要类**:\n"
                for cls in analyzer.classes:
                    desc += f"  - `{cls['name']}`: {cls['docstring'] or '无文档字符串'}\n"

            if analyzer.functions:
                desc += "- **关键函数**:\n"
                for func in analyzer.functions:
                    desc += f"  - `{func['name']}()`: {func['docstring'] or '无文档字符串'}\n"

            if analyzer.constants:
                desc += "- **重要常量**:\n"
                for const in analyzer.constants:
                    desc += f"  - `{const['name']}`: {const['value']}\n"

            descriptions.append(desc)

        return "\n".join(descriptions)

    def _generate_dependencies(self, python_analyses: List[Tuple[str, PythonFileAnalyzer]]) -> str:
        """Generate dependency analysis."""
        internal_deps = set()
        external_deps = set()

        for _, analyzer in python_analyses:
            for imp in analyzer.imports:
                module = imp.get('module', '')
                if not module:
                    continue

                # Check if it's an internal dependency (starts with project modules)
                if (module.startswith('dashboard') or
                    module.startswith('data_pipeline') or
                    module.startswith('execution') or
                    module.startswith('model_core') or
                    module.startswith('strategy_manager') or
                    module.startswith('lord')):
                    internal_deps.add(module.split('.')[0])  # Get top-level module
                elif module and not module.startswith('.'):
                    external_deps.add(module.split('.')[0])  # Get top-level module

        deps_text = ""
        if internal_deps:
            deps_text += "- **内部依赖**:\n"
            for dep in sorted(internal_deps):
                deps_text += f"  - `{dep}`\n"

        if external_deps:
            deps_text += "- **外部依赖**:\n"
            for dep in sorted(external_deps):
                deps_text += f"  - `{dep}`\n"

        return deps_text if deps_text else "本模块没有明显的依赖关系。\n"

    def _generate_architecture_diagram(self, python_analyses: List[Tuple[str, PythonFileAnalyzer]]) -> str:
        """Generate text-based architecture diagram."""
        dir_name = self.project_dir.name.lower()

        if dir_name == "dashboard":
            return """Streamlit Dashboard
    ├── app.py (主界面)
    ├── data_service.py (数据服务)
    └── visualizer.py (可视化组件)

数据流向:
外部数据源 → data_service → app.py → visualizer.py → 用户界面"""
        elif dir_name == "data_pipeline":
            return """数据管道架构
    ├── run_pipeline.py (主运行器)
    ├── fetcher.py (数据获取)
    ├── processor.py (数据处理)
    ├── db_manager.py (数据库管理)
    └── providers/ (数据提供商)
        ├── base.py (抽象基类)
        ├── birdeye.py (Birdeye API)
        └── dexscreener.py (DexScreener API)

数据流向:
外部API → fetcher → processor → db_manager → 数据库"""
        elif dir_name == "execution":
            return """交易执行层
    ├── trader.py (交易逻辑)
    ├── jupiter.py (Jupiter聚合器)
    ├── rpc_handler.py (Solana RPC)
    └── utils.py (工具函数)

交易流程:
策略信号 → trader → jupiter → rpc_handler → Solana链"""
        elif dir_name == "model_core":
            return """模型核心架构
    ├── alphagpt.py (主模型)
    ├── factors.py (因子工程)
    ├── vm.py (栈虚拟机)
    ├── engine.py (训练引擎)
    └── backtest.py (回测系统)

处理流程:
原始数据 → factors → alphagpt → vm → 交易信号"""
        elif dir_name == "strategy_manager":
            return """策略管理器
    ├── runner.py (策略运行器)
    ├── portfolio.py (投资组合)
    ├── risk.py (风控模块)
    └── config.py (配置)

工作流程:
市场数据 → runner → risk → portfolio → 交易决策"""
        elif dir_name == "lord":
            return """实验性模块
    └── experiment.py (实验代码)

包含LoRD (Layer-wise Relevance Decomposition)等高级正则化方法"""
        elif self.project_dir == PROJECT_ROOT:
            return """AlphaGPT 整体架构
    ├── dashboard/ (仪表板)
    ├── data_pipeline/ (数据管道)
    ├── execution/ (交易执行)
    ├── model_core/ (模型核心)
    ├── strategy_manager/ (策略管理)
    └── lord/ (实验模块)

系统流程:
数据管道 → 模型核心 → 策略管理 → 交易执行 → 仪表板监控"""
        else:
            return f"{self.project_dir.name} 模块架构\n(详细架构待补充)"

    def _generate_data_flow(self, python_analyses: List[Tuple[str, PythonFileAnalyzer]]) -> str:
        """Generate data flow description."""
        dir_name = self.project_dir.name.lower()

        if dir_name == "dashboard":
            return """1. 从数据库加载投资组合数据
2. 获取市场概览信息
3. 处理并可视化数据
4. 提供用户控制界面
5. 实时更新显示"""
        elif dir_name == "data_pipeline":
            return """1. 从多个数据提供商获取实时市场数据
2. 清洗和标准化数据格式
3. 计算技术指标和因子
4. 存储到数据库供其他模块使用
5. 定期更新数据保持新鲜度"""
        elif dir_name == "execution":
            return """1. 接收交易策略信号
2. 通过Jupiter寻找最佳交易路径
3. 构建Solana交易指令
4. 通过RPC发送交易到链上
5. 监控交易状态和确认"""
        elif dir_name == "model_core":
            return """1. 加载历史市场数据
2. 计算因子矩阵
3. 运行AlphaGPT模型预测
4. 使用栈虚拟机执行公式
5. 生成交易信号和权重"""
        elif dir_name == "strategy_manager":
            return """1. 实时扫描市场机会
2. 应用风控规则过滤
3. 管理投资组合头寸
4. 运行策略逻辑
5. 生成交易决策"""
        else:
            return "数据流分析待补充。\n"

    def _generate_usage_examples(self, python_analyses: List[Tuple[str, PythonFileAnalyzer]]) -> str:
        """Generate usage examples based on actual code."""
        # Try to find main classes or functions
        examples = []

        for filename, analyzer in python_analyses:
            if analyzer.classes:
                for cls in analyzer.classes[:1]:  # Take first class
                    examples.append(f"""```python
# 使用 {cls['name']} 类
from {self.project_dir.name}.{filename[:-3]} import {cls['name']}

instance = {cls['name']}()
# 调用方法...
```""")
                    break

        if examples:
            return "\n".join(examples)
        else:
            return "```python\n# 使用示例待补充\n```"

    def _generate_notes(self) -> str:
        """Generate important notes for the directory."""
        dir_name = self.project_dir.name.lower()

        if dir_name == "dashboard":
            return """- 需要Streamlit环境运行
- 依赖数据管道模块提供数据
- 包含紧急停止功能"""
        elif dir_name == "data_pipeline":
            return """- 需要配置API密钥
- 依赖外部数据提供商
- 数据库连接需要正确配置"""
        elif dir_name == "execution":
            return """- 需要Solana钱包和私钥
- 依赖网络RPC节点
- 交易可能产生实际资金损失"""
        elif dir_name == "model_core":
            return """- 需要大量历史数据训练
- 因子计算可能较耗时
- 模型需要定期重新训练"""
        elif dir_name == "strategy_manager":
            return """- 实时运行需要稳定环境
- 风控规则需谨慎配置
- 投资组合管理是关键"""
        elif dir_name == "lord":
            return """- 实验性代码，谨慎使用
- 高级功能可能需要专业知识
- 性能影响需要评估"""
        else:
            return "无特殊注意事项。\n"

def main():
    """Main function to generate directory documentation."""
    print("AlphaGPT Directory Documentation Generator")
    print("=" * 50)

    # Create mirror directory structure
    print("\n1. Creating mirror directory structure...")
    create_mirror_directories(PROJECT_ROOT, DOCS_ROOT)

    # Walk through all directories and generate documentation
    print("\n2. Analyzing directories and generating documentation...")

    directories_processed = 0
    for root, dirs, files in os.walk(PROJECT_ROOT):
        root_path = Path(root)

        # Filter out excluded directories
        dirs[:] = [d for d in dirs if not should_exclude(root_path / d)]

        # Skip excluded directories themselves
        if should_exclude(root_path):
            continue

        # Calculate corresponding docs directory
        rel_path = root_path.relative_to(PROJECT_ROOT)
        mirror_dir = DOCS_ROOT / rel_path

        # Analyze directory
        analyzer = DirectoryAnalyzer(root_path, mirror_dir)
        analyzer.analyze_directory()

        # Generate documentation
        doc_content = analyzer.generate_documentation()

        # Write ARCHITECTURE.md
        doc_file = mirror_dir / "ARCHITECTURE.md"
        doc_file.write_text(doc_content, encoding='utf-8')

        directories_processed += 1
        print(f"  [OK] Generated: {doc_file}")

    print(f"\n3. Documentation generation complete!")
    print(f"   Processed {directories_processed} directories")
    print(f"   Documentation saved to: {DOCS_ROOT}")

    # Generate root overview document
    print("\n4. Generating root overview document...")
    overview_content = generate_root_overview()
    overview_file = DOCS_ROOT / "ARCHITECTURE_OVERVIEW.md"
    overview_file.write_text(overview_content, encoding='utf-8')
    print(f"  [OK] Generated: {overview_file}")

    print("\nDone!")

def generate_root_overview() -> str:
    """Generate root overview document with project-wide architecture."""
    return """# AlphaGPT 项目架构总览

## 项目简介
AlphaGPT是一个"因子挖掘 + 实盘执行"的加密量化系统，专注于Solana meme代币生态。系统采用分层架构，结合深度学习模型和链上交易执行。

## 整体架构图
```
AlphaGPT 系统架构
┌─────────────────────────────────────────────────────────┐
│                     Dashboard Layer                      │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │  监控界面   │  │  控制面板   │  │  数据可视化     │  │
│  └────────────┘  └────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                 Strategy Manager Layer                   │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │  实时扫描   │  │  风控系统   │  │  投资组合管理    │  │
│  └────────────┘  └────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                   Model Core Layer                       │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │ AlphaGPT模型│  │  因子工程   │  │  栈虚拟机       │  │
│  └────────────┘  └────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                 Data Pipeline Layer                      │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │  数据获取   │  │  数据处理   │  │  数据库管理      │  │
│  └────────────┘  └────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                 Execution Layer                         │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │  交易执行   │  │  Jupiter路由│  │  Solana RPC      │  │
│  └────────────┘  └────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 模块职责说明

### 1. Dashboard Layer (仪表板层)
- **位置**: `dashboard/`
- **功能**: 提供Web界面监控系统状态、查看投资组合、控制交易执行
- **技术**: Streamlit框架

### 2. Strategy Manager Layer (策略管理层)
- **位置**: `strategy_manager/`
- **功能**: 实时市场扫描、风险控制、投资组合管理、策略执行
- **核心**: 策略运行器、风控引擎、头寸管理

### 3. Model Core Layer (模型核心层)
- **位置**: `model_core/`
- **功能**: AlphaGPT深度学习模型、因子工程、公式执行栈虚拟机
- **特色**: 模仿WorldQuant BRAIN的因子挖掘框架

### 4. Data Pipeline Layer (数据管道层)
- **位置**: `data_pipeline/`
- **功能**: 从Birdeye、DexScreener等获取市场数据，清洗处理，存储到数据库
- **提供商**: 支持多个数据源，可扩展架构

### 5. Execution Layer (执行层)
- **位置**: `execution/`
- **功能**: Solana链上交易执行，Jupiter聚合器路由，RPC通信
- **安全**: 钱包管理、交易签名、状态监控

### 6. Experimental Module (实验模块)
- **位置**: `lord/`
- **功能**: LoRD等高级正则化方法实验

## 数据流向
1. **数据收集**: 外部API → 数据管道 → 数据库
2. **模型处理**: 数据库 → 模型核心 → 交易信号
3. **策略执行**: 交易信号 → 策略管理 → 交易指令
4. **链上执行**: 交易指令 → 执行层 → Solana链
5. **监控反馈**: 链上结果 → 仪表板 → 用户

## 技术栈
- **后端**: Python 3.9+
- **深度学习**: PyTorch
- **数据处理**: Pandas, NumPy
- **数据库**: SQLite (可扩展)
- **Web界面**: Streamlit
- **区块链**: Solana (solana-py), Jupiter API
- **数据源**: Birdeye, DexScreener API

## 运行流程
```bash
# 1. 启动数据管道
python data_pipeline/run_pipeline.py

# 2. 启动策略管理器
python strategy_manager/runner.py

# 3. 启动仪表板
streamlit run dashboard/app.py
```

## 配置要求
1. Solana钱包和私钥
2. 数据提供商API密钥
3. Python环境依赖
4. 足够的存储空间历史数据

## 注意事项
- 实盘交易有资金损失风险
- 需要定期监控系统运行
- 模型需要重新训练以适应市场变化
- 遵守当地法律法规

## 目录文档
每个模块的详细文档位于对应的`ARCHITECTURE.md`文件中：
- `docs/yuanlin/dashboard/ARCHITECTURE.md`
- `docs/yuanlin/strategy_manager/ARCHITECTURE.md`
- `docs/yuanlin/model_core/ARCHITECTURE.md`
- `docs/yuanlin/data_pipeline/ARCHITECTURE.md`
- `docs/yuanlin/execution/ARCHITECTURE.md`
- `docs/yuanlin/lord/ARCHITECTURE.md`
"""

if __name__ == "__main__":
    main()