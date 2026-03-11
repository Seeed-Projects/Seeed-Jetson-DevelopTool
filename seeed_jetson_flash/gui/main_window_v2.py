"""
Seeed Jetson Develop Tool - 主窗口 V2
基于 PRD 设计：烧录 / 设备管理 / 应用市场 / Skills / 远程开发 / 社区
"""
import json
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QPoint, QEvent, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QPixmap, QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox,
    QProgressBar, QTextEdit, QScrollArea,
    QStackedWidget, QGraphicsDropShadowEffect,
    QSizePolicy, QSpacerItem,
)

from .styles import MAIN_STYLE, SEEED_GREEN, SEEED_BLUE
from ..flash import JetsonFlasher


# ─────────────────────────────────────────────
#  颜色常量
# ─────────────────────────────────────────────
C_BG        = "#0F1923"   # 深色主背景
C_SIDEBAR   = "#111D2B"   # 侧边栏
C_CARD      = "#162030"   # 卡片背景
C_CARD2     = "#1A2840"   # 卡片次色
C_BORDER    = "#1E3048"   # 边框
C_GREEN     = "#8DC21F"   # Seeed 绿
C_GREEN2    = "#76B900"   # NVIDIA 绿
C_BLUE      = "#2C7BE5"   # 信息蓝
C_ORANGE    = "#F5A623"   # 警告橙
C_RED       = "#E53E3E"   # 错误红
C_TEXT      = "#E8F0F8"   # 主文字
C_TEXT2     = "#8BA0B8"   # 次文字
C_TEXT3     = "#4A6278"   # 暗文字
C_TOPBAR    = "#0D1720"   # 顶栏


APP_STYLE = f"""
* {{
    font-family: "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {C_TEXT};
}}
QMainWindow, QWidget {{
    background-color: {C_BG};
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: {C_CARD};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {C_BORDER};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C_TEXT3};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {C_CARD};
    height: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {C_BORDER};
    border-radius: 3px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QComboBox {{
    background: {C_CARD2};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {C_TEXT};
    min-height: 22px;
}}
QComboBox:hover {{ border-color: {C_GREEN}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {C_CARD2};
    border: 1px solid {C_BORDER};
    selection-background-color: {C_GREEN};
    color: {C_TEXT};
}}
QCheckBox {{ color: {C_TEXT2}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {C_BORDER};
    border-radius: 3px;
    background: {C_CARD2};
}}
QCheckBox::indicator:checked {{
    background: {C_GREEN};
    border-color: {C_GREEN};
}}
QProgressBar {{
    background: {C_CARD2};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {C_GREEN},stop:1 {C_GREEN2});
    border-radius: 4px;
}}
QTextEdit {{
    background: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    color: {C_TEXT2};
    padding: 6px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
}}
QToolTip {{
    background: {C_CARD2};
    border: 1px solid {C_BORDER};
    color: {C_TEXT};
    padding: 4px 8px;
    border-radius: 4px;
}}
"""


def shadow(widget, blur=20, y=3, alpha=80):
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(blur)
    fx.setOffset(0, y)
    fx.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(fx)
    return widget


def make_label(text, size=13, color=C_TEXT, bold=False, wrap=False):
    lbl = QLabel(text)
    weight = "700" if bold else "400"
    lbl.setStyleSheet(f"color:{color}; font-size:{size}px; font-weight:{weight}; background:transparent;")
    if wrap:
        lbl.setWordWrap(True)
    return lbl


def make_btn(text, primary=False, danger=False, small=False):
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    h = "32px" if small else "38px"
    px = "12px 16px" if small else "10px 22px"
    fs = "12px" if small else "13px"
    if primary:
        bg, bg2, border, tc = C_GREEN, C_GREEN2, "#6A9A18", "#0A1A00"
    elif danger:
        bg, bg2, border, tc = "#C53030", "#9B2C2C", "#7B1D1D", "#FFE0E0"
    else:
        bg, bg2, border, tc = C_CARD2, C_CARD, C_BORDER, C_TEXT2
    btn.setStyleSheet(f"""
        QPushButton {{
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {bg},stop:1 {bg2});
            border: 1px solid {border};
            border-radius: 7px;
            color: {tc};
            font-size: {fs};
            font-weight: 600;
            padding: {px};
            min-height: {h};
        }}
        QPushButton:hover {{ background: {bg}; border-color: {C_GREEN if not danger else C_RED}; }}
        QPushButton:pressed {{ background: {bg2}; }}
        QPushButton:disabled {{ opacity: 0.4; }}
    """)
    return btn


