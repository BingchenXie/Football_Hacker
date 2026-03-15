"""
俱乐部球员页：展示某俱乐部在当前快照下的所有球员。
"""

from PyQt5.QtCore import Qt, QModelIndex, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableView, QHeaderView, QAbstractItemView,
    QDialog, QScrollArea, QFrame, QSizePolicy,
)
from PyQt5.QtGui import QFont

from data_loader import loader, SNAPSHOTS, DEFAULT_SNAPSHOT
from list_page import PlayerTableModel
from recommender import Recommender, player_from_db_row
import i18n


# ── 后台推荐线程 ──────────────────────────────────────────────────

class _RecommendThread(QThread):
    done    = pyqtSignal(list)   # list of result dicts
    error   = pyqtSignal(str)

    def __init__(self, club_id: int, snapshot: str, n_runs: int = 5,
                 temperature: float = 1.2):
        super().__init__()
        self._club_id    = club_id
        self._snapshot   = snapshot
        self._n_runs     = n_runs
        self._temperature = temperature

    def run(self):
        try:
            rec = Recommender()

            squad_rows = loader.get_club_players_full(self._club_id, self._snapshot)
            cand_rows  = loader.get_candidates(self._club_id, self._snapshot,
                                               min_ability=100)

            squad  = [player_from_db_row(r) for r in squad_rows]
            cands  = [player_from_db_row(r) for r in cand_rows]
            sq_ids = {p["id"] for p in squad}

            results = rec.recommend_multi(
                current_players=squad,
                candidate_players=cands,
                exclude_ids=sq_ids,
                n_runs=self._n_runs,
                temperature=self._temperature,
            )
            self.done.emit(results)
        except Exception as e:
            import traceback
            self.error.emit(traceback.format_exc())


# ── 推荐结果弹窗 ──────────────────────────────────────────────────

