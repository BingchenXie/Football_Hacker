# 球员相似度搜索

基于 `high_potential_players.csv`，找到与指定球员风格最相似的球员。

## 依赖

```bash
pip install scikit-learn pandas numpy
```

## 用法

```bash
# 演示（默认用数据集第一个球员）
python player_similarity.py

# 按球员 ID 查询
python player_similarity.py 7302

# 按姓名查询（大小写不敏感）
python player_similarity.py "Kylian" "Mbappe"
```

## 在代码中调用

```python
from player_similarity import find_similar, find_similar_by_name

# 按 ID
result = find_similar(7302, top_k=10)
print(result)

# 按姓名
result = find_similar_by_name("Kylian", "Mbappe", top_k=10)
print(result)
```

## 算法说明

| 步骤 | 说明 |
|------|------|
| 属性归一化 | `props / ability_now`，消除发展阶段差异，年轻潜力股与现役强将可被正确比较 |
| 风格向量 | L2 归一化后的属性轮廓，捕捉踢球方式/方向（权重 65%） |
| 属性组档案 | KMeans 自动将 77 个属性分为 8 组，计算球员在各组的相对强弱（权重 35%） |
| 相似度 | Cosine 相似度，返回 0~1 分值，越高越相似 |

> 首次运行会自动生成 `player_features.npy` 缓存，后续查询直接加载无需重新计算。