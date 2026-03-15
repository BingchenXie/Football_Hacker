"""
提取两个快照中 ability_potential > 160 或为 -9/-10/-95 的球员数据，合并后保存为宽表 CSV。

输出格式（每个球员一行）：
- 只保留在两个快照中都出现的球员
- 静态字段（姓名、出生日期、身高、体重、国籍）：只存一次
- 动态字段（能力值、俱乐部、合同、薪资、属性数组等）：用 _2401 / _2402 后缀区分两个快照
- ability_potential 输出时做映射：-10 → 185，-95 → 175，-9 → 165
"""

import json
import pandas as pd

THRESHOLD = 160
FILES = {
    "2401": "persons_2401.json",
    "2402": "persons_2402.json",
}
OUTPUT = "high_potential_players.csv"

# 静态字段：不随时间变化，每个球员只保留一份
STATIC_COLS = ["id", "first_name", "last_name", "full_name",
               "birth_date", "height", "weight", "nation_id"]

# 动态字段：两个快照各保留一列（_2401 / _2402）
DYNAMIC_COLS = ["ability_now", "ability_potential", "club_id", "play_number",
                "salary", "transfer_value",
                "contract_start_date", "contract_end_date", "entry_date"]
# properties_main / properties_hidden 展开后也作为动态字段处理


def load_snapshot(filepath: str) -> pd.DataFrame:
    print(f"Loading {filepath} ...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data["items"])
    print(f"  {len(df):,} records loaded")
    return df


def expand_array_col(df: pd.DataFrame, col: str, prefix: str) -> pd.DataFrame:
    """把 list 列展开为多列：properties_main -> prop_main_0, prop_main_1, ..."""
    expanded = pd.DataFrame(df[col].tolist(), index=df.index)
    expanded.columns = [f"{prefix}_{i}" for i in expanded.columns]
    return pd.concat([df.drop(columns=[col]), expanded], axis=1)


# ── 1. 读取数据 ──────────────────────────────────────────────
snapshots = {}
for label, path in FILES.items():
    snapshots[label] = load_snapshot(path)

# ── 2. 找出在任意一个快照中 ability_potential > THRESHOLD 的球员 ID ──
high_ids = set()
for label, df in snapshots.items():
    mask = (df["ability_potential"] > THRESHOLD) | (df["ability_potential"].isin([-9, -10, -95]))
    ids = set(df.loc[mask, "id"])
    print(f"  [{label}] ability_potential > {THRESHOLD} or in [-9, -10, -95]: {len(ids):,} players")
    high_ids |= ids

print(f"\nUnion of high-potential player IDs: {len(high_ids):,}")

# ── 3. 只保留在两个快照中都出现的球员 ID ──────────────────────
ids_2401 = set(snapshots["2401"]["id"])
ids_2402 = set(snapshots["2402"]["id"])
both_ids = high_ids & ids_2401 & ids_2402
print(f"Players in both snapshots: {len(both_ids):,}  "
      f"(dropped {len(high_ids) - len(both_ids):,} appearing in only one)")

# ── 4. 筛选 & 展开数组列 ──────────────────────────────────────
for label in list(snapshots.keys()):
    s = snapshots[label][snapshots[label]["id"].isin(both_ids)].copy()
    s = expand_array_col(s, "properties_main", "prop_main")
    s = expand_array_col(s, "properties_hidden", "prop_hidden")
    snapshots[label] = s

# ── 5. 确定动态字段完整列表（含展开后的属性列）───────────────
sample_cols = snapshots["2401"].columns.tolist()
dynamic_cols_full = [c for c in sample_cols if c not in STATIC_COLS]

# ── 6. 构建宽表：静态字段取一次，动态字段各加后缀 ─────────────
static_df = snapshots["2401"][STATIC_COLS].drop_duplicates("id").set_index("id")

dyn_2401 = (snapshots["2401"][["id"] + dynamic_cols_full]
            .drop_duplicates("id")
            .set_index("id")
            .add_suffix("_2401"))

dyn_2402 = (snapshots["2402"][["id"] + dynamic_cols_full]
            .drop_duplicates("id")
            .set_index("id")
            .add_suffix("_2402"))

# 释放内存
del snapshots

# ── 7. 合并为宽表（inner join，确保两个快照都有数据）──────────
result = static_df.join(dyn_2401, how="inner").join(dyn_2402, how="inner")
result = result.reset_index()  # id 还原为普通列

# ── 8. ability_potential 映射：-10→185，-95→175，-9→165 ────────
POTENTIAL_MAP = {-10: 185, -95: 175, -9: 165, -85:155, -8:145, -7:135}
for col in ["ability_potential_2401", "ability_potential_2402"]:
    result[col] = result[col].replace(POTENTIAL_MAP)

# ── 9. 列排序：静态列在前，动态列按 _2401/_2402 交替排列 ────────
ordered_cols = STATIC_COLS.copy()
for col in dynamic_cols_full:
    ordered_cols.append(f"{col}_2401")
    ordered_cols.append(f"{col}_2402")
# 过滤掉实际不存在的列（防御性处理）
ordered_cols = [c for c in ordered_cols if c in result.columns]
result = result[ordered_cols]

# ── 10. 保存 ───────────────────────────────────────────────────
result.to_csv(OUTPUT, index=False)
print(f"\nSaved {len(result):,} players to '{OUTPUT}'")
print(f"Total columns: {len(result.columns)}")
print(f"Static columns: {len(STATIC_COLS)}")
print(f"Dynamic columns per snapshot: {len(dynamic_cols_full)}")

# ── 11. 简单统计 ───────────────────────────────────────────────
print(f"\nTotal players saved : {len(result):,} (all appear in both snapshots)")
