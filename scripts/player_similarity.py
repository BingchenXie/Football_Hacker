"""
球员相似度搜索（无监督）

核心思路：
1. 用「属性向量 / 当前能力值」消除发展阶段差异：
   年轻潜力股与现役强将若属性分布方向一致，则被认为风格相似。
2. L2 归一化 → 纯风格向量（方向相似度）
3. KMeans 对属性列聚类，发现无监督属性组（技术/身体/心理等）
   → 每个球员的组内强弱档案（特点相似度）
4. 加权合并两种特征，综合衡量相似度

首次运行会保存特征矩阵（player_features.npy / player_index.npy），
后续查询直接加载，无需重新计算。
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler, normalize

warnings.filterwarnings("ignore")

# ── 配置 ────────────────────────────────────────────────────────
_ANALYSIS     = Path(__file__).parent.parent / "analysis"
CSV_PATH      = str(_ANALYSIS / "high_potential_players.csv")
FEATURES_PATH = str(_ANALYSIS / "player_features.npy")
INDEX_PATH    = str(_ANALYSIS / "player_index.npy")  # 保存 id 顺序，与特征矩阵行对应

N_ATTR_GROUPS  = 8    # 属性自动分组数（无监督发现）
STYLE_WEIGHT   = 0.65  # 风格向量权重
GROUP_WEIGHT   = 0.35  # 属性组强弱档案权重

# ── 工具函数 ─────────────────────────────────────────────────────

def _merge_snapshots(df: pd.DataFrame, base: str) -> np.ndarray:
    """
    对同一属性的两个快照列取均值，2402 缺失时用 2401 补。
    返回 shape=(n_players, n_attrs) 的 float 矩阵。
    """
    cols_2402 = sorted([c for c in df.columns
                        if c.startswith(base) and c.endswith("_2402")])
    cols_2401 = sorted([c for c in df.columns
                        if c.startswith(base) and c.endswith("_2401")])

    v2 = df[cols_2402].values.astype(float)
    v1 = df[cols_2401].values.astype(float)

    # 两个快照都有时取均值（更稳定），只有一个时用那个
    with np.errstate(invalid="ignore"):
        merged = np.where(
            ~np.isnan(v2) & ~np.isnan(v1), (v2 + v1) / 2,
            np.where(~np.isnan(v2), v2, v1)
        )
    return np.nan_to_num(merged, nan=0.0)


def build_features(df: pd.DataFrame) -> np.ndarray:
    """
    构建特征矩阵。
    返回 shape=(n_players, feature_dim) 的归一化特征矩阵。
    """
    print("Building features ...")

    # ── 原始属性矩阵（取两个快照均值）────────────────────────────
    props_main   = _merge_snapshots(df, "prop_main_")    # (N, 69)
    props_hidden = _merge_snapshots(df, "prop_hidden_")  # (N, 8)
    props = np.hstack([props_main, props_hidden])         # (N, 77)

    # ── ability_now：用于消除发展阶段差异 ─────────────────────────
    ability_now = (
        df[["ability_now_2401", "ability_now_2402"]]
        .mean(axis=1)
        .fillna(1)
        .clip(lower=1)
        .values
    )

    # ── 特征 1：风格向量（L2 单位化的归一化属性轮廓）─────────────
    # 除以 ability_now 后，年轻潜力股与现役强将的属性分布方向趋于一致
    style_raw = props / ability_now[:, np.newaxis]       # 消除级别差异
    style_vec = normalize(style_raw, norm="l2")          # L2 单位化

    # ── 特征 2：属性组强弱档案 ────────────────────────────────────
    # 对属性列做 KMeans 聚类，无监督发现属性组（如技术/身体/心理）
    print(f"  Clustering {props.shape[1]} attributes into {N_ATTR_GROUPS} groups ...")
    attr_kmeans = KMeans(n_clusters=N_ATTR_GROUPS, random_state=42, n_init=10)
    attr_labels = attr_kmeans.fit_predict(style_raw.T)   # 对属性聚类

    # 每个球员在每个属性组的均值得分
    group_scores = np.zeros((len(df), N_ATTR_GROUPS))
    for g in range(N_ATTR_GROUPS):
        idx = np.where(attr_labels == g)[0]
        if len(idx) > 0:
            group_scores[:, g] = style_raw[:, idx].mean(axis=1)

    # 跨球员做 Z-score，再 L2 归一化 → 体现球员在各组的相对强弱
    group_scaled = StandardScaler().fit_transform(group_scores)
    group_vec = normalize(group_scaled, norm="l2")

    # ── 加权合并 ──────────────────────────────────────────────────
    features = np.hstack([
        style_vec  * STYLE_WEIGHT,
        group_vec  * GROUP_WEIGHT,
    ])

    print(f"  Feature matrix shape: {features.shape}")
    return features


def load_or_build(df: pd.DataFrame, force_rebuild: bool = False):
    """加载已缓存的特征矩阵，或重新构建并保存。"""
    if not force_rebuild and Path(FEATURES_PATH).exists() and Path(INDEX_PATH).exists():
        print("Loading cached features ...")
        features   = np.load(FEATURES_PATH)
        cached_ids = np.load(INDEX_PATH)
        # 验证与当前 CSV 的 id 列表是否一致
        if np.array_equal(cached_ids, df["id"].values):
            print(f"  {features.shape[0]:,} players, {features.shape[1]} dims")
            return features
        print("  Cache mismatch, rebuilding ...")

    features = build_features(df)
    np.save(FEATURES_PATH, features)
    np.save(INDEX_PATH, df["id"].values)
    print(f"Features saved to '{FEATURES_PATH}'")
    return features


# ── 查询接口 ─────────────────────────────────────────────────────

_df       = None
_features = None

def _ensure_loaded():
    global _df, _features
    if _df is None:
        print(f"Loading '{CSV_PATH}' ...")
        _df = pd.read_csv(CSV_PATH)
        print(f"  {len(_df):,} players loaded")
        _features = load_or_build(_df)


def find_similar(player_id: int, top_k: int = 10) -> pd.DataFrame:
    """
    给定球员 ID，返回最相似的 top_k 个球员。

    相似度综合考虑：
    - 属性风格（与当前能力无关，体现踢球方式）
    - 属性组强弱档案（体现擅长领域，抓住球员特点）
    """
    _ensure_loaded()

    matches = _df.index[_df["id"] == player_id].tolist()
    if not matches:
        raise ValueError(f"Player ID {player_id} not found")
    idx = matches[0]

    # 对单个查询球员计算相似度（避免 N×N 全量矩阵）
    query_vec = _features[idx : idx + 1]
    sims = cosine_similarity(query_vec, _features)[0]
    sims[idx] = -1  # 排除自身

    top_indices = np.argsort(sims)[::-1][:top_k]

    player = _df.iloc[idx]
    print(
        f"\nQuery: {player['first_name']} {player['last_name']}"
        f"  |  ability_now={player.get('ability_now_2402', player.get('ability_now_2401', '?')):.0f}"
        f"  |  ability_potential={player.get('ability_potential_2402', player.get('ability_potential_2401', '?')):.0f}"
    )

    result = _df.iloc[top_indices][[
        "id", "first_name", "last_name", "birth_date",
        "ability_now_2402", "ability_potential_2402",
    ]].copy()
    result.insert(0, "similarity", np.round(sims[top_indices], 4))
    result = result.reset_index(drop=True)
    result.index += 1
    return result


def find_similar_by_name(first_name: str, last_name: str, top_k: int = 10) -> pd.DataFrame:
    """按姓名查找相似球员（大小写不敏感）。"""
    _ensure_loaded()

    mask = (
        _df["first_name"].str.lower() == first_name.lower()
    ) & (
        _df["last_name"].str.lower() == last_name.lower()
    )
    matches = _df[mask]
    if matches.empty:
        raise ValueError(f"Player '{first_name} {last_name}' not found")
    if len(matches) > 1:
        print(f"Warning: {len(matches)} players named '{first_name} {last_name}', using first match")
    return find_similar(int(matches.iloc[0]["id"]), top_k)


# ── 命令行入口 ────────────────────────────────────────────────────

if __name__ == "__main__":
    # 用法示例：
    #   python player_similarity.py                   → 用第一个球员演示
    #   python player_similarity.py 12345             → 按 ID 查询
    #   python player_similarity.py "Lionel" "Messi"  → 按姓名查询

    _ensure_loaded()

    if len(sys.argv) == 3:
        result = find_similar_by_name(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        result = find_similar(int(sys.argv[1]))
    else:
        # 默认演示：取数据中第一个球员
        first_id = int(_df.iloc[0]["id"])
        result = find_similar(first_id)

    print(result.to_string())