class RecommendDialog(QDialog):
    player_selected = pyqtSignal(int)

    _BTN_STYLE = """
        QPushButton {
            color: white; background: #2ecc71; border: none;
            border-radius: 5px; padding: 6px 18px; font-size: 13px; font-weight: bold;
        }
        QPushButton:hover    { background: #27ae60; }
        QPushButton:disabled { background: #aaa; }
    """
    _CLOSE_STYLE = """
        QPushButton {
            color: #555; background: #ecf0f1; border: none;
            border-radius: 5px; padding: 6px 18px; font-size: 13px;
        }
        QPushButton:hover { background: #dde; }
    """

    def __init__(self, club_id: int, club_name: str, snapshot: str, parent=None):
        super().__init__(parent)
        self._club_id   = club_id
        self._club_name = club_name
        self._snapshot  = snapshot
        self._thread: _RecommendThread | None = None

        if i18n.get_lang() == "zh":
            self.setWindowTitle(f"引援推荐 — {club_name}")
        else:
            self.setWindowTitle(f"Signing Recommendations — {club_name}")
        self.setMinimumWidth(680)
        self.setMinimumHeight(480)
        self._build_ui()
        self._run()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # 标题行
        if i18n.get_lang() == "zh":
            title_text = f"为 <b>{self._club_name}</b> 推荐引援"
        else:
            title_text = f"Recommended Signings for <b>{self._club_name}</b>"
        title = QLabel(title_text)
        title.setStyleSheet("font-size: 15px; color: #2c3e50;")
        root.addWidget(title)

        # 需求提示（填充后显示）
        self._demand_lbl = QLabel("")
        self._demand_lbl.setStyleSheet("font-size: 12px; color: #888;")
        self._demand_lbl.setWordWrap(True)
        root.addWidget(self._demand_lbl)

        # 滚动结果区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #ddd; border-radius: 6px; background: white; }")
        self._results_container = QWidget()
        self._results_container.setStyleSheet("background: white;")
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(0)
        self._results_layout.addStretch()
        scroll.setWidget(self._results_container)
        root.addWidget(scroll, stretch=1)

        # 状态标签
        self._status_lbl = QLabel(i18n.t("正在分析阵容，请稍候…"))
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setStyleSheet("font-size: 13px; color: #888;")
        root.addWidget(self._status_lbl)

        # 按钮行
        btn_row = QHBoxLayout()
        self._rerun_btn = QPushButton(i18n.t("重新推荐"))
        self._rerun_btn.setStyleSheet(self._BTN_STYLE)
        self._rerun_btn.setEnabled(False)
        self._rerun_btn.clicked.connect(self._run)

        close_btn = QPushButton(i18n.t("关闭"))
        close_btn.setStyleSheet(self._CLOSE_STYLE)
        close_btn.clicked.connect(self.reject)

        btn_row.addWidget(self._rerun_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    def _run(self):
        self._rerun_btn.setEnabled(False)
        self._status_lbl.setText(i18n.t("正在分析阵容，请稍候…"))
        self._demand_lbl.setText("")
        self._clear_results()

        self._thread = _RecommendThread(self._club_id, self._snapshot)
        self._thread.done.connect(self._on_done)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _clear_results(self):
        layout = self._results_layout
        while layout.count() > 1:          # keep trailing stretch
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_done(self, results: list):
        if i18n.get_lang() == "zh":
            self._status_lbl.setText(f"共推荐 {len(results)} 名球员  ·  双击查看详情")
        else:
            self._status_lbl.setText(f"{len(results)} players recommended  ·  Double-click to view")
        self._rerun_btn.setEnabled(True)

        if results:
            desc = results[0]["profile_desc"]
            pos_pairs = [(i18n.pos_t(n), v) for n, v in desc["positions"]]
            pos_str = " / ".join(f"{n}({v})" for n, v in pos_pairs)
            if i18n.get_lang() == "zh":
                self._demand_lbl.setText(
                    f"模型需求画像  ·  位置：{pos_str or '—'}  "
                    f"能力≈{desc['ability_now']}  潜力≈{desc['ability_pot']}  "
                    f"年龄≈{desc['age_approx']}岁"
                )
            else:
                self._demand_lbl.setText(
                    f"Model Profile  ·  Position: {pos_str or '—'}  "
                    f"Ability≈{desc['ability_now']}  Potential≈{desc['ability_pot']}  "
                    f"Age≈{desc['age_approx']}"
                )

        self._clear_results()
        for rank, r in enumerate(results, 1):
            card = self._make_card(rank, r)
            self._results_layout.insertWidget(
                self._results_layout.count() - 1, card
            )

    def _on_error(self, msg: str):
        self._status_lbl.setText(i18n.t("推荐失败，请检查模型文件是否存在。"))
        self._rerun_btn.setEnabled(True)
        print(msg)

    def _make_card(self, rank: int, r: dict) -> QWidget:
        p    = r["player"]
        desc = r["profile_desc"]
        score = r["score"]

        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or "—"
        pos  = " / ".join(f"{i18n.pos_t(n)}({v})" for n, v in desc["positions"]) or "—"
        tech   = "  ".join(f"{i18n.attr_name_t(n)} {v}" for n, v in desc["tech"])
        mental = "  ".join(f"{i18n.attr_name_t(n)} {v}" for n, v in desc["mental"])
        phys   = "  ".join(f"{i18n.attr_name_t(n)} {v}" for n, v in desc["physical"])

        ability_now = p.get("ability_now") or desc["ability_now"]
        ability_pot = p.get("ability_potential") or desc["ability_pot"]

        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet("""
            QFrame { background: white; border-bottom: 1px solid #eee; }
            QFrame:hover { background: #f0f7ff; }
        """)

        row = QHBoxLayout(card)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        # 排名
        rank_lbl = QLabel(f"#{rank}")
        rank_lbl.setFixedWidth(28)
        rank_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #bbb;")
        rank_lbl.setAlignment(Qt.AlignCenter)
        row.addWidget(rank_lbl)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #eee;")
        row.addWidget(sep)

        # 球员信息（左）
        info = QVBoxLayout()
        info.setSpacing(3)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        if i18n.get_lang() == "zh":
            pos_prefix   = "推荐位置："
            attr_fmt     = f"技术：{tech}   心理：{mental}   身体：{phys}"
            ab_text      = f"能力 {ability_now}  潜力 {ability_pot}"
        else:
            pos_prefix   = "Recommended Position: "
            attr_fmt     = f"Technical: {tech}   Mental: {mental}   Physical: {phys}"
            ab_text      = f"Ability {ability_now}  Potential {ability_pot}"
        pos_lbl = QLabel(f"{pos_prefix}{pos}")
        pos_lbl.setStyleSheet("font-size: 12px; color: #555;")
        attrs_lbl = QLabel(attr_fmt)
        attrs_lbl.setStyleSheet("font-size: 11px; color: #888;")
        attrs_lbl.setWordWrap(True)
        info.addWidget(name_lbl)
        info.addWidget(pos_lbl)
        info.addWidget(attrs_lbl)
        row.addLayout(info, stretch=1)

        # 能力 + 相似度（右）
        right = QVBoxLayout()
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right.setSpacing(2)
        ab_lbl = QLabel(ab_text)
        ab_lbl.setAlignment(Qt.AlignRight)
        ab_lbl.setStyleSheet("font-size: 12px; color: #34495e; font-weight: bold;")

        pct = int(score * 100)
        color = "#2ecc71" if pct >= 90 else "#f39c12" if pct >= 80 else "#e74c3c"
        score_text = f"匹配度 {pct}%" if i18n.get_lang() == "zh" else f"Match {pct}%"
        score_lbl = QLabel(score_text)
        score_lbl.setAlignment(Qt.AlignRight)
        score_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};")

        right.addWidget(ab_lbl)
        right.addWidget(score_lbl)
        row.addLayout(right)

        # 双击事件
        pid = p.get("id")
        if pid:
            card.mouseDoubleClickEvent = lambda _e, i=pid: self._on_player_dbl(i)

        return card

    def _on_player_dbl(self, player_id: int):
        self.player_selected.emit(player_id)
        self.accept()


