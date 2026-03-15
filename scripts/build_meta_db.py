#!/usr/bin/env python3
"""
构建 meta.db：包含 clubs 和 nations 两张轻量查找表。

用法：
    python scripts/build_meta_db.py

输出：项目根目录下的 meta.db（约 5MB，可提交到 git）
"""

import json
import sqlite3
from pathlib import Path

ROOT    = Path(__file__).parent.parent
DATA    = ROOT / "data"
DB_PATH = ROOT / "meta.db"

FILES_CLUBS = [
    DATA / "clubs_24.json",
    DATA / "clubs_25.json",
    DATA / "clubs_26.json",
]

FILES_NATIONS = [
    DATA / "nations_24.json",
    DATA / "nations_25.json",
    DATA / "nations_26.json",
]


def build_meta_db() -> None:
    print(f"目标数据库：{DB_PATH}\n")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clubs (
            id         INTEGER PRIMARY KEY,
            name       TEXT,
            short_name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nations (
            id         INTEGER PRIMARY KEY,
            name       TEXT,
            short_name TEXT
        )
    """)
    conn.commit()

    # ── clubs ──────────────────────────────────────────────────────
    print("导入 clubs...")
    for path in FILES_CLUBS:
        if not path.exists():
            print(f"  ⚠  {path.name} 不存在，跳过")
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        items = data["items"] if isinstance(data, dict) else data
        rows = [(item["id"], item.get("name", ""), item.get("short_name", ""))
                for item in items]
        conn.executemany(
            "INSERT OR IGNORE INTO clubs (id, name, short_name) VALUES (?, ?, ?)",
            rows
        )
        conn.commit()
        print(f"  {path.name}: {len(rows):,} 条")

    # ── nations ────────────────────────────────────────────────────
    print("导入 nations...")
    for path in FILES_NATIONS:
        if not path.exists():
            print(f"  ⚠  {path.name} 不存在，跳过")
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        items = data["items"] if isinstance(data, dict) else data
        rows = [(item["id"], item.get("name", ""), item.get("short_name", ""))
                for item in items]
        conn.executemany(
            "INSERT OR IGNORE INTO nations (id, name, short_name) VALUES (?, ?, ?)",
            rows
        )
        conn.commit()
        print(f"  {path.name}: {len(rows):,} 条")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_clubs_id   ON clubs(id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nations_id ON nations(id)")
    conn.commit()
    conn.close()

    size_kb = DB_PATH.stat().st_size / 1024
    print(f"\n完成 → {DB_PATH}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    build_meta_db()