def card_frame(radius=12):
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background: {C_CARD};
            border: 1px solid {C_BORDER};
            border-radius: {radius}px;
        }}
    """)
    return f


# ─────────────────────────────────────────────
#  Flash 线程（复用现有逻辑）
# ─────────────────────────────────────────────
class FlashThread(QThread):
    progress_msg = pyqtSignal(str)
    progress_val = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, product, l4t, skip_verify=False, download_only=False):
        super().__init__()
        self.product = product
        self.l4t = l4t
        self.skip_verify = skip_verify
        self.download_only = download_only
        self._cancel = False

    def cancel(self): self._cancel = True

    def run(self):
        try:
            flasher = JetsonFlasher(self.product, self.l4t,
                                    progress_callback=self._on_dl,
                                    should_cancel=lambda: self._cancel)
            self.progress_msg.emit("初始化..."); self.progress_val.emit(2)
            self.progress_msg.emit("下载固件中..."); self.progress_val.emit(5)
            if not flasher.download_firmware():
                self.finished.emit(False, "固件下载失败"); return
            self.progress_val.emit(50)
            if not self.skip_verify:
                self.progress_msg.emit("校验 SHA256...")
                if not flasher.verify_firmware():
                    self.finished.emit(False, "SHA256 校验失败"); return
            self.progress_val.emit(65)
            if self.download_only:
                self.progress_val.emit(100)
                self.finished.emit(True, "固件下载完成（未刷写）"); return
            self.progress_msg.emit("解压固件...")
            if not flasher.extract_firmware():
                self.finished.emit(False, "固件解压失败"); return
            self.progress_val.emit(80)
            self.progress_msg.emit("刷写中...")
            if not flasher.flash_firmware():
                self.finished.emit(False, "刷写失败"); return
            self.progress_val.emit(100)
            self.finished.emit(True, "刷写完成！")
        except Exception as e:
            self.finished.emit(False, str(e))

    def _on_dl(self, stage, cur, total):
        if stage == "download" and total:
            pct = int(5 + (cur / total) * 45)
            self.progress_val.emit(pct)


# ─────────────────────────────────────────────
#  侧边栏导航
# ─────────────────────────────────────────────
NAV_ITEMS = [
    ("flash",   "⚡", "烧录"),
    ("devices", "🖥", "设备管理"),
    ("apps",    "📦", "应用市场"),
    ("skills",  "🤖", "Skills"),
    ("remote",  "💻", "远程开发"),
    ("community","💬", "社区"),
]


class SidebarButton(QPushButton):
    def __init__(self, icon, label, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self._icon = icon
        self._label = label
        self.setText(f"  {icon}  {label}")
        self.setFixedHeight(44)
        self._apply_style(False)

    def _apply_style(self, active):
        if active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 rgba(141,194,31,0.18), stop:1 rgba(141,194,31,0.05));
                    border: none;
                    border-left: 3px solid {C_GREEN};
                    border-radius: 0px;
                    color: {C_GREEN};
                    font-size: 13px;
                    font-weight: 700;
                    text-align: left;
                    padding-left: 14px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 0px;
                    color: {C_TEXT2};
                    font-size: 13px;
                    font-weight: 500;
                    text-align: left;
                    padding-left: 14px;
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
        self._drag = False
        self._drag_pos = QPoint()
        self.flash_thread = None
        self._nav_btns = []
        self._current_page = 0

        self.l4t_data = []
        self.product_images = {}
        self.recovery_guides = {}
        self.products = {}
        self._load_data()
        self._init_ui()

    # ── 数据 ──────────────────────────────────
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

    # ── UI 骨架 ───────────────────────────────
    def _init_ui(self):
        self.setWindowTitle("Seeed Jetson Develop Tool")
        self.setMinimumSize(1280, 800)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet(APP_STYLE)

        root = QWidget()
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
        self.stack.addWidget(self._build_flash_page())
        self.stack.addWidget(self._build_devices_page())
        self.stack.addWidget(self._build_apps_page())
        self.stack.addWidget(self._build_skills_page())
        self.stack.addWidget(self._build_remote_page())
        self.stack.addWidget(self._build_community_page())
        content_layout.addWidget(self.stack)

        body_layout.addWidget(content_area, 1)
        root_layout.addWidget(body, 1)

        self._set_page(0)

    # ── 标题栏 ────────────────────────────────
    def _build_titlebar(self):
        bar = QFrame()
        bar.setFixedHeight(42)
        bar.setStyleSheet(f"""
            QFrame {{
                background: {C_TOPBAR};
                border-bottom: 1px solid {C_BORDER};
            }}
        """)
        bar.installEventFilter(self)

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 8, 0)
        lay.setSpacing(8)

        # Logo
        logo_lbl = QLabel()
        logo_path = self.project_root / "seeed-logo-blend.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path)).scaled(90, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        else:
            logo_lbl.setText("🌱 Seeed")
            logo_lbl.setStyleSheet(f"color:{C_GREEN}; font-weight:700; font-size:14px;")
        lay.addWidget(logo_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(f"color:{C_BORDER};")
        sep.setFixedHeight(20)
        lay.addWidget(sep)

        title = make_label("Jetson Develop Tool", 13, C_TEXT2)
        lay.addWidget(title)
        lay.addStretch()

        # 状态指示
        self.status_dot = QLabel("● 就绪")
        self.status_dot.setStyleSheet(f"color:{C_GREEN}; font-size:12px; background:transparent;")
        lay.addWidget(self.status_dot)

        lay.addSpacing(12)

        for sym, slot in [("-", self.showMinimized), ("□", self._toggle_max), ("✕", self.close)]:
            b = QPushButton(sym)
            b.setFixedSize(32, 28)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {C_TEXT3};
                    font-size: 14px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background: {'#C53030' if sym == '✕' else 'rgba(255,255,255,0.08)'};
                    color: {C_TEXT};
                }}
            """)
            b.clicked.connect(slot)
            lay.addWidget(b)

        self._titlebar = bar
        return bar

    def _toggle_max(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def eventFilter(self, src, ev):
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

    # ── 侧边栏 ────────────────────────────────
    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background: {C_SIDEBAR};
                border-right: 1px solid {C_BORDER};
            }}
        """)

        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(2)

        # 品牌区
        brand = QWidget()
        brand.setStyleSheet("background:transparent;")
        brand_lay = QVBoxLayout(brand)
        brand_lay.setContentsMargins(16, 0, 16, 12)
        brand_lay.setSpacing(2)
        brand_lay.addWidget(make_label("Seeed Studio", 11, C_TEXT3))
        brand_lay.addWidget(make_label("Jetson 开发工作台", 12, C_TEXT2, bold=True))
        lay.addWidget(brand)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{C_BORDER}; background:{C_BORDER}; max-height:1px;")
        lay.addWidget(sep)
        lay.addSpacing(8)

        # 导航按钮
        for idx, (key, icon, label) in enumerate(NAV_ITEMS):
            btn = SidebarButton(icon, label)
            btn.clicked.connect(lambda _, i=idx: self._set_page(i))
            lay.addWidget(btn)
            self._nav_btns.append(btn)

        lay.addStretch()

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"color:{C_BORDER}; background:{C_BORDER}; max-height:1px;")
        lay.addWidget(sep2)

        ver = make_label("v0.2.0-dev", 11, C_TEXT3)
        ver.setContentsMargins(16, 8, 0, 0)
        lay.addWidget(ver)

        return sidebar

    def _set_page(self, idx):
        self._current_page = idx
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setActive(i == idx)

    # ── 通用页面头部 ──────────────────────────
    def _page_header(self, title, subtitle, badge=None):
        header = QWidget()
        header.setStyleSheet(f"background:{C_TOPBAR}; border-bottom:1px solid {C_BORDER};")
        header.setFixedHeight(64)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(28, 0, 28, 0)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.addWidget(make_label(title, 18, C_TEXT, bold=True))
        text_col.addWidget(make_label(subtitle, 12, C_TEXT2))
        lay.addLayout(text_col)
        lay.addStretch()

        if badge:
            b = QLabel(badge)
            b.setStyleSheet(f"""
                background: rgba(141,194,31,0.15);
                color: {C_GREEN};
                border: 1px solid rgba(141,194,31,0.3);
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 11px;
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
        lay.addWidget(self._page_header("⚡ 烧录中心", "选择设备型号与系统版本，一键完成固件刷写", "刷写工具"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setStyleSheet(f"background:{C_BG};")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(28, 24, 28, 24)
        inner_lay.setSpacing(16)

        # ── 流程步骤提示 ──
        steps_row = QHBoxLayout()
        steps_row.setSpacing(0)
        for i, (num, txt) in enumerate([("1", "选择设备"), ("2", "进入 Recovery"), ("3", "开始刷写"), ("4", "完成")]):
            step_w = QWidget()
            step_w.setStyleSheet("background:transparent;")
            sw_lay = QHBoxLayout(step_w)
            sw_lay.setContentsMargins(0, 0, 0, 0)
            sw_lay.setSpacing(6)

            circle = QLabel(num)
            circle.setFixedSize(26, 26)
            circle.setAlignment(Qt.AlignCenter)
            circle.setStyleSheet(f"""
                background: {C_GREEN if i == 0 else C_CARD2};
                color: {'#0A1A00' if i == 0 else C_TEXT3};
                border-radius: 13px;
                font-weight: 700;
                font-size: 12px;
            """)
            sw_lay.addWidget(circle)
            sw_lay.addWidget(make_label(txt, 12, C_TEXT if i == 0 else C_TEXT3))
            steps_row.addWidget(step_w)

            if i < 3:
                arrow = make_label("  ──────  ", 11, C_TEXT3)
                steps_row.addWidget(arrow)

        steps_row.addStretch()
        inner_lay.addLayout(steps_row)

        # ── 两列布局 ──
        cols = QHBoxLayout()
        cols.setSpacing(16)

        # 左列：设备选择 + 选项
        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        # 设备选择卡片
        dev_card = card_frame()
        dev_lay = QVBoxLayout(dev_card)
        dev_lay.setContentsMargins(20, 18, 20, 18)
        dev_lay.setSpacing(14)
        dev_lay.addWidget(make_label("📱 目标设备", 14, C_TEXT, bold=True))
        dev_lay.addWidget(make_label("选择产品型号和对应的 L4T 系统版本", 12, C_TEXT2))

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{C_BORDER}; max-height:1px;")
        dev_lay.addWidget(sep)

        row1 = QHBoxLayout()
        row1.addWidget(make_label("产品型号", 12, C_TEXT2))
        row1.addStretch()
        self.flash_product_combo = QComboBox()
        self.flash_product_combo.setMinimumWidth(260)
        self.flash_product_combo.addItems(sorted(self.products.keys()))
        self.flash_product_combo.currentTextChanged.connect(self._on_flash_product_changed)
        row1.addWidget(self.flash_product_combo)
        dev_lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(make_label("L4T 版本", 12, C_TEXT2))
        row2.addStretch()
        self.flash_l4t_combo = QComboBox()
        self.flash_l4t_combo.setMinimumWidth(260)
        row2.addWidget(self.flash_l4t_combo)
        dev_lay.addLayout(row2)

        self.flash_info = QLabel("等待选择产品...")
        self.flash_info.setWordWrap(True)
        self.flash_info.setStyleSheet(f"""
            background: {C_CARD2};
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            color: {C_TEXT2};
            padding: 10px 12px;
            font-size: 12px;
            line-height: 1.6;
        """)
        dev_lay.addWidget(self.flash_info)
        shadow(dev_card)
        left_col.addWidget(dev_card)

        # 选项卡片
        opt_card = card_frame()
        opt_lay = QVBoxLayout(opt_card)
        opt_lay.setContentsMargins(20, 18, 20, 18)
        opt_lay.setSpacing(10)
        opt_lay.addWidget(make_label("⚙️ 执行选项", 14, C_TEXT, bold=True))

        self.skip_verify_cb = QCheckBox("跳过 SHA256 校验（不推荐）")
        self.download_only_cb = QCheckBox("仅下载固件，不执行刷写")
        self.download_only_cb.stateChanged.connect(self._on_dl_mode_changed)
        opt_lay.addWidget(self.skip_verify_cb)
        opt_lay.addWidget(self.download_only_cb)

        self.mode_hint_lbl = make_label("当前模式：下载 + 刷写", 11, C_TEXT3)
        opt_lay.addWidget(self.mode_hint_lbl)
        shadow(opt_card)
        left_col.addWidget(opt_card)
        left_col.addStretch()

        cols.addLayout(left_col, 1)

        # 右列：任务执行 + 日志
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        task_card = card_frame()
        task_lay = QVBoxLayout(task_card)
        task_lay.setContentsMargins(20, 18, 20, 18)
        task_lay.setSpacing(12)
        task_lay.addWidget(make_label("🚀 任务执行", 14, C_TEXT, bold=True))
        task_lay.addWidget(make_label("执行前请确认设备已进入 Recovery 模式", 12, C_TEXT2))

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"background:{C_BORDER}; max-height:1px;")
        task_lay.addWidget(sep2)

        self.flash_status_lbl = make_label("尚未开始", 13, C_TEXT2)
        task_lay.addWidget(self.flash_status_lbl)

        self.flash_progress = QProgressBar()
        self.flash_progress.setRange(0, 100)
        self.flash_progress.setValue(0)
        self.flash_progress.setFixedHeight(6)
        self.flash_progress.setVisible(False)
        task_lay.addWidget(self.flash_progress)

        btn_row = QHBoxLayout()
        self.flash_run_btn = make_btn("⚡  开始刷写", primary=True)
        self.flash_run_btn.clicked.connect(self._start_flash)
        self.flash_cancel_btn = make_btn("✕  取消", danger=True)
        self.flash_cancel_btn.setVisible(False)
        self.flash_cancel_btn.clicked.connect(self._cancel_flash)
        self.recovery_guide_btn = make_btn("🔄  Recovery 指南", small=True)
        self.recovery_guide_btn.clicked.connect(lambda: self._set_page(1))
        btn_row.addWidget(self.flash_run_btn)
        btn_row.addWidget(self.flash_cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.recovery_guide_btn)
        task_lay.addLayout(btn_row)
        shadow(task_card)
        right_col.addWidget(task_card)

        log_card = card_frame()
        log_lay = QVBoxLayout(log_card)
        log_lay.setContentsMargins(20, 18, 20, 18)
        log_lay.setSpacing(8)
        hdr = QHBoxLayout()
        hdr.addWidget(make_label("📝 执行日志", 14, C_TEXT, bold=True))
        hdr.addStretch()
        clear_btn = make_btn("清空", small=True)
        clear_btn.clicked.connect(lambda: self.flash_log.clear())
        hdr.addWidget(clear_btn)
        log_lay.addLayout(hdr)
        self.flash_log = QTextEdit()
        self.flash_log.setReadOnly(True)
        self.flash_log.setMinimumHeight(180)
        log_lay.addWidget(self.flash_log)
        shadow(log_card)
        right_col.addWidget(log_card, 1)

        cols.addLayout(right_col, 1)
        inner_lay.addLayout(cols)
        inner_lay.addStretch()

        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        self._on_flash_product_changed(self.flash_product_combo.currentText())
        return page

    def _on_flash_product_changed(self, product):
        self.flash_l4t_combo.clear()
        if product in self.products:
            self.flash_l4t_combo.addItems(self.products[product])
        info = self.product_images.get(product, {})
        name = info.get("name", product)
        wiki = info.get("wiki", "—")
        versions = len(self.products.get(product, []))
        self.flash_info.setText(f"型号：{name}\n可用版本：{versions} 个\nWiki：{wiki}")

    def _on_dl_mode_changed(self, state):
        if state:
            self.mode_hint_lbl.setText("当前模式：仅下载（不执行刷写）")
        else:
            self.mode_hint_lbl.setText("当前模式：下载 + 刷写")

    def _start_flash(self):
        product = self.flash_product_combo.currentText()
        l4t = self.flash_l4t_combo.currentText()
        if not product or not l4t:
            return
        self.flash_run_btn.setVisible(False)
        self.flash_cancel_btn.setVisible(True)
        self.flash_progress.setVisible(True)
        self.flash_progress.setValue(0)
        self.status_dot.setText("● 刷写中")
        self.status_dot.setStyleSheet(f"color:{C_ORANGE}; font-size:12px; background:transparent;")
        self.flash_log.clear()
        self.flash_log.append(f"[INFO] 开始：{product} / L4T {l4t}")

        self.flash_thread = FlashThread(product, l4t,
                                        self.skip_verify_cb.isChecked(),
                                        self.download_only_cb.isChecked())
        self.flash_thread.progress_msg.connect(self._on_flash_msg)
        self.flash_thread.progress_val.connect(self.flash_progress.setValue)
        self.flash_thread.finished.connect(self._on_flash_done)
        self.flash_thread.start()

    def _cancel_flash(self):
        if self.flash_thread:
            self.flash_thread.cancel()

    def _on_flash_msg(self, msg):
        self.flash_status_lbl.setText(msg)
        self.flash_log.append(f"[INFO] {msg}")

    def _on_flash_done(self, ok, msg):
        self.flash_run_btn.setVisible(True)
        self.flash_cancel_btn.setVisible(False)
        color = C_GREEN if ok else C_RED
        icon = "✓" if ok else "✗"
        self.flash_status_lbl.setText(f"{icon} {msg}")
        self.flash_status_lbl.setStyleSheet(f"color:{color}; background:transparent;")
        self.flash_log.append(f"[{'OK' if ok else 'ERR'}] {msg}")
        self.status_dot.setText("● 就绪")
        self.status_dot.setStyleSheet(f"color:{C_GREEN}; font-size:12px; background:transparent;")

    # ══════════════════════════════════════════
    #  PAGE 2: 设备管理
    # ══════════════════════════════════════════
    def _build_devices_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._page_header("🖥 设备管理", "查看已连接设备状态、运行诊断与快速修复"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setStyleSheet(f"background:{C_BG};")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(28, 24, 28, 24)
        inner_lay.setSpacing(16)

        # ── 设备状态卡片 ──
        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        for icon, label, val, color in [
            ("🖥", "已连接设备", "0", C_TEXT2),
            ("🌐", "网络状态", "检测中...", C_ORANGE),
            ("⚡", "GPU / Torch", "未检测", C_TEXT2),
            ("🐳", "Docker", "未检测", C_TEXT2),
        ]:
            c = card_frame(8)
            cl = QVBoxLayout(c)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(4)
            top = QHBoxLayout()
            top.addWidget(make_label(icon, 20))
            top.addStretch()
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{color}; font-size:10px; background:transparent;")
            top.addWidget(dot)
            cl.addLayout(top)
            cl.addWidget(make_label(val, 20, C_TEXT, bold=True))
            cl.addWidget(make_label(label, 11, C_TEXT3))
            shadow(c, blur=12)
            status_row.addWidget(c, 1)
        inner_lay.addLayout(status_row)

        # ── 快速诊断 ──
        diag_card = card_frame()
        diag_lay = QVBoxLayout(diag_card)
        diag_lay.setContentsMargins(20, 18, 20, 18)
        diag_lay.setSpacing(12)

        hdr = QHBoxLayout()
        hdr.addWidget(make_label("🔍 快速诊断", 14, C_TEXT, bold=True))
        hdr.addStretch()
        diag_btn = make_btn("▶  运行诊断", primary=True, small=True)
        hdr.addWidget(diag_btn)
        diag_lay.addLayout(hdr)
        diag_lay.addWidget(make_label("自动检查网络、GPU Torch、Docker、jtop、摄像头等关键组件状态", 12, C_TEXT2))

        # 诊断项列表
        diag_items = [
            ("🌐", "网络连接", "ping 8.8.8.8", "待检测"),
            ("⚡", "GPU Torch (CUDA)", "python3 -c 'import torch; print(torch.cuda.is_available())'", "待检测"),
            ("🐳", "Docker 服务", "docker ps", "待检测"),
            ("📊", "jtop 监控", "which jtop", "待检测"),
            ("📷", "USB 摄像头", "ls /dev/video*", "待检测"),
            ("💾", "磁盘启动方式", "lsblk", "待检测"),
        ]
        for icon, name, cmd, status in diag_items:
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background: {C_CARD2};
                    border: 1px solid {C_BORDER};
                    border-radius: 6px;
                }}
            """)
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(12, 8, 12, 8)
            row_lay.addWidget(make_label(icon, 14))
            row_lay.addWidget(make_label(name, 13, C_TEXT))
            row_lay.addStretch()
            row_lay.addWidget(make_label(cmd, 11, C_TEXT3))
            row_lay.addSpacing(12)
            status_lbl = QLabel(status)
            status_lbl.setStyleSheet(f"""
                background: rgba(255,255,255,0.05);
                color: {C_TEXT3};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            """)
            row_lay.addWidget(status_lbl)
            diag_lay.addWidget(row)

        shadow(diag_card)
        inner_lay.addWidget(diag_card)

        # ── 外设状态 ──
        periph_card = card_frame()
        periph_lay = QVBoxLayout(periph_card)
        periph_lay.setContentsMargins(20, 18, 20, 18)
        periph_lay.setSpacing(12)
        periph_lay.addWidget(make_label("🔌 外设状态", 14, C_TEXT, bold=True))

        periph_grid = QGridLayout()
        periph_grid.setSpacing(10)
        for i, (icon, name, status, color) in enumerate([
            ("📡", "USB-WiFi", "未检测", C_TEXT3),
            ("📶", "5G 模组", "未检测", C_TEXT3),
            ("🔵", "蓝牙", "未检测", C_TEXT3),
            ("💾", "NVMe SSD", "未检测", C_TEXT3),
            ("📷", "摄像头", "未检测", C_TEXT3),
            ("🖥", "HDMI 显示", "未检测", C_TEXT3),
        ]):
            c = card_frame(8)
            cl = QVBoxLayout(c)
            cl.setContentsMargins(12, 10, 12, 10)
            cl.setSpacing(4)
            cl.addWidget(make_label(f"{icon}  {name}", 12, C_TEXT))
            sl = QLabel(status)
            sl.setStyleSheet(f"color:{color}; font-size:11px; background:transparent;")
            cl.addWidget(sl)
            periph_grid.addWidget(c, i // 3, i % 3)

        periph_lay.addLayout(periph_grid)
        shadow(periph_card)
        inner_lay.addWidget(periph_card)
        inner_lay.addStretch()

        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return page

    # ══════════════════════════════════════════
    #  PAGE 3: 应用市场
    # ══════════════════════════════════════════
    def _build_apps_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._page_header("📦 应用市场", "浏览、安装和管理 Jetson 应用与 Demo", "Beta"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setStyleSheet(f"background:{C_BG};")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(28, 24, 28, 24)
        inner_lay.setSpacing(20)

        # 分类 Tab
        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)
        for label in ["全部", "CV / 视觉", "大语言模型", "TTS 语音", "机器人", "已安装"]:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            is_active = label == "全部"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'rgba(141,194,31,0.15)' if is_active else 'transparent'};
                    border: 1px solid {'rgba(141,194,31,0.4)' if is_active else C_BORDER};
                    border-radius: 16px;
                    color: {C_GREEN if is_active else C_TEXT2};
                    font-size: 12px;
                    font-weight: {'700' if is_active else '400'};
                    padding: 5px 14px;
                }}
                QPushButton:hover {{ background: rgba(255,255,255,0.06); color:{C_TEXT}; }}
            """)
            tab_row.addWidget(btn)
        tab_row.addStretch()
        inner_lay.addLayout(tab_row)

        # 应用卡片网格
        apps = [
            ("🎯", "YOLOv8 目标检测", "CV / 视觉", "实时目标检测，支持摄像头输入", "已安装", C_GREEN),
            ("🤖", "Qwen2 本地推理", "大语言模型", "阿里 Qwen2 模型，支持中文对话", "安装", C_BLUE),
            ("🦾", "LeRobot 机器人", "机器人", "Hugging Face LeRobot 开发套件", "安装", C_BLUE),
            ("🗣", "Kokoro TTS", "TTS 语音", "高质量文字转语音，支持多语言", "安装", C_BLUE),
            ("🌊", "Stable Diffusion", "CV / 视觉", "本地图像生成，SDXL-Turbo 优化版", "安装", C_BLUE),
            ("📊", "Jupyter Lab", "开发工具", "交互式 Python 开发环境", "已安装", C_GREEN),
            ("🔴", "Node-RED", "开发工具", "可视化流程编排，IoT 场景适用", "安装", C_BLUE),
            ("🦙", "Ollama", "大语言模型", "本地 LLM 运行框架，支持多种模型", "安装", C_BLUE),
        ]

        grid = QGridLayout()
        grid.setSpacing(14)
        for i, (icon, name, category, desc, status, sc) in enumerate(apps):
            c = card_frame(10)
            cl = QVBoxLayout(c)
            cl.setContentsMargins(16, 16, 16, 16)
            cl.setSpacing(8)

            top = QHBoxLayout()
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"font-size:28px; background:transparent;")
            top.addWidget(icon_lbl)
            top.addStretch()
            cat_lbl = QLabel(category)
            cat_lbl.setStyleSheet(f"""
                background: rgba(44,123,229,0.15);
                color: {C_BLUE};
                border-radius: 4px;
                padding: 2px 7px;
                font-size: 10px;
            """)
            top.addWidget(cat_lbl)
            cl.addLayout(top)

            cl.addWidget(make_label(name, 13, C_TEXT, bold=True))
            cl.addWidget(make_label(desc, 11, C_TEXT2, wrap=True))
            cl.addStretch()

            btn_row = QHBoxLayout()
            btn_row.addStretch()
            app_btn = QPushButton(status)
            app_btn.setCursor(Qt.PointingHandCursor)
            is_installed = status == "已安装"
            app_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'rgba(141,194,31,0.12)' if is_installed else f'rgba(44,123,229,0.15)'};
                    border: 1px solid {'rgba(141,194,31,0.3)' if is_installed else 'rgba(44,123,229,0.3)'};
                    border-radius: 6px;
                    color: {C_GREEN if is_installed else C_BLUE};
                    font-size: 11px;
                    font-weight: 600;
                    padding: 4px 12px;
                }}
                QPushButton:hover {{ opacity: 0.8; }}
            """)
            btn_row.addWidget(app_btn)
            cl.addLayout(btn_row)
            shadow(c, blur=14)
            grid.addWidget(c, i // 4, i % 4)

        inner_lay.addLayout(grid)
        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return page

    # ══════════════════════════════════════════
    #  PAGE 4: Skills
    # ══════════════════════════════════════════
    def _build_skills_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._page_header("🤖 Skills 中心", "自动化执行环境修复、驱动适配与应用部署任务"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setStyleSheet(f"background:{C_BG};")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(28, 24, 28, 24)
        inner_lay.setSpacing(16)

        # 说明横幅
        banner = QFrame()
        banner.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(141,194,31,0.12), stop:1 rgba(44,123,229,0.08));
                border: 1px solid rgba(141,194,31,0.2);
                border-radius: 10px;
            }}
        """)
        banner_lay = QHBoxLayout(banner)
        banner_lay.setContentsMargins(20, 14, 20, 14)
        banner_lay.addWidget(make_label("💡", 24))
        banner_lay.addSpacing(10)
        txt_col = QVBoxLayout()
        txt_col.addWidget(make_label("Skills 是可编排的自动化执行单元", 13, C_TEXT, bold=True))
        txt_col.addWidget(make_label("每个 Skill 包含目标说明、依赖检查、执行步骤与结果反馈，支持一键运行或参数化配置", 12, C_TEXT2))
        banner_lay.addLayout(txt_col, 1)
        inner_lay.addWidget(banner)

        # Skills 分类
        skills_data = {
            "🔧 驱动 & 系统修复 (P0)": [
                ("USB-WiFi 驱动适配", "自动检测并安装 USB-WiFi 网卡驱动", "已验证", C_GREEN, "~5 min"),
                ("5G 模组驱动安装", "支持 EC20/EC25 等主流 5G 模组", "待验证", C_ORANGE, "~8 min"),
                ("浏览器无法打开修复", "修复 Chromium/Firefox 启动异常", "已验证", C_GREEN, "~2 min"),
                ("蓝牙 WiFi 冲突修复", "解决蓝牙与 WiFi 共存干扰问题", "待验证", C_ORANGE, "~3 min"),
                ("固态启动异常修复", "NVMe SSD 启动失败诊断与修复", "待验证", C_ORANGE, "~10 min"),
            ],
            "📦 应用 & 环境部署 (P0)": [
                ("LeRobot 开发环境配置", "一键配置 Hugging Face LeRobot 开发环境", "已验证", C_GREEN, "~15 min"),
                ("Qwen Demo 适配", "适配 Qwen 模型在 Jetson 上的推理环境", "已验证", C_GREEN, "~20 min"),
                ("GPU Torch 安装", "安装 CUDA 版 PyTorch，自动匹配 JetPack 版本", "已验证", C_GREEN, "~10 min"),
                ("Docker 环境初始化", "安装并配置 Docker，设置镜像加速", "待验证", C_ORANGE, "~5 min"),
                ("jtop 监控工具安装", "安装 jetson-stats 系统监控工具", "已验证", C_GREEN, "~2 min"),
            ],
            "🌐 网络 & 远程 (P1)": [
                ("VS Code Server 部署", "在 Jetson 上部署 code-server 远程开发环境", "待验证", C_ORANGE, "~8 min"),
                ("Ollama 服务部署", "本地 LLM 推理服务，支持 API 访问", "待验证", C_ORANGE, "~12 min"),
                ("网络代理配置", "配置 apt/pip/docker 代理加速", "待验证", C_ORANGE, "~3 min"),
            ],
        }

        for category, skills in skills_data.items():
            cat_card = card_frame()
            cat_lay = QVBoxLayout(cat_card)
            cat_lay.setContentsMargins(20, 18, 20, 18)
            cat_lay.setSpacing(10)
            cat_lay.addWidget(make_label(category, 14, C_TEXT, bold=True))

            for name, desc, status, sc, duration in skills:
                skill_row = QFrame()
                skill_row.setStyleSheet(f"""
                    QFrame {{
                        background: {C_CARD2};
                        border: 1px solid {C_BORDER};
                        border-radius: 8px;
                    }}
                    QFrame:hover {{
                        border-color: rgba(141,194,31,0.3);
                    }}
                """)
                row_lay = QHBoxLayout(skill_row)
                row_lay.setContentsMargins(14, 10, 14, 10)
                row_lay.setSpacing(12)

                info_col = QVBoxLayout()
                info_col.setSpacing(3)
                info_col.addWidget(make_label(name, 13, C_TEXT, bold=True))
                info_col.addWidget(make_label(desc, 11, C_TEXT2))
                row_lay.addLayout(info_col, 1)

                row_lay.addWidget(make_label(duration, 11, C_TEXT3))

                status_lbl = QLabel(status)
                status_lbl.setStyleSheet(f"""
                    background: rgba({
                        '141,194,31' if sc == C_GREEN else
                        '245,166,35' if sc == C_ORANGE else '44,123,229'
                    },0.15);
                    color: {sc};
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: 600;
                """)
                row_lay.addWidget(status_lbl)

                run_btn = make_btn("▶  运行", primary=True, small=True)
                row_lay.addWidget(run_btn)

                cat_lay.addWidget(skill_row)

            shadow(cat_card)
            inner_lay.addWidget(cat_card)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return page

    # ══════════════════════════════════════════
    #  PAGE 5: 远程开发
    # ══════════════════════════════════════════
    def _build_remote_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._page_header("💻 远程开发", "通过 VS Code / Web IDE / AI 辅助建立远程开发环境"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setStyleSheet(f"background:{C_BG};")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(28, 24, 28, 24)
        inner_lay.setSpacing(16)

        # 连接状态卡片
        conn_card = card_frame()
        conn_lay = QVBoxLayout(conn_card)
        conn_lay.setContentsMargins(20, 18, 20, 18)
        conn_lay.setSpacing(12)

        hdr = QHBoxLayout()
        hdr.addWidget(make_label("🔗 设备连接", 14, C_TEXT, bold=True))
        hdr.addStretch()
        conn_status = QLabel("● 未连接")
        conn_status.setStyleSheet(f"color:{C_TEXT3}; font-size:12px; background:transparent;")
        hdr.addWidget(conn_status)
        conn_lay.addLayout(hdr)

        conn_row = QHBoxLayout()
        conn_row.addWidget(make_label("设备 IP / 主机名", 12, C_TEXT2))
        from PyQt5.QtWidgets import QLineEdit
        ip_input = QLineEdit()
        ip_input.setPlaceholderText("192.168.1.xxx 或 jetson.local")
        ip_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C_CARD2};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                color: {C_TEXT};
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {C_GREEN}; }}
        """)
        conn_row.addWidget(ip_input, 1)
        scan_btn = make_btn("🔍 扫描设备", small=True)
        conn_row.addWidget(scan_btn)
        conn_lay.addLayout(conn_row)
        shadow(conn_card)
        inner_lay.addWidget(conn_card)

        # 开发工具卡片
        tools = [
            ("🔵", "VS Code Remote SSH", "通过 SSH 远程连接，在本机 VS Code 中编辑 Jetson 代码",
             "需要本机安装 VS Code + Remote SSH 插件", "打开配置"),
            ("🌐", "VS Code Server (Web)", "在 Jetson 上运行 code-server，浏览器直接访问开发环境",
             "需要先通过 Skills 安装 code-server", "一键部署"),
            ("🤖", "Claude / AI 辅助", "接入 Claude API，在远程开发中获得 AI 代码辅助",
             "需要配置 API Key", "配置接入"),
            ("📓", "Jupyter Lab", "在 Jetson 上运行 Jupyter，浏览器访问交互式开发",
             "需要先安装 Jupyter Lab", "启动服务"),
        ]

        tools_card = card_frame()
        tools_lay = QVBoxLayout(tools_card)
        tools_lay.setContentsMargins(20, 18, 20, 18)
        tools_lay.setSpacing(12)
        tools_lay.addWidget(make_label("🛠 开发工具", 14, C_TEXT, bold=True))

        for icon, name, desc, note, action in tools:
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background: {C_CARD2};
                    border: 1px solid {C_BORDER};
                    border-radius: 8px;
                }}
            """)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 12, 14, 12)
            rl.setSpacing(14)

            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet("font-size:24px; background:transparent;")
            icon_lbl.setFixedWidth(36)
            rl.addWidget(icon_lbl)

            info = QVBoxLayout()
            info.setSpacing(3)
            info.addWidget(make_label(name, 13, C_TEXT, bold=True))
            info.addWidget(make_label(desc, 11, C_TEXT2))
            info.addWidget(make_label(f"ℹ  {note}", 10, C_TEXT3))
            rl.addLayout(info, 1)

            act_btn = make_btn(action, primary=True, small=True)
            rl.addWidget(act_btn)
            tools_lay.addWidget(row)

        shadow(tools_card)
        inner_lay.addWidget(tools_card)
        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return page

    # ══════════════════════════════════════════
    #  PAGE 6: 社区
    # ══════════════════════════════════════════
    def _build_community_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._page_header("💬 社区", "文档、论坛与常见问题解答"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setStyleSheet(f"background:{C_BG};")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(28, 24, 28, 24)
        inner_lay.setSpacing(16)

        # 快速链接
        links_card = card_frame()
        links_lay = QVBoxLayout(links_card)
        links_lay.setContentsMargins(20, 18, 20, 18)
        links_lay.setSpacing(12)
        links_lay.addWidget(make_label("🔗 快速链接", 14, C_TEXT, bold=True))

        link_grid = QGridLayout()
        link_grid.setSpacing(10)
        links = [
            ("📖", "Seeed Wiki", "Jetson 系列完整文档", "https://wiki.seeedstudio.com/"),
            ("💬", "Seeed 论坛", "社区问答与经验分享", "https://forum.seeedstudio.com/"),
            ("🐙", "GitHub", "开源代码与 Issue 反馈", "https://github.com/Seeed-Studio"),
            ("🎥", "视频教程", "YouTube 上手教程合集", "https://www.youtube.com/@SeeedStudio"),
            ("📦", "NVIDIA NGC", "官方容器镜像仓库", "https://catalog.ngc.nvidia.com/"),
            ("🤗", "Hugging Face", "模型与数据集下载", "https://huggingface.co/"),
        ]
        for i, (icon, name, desc, url) in enumerate(links):
            c = card_frame(8)
            cl = QVBoxLayout(c)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(4)
            top = QHBoxLayout()
            top.addWidget(make_label(icon, 18))
            top.addStretch()
            cl.addLayout(top)
            cl.addWidget(make_label(name, 13, C_TEXT, bold=True))
            cl.addWidget(make_label(desc, 11, C_TEXT2))
            open_btn = make_btn("打开 →", small=True)
            _url = url
            open_btn.clicked.connect(lambda _, u=_url: self._open_url(u))
            cl.addWidget(open_btn)
            shadow(c, blur=12)
            link_grid.addWidget(c, i // 3, i % 3)

        links_lay.addLayout(link_grid)
        shadow(links_card)
        inner_lay.addWidget(links_card)

        # Recovery 指南入口
        rec_card = card_frame()
        rec_lay = QVBoxLayout(rec_card)
        rec_lay.setContentsMargins(20, 18, 20, 18)
        rec_lay.setSpacing(12)
        rec_lay.addWidget(make_label("🔄 Recovery 模式指南", 14, C_TEXT, bold=True))
        rec_lay.addWidget(make_label("按产品型号查看进入 Recovery 模式的详细步骤", 12, C_TEXT2))

        rec_combo = QComboBox()
        rec_combo.addItems(sorted(self.products.keys()))
        rec_lay.addWidget(rec_combo)

        rec_btn = make_btn("查看指南", primary=True, small=True)
        rec_lay.addWidget(rec_btn)
        shadow(rec_card)
        inner_lay.addWidget(rec_card)
        inner_lay.addStretch()

        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return page

    def _open_url(self, url):
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))


# ─────────────────────────────────────────────
#  入口
# ─────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Seeed Jetson Develop Tool")
    win = MainWindowV2()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
