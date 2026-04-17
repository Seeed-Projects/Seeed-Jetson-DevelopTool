"""Flash page UI."""
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
from seeed_jetson_develop.gui.i18n_binding import I18nBinding
from seeed_jetson_develop.gui.i18n import get_language, t
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_BLUE, C_CARD_LIGHT, C_GREEN, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3, make_button, make_card, make_label, pt, PLATFORM,
    DropdownButton,
)

log = logging.getLogger(__name__)

# Data directories
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
FLASH_FORCE_TWO_COLUMNS = True


# ── helpers ──────────────────────────────────────────────────────
def _page_header(title: str, subtitle: str) -> tuple[QWidget, QLabel, QLabel]:
    header = QWidget()
    header.setFixedHeight(pt(64))
    header.setStyleSheet(f"background: {C_BG_DEEP};")
    lay = QHBoxLayout(header)
    lay.setContentsMargins(pt(28), pt(10), pt(28), pt(10))
    lay.setSpacing(0)

    text_col = QVBoxLayout()
    text_col.setSpacing(4)
    text_col.setContentsMargins(0, 0, 0, 0)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(
        f"color:{C_TEXT}; font-size:{pt(18)}px; font-weight:700;"
        " background:transparent; border:none; text-decoration:none;"
    )
    text_col.addWidget(title_lbl)
    sub_lbl = QLabel(subtitle)
    sub_lbl.setStyleSheet(
        f"color:{C_TEXT3}; font-size:{pt(12)}px;"
        " background:transparent; border:none; text-decoration:none;"
    )
    text_col.addWidget(sub_lbl)
    lay.addLayout(text_col)
    lay.addStretch()
    return header, title_lbl, sub_lbl


def _open_url(url: str):
    from PyQt5.QtCore import QUrl
    QDesktopServices.openUrl(QUrl(url))


def _load_flash_data():
    """Load l4t_data and product_images."""
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


_FLASH_LANG_OVERRIDE: str | None = None


def _flash_lang() -> str:
    return _FLASH_LANG_OVERRIDE or get_language()


def _flash_info_html(name: str, versions: int) -> str:
    lang = _flash_lang()
    from seeed_jetson_develop.gui.theme import C_CARD_LIGHT, C_TEXT2
    return (
        f'<html><body style="background:{C_CARD_LIGHT}; color:{C_TEXT2}; margin:0; padding:0;">'
        f"{t('flash.product_summary.model', lang=lang, name=name)}<br>"
        f"{t('flash.product_summary.versions', lang=lang, count=versions)}<br>"
        f"{t('flash.product_summary.docs_shortcut', lang=lang)}"
        f"</body></html>"
    )


def _ft(key: str, **kwargs) -> str:
    return t(key, lang=_flash_lang(), **kwargs)


# ═════════════════════════════════════════════════════════════════
# build_page() returns QWidget
# ═════════════════════════════════════════════════════════════════

