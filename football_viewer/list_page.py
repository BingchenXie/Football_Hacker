"""
列表页：球员搜索 + 表格展示。
"""

from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableView, QLabel, QHeaderView, QAbstractItemView,
)
from PyQt5.QtGui import QFont, QColor

from data_loader import loader, DataLoader


# ── 列定义 ────────────────────────────────────────────────────────

def _val(row: dict, *keys) -> str:
    for k in keys:
        v = row.get(k)
        if v is not None:
            try:
                return str(int(v))
            except (ValueError, TypeError):
                pass
    return "—"


def _delta(row: dict, field: str) -> str:
    cur = row.get(field)
    old = row.get(f"{field}_24")
    try:
        c, o = int(cur), int(old)
    except (TypeError, ValueError):
        return "0"
    if c == 0 or o == 0:
        return "0"
    d = c - o
    if d > 0:  return f"+{d}"
    if d < 0:  return str(d)
    return "0"


COLUMNS = [
    ("姓名",        lambda r: f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()),
    ("当前能力",    lambda r: _val(r, "ability_now")),
    ("潜力上限",    lambda r: _val(r, "ability_potential")),
    ("能力变化",    lambda r: _delta(r, "ability_now")),
    ("潜力变化",    lambda r: _delta(r, "ability_potential")),
    ("年龄",        lambda r: DataLoader.calc_age(r.get("birth_date", ""))),
    ("主要位置",    lambda r: DataLoader.main_positions_str(r)),
]

# 各列的排序 key（统一返回自然值，reverse 由 _apply_sort 控制）
_SORT_KEYS = [
    lambda r: (r.get("last_name") or "", r.get("first_name") or ""),   # 姓名
    lambda r: r.get("ability_now") or 0,                                # 当前能力
    lambda r: r.get("ability_potential") or 0,                          # 潜力上限
    lambda r: _sort_delta(r, "ability_now"),                            # 能力变化
    lambda r: _sort_delta(r, "ability_potential"),                      # 潜力变化
    lambda r: r.get("birth_date") or "",                                # 年龄（出生日期）
    lambda r: DataLoader.main_positions_str(r),                         # 主要位置
]


def _sort_delta(row: dict, field: str) -> int:
    cur = row.get(field)
    old = row.get(f"{field}_24")
    try:
        c, o = int(cur), int(old)
    except (TypeError, ValueError):
        return 0
    if c == 0 or o == 0:
        return 0
    return c - o


# ── 表格模型 ──────────────────────────────────────────────────────

class PlayerTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []
        self._cache: list[list] = []
        self._sort_col: int = 2        # 默认按潜力上限排序
        self._sort_asc: bool = False   # 默认降序

    def set_data(self, rows: list[dict]):
        self.beginResetModel()
        self._rows = rows
        self._apply_sort()
        self.endResetModel()

    def _apply_sort(self):
        # reverse=True → 降序（大→小）；reverse=False → 升序（小→大）
        self._rows.sort(key=_SORT_KEYS[self._sort_col], reverse=not self._sort_asc)
        self._cache = [[fn(r) for _, fn in COLUMNS] for r in self._rows]

    def sort(self, column: int, order=Qt.AscendingOrder):
        """QHeaderView 点击时调用。"""
        asc = (order == Qt.AscendingOrder)
        self.beginResetModel()
        self._sort_col = column
        self._sort_asc = asc
        self._apply_sort()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._cache)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self._cache[index.row()][index.column()]
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        if role == Qt.ForegroundRole and index.column() == 2:
            try:
                val = int(self._cache[index.row()][2])
                if val >= 180:
                    return QColor("#2ecc71")
                if val >= 165:
                    return QColor("#f39c12")
            except (ValueError, TypeError):
                pass
        if role == Qt.ForegroundRole and index.column() in (3, 4):
            txt = self._cache[index.row()][index.column()]
            if txt.startswith("+"):
                return QColor("#2ecc71")
            if txt.startswith("-"):
                return QColor("#e74c3c")
        if role == Qt.UserRole:
            return int(self._rows[index.row()]["id"])
        return None

    def headerData(self, section: int, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section][0]
        return None


# ── 列表页 ────────────────────────────────────────────────────────

class ListPage(QWidget):
    player_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = PlayerTableModel()
        self._build_ui()
        self._load_data("")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("⚽ Football Hacker — 球员数据库")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        layout.addWidget(title)

        # ── 搜索栏 ────────────────────────────────────────────────
        search_row = QHBoxLayout()

        self._search = QLineEdit()
        self._search.setPlaceholderText("输入球员姓名后按回车或点击搜索…")
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(
            "QLineEdit { font-size: 14px; padding: 4px 8px; border-radius: 6px; }"
        )
        self._search.returnPressed.connect(self._on_search)

        search_btn = QPushButton("搜索")
        search_btn.setFixedHeight(36)
        search_btn.setFixedWidth(72)
        search_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px; border-radius: 6px;
                background: #3498db; color: white; border: none;
            }
            QPushButton:hover { background: #2980b9; }
            QPushButton:pressed { background: #2471a3; }
        """)
        search_btn.clicked.connect(self._on_search)

        self._count_label = QLabel()
        self._count_label.setStyleSheet("color: gray; font-size: 13px;")

        search_row.addWidget(self._search)
        search_row.addWidget(search_btn)
        search_row.addWidget(self._count_label)
        layout.addLayout(search_row)

        # ── 表格 ──────────────────────────────────────────────────
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, len(COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(2, Qt.DescendingOrder)   # 初始：潜力上限降序
        header.sectionClicked.connect(self._on_header_clicked)

        self._table.setStyleSheet("""
            QTableView { font-size: 13px; gridline-color: #e0e0e0; }
            QTableView::item:selected { background: #3498db; color: white; }
            QHeaderView::section {
                background: #f5f5f5; font-weight: bold; padding: 6px;
            }
            QHeaderView::section:hover { background: #e0e0e0; }
        """)
        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        hint = QLabel("双击行查看球员详情  ·  点击表头排序")
        hint.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(hint)

    def _load_data(self, query: str):
        self._count_label.setText("加载中…")
        rows = loader.search(query)
        self._model.set_data(rows)
        self._count_label.setText(f"共 {len(rows):,} 名球员")

    def _on_search(self):
        self._load_data(self._search.text())

    def _on_header_clicked(self, logical_index: int):
        model = self._model
        if model._sort_col == logical_index:
            # 同列再次点击：翻转方向（从模型自身状态读取，避免 Qt header 状态不一致）
            new_asc = not model._sort_asc
        else:
            # 新列：姓名/位置默认升序，数值列默认降序
            new_asc = logical_index in (0, 6)
        new_order = Qt.AscendingOrder if new_asc else Qt.DescendingOrder
        self._table.horizontalHeader().setSortIndicator(logical_index, new_order)
        model.sort(logical_index, new_order)

    def _on_double_click(self, index: QModelIndex):
        player_id = self._model.data(index, Qt.UserRole)
        if player_id:
            self.player_selected.emit(player_id)