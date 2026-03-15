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

from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget, QSplashScreen, QLabel, QMessageBox
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

from data_loader import loader
from list_page import ListPage
from detail_page import DetailPage


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
        loading = QLabel("正在加载球员数据，请稍候…")
        loading.setAlignment(Qt.AlignCenter)
        loading.setFont(QFont("Arial", 16))
        self._stack.addWidget(loading)   # index 0

        self._list_page: ListPage | None = None
        self._detail_page: DetailPage | None = None

        # 后台读取 CSV
        self._loader_thread = LoadThread()
        self._loader_thread.finished.connect(self._on_data_loaded)
        self._loader_thread.start()

    def _on_data_loaded(self):
        try:
            self._list_page   = ListPage()
            self._detail_page = DetailPage()

            self._stack.addWidget(self._list_page)    # index 1
            self._stack.addWidget(self._detail_page)  # index 2

            self._list_page.player_selected.connect(self._show_detail)
            self._detail_page.back_requested.connect(self._show_list)

            self._stack.setCurrentIndex(1)
        except Exception:
            _global_except_hook(*sys.exc_info())

    def _show_detail(self, player_id: int):
        self._detail_page.load_player(player_id)
        self._stack.setCurrentWidget(self._detail_page)

    def _show_list(self):
        self._stack.setCurrentWidget(self._list_page)


# ── 入口 ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Arial", 12))

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())