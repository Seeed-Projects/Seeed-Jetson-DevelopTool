"""
Seeed Jetson Develop Tool - 主窗口 V2
无边框大气风格 - 用背景层次代替线条
"""
import json
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QPoint, QEvent, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPixmap, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox,
    QProgressBar, QTextEdit, QScrollArea,
    QStackedWidget, QSizePolicy,
)

# 使用新的无边框主题
from .theme import (
    C_BG, C_BG_DEEP, C_BG_LIGHT, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_GREEN2, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt, make_label, make_button, make_card, make_input_card,
    make_section_header, apply_shadow, apply_app_theme
)
from ..flash import JetsonFlasher
from ..core.platform_detect import is_jetson
from ..core.events import bus


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


# ─────────────────────────────────────────────
#  Flash 线程
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
        self._drag = False
        self._drag_pos = QPoint()
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
        self.setMinimumSize(1080, 720)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)

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
        from seeed_jetson_develop.modules.devices.page import build_page as _devices_page
        from seeed_jetson_develop.modules.apps.page import build_page as _apps_page
        from seeed_jetson_develop.modules.skills.page import build_page as _skills_page
        from seeed_jetson_develop.modules.remote.page import build_page as _remote_page
        self.stack.addWidget(self._build_flash_page())
        self.stack.addWidget(_devices_page())
        self.stack.addWidget(_apps_page())
        self.stack.addWidget(_skills_page())
        self.stack.addWidget(_remote_page())
        self.stack.addWidget(self._build_community_page())
        content_layout.addWidget(self.stack)

        body_layout.addWidget(content_area, 1)
        root_layout.addWidget(body, 1)

        self._set_page(0)

    # ── 标题栏 - 无下边框 ───────────────────────
    def _build_titlebar(self):
        bar = QFrame()
        bar.setFixedHeight(pt(48))
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
        logo_path = self.project_root / "assets" / "seeed-logo-blend.png"
        if logo_path.exists():
            lh = pt(24)
            pix = QPixmap(str(logo_path)).scaled(int(lh * 90 / 28), lh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        else:
            logo_lbl.setText("Seeed")
            logo_lbl.setStyleSheet(f"color:{C_GREEN}; font-weight:700; font-size:{pt(12)}pt; background:transparent;")
        lay.addWidget(logo_lbl)

        # 分隔点代替线
        dot = QLabel("·")
        dot.setStyleSheet(f"color:{C_TEXT3}; font-size:20px; background:transparent;")
        lay.addWidget(dot)

        title = QLabel("Jetson Develop Tool")
        title.setStyleSheet(f"color:{C_TEXT2}; font-size:{pt(12)}pt; background:transparent; font-weight:500;")
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

        lay.addSpacing(16)

        # 窗口控制按钮
        for sym, slot, hover_col in [
            ("−", self.showMinimized, C_TEXT2),
            ("□", self._toggle_max,   C_TEXT2),
            ("×", self.close,         "#FF6B6B"),
        ]:
            b = QPushButton(sym)
            b.setFixedSize(pt(32), pt(28))
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

    # ── 侧边栏 - 无右边框 ──────────────────────
    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setFixedWidth(pt(200))
        sidebar.setStyleSheet(f"background: {C_BG_DEEP};")

        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # 品牌区 - 与标题栏同色，无下边框
        brand_container = QWidget()
        brand_container.setFixedHeight(pt(48))
        brand_container.setStyleSheet(f"background: {C_BG_DEEP};")
        brand_lay = QVBoxLayout(brand_container)
        brand_lay.setContentsMargins(pt(20), 0, 0, 0)
        brand_lay.setSpacing(2)
        brand_lay.setAlignment(Qt.AlignVCenter)
        brand_lay.addWidget(make_label("Seeed Studio", 9, C_TEXT3))
        brand_lay.addWidget(make_label("Jetson 开发工作台", 11, C_TEXT2, bold=True))
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
        if idx in (1, 2, 3) and not self._is_jetson and not self._remote_connected:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "需要先连接设备",
                "当前运行在 PC 上，请先在「远程开发」页建立 SSH 连接，再使用此功能。"
            )
            idx = 4

        self._current_page = idx
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setActive(i == idx)

    def _update_env_label(self):
        if not hasattr(self, "_env_dot"):
            return
        pad = pt(20)
        if self._is_jetson:
            self._env_dot.setText("● Jetson 本机")
            self._env_dot.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(10)}pt; background:transparent; padding:8px 0 4px {pad}px;")
        elif self._remote_connected:
            self._env_dot.setText("● 远程已连接")
            self._env_dot.setStyleSheet(f"color:{C_BLUE}; font-size:{pt(10)}pt; background:transparent; padding:8px 0 4px {pad}px;")
        else:
            self._env_dot.setText("● 未连接设备")
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

        for i, (num, txt) in enumerate(step_configs):
            # 步骤圆点
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
            
            # 文字
            lbl = QLabel(txt)
            lbl.setStyleSheet(f"""
                color: {C_GREEN if is_active else C_TEXT3};
                font-size: {pt(11)}pt;
                font-weight: {'600' if is_active else '400'};
                background: transparent;
                padding-left: 8px;
            """)
            step_layout.addWidget(lbl)
            
            # 箭头（最后一步除外）
            if i < 3:
                arrow = QLabel("›")
                arrow.setStyleSheet(f"color:{C_TEXT3}; font-size:24px; background:transparent; padding:0 16px;")
                step_layout.addWidget(arrow)

        step_layout.addStretch()
        wizard_outer.addLayout(step_layout)
        inner_lay.addWidget(wizard_card)

        # ── 两列布局 ──
        cols = QHBoxLayout()
        cols.setSpacing(pt(24))

        # 左列
        left_col = QVBoxLayout()
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

        # 信息展示
        self.flash_info = QLabel("等待选择产品...")
        self.flash_info.setWordWrap(True)
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
        left_col.addWidget(dev_card)

        # 选项卡片
        opt_card = make_card(12)
        opt_lay = QVBoxLayout(opt_card)
        opt_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        opt_lay.setSpacing(pt(12))
        opt_lay.addWidget(make_label("执行选项", 14, C_TEXT, bold=True))

        self.skip_verify_cb = QCheckBox("跳过 SHA256 校验（不推荐）")
        self.download_only_cb = QCheckBox("仅下载固件，不执行刷写")
        self.download_only_cb.stateChanged.connect(self._on_dl_mode_changed)
        opt_lay.addWidget(self.skip_verify_cb)
        opt_lay.addWidget(self.download_only_cb)

        self.mode_hint_lbl = make_label("当前模式：下载 + 刷写", 11, C_TEXT3)
        opt_lay.addWidget(self.mode_hint_lbl)
        left_col.addWidget(opt_card)
        left_col.addStretch()

        cols.addLayout(left_col, 1)

        # 右列
        right_col = QVBoxLayout()
        right_col.setSpacing(pt(20))

        task_card = make_card(12)
        task_lay = QVBoxLayout(task_card)
        task_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        task_lay.setSpacing(pt(16))
        task_lay.addWidget(make_label("任务执行", 14, C_TEXT, bold=True))
        task_lay.addWidget(make_label("执行前请确认设备已进入 Recovery 模式", 11, C_TEXT3))

        self.flash_status_lbl = make_label("尚未开始", 14, C_TEXT2)
        task_lay.addWidget(self.flash_status_lbl)

        self.flash_progress = QProgressBar()
        self.flash_progress.setRange(0, 100)
        self.flash_progress.setValue(0)
        self.flash_progress.setFixedHeight(6)
        self.flash_progress.setVisible(False)
        task_lay.addWidget(self.flash_progress)

        btn_row = QHBoxLayout()
        self.flash_run_btn = make_button("开始刷写", primary=True)
        self.flash_run_btn.clicked.connect(self._start_flash)
        self.flash_cancel_btn = make_button("取消", danger=True)
        self.flash_cancel_btn.setVisible(False)
        self.flash_cancel_btn.clicked.connect(self._cancel_flash)
        self.recovery_guide_btn = make_button("Recovery 指南", small=True)
        self.recovery_guide_btn.clicked.connect(lambda: self._set_page(1))
        btn_row.addWidget(self.flash_run_btn)
        btn_row.addWidget(self.flash_cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.recovery_guide_btn)
        task_lay.addLayout(btn_row)
        right_col.addWidget(task_card)

        log_card = make_card(12)
        log_lay = QVBoxLayout(log_card)
        log_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        log_lay.setSpacing(pt(12))
        hdr = QHBoxLayout()
        hdr.addWidget(make_label("日志", 14, C_TEXT, bold=True))
        hdr.addStretch()
        clear_btn = make_button("清空", small=True)
        clear_btn.clicked.connect(lambda: self.flash_log.clear())
        hdr.addWidget(clear_btn)
        log_lay.addLayout(hdr)
        self.flash_log = QTextEdit()
        self.flash_log.setReadOnly(True)
        self.flash_log.setMinimumHeight(200)
        log_lay.addWidget(self.flash_log)
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
        self.status_dot.setText("刷写中")
        self.status_dot.setStyleSheet(f"""
            color: {C_ORANGE};
            font-size: {pt(11)}pt;
            background: transparent;
            padding: 0;
        """)
        self.flash_log.clear()
        self._flash_log(f"[INFO] 开始：{product} / L4T {l4t}")

        self.flash_thread = FlashThread(product, l4t,
                                        self.skip_verify_cb.isChecked(),
                                        self.download_only_cb.isChecked())
        self.flash_thread.progress_msg.connect(self._on_flash_msg)
        self.flash_thread.progress_val.connect(self.flash_progress.setValue)
        self.flash_thread.finished.connect(self._on_flash_done)
        self.flash_thread.start()

    def _flash_log(self, text: str):
        from PyQt5.QtGui import QTextCursor
        self.flash_log.moveCursor(QTextCursor.End)
        self.flash_log.insertPlainText(text + "\n")
        self.flash_log.ensureCursorVisible()

    def _cancel_flash(self):
        if self.flash_thread:
            self.flash_thread.cancel()

    def _on_flash_msg(self, msg):
        self.flash_status_lbl.setText(msg)
        self._flash_log(f"[INFO] {msg}")

    def _on_flash_done(self, ok, msg):
        self.flash_run_btn.setVisible(True)
        self.flash_cancel_btn.setVisible(False)
        color = C_GREEN if ok else C_RED
        icon = "✓" if ok else "✗"
        self.flash_status_lbl.setText(f"{icon} {msg}")
        self.flash_status_lbl.setStyleSheet(f"color:{color}; background:transparent;")
        self._flash_log(f"[{'OK' if ok else 'ERR'}] {msg}")
        self.status_dot.setText("就绪")
        self.status_dot.setStyleSheet(f"""
            color: {C_GREEN};
            font-size: {pt(11)}pt;
            background: transparent;
            padding: 0;
        """)

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

        # Recovery 指南入口
        rec_card = make_card(12)
        rec_lay = QVBoxLayout(rec_card)
        rec_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
        rec_lay.setSpacing(pt(16))
        rec_lay.addWidget(make_label("Recovery 模式指南", 15, C_TEXT, bold=True))
        rec_lay.addWidget(make_label("按产品型号查看进入 Recovery 模式的详细步骤", 12, C_TEXT3))

        rec_combo = QComboBox()
        rec_combo.addItems(sorted(self.products.keys()))
        rec_lay.addWidget(rec_combo)

        rec_btn = make_button("查看指南", primary=True, small=True)
        rec_lay.addWidget(rec_btn)
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
        app.setFont(QFont(
            "Noto Sans CJK SC, PingFang SC, Microsoft YaHei, Segoe UI, sans-serif",
            base_pt,
        ))

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
