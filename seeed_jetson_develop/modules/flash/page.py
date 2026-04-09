"""烧录页 UI — 从 main_window_v2 迁移，独立模块化"""
import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QTextCursor, QDesktopServices
from PyQt5.QtWidgets import (
    QApplication, QBoxLayout, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from seeed_jetson_develop.core.events import bus
from seeed_jetson_develop.flash import JetsonFlasher, sudo_authenticate, sudo_check_cached
from seeed_jetson_develop.gui.flash_animation import FlashAnimationWidget
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_BLUE, C_CARD_LIGHT, C_GREEN, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3, make_button, make_card, make_label, pt,
)

log = logging.getLogger(__name__)

# 数据目录
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ── helpers ──────────────────────────────────────────────────────
def _page_header(title: str, subtitle: str) -> QWidget:
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
    return header


def _open_url(url: str):
    from PyQt5.QtCore import QUrl
    QDesktopServices.openUrl(QUrl(url))


def _load_flash_data():
    """加载 l4t_data / product_images，返回 (l4t_data, products, product_images)。"""
    l4t_data = []
    product_images = {}
    products = {}
    try:
        with open(_DATA_DIR / "l4t_data.json", encoding="utf-8") as f:
            l4t_data = json.load(f)
        for item in l4t_data:
            p = item["product"]
            products.setdefault(p, []).append(item["l4t"])
    except Exception:
        pass
    try:
        with open(_DATA_DIR / "product_images.json", encoding="utf-8") as f:
            product_images = json.load(f)
    except Exception:
        pass
    return l4t_data, products, product_images


# ═════════════════════════════════════════════════════════════════
#  build_page() — 闭包模式，返回 QWidget
# ═════════════════════════════════════════════════════════════════

