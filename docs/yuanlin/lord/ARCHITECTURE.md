# lord 模块文档

## 概述
实验性模块，包含LoRD（Layer-wise Relevance Decomposition）等高级正则化方法。

## 文件结构
```
├── experiment.py
```

## 关键文件说明
### experiment.py
- **主要类**:
  - `NewtonSchulzLowRankDecay`: 无文档字符串
  - `ModelConfig`: 无文档字符串
  - `RMSNorm`: 无文档字符串
  - `Attention`: 无文档字符串
  - `Transformer`: 无文档字符串
  - `ModularAdditionDataset`: 无文档字符串
- **关键函数**:
  - `get_stable_rank()`: 无文档字符串
  - `train_run()`: 无文档字符串
  - `run_phase_diagram()`: 无文档字符串
  - `run_mechanism_analysis()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `step()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `forward()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `forward()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `forward()`: 无文档字符串
  - `__init__()`: 无文档字符串
  - `__len__()`: 无文档字符串
  - `__getitem__()`: 无文档字符串
  - `get_svd()`: 无文档字符串
  - `plot_attn()`: 无文档字符串
- **重要常量**:
  - `W`: model.layers[0]['attn'].q_proj.weight.detach()
  - `S`: torch.linalg.svdvals(W.float()).cpu().numpy()
  - `Q`: attn_layer.q_norm(attn_layer.q_proj(x))
  - `K`: attn_layer.k_norm(attn_layer.k_proj(x))
  - `Q`: Q.view(p, model.config.heads, head_dim)[:, 0, :]
  - `K`: K.view(p, model.config.heads, head_dim)[:, 0, :]
  - `X`: W.float()
  - `X`: X / norm
  - `Y`: X
  - `I`: torch.eye(min(r, c), device=X.device)
  - `W`: param.detach().float()
  - `S`: torch.linalg.svdvals(W)
  - `X`: X.T
  - `A`: Y.T @ Y
  - `Y`: 0.5 * Y @ (3.0 * I - A)
  - `Y`: Y.T


## 依赖关系
- **外部依赖**:
  - `argparse`
  - `copy`
  - `dataclasses`
  - `itertools`
  - `math`
  - `matplotlib`
  - `numpy`
  - `random`
  - `seaborn`
  - `torch`
  - `tqdm`


## 架构图
```
实验性模块
    └── experiment.py (实验代码)

包含LoRD (Layer-wise Relevance Decomposition)等高级正则化方法
```

## 数据流
数据流分析待补充。


## 使用示例
```python
# 使用 NewtonSchulzLowRankDecay 类
from lord.experiment import NewtonSchulzLowRankDecay

instance = NewtonSchulzLowRankDecay()
# 调用方法...
```

## 注意事项
- 实验性代码，谨慎使用
- 高级功能可能需要专业知识
- 性能影响需要评估
