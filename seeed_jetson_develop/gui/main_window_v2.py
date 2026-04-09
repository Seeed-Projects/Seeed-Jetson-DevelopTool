"""
Seeed Jetson Develop Tool - 主窗口 V2
无边框大气风格 - 用背景层次代替线条
"""
import json
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QPoint, QEvent, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QPixmap, QPainter
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame,
    QVBoxLayout, QHBoxLayout, QGridLayout, QBoxLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QToolButton, QMenu,
    QProgressBar, QTextEdit, QScrollArea, QDialog, QFileDialog, QMessageBox,
    QStackedWidget, QSizePolicy,
)

# 使用新的无边框主题
from .theme import (
    C_BG, C_BG_DEEP, C_BG_LIGHT, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_GREEN2, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt, make_label, make_button, make_card, make_input_card,
    make_section_header, apply_shadow, apply_app_theme, build_app_font,
    create_themed_message_box,
)
from ..flash import JetsonFlasher, sudo_authenticate, sudo_check_cached
from ..core.platform_detect import is_jetson
from ..core.events import bus
from ..modules.remote.jetson_init import open_jetson_init_dialog
from .flash_animation import FlashAnimationWidget
from .ai_chat import FloatingAIAssistant, build_ai_system_prompt
from .runtime_i18n import apply_language, translate_text


log = logging.getLogger("seeed")


# ─────────────────────────────────────────────
#  颜色常量（兼容旧代码）
# ─────────────────────────────────────────────
C_SIDEBAR   = C_BG_DEEP
C_TOPBAR    = C_BG_DEEP


def shadow(widget, blur=20, y=4, alpha=60):
    """兼容旧代码的阴影函数"""
    return apply_shadow(widget, blur, y, alpha)


def card_frame(radius=12):
    """兼容旧代码的卡片函数"""
    return make_card(radius)