def build_page() -> QWidget:
    """Build and return flash page QWidget."""
    from .thread import FlashThread
    from seeed_jetson_develop.modules.remote.jetson_init import open_jetson_init_dialog

    # Load data
    l4t_data, products, product_images = _load_flash_data()

    # Mutable state
    _state = {
        "flash_thread": None,
        "flash_prepare_only": False,
        "flash_download_only": False,
        "flash_flash_only": False,
        "lang": _flash_lang(),
        "active_status_label": None,
        "active_progress": None,
    }

    # Custom QWidget for adaptive resize behavior.
    class _FlashPage(QWidget):
        def resizeEvent(self, event):
            super().resizeEvent(event)
            _update_adaptive_layout()

    page = _FlashPage()
    page.i18n = I18nBinding()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    header_widget, header_title_lbl, header_sub_lbl = _page_header(
        _ft("flash.page.title"),
        _ft("flash.page.subtitle"),
    )
    lay.addWidget(header_widget)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    inner = QWidget()
    inner.setStyleSheet(f"background:{C_BG};")
    inner_lay = QVBoxLayout(inner)
    inner_lay.setContentsMargins(pt(28), pt(24), pt(28), pt(24))
    inner_lay.setSpacing(pt(24))

    # Step wizard
    wizard_card = make_card(12)
    wizard_outer = QVBoxLayout(wizard_card)
    wizard_outer.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    wizard_outer.setSpacing(0)

    step_key_order = [
        "flash.wizard.step.select_device",
        "flash.wizard.step.enter_recovery",
        "flash.wizard.step.start_flash",
        "flash.wizard.step.done",
    ]
    step_configs = [(str(i + 1), _ft(k)) for i, k in enumerate(step_key_order)]
    step_layout = QHBoxLayout()
    step_layout.setSpacing(pt(10))

    _step_circles = []
    _step_labels = []
    _step_arrows = []

    def _apply_step_style(circle: QLabel, lbl: QLabel, state: str):
        if state == "active":
            circle.setStyleSheet(f"""
                background: {C_GREEN};
                color: #071200;
                border: none;
                border-radius: {pt(18)}px;
                font-weight: 700;
                font-size: {pt(13)}pt;
            """)
            lbl.setStyleSheet(
                f"color:{C_GREEN}; font-size:{pt(12)}pt; font-weight:700;"
                " background:transparent; border:none;"
            )
        elif state == "done":
            circle.setStyleSheet(f"""
                background: rgba(122,179,23,0.24);
                color: {C_GREEN};
                border: 1px solid rgba(122,179,23,0.28);
                border-radius: {pt(18)}px;
                font-weight: 700;
                font-size: {pt(13)}pt;
            """)
            lbl.setStyleSheet(
                f"color:{C_TEXT2}; font-size:{pt(12)}pt; font-weight:500;"
                " background:transparent; border:none;"
            )
        else:
            circle.setStyleSheet(f"""
                background: transparent;
                color: {C_TEXT3};
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: {pt(18)}px;
                font-weight: 700;
                font-size: {pt(13)}pt;
            """)
            lbl.setStyleSheet(
                f"color:{C_TEXT3}; font-size:{pt(12)}pt; font-weight:500;"
                " background:transparent; border:none;"
            )

    for i, (num, txt) in enumerate(step_configs):
        step_item = QWidget()
        step_item.setStyleSheet("background:transparent; border:none;")
        step_item.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        step_item_lay = QHBoxLayout(step_item)
        step_item_lay.setContentsMargins(0, 0, 0, 0)
        step_item_lay.setSpacing(pt(12))

        circle = QLabel(num)
        circle.setFixedSize(pt(36), pt(36))
        circle.setAlignment(Qt.AlignCenter)
        step_item_lay.addWidget(circle)
        _step_circles.append(circle)

        lbl = QLabel(txt)
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lbl.setMinimumWidth(0)
        lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        step_item_lay.addWidget(lbl, 1)
        _step_labels.append(lbl)
        _apply_step_style(circle, lbl, "active" if i == 0 else "pending")
        step_layout.addWidget(step_item, 1)

        if i < 3:
            arrow = QLabel("\u203a")
            arrow.setAlignment(Qt.AlignCenter)
            arrow.setFixedSize(pt(28), pt(36))
            arrow.setStyleSheet(
                f"color:{C_TEXT3}; font-size:{pt(21)}px; font-weight:600;"
                " background:transparent; border:none; padding:0;"
            )
            step_layout.addWidget(arrow)
            _step_arrows.append(arrow)

    wizard_outer.addLayout(step_layout)
    inner_lay.addWidget(wizard_card)

    # Two-column layout
    flash_cols = QBoxLayout(QBoxLayout.LeftToRight)
    flash_cols.setContentsMargins(0, 0, 0, 0)
    flash_cols.setSpacing(pt(20))

    # Left stacked panel
    flash_left_stack = QStackedWidget()
    flash_left_stack.setContentsMargins(0, 0, 0, 0)
    flash_left_stack.setFrameShape(QFrame.NoFrame)
    flash_left_stack.setLineWidth(0)
    flash_left_stack.setStyleSheet("QStackedWidget { background:transparent; border:none; margin:0; padding:0; }")

    # Left page 0: device selection — wrapped in a scroll area
    left_page0_inner = QWidget()
    left_page0_inner.setStyleSheet("background:transparent;")
    left_col = QVBoxLayout(left_page0_inner)
    left_col.setContentsMargins(0, 0, pt(4), 0)
    left_col.setSpacing(pt(20))

    dev_card = make_card(12)
    dev_lay = QVBoxLayout(dev_card)
    dev_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    dev_lay.setSpacing(pt(16))

    dev_title_lbl = make_label(_ft("flash.device.title"), 14, C_TEXT, bold=True)
    dev_sub_lbl = make_label(_ft("flash.device.subtitle"), 11, C_TEXT3)
    dev_lay.addWidget(dev_title_lbl)
    dev_lay.addWidget(dev_sub_lbl)

    prod_row = QHBoxLayout()
    prod_name_lbl = make_label(_ft("flash.device.product"), 12, C_TEXT2)
    prod_row.addWidget(prod_name_lbl)
    prod_row.addStretch()
    flash_product_combo = DropdownButton(max_popup_height=pt(320))
    flash_product_combo.setMinimumWidth(pt(260))
    flash_product_combo.addItems(sorted(products.keys()))
    prod_row.addWidget(flash_product_combo)
    dev_lay.addLayout(prod_row)

    l4t_row = QHBoxLayout()
    l4t_name_lbl = make_label(_ft("flash.device.l4t"), 12, C_TEXT2)
    l4t_row.addWidget(l4t_name_lbl)
    l4t_row.addStretch()
    flash_l4t_combo = DropdownButton(max_popup_height=pt(200))
    flash_l4t_combo.setMinimumWidth(pt(260))
    l4t_row.addWidget(flash_l4t_combo)
    dev_lay.addLayout(l4t_row)

    # Device image
    flash_device_img = QLabel()
    flash_device_img.setFixedSize(320 if PLATFORM.win_min_w > 1024 else 280, 200 if PLATFORM.win_min_w > 1024 else 160)
    flash_device_img.setAlignment(Qt.AlignCenter)
    flash_device_img.setStyleSheet(f"""
        background: {C_CARD_LIGHT};
        border: none;
        border-radius: 10px;
        color: {C_TEXT3};
        font-size: {pt(11)}pt;
    """)
    flash_device_img.setText(_ft("flash.product_summary.no_image"))
    dev_lay.addWidget(flash_device_img, alignment=Qt.AlignHCenter)

    # Product info
    flash_info = QLabel(_ft("flash.product_summary.waiting"))
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

    flash_getting_started_btn = make_button(_ft("flash.docs.getting_started"), primary=True, small=True)
    flash_getting_started_btn.clicked.connect(
        lambda: _open_flash_doc(flash_getting_started_btn)
    )
    flash_docs_row.addWidget(flash_getting_started_btn)

    flash_hardware_btn = make_button(_ft("flash.docs.hardware_interface"), small=True)
    flash_hardware_btn.clicked.connect(
        lambda: _open_flash_doc(flash_hardware_btn)
    )
    flash_docs_row.addWidget(flash_hardware_btn)
    flash_docs_row.addStretch()
    dev_lay.addLayout(flash_docs_row)
    left_col.addWidget(dev_card)

    # Options card
    opt_card = make_card(12)
    opt_lay = QVBoxLayout(opt_card)
    opt_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    opt_lay.setSpacing(pt(12))
    opt_title_lbl = make_label(_ft("flash.options.title"), 14, C_TEXT, bold=True)
    opt_lay.addWidget(opt_title_lbl)
    skip_verify_cb = QCheckBox(_ft("flash.options.skip_verify"))
    skip_verify_cb.setChecked(True)
    opt_lay.addWidget(skip_verify_cb)
    left_col.addWidget(opt_card)
    left_col.addStretch()

    left_page0 = QScrollArea()
    left_page0.setWidgetResizable(True)
    left_page0.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    left_page0.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    left_page0.setFrameShape(QFrame.NoFrame)
    left_page0.setStyleSheet(
        "QScrollArea { background:transparent; border:none; }"
        "QScrollBar:vertical { background:transparent; width:6px; border-radius:3px; }"
        f"QScrollBar::handle:vertical {{ background:rgba(255,255,255,0.18); border-radius:3px; min-height:{pt(24)}px; }}"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }"
    )
    left_page0.setWidget(left_page0_inner)
    flash_left_stack.addWidget(left_page0)

    # Left page 1: Recovery guide
    rec_guide_card = make_card(12)
    rec_guide_outer = QVBoxLayout(rec_guide_card)
    rec_guide_outer.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    rec_guide_outer.setSpacing(pt(12))
    rec_guide_title_lbl = make_label(_ft("flash.recovery.title"), 14, C_TEXT, bold=True)
    rec_guide_outer.addWidget(rec_guide_title_lbl)

    rec_guide_scroll = QScrollArea()
    rec_guide_scroll.setWidgetResizable(True)
    rec_guide_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    rec_guide_scroll.setStyleSheet("background:transparent; border:none;")

    rec_guide_content = QWidget()
    rec_guide_content.setStyleSheet("background:transparent;")
    rec_guide_layout = QVBoxLayout(rec_guide_content)
    rec_guide_layout.setContentsMargins(0, 0, pt(8), 0)
    rec_guide_layout.setSpacing(pt(12))
    rec_guide_empty_lbl = make_label(_ft("flash.recovery.select_first"), 12, C_TEXT3)
    rec_guide_layout.addWidget(rec_guide_empty_lbl)
    rec_guide_layout.addStretch()

    rec_guide_scroll.setWidget(rec_guide_content)
    rec_guide_outer.addWidget(rec_guide_scroll, 1)
    flash_left_stack.addWidget(rec_guide_card)

    # Left page 2: post-flash quick start
    guide_card = make_card(12)
    guide_outer = QVBoxLayout(guide_card)
    guide_outer.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    guide_outer.setSpacing(pt(14))
    guide_title_lbl = make_label(_ft("flash.guide.title"), 14, C_TEXT, bold=True)
    guide_sub_lbl = make_label(_ft("flash.guide.subtitle"), 11, C_TEXT3)
    guide_outer.addWidget(guide_title_lbl)
    guide_outer.addWidget(guide_sub_lbl)

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

    hint_badge = QLabel(_ft("flash.guide.recommended"))
    hint_badge.setStyleSheet(f"""
        background: rgba(7,18,0,0.35);
        color: {C_GREEN};
        border-radius: 8px;
        padding: 4px 10px;
        font-size: {pt(9)}pt;
        font-weight: 700;
    """)
    hint_lay.addWidget(hint_badge, alignment=Qt.AlignLeft)
    hint_title_lbl = make_label(_ft("flash.guide.next_title"), 13, C_TEXT, bold=True)
    hint_desc_lbl = make_label(_ft("flash.guide.next_desc"), 10, C_TEXT2, wrap=True)
    hint_lay.addWidget(hint_title_lbl)
    hint_lay.addWidget(hint_desc_lbl)
    hint_btn_row = QHBoxLayout()
    hint_btn_row.setSpacing(pt(10))
    hint_init_btn = make_button(_ft("flash.btn.jetson_init"), primary=True, small=True)
    hint_init_btn.clicked.connect(lambda: open_jetson_init_dialog(parent=page.window()))
    hint_btn_row.addWidget(hint_init_btn)
    hint_btn_row.addStretch()
    hint_lay.addLayout(hint_btn_row)
    guide_layout.addWidget(hint_card)

    next_steps = [
        ("\U0001f5a5", "flash.guide.step.devices.title", "flash.guide.step.devices.desc"),
        ("\U0001f4e6", "flash.guide.step.apps.title", "flash.guide.step.apps.desc"),
        ("\U0001f9e0", "flash.guide.step.skills.title", "flash.guide.step.skills.desc"),
        ("\U0001f310", "flash.guide.step.remote.title", "flash.guide.step.remote.desc"),
        ("\U0001f4ac", "flash.guide.step.community.title", "flash.guide.step.community.desc"),
    ]
    next_step_text_labels = []
    for icon, title_key, desc_key in next_steps:
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
        step_title_lbl = make_label(_ft(title_key), 12, C_TEXT, bold=True)
        step_desc_lbl = make_label(_ft(desc_key), 10, C_TEXT2, wrap=True)
        next_step_text_labels.append((step_title_lbl, title_key, step_desc_lbl, desc_key))
        text_col_v.addWidget(step_title_lbl)
        text_col_v.addWidget(step_desc_lbl)
        item_lay_h.addLayout(text_col_v, 1)
        guide_layout.addWidget(item_card)
    guide_layout.addStretch()

    guide_scroll.setWidget(guide_content)
    guide_outer.addWidget(guide_scroll, 1)
    flash_left_stack.addWidget(guide_card)

    flash_cols.addWidget(flash_left_stack, 1)

    # Right column
    flash_right_panel = QWidget()
    flash_right_panel.setStyleSheet("background:transparent;")
    flash_right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    right_col = QVBoxLayout(flash_right_panel)
    right_col.setContentsMargins(0, 0, 0, 0)
    right_col.setSpacing(pt(20))

    flash_step_stack = QStackedWidget()
    flash_step_stack.setContentsMargins(0, 0, 0, 0)
    flash_step_stack.setFrameShape(QFrame.NoFrame)
    flash_step_stack.setLineWidth(0)
    flash_step_stack.setStyleSheet("QStackedWidget { background:transparent; border:none; margin:0; padding:0; }")

    # Step 1: prepare firmware
    step1_card = make_card(12)
    task_lay = QVBoxLayout(step1_card)
    task_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    task_lay.setSpacing(pt(16))
    step1_title_lbl = make_label(_ft("flash.step1.title"), 14, C_TEXT, bold=True)
    step1_sub_lbl = make_label(_ft("flash.step1.subtitle"), 11, C_TEXT3)
    task_lay.addWidget(step1_title_lbl)
    task_lay.addWidget(step1_sub_lbl)

    flash_status_lbl = make_label(_ft("flash.status.not_started"), 14, C_TEXT2)
    task_lay.addWidget(flash_status_lbl)

    flash_progress = QProgressBar()
    flash_progress.setRange(0, 100)
    flash_progress.setValue(0)
    flash_progress.setFixedHeight(6)
    flash_progress.setVisible(False)
    task_lay.addWidget(flash_progress)

    flash_prepare_scene = FlashAnimationWidget()
    flash_prepare_scene.setFixedHeight(160)
    task_lay.addWidget(flash_prepare_scene)

    btn_row = QHBoxLayout()
    flash_cancel_btn = make_button(_ft("flash.btn.cancel"), danger=True)
    flash_cancel_btn.setVisible(False)
    flash_cancel_btn.clicked.connect(lambda: _cancel_flash())

    flash_download_btn = QPushButton(_ft("flash.btn.download_extract"))
    flash_download_btn.setCursor(Qt.PointingHandCursor)
    flash_download_btn.setToolTip(_ft("flash.btn.download_extract_tip"))
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

    flash_clear_btn = QPushButton(_ft("flash.btn.clear_cache"))
    flash_clear_btn.setCursor(Qt.PointingHandCursor)
    flash_clear_btn.setToolTip(_ft("flash.btn.clear_cache_tip"))
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

    flash_next_btn = QPushButton(_ft("flash.btn.next"))
    flash_next_btn.setCursor(Qt.PointingHandCursor)
    flash_next_btn.setToolTip(_ft("flash.btn.next_tip"))
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

    # Step 2: enter Recovery mode
    step2_card = make_card(12)
    rec_lay = QVBoxLayout(step2_card)
    rec_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    rec_lay.setSpacing(pt(16))
    step2_title_lbl = make_label(_ft("flash.step2.title"), 14, C_TEXT, bold=True)
    step2_sub_lbl = make_label(_ft("flash.step2.subtitle"), 11, C_TEXT3)
    step2_sub_lbl.setWordWrap(True)
    rec_lay.addWidget(step2_title_lbl)
    rec_lay.addWidget(step2_sub_lbl)

    rec_status_lbl = make_label(_ft("flash.status.waiting_detection"), 13, C_TEXT2)
    rec_lay.addWidget(rec_status_lbl)

    rec_btn_row = QHBoxLayout()
    rec_back_btn = QPushButton(_ft("flash.btn.back"))
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

    rec_detect_btn = QPushButton(_ft("flash.btn.detect_device"))
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

    rec_flash_btn = QPushButton(_ft("flash.btn.start_flash"))
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

    # Step 3: flashing
    step3_card = make_card(12)
    run_lay = QVBoxLayout(step3_card)
    run_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    run_lay.setSpacing(pt(16))
    step3_title_lbl = make_label(_ft("flash.step3.title"), 14, C_TEXT, bold=True)
    run_lay.addWidget(step3_title_lbl)

    flash_run_status_lbl = make_label(_ft("flash.status.preparing_flash"), 13, C_TEXT2)
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
    flash_run_cancel_btn = make_button(_ft("flash.btn.cancel"), danger=True)
    flash_run_cancel_btn.clicked.connect(lambda: _cancel_flash())
    flash_run_retry_btn = make_button(_ft("flash.btn.retry_flash"), primary=True)
    flash_run_retry_btn.setVisible(False)
    flash_run_retry_btn.clicked.connect(lambda: _retry_flash())
    flash_run_back_btn = make_button(_ft("flash.btn.back_to_recovery"), small=False)
    flash_run_back_btn.setVisible(False)
    flash_run_back_btn.clicked.connect(lambda: _flash_go_next_step())
    run_btn_row.addWidget(flash_run_cancel_btn)
    run_btn_row.addStretch()
    run_btn_row.addWidget(flash_run_retry_btn)
    run_btn_row.addWidget(flash_run_back_btn)
    run_lay.addLayout(run_btn_row)
    flash_step_stack.addWidget(step3_card)

    # Step 4: done
    step4_card = make_card(12)
    done_lay = QVBoxLayout(step4_card)
    done_lay.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    done_lay.setSpacing(pt(16))
    step4_title_lbl = make_label(_ft("flash.step4.title"), 14, C_TEXT, bold=True)
    done_lay.addWidget(step4_title_lbl)
    flash_done_status_lbl = make_label(_ft("flash.status.done"), 13, C_GREEN)
    done_lay.addWidget(flash_done_status_lbl)

    flash_done_scene = FlashAnimationWidget()
    flash_done_scene.setFixedHeight(160)
    flash_done_scene.set_mode("success")
    done_lay.addWidget(flash_done_scene)

    done_btn_row = QHBoxLayout()
    flash_done_init_btn = make_button(_ft("flash.btn.jetson_init"), primary=True)
    flash_done_init_btn.clicked.connect(lambda: open_jetson_init_dialog(parent=page.window()))
    flash_done_restart_btn = make_button(_ft("flash.btn.restart"))
    flash_done_restart_btn.clicked.connect(lambda: _flash_reset_to_start())
    done_btn_row.addWidget(flash_done_init_btn)
    done_btn_row.addStretch()
    done_btn_row.addWidget(flash_done_restart_btn)
    done_lay.addLayout(done_btn_row)
    flash_step_stack.addWidget(step4_card)

    right_col.addWidget(flash_step_stack)

    # Log card
    log_card = make_card(12)
    log_lay_inner = QVBoxLayout(log_card)
    log_lay_inner.setContentsMargins(pt(24), pt(20), pt(24), pt(20))
    log_lay_inner.setSpacing(pt(12))
    hdr = QHBoxLayout()
    log_title_lbl = make_label(_ft("flash.log.title"), 14, C_TEXT, bold=True)
    hdr.addWidget(log_title_lbl)
    hdr.addStretch()
    save_btn = make_button(_ft("flash.log.save"), small=True)
    save_btn.clicked.connect(lambda: _save_flash_log())
    hdr.addWidget(save_btn)
    clear_log_btn = make_button(_ft("flash.log.clear"), small=True)
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

    # Local helper methods.

    def _flash_log_append(text: str):
        flash_log.moveCursor(QTextCursor.End)
        flash_log.insertPlainText(text + "\n")
        flash_log.ensureCursorVisible()

    def _save_flash_log():
        text = flash_log.toPlainText().strip()
        if not text:
            _flash_log_append(_ft("flash.log.warn_empty"))
            return
        default_name = f"seeed_flash_log_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        default_path = str(Path.home() / default_name)
        file_path, _ = QFileDialog.getSaveFileName(
            page.window(), _ft("flash.log.save_dialog_title"), default_path,
            "Log Files (*.log);;Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return
        try:
            Path(file_path).write_text(text + "\n", encoding="utf-8")
            _flash_log_append(_ft("flash.log.saved", path=file_path))
        except Exception as exc:
            _flash_log_append(_ft("flash.log.save_failed", error=exc))

    def _cancel_flash():
        if _state["flash_thread"]:
            _state["flash_thread"].cancel()

    def _update_adaptive_layout():
        width = flash_cols_host.width() or page.width()
        if FLASH_FORCE_TWO_COLUMNS:
            flash_cols.setDirection(QBoxLayout.LeftToRight)
        compact_visual = width < 1100
        if compact_visual:
            flash_device_img.setFixedSize(pt(200), pt(126))
        else:
            flash_device_img.setFixedSize(pt(320), pt(200))
        flash_log.setMinimumHeight(pt(120) if compact_visual else pt(200))

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
        flash_info.setText(_flash_info_html(name, versions))
        _set_flash_doc_button(flash_getting_started_btn, getting_started, _ft("flash.docs.getting_started_tip"))
        _set_flash_doc_button(flash_hardware_btn, hardware_interfaces, _ft("flash.docs.hardware_tip"))
        # Load device image.
        local_img = info.get("local_image", "")
        img_path = _PROJECT_ROOT / local_img if local_img else None
        if img_path and img_path.exists():
            pix = QPixmap(str(img_path)).scaled(320, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            flash_device_img.setPixmap(pix)
            flash_device_img.setText("")
        else:
            image_url = info.get("image_url", "")
            if image_url:
                flash_device_img.clear()
                flash_device_img.setText(t("flash.product_summary.no_image", lang=get_language()))
                def _fetch_device_img(url=image_url):
                    try:
                        import requests as _req
                        resp = _req.get(url, timeout=10)
                        resp.raise_for_status()
                        data = resp.content
                        def _update():
                            p = QPixmap()
                            p.loadFromData(data)
                            if not p.isNull():
                                flash_device_img.setPixmap(p.scaled(320, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                                flash_device_img.setText("")
                        QTimer.singleShot(0, _update)
                    except Exception:
                        pass
                threading.Thread(target=_fetch_device_img, daemon=True).start()
            else:
                flash_device_img.clear()
                flash_device_img.setText(t("flash.product_summary.no_image", lang=get_language()))
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
                flash_cache_lbl.setText(t("flash.cache.extracted_ready", lang=get_language()))
                flash_cache_lbl.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(11)}pt; background:transparent;")
                flash_prepare_scene.set_mode("idle")
                flash_prepare_scene.set_download_progress(1.0)
                _set_next_enabled(True)
            elif has_archive:
                fp = flasher.download_dir / flasher.firmware_info['filename']
                size_mb = fp.stat().st_size / 1024 / 1024
                flash_cache_lbl.setText(
                    t("flash.cache.archive_ready", lang=get_language(), size_mb=size_mb)
                )
                flash_cache_lbl.setStyleSheet(f"color:{C_BLUE}; font-size:{pt(11)}pt; background:transparent;")
                if not flash_cancel_btn.isVisible():
                    flash_prepare_scene.set_mode("idle")
                    flash_prepare_scene.set_download_progress(0.0)
                _set_next_enabled(False)
            else:
                flash_cache_lbl.setText(t("flash.cache.no_local", lang=get_language()))
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
        dlg.setWindowTitle(_ft("flash.dialog.clear_cache.title"))
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(f"background:{C_BG};")
        d_lay = QVBoxLayout(dlg)
        d_lay.setSpacing(12)
        d_lay.setContentsMargins(20, 20, 20, 20)
        d_lay.addWidget(make_label(_ft("flash.dialog.clear_cache.prompt"), 13, C_TEXT))
        d_lay.addWidget(make_label(_ft("flash.dialog.clear_cache.details"), 10, C_TEXT3))

        checkbox_style = f"""
            QCheckBox {{ color: {C_TEXT2}; font-size: {pt(12)}pt; spacing: 0px; padding: 10px 14px;
                background: transparent; border-radius: 10px; }}
            QCheckBox:hover {{ background: rgba(255,255,255,0.04); }}
            QCheckBox::indicator {{ width: 0px; height: 0px; }}
        """
        archive_label = "  " + _ft("flash.dialog.clear_cache.archive")
        extracted_label = "  " + _ft("flash.dialog.clear_cache.extracted")
        cb_archive = QCheckBox()
        cb_extracted = QCheckBox()
        cb_archive.setStyleSheet(checkbox_style)
        cb_extracted.setStyleSheet(checkbox_style)
        cb_archive.setChecked(True)
        cb_extracted.setChecked(True)

        def _sync_checkbox_text(box: QCheckBox, label: str):
            suffix = f"  {_ft('flash.dialog.clear_cache.selected')}" if box.isChecked() else ""
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
        cancel_btn_d = make_button(_ft("common.cancel"))
        ok_btn = make_button(_ft("flash.dialog.clear_cache.confirm"), primary=True)
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
                _flash_log_append(_ft("flash.log.cache_cleared") + "\n" + "\n".join(f"  {p}" for p in removed))
            else:
                _flash_log_append(_ft("flash.log.cache_none"))
        except Exception as e:
            _flash_log_append(_ft("flash.log.cache_clear_failed", error=e))
        _update_cache_label()
        _set_next_enabled(False)

    def _ensure_sudo() -> bool:
        import getpass as _getpass
        if sudo_check_cached():
            return True
        dlg = QDialog(page.window())
        dlg.setWindowTitle(_ft("flash.dialog.sudo.title"))
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet(f"background:{C_BG};")
        d_lay = QVBoxLayout(dlg)
        d_lay.setSpacing(12)
        d_lay.setContentsMargins(20, 20, 20, 20)
        d_lay.addWidget(make_label(_ft("flash.dialog.sudo.desc"), 13, C_TEXT))
        try:
            username = _getpass.getuser()
        except Exception:
            username = _ft("flash.dialog.sudo.current_user")
        hint_lbl = QLabel("  " + _ft("flash.dialog.sudo.hint", username=username))
        hint_lbl.setStyleSheet(f"""
            color: {C_BLUE}; background: rgba(41,121,255,0.10);
            border-radius: 6px; padding: 6px 10px; font-size: {pt(11)}pt;
        """)
        d_lay.addWidget(hint_lbl)
        pwd_input = QLineEdit()
        pwd_input.setEchoMode(QLineEdit.Password)
        pwd_input.setPlaceholderText(_ft("flash.dialog.sudo.password_placeholder"))
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
            err_lbl.setText(_ft("flash.dialog.sudo.password_wrong"))
            pwd_input.clear()
            pwd_input.setFocus()

    def _on_prepare_bsp():
        if not _ensure_sudo():
            _flash_log_append(_ft("flash.log.sudo_denied_operation"))
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
            msg.setWindowTitle(_ft("flash.dialog.extracted_exists.title"))
            msg.setText(_ft("flash.dialog.extracted_exists.text"))
            msg.setInformativeText(_ft("flash.dialog.extracted_exists.info"))
            skip_btn = msg.addButton(_ft("flash.dialog.extracted_exists.btn.skip"), QMessageBox.AcceptRole)
            overwrite_btn = msg.addButton(_ft("flash.dialog.extracted_exists.btn.overwrite"), QMessageBox.DestructiveRole)
            msg.addButton(_ft("common.cancel"), QMessageBox.RejectRole)
            msg.exec_()
            clicked = msg.clickedButton()
            if clicked is skip_btn:
                _flash_log_append(_ft("flash.log.use_existing_extracted"))
                _set_next_enabled(True)
                return
            elif clicked is overwrite_btn:
                _run_flash_thread(product, l4t, force_redownload=True, prepare_only=True)
        elif has_archive:
            _flash_log_append(_ft("flash.log.archive_exists_skip_download"))
            _run_flash_thread(product, l4t, force_redownload=False, prepare_only=True)
        else:
            _run_flash_thread(product, l4t, force_redownload=False, prepare_only=True)

    def _set_wizard_step(active_idx: int):
        for i, (circle, lbl) in enumerate(zip(_step_circles, _step_labels)):
            done = i < active_idx
            active = i == active_idx
            if active:
                _apply_step_style(circle, lbl, "active")
            elif done:
                _apply_step_style(circle, lbl, "done")
            else:
                _apply_step_style(circle, lbl, "pending")

        for i, arrow in enumerate(_step_arrows):
            arrow.setStyleSheet(
                f"color:{C_GREEN if i < active_idx else C_TEXT3}; font-size:{pt(21)}px; font-weight:600;"
                " background:transparent; border:none; padding:0;"
            )

    def _flash_go_next_step():
        _set_wizard_step(1)
        flash_step_stack.setCurrentIndex(1)
        flash_left_stack.setCurrentIndex(1)
        _build_recovery_guide(flash_product_combo.currentText())
        rec_status_lbl.setText(_ft("flash.status.waiting_detection"))
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
        flash_status_lbl.setText(_ft("flash.status.not_started"))
        flash_status_lbl.setStyleSheet(f"color:{C_TEXT2}; background:transparent;")
        flash_run_status_lbl.setText(_ft("flash.status.ready_start"))
        flash_run_status_lbl.setStyleSheet(f"color:{C_TEXT2}; background:transparent;")
        flash_progress.setVisible(False)
        flash_progress.setValue(0)
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
            rec_guide_layout.addWidget(make_label(_ft("flash.recovery.no_guide"), 12, C_TEXT3))
            rec_guide_layout.addStretch()
            return
        title_lbl = make_label(guide["title"], 13, C_TEXT, bold=True)
        title_lbl.setWordWrap(True)
        rec_guide_layout.addWidget(title_lbl)
        rec_guide_layout.addWidget(make_label(_ft("flash.recovery.required_cable", cable=guide["cable"]), 11, C_TEXT2))
        if guide.get("image_url") or guide.get("local_image"):
            img_lbl = QLabel()
            img_lbl.setAlignment(Qt.AlignCenter)
            img_lbl.setFixedHeight(280)
            img_lbl.setText(_ft("flash.image.loading"))
            img_lbl.setStyleSheet(f"color:{C_TEXT3}; background:{C_CARD_LIGHT}; border-radius:8px; font-size:{pt(10)}pt;")
            rec_guide_layout.addWidget(img_lbl)
            _load_guide_image(guide.get("image_url", ""), img_lbl, guide.get("local_image", ""), guide["title"])
        rec_guide_layout.addWidget(make_label(_ft("flash.recovery.steps"), 12, C_TEXT, bold=True))
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
        rec_guide_layout.addWidget(make_label(_ft("flash.recovery.usb_ids"), 12, C_TEXT, bold=True))
        for name, uid in guide["usb_ids"]:
            id_lbl = QLabel(f"  {name}: {uid}")
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
        label.setToolTip(_ft("flash.image.click_view"))
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
        root.addWidget(make_label(_ft("flash.image.zoom_hint"), 10, C_TEXT3))
        close_btn = make_button(_ft("common.close"))
        close_btn.clicked.connect(dlg.accept)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(close_btn)
        root.addLayout(close_row)
        dlg.exec_()

    def _load_guide_image(url: str, label: QLabel, local_image: str = "", title: str = ""):
        if not title:
            title = _ft("flash.image.dialog_title")
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
                        label.setText(_ft("flash.image.load_failed"))
                QTimer.singleShot(0, update)
            except Exception:
                QTimer.singleShot(0, lambda: (
                    label.setText(_ft("flash.image.load_failed")),
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
                            _flash_log_append(_ft("flash.detect.log_found", line=line.strip()))
                            break
            if found:
                rec_status_lbl.setText(_ft("flash.detect.status_found"))
                rec_status_lbl.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
                rec_flash_btn.setEnabled(True)
            else:
                rec_status_lbl.setText(_ft("flash.detect.status_not_found"))
                rec_status_lbl.setStyleSheet(f"color:{C_ORANGE}; background:transparent;")
                rec_flash_btn.setEnabled(False)
                _flash_log_append(_ft("flash.detect.warn_no_apx"))
        except Exception as e:
            rec_status_lbl.setText(_ft("flash.detect.status_failed", error=e))
            rec_status_lbl.setStyleSheet(f"color:{C_RED}; background:transparent;")
            _flash_log_append(_ft("flash.detect.err_lsusb", error=e))

    def _start_flash():
        product = flash_product_combo.currentText()
        l4t = flash_l4t_combo.currentText()
        if not product or not l4t:
            return
        if not _ensure_sudo():
            _flash_log_append(_ft("flash.log.sudo_flash_cancelled"))
            return
        _run_flash_thread(product, l4t, flash_only=True)

    def _retry_flash():
        product = flash_product_combo.currentText()
        l4t = flash_l4t_combo.currentText()
        if not product or not l4t:
            return
        _flash_log_append(_ft("flash.log.retry_requested"))
        if not _ensure_sudo():
            _flash_log_append(_ft("flash.log.sudo_retry_cancelled"))
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
        bus.status_busy.emit(_ft("flash.status.processing"))
        if not flash_only:
            flash_log.clear()
        _flash_log_append(
            _ft(
                "flash.log.start",
                product=product,
                l4t=l4t,
                force_redownload=(f" {_ft('flash.log.tag_force_redownload')}" if force_redownload else ""),
                flash_only=(f" {_ft('flash.log.tag_flash_only')}" if flash_only else ""),
            )
        )
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
                             force_redownload=force_redownload, prepare_only=prepare_only,
                             flash_only=flash_only, lang=_state["lang"])
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
        msg_lower = msg.lower()
        if any(k in msg_lower for k in ("skip download", "verify", "extract", "flash")):
            bar = _state["active_progress"]
            if bar.maximum() == 0:
                bar.setRange(0, 100)
        if flash_step_stack.currentIndex() == 0:
            if any(k in msg_lower for k in ("extract", "skip download", "download", "verify", "initialize")):
                flash_prepare_scene.set_mode("downloading")
            elif "complete" in msg_lower:
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
            label_text = _ft(
                "flash.status.downloading_with_total",
                downloaded=_fmt(downloaded),
                total=_fmt(total),
                pct=pct,
            )
            if flash_step_stack.currentIndex() == 0:
                flash_prepare_scene.set_download_progress(pct / 100)
        else:
            bar.setRange(0, 0)
            label_text = _ft("flash.status.downloading", downloaded=_fmt(downloaded))
        _state["active_status_label"].setText(label_text)

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
        color = C_GREEN if ok else C_RED
        icon = "\u2713" if ok else "\u2717"
        _state["active_progress"].setRange(0, 100)
        _state["active_progress"].setValue(100 if ok else max(5, _state["active_progress"].value()))
        _state["active_status_label"].setText(f"{icon} {msg}")
        _state["active_status_label"].setStyleSheet(f"color:{color}; background:transparent;")
        _flash_log_append(f"[{'OK' if ok else 'ERR'}] {msg}")
        bus.status_idle.emit(_ft("flash.status.ready"))
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

    i18n = page.i18n
    i18n.bind_text(header_title_lbl, "flash.page.title")
    i18n.bind_text(header_sub_lbl, "flash.page.subtitle")
    for idx, lbl in enumerate(_step_labels):
        i18n.bind_text(lbl, step_key_order[idx])
    i18n.bind_text(dev_title_lbl, "flash.device.title")
    i18n.bind_text(dev_sub_lbl, "flash.device.subtitle")
    i18n.bind_text(prod_name_lbl, "flash.device.product")
    i18n.bind_text(l4t_name_lbl, "flash.device.l4t")
    i18n.bind_text(flash_getting_started_btn, "flash.docs.getting_started")
    i18n.bind_text(flash_hardware_btn, "flash.docs.hardware_interface")
    i18n.bind_text(opt_title_lbl, "flash.options.title")
    i18n.bind_text(skip_verify_cb, "flash.options.skip_verify")
    i18n.bind_text(rec_guide_title_lbl, "flash.recovery.title")
    i18n.bind_text(rec_guide_empty_lbl, "flash.recovery.select_first")
    i18n.bind_text(guide_title_lbl, "flash.guide.title")
    i18n.bind_text(guide_sub_lbl, "flash.guide.subtitle")
    i18n.bind_text(hint_badge, "flash.guide.recommended")
    i18n.bind_text(hint_title_lbl, "flash.guide.next_title")
    i18n.bind_text(hint_desc_lbl, "flash.guide.next_desc")
    i18n.bind_text(hint_init_btn, "flash.btn.jetson_init")
    for step_title_lbl, title_key, step_desc_lbl, desc_key in next_step_text_labels:
        i18n.bind_text(step_title_lbl, title_key)
        i18n.bind_text(step_desc_lbl, desc_key)
    i18n.bind_text(step1_title_lbl, "flash.step1.title")
    i18n.bind_text(step1_sub_lbl, "flash.step1.subtitle")
    i18n.bind_text(step2_title_lbl, "flash.step2.title")
    i18n.bind_text(step2_sub_lbl, "flash.step2.subtitle")
    i18n.bind_text(step3_title_lbl, "flash.step3.title")
    i18n.bind_text(step4_title_lbl, "flash.step4.title")
    i18n.bind_text(flash_cancel_btn, "flash.btn.cancel")
    i18n.bind_text(flash_download_btn, "flash.btn.download_extract")
    i18n.bind_tooltip(flash_download_btn, "flash.btn.download_extract_tip")
    i18n.bind_text(flash_clear_btn, "flash.btn.clear_cache")
    i18n.bind_tooltip(flash_clear_btn, "flash.btn.clear_cache_tip")
    i18n.bind_text(flash_next_btn, "flash.btn.next")
    i18n.bind_tooltip(flash_next_btn, "flash.btn.next_tip")
    i18n.bind_text(rec_back_btn, "flash.btn.back")
    i18n.bind_text(rec_detect_btn, "flash.btn.detect_device")
    i18n.bind_text(rec_flash_btn, "flash.btn.start_flash")
    i18n.bind_text(flash_run_cancel_btn, "flash.btn.cancel")
    i18n.bind_text(flash_run_retry_btn, "flash.btn.retry_flash")
    i18n.bind_text(flash_run_back_btn, "flash.btn.back_to_recovery")
    i18n.bind_text(flash_done_init_btn, "flash.btn.jetson_init")
    i18n.bind_text(flash_done_restart_btn, "flash.btn.restart")
    i18n.bind_text(log_title_lbl, "flash.log.title")
    i18n.bind_text(save_btn, "flash.log.save")
    i18n.bind_text(clear_log_btn, "flash.log.clear")

    def _refresh_product_summary():
        product = flash_product_combo.currentText()
        if not product:
            flash_info.setText(_ft("flash.product_summary.waiting"))
            if not flash_device_img.pixmap():
                flash_device_img.setText(_ft("flash.product_summary.no_image"))
            return
        info = product_images.get(product, {})
        name = info.get("name", product)
        versions = len(products.get(product, []))
        flash_info.setText(_flash_info_html(name, versions))
        _set_flash_doc_button(
            flash_getting_started_btn,
            (info.get("getting_started", "") or "").strip(),
            _ft("flash.docs.getting_started_tip"),
        )
        _set_flash_doc_button(
            flash_hardware_btn,
            (info.get("hardware_interfaces", "") or "").strip(),
            _ft("flash.docs.hardware_tip"),
        )
        if not flash_device_img.pixmap():
            flash_device_img.setText(_ft("flash.product_summary.no_image"))

    i18n.bind_callable(_refresh_product_summary)
    i18n.bind_callable(_update_cache_label)

    def _retranslate_ui(lang=None):
        global _FLASH_LANG_OVERRIDE
        if lang:
            _FLASH_LANG_OVERRIDE = lang
            _state["lang"] = lang
        i18n.apply(lang)
    page.retranslate_ui = _retranslate_ui

    # Signal wiring.
    flash_product_combo.currentTextChanged.connect(_on_flash_product_changed)
    flash_l4t_combo.currentTextChanged.connect(lambda _: _update_cache_label())

    # Initial state.
    page.retranslate_ui(get_language())
    if flash_product_combo.currentText():
        _on_flash_product_changed(flash_product_combo.currentText())
    QTimer.singleShot(0, _update_adaptive_layout)

    return page