def build_page() -> QWidget:
    """构建并返回烧录页 QWidget。内部自行加载数据。"""
    from .thread import FlashThread
    from seeed_jetson_develop.modules.remote.jetson_init import open_jetson_init_dialog

    # ── 加载数据 ──
    l4t_data, products, product_images = _load_flash_data()

    # ── 可变状态 ──
    _state = {
        "flash_thread": None,
        "flash_prepare_only": False,
        "flash_download_only": False,
        "flash_flash_only": False,
        "active_status_label": None,
        "active_progress": None,
    }

    # ── 自定义 QWidget，用于 resizeEvent 触发自适应 ──
    class _FlashPage(QWidget):
        def resizeEvent(self, event):
            super().resizeEvent(event)
            _update_adaptive_layout()

    page = _FlashPage()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    lay.addWidget(_page_header("烧录中心", "选择设备型号与系统版本，一键完成固件刷写"))

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    inner = QWidget()
    inner.setStyleSheet(f"background:{C_BG};")
    inner_lay = QVBoxLayout(inner)
    inner_lay.setContentsMargins(pt(32), pt(28), pt(32), pt(28))
    inner_lay.setSpacing(pt(24))

    # ── 步骤向导 ──
    wizard_card = make_card(12)
    wizard_outer = QVBoxLayout(wizard_card)
    wizard_outer.setContentsMargins(pt(32), pt(20), pt(32), pt(20))
    wizard_outer.setSpacing(0)

    step_configs = [("1", "选择设备"), ("2", "进入 Recovery"), ("3", "开始刷写"), ("4", "完成")]
    step_layout = QHBoxLayout()
    step_layout.setSpacing(0)

    _step_circles = []
    _step_labels = []

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
        _step_circles.append(circle)

        lbl = QLabel(txt)
        lbl.setStyleSheet(f"""
            color: {C_GREEN if is_active else C_TEXT3};
            font-size: {pt(11)}pt;
            font-weight: {'600' if is_active else '400'};
            background: transparent;
            padding-left: 8px;
        """)
        step_layout.addWidget(lbl)
        _step_labels.append(lbl)

        if i < 3:
            arrow = QLabel("\u203a")
            arrow.setStyleSheet(f"color:{C_TEXT3}; font-size:24px; background:transparent; padding:0 16px;")
            step_layout.addWidget(arrow)

    step_layout.addStretch()
    wizard_outer.addLayout(step_layout)
    inner_lay.addWidget(wizard_card)

    # ── 两列布局 ──
    flash_cols = QBoxLayout(QBoxLayout.LeftToRight)
    flash_cols.setSpacing(pt(24))

    # 左列 QStackedWidget
    flash_left_stack = QStackedWidget()
    flash_left_stack.setStyleSheet("background:transparent;")

    # ── 左侧页0：设备选择 ──
    left_page0 = QWidget()
    left_page0.setStyleSheet("background:transparent;")
    left_col = QVBoxLayout(left_page0)
    left_col.setContentsMargins(0, 0, 0, 0)
    left_col.setSpacing(pt(20))

    dev_card = make_card(12)
    dev_lay = QVBoxLayout(dev_card)
    dev_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    dev_lay.setSpacing(pt(16))

    dev_lay.addWidget(make_label("目标设备", 14, C_TEXT, bold=True))
    dev_lay.addWidget(make_label("选择产品型号和对应的 L4T 系统版本", 11, C_TEXT3))

    prod_row = QHBoxLayout()
    prod_row.addWidget(make_label("产品型号", 12, C_TEXT2))
    prod_row.addStretch()
    flash_product_combo = QComboBox()
    flash_product_combo.setMinimumWidth(260)
    flash_product_combo.addItems(sorted(products.keys()))
    prod_row.addWidget(flash_product_combo)
    dev_lay.addLayout(prod_row)

    l4t_row = QHBoxLayout()
    l4t_row.addWidget(make_label("L4T 版本", 12, C_TEXT2))
    l4t_row.addStretch()
    flash_l4t_combo = QComboBox()
    flash_l4t_combo.setMinimumWidth(260)
    l4t_row.addWidget(flash_l4t_combo)
    dev_lay.addLayout(l4t_row)

    # 设备图片
    flash_device_img = QLabel()
    flash_device_img.setFixedSize(320, 200)
    flash_device_img.setAlignment(Qt.AlignCenter)
    flash_device_img.setStyleSheet(f"""
        background: {C_CARD_LIGHT};
        border: none;
        border-radius: 10px;
        color: {C_TEXT3};
        font-size: {pt(11)}pt;
    """)
    flash_device_img.setText("暂无图片")
    dev_lay.addWidget(flash_device_img, alignment=Qt.AlignHCenter)

    # 信息展示
    flash_info = QLabel("等待选择产品...")
    flash_info.setWordWrap(True)
    flash_info.setTextFormat(Qt.RichText)
    flash_info.setTextInteractionFlags(Qt.TextBrowserInteraction)
    flash_info.setOpenExternalLinks(False)
    flash_info.linkActivated.connect(_open_url)
    flash_info.setStyleSheet(f"""
        background: {C_CARD_LIGHT};
        border: none;
        border-radius: 10px;
        color: {C_TEXT2};
        padding: {pt(14)}px;
        font-size: {pt(12)}pt;
        line-height: 1.6;
    """)
    dev_lay.addWidget(flash_info)

    flash_docs_row = QHBoxLayout()
    flash_docs_row.setSpacing(pt(10))

    flash_getting_started_btn = make_button("Getting Started", primary=True, small=True)
    flash_getting_started_btn.clicked.connect(
        lambda: _open_flash_doc(flash_getting_started_btn)
    )
    flash_docs_row.addWidget(flash_getting_started_btn)

    flash_hardware_btn = make_button("Hardware Interface", small=True)
    flash_hardware_btn.clicked.connect(
        lambda: _open_flash_doc(flash_hardware_btn)
    )
    flash_docs_row.addWidget(flash_hardware_btn)
    flash_docs_row.addStretch()
    dev_lay.addLayout(flash_docs_row)
    left_col.addWidget(dev_card)

    # 选项卡片
    opt_card = make_card(12)
    opt_lay = QVBoxLayout(opt_card)
    opt_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    opt_lay.setSpacing(pt(12))
    opt_lay.addWidget(make_label("执行选项", 14, C_TEXT, bold=True))
    skip_verify_cb = QCheckBox("跳过 SHA256 校验（不推荐）")
    opt_lay.addWidget(skip_verify_cb)
    left_col.addWidget(opt_card)
    left_col.addStretch()
    flash_left_stack.addWidget(left_page0)

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

    rec_guide_content = QWidget()
    rec_guide_content.setStyleSheet("background:transparent;")
    rec_guide_layout = QVBoxLayout(rec_guide_content)
    rec_guide_layout.setContentsMargins(0, 0, pt(8), 0)
    rec_guide_layout.setSpacing(pt(12))
    rec_guide_layout.addWidget(make_label("请先选择设备", 12, C_TEXT3))
    rec_guide_layout.addStretch()

    rec_guide_scroll.setWidget(rec_guide_content)
    rec_guide_outer.addWidget(rec_guide_scroll, 1)
    flash_left_stack.addWidget(rec_guide_card)

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
    hint_card.setStyleSheet("""
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
    hint_init_btn.clicked.connect(lambda: open_jetson_init_dialog(parent=page.window()))
    hint_btn_row.addWidget(hint_init_btn)
    hint_btn_row.addStretch()
    hint_lay.addLayout(hint_btn_row)
    guide_layout.addWidget(hint_card)

    next_steps = [
        ("\U0001f5a5", "设备管理", "查看 Jetson 状态、运行诊断、排查外设问题。"),
        ("\U0001f4e6", "应用市场", "安装常用 AI 应用、推理环境和开发工具。"),
        ("\U0001f9e0", "Skills", "用内置技能快速完成部署、修复和配置任务。"),
        ("\U0001f310", "远程开发", "建立 SSH 连接，继续用电脑远程操作设备。"),
        ("\U0001f4ac", "社区", "查看文档、论坛和常见问题，继续深入使用。"),
    ]
    for icon, title, desc in next_steps:
        item_card = QFrame()
        item_card.setStyleSheet(f"""
            background:{C_CARD_LIGHT};
            border:none;
            border-radius:10px;
        """)
        item_lay_h = QHBoxLayout(item_card)
        item_lay_h.setContentsMargins(pt(14), pt(12), pt(14), pt(12))
        item_lay_h.setSpacing(pt(12))

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(pt(28))
        icon_lbl.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        icon_lbl.setStyleSheet(f"background:transparent; font-size:{pt(16)}pt;")
        item_lay_h.addWidget(icon_lbl)

        text_col_v = QVBoxLayout()
        text_col_v.setSpacing(pt(4))
        text_col_v.addWidget(make_label(title, 12, C_TEXT, bold=True))
        text_col_v.addWidget(make_label(desc, 10, C_TEXT2, wrap=True))
        item_lay_h.addLayout(text_col_v, 1)
        guide_layout.addWidget(item_card)
    guide_layout.addStretch()

    guide_scroll.setWidget(guide_content)
    guide_outer.addWidget(guide_scroll, 1)
    flash_left_stack.addWidget(guide_card)

    flash_cols.addWidget(flash_left_stack, 1)

    # ── 右列 ──
    flash_right_panel = QWidget()
    flash_right_panel.setStyleSheet("background:transparent;")
    flash_right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    right_col = QVBoxLayout(flash_right_panel)
    right_col.setSpacing(pt(20))

    flash_step_stack = QStackedWidget()
    flash_step_stack.setStyleSheet("background:transparent;")

    # ── 步骤一：准备固件 ──
    step1_card = make_card(12)
    task_lay = QVBoxLayout(step1_card)
    task_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    task_lay.setSpacing(pt(16))
    task_lay.addWidget(make_label("步骤一：准备固件", 14, C_TEXT, bold=True))
    task_lay.addWidget(make_label("下载并解压 BSP 到本地，或使用已有缓存直接进入下一步", 11, C_TEXT3))

    flash_status_lbl = make_label("尚未开始", 14, C_TEXT2)
    task_lay.addWidget(flash_status_lbl)

    flash_progress = QProgressBar()
    flash_progress.setRange(0, 100)
    flash_progress.setValue(0)
    flash_progress.setFixedHeight(6)
    flash_progress.setVisible(False)
    task_lay.addWidget(flash_progress)

    flash_progress_detail_lbl = make_label("", 11, C_TEXT3)
    flash_progress_detail_lbl.setVisible(False)
    task_lay.addWidget(flash_progress_detail_lbl)

    flash_prepare_scene = FlashAnimationWidget()
    flash_prepare_scene.setFixedHeight(160)
    task_lay.addWidget(flash_prepare_scene)

    btn_row = QHBoxLayout()
    flash_cancel_btn = make_button("取消", danger=True)
    flash_cancel_btn.setVisible(False)
    flash_cancel_btn.clicked.connect(lambda: _cancel_flash())

    flash_download_btn = QPushButton("下载/解压 BSP")
    flash_download_btn.setCursor(Qt.PointingHandCursor)
    flash_download_btn.setToolTip("有压缩包则跳过下载直接解压；有解压目录则弹窗确认是否覆盖")
    flash_download_btn.setStyleSheet(f"""
        QPushButton {{
            background: {C_BLUE};
            border: none; border-radius: 8px;
            color: #FFFFFF; font-size: {pt(12)}pt; font-weight: 600;
            padding: 0 {pt(20)}px; min-height: {pt(42)}px;
        }}
        QPushButton:hover {{ background: #3D8EF0; }}
        QPushButton:pressed {{ background: #1A6ACC; }}
    """)
    flash_download_btn.clicked.connect(lambda: _on_prepare_bsp())

    flash_clear_btn = QPushButton("清除缓存")
    flash_clear_btn.setCursor(Qt.PointingHandCursor)
    flash_clear_btn.setToolTip("选择清除压缩包或解压目录")
    flash_clear_btn.setStyleSheet(f"""
        QPushButton {{
            background: rgba(245,166,35,0.15);
            border: none; border-radius: 8px;
            color: {C_ORANGE}; font-size: {pt(12)}pt; font-weight: 600;
            padding: 0 {pt(20)}px; min-height: {pt(42)}px;
        }}
        QPushButton:hover {{ background: rgba(245,166,35,0.25); }}
        QPushButton:pressed {{ background: rgba(245,166,35,0.35); }}
    """)
    flash_clear_btn.clicked.connect(lambda: _clear_firmware_cache())

    flash_next_btn = QPushButton("下一步 \u2192")
    flash_next_btn.setCursor(Qt.PointingHandCursor)
    flash_next_btn.setToolTip("已有解压目录，直接进入刷写步骤")
    flash_next_btn.setStyleSheet(f"""
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
    flash_next_btn.setEnabled(False)
    flash_next_btn.clicked.connect(lambda: _flash_go_next_step())

    btn_row.addWidget(flash_download_btn)
    btn_row.addWidget(flash_clear_btn)
    btn_row.addWidget(flash_cancel_btn)
    btn_row.addStretch()
    btn_row.addWidget(flash_next_btn)
    task_lay.addLayout(btn_row)

    flash_cache_lbl = make_label("", 11, C_TEXT3)
    task_lay.addWidget(flash_cache_lbl)
    flash_step_stack.addWidget(step1_card)

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

    rec_status_lbl = make_label("等待检测...", 13, C_TEXT2)
    rec_lay.addWidget(rec_status_lbl)

    rec_btn_row = QHBoxLayout()
    rec_back_btn = QPushButton("\u2190 返回")
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
    rec_back_btn.clicked.connect(lambda: _flash_go_step1())

    rec_detect_btn = QPushButton("检测设备")
    rec_detect_btn.setCursor(Qt.PointingHandCursor)
    rec_detect_btn.setStyleSheet(f"""
        QPushButton {{
            background: {C_BLUE};
            border: none; border-radius: 8px;
            color: #FFFFFF; font-size: {pt(12)}pt; font-weight: 600;
            padding: 0 {pt(20)}px; min-height: {pt(42)}px;
        }}
        QPushButton:hover {{ background: #3D8EF0; }}
        QPushButton:pressed {{ background: #1A6ACC; }}
    """)
    rec_detect_btn.clicked.connect(lambda: _detect_recovery())

    rec_flash_btn = QPushButton("开始刷写 \u2192")
    rec_flash_btn.setCursor(Qt.PointingHandCursor)
    rec_flash_btn.setEnabled(False)
    rec_flash_btn.setStyleSheet(f"""
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
    rec_flash_btn.clicked.connect(lambda: _start_flash())

    rec_btn_row.addWidget(rec_back_btn)
    rec_btn_row.addWidget(rec_detect_btn)
    rec_btn_row.addStretch()
    rec_btn_row.addWidget(rec_flash_btn)
    rec_lay.addLayout(rec_btn_row)
    flash_step_stack.addWidget(step2_card)

    # ── 步骤三：开始刷写 ──
    step3_card = make_card(12)
    run_lay = QVBoxLayout(step3_card)
    run_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    run_lay.setSpacing(pt(16))
    run_lay.addWidget(make_label("步骤三：开始刷写", 14, C_TEXT, bold=True))

    flash_run_status_lbl = make_label("准备开始刷写...", 13, C_TEXT2)
    run_lay.addWidget(flash_run_status_lbl)

    flash_run_progress = QProgressBar()
    flash_run_progress.setRange(0, 100)
    flash_run_progress.setValue(0)
    flash_run_progress.setFixedHeight(6)
    run_lay.addWidget(flash_run_progress)

    flash_scene = FlashAnimationWidget()
    flash_scene.setFixedHeight(160)
    run_lay.addWidget(flash_scene)

    run_btn_row = QHBoxLayout()
    flash_run_cancel_btn = make_button("取消", danger=True)
    flash_run_cancel_btn.clicked.connect(lambda: _cancel_flash())
    flash_run_retry_btn = make_button("重新烧录", primary=True)
    flash_run_retry_btn.setVisible(False)
    flash_run_retry_btn.clicked.connect(lambda: _retry_flash())
    flash_run_back_btn = make_button("返回 Recovery", small=False)
    flash_run_back_btn.setVisible(False)
    flash_run_back_btn.clicked.connect(lambda: _flash_go_next_step())
    run_btn_row.addWidget(flash_run_cancel_btn)
    run_btn_row.addStretch()
    run_btn_row.addWidget(flash_run_retry_btn)
    run_btn_row.addWidget(flash_run_back_btn)
    run_lay.addLayout(run_btn_row)
    flash_step_stack.addWidget(step3_card)

    # ── 步骤四：完成 ──
    step4_card = make_card(12)
    done_lay = QVBoxLayout(step4_card)
    done_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    done_lay.setSpacing(pt(16))
    done_lay.addWidget(make_label("步骤四：完成", 14, C_TEXT, bold=True))
    flash_done_status_lbl = make_label("刷写已完成。", 13, C_GREEN)
    done_lay.addWidget(flash_done_status_lbl)

    flash_done_scene = FlashAnimationWidget()
    flash_done_scene.setFixedHeight(160)
    flash_done_scene.set_mode("success")
    done_lay.addWidget(flash_done_scene)

    done_btn_row = QHBoxLayout()
    flash_done_init_btn = make_button("Jetson 初始化", primary=True)
    flash_done_init_btn.clicked.connect(lambda: open_jetson_init_dialog(parent=page.window()))
    flash_done_restart_btn = make_button("重新开始")
    flash_done_restart_btn.clicked.connect(lambda: _flash_reset_to_start())
    done_btn_row.addWidget(flash_done_init_btn)
    done_btn_row.addStretch()
    done_btn_row.addWidget(flash_done_restart_btn)
    done_lay.addLayout(done_btn_row)
    flash_step_stack.addWidget(step4_card)

    right_col.addWidget(flash_step_stack)

    # 日志卡片
    log_card = make_card(12)
    log_lay_inner = QVBoxLayout(log_card)
    log_lay_inner.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    log_lay_inner.setSpacing(pt(12))
    hdr = QHBoxLayout()
    hdr.addWidget(make_label("日志", 14, C_TEXT, bold=True))
    hdr.addStretch()
    save_btn = make_button("保存日志", small=True)
    save_btn.clicked.connect(lambda: _save_flash_log())
    hdr.addWidget(save_btn)
    clear_log_btn = make_button("清空", small=True)
    clear_log_btn.clicked.connect(lambda: flash_log.clear())
    hdr.addWidget(clear_log_btn)
    log_lay_inner.addLayout(hdr)
    flash_log = QTextEdit()
    flash_log.setReadOnly(True)
    flash_log.setMinimumHeight(200)
    log_lay_inner.addWidget(flash_log)
    right_col.addWidget(log_card, 1)

    flash_cols.addWidget(flash_right_panel, 1)
    flash_cols.setStretch(0, 1)
    flash_cols.setStretch(1, 1)
    flash_cols_host = QWidget()
    flash_cols_host.setStyleSheet("background:transparent;")
    flash_cols_host.setLayout(flash_cols)
    inner_lay.addWidget(flash_cols_host)
    inner_lay.addStretch()

    scroll.setWidget(inner)
    lay.addWidget(scroll, 1)

    # ═════════════════════════════════════════════
    #  闭包方法
    # ═════════════════════════════════════════════

    def _flash_log_append(text: str):
        flash_log.moveCursor(QTextCursor.End)
        flash_log.insertPlainText(text + "\n")
        flash_log.ensureCursorVisible()

    def _save_flash_log():
        text = flash_log.toPlainText().strip()
        if not text:
            _flash_log_append("[WARN] 当前没有可保存的日志")
            return
        default_name = f"seeed_flash_log_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        default_path = str(Path.home() / default_name)
        file_path, _ = QFileDialog.getSaveFileName(
            page.window(), "保存烧录日志", default_path,
            "Log Files (*.log);;Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return
        try:
            Path(file_path).write_text(text + "\n", encoding="utf-8")
            _flash_log_append(f"[OK] 日志已保存到 {file_path}")
        except Exception as exc:
            _flash_log_append(f"[ERR] 保存日志失败: {exc}")

    def _cancel_flash():
        if _state["flash_thread"]:
            _state["flash_thread"].cancel()

    def _update_adaptive_layout():
        width = flash_cols_host.width() or page.width()
        compact = width < 1180
        direction = QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight
        flash_cols.setDirection(direction)
        if compact:
            flash_device_img.setFixedSize(280, 176)
        else:
            flash_device_img.setFixedSize(320, 200)
        flash_log.setMinimumHeight(160 if compact else 200)

    def _set_flash_doc_button(button, url: str, tooltip: str):
        url = (url or "").strip()
        button.setProperty("doc_url", url)
        button.setEnabled(bool(url))
        button.setToolTip(url if url else tooltip)

    def _open_flash_doc(button):
        url = button.property("doc_url") or ""
        if url:
            _open_url(url)

    def _on_flash_product_changed(product):
        flash_l4t_combo.clear()
        if product in products:
            flash_l4t_combo.addItems(products[product])
        info = product_images.get(product, {})
        name = info.get("name", product)
        versions = len(products.get(product, []))
        getting_started = info.get("getting_started", "").strip()
        hardware_interfaces = info.get("hardware_interfaces", "").strip()
        flash_info.setText(
            f"型号：{name}<br>"
            f"可用版本：{versions} 个<br>"
            "文档快捷入口：使用下方按钮打开"
        )
        _set_flash_doc_button(flash_getting_started_btn, getting_started, "打开该产品的 Getting Started Wiki")
        _set_flash_doc_button(flash_hardware_btn, hardware_interfaces, "打开该产品的 Hardware Interface Wiki")
        # 加载设备图片
        local_img = info.get("local_image", "")
        img_path = _PROJECT_ROOT / local_img if local_img else None
        if img_path and img_path.exists():
            pix = QPixmap(str(img_path)).scaled(320, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            flash_device_img.setPixmap(pix)
            flash_device_img.setText("")
        else:
            flash_device_img.clear()
            flash_device_img.setText("暂无图片")
        _update_cache_label()

    def _update_cache_label():
        product = flash_product_combo.currentText()
        l4t = flash_l4t_combo.currentText()
        if not product or not l4t:
            return
        try:
            flasher = JetsonFlasher(product, l4t)
            has_archive = flasher.firmware_cached()
            has_extracted = flasher.firmware_extracted()
            if has_extracted:
                flash_cache_lbl.setText("已下载并解压，可直接刷写（跳过下载）")
                flash_cache_lbl.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(11)}pt; background:transparent;")
                flash_prepare_scene.set_mode("idle")
                flash_prepare_scene.set_download_progress(1.0)
                _set_next_enabled(True)
            elif has_archive:
                fp = flasher.download_dir / flasher.firmware_info['filename']
                size_mb = fp.stat().st_size / 1024 / 1024
                flash_cache_lbl.setText(f"已缓存压缩包 {size_mb:.0f} MB，刷写时将自动解压")
                flash_cache_lbl.setStyleSheet(f"color:{C_BLUE}; font-size:{pt(11)}pt; background:transparent;")
                if not flash_cancel_btn.isVisible():
                    flash_prepare_scene.set_mode("idle")
                    flash_prepare_scene.set_download_progress(0.0)
                _set_next_enabled(False)
            else:
                flash_cache_lbl.setText("无本地缓存，请先点击「下载/解压 BSP」")
                flash_cache_lbl.setStyleSheet(f"""
                    color: {C_ORANGE}; font-size: {pt(11)}pt;
                    background: rgba(245,166,35,0.10); border-radius: 6px; padding: 4px 10px;
                """)
                if not flash_cancel_btn.isVisible():
                    flash_prepare_scene.set_mode("idle")
                    flash_prepare_scene.set_download_progress(0.0)
                _set_next_enabled(False)
        except Exception:
            flash_cache_lbl.setText("")

    def _set_next_enabled(enabled: bool):
        flash_next_btn.setEnabled(enabled)
        if enabled:
            flash_prepare_scene.set_mode("idle")
            flash_prepare_scene.set_download_progress(1.0)
        elif not flash_cancel_btn.isVisible():
            flash_prepare_scene.set_mode("idle")
            flash_prepare_scene.set_download_progress(0.0)

    def _clear_firmware_cache():
        product = flash_product_combo.currentText()
        l4t = flash_l4t_combo.currentText()
        if not product or not l4t:
            return

        dlg = QDialog(page.window())
        dlg.setWindowTitle("清除缓存")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(f"background:{C_BG};")
        d_lay = QVBoxLayout(dlg)
        d_lay.setSpacing(12)
        d_lay.setContentsMargins(20, 20, 20, 20)
        d_lay.addWidget(make_label("选择要清除的内容：", 13, C_TEXT))
        d_lay.addWidget(make_label("可只清除压缩包，或只清理解压后的工作目录。", 10, C_TEXT3))

        checkbox_style = f"""
            QCheckBox {{ color: {C_TEXT2}; font-size: {pt(12)}pt; spacing: 0px; padding: 10px 14px;
                background: transparent; border-radius: 10px; }}
            QCheckBox:hover {{ background: rgba(255,255,255,0.04); }}
            QCheckBox::indicator {{ width: 0px; height: 0px; }}
        """
        archive_label = "  压缩包缓存（.tar.gz / .tar）"
        extracted_label = "  解压目录（工作目录）"
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
                + (f"QCheckBox {{ color: {C_TEXT}; font-size: {pt(12)}pt; spacing: 0px; padding: 10px 14px; "
                   f"background: rgba(255,255,255,0.05); border-radius: 10px; font-weight: 600; }}"
                   f"QCheckBox:hover {{ background: rgba(255,255,255,0.08); }}"
                   f"QCheckBox::indicator {{ width: 0px; height: 0px; }}"
                   if box.isChecked() else "")
            )

        cb_archive.stateChanged.connect(lambda _s: _sync_checkbox_text(cb_archive, archive_label))
        cb_extracted.stateChanged.connect(lambda _s: _sync_checkbox_text(cb_extracted, extracted_label))
        _sync_checkbox_text(cb_archive, archive_label)
        _sync_checkbox_text(cb_extracted, extracted_label)
        d_lay.addWidget(cb_archive)
        d_lay.addWidget(cb_extracted)

        d_btn_row = QHBoxLayout()
        d_btn_row.setSpacing(10)
        d_btn_row.addStretch()
        cancel_btn_d = make_button("取消")
        ok_btn = make_button("确认清除", primary=True)
        cancel_btn_d.clicked.connect(dlg.reject)
        ok_btn.clicked.connect(dlg.accept)
        d_btn_row.addWidget(cancel_btn_d)
        d_btn_row.addWidget(ok_btn)
        d_lay.addLayout(d_btn_row)

        if dlg.exec_() != QDialog.Accepted:
            return
        try:
            flasher = JetsonFlasher(product, l4t)
            removed = flasher.clear_cache(clear_archive=cb_archive.isChecked(), clear_extracted=cb_extracted.isChecked())
            if removed:
                _flash_log_append("[INFO] 已清除:\n" + "\n".join(f"  {p}" for p in removed))
            else:
                _flash_log_append("[INFO] 无缓存可清除")
        except Exception as e:
            _flash_log_append(f"[ERR] 清除缓存失败: {e}")
        _update_cache_label()
        _set_next_enabled(False)

    def _ensure_sudo() -> bool:
        import getpass as _getpass
        if sudo_check_cached():
            return True
        dlg = QDialog(page.window())
        dlg.setWindowTitle("需要本机管理员权限")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet(f"background:{C_BG};")
        d_lay = QVBoxLayout(dlg)
        d_lay.setSpacing(12)
        d_lay.setContentsMargins(20, 20, 20, 20)
        d_lay.addWidget(make_label("解压和烧录固件需要 sudo 权限。", 13, C_TEXT))
        try:
            username = _getpass.getuser()
        except Exception:
            username = "当前用户"
        hint_lbl = QLabel(f"  本机（PC）sudo 密码  ·  用户：{username}")
        hint_lbl.setStyleSheet(f"""
            color: {C_BLUE}; background: rgba(41,121,255,0.10);
            border-radius: 6px; padding: 6px 10px; font-size: {pt(11)}pt;
        """)
        d_lay.addWidget(hint_lbl)
        pwd_input = QLineEdit()
        pwd_input.setEchoMode(QLineEdit.Password)
        pwd_input.setPlaceholderText("输入本机密码...")
        pwd_input.setStyleSheet(f"""
            QLineEdit {{ background: {C_CARD_LIGHT}; border: none; border-radius: 8px;
                color: {C_TEXT}; padding: 8px 12px; font-size: {pt(12)}pt; }}
        """)
        d_lay.addWidget(pwd_input)
        err_lbl = make_label("", 11, C_RED)
        d_lay.addWidget(err_lbl)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        d_lay.addWidget(btns)
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

    def _on_prepare_bsp():
        if not _ensure_sudo():
            _flash_log_append("[WARN] 未获得 sudo 权限，操作取消")
            return
        product = flash_product_combo.currentText()
        l4t = flash_l4t_combo.currentText()
        if not product or not l4t:
            return
        try:
            flasher = JetsonFlasher(product, l4t)
            has_extracted = flasher.firmware_extracted()
            has_archive = flasher.firmware_cached()
        except Exception as e:
            _flash_log_append(f"[ERR] {e}")
            return

        if has_extracted:
            msg = QMessageBox(page.window())
            msg.setWindowTitle("已有解压目录")
            msg.setText("检测到本地已有解压好的固件目录。\n是否覆盖重新下载并解压？")
            msg.setInformativeText("选择「跳过」可直接使用现有目录进入下一步。")
            skip_btn = msg.addButton("跳过，直接下一步", QMessageBox.AcceptRole)
            overwrite_btn = msg.addButton("覆盖重新下载解压", QMessageBox.DestructiveRole)
            msg.addButton("取消", QMessageBox.RejectRole)
            msg.exec_()
            clicked = msg.clickedButton()
            if clicked is skip_btn:
                _flash_log_append("[INFO] 使用现有解压目录，跳过下载解压")
                _set_next_enabled(True)
                return
            elif clicked is overwrite_btn:
                _run_flash_thread(product, l4t, force_redownload=True, prepare_only=True)
        elif has_archive:
            _flash_log_append("[INFO] 压缩包已存在，跳过下载，直接解压")
            _run_flash_thread(product, l4t, force_redownload=False, prepare_only=True)
        else:
            _run_flash_thread(product, l4t, force_redownload=False, prepare_only=True)

    def _set_wizard_step(active_idx: int):
        for i, (circle, lbl) in enumerate(zip(_step_circles, _step_labels)):
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

    def _flash_go_next_step():
        _set_wizard_step(1)
        flash_step_stack.setCurrentIndex(1)
        flash_left_stack.setCurrentIndex(1)
        _build_recovery_guide(flash_product_combo.currentText())
        rec_status_lbl.setText("等待检测...")
        rec_status_lbl.setStyleSheet(f"color:{C_TEXT2}; background:transparent;")
        rec_flash_btn.setEnabled(False)
        flash_scene.set_mode("idle")
        flash_scene.set_download_progress(0.0)
        flash_prepare_scene.set_mode("idle")
        flash_prepare_scene.set_download_progress(1.0 if flash_next_btn.isEnabled() else 0.0)
        flash_run_back_btn.setVisible(False)

    def _flash_go_step1():
        _set_wizard_step(0)
        flash_step_stack.setCurrentIndex(0)
        flash_left_stack.setCurrentIndex(0)
        flash_scene.set_mode("idle")
        flash_scene.set_download_progress(0.0)
        flash_prepare_scene.set_mode("idle")
        flash_prepare_scene.set_download_progress(1.0 if flash_next_btn.isEnabled() else 0.0)
        flash_run_back_btn.setVisible(False)

    def _flash_reset_to_start():
        _set_wizard_step(0)
        flash_step_stack.setCurrentIndex(0)
        flash_left_stack.setCurrentIndex(0)
        flash_status_lbl.setText("尚未开始")
        flash_status_lbl.setStyleSheet(f"color:{C_TEXT2}; background:transparent;")
        flash_run_status_lbl.setText("准备开始刷写...")
        flash_run_status_lbl.setStyleSheet(f"color:{C_TEXT2}; background:transparent;")
        flash_progress.setVisible(False)
        flash_progress.setValue(0)
        flash_progress_detail_lbl.clear()
        flash_progress_detail_lbl.setVisible(False)
        flash_run_progress.setValue(0)
        flash_prepare_scene.set_mode("idle")
        flash_prepare_scene.set_download_progress(0.0)
        flash_scene.set_mode("idle")
        flash_scene.set_download_progress(0.0)
        flash_done_scene.set_mode("success")
        flash_done_scene.set_download_progress(1.0)
        flash_run_back_btn.setVisible(False)

    def _build_recovery_guide(product: str):
        from seeed_jetson_develop.data.recovery_guides import get_guide
        while rec_guide_layout.count():
            item = rec_guide_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        guide = get_guide(product)
        if not guide:
            rec_guide_layout.addWidget(make_label("暂无该设备的 Recovery 指南", 12, C_TEXT3))
            rec_guide_layout.addStretch()
            return
        title_lbl = make_label(guide["title"], 13, C_TEXT, bold=True)
        title_lbl.setWordWrap(True)
        rec_guide_layout.addWidget(title_lbl)
        rec_guide_layout.addWidget(make_label(f"所需线缆：{guide['cable']}", 11, C_TEXT2))
        if guide.get("image_url") or guide.get("local_image"):
            img_lbl = QLabel()
            img_lbl.setAlignment(Qt.AlignCenter)
            img_lbl.setFixedHeight(280)
            img_lbl.setText("图片加载中...")
            img_lbl.setStyleSheet(f"color:{C_TEXT3}; background:{C_CARD_LIGHT}; border-radius:8px; font-size:{pt(10)}pt;")
            rec_guide_layout.addWidget(img_lbl)
            _load_guide_image(guide.get("image_url", ""), img_lbl, guide.get("local_image", ""), guide["title"])
        rec_guide_layout.addWidget(make_label("操作步骤：", 12, C_TEXT, bold=True))
        for i, step in enumerate(guide["steps"], 1):
            row = QHBoxLayout()
            row.setSpacing(pt(8))
            num = QLabel(str(i))
            num.setFixedSize(pt(22), pt(22))
            num.setAlignment(Qt.AlignCenter)
            num.setStyleSheet(f"background: {C_BLUE}; color: #fff; border-radius: {pt(11)}px; font-size: {pt(10)}pt; font-weight: 700;")
            step_lbl = QLabel(step)
            step_lbl.setWordWrap(True)
            step_lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:{pt(11)}pt; background:transparent;")
            row.addWidget(num, alignment=Qt.AlignTop)
            row.addWidget(step_lbl, 1)
            container = QWidget()
            container.setStyleSheet("background:transparent;")
            container.setLayout(row)
            rec_guide_layout.addWidget(container)
        rec_guide_layout.addWidget(make_label("Recovery 模式 USB ID：", 12, C_TEXT, bold=True))
        for name, uid in guide["usb_ids"]:
            id_lbl = QLabel(f"  {name}：{uid}")
            id_lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:{pt(11)}pt; font-family:monospace; background:transparent;")
            rec_guide_layout.addWidget(id_lbl)
        if guide.get("note"):
            note_lbl = QLabel(guide["note"])
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet(f"color: {C_ORANGE}; background: rgba(245,166,35,0.10); border-radius: 6px; padding: 8px 10px; font-size: {pt(11)}pt;")
            rec_guide_layout.addWidget(note_lbl)
        rec_guide_layout.addStretch()

    def _set_guide_image_preview(label: QLabel, pix: QPixmap, title: str):
        target_w = label.width() - 16 if label.width() > 16 else 560
        target_h = label.height() - 8 if label.height() > 8 else 272
        preview = pix.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(preview)
        label.setStyleSheet(f"background:{C_CARD_LIGHT}; border-radius:8px; padding:4px;")
        label.setText("")
        label.setCursor(Qt.PointingHandCursor)
        label.setToolTip("点击查看大图")
        label.mousePressEvent = lambda _event, p=pix, t=title: _show_guide_image_dialog(p, t)

    def _show_guide_image_dialog(pix: QPixmap, title: str):
        dlg = QDialog(page.window())
        dlg.setWindowTitle(title)
        dlg.setMinimumSize(980, 760)
        dlg.setStyleSheet(f"background:{C_BG};")
        root = QVBoxLayout(dlg)
        root.setContentsMargins(pt(20), pt(20), pt(20), pt(20))
        root.setSpacing(pt(12))
        root.addWidget(make_label(title, 14, C_TEXT, bold=True))
        d_scroll = QScrollArea()
        d_scroll.setWidgetResizable(False)
        d_scroll.setStyleSheet("background:transparent; border:none;")
        d_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        d_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        image = QLabel()
        image.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        image.setStyleSheet(f"background:{C_CARD_LIGHT}; border-radius:10px;")
        image.setCursor(Qt.OpenHandCursor)
        drag_state = {"active": False, "pos": None}
        zoom_state = {"scale": 1.0, "min": 0.2, "max": 6.0}

        def apply_scale(new_scale, anchor_pos=None):
            new_scale = max(zoom_state["min"], min(zoom_state["max"], new_scale))
            if abs(new_scale - zoom_state["scale"]) < 1e-4:
                return
            hbar, vbar = d_scroll.horizontalScrollBar(), d_scroll.verticalScrollBar()
            if anchor_pos is not None:
                ratio_x = (hbar.value() + anchor_pos.x()) / max(1, image.width())
                ratio_y = (vbar.value() + anchor_pos.y()) / max(1, image.height())
            else:
                ratio_x = ratio_y = 0.5
            zoom_state["scale"] = new_scale
            scaled = pix.scaled(max(1, int(pix.width() * new_scale)), max(1, int(pix.height() * new_scale)),
                                Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            image.setPixmap(scaled)
            image.resize(scaled.size())
            image.setMinimumSize(scaled.size())
            if anchor_pos is not None:
                hbar.setValue(int(image.width() * ratio_x - anchor_pos.x()))
                vbar.setValue(int(image.height() * ratio_y - anchor_pos.y()))

        def fit_initial():
            vp = d_scroll.viewport().size()
            if vp.width() <= 0 or vp.height() <= 0:
                return
            fit_scale = min(vp.width() / max(1, pix.width()), vp.height() / max(1, pix.height()), 1.0)
            zoom_state["scale"] = 1.0
            apply_scale(fit_scale)

        image.mousePressEvent = lambda e: (drag_state.update(active=True, pos=e.globalPos()), image.setCursor(Qt.ClosedHandCursor), e.accept()) if e.button() == Qt.LeftButton else None
        image.mouseMoveEvent = lambda e: (
            (lambda d: (drag_state.update(pos=e.globalPos()), d_scroll.horizontalScrollBar().setValue(d_scroll.horizontalScrollBar().value() - d.x()), d_scroll.verticalScrollBar().setValue(d_scroll.verticalScrollBar().value() - d.y())))(e.globalPos() - drag_state["pos"])
            if drag_state["active"] and drag_state["pos"] else None
        )
        image.mouseReleaseEvent = lambda e: (drag_state.update(active=False, pos=None), image.setCursor(Qt.OpenHandCursor), e.accept()) if e.button() == Qt.LeftButton else None

        def on_wheel(event):
            delta = event.angleDelta().y()
            if not delta:
                event.ignore()
                return
            apply_scale(zoom_state["scale"] * (1.15 if delta > 0 else 1 / 1.15), event.pos())
            event.accept()
        d_scroll.wheelEvent = on_wheel

        d_scroll.setWidget(image)
        root.addWidget(d_scroll, 1)
        QTimer.singleShot(0, fit_initial)
        root.addWidget(make_label("滚轮可缩放图片，按住鼠标左键可拖动查看指定位置。", 10, C_TEXT3))
        close_btn = make_button("关闭")
        close_btn.clicked.connect(dlg.accept)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(close_btn)
        root.addLayout(close_row)
        dlg.exec_()

    def _load_guide_image(url: str, label: QLabel, local_image: str = "", title: str = "Recovery 指南图片"):
        local_path = _PROJECT_ROOT / local_image if local_image else None
        if local_path and local_path.exists():
            pix = QPixmap(str(local_path))
            if not pix.isNull():
                _set_guide_image_preview(label, pix, title)
                return

        def fetch():
            try:
                import requests as _req
                resp = _req.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.content
                def update():
                    p = QPixmap()
                    p.loadFromData(data)
                    if not p.isNull():
                        _set_guide_image_preview(label, p, title)
                    else:
                        label.setText("图片加载失败")
                QTimer.singleShot(0, update)
            except Exception:
                QTimer.singleShot(0, lambda: (
                    label.setText("图片加载失败"),
                    label.setStyleSheet(f"color:{C_TEXT3}; background:{C_CARD_LIGHT}; border-radius:8px; font-size:{pt(10)}pt;")
                ))
        threading.Thread(target=fetch, daemon=True).start()

    def _detect_recovery():
        import subprocess
        NVIDIA_APX_IDS = {"7023", "7223", "7323", "7423", "7523", "7623"}
        try:
            result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
            found = False
            for line in result.stdout.splitlines():
                if "0955:" in line.lower() or "nvidia" in line.lower():
                    parts = line.split("ID ")
                    if len(parts) > 1:
                        pid = parts[1].split()[0].split(":")[-1].lower()
                        if pid in NVIDIA_APX_IDS:
                            found = True
                            _flash_log_append(f"[INFO] 检测到 Recovery 设备: {line.strip()}")
                            break
            if found:
                rec_status_lbl.setText("已检测到 Jetson Recovery 设备，可以开始刷写")
                rec_status_lbl.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
                rec_flash_btn.setEnabled(True)
            else:
                rec_status_lbl.setText("未检测到 Recovery 设备，请检查连接和 Recovery 模式")
                rec_status_lbl.setStyleSheet(f"color:{C_ORANGE}; background:transparent;")
                rec_flash_btn.setEnabled(False)
                _flash_log_append("[WARN] lsusb 未找到 NVIDIA APX 设备")
        except Exception as e:
            rec_status_lbl.setText(f"检测失败: {e}")
            rec_status_lbl.setStyleSheet(f"color:{C_RED}; background:transparent;")
            _flash_log_append(f"[ERR] lsusb 执行失败: {e}")

    def _start_flash():
        product = flash_product_combo.currentText()
        l4t = flash_l4t_combo.currentText()
        if not product or not l4t:
            return
        if not _ensure_sudo():
            _flash_log_append("[WARN] 未获得 sudo 权限，烧录取消")
            return
        _run_flash_thread(product, l4t, flash_only=True)

    def _retry_flash():
        product = flash_product_combo.currentText()
        l4t = flash_l4t_combo.currentText()
        if not product or not l4t:
            return
        _flash_log_append("[INFO] 用户请求重新烧录，正在重试当前设备与版本")
        if not _ensure_sudo():
            _flash_log_append("[WARN] 未获得 sudo 权限，重新烧录取消")
            return
        _run_flash_thread(product, l4t, flash_only=True)

    def _run_flash_thread(product, l4t, force_redownload=False,
                          download_only=False, prepare_only=False, flash_only=False):
        is_actual_flash = flash_only or (not prepare_only and not download_only)
        flash_download_btn.setVisible(False)
        flash_clear_btn.setVisible(False)
        flash_cancel_btn.setVisible(True)
        flash_next_btn.setEnabled(False)
        flash_progress.setVisible(True)
        flash_progress.setValue(0)
        flash_progress_detail_lbl.clear()
        flash_progress_detail_lbl.setVisible(not is_actual_flash)
        bus.status_busy.emit("处理中")
        if not flash_only:
            flash_log.clear()
        _flash_log_append(f"[INFO] 开始：{product} / L4T {l4t}"
                          + (" [强制重下]" if force_redownload else "")
                          + (" [仅刷写]" if flash_only else ""))
        _state["flash_prepare_only"] = prepare_only
        _state["flash_download_only"] = download_only
        _state["flash_flash_only"] = flash_only
        _state["active_status_label"] = flash_run_status_lbl if is_actual_flash else flash_status_lbl
        _state["active_progress"] = flash_run_progress if is_actual_flash else flash_progress
        _state["active_progress"].setValue(0)
        _state["active_status_label"].setStyleSheet(f"color:{C_GREEN if is_actual_flash else C_TEXT2}; background:transparent;")
        if is_actual_flash:
            _set_wizard_step(2)
            flash_step_stack.setCurrentIndex(2)
            flash_left_stack.setCurrentIndex(1)
            flash_run_cancel_btn.setVisible(True)
            flash_run_retry_btn.setVisible(False)
            flash_run_back_btn.setVisible(False)
            flash_scene.set_mode("flashing")
            flash_scene.set_download_progress(0.0)
        else:
            flash_scene.set_mode("idle")
            flash_scene.set_download_progress(0.0)
        flash_prepare_scene.set_mode("downloading" if not is_actual_flash else "idle")
        flash_prepare_scene.set_download_progress(0.0 if not is_actual_flash else 1.0)
        bus.flash_started.emit(product, l4t)
        thread = FlashThread(product, l4t, skip_verify_cb.isChecked(), download_only,
                             force_redownload=force_redownload, prepare_only=prepare_only, flash_only=flash_only)
        thread.progress_msg.connect(_on_flash_msg)
        thread.progress_val.connect(_on_flash_progress)
        thread.progress_log.connect(_flash_log_append)
        thread.download_progress.connect(_on_download_progress)
        thread.finished.connect(_on_flash_done)
        _state["flash_thread"] = thread
        thread.start()

    def _on_flash_msg(msg):
        _state["active_status_label"].setText(msg)
        _flash_log_append(f"[INFO] {msg}")
        if flash_step_stack.currentIndex() == 0 and not any(k in msg for k in ("下载", "下载固件")):
            flash_progress_detail_lbl.clear()
            flash_progress_detail_lbl.setVisible(False)
        if "跳过下载" in msg or "校验" in msg or "解压" in msg or "刷写" in msg:
            bar = _state["active_progress"]
            if bar.maximum() == 0:
                bar.setRange(0, 100)
        if flash_step_stack.currentIndex() == 0:
            if any(k in msg for k in ("解压", "跳过下载", "下载", "校验", "初始化")):
                flash_prepare_scene.set_mode("downloading")
            elif "完成" in msg:
                flash_prepare_scene.set_mode("idle")

    def _on_flash_progress(value):
        _state["active_progress"].setValue(value)
        if flash_step_stack.currentIndex() == 0:
            flash_prepare_scene.set_download_progress(value / 100)
        if flash_step_stack.currentIndex() == 2:
            flash_scene.set_download_progress(value / 100)

    def _on_download_progress(downloaded: int, total: int):
        bar = _state["active_progress"]
        def _fmt(b):
            if b >= 1024 ** 3: return f"{b / 1024 ** 3:.1f} GB"
            if b >= 1024 ** 2: return f"{b / 1024 ** 2:.0f} MB"
            return f"{b / 1024:.0f} KB"
        if total > 0:
            pct = int(downloaded / total * 100)
            bar.setRange(0, 100)
            bar.setValue(pct)
            label_text = f"下载固件中... {_fmt(downloaded)} / {_fmt(total)}  ({pct}%)"
            detail_text = f"BSP 下载进度：已下载 {_fmt(downloaded)}，总大小 {_fmt(total)}，完成 {pct}%"
            if flash_step_stack.currentIndex() == 0:
                flash_prepare_scene.set_download_progress(pct / 100)
        else:
            bar.setRange(0, 0)
            label_text = f"下载固件中... {_fmt(downloaded)}"
            detail_text = f"BSP 下载进度：已下载 {_fmt(downloaded)}，正在获取总大小..."
        _state["active_status_label"].setText(label_text)
        if flash_step_stack.currentIndex() == 0:
            flash_progress_detail_lbl.setText(detail_text)
            flash_progress_detail_lbl.setVisible(True)

    def _on_flash_done(ok, msg):
        was_prepare_only = _state["flash_prepare_only"]
        was_download_only = _state["flash_download_only"]
        was_flash_only = _state["flash_flash_only"]
        was_actual_flash = was_flash_only or (not was_prepare_only and not was_download_only)
        flash_download_btn.setVisible(True)
        flash_clear_btn.setVisible(True)
        flash_cancel_btn.setVisible(False)
        flash_run_cancel_btn.setVisible(False)
        flash_run_retry_btn.setVisible(False)
        flash_progress_detail_lbl.clear()
        flash_progress_detail_lbl.setVisible(False)
        color = C_GREEN if ok else C_RED
        icon = "\u2713" if ok else "\u2717"
        _state["active_progress"].setRange(0, 100)
        _state["active_progress"].setValue(100 if ok else max(5, _state["active_progress"].value()))
        _state["active_status_label"].setText(f"{icon} {msg}")
        _state["active_status_label"].setStyleSheet(f"color:{color}; background:transparent;")
        _flash_log_append(f"[{'OK' if ok else 'ERR'}] {msg}")
        bus.status_idle.emit("就绪")
        _update_cache_label()

        if was_actual_flash:
            flash_scene.set_mode("success" if ok else "error")
            flash_scene.set_download_progress(1.0 if ok else _state["active_progress"].value() / 100)
        else:
            flash_scene.set_mode("idle")
            flash_scene.set_download_progress(0.0)
        if not was_actual_flash:
            flash_prepare_scene.set_mode("idle" if ok else "error")
            flash_prepare_scene.set_download_progress(1.0 if ok else _state["active_progress"].value() / 100)
        flash_done_scene.set_mode("success" if ok else "error")
        flash_done_scene.set_download_progress(1.0 if ok else _state["active_progress"].value() / 100)

        if was_actual_flash and ok:
            _set_wizard_step(3)
            flash_done_status_lbl.setText(f"\u2713 {msg}")
            flash_done_status_lbl.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
            flash_step_stack.setCurrentIndex(3)
            flash_left_stack.setCurrentIndex(2)
        elif was_actual_flash and not ok:
            flash_step_stack.setCurrentIndex(2)
            flash_left_stack.setCurrentIndex(1)
            flash_run_retry_btn.setVisible(True)
            flash_run_back_btn.setVisible(True)
        if ok and not was_flash_only:
            try:
                flasher = JetsonFlasher(flash_product_combo.currentText(), flash_l4t_combo.currentText())
                _set_next_enabled(flasher.firmware_extracted())
            except Exception:
                pass
        _update_cache_label()
        bus.flash_completed.emit(ok, msg)

    # ── 信号连接 ──
    flash_product_combo.currentTextChanged.connect(_on_flash_product_changed)
    flash_l4t_combo.currentTextChanged.connect(lambda _: _update_cache_label())

    # ── 初始化 ──
    if flash_product_combo.currentText():
        _on_flash_product_changed(flash_product_combo.currentText())
    QTimer.singleShot(0, _update_adaptive_layout)

    return page
