"""
数据加载模块：读取 SQLite (football.db)，提供查询接口和属性映射常量。
"""

import sys
import sqlite3
from pathlib import Path
from datetime import date

if getattr(sys, "frozen", False):
    # PyInstaller 打包模式：football.db 与可执行文件同目录
    DB_PATH = Path(sys._MEIPASS) / "football.db"
else:
    DB_PATH = Path(__file__).parent.parent / "football.db"

# ── 可用快照 ──────────────────────────────────────────────────────
SNAPSHOTS        = ["24", "25", "26"]
DEFAULT_SNAPSHOT = "26"

# ── 属性名称映射 ──────────────────────────────────────────────────

POSITIONS = {
    0:  "门将",
    1:  "未知",
    2:  "左后卫",
    3:  "中后卫",
    4:  "右后卫",
    5:  "防守中场",
    6:  "左前卫",
    7:  "中前卫",
    8:  "右前卫",
    9:  "左路攻前",
    10: "中路攻前",
    11: "右路攻前",
    12: "前锋",
    13: "左翼卫",
    14: "右翼卫",
}

TECH = {
    42: "角球", 15: "传中", 16: "盘带", 17: "射门", 37: "停球",
    50: "任意球", 18: "头球", 19: "远射", 45: "界外球",
    20: "盯人", 22: "传球", 23: "点球", 24: "抢断", 38: "技术",
}

TECH_GK = {
    27: "制空范围", 28: "拦截传中", 29: "指挥防守", 46: "意外性",
    37: "停球", 26: "手控球", 30: "大脚开球", 34: "一对一",
    22: "传球", 48: "击球倾向", 36: "反应", 47: "出击倾向", 31: "手抛球",
}

MENTAL = {
    60: "侵略性", 32: "预判", 58: "勇敢", 67: "镇定", 68: "专注",
    33: "决断", 66: "意志力", 41: "才华", 55: "领导力",
    21: "无球跑动", 35: "防守站位", 43: "团队合作", 25: "视野", 44: "工作投入",
}

PHYSICAL = {
    49: "爆发力", 56: "灵活", 57: "平衡", 54: "弹跳", 65: "体质",
    53: "速度", 52: "耐力", 51: "强壮", 39: "左脚", 40: "右脚",
}

PERSONALITY_MAIN = {
    59: "稳定", 61: "灵活", 62: "大赛发挥", 63: "受伤倾向", 64: "多面性",
}

HIDDEN = {
    0: "适应性", 1: "雄心", 2: "争论", 3: "忠诚",
    4: "抗压能力", 5: "职业", 6: "体育道德", 7: "情绪控制",
}

ATTRIBUTE_GROUPS = [
    ("技术", TECH),
    ("门将", TECH_GK),
    ("心理", MENTAL),
    ("身体", PHYSICAL),
]

# 列表页只需要前 15 个 pm 列（位置评分）
_POS_COLS = ", ".join(f"ps.pm_{i}" for i in range(15))


# ── DataLoader ────────────────────────────────────────────────────

class DataLoader:
    def __init__(self):
        self._conn: sqlite3.Connection | None = None

    def load(self) -> None:
        self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.load()
        return self._conn

    def search(self, query: str, snapshot: str = DEFAULT_SNAPSHOT) -> list[dict]:
        """按姓名（大小写不敏感）过滤，返回列表页所需字段。"""
        q = f"%{query.strip().lower()}%" if query.strip() else "%"
        sql = f"""
            SELECT pi.id, pi.first_name, pi.last_name, pi.birth_date, pi.height,
                   ps.ability_now, ps.ability_potential,
                   ps24.ability_now       AS ability_now_24,
                   ps24.ability_potential AS ability_potential_24,
                   {_POS_COLS}
            FROM player_info pi
            LEFT JOIN player_snapshot ps   ON pi.id = ps.id   AND ps.snapshot = ?
            LEFT JOIN player_snapshot ps24 ON pi.id = ps24.id AND ps24.snapshot = '24'
            WHERE lower(pi.first_name) LIKE ?
               OR lower(pi.last_name)  LIKE ?
            ORDER BY COALESCE(ps.ability_potential, 0) DESC
        """
        rows = self.conn.execute(sql, (snapshot, q, q)).fetchall()
        return [dict(r) for r in rows]

    def get_player(self, player_id: int, snapshot: str) -> dict:
        """获取单个球员在指定快照的完整数据（静态信息 + 快照数据）。"""
        sql = """
            SELECT pi.*, ps.*
            FROM player_info pi
            LEFT JOIN player_snapshot ps ON pi.id = ps.id AND ps.snapshot = ?
            WHERE pi.id = ?
        """
        row = self.conn.execute(sql, (snapshot, player_id)).fetchone()
        if row is None:
            raise ValueError(f"Player {player_id} not found")
        return dict(row)

    def get_player_all_snapshots(self, player_id: int) -> dict[str, dict]:
        """获取球员在所有快照中的数据，用于计算跨快照变化量。"""
        sql = """
            SELECT pi.id, pi.first_name, pi.last_name, pi.birth_date,
                   ps.*
            FROM player_info pi
            JOIN player_snapshot ps ON pi.id = ps.id
            WHERE pi.id = ?
        """
        rows = self.conn.execute(sql, (player_id,)).fetchall()
        return {r["snapshot"]: dict(r) for r in rows}

    # ── 静态工具方法 ─────────────────────────────────────────────

    @staticmethod
    def calc_age(birth_date_str: str) -> str:
        try:
            bd = date.fromisoformat(str(birth_date_str))
            today = date.today()
            age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
            return str(age)
        except Exception:
            return "—"

    @staticmethod
    def get_positions(row: dict) -> list[tuple[int, str, int]]:
        """返回评分 >= 5 的位置列表 [(idx, 位置名, 评分), ...]，按评分降序。"""
        result = []
        for idx, name in POSITIONS.items():
            val = row.get(f"pm_{idx}") or 0
            if val >= 5:
                result.append((idx, name, int(val)))
        result.sort(key=lambda x: -x[2])
        return result

    @staticmethod
    def get_attrs(row: dict, attr_dict: dict) -> list[tuple[str, int]]:
        """返回指定属性字典对应的 [(属性名, 值), ...] 列表。"""
        return [
            (name, int(row.get(f"pm_{idx}") or 0))
            for idx, name in attr_dict.items()
        ]

    @staticmethod
    def get_hidden_attrs(row: dict) -> list[tuple[str, int]]:
        """返回隐藏属性列表。"""
        return [
            (name, int(row.get(f"ph_{idx}") or 0))
            for idx, name in HIDDEN.items()
        ]

    @staticmethod
    def get_personality_attrs(row: dict) -> list[tuple[str, int]]:
        """返回性格属性列表（隐藏属性 + 性格相关主属性）。"""
        result = [
            (name, int(row.get(f"ph_{idx}") or 0))
            for idx, name in HIDDEN.items()
        ]
        result += [
            (name, int(row.get(f"pm_{idx}") or 0))
            for idx, name in PERSONALITY_MAIN.items()
        ]
        return result

    @staticmethod
    def main_positions_str(row: dict) -> str:
        """列表页：主要位置字符串（评分 ≥ 15），最多 3 个。"""
        positions = [
            name
            for idx, name in POSITIONS.items()
            if int(row.get(f"pm_{idx}") or 0) >= 15
        ]
        return " / ".join(positions[:3]) if positions else "—"


# 全局单例
loader = DataLoader()