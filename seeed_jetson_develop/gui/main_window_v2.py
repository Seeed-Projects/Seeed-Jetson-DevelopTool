"""
Seeed Jetson Develop Tool - 主窗口 V2
无边框大气风格 - 用背景层次代替线条
"""
import json
import logging
import re
import sys
import traceback
from pathlib import Path

from PyQt5.QtCore import Qt, QPoint, QEvent, QTimer
from PyQt5.QtGui import QColor, QPixmap, QPainter
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame,
    QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QToolButton, QMenu,
    QTextEdit, QStackedWidget,
)

# 使用新的无边框主题
from .theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_ORANGE,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt, make_label, make_button, make_card,
    apply_shadow, apply_app_theme, build_app_font,
)
from ..core.platform_detect import is_jetson
from ..core.events import bus
from .ai_chat import FloatingAIAssistant, build_ai_system_prompt
from .i18n import get_language, set_language as _save_language, t
from .runtime_i18n import apply_language


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

NAV_ITEMS = [
    ("flash", "main.nav.flash"),
    ("remote", "main.nav.remote"),
    ("devices", "main.nav.devices"),
    ("apps", "main.nav.apps"),
    ("skills", "main.nav.skills"),
    ("community", "main.nav.community"),
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
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 rgba(141,194,31,0.18), stop:1 rgba(141,194,31,0.06));
                    border: none;
                    border-left: 3px solid {C_GREEN};
                    border-radius: 0px;
                    border-top-right-radius: 10px;
                    border-bottom-right-radius: 10px;
                    color: {C_GREEN};
                    font-size: {fs}pt;
                    font-weight: 700;
                    text-align: left;
                    padding-left: {pad - 3}px;
                    margin: 0 8px 0 0;
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
                    background: rgba(255,255,255,0.05);
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
        self._lang = get_language()
        self._drag = False
        self._drag_pos = QPoint()
        self._resize_edge = None   # 当前拖拽的边缘方向
        self._resize_start_pos = None
        self._resize_start_geom = None
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
        self.setWindowTitle(t("main.app_title", lang=self._lang))
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
        from seeed_jetson_develop.modules.flash.page import build_page as _flash_page
        from seeed_jetson_develop.modules.devices.page import build_page as _devices_page
        from seeed_jetson_develop.modules.community.page import build_page as _community_page
        from seeed_jetson_develop.modules.remote.page import build_page as _remote_page
        # 顺序必须与 NAV_ITEMS 一致: flash, remote, devices, apps, skills, community
        self.stack.addWidget(_flash_page())        # 0
        self.stack.addWidget(_remote_page())       # 1
        self.stack.addWidget(_devices_page())      # 2
        # Apps 页面延迟加载（placeholder 占位，首次访问时替换）
        self._apps_placeholder = QWidget()
        self._apps_placeholder.setStyleSheet(f"background:{C_BG};")
        self._apps_built = False
        self.stack.addWidget(self._apps_placeholder)   # 3: apps
        # Skills 页面延迟加载
        self._skills_placeholder = QWidget()
        self._skills_placeholder.setStyleSheet(f"background:{C_BG};")
        self._skills_built = False
        self.stack.addWidget(self._skills_placeholder) # 4: skills
        self.stack.addWidget(_community_page(self.products, self.product_images))  # 5: community
        content_layout.addWidget(self.stack)

        body_layout.addWidget(content_area, 1)
        root_layout.addWidget(body, 1)

        self._set_page(0)
        self._floating_ai = FloatingAIAssistant(self, system_prompt=build_ai_system_prompt())
        self._apply_runtime_language()

    def resizeEvent(self, event):
        super().resizeEvent(event)

    # ── 标题栏 - 带底部微光分隔线 ───────────────────────
    def _build_titlebar(self):
        bar = QFrame()
        bar.setFixedHeight(pt(64))
        bar.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #0E1620, stop:1 {C_BG_DEEP});
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

        self._title_label = QLabel(t("main.title.tool", lang=self._lang))
        self._title_label.setStyleSheet(f"color:{C_TEXT2}; font-size:{pt(13)}pt; background:transparent; font-weight:500;")
        lay.addWidget(self._title_label)
        lay.addStretch()

        # 状态指示
        self.status_dot = QLabel(t("common.ready", lang=self._lang))
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
        for code, text in [("en", "English"), ("zh-CN", "中文")]:
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
        if self._lang == "en" and ev.type() == QEvent.Show and src is self:
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

    # ── 侧边栏 - 带右侧微光分隔线 ──────────────────────
    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setFixedWidth(pt(220) if self._lang == "en" else pt(200))
        sidebar.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {C_BG_DEEP}, stop:1 #0D1520);
            border-right: 1px solid rgba(255,255,255,0.05);
        """)
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
        self._brand_label = make_label(t("main.brand.workspace", lang=self._lang), 12, C_TEXT2, bold=True)
        brand_lay.addWidget(self._brand_label)
        lay.addWidget(brand_container)

        lay.addSpacing(0)

        # 导航按钮
        for idx, (key, label_key) in enumerate(NAV_ITEMS):
            btn = SidebarButton(t(label_key, lang=self._lang))
            btn._i18n_key = label_key
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
        # Apps 页面（index=3）首次访问时懒加载
        if idx == 3 and not self._apps_built:
            try:
                from seeed_jetson_develop.modules.apps.page import build_page as _apps_page
                real_page = _apps_page()
            except Exception:
                msg = traceback.format_exc()
                log.error("failed to build App Market page\n%s", msg)
                real_page = self._build_lazy_error_page(
                    t("main.lazy.apps_error_title", lang=self._lang),
                    t("main.lazy.load_error_message", lang=self._lang),
                    msg,
                )
            self._apps_built = True
            _apps_idx = self.stack.indexOf(self._apps_placeholder)
            self.stack.removeWidget(self._apps_placeholder)
            self.stack.insertWidget(_apps_idx, real_page)
            self._apps_placeholder.deleteLater()
            if self._lang == "en":
                from .runtime_i18n import apply_language
                apply_language(real_page, "en")
        # Skills 页面（index=4）首次访问时懒加载
        if idx == 4 and not self._skills_built:
            try:
                from seeed_jetson_develop.modules.skills.page import build_page as _skills_page
                real_page = _skills_page()
            except Exception:
                msg = traceback.format_exc()
                log.error("failed to build Skills page\n%s", msg)
                real_page = self._build_lazy_error_page(
                    t("main.lazy.skills_error_title", lang=self._lang),
                    t("main.lazy.load_error_message", lang=self._lang),
                    msg,
                )
            self._skills_built = True
            _skills_idx = self.stack.indexOf(self._skills_placeholder)
            self.stack.removeWidget(self._skills_placeholder)
            self.stack.insertWidget(_skills_idx, real_page)
            self._skills_placeholder.deleteLater()
            if self._lang == "en":
                from .runtime_i18n import apply_language
                apply_language(real_page, "en")
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
            self._env_dot.setText("● " + t("common.status.local_jetson", lang=self._lang))
            self._env_dot.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(10)}pt; background:transparent; padding:8px 0 4px {pad}px;")
        elif self._remote_connected:
            self._env_dot.setText("● " + t("common.status.remote_connected", lang=self._lang))
            self._env_dot.setStyleSheet(f"color:{C_BLUE}; font-size:{pt(10)}pt; background:transparent; padding:8px 0 4px {pad}px;")
        else:
            self._env_dot.setText("● " + t("common.status.no_device", lang=self._lang))
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
        lay.setContentsMargins(pt(32), pt(10), pt(32), pt(10))
        lay.setSpacing(0)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        text_col.setContentsMargins(0, 0, 0, 0)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color:{C_TEXT}; font-size:{pt(18)}px; font-weight:700; background:transparent;")
        text_col.addWidget(title_lbl)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}px; background:transparent;")
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

    def _sync_language_selector(self):
        if not hasattr(self, "lang_menu_btn"):
            return
        self.lang_menu_btn.setText(t("common.language", lang=self._lang))
        self.lang_menu_btn.setToolTip(t("common.switch_language", lang=self._lang))
        for code, action in getattr(self, "_lang_actions", {}).items():
            action.setChecked(code == self._lang)

    def _set_language(self, lang: str):
        if not lang or lang == self._lang:
            return
        self._lang = _save_language(lang)
        self._apply_runtime_language()

    def _apply_runtime_language(self):
        apply_language(self, self._lang)
        self.setMinimumSize(1120 if self._lang == "en" else 1080, 720)
        if hasattr(self, "_sidebar"):
            self._sidebar.setFixedWidth(pt(220) if self._lang == "en" else pt(200))
        if hasattr(self, "status_dot"):
            self.status_dot.setText(t("common.ready", lang=self._lang))
        if hasattr(self, "_title_label"):
            self._title_label.setText(t("main.title.tool", lang=self._lang))
        if hasattr(self, "_brand_label"):
            self._brand_label.setText(t("main.brand.workspace", lang=self._lang))
        self.setWindowTitle(t("main.app_title", lang=self._lang))
        for btn in getattr(self, "_nav_btns", []):
            key = getattr(btn, "_i18n_key", None)
            if key:
                btn.setText(t(key, lang=self._lang))
        if hasattr(self, "stack"):
            for idx in range(self.stack.count()):
                page = self.stack.widget(idx)
                if hasattr(page, "retranslate_ui"):
                    # Backward-compatible: support both retranslate_ui(lang)
                    # and legacy retranslate_ui() page implementations.
                    try:
                        page.retranslate_ui(self._lang)
                    except TypeError:
                        page.retranslate_ui()
                else:
                    apply_language(page, self._lang)
        self._update_env_label()
        self._sync_language_selector()
        # Notify floating AI assistant
        if hasattr(self, "_floating_ai"):
            chat = getattr(self._floating_ai, "_chat", None)
            if chat and hasattr(chat, "retranslate_ui"):
                chat.retranslate_ui(self._lang)
            # Rebuild system prompt in new language
            from seeed_jetson_develop.gui.ai_chat import build_ai_system_prompt
            self._floating_ai._system = build_ai_system_prompt()
            self._floating_ai._chat.set_system(self._floating_ai._system)

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
