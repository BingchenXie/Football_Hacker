"""
详情页：显示单个球员的全部信息。
"""

from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize
from PyQt5.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QFrame, QSizePolicy,
)
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush

from data_loader import loader, ATTRIBUTE_GROUPS, POSITIONS, SNAPSHOTS
import i18n


# ── 属性条 ────────────────────────────────────────────────────────

def _attr_color(value: int) -> str:
    if value <= 0:  return "#cccccc"
    if value <= 5:  return "#e74c3c"
    if value <= 10: return "#e67e22"
    if value <= 14: return "#f1c40f"
    if value <= 17: return "#2ecc71"
    return "#27ae60"


class AttributeBar(QWidget):
    MAX_VAL = 20

    def __init__(self, name: str, value: int, parent=None):
        super().__init__(parent)
        self._name  = name
        self._value = value
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        name_lbl = QLabel(self._name)
        name_lbl.setFixedWidth(110)
        name_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        name_lbl.setStyleSheet("font-size: 12px; color: #444;")
        layout.addWidget(name_lbl)

        bar_bg = QFrame()
        bar_bg.setFixedHeight(14)
        bar_bg.setStyleSheet("background: #eeeeee; border-radius: 5px;")
        bar_bg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        filled = max(0, min(self._value, self.MAX_VAL))
        pct    = filled / self.MAX_VAL * 100

        bar_inner = QFrame(bar_bg)
        bar_inner.setStyleSheet(
            f"background: {_attr_color(self._value)}; border-radius: 5px;"
        )
        bar_inner.setFixedHeight(14)
        bar_bg._pct   = pct
        bar_bg._inner = bar_inner
        bar_bg.resizeEvent = lambda e, b=bar_bg: self._resize_bar(b, e)
        layout.addWidget(bar_bg)

        val_lbl = QLabel(str(self._value) if self._value > 0 else "—")
        val_lbl.setFixedWidth(28)
        val_lbl.setAlignment(Qt.AlignCenter)
        val_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {_attr_color(self._value)};"
        )
        layout.addWidget(val_lbl)

    @staticmethod
    def _resize_bar(bar_bg, event):
        w = int(bar_bg.width() * bar_bg._pct / 100)
        bar_bg._inner.setFixedWidth(max(0, w))


class AttributeGroup(QGroupBox):
    _GRP_STYLE = """
        QGroupBox {
            font-size: 13px; font-weight: bold;
            border: 1px solid #ddd; border-radius: 6px;
            margin-top: 8px; padding-top: 10px;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
    """

    def __init__(self, title: str, attrs: list[tuple[str, int]], parent=None):
        super().__init__(title, parent)
        self.setStyleSheet(self._GRP_STYLE)
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(12, 16, 12, 8)
        for name, val in attrs:
            layout.addWidget(AttributeBar(name, val))


# ── 信息卡片 ──────────────────────────────────────────────────────

class InfoCard(QGroupBox):
    _GRP_STYLE = """
        QGroupBox {
            font-size: 13px; font-weight: bold;
            border: 1px solid #ddd; border-radius: 6px;
            margin-top: 8px; padding-top: 10px;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
    """

    def __init__(self, title: str, fields: list[tuple[str, str]], parent=None):
        super().__init__(title, parent)
        self.setStyleSheet(self._GRP_STYLE)
        grid = QGridLayout(self)
        grid.setContentsMargins(12, 16, 12, 12)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)
        for i, (key, val) in enumerate(fields):
            row, col = divmod(i, 2)
            key_lbl = QLabel(f"{key}：")
            key_lbl.setStyleSheet("color: #888; font-size: 12px;")
            disp = str(val) if val not in (None, "", "nan", "NaN", "0000-00-00", "1900-01-01") else "—"
            val_lbl = QLabel(disp)
            val_lbl.setStyleSheet("font-size: 13px; font-weight: bold;")
            grid.addWidget(key_lbl, row, col * 2)
            grid.addWidget(val_lbl, row, col * 2 + 1)


# ── 球场位置图 ────────────────────────────────────────────────────