# ── 俱乐部页面 ────────────────────────────────────────────────────

class ClubPage(QWidget):
    back_requested  = pyqtSignal()
    player_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._club_id:   int | None = None
        self._club_name: str = ""
        self._snapshot   = DEFAULT_SNAPSHOT
        self._snap_btns: dict[str, QPushButton] = {}
        self._model = PlayerTableModel()
        self._club_count = 0
        self._build_ui()
        i18n.register(self.retranslate_ui)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 顶部工具栏 ────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setStyleSheet("background: #2c3e50;")
        toolbar.setFixedHeight(52)
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 0, 16, 0)

        self._back_btn = QPushButton(i18n.t("← 返回球员"))
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

        self._count_lbl = QLabel()
        self._count_lbl.setStyleSheet("color: #aaa; font-size: 13px;")

        # 推荐引援按钮
        self._rec_btn = QPushButton(i18n.t("推荐引援"))
        self._rec_btn.setStyleSheet("""
            QPushButton {
                color: white; background: #27ae60; border: none;
                border-radius: 4px; padding: 4px 14px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover    { background: #2ecc71; }
            QPushButton:disabled { background: #aaa; }
        """)
        self._rec_btn.setEnabled(False)
        self._rec_btn.clicked.connect(self._open_recommend)

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

        tb.addWidget(self._back_btn)
        tb.addSpacing(16)
        tb.addWidget(self._title_lbl)
        tb.addSpacing(12)
        tb.addWidget(self._count_lbl)
        tb.addSpacing(16)
        tb.addWidget(self._rec_btn)
        tb.addStretch()
        tb.addWidget(self._snap_label)
        for btn in self._snap_btns.values():
            tb.addWidget(btn)
        layout.addWidget(toolbar)

        # ── 表格 ──────────────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet("background: #f8f8f8;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 12, 16, 12)

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, self._model.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(2, Qt.DescendingOrder)
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
        cl.addWidget(self._table)

        self._hint_lbl = QLabel(i18n.t("双击行查看球员详情  ·  点击表头排序"))
        self._hint_lbl.setStyleSheet("color: gray; font-size: 12px;")
        cl.addWidget(self._hint_lbl)

        layout.addWidget(content)

    def load_club(self, club_id: int, club_name: str):
        self._club_id   = club_id
        self._club_name = club_name
        self._rec_btn.setEnabled(True)
        self._refresh()

    def _switch_snapshot(self, snapshot: str):
        self._snapshot = snapshot
        for s, btn in self._snap_btns.items():
            btn.setChecked(s == snapshot)
        if self._club_id is not None:
            self._refresh()

    def retranslate_ui(self):
        self._back_btn.setText(i18n.t("← 返回球员"))
        self._snap_label.setText(i18n.t("赛季："))
        self._rec_btn.setText(i18n.t("推荐引援"))
        self._hint_lbl.setText(i18n.t("双击行查看球员详情  ·  点击表头排序"))
        self._update_count(self._club_count)
        self._model.headerDataChanged.emit(Qt.Horizontal, 0, self._model.columnCount() - 1)
        self._model._apply_sort()
        self._model.layoutChanged.emit()

    def _update_count(self, n: int):
        self._club_count = n
        if i18n.get_lang() == "zh":
            self._count_lbl.setText(f"共 {n} 名球员")
        else:
            self._count_lbl.setText(f"{n} players")

    def _refresh(self):
        rows = loader.get_club_players(self._club_id, self._snapshot)
        self._model.set_data(rows)
        self._title_lbl.setText(self._club_name)
        self._update_count(len(rows))

    def _open_recommend(self):
        if self._club_id is None:
            return
        dlg = RecommendDialog(self._club_id, self._club_name,
                              self._snapshot, parent=self)
        dlg.player_selected.connect(self.player_selected)
        dlg.exec_()

    def _on_header_clicked(self, logical_index: int):
        model = self._model
        if model._sort_col == logical_index:
            new_asc = not model._sort_asc
        else:
            new_asc = logical_index in (0, 6)
        new_order = Qt.AscendingOrder if new_asc else Qt.DescendingOrder
        self._table.horizontalHeader().setSortIndicator(logical_index, new_order)
        model.sort(logical_index, new_order)

    def _on_double_click(self, index: QModelIndex):
        player_id = self._model.data(index, Qt.UserRole)
        if player_id:
            self.player_selected.emit(player_id)
