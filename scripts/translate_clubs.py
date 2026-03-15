#!/usr/bin/env python3
"""
将 meta.db 中实际被球员使用的俱乐部名翻译成英文，存入 meta.db 的 name_en 列。

用法：
    python scripts/translate_clubs.py

特性：
  - 只翻译 football.db 中实际出现的 club_id（约 2.6 万个）
  - 断点续传：已翻译的跳过
  - 批量请求 + 自动限速，避免被封
  - 预计耗时 30-60 分钟
"""

import sqlite3
import time
import sys
from pathlib import Path
from deep_translator import GoogleTranslator

ROOT      = Path(__file__).parent.parent
DB_PATH   = ROOT / "football.db"
META_PATH = ROOT / "meta.db"

BATCH     = 50    # 每批翻译条数
DELAY     = 0.5   # 每批间隔（秒）


def main():
    # ── 1. 给 meta.db 加 name_en 列 ──────────────────────────────
    meta = sqlite3.connect(META_PATH)
    try:
        meta.execute("ALTER TABLE clubs ADD COLUMN name_en TEXT")
        meta.commit()
        print("已添加 name_en 列")
    except sqlite3.OperationalError:
        print("name_en 列已存在，继续...")

    # ── 2. 获取实际用到的 club_id ─────────────────────────────────
    fb = sqlite3.connect(DB_PATH)
    used_ids = {row[0] for row in fb.execute(
        "SELECT DISTINCT club_id FROM player_snapshot "
        "WHERE club_id IS NOT NULL AND club_id != 0"
    )}
    fb.close()
    print(f"实际用到的俱乐部：{len(used_ids):,} 个")

    # ── 3. 取出待翻译的俱乐部（name_en 为空的） ───────────────────
    rows = meta.execute(
        "SELECT id, name FROM clubs WHERE id IN ({}) AND (name_en IS NULL OR name_en = '')".format(
            ",".join("?" * len(used_ids))
        ),
        list(used_ids)
    ).fetchall()
    print(f"待翻译：{len(rows):,} 个（已跳过已翻译的）")

    if not rows:
        print("全部已翻译完毕！")
        meta.close()
        return

    # ── 4. 批量翻译 ───────────────────────────────────────────────
    translator = GoogleTranslator(source="zh-CN", target="en")
    total   = len(rows)
    done    = 0
    errors  = 0

    for i in range(0, total, BATCH):
        batch = rows[i: i + BATCH]
        ids   = [r[0] for r in batch]
        names = [r[1] for r in batch]

        try:
            translated = translator.translate_batch(names)
            updates = [(t or n, id_) for t, n, id_ in zip(translated, names, ids)]
            meta.executemany("UPDATE clubs SET name_en = ? WHERE id = ?", updates)
            meta.commit()
            done += len(batch)
        except Exception as e:
            errors += len(batch)
            print(f"\n  ⚠ 翻译失败（批次 {i//BATCH}）: {e}，跳过此批次")
            time.sleep(2)
            continue

        pct = done / total * 100
        print(f"\r  进度：{done:,}/{total:,}  ({pct:.1f}%)  错误：{errors}", end="", flush=True)
        time.sleep(DELAY)

    print(f"\n\n完成！翻译 {done:,} 条，失败 {errors:,} 条")
    meta.close()


if __name__ == "__main__":
    main()