class PitchWidget(QWidget):
    """在球场俯视图上用彩色圆点标注各位置评分。"""

    # (x%, y%)：x=0 己方球门 → x=1 对方球门；y=0 上边线 → y=1 下边线
    POS_COORDS = {
        0:  (0.05, 0.50),   # GK
        2:  (0.22, 0.22),   # LB
        3:  (0.22, 0.50),   # CB
        4:  (0.22, 0.78),   # RB
        13: (0.35, 0.22),   # LWB
        5:  (0.38, 0.50),   # DM
        14: (0.35, 0.78),   # RWB
        6:  (0.55, 0.22),   # LM
        7:  (0.55, 0.50),   # CM
        8:  (0.55, 0.78),   # RM
        9:  (0.72, 0.28),   # AML
        10: (0.72, 0.50),   # AMC
        11: (0.72, 0.72),   # AMR
        12: (0.88, 0.50),   # ST
    }

    def __init__(self, positions: list[tuple[int, str, int]], parent=None):
        super().__init__(parent)
        self._pos_map = {idx: (name, val) for idx, name, val in positions}
        self.setMinimumSize(300, int(300 * 68 / 105))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        return int(w * 68 / 105)

    def sizeHint(self) -> QSize:
        return QSize(480, int(480 * 68 / 105))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        W, H = self.width(), self.height()
        mx = int(W * 0.04)
        my = int(H * 0.06)
        pw = W - 2 * mx
        ph = H - 2 * my

        # ── 背景 & 草地 ───────────────────────────────────────────
        painter.fillRect(0, 0, W, H, QColor("#1e2b1e"))
        painter.fillRect(mx, my, pw, ph, QColor("#2d4a2d"))

        # ── 线条 ──────────────────────────────────────────────────
        lc = QColor(255, 255, 255, 150)
        painter.setPen(QPen(lc, 1.2))
        painter.setBrush(Qt.NoBrush)

        # 外框
        painter.drawRect(mx, my, pw, ph)
        # 中线
        painter.drawLine(mx + pw // 2, my, mx + pw // 2, my + ph)
        # 中圈
        cr = int(ph * 0.135)
        cx_c, cy_c = mx + pw // 2, my + ph // 2
        painter.drawEllipse(QPoint(cx_c, cy_c), cr, cr)
        # 中点
        painter.setBrush(lc)
        painter.drawEllipse(QPoint(cx_c, cy_c), 2, 2)
        painter.setBrush(Qt.NoBrush)

        # 禁区 (16.5/105 深, 40.32/68 宽)
        pad_d = int(pw * 0.157)
        pad_h = int(ph * 0.593)
        pad_y = my + (ph - pad_h) // 2
        painter.drawRect(mx, pad_y, pad_d, pad_h)
        painter.drawRect(mx + pw - pad_d, pad_y, pad_d, pad_h)

        # 小禁区 (5.5/105 深, 18.32/68 宽)
        gad_d = int(pw * 0.052)
        gad_h = int(ph * 0.27)
        gad_y = my + (ph - gad_h) // 2
        painter.drawRect(mx, gad_y, gad_d, gad_h)
        painter.drawRect(mx + pw - gad_d, gad_y, gad_d, gad_h)

        # 球门
        goal_w = int(pw * 0.018)
        goal_h = int(ph * 0.14)
        goal_y = my + (ph - goal_h) // 2
        painter.drawRect(mx - goal_w, goal_y, goal_w, goal_h)
        painter.drawRect(mx + pw, goal_y, goal_w, goal_h)

        # 点球点
        ps_x = int(pw * 0.105)
        painter.setBrush(lc)
        for sx in (mx + ps_x, mx + pw - ps_x):
            painter.drawEllipse(QPoint(sx, cy_c), 2, 2)
        painter.setBrush(Qt.NoBrush)

        # ── 位置圆点 ──────────────────────────────────────────────
        dot_r = max(11, int(min(pw, ph) * 0.068))

        for idx, (x_pct, y_pct) in self.POS_COORDS.items():
            if idx not in self._pos_map:
                continue
            name, val = self._pos_map[idx]
            dx = mx + int(pw * x_pct)
            dy = my + int(ph * y_pct)
            color = QColor(_attr_color(val))

            # 阴影
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 70))
            painter.drawEllipse(QPoint(dx + 1, dy + 2), dot_r, dot_r)

            # 圆点
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(255, 255, 255, 180), 1.5))
            painter.drawEllipse(QPoint(dx, dy), dot_r, dot_r)

            # 数字
            painter.setPen(QColor("#ffffff"))
            f = QFont()
            f.setPixelSize(max(8, dot_r - 2))
            f.setBold(True)
            painter.setFont(f)
            painter.drawText(
                QRect(dx - dot_r, dy - dot_r, dot_r * 2, dot_r * 2),
                Qt.AlignCenter,
                str(val)
            )