def make_btn(text, primary=False, danger=False, small=False):
    """兼容旧代码的按钮函数"""
    return make_button(text, primary, small, danger)


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        scene_w = 96
        scene_h = 34
        cell = max(4, min(self.width() // scene_w, self.height() // scene_h))
        ox = (self.width() - scene_w * cell) // 2
        oy = (self.height() - scene_h * cell) // 2

        def block(x, y, w=1, h=1, color="#ffffff"):
            painter.fillRect(ox + x * cell, oy + y * cell, w * cell, h * cell, QColor(color))

        def pixel_art(x, y, pattern, palette):
            for row_idx, row in enumerate(pattern):
                for col_idx, key in enumerate(row):
                    if key == " ":
                        continue
                    color = palette.get(key)
                    if color:
                        block(x + col_idx, y + row_idx, color=color)

        sky_top = "#0f1823"
        sky_mid = "#152232"
        sky_low = "#1d2b3b"
        ridge_a = "#233247"
        ridge_b = "#2b3c50"
        ground = "#23392c"
        ground_high = "#45634b"
        soil = "#4b4538"
        soil_high = "#6a604f"
        hut_roof = "#64513e"
        hut_roof_dark = "#4f3f31"
        hut_wall = "#776853"
        hut_shadow = "#5f513e"
        window_on = "#a8d679"
        window_off = "#62705d"
        tree_leaf = "#41684a"
        tree_leaf_dark = "#2f5238"
        tree_trunk = "#5b4939"
        rail = "#274453"
        rail_dark = "#203743"
        dock = "#314e60"
        dock_dark = "#243a47"
        dock_screen = "#7ddbd3"
        dock_success = "#97dd74"
        dock_error = "#c86b6b"
        packet = "#70d2c8"
        packet_glow = "#a1ece4"
        packet_success = "#9fdf74"
        star = "#d6e7c6"
        red = "#c96a6a"
        capsule_off = "#2b3844"

        painter.fillRect(self.rect(), QColor(C_CARD_LIGHT))
        for y in range(0, 10):
            block(0, y, scene_w, 1, sky_top)
        for y in range(10, 20):
            block(0, y, scene_w, 1, sky_mid)
        for y in range(20, 24):
            block(0, y, scene_w, 1, sky_low)

        for idx in range(6):
            sx = 8 + idx * 14
            if self._mode == "success" or (self._frame + idx * 2) % 5 < 3:
                block(sx, 3 + idx % 3, color=star)

        for i in range(12):
            block(4 + i, 20 - i, 1, i + 4, ridge_a)
        for i in range(14):
            block(18 + i, 18 - i, 1, i + 6, ridge_b)
        for i in range(12):
            block(37 + i, 19 - i, 1, i + 5, ridge_a)

        block(0, 24, scene_w, 10, ground)
        block(0, 24, scene_w, 2, ground_high)
        block(0, 28, scene_w, 6, soil)
        block(10, 29, 70, 2, soil_high)
        for x in range(8, 82, 9):
            block(x, 30 + ((x // 9) % 2), 2, 1, "#85745d")

        pixel_art(10, 16, [
            "   rrrrr   ",
            "  rrwwwrr  ",
            " rrrrrrrrr ",
            " tbbbbbbt  ",
            " tbbllbbt  ",
            " tbbddbbt  ",
            " tbbbbbbt  ",
            " ttt  ttt  ",
        ], {
            "r": hut_roof,
            "w": hut_roof_dark,
            "t": hut_wall,
            "b": hut_wall,
            "l": window_on if self._mode in {"running", "success"} else window_off,
            "d": hut_shadow,
        })

        pixel_art(6, 17, [
            "  aa  ",
            " abba ",
            "abbba ",
            "  tt  ",
            "  tt  ",
        ], {
            "a": tree_leaf,
            "b": tree_leaf_dark,
            "t": tree_trunk,
        })

        pixel_art(67, 17, [
            "  mmmmmmm  ",
            " mmsssssmm ",
            " mslllllsm ",
            " mslllllsm ",
            " msdddddsm ",
            "  t t t t  ",
        ], {
            "m": dock,
            "s": dock_dark,
            "l": dock_screen if self._mode == "running" else (dock_success if self._mode == "success" else dock_error if self._mode == "error" else "#56737a"),
            "d": dock_dark,
            "t": "#91a7b2",
        })

        for idx in range(12):
            color = capsule_off
            if self._mode == "running" and idx <= max(1, self._progress // 9):
                if idx in {(self._frame // 2) % 12, ((self._frame // 2) + 1) % 12}:
                    color = packet_glow
                else:
                    color = packet
            elif self._mode == "success":
                color = packet_success
            elif self._mode == "error":
                color = red if idx % 2 == self._frame % 2 else capsule_off
            block(30 + idx * 3, 3, 2, 1, color)

        for x in range(26, 69, 4):
            block(x, 21, 2, 1, rail_dark)

        if self._mode in {"idle", "running", "success"}:
            packet_color = packet if self._mode != "success" else packet_success
            points = [(26 + idx * 4, 21 - (1 if idx in {3, 4, 5} else 0)) for idx in range(11)]
            if self._mode == "idle":
                points = points[:2]
            elif self._mode == "running":
                count = max(3, min(len(points), self._progress // 10 + 2))
                start = (self._frame // 2) % len(points)
                points = [points[(start + idx) % len(points)] for idx in range(count)]
            for idx, (x, y) in enumerate(points):
                tone = packet_glow if self._mode == "running" and idx % 3 == 1 else packet_color
                block(x, y, 2, 1, tone)

        if self._mode == "running":
            scan_x = 70 + (self._frame % 5)
            block(scan_x, 19, 1, 3, packet_glow)
            orbit = [(76, 15), (80, 14), (84, 16)]
            for idx, (x, y) in enumerate(orbit):
                if (self._frame + idx) % 4 < 2:
                    block(x, y, color=packet_glow)
            for idx in range(5):
                x = 30 + ((self._frame + idx * 3) % 28)
                block(x, 24, 1, 1, "#83c06b")

        if self._mode == "success":
            for idx in range(5):
                sx = 24 + idx * 13
                sy = 8 + (idx % 2)
                block(sx, sy, color="#d9f2b4")
                block(sx + 1, sy + 1, color="#d9f2b4")
            block(73, 14, 2, 1, "#d9f2b4")
            block(75, 15, 2, 1, "#d9f2b4")
            block(77, 16, 4, 1, "#d9f2b4")

        if self._mode == "error":
            block(46, 19, 3, 1, red)
            block(47, 20, 1, 2, red)
            block(45, 21, 1, 1, red)
            block(49, 21, 1, 1, red)
            for idx in range(4):
                x = 68 + idx * 4
                if idx != (self._frame // 2) % 4:
                    block(x, 15, 1, 1, red)


# ─────────────────────────────────────────────
#  Flash 线程
# ─────────────────────────────────────────────
class FlashThread(QThread):
    progress_msg      = pyqtSignal(str)
    progress_val      = pyqtSignal(int)
    progress_log      = pyqtSignal(str)          # 实时日志行
    download_progress = pyqtSignal(int, int)     # (downloaded_bytes, total_bytes)  total=0 表示未知
    finished          = pyqtSignal(bool, str)

    def __init__(self, product, l4t, skip_verify=False, download_only=False,
                 force_redownload=False, prepare_only=False, flash_only=False):
        super().__init__()
        self.product = product
        self.l4t = l4t
        self.skip_verify = skip_verify
        self.download_only = download_only
        self.force_redownload = force_redownload
        self.prepare_only = prepare_only
        self.flash_only = flash_only
        self._cancel = False

    def cancel(self): self._cancel = True

    def run(self):
        try:
            flasher = JetsonFlasher(self.product, self.l4t,
                                    progress_callback=self._on_dl,
                                    should_cancel=lambda: self._cancel)
            self.progress_msg.emit("初始化..."); self.progress_val.emit(2)

            # flash_only：跳过下载/解压，直接刷写
            if self.flash_only:
                self.progress_msg.emit("刷写中..."); self.progress_val.emit(10)
                if not flasher.flash_firmware():
                    self.finished.emit(False, "刷写失败"); return
                self.progress_val.emit(100)
                self.finished.emit(True, "刷写完成！"); return

            if self.force_redownload or not flasher.firmware_cached():
                self.progress_msg.emit("下载固件中..."); self.progress_val.emit(5)
                if not flasher.download_firmware(force_redownload=self.force_redownload):
                    self.finished.emit(False, "固件下载失败"); return
            else:
                self.progress_msg.emit("压缩包已存在，跳过下载"); self.progress_val.emit(50)

            self.progress_val.emit(50)
            if not self.skip_verify:
                self.progress_msg.emit("校验 SHA256...")
                if not flasher.verify_firmware():
                    self.finished.emit(False, "SHA256 校验失败"); return
            self.progress_val.emit(60)
            if self.download_only:
                self.progress_val.emit(100)
                self.finished.emit(True, "固件下载完成（未刷写）"); return
            self.progress_msg.emit("解压固件...")
            if not flasher.extract_firmware():
                self.finished.emit(False, "固件解压失败"); return
            self.progress_val.emit(80)
            if self.prepare_only:
                self.progress_val.emit(100)
                self.finished.emit(True, "下载并解压完成，可进入下一步刷写"); return
            self.progress_msg.emit("刷写中...")
            if not flasher.flash_firmware():
                self.finished.emit(False, "刷写失败"); return
            self.progress_val.emit(100)
            self.finished.emit(True, "刷写完成！")
        except Exception as e:
            self.finished.emit(False, str(e))

    def _on_dl(self, stage, cur, total):
        if stage == "download":
            # 无论 total 是否已知，都发出真实字节进度
            self.download_progress.emit(int(cur), int(total))
            if total:
                pct = int(5 + (cur / total) * 45)
                self.progress_val.emit(pct)
        elif stage == "log":
            self.progress_log.emit(cur)  # cur 此时是日志字符串


# ─────────────────────────────────────────────
#  侧边栏导航
# ─────────────────────────────────────────────
NAV_ITEMS = [
    ("flash",    "烧录"),
    ("devices",  "设备管理"),
    ("apps",     "应用市场"),
    ("skills",   "Skills"),
    ("remote",   "远程开发"),
    ("community","社区"),
]


class SidebarButton(QPushButton):
    """侧边栏按钮 - 无左边框，用背景色区分选中状态"""
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self._label = label
        self.setText(label)
        self.setFixedHeight(pt(44))
        self._apply_style(False)

    def _apply_style(self, active):
        fs = pt(13)
        pad = pt(20)
        if active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(122,179,23,0.12);
                    border: none;
                    border-radius: 10px;
                    color: {C_GREEN};
                    font-size: {fs}pt;
                    font-weight: 600;
                    text-align: left;
                    padding-left: {pad}px;
                    margin: 0 8px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 10px;
                    color: {C_TEXT2};
                    font-size: {fs}pt;
                    font-weight: 400;
                    text-align: left;
                    padding-left: {pad}px;
                    margin: 0 8px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.04);
                    color: {C_TEXT};
                }}
            """)

    def setActive(self, v):
        self._apply_style(v)


# ─────────────────────────────────────────────
#  主窗口
# ─────────────────────────────────────────────
class MainWindowV2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data_path = Path(__file__).parent.parent / "data"
        self.project_root = Path(__file__).resolve().parents[2]
        self._lang = "en"
        self._drag = False
        self._drag_pos = QPoint()
        self._resize_edge = None   # 当前拖拽的边缘方向
        self._resize_start_pos = None
        self._resize_start_geom = None
        self.flash_thread = None
        self._nav_btns = []
        self._current_page = 0
        self._is_jetson = is_jetson()
        self._remote_connected = False

        bus.device_connected.connect(self._on_remote_connected)
        bus.device_disconnected.connect(self._on_remote_disconnected)

        self.l4t_data = []
        self.product_images = {}
        self.recovery_guides = {}
        self.products = {}
        self._load_data()
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
        self._init_ui()

    def _load_data(self):
        try:
            with open(self.data_path / "l4t_data.json", encoding="utf-8") as f:
                self.l4t_data = json.load(f)
            for item in self.l4t_data:
                p = item["product"]
                self.products.setdefault(p, []).append(item["l4t"])
        except Exception: pass
        try:
            with open(self.data_path / "product_images.json", encoding="utf-8") as f:
                self.product_images = json.load(f)
        except Exception: pass
        try:
            with open(self.data_path / "recovery_guides.json", encoding="utf-8") as f:
                self.recovery_guides = json.load(f)
        except Exception: pass

    def _init_ui(self):
        self.setWindowTitle("Seeed Jetson Develop Tool")
        self.setMinimumSize(1120 if self._lang == "en" else 1080, 720)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setMouseTracking(True)   # 不按键也能收到 mouseMoveEvent，用于边缘 cursor 更新

        root = QWidget()
        root.setMouseTracking(True)
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 标题栏
        root_layout.addWidget(self._build_titlebar())

        # 主体：侧边栏 + 内容区
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        body_layout.addWidget(self._build_sidebar())

        content_area = QWidget()
        content_area.setStyleSheet(f"background:{C_BG};")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background:transparent;")
        from seeed_jetson_develop.modules.devices.page import build_page as _devices_page
        from seeed_jetson_develop.modules.remote.page import build_page as _remote_page
        self.stack.addWidget(self._build_flash_page())
        self.stack.addWidget(_devices_page())
        # Apps 页面延迟加载
        self._apps_placeholder = QWidget()
        self._apps_placeholder.setStyleSheet(f"background:{C_BG};")
        self._apps_built = False
        self.stack.addWidget(self._apps_placeholder)
        # Skills 页面延迟加载
        self._skills_placeholder = QWidget()
        self._skills_placeholder.setStyleSheet(f"background:{C_BG};")
        self._skills_built = False
        self.stack.addWidget(self._skills_placeholder)
        self.stack.addWidget(_remote_page())
        self.stack.addWidget(self._build_community_page())
        content_layout.addWidget(self.stack)

        body_layout.addWidget(content_area, 1)
        root_layout.addWidget(body, 1)

        self._set_page(0)
        self._floating_ai = FloatingAIAssistant(self, system_prompt=build_ai_system_prompt())
        self._apply_runtime_language()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_flash_adaptive_layout()

    # ── 标题栏 - 无下边框 ───────────────────────
    def _build_titlebar(self):
        bar = QFrame()
        bar.setFixedHeight(pt(64))
        bar.setStyleSheet(f"""
            QFrame {{
                background: {C_BG_DEEP};
                border: none;
            }}
        """)
        bar.installEventFilter(self)

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 12, 0)
        lay.setSpacing(12)

        # Logo
        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        logo_path = self.project_root / "assets" / "seeed-logo-blend.png"
        if logo_path.exists():
            target_h = max(28, pt(38))
            source = QPixmap(str(logo_path))
            pix = source.scaledToHeight(target_h, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
            logo_lbl.setFixedSize(pix.width() + 8, target_h + 4)
        else:
            logo_lbl.setText("Seeed")
            logo_lbl.setStyleSheet(f"color:{C_GREEN}; font-weight:700; font-size:{pt(12)}pt; background:transparent;")
        lay.addWidget(logo_lbl)

        # 分隔点代替线
        dot = QLabel("·")
        dot.setStyleSheet(f"color:{C_TEXT3}; font-size:20px; background:transparent;")
        lay.addWidget(dot)

        title = QLabel("Jetson Develop Tool")
        title.setStyleSheet(f"color:{C_TEXT2}; font-size:{pt(13)}pt; background:transparent; font-weight:500;")
        lay.addWidget(title)
        lay.addStretch()

        # 状态指示
        self.status_dot = QLabel("就绪")
        self.status_dot.setStyleSheet(f"""
            color: {C_GREEN};
            font-size: {pt(11)}pt;
            background: transparent;
            padding: 0;
        """)
        lay.addWidget(self.status_dot)

        self.lang_menu_btn = QToolButton()
        self.lang_menu_btn.setCursor(Qt.PointingHandCursor)
        self.lang_menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.lang_menu_btn.setFixedSize(pt(124), pt(34))
        self.lang_menu_btn.setStyleSheet(f"""
            QToolButton {{
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 8px;
                color: {C_TEXT2};
                font-size: {pt(10)}pt;
                font-weight: 600;
                padding: 0 24px 0 12px;
                text-align: left;
            }}
            QToolButton:hover {{
                background: rgba(255,255,255,0.10);
                color: {C_TEXT};
            }}
            QToolButton::menu-indicator {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                right: 10px;
                image: none;
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {C_TEXT2};
            }}
        """)

        self.lang_menu = QMenu(self.lang_menu_btn)
        self.lang_menu.setStyleSheet(f"""
            QMenu {{
                background: {C_CARD};
                color: {C_TEXT};
                border: 1px solid rgba(255,255,255,0.08);
                padding: 6px 0;
            }}
            QMenu::item {{
                padding: 8px 18px;
                background: transparent;
            }}
            QMenu::item:selected {{
                background: rgba(122,179,23,0.18);
            }}
        """)
        self._lang_actions = {}
        for code, text in [("en", "English"), ("zh", "中文")]:
            action = self.lang_menu.addAction(text)
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, lang=code: self._set_language(lang))
            self._lang_actions[code] = action
        self.lang_menu_btn.setMenu(self.lang_menu)
        lay.addWidget(self.lang_menu_btn)

        lay.addSpacing(16)

        # 窗口控制按钮
        for sym, slot, hover_col in [
            ("−", self.showMinimized, C_TEXT2),
            ("□", self._toggle_max,   C_TEXT2),
            ("×", self.close,         "#FF6B6B"),
        ]:
            b = QPushButton(sym)
            b.setFixedSize(pt(36), pt(32))
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {C_TEXT3};
                    font-size: {pt(14)}pt;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.08);
                    color: {hover_col};
                }}
            """)
            b.clicked.connect(slot)
            lay.addWidget(b)

        self._titlebar = bar
        return bar

    def _toggle_max(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def _get_resize_edge(self, pos):
        """检测鼠标是否在窗口边缘（用于 resize），返回方向字符串或 None"""
        if self.isMaximized():
            return None
        m = 10  # 边缘检测宽度 px，加大方便触发
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        left   = x < m
        right  = x > w - m
        top    = y < m
        bottom = y > h - m
        if top and left:     return "tl"
        if top and right:    return "tr"
        if bottom and left:  return "bl"
        if bottom and right: return "br"
        if left:   return "l"
        if right:  return "r"
        if top:    return "t"
        if bottom: return "b"
        return None

    _EDGE_CURSORS = {
        "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor,
        "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
        "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
        "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
    }

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            edge = self._get_resize_edge(ev.pos())
            if edge:
                self._resize_edge = edge
                self._resize_start_pos = ev.globalPos()
                self._resize_start_geom = self.geometry()
                ev.accept()
                return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._resize_edge and self._resize_start_pos:
            delta = ev.globalPos() - self._resize_start_pos
            g = self._resize_start_geom
            x, y, w, h = g.x(), g.y(), g.width(), g.height()
            dx, dy = delta.x(), delta.y()
            min_w, min_h = self.minimumWidth(), self.minimumHeight()
            edge = self._resize_edge
            if "r" in edge: w = max(min_w, w + dx)
            if "b" in edge: h = max(min_h, h + dy)
            if "l" in edge:
                new_w = max(min_w, w - dx)
                x = x + (w - new_w)
                w = new_w
            if "t" in edge:
                new_h = max(min_h, h - dy)
                y = y + (h - new_h)
                h = new_h
            self.setGeometry(x, y, w, h)
            ev.accept()
            return
        # 更新鼠标形状
        edge = self._get_resize_edge(ev.pos())
        if edge:
            self.setCursor(self._EDGE_CURSORS[edge])
        else:
            self.unsetCursor()
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._resize_edge = None
        self._resize_start_pos = None
        self._resize_start_geom = None
        self.unsetCursor()
        super().mouseReleaseEvent(ev)

    def eventFilter(self, src, ev):
        if self._lang == "en" and ev.type() == QEvent.Show and isinstance(src, QWidget):
            QTimer.singleShot(0, self._apply_runtime_language)
        if src is getattr(self, "_titlebar", None):
            if ev.type() == QEvent.MouseButtonDblClick:
                self._toggle_max(); return True
            if ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton:
                self._drag = True
                self._drag_pos = ev.globalPos() - self.frameGeometry().topLeft()
                return True
            if ev.type() == QEvent.MouseMove and self._drag and not self.isMaximized():
                self.move(ev.globalPos() - self._drag_pos); return True
            if ev.type() == QEvent.MouseButtonRelease:
                self._drag = False; return True
        return super().eventFilter(src, ev)

    # ── 侧边栏 - 无右边框 ──────────────────────
    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setFixedWidth(pt(220) if self._lang == "en" else pt(200))
        sidebar.setStyleSheet(f"background: {C_BG_DEEP};")
        self._sidebar = sidebar

        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # 品牌区 - 与标题栏同色，无下边框
        brand_container = QWidget()
        brand_container.setFixedHeight(pt(64))
        brand_container.setStyleSheet(f"background: {C_BG_DEEP};")
        brand_lay = QVBoxLayout(brand_container)
        brand_lay.setContentsMargins(pt(20), 0, 0, 0)
        brand_lay.setSpacing(4)
        brand_lay.setAlignment(Qt.AlignVCenter)
        brand_lay.addWidget(make_label("Seeed Studio", 10, C_TEXT3))
        brand_lay.addWidget(make_label("Jetson 开发工作台", 12, C_TEXT2, bold=True))
        lay.addWidget(brand_container)

        lay.addSpacing(8)

        # 导航按钮
        for idx, (key, label) in enumerate(NAV_ITEMS):
            btn = SidebarButton(label)
            btn.clicked.connect(lambda _, i=idx: self._set_page(i))
            lay.addWidget(btn)
            self._nav_btns.append(btn)

        lay.addStretch()

        # 底部状态 - 无分割线
        self._env_dot = QLabel("● 就绪")
        self._env_dot.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(10)}pt; background:transparent; padding:8px 0 4px {pt(20)}px;")
        lay.addWidget(self._env_dot)

        ver = make_label("v0.2.0-dev", 9, C_TEXT3)
        ver.setContentsMargins(pt(20), 0, 0, pt(12))
        lay.addWidget(ver)

        self._update_env_label()
        return sidebar

    def _set_page(self, idx):
        # Apps 页面（index=2）首次访问时懒加载
        if idx == 2 and not self._apps_built:
            try:
                from seeed_jetson_develop.modules.apps.page import build_page as _apps_page
                real_page = _apps_page()
            except Exception:
                msg = traceback.format_exc()
                log.error("failed to build App Market page\n%s", msg)
                real_page = self._build_lazy_error_page(
                    "App Market",
                    "页面加载失败，请重试或查看日志。",
                    msg,
                )
            self._apps_built = True
            self.stack.removeWidget(self._apps_placeholder)
            self._apps_placeholder.deleteLater()
            self.stack.insertWidget(2, real_page)
        # Skills 页面（index=3）首次访问时懒加载
        if idx == 3 and not self._skills_built:
            try:
                from seeed_jetson_develop.modules.skills.page import build_page as _skills_page
                real_page = _skills_page()
            except Exception:
                msg = traceback.format_exc()
                log.error("failed to build Skills page\n%s", msg)
                real_page = self._build_lazy_error_page(
                    "Skills",
                    "页面加载失败，请重试或查看日志。",
                    msg,
                )
            self._skills_built = True
            self.stack.removeWidget(self._skills_placeholder)
            self._skills_placeholder.deleteLater()
            self.stack.insertWidget(3, real_page)
        self._current_page = idx
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setActive(i == idx)

    def _build_lazy_error_page(self, title: str, message: str, detail: str) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background:{C_BG};")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(pt(32), pt(28), pt(32), pt(28))
        lay.setSpacing(pt(18))

        card = make_card(12)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        card_lay.setSpacing(pt(12))
        card_lay.addWidget(make_label(title, 16, C_TEXT, bold=True))
        card_lay.addWidget(make_label(message, 12, C_TEXT2, wrap=True))

        detail_box = QTextEdit()
        detail_box.setReadOnly(True)
        detail_box.setMinimumHeight(pt(220))
        detail_box.setPlainText(detail[-1500:])
        card_lay.addWidget(detail_box)

        lay.addWidget(card)
        lay.addStretch()
        return page

    def _update_env_label(self):
        if not hasattr(self, "_env_dot"):
            return
        pad = pt(20)
        if self._is_jetson:
            self._env_dot.setText("● " + translate_text("Jetson 本机", self._lang))
            self._env_dot.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(10)}pt; background:transparent; padding:8px 0 4px {pad}px;")
        elif self._remote_connected:
            self._env_dot.setText("● " + translate_text("远程已连接", self._lang))
            self._env_dot.setStyleSheet(f"color:{C_BLUE}; font-size:{pt(10)}pt; background:transparent; padding:8px 0 4px {pad}px;")
        else:
            self._env_dot.setText("● " + translate_text("未连接设备", self._lang))
            self._env_dot.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(10)}pt; background:transparent; padding:8px 0 4px {pad}px;")

    def _on_remote_connected(self, payload: dict):
        self._remote_connected = True
        self._update_env_label()

    def _on_remote_disconnected(self, ip: str):
        self._remote_connected = False
        self._update_env_label()

    # ── 通用页面头部 - 无边框无accent bar ───────
    def _page_header(self, title, subtitle, badge=None):
        header = QWidget()
        header.setFixedHeight(pt(64))
        header.setStyleSheet(f"background: {C_BG_DEEP};")

        lay = QHBoxLayout(header)
        lay.setContentsMargins(pt(32), 0, pt(32), 0)
        lay.setSpacing(0)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        text_col.setContentsMargins(0, 0, 0, 0)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color:{C_TEXT}; font-size:{pt(18)}pt; font-weight:700; background:transparent;")
        text_col.addWidget(title_lbl)
        
        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}pt; background:transparent;")
        text_col.addWidget(sub_lbl)
        
        lay.addLayout(text_col)
        lay.addStretch()

        if badge:
            b = QLabel(badge)
            b.setStyleSheet(f"""
                background: {C_GREEN};
                color: #071200;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: {pt(10)}pt;
                font-weight: 700;
            """)
            lay.addWidget(b)

        return header

    # ══════════════════════════════════════════
    #  PAGE 1: 烧录
    # ══════════════════════════════════════════
    def _build_flash_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._page_header("烧录中心", "选择设备型号与系统版本，一键完成固件刷写"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setStyleSheet(f"background:{C_BG};")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(pt(32), pt(28), pt(32), pt(28))
        inner_lay.setSpacing(pt(24))

        # ── 步骤向导 - 简化设计 ──
        wizard_card = make_card(12)
        wizard_outer = QVBoxLayout(wizard_card)
        wizard_outer.setContentsMargins(pt(32), pt(20), pt(32), pt(20))
        wizard_outer.setSpacing(0)

        step_configs = [("1", "选择设备"), ("2", "进入 Recovery"), ("3", "开始刷写"), ("4", "完成")]

        step_layout = QHBoxLayout()
        step_layout.setSpacing(0)

        self._step_circles = []
        self._step_labels  = []

        for i, (num, txt) in enumerate(step_configs):
            is_active = (i == 0)
            circle = QLabel(num)
            circle.setFixedSize(pt(36), pt(36))
            circle.setAlignment(Qt.AlignCenter)
            circle.setStyleSheet(f"""
                background: {C_GREEN if is_active else C_CARD_LIGHT};
                color: {'#071200' if is_active else C_TEXT3};
                border-radius: {pt(18)}px;
                font-weight: 700;
                font-size: {pt(13)}pt;
            """)
            step_layout.addWidget(circle)
            self._step_circles.append(circle)

            lbl = QLabel(txt)
            lbl.setStyleSheet(f"""
                color: {C_GREEN if is_active else C_TEXT3};
                font-size: {pt(11)}pt;
                font-weight: {'600' if is_active else '400'};
                background: transparent;
                padding-left: 8px;
            """)
            step_layout.addWidget(lbl)
            self._step_labels.append(lbl)

            if i < 3:
                arrow = QLabel("›")
                arrow.setStyleSheet(f"color:{C_TEXT3}; font-size:24px; background:transparent; padding:0 16px;")
                step_layout.addWidget(arrow)

        step_layout.addStretch()
        wizard_outer.addLayout(step_layout)
        inner_lay.addWidget(wizard_card)

        # ── 两列布局 ──
        self.flash_cols = QBoxLayout(QBoxLayout.LeftToRight)
        self.flash_cols.setSpacing(pt(24))

        # 左列 QStackedWidget（步骤一：设备选择 / 步骤二：Recovery 指南）
        self.flash_left_stack = QStackedWidget()
        self.flash_left_stack.setStyleSheet("background:transparent;")

        # ── 左侧页0：设备选择 ──
        left_page0 = QWidget()
        left_page0.setStyleSheet("background:transparent;")
        left_col = QVBoxLayout(left_page0)
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(pt(20))

        # 设备选择卡片
        dev_card = make_card(12)
        dev_lay = QVBoxLayout(dev_card)
        dev_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        dev_lay.setSpacing(pt(16))
        
        dev_lay.addWidget(make_label("目标设备", 14, C_TEXT, bold=True))
        dev_lay.addWidget(make_label("选择产品型号和对应的 L4T 系统版本", 11, C_TEXT3))

        # 产品选择
        prod_row = QHBoxLayout()
        prod_row.addWidget(make_label("产品型号", 12, C_TEXT2))
        prod_row.addStretch()
        self.flash_product_combo = QComboBox()
        self.flash_product_combo.setMinimumWidth(260)
        self.flash_product_combo.addItems(sorted(self.products.keys()))
        self.flash_product_combo.currentTextChanged.connect(self._on_flash_product_changed)
        prod_row.addWidget(self.flash_product_combo)
        dev_lay.addLayout(prod_row)

        # L4T 选择
        l4t_row = QHBoxLayout()
        l4t_row.addWidget(make_label("L4T 版本", 12, C_TEXT2))
        l4t_row.addStretch()
        self.flash_l4t_combo = QComboBox()
        self.flash_l4t_combo.setMinimumWidth(260)
        l4t_row.addWidget(self.flash_l4t_combo)
        dev_lay.addLayout(l4t_row)

        # 设备图片
        self.flash_device_img = QLabel()
        self.flash_device_img.setFixedSize(320, 200)
        self.flash_device_img.setAlignment(Qt.AlignCenter)
        self.flash_device_img.setStyleSheet(f"""
            background: {C_CARD_LIGHT};
            border: none;
            border-radius: 10px;
            color: {C_TEXT3};
            font-size: {pt(11)}pt;
        """)
        self.flash_device_img.setText("暂无图片")
        dev_lay.addWidget(self.flash_device_img, alignment=Qt.AlignHCenter)

        # 信息展示
        self.flash_info = QLabel("等待选择产品...")
        self.flash_info.setWordWrap(True)
        self.flash_info.setTextFormat(Qt.RichText)
        self.flash_info.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.flash_info.setOpenExternalLinks(False)
        self.flash_info.linkActivated.connect(self._open_url)
        self.flash_info.setStyleSheet(f"""
            background: {C_CARD_LIGHT};
            border: none;
            border-radius: 10px;
            color: {C_TEXT2};
            padding: {pt(14)}px;
            font-size: {pt(12)}pt;
            line-height: 1.6;
        """)
        dev_lay.addWidget(self.flash_info)

        flash_docs_row = QHBoxLayout()
        flash_docs_row.setSpacing(pt(10))

        self.flash_getting_started_btn = make_button("Getting Started", primary=True, small=True)
        self.flash_getting_started_btn.clicked.connect(
            lambda: self._open_flash_doc(self.flash_getting_started_btn)
        )
        flash_docs_row.addWidget(self.flash_getting_started_btn)

        self.flash_hardware_btn = make_button("Hardware Interface", small=True)
        self.flash_hardware_btn.clicked.connect(
            lambda: self._open_flash_doc(self.flash_hardware_btn)
        )
        flash_docs_row.addWidget(self.flash_hardware_btn)
        flash_docs_row.addStretch()
        dev_lay.addLayout(flash_docs_row)
        left_col.addWidget(dev_card)

        # 选项卡片
        opt_card = make_card(12)
        opt_lay = QVBoxLayout(opt_card)
        opt_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        opt_lay.setSpacing(pt(12))
        opt_lay.addWidget(make_label("执行选项", 14, C_TEXT, bold=True))

        self.skip_verify_cb = QCheckBox("跳过 SHA256 校验（不推荐）")
        opt_lay.addWidget(self.skip_verify_cb)
        left_col.addWidget(opt_card)
        left_col.addStretch()
        self.flash_left_stack.addWidget(left_page0)

        # ── 左侧页1：Recovery 指南 ──
        rec_guide_card = make_card(12)
        rec_guide_outer = QVBoxLayout(rec_guide_card)
        rec_guide_outer.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        rec_guide_outer.setSpacing(pt(12))
        rec_guide_outer.addWidget(make_label("Recovery 模式指南", 14, C_TEXT, bold=True))

        rec_guide_scroll = QScrollArea()
        rec_guide_scroll.setWidgetResizable(True)
        rec_guide_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rec_guide_scroll.setStyleSheet("background:transparent; border:none;")

        self.rec_guide_content = QWidget()
        self.rec_guide_content.setStyleSheet("background:transparent;")
        self.rec_guide_layout = QVBoxLayout(self.rec_guide_content)
        self.rec_guide_layout.setContentsMargins(0, 0, pt(8), 0)
        self.rec_guide_layout.setSpacing(pt(12))
        self.rec_guide_layout.addWidget(make_label("请先选择设备", 12, C_TEXT3))
        self.rec_guide_layout.addStretch()

        rec_guide_scroll.setWidget(self.rec_guide_content)
        rec_guide_outer.addWidget(rec_guide_scroll, 1)
        self.flash_left_stack.addWidget(rec_guide_card)

        # ── 左侧页2：完成后的客户端上手指南 ──
        guide_card = make_card(12)
        guide_outer = QVBoxLayout(guide_card)
        guide_outer.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        guide_outer.setSpacing(pt(14))
        guide_outer.addWidget(make_label("客户端 Getting Started", 14, C_TEXT, bold=True))
        guide_outer.addWidget(make_label("刷写完成后，可以继续从这些板块开始上手。", 11, C_TEXT3))

        guide_scroll = QScrollArea()
        guide_scroll.setWidgetResizable(True)
        guide_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        guide_scroll.setStyleSheet("background:transparent; border:none;")

        guide_content = QWidget()
        guide_content.setStyleSheet("background:transparent;")
        guide_layout = QVBoxLayout(guide_content)
        guide_layout.setContentsMargins(0, 0, pt(8), 0)
        guide_layout.setSpacing(pt(12))

        hint_card = QFrame()
        hint_card.setStyleSheet(f"""
            background: rgba(122,179,23,0.16);
            border: none;
            border-radius: 12px;
        """)
        hint_lay = QVBoxLayout(hint_card)
        hint_lay.setContentsMargins(pt(16), pt(15), pt(16), pt(15))
        hint_lay.setSpacing(pt(8))

        hint_badge = QLabel("推荐路径")
        hint_badge.setStyleSheet(f"""
            background: rgba(7,18,0,0.35);
            color: {C_GREEN};
            border-radius: 8px;
            padding: 4px 10px;
            font-size: {pt(9)}pt;
            font-weight: 700;
        """)
        hint_lay.addWidget(hint_badge, alignment=Qt.AlignLeft)
        hint_lay.addWidget(make_label("下一步先完成设备首次开机初始化", 13, C_TEXT, bold=True))
        hint_lay.addWidget(make_label(
            "建议先重启设备，完成用户名、网络和基础系统设置，再进入设备管理或远程开发继续配置。",
            10, C_TEXT2, wrap=True))
        hint_btn_row = QHBoxLayout()
        hint_btn_row.setSpacing(pt(10))
        hint_init_btn = make_button("Jetson 初始化", primary=True, small=True)
        hint_init_btn.clicked.connect(lambda: open_jetson_init_dialog(parent=self))
        hint_btn_row.addWidget(hint_init_btn)
        hint_btn_row.addStretch()
        hint_lay.addLayout(hint_btn_row)
        guide_layout.addWidget(hint_card)

        next_steps = [
            ("🖥", "设备管理", "查看 Jetson 状态、运行诊断、排查外设问题。"),
            ("📦", "应用市场", "安装常用 AI 应用、推理环境和开发工具。"),
            ("🧠", "Skills", "用内置技能快速完成部署、修复和配置任务。"),
            ("🌐", "远程开发", "建立 SSH 连接，继续用电脑远程操作设备。"),
            ("💬", "社区", "查看文档、论坛和常见问题，继续深入使用。"),
        ]

        for icon, title, desc in next_steps:
            item_card = QFrame()
            item_card.setStyleSheet(f"""
                background:{C_CARD_LIGHT};
                border:none;
                border-radius:10px;
            """)
            item_lay = QHBoxLayout(item_card)
            item_lay.setContentsMargins(pt(14), pt(12), pt(14), pt(12))
            item_lay.setSpacing(pt(12))

            icon_lbl = QLabel(icon)
            icon_lbl.setFixedWidth(pt(28))
            icon_lbl.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
            icon_lbl.setStyleSheet(f"background:transparent; font-size:{pt(16)}pt;")
            item_lay.addWidget(icon_lbl)

            text_col = QVBoxLayout()
            text_col.setSpacing(pt(4))
            text_col.addWidget(make_label(title, 12, C_TEXT, bold=True))
            text_col.addWidget(make_label(desc, 10, C_TEXT2, wrap=True))
            item_lay.addLayout(text_col, 1)
            guide_layout.addWidget(item_card)
        guide_layout.addStretch()

        guide_scroll.setWidget(guide_content)
        guide_outer.addWidget(guide_scroll, 1)
        self.flash_left_stack.addWidget(guide_card)

        self.flash_cols.addWidget(self.flash_left_stack, 1)

        # 右列
        self.flash_right_panel = QWidget()
        self.flash_right_panel.setStyleSheet("background:transparent;")
        self.flash_right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_col = QVBoxLayout(self.flash_right_panel)
        right_col.setSpacing(pt(20))

        # 步骤内容区（QStackedWidget 切换步骤一/步骤二）
        self.flash_step_stack = QStackedWidget()
        self.flash_step_stack.setStyleSheet("background:transparent;")

        # ── 步骤一：准备固件 ──
        step1_card = make_card(12)
        task_lay = QVBoxLayout(step1_card)
        task_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        task_lay.setSpacing(pt(16))
        task_lay.addWidget(make_label("步骤一：准备固件", 14, C_TEXT, bold=True))
        task_lay.addWidget(make_label("下载并解压 BSP 到本地，或使用已有缓存直接进入下一步", 11, C_TEXT3))

        self.flash_status_lbl = make_label("尚未开始", 14, C_TEXT2)
        task_lay.addWidget(self.flash_status_lbl)

        self.flash_progress = QProgressBar()
        self.flash_progress.setRange(0, 100)
        self.flash_progress.setValue(0)
        self.flash_progress.setFixedHeight(6)
        self.flash_progress.setVisible(False)
        task_lay.addWidget(self.flash_progress)

        self.flash_prepare_scene = FlashAnimationWidget()
        self.flash_prepare_scene.setFixedHeight(160)
        task_lay.addWidget(self.flash_prepare_scene)

        btn_row = QHBoxLayout()
        self.flash_cancel_btn = make_button("取消", danger=True)
        self.flash_cancel_btn.setVisible(False)
        self.flash_cancel_btn.clicked.connect(self._cancel_flash)

        self.flash_download_btn = QPushButton("下载/解压 BSP")
        self.flash_download_btn.setCursor(Qt.PointingHandCursor)
        self.flash_download_btn.setToolTip("有压缩包则跳过下载直接解压；有解压目录则弹窗确认是否覆盖")
        self.flash_download_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_BLUE};
                border: none; border-radius: 8px;
                color: #FFFFFF; font-size: {pt(12)}pt; font-weight: 600;
                padding: 0 {pt(20)}px; min-height: {pt(42)}px;
            }}
            QPushButton:hover {{ background: #3D8EF0; }}
            QPushButton:pressed {{ background: #1A6ACC; }}
        """)
        self.flash_download_btn.clicked.connect(self._on_prepare_bsp)

        self.flash_clear_btn = QPushButton("清除缓存")
        self.flash_clear_btn.setCursor(Qt.PointingHandCursor)
        self.flash_clear_btn.setToolTip("选择清除压缩包或解压目录")
        self.flash_clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(245,166,35,0.15);
                border: none; border-radius: 8px;
                color: {C_ORANGE}; font-size: {pt(12)}pt; font-weight: 600;
                padding: 0 {pt(20)}px; min-height: {pt(42)}px;
            }}
            QPushButton:hover {{ background: rgba(245,166,35,0.25); }}
            QPushButton:pressed {{ background: rgba(245,166,35,0.35); }}
        """)
        self.flash_clear_btn.clicked.connect(self._clear_firmware_cache)

        self.flash_next_btn = QPushButton("下一步 →")
        self.flash_next_btn.setCursor(Qt.PointingHandCursor)
        self.flash_next_btn.setToolTip("已有解压目录，直接进入刷写步骤")
        self.flash_next_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #8DC21F, stop:1 #7AB317);
                border: none; border-radius: 8px;
                color: #071200; font-size: {pt(12)}pt; font-weight: 700;
                padding: 0 {pt(24)}px; min-height: {pt(42)}px;
            }}
            QPushButton:hover {{ background: #9CD62F; }}
            QPushButton:pressed {{ background: #6BA30F; }}
            QPushButton:disabled {{ background: #1A232E; color: #5A6B7A; }}
        """)
        self.flash_next_btn.setEnabled(False)
        self.flash_next_btn.clicked.connect(self._flash_go_next_step)

        btn_row.addWidget(self.flash_download_btn)
        btn_row.addWidget(self.flash_clear_btn)
        btn_row.addWidget(self.flash_cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.flash_next_btn)
        task_lay.addLayout(btn_row)

        self.flash_cache_lbl = make_label("", 11, C_TEXT3)
        task_lay.addWidget(self.flash_cache_lbl)
        self.flash_step_stack.addWidget(step1_card)

        # ── 步骤二：进入 Recovery 模式 ──
        step2_card = make_card(12)
        rec_lay = QVBoxLayout(step2_card)
        rec_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        rec_lay.setSpacing(pt(16))
        rec_lay.addWidget(make_label("步骤二：进入 Recovery 模式", 14, C_TEXT, bold=True))
        rec_lay.addWidget(make_label(
            "将设备通过 USB 连接到本机，按住 Recovery 键后上电（或按 Reset），\n"
            "然后点击「检测设备」确认设备已进入 Recovery 模式。",
            11, C_TEXT3))

        self.rec_status_lbl = make_label("等待检测...", 13, C_TEXT2)
        rec_lay.addWidget(self.rec_status_lbl)

        rec_btn_row = QHBoxLayout()
        rec_back_btn = QPushButton("← 返回")
        rec_back_btn.setCursor(Qt.PointingHandCursor)
        rec_back_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_CARD_LIGHT};
                border: none; border-radius: 8px;
                color: {C_TEXT2}; font-size: {pt(12)}pt; font-weight: 600;
                padding: 0 {pt(20)}px; min-height: {pt(42)}px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.08); }}
        """)
        rec_back_btn.clicked.connect(self._flash_go_step1)

        self.rec_detect_btn = QPushButton("检测设备")
        self.rec_detect_btn.setCursor(Qt.PointingHandCursor)
        self.rec_detect_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_BLUE};
                border: none; border-radius: 8px;
                color: #FFFFFF; font-size: {pt(12)}pt; font-weight: 600;
                padding: 0 {pt(20)}px; min-height: {pt(42)}px;
            }}
            QPushButton:hover {{ background: #3D8EF0; }}
            QPushButton:pressed {{ background: #1A6ACC; }}
        """)
        self.rec_detect_btn.clicked.connect(self._detect_recovery)

        self.rec_flash_btn = QPushButton("开始刷写 →")
        self.rec_flash_btn.setCursor(Qt.PointingHandCursor)
        self.rec_flash_btn.setEnabled(False)
        self.rec_flash_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #8DC21F, stop:1 #7AB317);
                border: none; border-radius: 8px;
                color: #071200; font-size: {pt(12)}pt; font-weight: 700;
                padding: 0 {pt(24)}px; min-height: {pt(42)}px;
            }}
            QPushButton:hover {{ background: #9CD62F; }}
            QPushButton:pressed {{ background: #6BA30F; }}
            QPushButton:disabled {{ background: #1A232E; color: #5A6B7A; }}
        """)
        self.rec_flash_btn.clicked.connect(self._start_flash)

        rec_btn_row.addWidget(rec_back_btn)
        rec_btn_row.addWidget(self.rec_detect_btn)
        rec_btn_row.addStretch()
        rec_btn_row.addWidget(self.rec_flash_btn)
        rec_lay.addLayout(rec_btn_row)
        self.flash_step_stack.addWidget(step2_card)

        # ── 步骤三：开始刷写 ──
        step3_card = make_card(12)
        run_lay = QVBoxLayout(step3_card)
        run_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        run_lay.setSpacing(pt(16))
        run_lay.addWidget(make_label("步骤三：开始刷写", 14, C_TEXT, bold=True))

        self.flash_run_status_lbl = make_label("准备开始刷写...", 13, C_TEXT2)
        run_lay.addWidget(self.flash_run_status_lbl)

        self.flash_run_progress = QProgressBar()
        self.flash_run_progress.setRange(0, 100)
        self.flash_run_progress.setValue(0)
        self.flash_run_progress.setFixedHeight(6)
        run_lay.addWidget(self.flash_run_progress)

        self.flash_scene = FlashAnimationWidget()
        self.flash_scene.setFixedHeight(160)
        run_lay.addWidget(self.flash_scene)

        run_btn_row = QHBoxLayout()
        self.flash_run_cancel_btn = make_button("取消", danger=True)
        self.flash_run_cancel_btn.clicked.connect(self._cancel_flash)
        self.flash_run_retry_btn = make_button("重新烧录", primary=True)
        self.flash_run_retry_btn.setVisible(False)
        self.flash_run_retry_btn.clicked.connect(self._retry_flash)
        self.flash_run_back_btn = make_button("返回 Recovery", small=False)
        self.flash_run_back_btn.setVisible(False)
        self.flash_run_back_btn.clicked.connect(self._flash_go_next_step)
        run_btn_row.addWidget(self.flash_run_cancel_btn)
        run_btn_row.addStretch()
        run_btn_row.addWidget(self.flash_run_retry_btn)
        run_btn_row.addWidget(self.flash_run_back_btn)
        run_lay.addLayout(run_btn_row)
        self.flash_step_stack.addWidget(step3_card)

        # ── 步骤四：完成 ──
        step4_card = make_card(12)
        done_lay = QVBoxLayout(step4_card)
        done_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        done_lay.setSpacing(pt(16))
        done_lay.addWidget(make_label("步骤四：完成", 14, C_TEXT, bold=True))
        self.flash_done_status_lbl = make_label("刷写已完成。", 13, C_GREEN)
        done_lay.addWidget(self.flash_done_status_lbl)

        self.flash_done_scene = FlashAnimationWidget()
        self.flash_done_scene.setFixedHeight(160)
        self.flash_done_scene.set_mode("success")
        done_lay.addWidget(self.flash_done_scene)

        done_btn_row = QHBoxLayout()
        self.flash_done_init_btn = make_button("Jetson 初始化", primary=True)
        self.flash_done_init_btn.clicked.connect(lambda: open_jetson_init_dialog(parent=self))
        self.flash_done_restart_btn = make_button("重新开始")
        self.flash_done_restart_btn.clicked.connect(self._flash_reset_to_start)
        done_btn_row.addWidget(self.flash_done_init_btn)
        done_btn_row.addStretch()
        done_btn_row.addWidget(self.flash_done_restart_btn)
        done_lay.addLayout(done_btn_row)
        self.flash_step_stack.addWidget(step4_card)

        right_col.addWidget(self.flash_step_stack)

        log_card = make_card(12)
        log_lay = QVBoxLayout(log_card)
        log_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        log_lay.setSpacing(pt(12))
        hdr = QHBoxLayout()
        hdr.addWidget(make_label("日志", 14, C_TEXT, bold=True))
        hdr.addStretch()
        save_btn = make_button("保存日志", small=True)
        save_btn.clicked.connect(self._save_flash_log)
        hdr.addWidget(save_btn)
        clear_btn = make_button("清空", small=True)
        clear_btn.clicked.connect(lambda: self.flash_log.clear())
        hdr.addWidget(clear_btn)
        log_lay.addLayout(hdr)
        self.flash_log = QTextEdit()
        self.flash_log.setReadOnly(True)
        self.flash_log.setMinimumHeight(200)
        log_lay.addWidget(self.flash_log)
        right_col.addWidget(log_card, 1)

        self.flash_cols.addWidget(self.flash_right_panel, 1)
        self.flash_cols.setStretch(0, 1)
        self.flash_cols.setStretch(1, 1)
        self.flash_cols_host = QWidget()
        self.flash_cols_host.setStyleSheet("background:transparent;")
        self.flash_cols_host.setLayout(self.flash_cols)
        inner_lay.addWidget(self.flash_cols_host)
        inner_lay.addStretch()

        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        self._on_flash_product_changed(self.flash_product_combo.currentText())
        QTimer.singleShot(0, self._update_flash_adaptive_layout)
        return page

    def _update_flash_adaptive_layout(self):
        if not hasattr(self, "flash_cols") or not hasattr(self, "flash_cols_host"):
            return

        width = self.flash_cols_host.width() or self.stack.width() or self.width()
        compact = width < 1180
        direction = QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight
        self.flash_cols.setDirection(direction)

        if hasattr(self, "flash_device_img"):
            if compact:
                self.flash_device_img.setFixedSize(280, 176)
            else:
                self.flash_device_img.setFixedSize(320, 200)

        if hasattr(self, "flash_log"):
            self.flash_log.setMinimumHeight(160 if compact else 200)

    def _on_flash_product_changed(self, product):
        self.flash_l4t_combo.clear()
        if product in self.products:
            self.flash_l4t_combo.addItems(self.products[product])
        info = self.product_images.get(product, {})
        name = info.get("name", product)
        versions = len(self.products.get(product, []))
        getting_started = info.get("getting_started", "").strip()
        hardware_interfaces = info.get("hardware_interfaces", "").strip()
        if self._lang == "en":
            self.flash_info.setText(
                f"Model: {name}<br>"
                f"Available Versions: {versions}<br>"
                "Documentation: use the buttons below"
            )
        else:
            self.flash_info.setText(
                f"型号：{name}<br>"
                f"可用版本：{versions} 个<br>"
                "文档快捷入口：使用下方按钮打开"
            )
        self._set_flash_doc_button(
            self.flash_getting_started_btn,
            getting_started,
            "打开该产品的 Getting Started Wiki",
        )
        self._set_flash_doc_button(
            self.flash_hardware_btn,
            hardware_interfaces,
            "打开该产品的 Hardware Interface Wiki",
        )

        # 加载设备图片
        if hasattr(self, "flash_device_img"):
            local_img = info.get("local_image", "")
            img_path = self.project_root / local_img if local_img else None
            if img_path and img_path.exists():
                pix = QPixmap(str(img_path)).scaled(
                    320, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.flash_device_img.setPixmap(pix)
                self.flash_device_img.setText("")
            else:
                self.flash_device_img.clear()
                self.flash_device_img.setText("暂无图片")

        self._update_cache_label()

    def _set_flash_doc_button(self, button, url: str, tooltip: str):
        url = (url or "").strip()
        button.setProperty("doc_url", url)
        button.setEnabled(bool(url))
        button.setToolTip(url if url else tooltip)

    def _open_flash_doc(self, button):
        url = button.property("doc_url") or ""
        if url:
            self._open_url(url)


    def _update_cache_label(self):
        if not hasattr(self, "flash_cache_lbl"):
            return
        product = self.flash_product_combo.currentText()
        l4t = self.flash_l4t_combo.currentText()
        if not product or not l4t:
            return
        try:
            flasher = JetsonFlasher(product, l4t)
            has_archive  = flasher.firmware_cached()
            has_extracted = flasher.firmware_extracted()
            if has_extracted:
                text = "✓ Firmware downloaded and extracted. You can flash directly." if self._lang == "en" else "✓ 已下载并解压，可直接刷写（跳过下载）"
                self.flash_cache_lbl.setText(text)
                self.flash_cache_lbl.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(11)}pt; background:transparent;")
                if hasattr(self, "flash_prepare_scene"):
                    self.flash_prepare_scene.set_mode("idle")
                    self.flash_prepare_scene.set_download_progress(1.0)
                self._set_next_enabled(True)
            elif has_archive:
                fp = flasher.download_dir / flasher.firmware_info['filename']
                size_mb = fp.stat().st_size / 1024 / 1024
                if self._lang == "en":
                    self.flash_cache_lbl.setText(f"✓ Cached archive: {size_mb:.0f} MB. It will be extracted automatically.")
                else:
                    self.flash_cache_lbl.setText(f"✓ 已缓存压缩包 {size_mb:.0f} MB，刷写时将自动解压")
                self.flash_cache_lbl.setStyleSheet(f"color:{C_BLUE}; font-size:{pt(11)}pt; background:transparent;")
                if hasattr(self, "flash_prepare_scene") and not self.flash_cancel_btn.isVisible():
                    self.flash_prepare_scene.set_mode("idle")
                    self.flash_prepare_scene.set_download_progress(0.0)
                self._set_next_enabled(False)
            else:
                text = "⚠ No local cache found. Click Download / Extract BSP first." if self._lang == "en" else "⚠ 无本地缓存，请先点击「下载/解压 BSP」"
                self.flash_cache_lbl.setText(text)
                self.flash_cache_lbl.setStyleSheet(f"""
                    color: {C_ORANGE};
                    font-size: {pt(11)}pt;
                    background: rgba(245,166,35,0.10);
                    border-radius: 6px;
                    padding: 4px 10px;
                """)
                if hasattr(self, "flash_prepare_scene") and not self.flash_cancel_btn.isVisible():
                    self.flash_prepare_scene.set_mode("idle")
                    self.flash_prepare_scene.set_download_progress(0.0)
                self._set_next_enabled(False)
        except Exception:
            self.flash_cache_lbl.setText("")

    def _clear_firmware_cache(self):
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QCheckBox
        product = self.flash_product_combo.currentText()
        l4t = self.flash_l4t_combo.currentText()
        if not product or not l4t:
            return

        # 选择弹窗
        dlg = QDialog(self)
        dlg.setWindowTitle("清除缓存")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(f"background:{C_BG};")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.addWidget(make_label("选择要清除的内容：", 13, C_TEXT))
        lay.addWidget(make_label("可只清除压缩包，或只清理解压后的工作目录。", 10, C_TEXT3))

        checkbox_style = f"""
            QCheckBox {{
                color: {C_TEXT2};
                font-size: {pt(12)}pt;
                spacing: 0px;
                padding: 10px 14px;
                background: transparent;
                border-radius: 10px;
            }}
            QCheckBox:hover {{
                background: rgba(255,255,255,0.04);
            }}
            QCheckBox::indicator {{
                width: 0px;
                height: 0px;
            }}
        """

        archive_label = "📦  压缩包缓存（.tar.gz / .tar）"
        extracted_label = "🗂  解压目录（工作目录）"
        cb_archive = QCheckBox()
        cb_extracted = QCheckBox()
        cb_archive.setStyleSheet(checkbox_style)
        cb_extracted.setStyleSheet(checkbox_style)
        cb_archive.setChecked(True)
        cb_extracted.setChecked(True)

        def _sync_checkbox_text(box: QCheckBox, label: str):
            suffix = "  已选中" if box.isChecked() else ""
            box.setText(f"{label}{suffix}")
            box.setStyleSheet(
                checkbox_style
                + (
                    f"QCheckBox {{ color: {C_TEXT}; font-size: {pt(12)}pt; spacing: 0px; padding: 10px 14px; "
                    f"background: rgba(255,255,255,0.05); border-radius: 10px; font-weight: 600; }}"
                    f"QCheckBox:hover {{ background: rgba(255,255,255,0.08); }}"
                    f"QCheckBox::indicator {{ width: 0px; height: 0px; }}"
                    if box.isChecked()
                    else ""
                )
            )

        cb_archive.stateChanged.connect(lambda _state: _sync_checkbox_text(cb_archive, archive_label))
        cb_extracted.stateChanged.connect(lambda _state: _sync_checkbox_text(cb_extracted, extracted_label))
        _sync_checkbox_text(cb_archive, archive_label)
        _sync_checkbox_text(cb_extracted, extracted_label)

        lay.addWidget(cb_archive)
        lay.addWidget(cb_extracted)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        cancel_btn = make_button("取消")
        ok_btn = make_button("确认清除", primary=True)
        cancel_btn.clicked.connect(dlg.reject)
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        if dlg.exec_() != QDialog.Accepted:
            return

        try:
            flasher = JetsonFlasher(product, l4t)
            removed = flasher.clear_cache(
                clear_archive=cb_archive.isChecked(),
                clear_extracted=cb_extracted.isChecked(),
            )
            if removed:
                self._flash_log("[INFO] 已清除:\n" + "\n".join(f"  {p}" for p in removed))
            else:
                self._flash_log("[INFO] 无缓存可清除")
        except Exception as e:
            self._flash_log(f"[ERR] 清除缓存失败: {e}")
        self._update_cache_label()
        self._set_next_enabled(False)

    def _ask_password(self, title: str, description: str, hint: str) -> str | None:
        """通用密码输入弹窗。返回输入的密码字符串，取消则返回 None。
        
        Args:
            title:       对话框标题
            description: 主说明文字（说明为什么需要密码）
            hint:        输入框下方的小字提示（说明是哪台机器的密码）
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QDialogButtonBox, QFrame
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet(f"background:{C_BG};")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        lay.addWidget(make_label(description, 13, C_TEXT))

        # 来源标签（区分 PC / Jetson）
        hint_lbl = QLabel(hint)
        hint_lbl.setWordWrap(True)
        hint_lbl.setStyleSheet(f"""
            color: {C_ORANGE};
            background: rgba(245,166,35,0.10);
            border-radius: 6px;
            padding: 6px 10px;
            font-size: {pt(11)}pt;
        """)
        lay.addWidget(hint_lbl)

        pwd_input = QLineEdit()
        pwd_input.setEchoMode(QLineEdit.Password)
        pwd_input.setPlaceholderText("输入密码…")
        pwd_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C_CARD_LIGHT}; border: none; border-radius: 8px;
                color: {C_TEXT}; padding: 8px 12px; font-size: {pt(12)}pt;
            }}
        """)
        lay.addWidget(pwd_input)

        err_lbl = make_label("", 11, C_RED)
        lay.addWidget(err_lbl)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        pwd_input.returnPressed.connect(dlg.accept)

        if dlg.exec_() != QDialog.Accepted:
            return None
        return pwd_input.text()

    def _ensure_sudo(self) -> bool:
        """检查 PC 本机 sudo 缓存，过期则弹密码框验证。返回 True 表示已授权。"""
        import getpass
        if sudo_check_cached():
            return True

        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("需要本机管理员权限")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet(f"background:{C_BG};")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        lay.addWidget(make_label("解压和烧录固件需要 sudo 权限。", 13, C_TEXT))

        # 明确标注是 PC 本机密码
        try:
            username = getpass.getuser()
        except Exception:
            username = "当前用户"
        hint_lbl = QLabel(f"🖥  本机（PC）sudo 密码  ·  用户：{username}")
        hint_lbl.setStyleSheet(f"""
            color: {C_BLUE};
            background: rgba(41,121,255,0.10);
            border-radius: 6px;
            padding: 6px 10px;
            font-size: {pt(11)}pt;
        """)
        lay.addWidget(hint_lbl)

        pwd_input = QLineEdit()
        pwd_input.setEchoMode(QLineEdit.Password)
        pwd_input.setPlaceholderText("输入本机密码…")
        pwd_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C_CARD_LIGHT}; border: none; border-radius: 8px;
                color: {C_TEXT}; padding: 8px 12px; font-size: {pt(12)}pt;
            }}
        """)
        lay.addWidget(pwd_input)
        err_lbl = make_label("", 11, C_RED)
        lay.addWidget(err_lbl)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        pwd_input.returnPressed.connect(dlg.accept)

        while True:
            if dlg.exec_() != QDialog.Accepted:
                return False
            pwd = pwd_input.text()
            if sudo_authenticate(pwd):
                return True
            err_lbl.setText("密码错误，请重试")
            pwd_input.clear()
            pwd_input.setFocus()

    def _on_prepare_bsp(self):
        """点击"下载/解压 BSP"的入口逻辑。"""
        if not self._ensure_sudo():
            self._flash_log("[WARN] 未获得 sudo 权限，操作取消")
            return

        product = self.flash_product_combo.currentText()
        l4t = self.flash_l4t_combo.currentText()
        if not product or not l4t:
            return
        try:
            flasher = JetsonFlasher(product, l4t)
            has_extracted = flasher.firmware_extracted()
            has_archive   = flasher.firmware_cached()
        except Exception as e:
            self._flash_log(f"[ERR] {e}")
            return

        if has_extracted:
            msg = create_themed_message_box(
                self,
                "已有解压目录",
                "检测到本地已有解压好的固件目录。\n是否覆盖重新下载并解压？",
                icon=QMessageBox.Question,
                informative_text="选择「跳过」可直接使用现有目录进入下一步。",
                buttons=QMessageBox.NoButton,
            )
            skip_btn     = msg.addButton("跳过，直接下一步", QMessageBox.AcceptRole)
            overwrite_btn = msg.addButton("覆盖重新下载解压", QMessageBox.DestructiveRole)
            cancel_btn = msg.addButton("取消", QMessageBox.RejectRole)
            for btn in (skip_btn, overwrite_btn, cancel_btn):
                btn.setCursor(Qt.PointingHandCursor)
            msg.exec_()
            clicked = msg.clickedButton()
            if clicked is skip_btn:
                self._flash_log("[INFO] 使用现有解压目录，跳过下载解压")
                self._set_next_enabled(True)
                return
            elif clicked is overwrite_btn:
                self._run_flash_thread(product, l4t, force_redownload=True, prepare_only=True)
        elif has_archive:
            self._flash_log("[INFO] 压缩包已存在，跳过下载，直接解压")
            self._run_flash_thread(product, l4t, force_redownload=False, prepare_only=True)
        else:
            self._run_flash_thread(product, l4t, force_redownload=False, prepare_only=True)

    def _flash_go_next_step(self):
        """切换到步骤二：Recovery 检测。"""
        self._set_wizard_step(1)
        self.flash_step_stack.setCurrentIndex(1)
        self.flash_left_stack.setCurrentIndex(1)
        self._build_recovery_guide(self.flash_product_combo.currentText())
        self.rec_status_lbl.setText("Waiting for detection..." if self._lang == "en" else "等待检测...")
        self.rec_status_lbl.setStyleSheet(f"color:{C_TEXT2}; background:transparent;")
        self.rec_flash_btn.setEnabled(False)
        if hasattr(self, "flash_scene"):
            self.flash_scene.set_mode("idle")
            self.flash_scene.set_download_progress(0.0)
        if hasattr(self, "flash_prepare_scene"):
            self.flash_prepare_scene.set_mode("idle")
            self.flash_prepare_scene.set_download_progress(1.0 if self.flash_next_btn.isEnabled() else 0.0)
        if hasattr(self, "flash_run_back_btn"):
            self.flash_run_back_btn.setVisible(False)

    def _flash_go_step1(self):
        """从步骤二返回步骤一。"""
        self._set_wizard_step(0)
        self.flash_step_stack.setCurrentIndex(0)
        self.flash_left_stack.setCurrentIndex(0)
        if hasattr(self, "flash_scene"):
            self.flash_scene.set_mode("idle")
            self.flash_scene.set_download_progress(0.0)
        if hasattr(self, "flash_prepare_scene"):
            self.flash_prepare_scene.set_mode("idle")
            self.flash_prepare_scene.set_download_progress(1.0 if self.flash_next_btn.isEnabled() else 0.0)
        if hasattr(self, "flash_run_back_btn"):
            self.flash_run_back_btn.setVisible(False)

    def _flash_reset_to_start(self):
        """完成后回到第一步。"""
        self._set_wizard_step(0)
        self.flash_step_stack.setCurrentIndex(0)
        self.flash_left_stack.setCurrentIndex(0)
        self.flash_status_lbl.setText("Not started" if self._lang == "en" else "尚未开始")
        self.flash_status_lbl.setStyleSheet(f"color:{C_TEXT2}; background:transparent;")
        self.flash_run_status_lbl.setText("Preparing to flash..." if self._lang == "en" else "准备开始刷写...")
        self.flash_run_status_lbl.setStyleSheet(f"color:{C_TEXT2}; background:transparent;")
        self.flash_progress.setVisible(False)
        self.flash_progress.setValue(0)
        self.flash_run_progress.setValue(0)
        if hasattr(self, "flash_prepare_scene"):
            self.flash_prepare_scene.set_mode("idle")
            self.flash_prepare_scene.set_download_progress(0.0)
        if hasattr(self, "flash_scene"):
            self.flash_scene.set_mode("idle")
            self.flash_scene.set_download_progress(0.0)
        if hasattr(self, "flash_done_scene"):
            self.flash_done_scene.set_mode("success")
            self.flash_done_scene.set_download_progress(1.0)
        if hasattr(self, "flash_run_back_btn"):
            self.flash_run_back_btn.setVisible(False)

    def _build_recovery_guide(self, product: str):
        """动态构建左侧 Recovery 指南内容。"""
        from seeed_jetson_develop.data.recovery_guides import get_guide

        # 清空旧内容
        while self.rec_guide_layout.count():
            item = self.rec_guide_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        guide = get_guide(product)
        if not guide:
            self.rec_guide_layout.addWidget(make_label("暂无该设备的 Recovery 指南", 12, C_TEXT3))
            self.rec_guide_layout.addStretch()
            return

        # 标题
        title_lbl = make_label(guide["title"], 13, C_TEXT, bold=True)
        title_lbl.setWordWrap(True)
        self.rec_guide_layout.addWidget(title_lbl)

        # 所需线缆
        cable_lbl = make_label(f"所需线缆：{guide['cable']}", 11, C_TEXT2)
        self.rec_guide_layout.addWidget(cable_lbl)

        # 参考图片
        if guide.get("image_url") or guide.get("local_image"):
            img_lbl = QLabel()
            img_lbl.setAlignment(Qt.AlignCenter)
            img_lbl.setStyleSheet(f"background:{C_CARD_LIGHT}; border-radius:8px; padding:4px;")
            img_lbl.setFixedHeight(280)
            img_lbl.setText("图片加载中...")
            img_lbl.setStyleSheet(f"color:{C_TEXT3}; background:{C_CARD_LIGHT}; border-radius:8px; font-size:{pt(10)}pt;")
            self.rec_guide_layout.addWidget(img_lbl)
            # 优先加载项目内静态资源，缺失时再回退到远程 URL。
            self._load_guide_image(
                guide.get("image_url", ""),
                img_lbl,
                guide.get("local_image", ""),
                guide["title"],
            )

        # 步骤列表
        steps_lbl = make_label("操作步骤：", 12, C_TEXT, bold=True)
        self.rec_guide_layout.addWidget(steps_lbl)

        for i, step in enumerate(guide["steps"], 1):
            row = QHBoxLayout()
            row.setSpacing(pt(8))
            num = QLabel(str(i))
            num.setFixedSize(pt(22), pt(22))
            num.setAlignment(Qt.AlignCenter)
            num.setStyleSheet(f"""
                background: {C_BLUE}; color: #fff;
                border-radius: {pt(11)}px;
                font-size: {pt(10)}pt; font-weight: 700;
            """)
            step_lbl = QLabel(step)
            step_lbl.setWordWrap(True)
            step_lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:{pt(11)}pt; background:transparent;")
            row.addWidget(num, alignment=Qt.AlignTop)
            row.addWidget(step_lbl, 1)
            container = QWidget()
            container.setStyleSheet("background:transparent;")
            container.setLayout(row)
            self.rec_guide_layout.addWidget(container)

        # USB ID 列表
        ids_lbl = make_label("Recovery 模式 USB ID：", 12, C_TEXT, bold=True)
        self.rec_guide_layout.addWidget(ids_lbl)
        for name, uid in guide["usb_ids"]:
            id_lbl = QLabel(f"  {name}：{uid}")
            id_lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:{pt(11)}pt; font-family:monospace; background:transparent;")
            self.rec_guide_layout.addWidget(id_lbl)

        # 警告
        if guide.get("note"):
            note_lbl = QLabel(guide["note"])
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet(f"""
                color: {C_ORANGE};
                background: rgba(245,166,35,0.10);
                border-radius: 6px;
                padding: 8px 10px;
                font-size: {pt(11)}pt;
            """)
            self.rec_guide_layout.addWidget(note_lbl)

        self.rec_guide_layout.addStretch()

    def _set_guide_image_preview(self, label: QLabel, pix: QPixmap, title: str):
        """将图片渲染为较大的预览，并支持点击查看大图。"""
        target_w = label.width() - 16 if label.width() > 16 else 560
        target_h = label.height() - 8 if label.height() > 8 else 272
        preview = pix.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(preview)
        label.setStyleSheet(f"background:{C_CARD_LIGHT}; border-radius:8px; padding:4px;")
        label.setText("")
        label.setCursor(Qt.PointingHandCursor)
        label.setToolTip("点击查看大图")
        label.mousePressEvent = lambda _event, p=pix, t=title: self._show_guide_image_dialog(p, t)

    def _show_guide_image_dialog(self, pix: QPixmap, title: str):
        """弹出支持滚轮缩放与鼠标拖动查看的大图预览。"""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setMinimumSize(980, 760)
        dlg.setStyleSheet(f"background:{C_BG};")

        root = QVBoxLayout(dlg)
        root.setContentsMargins(pt(20), pt(20), pt(20), pt(20))
        root.setSpacing(pt(12))

        title_lbl = make_label(title, 14, C_TEXT, bold=True)
        root.addWidget(title_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        image = QLabel()
        image.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        image.setStyleSheet(f"background:{C_CARD_LIGHT}; border-radius:10px;")
        image.setCursor(Qt.OpenHandCursor)

        drag_state = {"active": False, "pos": None}
        zoom_state = {"scale": 1.0, "min": 0.2, "max": 6.0}

        def apply_scale(new_scale: float, anchor_pos=None):
            new_scale = max(zoom_state["min"], min(zoom_state["max"], new_scale))
            old_scale = zoom_state["scale"]
            if abs(new_scale - old_scale) < 1e-4:
                return

            hbar = scroll.horizontalScrollBar()
            vbar = scroll.verticalScrollBar()
            if anchor_pos is not None:
                content_x = hbar.value() + anchor_pos.x()
                content_y = vbar.value() + anchor_pos.y()
                ratio_x = content_x / max(1, image.width())
                ratio_y = content_y / max(1, image.height())
            else:
                ratio_x = 0.5
                ratio_y = 0.5

            zoom_state["scale"] = new_scale
            scaled = pix.scaled(
                max(1, int(pix.width() * new_scale)),
                max(1, int(pix.height() * new_scale)),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation,
            )
            image.setPixmap(scaled)
            image.resize(scaled.size())
            image.setMinimumSize(scaled.size())

            if anchor_pos is not None:
                hbar.setValue(int(image.width() * ratio_x - anchor_pos.x()))
                vbar.setValue(int(image.height() * ratio_y - anchor_pos.y()))

        def fit_initial():
            viewport = scroll.viewport().size()
            if viewport.width() <= 0 or viewport.height() <= 0:
                return
            fit_scale = min(
                viewport.width() / max(1, pix.width()),
                viewport.height() / max(1, pix.height()),
                1.0,
            )
            zoom_state["scale"] = 1.0
            apply_scale(fit_scale)

        def on_press(event):
            if event.button() == Qt.LeftButton:
                drag_state["active"] = True
                drag_state["pos"] = event.globalPos()
                image.setCursor(Qt.ClosedHandCursor)
                event.accept()

        def on_move(event):
            if drag_state["active"] and drag_state["pos"] is not None:
                delta = event.globalPos() - drag_state["pos"]
                drag_state["pos"] = event.globalPos()
                hbar = scroll.horizontalScrollBar()
                vbar = scroll.verticalScrollBar()
                hbar.setValue(hbar.value() - delta.x())
                vbar.setValue(vbar.value() - delta.y())
                event.accept()

        def on_release(event):
            if event.button() == Qt.LeftButton:
                drag_state["active"] = False
                drag_state["pos"] = None
                image.setCursor(Qt.OpenHandCursor)
                event.accept()

        def on_wheel(event):
            delta = event.angleDelta().y()
            if not delta:
                event.ignore()
                return
            factor = 1.15 if delta > 0 else (1 / 1.15)
            apply_scale(zoom_state["scale"] * factor, event.pos())
            event.accept()

        image.mousePressEvent = on_press
        image.mouseMoveEvent = on_move
        image.mouseReleaseEvent = on_release
        scroll.wheelEvent = on_wheel

        scroll.setWidget(image)
        root.addWidget(scroll, 1)
        QTimer.singleShot(0, fit_initial)

        tip_lbl = make_label("滚轮可缩放图片，按住鼠标左键可拖动查看指定位置。", 10, C_TEXT3)
        root.addWidget(tip_lbl)

        close_btn = make_button("关闭")
        close_btn.clicked.connect(dlg.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close_btn)
        root.addLayout(row)

        dlg.exec_()

    def _load_guide_image(self, url: str, label: QLabel, local_image: str = "", title: str = "Recovery 指南图片"):
        """优先从项目内加载指南图片，缺失时再尝试远程下载。"""
        import threading
        from PyQt5.QtCore import QTimer

        local_path = self.project_root / local_image if local_image else None
        if local_path and local_path.exists():
            pix = QPixmap(str(local_path))
            if not pix.isNull():
                self._set_guide_image_preview(label, pix, title)
                return

        def fetch():
            try:
                import requests as _req
                resp = _req.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.content
                # 回主线程更新
                def update():
                    pix = QPixmap()
                    pix.loadFromData(data)
                    if not pix.isNull():
                        self._set_guide_image_preview(label, pix, title)
                    else:
                        label.setText("Image preview failed" if self._lang == "en" else "图片加载失败")
                QTimer.singleShot(0, update)
            except Exception:
                def show_fail():
                    label.setText("Image preview failed" if self._lang == "en" else "图片加载失败")
                    label.setStyleSheet(
                        f"color:{C_TEXT3}; background:{C_CARD_LIGHT}; border-radius:8px; font-size:{pt(10)}pt;"
                    )
                QTimer.singleShot(0, show_fail)

        threading.Thread(target=fetch, daemon=True).start()

    def _set_wizard_step(self, active_idx: int):
        """更新步骤向导高亮。"""
        if not hasattr(self, "_step_circles"):
            return
        for i, (circle, lbl) in enumerate(zip(self._step_circles, self._step_labels)):
            done = i < active_idx
            active = i == active_idx
            if active:
                circle.setStyleSheet(f"""
                    background: {C_GREEN}; color: #071200;
                    border-radius: {pt(18)}px; font-weight: 700; font-size: {pt(13)}pt;
                """)
                lbl.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(11)}pt; font-weight:600; background:transparent; padding-left:8px;")
            elif done:
                circle.setStyleSheet(f"""
                    background: rgba(122,179,23,0.3); color: {C_GREEN};
                    border-radius: {pt(18)}px; font-weight: 700; font-size: {pt(13)}pt;
                """)
                lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:{pt(11)}pt; font-weight:400; background:transparent; padding-left:8px;")
            else:
                circle.setStyleSheet(f"""
                    background: {C_CARD_LIGHT}; color: {C_TEXT3};
                    border-radius: {pt(18)}px; font-weight: 700; font-size: {pt(13)}pt;
                """)
                lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(11)}pt; font-weight:400; background:transparent; padding-left:8px;")

    def _detect_recovery(self):
        """调用 lsusb 检测 NVIDIA APX Recovery 设备。"""
        import subprocess
        # NVIDIA APX USB IDs（各 Jetson 系列）
        NVIDIA_APX_IDS = {"7023", "7223", "7323", "7423", "7523", "7623"}
        try:
            result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
            found = False
            for line in result.stdout.splitlines():
                # 格式：Bus 001 Device 002: ID 0955:7323 NVIDIA Corp. APX
                if "0955:" in line.lower() or "nvidia" in line.lower():
                    parts = line.split("ID ")
                    if len(parts) > 1:
                        vid_pid = parts[1].split()[0]  # e.g. "0955:7323"
                        pid = vid_pid.split(":")[-1].lower()
                        if pid in NVIDIA_APX_IDS:
                            found = True
                            self._flash_log(f"[INFO] 检测到 Recovery 设备: {line.strip()}")
                            break
            if found:
                text = "✓ Jetson Recovery device detected. Ready to flash." if self._lang == "en" else "✓ 已检测到 Jetson Recovery 设备，可以开始刷写"
                self.rec_status_lbl.setText(text)
                self.rec_status_lbl.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
                self.rec_flash_btn.setEnabled(True)
            else:
                text = "✗ No Recovery device detected. Check the cable and Recovery mode." if self._lang == "en" else "✗ 未检测到 Recovery 设备，请检查连接和 Recovery 模式"
                self.rec_status_lbl.setText(text)
                self.rec_status_lbl.setStyleSheet(f"color:{C_ORANGE}; background:transparent;")
                self.rec_flash_btn.setEnabled(False)
                self._flash_log("[WARN] lsusb 未找到 NVIDIA APX 设备")
        except Exception as e:
            prefix = "Detection failed" if self._lang == "en" else "检测失败"
            self.rec_status_lbl.setText(f"{prefix}: {e}")
            self.rec_status_lbl.setStyleSheet(f"color:{C_RED}; background:transparent;")
            self._flash_log(f"[ERR] lsusb 执行失败: {e}")

    def _set_next_enabled(self, enabled: bool):
        if hasattr(self, "flash_next_btn"):
            self.flash_next_btn.setEnabled(enabled)
            if enabled:
                if hasattr(self, "flash_prepare_scene"):
                    self.flash_prepare_scene.set_mode("idle")
                    self.flash_prepare_scene.set_download_progress(1.0)
            elif hasattr(self, "flash_prepare_scene") and not self.flash_cancel_btn.isVisible():
                self.flash_prepare_scene.set_mode("idle")
                self.flash_prepare_scene.set_download_progress(0.0)

    def _start_redownload(self):
        """保留兼容，实际入口已改为 _on_prepare_bsp。"""
        self._on_prepare_bsp()

    def _start_flash(self):
        product = self.flash_product_combo.currentText()
        l4t = self.flash_l4t_combo.currentText()
        if not product or not l4t:
            return
        if not self._ensure_sudo():
            self._flash_log("[WARN] 未获得 sudo 权限，烧录取消")
            return
        self._run_flash_thread(product, l4t, flash_only=True)

    def _retry_flash(self):
        product = self.flash_product_combo.currentText()
        l4t = self.flash_l4t_combo.currentText()
        if not product or not l4t:
            return
        self._flash_log("[INFO] 用户请求重新烧录，正在重试当前设备与版本")
        if not self._ensure_sudo():
            self._flash_log("[WARN] 未获得 sudo 权限，重新烧录取消")
            return
        self._run_flash_thread(product, l4t, flash_only=True)

    def _run_flash_thread(self, product, l4t, force_redownload=False,
                          download_only=False, prepare_only=False, flash_only=False):
        is_actual_flash = flash_only or (not prepare_only and not download_only)
        self.flash_download_btn.setVisible(False)
        self.flash_clear_btn.setVisible(False)
        self.flash_cancel_btn.setVisible(True)
        self.flash_next_btn.setEnabled(False)
        self.flash_progress.setVisible(True)
        self.flash_progress.setValue(0)
        self.status_dot.setText("处理中")
        self.status_dot.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(11)}pt; background:transparent; padding:0;")
        if not flash_only:
            self.flash_log.clear()
        self._flash_log(f"[INFO] 开始：{product} / L4T {l4t}"
                        + (" [强制重下]" if force_redownload else "")
                        + (" [仅刷写]" if flash_only else ""))
        self._flash_prepare_only = prepare_only
        self._flash_download_only = download_only
        self._flash_flash_only = flash_only
        self._active_flash_status_label = self.flash_run_status_lbl if is_actual_flash else self.flash_status_lbl
        self._active_flash_progress = self.flash_run_progress if is_actual_flash else self.flash_progress
        self._active_flash_progress.setValue(0)
        self._active_flash_status_label.setStyleSheet(
            f"color:{C_GREEN if is_actual_flash else C_TEXT2}; background:transparent;"
        )
        if is_actual_flash:
            self._set_wizard_step(2)
            self.flash_step_stack.setCurrentIndex(2)
            self.flash_left_stack.setCurrentIndex(1)
            self.flash_run_cancel_btn.setVisible(True)
            self.flash_run_retry_btn.setVisible(False)
            self.flash_run_back_btn.setVisible(False)
            if hasattr(self, "flash_scene"):
                self.flash_scene.set_mode("flashing")
                self.flash_scene.set_download_progress(0.0)
        elif hasattr(self, "flash_scene"):
            self.flash_scene.set_mode("idle")
            self.flash_scene.set_download_progress(0.0)
        if hasattr(self, "flash_prepare_scene"):
            self.flash_prepare_scene.set_mode("downloading" if not is_actual_flash else "idle")
            self.flash_prepare_scene.set_download_progress(0.0 if not is_actual_flash else 1.0)

        self.flash_thread = FlashThread(product, l4t,
                                        self.skip_verify_cb.isChecked(),
                                        download_only,
                                        force_redownload=force_redownload,
                                        prepare_only=prepare_only,
                                        flash_only=flash_only)
        self.flash_thread.progress_msg.connect(self._on_flash_msg)
        self.flash_thread.progress_val.connect(self._on_flash_progress)
        self.flash_thread.progress_log.connect(self._flash_log)
        self.flash_thread.download_progress.connect(self._on_download_progress)
        self.flash_thread.finished.connect(self._on_flash_done)
        self.flash_thread.start()

    def _flash_log(self, text: str):
        from PyQt5.QtGui import QTextCursor
        self.flash_log.moveCursor(QTextCursor.End)
        self.flash_log.insertPlainText(text + "\n")
        self.flash_log.ensureCursorVisible()

    def _save_flash_log(self):
        text = self.flash_log.toPlainText().strip()
        if not text:
            self._flash_log("[WARN] 当前没有可保存的日志")
            return

        default_name = f"seeed_flash_log_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        default_path = str(Path.home() / default_name)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存烧录日志",
            default_path,
            "Log Files (*.log);;Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return

        try:
            Path(file_path).write_text(text + "\n", encoding="utf-8")
            self._flash_log(f"[OK] 日志已保存到 {file_path}")
        except Exception as exc:
            self._flash_log(f"[ERR] 保存日志失败: {exc}")

    def _cancel_flash(self):
        if self.flash_thread:
            self.flash_thread.cancel()

    def _on_flash_msg(self, msg):
        self._active_flash_status_label.setText(msg)
        self._flash_log(f"[INFO] {msg}")
        # 下载完成后恢复进度条为确定模式
        if "跳过下载" in msg or "校验" in msg or "解压" in msg or "刷写" in msg:
            bar = self._active_flash_progress
            if bar.maximum() == 0:   # indeterminate 状态
                bar.setRange(0, 100)
        if hasattr(self, "flash_prepare_scene") and self.flash_step_stack.currentIndex() == 0:
            if "解压" in msg:
                self.flash_prepare_scene.set_mode("downloading")
            elif "跳过下载" in msg:
                self.flash_prepare_scene.set_mode("downloading")
            elif "下载" in msg or "校验" in msg or "初始化" in msg:
                self.flash_prepare_scene.set_mode("downloading")
            elif "完成" in msg:
                self.flash_prepare_scene.set_mode("idle")

    def _on_flash_progress(self, value):
        self._active_flash_progress.setValue(value)
        if hasattr(self, "flash_prepare_scene") and self.flash_step_stack.currentIndex() == 0:
            self.flash_prepare_scene.set_download_progress(value / 100)
        if hasattr(self, "flash_scene") and self.flash_step_stack.currentIndex() == 2:
            self.flash_scene.set_download_progress(value / 100)

    def _on_download_progress(self, downloaded: int, total: int):
        """处理真实下载字节进度，更新进度条和状态标签。"""
        bar = self._active_flash_progress

        def _fmt(b):
            if b >= 1024 ** 3:
                return f"{b / 1024 ** 3:.1f} GB"
            if b >= 1024 ** 2:
                return f"{b / 1024 ** 2:.0f} MB"
            return f"{b / 1024:.0f} KB"

        if total > 0:
            pct = int(downloaded / total * 100)
            bar.setRange(0, 100)
            bar.setValue(pct)
            label_text = f"下载固件中... {_fmt(downloaded)} / {_fmt(total)}  ({pct}%)"
            if hasattr(self, "flash_prepare_scene") and self.flash_step_stack.currentIndex() == 0:
                self.flash_prepare_scene.set_download_progress(pct / 100)
        else:
            # total 未知：切换为 indeterminate 样式（range 0,0）
            bar.setRange(0, 0)
            label_text = f"下载固件中... {_fmt(downloaded)}"

        self._active_flash_status_label.setText(label_text)

    def _on_flash_done(self, ok, msg):
        was_prepare_only = getattr(self, "_flash_prepare_only", False)
        was_download_only = getattr(self, "_flash_download_only", False)
        was_flash_only   = getattr(self, "_flash_flash_only", False)
        was_actual_flash = was_flash_only or (not was_prepare_only and not was_download_only)
        self.flash_download_btn.setVisible(True)
        self.flash_clear_btn.setVisible(True)
        self.flash_cancel_btn.setVisible(False)
        self.flash_run_cancel_btn.setVisible(False)
        self.flash_run_retry_btn.setVisible(False)
        color = C_GREEN if ok else C_RED
        icon = "✓" if ok else "✗"
        # 恢复进度条为确定模式（防止 indeterminate 状态残留）
        self._active_flash_progress.setRange(0, 100)
        self._active_flash_progress.setValue(100 if ok else max(5, self._active_flash_progress.value()))
        self._active_flash_status_label.setText(f"{icon} {msg}")
        self._active_flash_status_label.setStyleSheet(f"color:{color}; background:transparent;")
        self._flash_log(f"[{'OK' if ok else 'ERR'}] {msg}")
        self.status_dot.setText("就绪")
        self.status_dot.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(11)}pt; background:transparent; padding:0;")
        self._update_cache_label()
        if hasattr(self, "flash_scene"):
            if was_actual_flash:
                self.flash_scene.set_mode("success" if ok else "error")
                self.flash_scene.set_download_progress(1.0 if ok else self._active_flash_progress.value() / 100)
            else:
                self.flash_scene.set_mode("idle")
                self.flash_scene.set_download_progress(0.0)
        if hasattr(self, "flash_prepare_scene") and not was_actual_flash:
            self.flash_prepare_scene.set_mode("idle" if ok else "error")
            self.flash_prepare_scene.set_download_progress(1.0 if ok else self._active_flash_progress.value() / 100)
        if hasattr(self, "flash_done_scene"):
            self.flash_done_scene.set_mode("success" if ok else "error")
            self.flash_done_scene.set_download_progress(1.0 if ok else self._active_flash_progress.value() / 100)
        if was_actual_flash and ok:
            self._set_wizard_step(3)
            self.flash_done_status_lbl.setText(f"✓ {msg}")
            self.flash_done_status_lbl.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
            self.flash_step_stack.setCurrentIndex(3)
            self.flash_left_stack.setCurrentIndex(2)
        elif was_actual_flash and not ok:
            self.flash_step_stack.setCurrentIndex(2)
            self.flash_left_stack.setCurrentIndex(1)
            self.flash_run_retry_btn.setVisible(True)
            self.flash_run_back_btn.setVisible(True)
        # 下载/解压成功后激活 Next
        if ok and not was_flash_only:
            try:
                product = self.flash_product_combo.currentText()
                l4t = self.flash_l4t_combo.currentText()
                flasher = JetsonFlasher(product, l4t)
                self._set_next_enabled(flasher.firmware_extracted())
            except Exception:
                pass
        self.status_dot.setStyleSheet(f"""
            color: {C_GREEN};
            font-size: {pt(11)}pt;
            background: transparent;
            padding: 0;
        """)
        self._update_cache_label()

    # ══════════════════════════════════════════
    #  PAGE 6: 社区
    # ══════════════════════════════════════════
    def _build_community_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._page_header("社区", "文档、论坛与常见问题解答"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setStyleSheet(f"background:{C_BG};")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(pt(32), pt(28), pt(32), pt(28))
        inner_lay.setSpacing(pt(24))

        # 快速链接
        links_card = make_card(12)
        links_lay = QVBoxLayout(links_card)
        links_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        links_lay.setSpacing(pt(16))
        links_lay.addWidget(make_label("快速链接", 15, C_TEXT, bold=True))

        link_grid = QGridLayout()
        link_grid.setSpacing(pt(16))
        links = [
            ("📖", "Seeed Wiki", "Jetson 系列完整文档", "https://wiki.seeedstudio.com/"),
            ("💬", "Seeed 论坛", "社区问答与经验分享", "https://forum.seeedstudio.com/"),
            ("🐙", "GitHub", "开源代码与 Issue 反馈", "https://github.com/Seeed-Studio"),
            ("🎥", "视频教程", "YouTube 上手教程合集", "https://www.youtube.com/@SeeedStudio"),
            ("📦", "NVIDIA NGC", "官方容器镜像仓库", "https://catalog.ngc.nvidia.com/"),
            ("🤗", "Hugging Face", "模型与数据集下载", "https://huggingface.co/"),
        ]
        for i, (icon, name, desc, url) in enumerate(links):
            c = make_card(10)
            cl = QVBoxLayout(c)
            cl.setContentsMargins(pt(16), pt(14), pt(16), pt(14))
            cl.setSpacing(pt(6))
            top = QHBoxLayout()
            top.addWidget(make_label(icon, 20))
            top.addStretch()
            cl.addLayout(top)
            cl.addWidget(make_label(name, 13, C_TEXT, bold=True))
            cl.addWidget(make_label(desc, 11, C_TEXT2))
            open_btn = make_button("打开 →", small=True)
            _url = url
            open_btn.clicked.connect(lambda _, u=_url: self._open_url(u))
            cl.addWidget(open_btn)
            link_grid.addWidget(c, i // 3, i % 3)

        links_lay.addLayout(link_grid)
        inner_lay.addWidget(links_card)

        # 产品购买入口
        buy_card = make_card(12)
        buy_lay = QVBoxLayout(buy_card)
        buy_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        buy_lay.setSpacing(pt(16))
        buy_lay.addWidget(make_label("购买商品", 15, C_TEXT, bold=True))
        buy_lay.addWidget(make_label("按产品型号打开对应商品页，购买整机或官方配套版本。", 12, C_TEXT3))

        self.community_buy_combo = QComboBox()
        self.community_buy_combo.addItems(sorted(self.products.keys()))
        self.community_buy_combo.currentTextChanged.connect(self._update_community_buy_button)
        buy_lay.addWidget(self.community_buy_combo)

        self.community_buy_btn = make_button("购买商品", primary=True, small=True)
        self.community_buy_btn.clicked.connect(
            lambda: self._open_selected_product_purchase(self.community_buy_combo.currentText())
        )
        buy_lay.addWidget(self.community_buy_btn)
        inner_lay.addWidget(buy_card)
        inner_lay.addStretch()

        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        self._update_community_buy_button(self.community_buy_combo.currentText())
        return page

    def _get_product_purchase_url(self, product: str) -> str:
        info = self.product_images.get(product, {})
        purchase_url = (info.get("purchase_url") or "").strip()
        if purchase_url:
            return purchase_url

        purchase_map = {
            "j4012s": "https://www.seeedstudio.com/reComputer-Super-Bundle.html",
            "j4011s": "https://www.seeedstudio.com/reComputer-Super-Bundle.html",
            "j3011s": "https://www.seeedstudio.com/reComputer-Super-Bundle.html",
            "j3010s": "https://www.seeedstudio.com/reComputer-Super-Bundle.html",
            "j4012mini": "https://www.seeedstudio.com/reComputer-Mini-optional-accessories.html",
            "j4011mini": "https://www.seeedstudio.com/reComputer-Mini-optional-accessories.html",
            "j3011mini": "https://www.seeedstudio.com/reComputer-Mini-optional-accessories.html",
            "j3010mini": "https://www.seeedstudio.com/reComputer-Mini-optional-accessories.html",
            "j4012robotics": "https://www.seeedstudio.com/reComputer-Robotics-J4012-p-6505.html",
            "j4011robotics": "https://www.seeedstudio.com/reComputer-Robotics-J4012-p-6505.html",
            "j3011robotics": "https://www.seeedstudio.com/reComputer-Robotics-J3011-p-6503.html",
            "j3010robotics": "https://www.seeedstudio.com/reComputer-Robotics-J4012-p-6505.html",
            "j4012classic": "https://www.seeedstudio.com/reComputer-J4012-w-o-power-adapter-p-5628.html",
            "j4011classic": "https://www.seeedstudio.com/reComputer-J4011-w-o-power-adapter-p-5629.html",
            "j3011classic": "https://www.seeedstudio.com/reComputer-J3011-p-5590.html",
            "j3010classic": "https://www.seeedstudio.com/reComputer-J3010-w-o-power-adapter-p-5631.html",
            "j4012industrial": "https://www.seeedstudio.com/reComputer-Industrial-J4012-p-5684.html",
            "j4011industrial": "https://www.seeedstudio.com/reComputer-Industrial-J4011-p-5681.html",
            "j3011industrial": "https://www.seeedstudio.com/reComputer-Industrial-J3011-p-5682.html",
            "j3010industrial": "https://www.seeedstudio.com/reComputer-Industrial-J3010-p-5686.html",
            "j2012industrial": "https://www.seeedstudio.com/reComputer-Industrial-J2012-p-5685.html",
            "j2011industrial": "https://www.seeedstudio.com/reComputer-Industrial-J2011-p-5683.html",
            "j4012reserver": "https://www.seeedstudio.com/reServer-industrial-J4012-p-5747.html",
            "j4011reserver": "https://www.seeedstudio.com/reServer-industrial-J4011-p-5748.html",
            "j3011reserver": "https://www.seeedstudio.com/reServer-industrial-J3011-p-5750.html",
            "j3010reserver": "https://www.seeedstudio.com/reServer-industrial-J3010-p-5749.html",
            "j501-carrier AGX-Orin 64g": "https://www.seeedstudio.com/reServer-Industrial-J501-Carrier-Board-Add-on.html",
            "j501-carrier AGX-Orin 32g": "https://www.seeedstudio.com/reServer-Industrial-J501-Carrier-Board-Add-on.html",
            "j501mini-agx-orin-64g": "https://www.seeedstudio.com/reComputer-Mini-J501-Carrier-Board-for-Jetson-AGX-Orin-p-6606.html",
            "j501mini-agx-orin-32g": "https://www.seeedstudio.com/reComputer-Mini-J501-Carrier-Board-for-Jetson-AGX-Orin-p-6606.html",
            "j501-agx-orin-64g": "https://www.seeedstudio.com/reComputer-Robotics-J5012-with-GMSL-extension-board-p-6682.html",
            "j501-agx-orin-32g": "https://www.seeedstudio.com/reComputer-Robotics-J5012-with-GMSL-extension-board-p-6682.html",
        }
        return purchase_map.get(product, (info.get("getting_started") or "").strip())

    def _update_community_buy_button(self, product: str):
        if not hasattr(self, "community_buy_btn"):
            return
        url = self._get_product_purchase_url(product)
        self.community_buy_btn.setEnabled(bool(url))
        self.community_buy_btn.setToolTip(url if url else "未找到该产品的购买链接")

    def _open_selected_product_purchase(self, product: str):
        url = self._get_product_purchase_url(product)
        if url:
            self._open_url(url)

    def _sync_language_selector(self):
        if not hasattr(self, "lang_menu_btn"):
            return
        self.lang_menu_btn.setText("Language" if self._lang == "en" else "语言")
        self.lang_menu_btn.setToolTip(
            "切换界面语言" if self._lang == "zh" else "Switch interface language"
        )
        for code, action in getattr(self, "_lang_actions", {}).items():
            action.setChecked(code == self._lang)

    def _set_language(self, lang: str):
        if not lang or lang == self._lang:
            return
        self._lang = lang
        self._apply_runtime_language()

    def _apply_runtime_language(self):
        apply_language(self, self._lang)
        self.setMinimumSize(1120 if self._lang == "en" else 1080, 720)
        if hasattr(self, "_sidebar"):
            self._sidebar.setFixedWidth(pt(220) if self._lang == "en" else pt(200))
        if hasattr(self, "status_dot"):
            self.status_dot.setText(translate_text("就绪", self._lang))
        self._update_env_label()
        self._sync_language_selector()
        if hasattr(self, "flash_product_combo"):
            self._on_flash_product_changed(self.flash_product_combo.currentText())
        if hasattr(self, "community_buy_combo"):
            self._update_community_buy_button(self.community_buy_combo.currentText())
        self._update_flash_adaptive_layout()

    def _open_url(self, url):
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))


# ─────────────────────────────────────────────
#  入口
# ─────────────────────────────────────────────
def main():
    from PyQt5.QtGui import QFont
    app = QApplication(sys.argv)
    app.setApplicationName("Seeed Jetson Develop Tool")
    
    # 应用全局主题
    apply_app_theme()

    # DPI 自适应字体
    screen = app.primaryScreen()
    if screen:
        dpi = screen.logicalDotsPerInch()
        base_pt = max(11, round(13 * dpi / 96))
        app.setFont(build_app_font(base_pt))

    win = MainWindowV2()

    # 窗口大小基于屏幕可用区域
    if screen:
        geo = screen.availableGeometry()
        w = max(1080, min(int(geo.width()  * 0.85), 1920))
        h = max(720, min(int(geo.height() * 0.88), 1080))
        win.resize(w, h)
        # 居中
        win.move(
            geo.x() + (geo.width()  - w) // 2,
            geo.y() + (geo.height() - h) // 2,
        )

    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
