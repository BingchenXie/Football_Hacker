"""
Football Hacker — PyQt5 球员浏览器

运行方式：
    cd football_viewer
    python main.py
"""

import sys
import traceback
from pathlib import Path

# 确保能找到同目录的模块
sys.path.insert(0, str(Path(__file__).parent))

from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget, QSplashScreen, QLabel, QMessageBox, QPushButton
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont


def _global_except_hook(exc_type, exc_value, exc_tb):
    """将未捕获的 Python 异常显示为弹窗，而不是直接崩溃。"""
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("发生错误")
        box.setText(str(exc_value))
        box.setDetailedText(msg)
        box.exec_()
    except Exception:
        print(msg, file=sys.stderr)


sys.excepthook = _global_except_hook

import i18n
from data_loader import loader
from list_page import ListPage
from detail_page import DetailPage
from club_page import ClubPage


# ── 后台加载线程 ──────────────────────────────────────────────────

class LoadThread(QThread):
    finished = pyqtSignal()

    def run(self):
        loader.load()
        self.finished.emit()


# ── 主窗口 ────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Football Hacker")
        self.resize(1100, 760)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # 加载中占位页
        self._loading_lbl = QLabel(i18n.t("正在加载球员数据，请稍候…"))
        self._loading_lbl.setAlignment(Qt.AlignCenter)
        self._loading_lbl.setFont(QFont("Arial", 16))
        self._stack.addWidget(self._loading_lbl)   # index 0

        # 语言切换按钮（状态栏）
        self._lang_btn = QPushButton("EN")
        self._lang_btn.setFixedWidth(42)
        self._lang_btn.setStyleSheet("""
            QPushButton {
                font-size: 12px; font-weight: bold;
                border: 1px solid #aaa; border-radius: 4px;
                padding: 2px 6px; background: #f5f5f5;
            }
            QPushButton:hover { background: #e0e0e0; }
        """)
        self._lang_btn.clicked.connect(self._toggle_lang)
        self.statusBar().addPermanentWidget(self._lang_btn)
        self.statusBar().setStyleSheet("QStatusBar { font-size: 12px; }")

        self._list_page:   ListPage   | None = None
        self._detail_page: DetailPage | None = None
        self._club_page:   ClubPage   | None = None

        # 后台读取 CSV
        self._loader_thread = LoadThread()
        self._loader_thread.finished.connect(self._on_data_loaded)
        self._loader_thread.start()

    def _on_data_loaded(self):
        try:
            self._list_page   = ListPage()
            self._detail_page = DetailPage()
            self._club_page   = ClubPage()

            self._stack.addWidget(self._list_page)    # index 1
            self._stack.addWidget(self._detail_page)  # index 2
            self._stack.addWidget(self._club_page)    # index 3

            self._list_page.player_selected.connect(self._show_detail)
            self._detail_page.back_requested.connect(self._show_list)
            self._detail_page.club_selected.connect(self._show_club)
            self._club_page.back_requested.connect(self._show_detail_from_club)
            self._club_page.player_selected.connect(self._show_detail)

            self._stack.setCurrentIndex(1)
        except Exception:
            _global_except_hook(*sys.exc_info())

    def _show_detail(self, player_id: int):
        self._detail_page.load_player(player_id)
        self._stack.setCurrentWidget(self._detail_page)

    def _show_list(self):
        self._stack.setCurrentWidget(self._list_page)

    def _show_club(self, club_id: int, club_name: str):
        self._club_page.load_club(club_id, club_name)
        self._stack.setCurrentWidget(self._club_page)

    def _toggle_lang(self):
        i18n.toggle()
        self._lang_btn.setText("中" if i18n.get_lang() == "en" else "EN")
        self._loading_lbl.setText(i18n.t("正在加载球员数据，请稍候…"))

    def _show_detail_from_club(self):
        self._stack.setCurrentWidget(self._detail_page)


# ── 入口 ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Arial", 12))

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())