class PositionGroup(QGroupBox):
    _GRP_STYLE = """
        QGroupBox {
            font-size: 13px; font-weight: bold;
            border: 1px solid #ddd; border-radius: 6px;
            margin-top: 8px; padding-top: 10px;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
    """

    def __init__(self, positions: list[tuple[int, str, int]], parent=None):
        super().__init__(i18n.t("位置评分"), parent)
        self.setStyleSheet(self._GRP_STYLE)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 16, 8, 8)
        row.setSpacing(12)

        # 左：球场图（限制最大宽度缩小）
        if positions:
            pitch = PitchWidget(positions)
            pitch.setMaximumWidth(320)
            row.addWidget(pitch, stretch=3)
        else:
            row.addWidget(QLabel("—"))

        # 右：位置文字列表
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 4, 0)
        right_layout.setSpacing(4)
        right_layout.setAlignment(Qt.AlignTop)

        if positions:
            for _, name, val in positions:
                color = _attr_color(val)
                lbl = QLabel(f"<span style='color:#555;font-size:13px;'>{name}</span>"
                             f"&nbsp;&nbsp;"
                             f"<span style='color:{color};font-size:14px;font-weight:bold;'>{val}</span>")
                lbl.setTextFormat(Qt.RichText)
                right_layout.addWidget(lbl)
        else:
            right_layout.addWidget(QLabel("—"))

        right_layout.addStretch()
        row.addWidget(right, stretch=2)


# ── 详情页 ────────────────────────────────────────────────────────

