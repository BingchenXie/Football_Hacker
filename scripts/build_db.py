#!/usr/bin/env python3
"""
一次性 ETL 脚本：将 persons_24/25/26.json 导入 football.db (SQLite)

用法：
    python build_db.py

注意：
  - 首次运行约需 5-15 分钟（取决于磁盘速度）
  - 内存峰值约 3-4 GB（每个文件加载后立即释放）
  - 重复运行是安全的（INSERT OR IGNORE / INSERT OR REPLACE）
"""

import json
import sqlite3
import time
from pathlib import Path

ROOT    = Path(__file__).parent.parent
DATA    = ROOT / "data"
DB_PATH = ROOT / "football.db"

FILES = [
    (DATA / "persons_24.json", "24"),
    (DATA / "persons_25.json", "25"),
    (DATA / "persons_26.json", "26"),
]

# ability_potential 特殊值映射（负数代表潜力区间，取中间值）
POTENTIAL_MAP = {
    -10: 185,
    -95: 175,
    -9:  165,
    -85: 155,
    -8:  145,
    -75: 135,
    -7:  125,
    -65: 115,
    -6:  105,
    -55:  95,
    -5:   85,
    -45:  75,
    -4:   65,
    -35:  55,
    -3:   45,
    -25:  35,
    -2:   25,
    -15:  15,
    -1:    5,
}

N_MAIN   = 69
N_HIDDEN = 8
BATCH    = 5000

# ── 列名列表 ─────────────────────────────────────────────────────────

PM_COLS = [f"pm_{i}" for i in range(N_MAIN)]
PH_COLS = [f"ph_{i}" for i in range(N_HIDDEN)]

INFO_COLS = ["id", "first_name", "last_name", "full_name",
             "birth_date", "height", "weight", "nation_id"]

SNAP_COLS = (["id", "snapshot", "ability_now", "ability_potential",
              "club_id", "contract_start_date", "contract_end_date",
              "entry_date", "salary", "transfer_value", "play_number"]
             + PM_COLS + PH_COLS)

# ── 建表 SQL ──────────────────────────────────────────────────────────

CREATE_INFO = """
CREATE TABLE IF NOT EXISTS player_info (
    id          INTEGER PRIMARY KEY,
    first_name  TEXT,
    last_name   TEXT,
    full_name   TEXT,
    birth_date  TEXT,
    height      INTEGER,
    weight      INTEGER,
    nation_id   INTEGER
)
"""

_pm_defs = ", ".join(f"pm_{i} INTEGER" for i in range(N_MAIN))
_ph_defs = ", ".join(f"ph_{i} INTEGER" for i in range(N_HIDDEN))

CREATE_SNAP = f"""
CREATE TABLE IF NOT EXISTS player_snapshot (
    id                  INTEGER,
    snapshot            TEXT,
    ability_now         INTEGER,
    ability_potential   INTEGER,
    club_id             INTEGER,
    contract_start_date TEXT,
    contract_end_date   TEXT,
    entry_date          TEXT,
    salary              INTEGER,
    transfer_value      INTEGER,
    play_number         INTEGER,
    {_pm_defs},
    {_ph_defs},
    PRIMARY KEY (id, snapshot)
)
"""

# ── 主函数 ────────────────────────────────────────────────────────────

def build_db() -> None:
    print(f"目标数据库：{DB_PATH}\n")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-262144")   # 256 MB page cache
    conn.execute(CREATE_INFO)
    conn.execute(CREATE_SNAP)
    conn.commit()

    _info_ph = ", ".join("?" * len(INFO_COLS))
    _snap_ph = ", ".join("?" * len(SNAP_COLS))
    INSERT_INFO = (f"INSERT OR IGNORE INTO player_info "
                   f"({', '.join(INFO_COLS)}) VALUES ({_info_ph})")
    INSERT_SNAP = (f"INSERT OR REPLACE INTO player_snapshot "
                   f"({', '.join(SNAP_COLS)}) VALUES ({_snap_ph})")

    for path, snapshot in FILES:
        if not path.exists():
            print(f"⚠  {path.name} 不存在，跳过")
            continue

        t0 = time.time()
        print(f"读取 {path.name}（快照 '{snapshot}'）...")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        items = data["items"]
        total = len(items)
        print(f"  共 {total:,} 条记录，开始写入...")

        info_batch: list = []
        snap_batch: list = []

        for i, item in enumerate(items):
            pid = item["id"]

            info_batch.append((
                pid,
                item.get("first_name", "") or "",
                item.get("last_name",  "") or "",
                item.get("full_name",  "") or "",
                item.get("birth_date", "") or "",
                item.get("height",  0) or 0,
                item.get("weight",  0) or 0,
                item.get("nation_id", 0) or 0,
            ))

            ap  = item.get("ability_potential", 0) or 0
            ap  = POTENTIAL_MAP.get(ap, ap)
            pm  = item.get("properties_main",   [])
            ph  = item.get("properties_hidden", [])
            pm  = (list(pm) + [0] * N_MAIN)[:N_MAIN]
            ph  = (list(ph) + [0] * N_HIDDEN)[:N_HIDDEN]

            snap_batch.append((
                pid, snapshot,
                item.get("ability_now", 0) or 0,
                ap,
                item.get("club_id",              0) or 0,
                item.get("contract_start_date", "") or "",
                item.get("contract_end_date",   "") or "",
                item.get("entry_date",          "") or "",
                item.get("salary",               0) or 0,
                item.get("transfer_value",       0) or 0,
                item.get("play_number",          0) or 0,
                *pm,
                *ph,
            ))

            if len(info_batch) >= BATCH:
                conn.executemany(INSERT_INFO, info_batch)
                conn.executemany(INSERT_SNAP, snap_batch)
                conn.commit()
                info_batch.clear()
                snap_batch.clear()
                print(f"  {i + 1:>9,} / {total:,}", end="\r")

        if info_batch:
            conn.executemany(INSERT_INFO, info_batch)
            conn.executemany(INSERT_SNAP, snap_batch)
            conn.commit()

        elapsed = time.time() - t0
        print(f"  {total:,} / {total:,}  ✓  ({elapsed:.1f}s)")
        del data   # 释放内存再处理下一个文件

    # ── 建索引 ────────────────────────────────────────────────────
    print("\n建立索引...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_info_name "
                 "ON player_info(last_name, first_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snap_ability "
                 "ON player_snapshot(snapshot, ability_potential DESC)")
    conn.commit()
    conn.close()

    size_mb = DB_PATH.stat().st_size / 1024 / 1024
    print(f"\n完成 → {DB_PATH}  ({size_mb:.0f} MB)")


if __name__ == "__main__":
    build_db()