class DetailPage(QWidget):
    back_requested = pyqtSignal()
    club_selected  = pyqtSignal(int, str)   # (club_id, club_name)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapshot  = "26"
        self._player_id: int | None = None
        self._snap_btns: dict[str, QPushButton] = {}
        self._build_skeleton()
        i18n.register(self.retranslate_ui)

    def _build_skeleton(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── 顶部工具栏 ──────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setStyleSheet("background: #2c3e50;")
        toolbar.setFixedHeight(52)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 0, 16, 0)

        self._back_btn = QPushButton(i18n.t("← 返回列表"))
        self._back_btn.setStyleSheet("""
            QPushButton {
                color: white; background: transparent;
                border: 1px solid #aaa; border-radius: 4px;
                padding: 4px 12px; font-size: 13px;
            }
            QPushButton:hover { background: #34495e; }
        """)
        self._back_btn.clicked.connect(self.back_requested)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")

        # 快照切换按钮（24 / 25 / 26）
        self._snap_label = QLabel(i18n.t("赛季："))
        self._snap_label.setStyleSheet("color: #aaa; font-size: 12px;")

        btn_style = """
            QPushButton { color: #ccc; background: #34495e; border: none;
                          border-radius: 4px; padding: 4px 8px; font-size: 12px; }
            QPushButton:checked { background: #3498db; color: white; }
            QPushButton:hover   { background: #2980b9; color: white; }
        """
        for snap in SNAPSHOTS:
            btn = QPushButton(f"20{snap}")
            btn.setCheckable(True)
            btn.setFixedWidth(52)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda _, s=snap: self._switch_snapshot(s))
            self._snap_btns[snap] = btn

        self._snap_btns[self._snapshot].setChecked(True)

        tb_layout.addWidget(self._back_btn)
        tb_layout.addSpacing(16)
        tb_layout.addWidget(self._title_lbl)
        tb_layout.addStretch()
        tb_layout.addWidget(self._snap_label)
        for btn in self._snap_btns.values():
            tb_layout.addWidget(btn)
        outer.addWidget(toolbar)

        # ── 可滚动内容区 ────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #f8f8f8; }")
        self._content = QWidget()
        self._content.setStyleSheet("background: #f8f8f8;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(20, 16, 20, 24)
        self._content_layout.setSpacing(12)
        self._content_layout.addStretch()
        scroll.setWidget(self._content)
        outer.addWidget(scroll)

    def _clear_content(self):
        def _clear_layout(lo):
            while lo.count():
                item = lo.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    _clear_layout(item.layout())
        _clear_layout(self._content_layout)

    def retranslate_ui(self):
        self._back_btn.setText(i18n.t("← 返回列表"))
        self._snap_label.setText(i18n.t("赛季："))
        if self._player_id is not None:
            self._render()

    def load_player(self, player_id: int):
        self._player_id = player_id
        self._render()

    def _switch_snapshot(self, snapshot: str):
        self._snapshot = snapshot
        for s, btn in self._snap_btns.items():
            btn.setChecked(s == snapshot)
        if self._player_id is not None:
            self._render()

    def _render(self):
        snap = self._snapshot
        row  = loader.get_player(self._player_id, snap)

        # 获取所有快照数据（用于计算变化量）
        all_snaps = loader.get_player_all_snapshots(self._player_id)

        name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
        self._title_lbl.setText(name)

        self._clear_content()
        layout = self._content_layout

        def safe(key: str) -> str:
            v = row.get(key)
            if v is None or str(v) in ("", "nan", "NaN", "0", "0000-00-00", "1900-01-01"):
                return "—"
            return str(v)

        def safe_salary() -> str:
            v = row.get("salary")
            if not v:
                return "—"
            try:
                return f"€{int(v):,}"
            except (ValueError, TypeError):
                return "—"

        def ability_with_change(field: str) -> str:
            cur = row.get(field)
            val = str(int(cur)) if cur is not None else "—"
            # 找当前快照的前一个快照计算变化
            idx = SNAPSHOTS.index(snap) if snap in SNAPSHOTS else -1
            if idx > 0:
                prev_snap = SNAPSHOTS[idx - 1]
                prev_row  = all_snaps.get(prev_snap)
                if prev_row:
                    prev_val = prev_row.get(field)
                    if prev_val is not None and cur is not None:
                        diff = int(cur) - int(prev_val)
                        if diff > 0:   val += f"  ▲{diff}"
                        elif diff < 0: val += f"  ▼{abs(diff)}"
            return val

        # ── 基本信息 ────────────────────────────────────────────
        nation_disp = loader.nation_name(row.get("nation_id")) or safe("nation_id")
        club_id     = row.get("club_id")
        club_disp   = loader.club_name(club_id) or "—"
        layout.addWidget(InfoCard(i18n.t("基本信息"), [
            (i18n.t("姓名"),       name),
            (i18n.t("出生日期"),   safe("birth_date")),
            (i18n.t("年龄"),       loader.calc_age(safe("birth_date"))),
            (i18n.t("身高"),       f"{safe('height')} cm"),
            (i18n.t("国籍"),       nation_disp),
            (i18n.t("球衣号"),     safe("play_number")),
            (i18n.t("薪资（/周）"), safe_salary()),
        ]))

        # ── 所属球队（可点击）────────────────────────────────────
        club_row = QHBoxLayout()
        club_row.setContentsMargins(4, 0, 4, 0)
        club_lbl = QLabel(i18n.t("所属球队："))
        club_lbl.setStyleSheet("color: #888; font-size: 12px;")
        if club_id and club_disp != "—":
            club_btn = QPushButton(club_disp)
            club_btn.setFlat(True)
            club_btn.setCursor(Qt.PointingHandCursor)
            club_btn.setStyleSheet("""
                QPushButton {
                    color: #3498db; font-size: 13px; font-weight: bold;
                    border: none; background: transparent;
                    text-align: left; padding: 0;
                }
                QPushButton:hover { color: #2980b9; text-decoration: underline; }
            """)
            club_btn.clicked.connect(lambda _, cid=int(club_id), cn=club_disp:
                                     self.club_selected.emit(cid, cn))
            club_row.addWidget(club_lbl)
            club_row.addWidget(club_btn)
        else:
            club_row.addWidget(club_lbl)
            club_row.addWidget(QLabel("—"))
        club_row.addStretch()
        layout.addLayout(club_row)

        # ── 能力值 ──────────────────────────────────────────────
        prev_label = ""
        if snap in SNAPSHOTS and SNAPSHOTS.index(snap) > 0:
            prev = SNAPSHOTS[SNAPSHOTS.index(snap) - 1]
            if i18n.get_lang() == "zh":
                prev_label = f" · △为20{prev}→20{snap}变化"
            else:
                prev_label = f" · △ 20{prev}→20{snap}"
        if i18n.get_lang() == "zh":
            ability_title = f"能力值（当前快照{prev_label}）"
        else:
            ability_title = f"Ability (Snapshot{prev_label})"
        layout.addWidget(InfoCard(ability_title, [
            (i18n.t("当前能力"), ability_with_change("ability_now")),
            (i18n.t("潜力上限"), ability_with_change("ability_potential")),
        ]))

        # ── 位置 ────────────────────────────────────────────────
        positions = loader.get_positions(row)
        layout.addWidget(PositionGroup(positions))

        # ── 技术属性各组 ────────────────────────────────────────
        for group_title, attr_dict in ATTRIBUTE_GROUPS:
            attrs = loader.get_attrs(row, attr_dict)
            layout.addWidget(AttributeGroup(i18n.t(group_title), attrs))

        # ── 性格属性 ────────────────────────────────────────────
        personality_attrs = loader.get_personality_attrs(row)
        layout.addWidget(AttributeGroup(i18n.t("性格"), personality_attrs))

        layout.addStretch()