"""集中主题定义 — 无边框、大气上位机风格

设计理念：
- 用背景色层次代替边框
- 用阴影代替硬边框
- 用留白代替分隔线
- 深色科技风，符合上位机气质
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QColor, QFont, QFontDatabase
from PyQt5.QtWidgets import (
    QApplication, QDialog, QFrame, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QWidget, QVBoxLayout,
)


@dataclass(frozen=True)
class _PlatformConfig:
    """Compatibility platform config consumed by legacy pages."""
    is_windows: bool
    win_min_w: int
    win_min_h: int


PLATFORM = _PlatformConfig(
    is_windows=(sys.platform == "win32"),
    win_min_w=1120,
    win_min_h=720,
)

# ── 颜色系统 ──────────────────────────────────────────────────────────────────
# 背景层次：从深到浅（整体提亮，减少"黑洞感"）
C_BG_DEEP   = "#0A0F17"   # 最深背景（标题栏、侧边栏）
C_BG        = "#0F1620"   # 主背景
C_BG_LIGHT  = "#141D28"   # 内容区背景

# 卡片层次：从深到浅（与背景拉开对比）
C_CARD      = "#192333"   # 主卡片（更蓝，更有质感）
C_CARD_HOVER= "#1F2C3E"   # 卡片悬停
C_CARD_LIGHT= "#1E2B3C"   # 次级卡片/输入框背景

# 高光 & 边框（营造立体感的关键）
C_BORDER_SUBTLE  = "rgba(255,255,255,0.07)"   # 卡片顶部高光边
C_BORDER_FOCUS   = "rgba(122,179,23,0.55)"    # 焦点边框
C_BORDER_CARD    = "rgba(255,255,255,0.05)"   # 卡片外边框

# 强调色
C_GREEN     = "#8DC21F"   # Seeed 绿（更亮更鲜）
C_GREEN2    = "#7AB317"   # 深绿
C_GREEN_DIM = "#6BA30F"   # 按压态
C_GREEN_GLOW= "rgba(141,194,31,0.18)"  # 绿色光晕

C_BLUE      = "#3D8EF0"   # 更亮的蓝
C_ORANGE    = "#F5A623"
C_RED       = "#E53E3E"

# 文字颜色（主文字提亮）
C_TEXT      = "#F4F8FC"   # 主文字（更白更清晰）
C_TEXT2     = "#B8CCDC"   # 次级文字
C_TEXT3     = "#8A9EAE"   # 辅助文字

UI_FONT_CANDIDATES = (
    "Noto Sans CJK SC",
    "Noto Sans SC",
    "Source Han Sans SC",
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "PingFang SC",
    "Hiragino Sans GB",
    "WenQuanYi Micro Hei",
    "SimHei",
    "Arial Unicode MS",
)

MONO_FONT_CANDIDATES = (
    "Sarasa Mono SC",
    "Sarasa Term SC",
    "Noto Sans Mono CJK SC",
    "Source Han Mono SC",
    "WenQuanYi Zen Hei Mono",
    "Cascadia Mono",
    "Cascadia Code",
    "JetBrains Mono",
    "Consolas",
    "DejaVu Sans Mono",
)

# ── DPI-aware 字体缩放 ────────────────────────────────────────────────────────
def pt(px: int) -> int:
    """返回字体大小（px），stylesheet 中用 px 单位更可靠。
    Windows 上 Qt stylesheet 的 pt 单位会被系统 DPI 二次放大，
    所以 Windows 下按 0.80 缩放避免字号偏大。
    """
    scale = 0.80 if sys.platform == "win32" else 1.0
    return max(8, int(px * scale))


def pick_font_family(candidates: tuple[str, ...], fallback: str = "Sans Serif") -> str:
    families = set(QFontDatabase().families())
    for family in candidates:
        if family in families:
            return family
    return fallback


def build_app_font(point_size: int | None = None) -> QFont:
    font = QFont(pick_font_family(UI_FONT_CANDIDATES))
    if point_size is not None:
        font.setPointSize(point_size)
    return font


def build_mono_font(point_size: int | None = None) -> QFont:
    fallback = pick_font_family(UI_FONT_CANDIDATES)
    font = QFont(pick_font_family(MONO_FONT_CANDIDATES, fallback=fallback))
    font.setStyleHint(QFont.TypeWriter)
    font.setFixedPitch(True)
    if point_size is not None:
        font.setPointSize(point_size)
    return font


# ── 通用组件工厂 ──────────────────────────────────────────────────────────────
def make_label(text: str, size: int = 13, color: str = C_TEXT,
               bold: bool = False, wrap: bool = False) -> QLabel:
    """创建标签 - 无背景，纯文字"""
    lbl = QLabel(text)
    weight = 700 if bold else 400
    lbl.setStyleSheet(
        f"color:{color}; font-size:{pt(size)}px; font-weight:{weight}; "
        f"background:transparent; border:none;"
    )
    if wrap:
        lbl.setWordWrap(True)
    return lbl


def make_button(text: str, primary: bool = False,
                small: bool = False, danger: bool = False) -> QPushButton:
    """创建按钮 - 带高光边框和立体渐变"""
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    
    h  = pt(36) if small else pt(42)
    fs = pt(11) if small else pt(12)
    
    if primary:
        # 主按钮：绿色渐变 + 顶部高光 + 底部阴影边
        b.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #A0D428, stop:1 #7AB317);
                border: 1px solid rgba(0,0,0,0.35);
                border-top-color: rgba(180,240,60,0.45);
                border-radius: 8px;
                color: #0A1800;
                font-size: {fs}px;
                font-weight: 700;
                padding: 0 {pt(24)}px;
                min-height: {h}px;
            }}
            QPushButton:hover {{ 
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #B0E030, stop:1 #8DC21F);
                border-top-color: rgba(200,255,80,0.55);
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #6BA30F, stop:1 #7AB317);
                border-top-color: rgba(100,160,20,0.3);
            }}
            QPushButton:disabled {{ 
                background: #1A2535; 
                border-color: rgba(255,255,255,0.04);
                color: #4A5B6A; 
            }}
        """)
    elif danger:
        # 危险按钮：红色渐变 + 高光边
        b.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(229,62,62,0.22), stop:1 rgba(180,30,30,0.18));
                border: 1px solid rgba(229,62,62,0.25);
                border-top-color: rgba(255,120,120,0.20);
                border-radius: 8px;
                color: #FF8080;
                font-size: {fs}px;
                font-weight: 600;
                padding: 0 {pt(20)}px;
                min-height: {h}px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(229,62,62,0.32), stop:1 rgba(180,30,30,0.28));
                border-color: rgba(229,62,62,0.40);
            }}
            QPushButton:pressed {{
                background: rgba(180,30,30,0.35);
            }}
        """)
    else:
        # 普通按钮：微妙边框 + 悬停高亮
        b.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-top-color: rgba(255,255,255,0.12);
                border-radius: 8px;
                color: {C_TEXT2};
                font-size: {fs}px;
                font-weight: 500;
                padding: 0 {pt(16)}px;
                min-height: {h}px;
            }}
            QPushButton:hover {{ 
                background: rgba(255,255,255,0.09); 
                border-color: rgba(255,255,255,0.15);
                color: {C_TEXT};
            }}
            QPushButton:pressed {{
                background: rgba(255,255,255,0.05);
                border-color: rgba(255,255,255,0.08);
            }}
        """)
    return b


def make_card(radius: int = 12, with_shadow: bool = True) -> QFrame:
    """创建卡片 - 带高光顶边和立体阴影"""
    f = QFrame()
    f.setObjectName("SeeedCard")
    f.setStyleSheet(f"""
        QFrame#SeeedCard {{
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #1E2D40, stop:1 {C_CARD});
            border: 1px solid {C_BORDER_CARD};
            border-top-color: {C_BORDER_SUBTLE};
            border-radius: {radius}px;
        }}
    """)
    if with_shadow:
        apply_shadow(f, blur=28, y=6, alpha=80)
    return f


def make_list_card() -> QFrame:
    """Backward-compatible alias for list-style cards."""
    return make_card()


def make_input_card(radius: int = 10) -> QFrame:
    """创建输入框容器 - 内凹感"""
    f = QFrame()
    f.setObjectName("SeeedInputCard")
    f.setStyleSheet(f"""
        QFrame#SeeedInputCard {{
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #141E2C, stop:1 {C_CARD_LIGHT});
            border: 1px solid rgba(255,255,255,0.06);
            border-top-color: rgba(0,0,0,0.3);
            border-radius: {radius}px;
        }}
    """)
    return f


def make_section_header(title: str, subtitle: str = "") -> QWidget:
    """创建区块标题 - 无分割线，纯文字层次"""
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, pt(16))
    layout.setSpacing(pt(4))
    
    title_lbl = make_label(title, size=15, bold=True)
    layout.addWidget(title_lbl)
    
    if subtitle:
        sub_lbl = make_label(subtitle, size=11, color=C_TEXT3)
        layout.addWidget(sub_lbl)
    
    return w


def apply_shadow(w, blur: int = 20, y: int = 4, alpha: int = 60):
    """添加柔和阴影"""
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(blur)
    fx.setOffset(0, y)
    fx.setColor(QColor(0, 0, 0, alpha))
    w.setGraphicsEffect(fx)
    return w


def apply_glow(w, color: str = C_GREEN):
    """添加发光效果（用于选中状态）"""
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(15)
    fx.setOffset(0, 0)
    fx.setColor(QColor(int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16), 80))
    w.setGraphicsEffect(fx)
    return w


def make_tab_button(text: str, active: bool = False) -> "QPushButton":
    """创建分类筛选标签按钮"""
    from PyQt5.QtWidgets import QPushButton
    from PyQt5.QtCore import Qt
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    bg = "rgba(122,179,23,0.15)" if active else "transparent"
    color = C_GREEN if active else C_TEXT2
    weight = "600" if active else "400"
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {bg};
            color: {color};
            border: none;
            border-radius: 0px;
            padding: 0px {pt(18)}px;
            font-size: {pt(11)}px;
            font-weight: {weight};
            min-height: {pt(36)}px;
            text-align: center;
        }}
        QPushButton:hover {{ background: rgba(255,255,255,0.06); color:{C_TEXT}; }}
    """)
    return btn


def make_input_field(placeholder: str = "", multiline: bool = False) -> "QWidget":
    """创建统一样式的输入框（单行 QLineEdit 或多行 QTextEdit）"""
    from PyQt5.QtWidgets import QLineEdit, QTextEdit
    if multiline:
        w = QTextEdit()
        w.setPlaceholderText(placeholder)
    else:
        w = QLineEdit()
        w.setPlaceholderText(placeholder)
    w.setStyleSheet(f"""
        background:{C_CARD_LIGHT};
        border:none;
        border-radius:{pt(8)}px;
        padding:{pt(8)}px {pt(14)}px;
        color:{C_TEXT};
        font-size:{pt(12)}pt;
    """)
    return w


# ── 应用级 QSS ────────────────────────────────────────────────────────────────
APP_QSS = f"""
/* 全局滚动条 - 带圆角和悬停高亮 */
QScrollBar:vertical {{
    background: rgba(0,0,0,0.15);
    width: 6px;
    margin: 2px 1px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.12);
    border-radius: 3px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(141,194,31,0.45);
}}
QScrollBar::handle:vertical:pressed {{
    background: rgba(141,194,31,0.65);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background: rgba(0,0,0,0.15);
    height: 6px;
    margin: 1px 2px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(255,255,255,0.12);
    border-radius: 3px;
    min-width: 40px;
}}
QScrollBar::handle:horizontal:hover {{
    background: rgba(141,194,31,0.45);
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* 下拉框 - 带高光边框和渐变背景 */
QComboBox {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #1E2D40, stop:1 {C_CARD_LIGHT});
    border: 1px solid rgba(255,255,255,0.10);
    border-top-color: rgba(255,255,255,0.16);
    border-radius: 8px;
    padding: 8px 14px;
    color: {C_TEXT};
    min-height: {pt(20)}px;
}}
QComboBox:hover {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #253545, stop:1 #1E2B3C);
    border-color: rgba(255,255,255,0.18);
}}
QComboBox:focus {{
    border-color: {C_BORDER_FOCUS};
    border-top-color: rgba(141,194,31,0.35);
}}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{
    width: 8px; height: 8px;
    border-left: 2px solid {C_TEXT3};
    border-bottom: 2px solid {C_TEXT3};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background: #1A2840;
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 8px;
    selection-background-color: rgba(141,194,31,0.18);
    selection-color: {C_GREEN};
    color: {C_TEXT};
    outline: none;
    padding: 6px;
}}

/* 复选框 - 带边框和选中渐变 */
QCheckBox {{
    color: {C_TEXT2};
    spacing: 10px;
    font-size: {pt(12)}px;
}}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border-radius: 5px;
    background: {C_CARD_LIGHT};
    border: 1px solid rgba(255,255,255,0.10);
}}
QCheckBox::indicator:hover {{
    border-color: rgba(141,194,31,0.40);
    background: #1E2B3C;
}}
QCheckBox::indicator:checked {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #A0D428, stop:1 #7AB317);
    border-color: rgba(0,0,0,0.3);
    image: none;
}}

/* 进度条 - 带光泽渐变 */
QProgressBar {{
    background: rgba(0,0,0,0.30);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 5px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C_GREEN2}, stop:0.5 #A8D830, stop:1 {C_GREEN});
    border-radius: 4px;
}}

/* 文本输入 - 带焦点高亮边框 */
QTextEdit {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #111A28, stop:1 {C_CARD_LIGHT});
    border: 1px solid rgba(255,255,255,0.07);
    border-top-color: rgba(0,0,0,0.25);
    border-radius: 10px;
    color: {C_TEXT2};
    padding: 14px;
    font-family: "JetBrains Mono", "Consolas", "Courier New", monospace;
    font-size: {pt(11)}px;
    selection-background-color: rgba(141,194,31,0.25);
}}
QTextEdit:focus {{
    border-color: {C_BORDER_FOCUS};
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #141E2C, stop:1 {C_CARD});
}}

QLineEdit {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #1A2638, stop:1 {C_CARD_LIGHT});
    border: 1px solid rgba(255,255,255,0.09);
    border-top-color: rgba(255,255,255,0.14);
    border-radius: 8px;
    padding: 8px 14px;
    color: {C_TEXT};
    font-size: {pt(12)}px;
    selection-background-color: rgba(141,194,31,0.25);
}}
QLineEdit:focus {{
    border-color: {C_BORDER_FOCUS};
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #1C2A3C, stop:1 {C_CARD});
}}
QLineEdit:hover {{
    border-color: rgba(255,255,255,0.16);
}}

QDialog {{
    background: {C_BG};
    color: {C_TEXT};
}}

QDialog QLabel {{
    background: transparent;
    color: {C_TEXT2};
}}

QDialog QPushButton {{
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.09);
    border-top-color: rgba(255,255,255,0.14);
    border-radius: 8px;
    color: {C_TEXT};
    font-size: {pt(11)}px;
    font-weight: 600;
    padding: 0 {pt(16)}px;
    min-height: {pt(38)}px;
}}

QDialog QPushButton:hover {{
    background: rgba(255,255,255,0.10);
    border-color: rgba(255,255,255,0.18);
}}

QDialog QPushButton:pressed {{
    background: rgba(255,255,255,0.06);
}}

QDialog QPushButton:default {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #A0D428, stop:1 #7AB317);
    border-color: rgba(0,0,0,0.3);
    border-top-color: rgba(180,240,60,0.45);
    color: #0A1800;
    font-weight: 700;
}}

QMessageBox {{
    background: {C_BG};
}}

QMessageBox QLabel#qt_msgbox_label {{
    color: {C_TEXT};
    font-size: {pt(12)}px;
    font-weight: 600;
    min-width: 340px;
}}

QMessageBox QLabel#qt_msgbox_informativelabel {{
    color: {C_TEXT2};
    font-size: {pt(11)}px;
    font-weight: 400;
    min-width: 340px;
}}

QMessageBox QLabel#qt_msgboxex_icon_label {{
    background: transparent;
}}

/* 工具提示 - 带边框和阴影 */
QToolTip {{
    background: #1A2840;
    border: 1px solid rgba(255,255,255,0.12);
    border-top-color: rgba(255,255,255,0.20);
    border-radius: 8px;
    color: {C_TEXT};
    padding: 8px 14px;
    font-size: {pt(11)}px;
}}

/* 滚动区域透明背景 */
QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
"""


def apply_app_theme():
    """在 QApplication 实例创建后调用，全局应用主题样式。"""
    app = QApplication.instance()
    if app:
        app.setStyleSheet(APP_QSS)
        current_font = app.font()
        base_size = current_font.pointSize() if current_font.pointSize() > 0 else 11
        app.setFont(build_app_font(base_size))


def _dialog_qss() -> str:
    return f"""
        QMessageBox {{
            background: {C_BG};
            color: {C_TEXT};
        }}
        QMessageBox QLabel {{
            background: transparent;
        }}
        QMessageBox QLabel#qt_msgbox_label {{
            color: {C_TEXT};
            font-size: {pt(12)}px;
            font-weight: 600;
            min-width: 360px;
            padding-right: 8px;
        }}
        QMessageBox QLabel#qt_msgbox_informativelabel {{
            color: {C_TEXT2};
            font-size: {pt(11)}px;
            min-width: 360px;
            line-height: 1.45;
        }}
        QMessageBox QPushButton {{
            background: rgba(255,255,255,0.05);
            border: none;
            border-radius: 8px;
            color: {C_TEXT};
            font-size: {pt(11)}px;
            font-weight: 600;
            padding: 0 {pt(18)}px;
            min-width: 110px;
            min-height: {pt(38)}px;
        }}
        QMessageBox QPushButton:hover {{
            background: rgba(255,255,255,0.10);
        }}
        QMessageBox QPushButton:pressed {{
            background: rgba(255,255,255,0.14);
        }}
        QMessageBox QPushButton:default {{
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #8DC21F, stop:1 #7AB317);
            color: #071200;
        }}
    """


class ThemedMessageBox(QDialog):
    _ICON_TEXT = {
        QMessageBox.Information: "i",
        QMessageBox.Warning: "!",
        QMessageBox.Critical: "✕",
        QMessageBox.Question: "?",
    }
    _ICON_STYLE = {
        QMessageBox.Information: (C_BLUE,   "rgba(61,142,240,0.14)"),
        QMessageBox.Warning:     (C_ORANGE, "rgba(245,166,35,0.14)"),
        QMessageBox.Critical:    (C_RED,    "rgba(229,62,62,0.14)"),
        QMessageBox.Question:    (C_GREEN,  "rgba(141,194,31,0.14)"),
    }
    _STANDARD_BUTTONS = (
        QMessageBox.Ok,
        QMessageBox.Yes,
        QMessageBox.No,
        QMessageBox.Cancel,
    )
    _STANDARD_TEXT = {
        QMessageBox.Ok:     "OK",
        QMessageBox.Yes:    "是",
        QMessageBox.No:     "否",
        QMessageBox.Cancel: "取消",
    }
    _ROLE_RESULT = {
        QMessageBox.AcceptRole:     QDialog.Accepted,
        QMessageBox.YesRole:        QMessageBox.Yes,
        QMessageBox.NoRole:         QMessageBox.No,
        QMessageBox.RejectRole:     QDialog.Rejected,
        QMessageBox.DestructiveRole: QDialog.Accepted,
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._title = ""
        self._icon = QMessageBox.Information
        self._clicked_button = None
        self._buttons: list[QPushButton] = []
        self._default_button = None
        self._result_value = QDialog.Rejected
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumWidth(pt(460))
        self.setMaximumWidth(pt(600))
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)   # 留出阴影空间
        outer.setSpacing(0)

        # ── 主卡片 ──────────────────────────────────────────────────
        self._card = QFrame(self)
        self._card.setObjectName("MsgCard")
        self._card.setStyleSheet(f"""
            QFrame#MsgCard {{
                background: {C_CARD};
                border: 1px solid rgba(255,255,255,0.09);
                border-top-color: rgba(255,255,255,0.15);
                border-radius: 12px;
            }}
        """)
        apply_shadow(self._card, blur=32, y=10, alpha=120)
        outer.addWidget(self._card)

        root = QVBoxLayout(self._card)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Body：图标 + 标题 + 正文 ────────────────────────────────
        body = QFrame()
        body.setObjectName("MsgBody")
        body.setStyleSheet("QFrame#MsgBody { background:transparent; border:none; }")
        b_lay = QHBoxLayout(body)
        b_lay.setContentsMargins(pt(24), pt(22), pt(20), pt(18))
        b_lay.setSpacing(pt(16))

        # 图标圆圈
        self._icon_label = QLabel("!")
        self._icon_label.setAlignment(Qt.AlignCenter)
        sz = pt(40)
        self._icon_label.setFixedSize(sz, sz)
        self._icon_label.setStyleSheet(f"""
            background: rgba(245,166,35,0.14);
            color: {C_ORANGE};
            border: none;
            border-radius: {sz // 2}px;
            font-size: {pt(18)}px;
            font-weight: 800;
        """)
        b_lay.addWidget(self._icon_label, 0, Qt.AlignTop)

        # 文字区
        text_col = QVBoxLayout()
        text_col.setSpacing(pt(6))
        text_col.setContentsMargins(0, pt(2), 0, 0)

        self._title_label = QLabel("")
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet(
            f"color:{C_TEXT}; font-size:{pt(13)}px; font-weight:700; "
            f"background:transparent; border:none;"
        )
        text_col.addWidget(self._title_label)

        self._text_label = QLabel("")
        self._text_label.setWordWrap(True)
        self._text_label.setStyleSheet(
            f"color:{C_TEXT2}; font-size:{pt(12)}px; font-weight:400; "
            f"background:transparent; border:none;"
        )
        text_col.addWidget(self._text_label)

        # 详情框（次要补充信息，无边框，仅换色区分）
        self._info_wrap = QFrame()
        self._info_wrap.setObjectName("InfoWrap")
        self._info_wrap.setStyleSheet(
            "QFrame#InfoWrap { background:transparent; border:none; }"
        )
        iw_lay = QVBoxLayout(self._info_wrap)
        iw_lay.setContentsMargins(0, pt(2), 0, 0)
        iw_lay.setSpacing(0)
        self._info_label = QLabel("")
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet(
            f"color:{C_TEXT3}; font-size:{pt(11)}px; background:transparent; border:none;"
        )
        iw_lay.addWidget(self._info_label)
        self._info_wrap.hide()
        text_col.addWidget(self._info_wrap)

        b_lay.addLayout(text_col, 1)
        root.addWidget(body)

        # ── Footer：按钮行 ──────────────────────────────────────────
        footer = QFrame()
        footer.setObjectName("MsgFooter")
        footer.setStyleSheet(f"""
            QFrame#MsgFooter {{
                background: transparent;
                border: none;
                border-top: 1px solid rgba(255,255,255,0.06);
            }}
        """)
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(pt(20), pt(12), pt(20), pt(14))
        f_lay.setSpacing(pt(10))
        f_lay.addStretch()
        self._button_layout = f_lay
        root.addWidget(footer)

    def setWindowTitle(self, title: str):
        self._title = title
        self._title_label.setText(title)
        return super().setWindowTitle(title)

    def setText(self, text: str):
        self._text_label.setText(text)

    def setInformativeText(self, text: str):
        self._info_label.setText(text)
        self._info_wrap.setVisible(bool(text))

    def setIcon(self, icon):
        self._icon = icon
        fg, bg = self._ICON_STYLE.get(icon, self._ICON_STYLE[QMessageBox.Information])
        sz = pt(40)
        self._icon_label.setText(self._ICON_TEXT.get(icon, "i"))
        self._icon_label.setStyleSheet(f"""
            background: {bg};
            color: {fg};
            border: none;
            border-radius: {sz // 2}px;
            font-size: {pt(18)}px;
            font-weight: 800;
        """)

    def _clear_buttons(self):
        while self._buttons:
            btn = self._buttons.pop()
            self._button_layout.removeWidget(btn)
            btn.deleteLater()
        self._clicked_button = None

    def _style_button(self, btn: QPushButton, *, primary: bool = False, danger: bool = False):
        if danger:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba(229,62,62,0.22), stop:1 rgba(180,30,30,0.18));
                    border: 1px solid rgba(229,62,62,0.28);
                    border-top-color: rgba(255,120,120,0.20);
                    border-radius: 10px;
                    color: #FF8B8B;
                    font-size: {pt(11)}px;
                    font-weight: 700;
                    padding: 0 18px;
                    min-width: 110px;
                    min-height: 38px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba(229,62,62,0.32), stop:1 rgba(180,30,30,0.28));
                    border-color: rgba(229,62,62,0.45);
                }}
            """)
            return
        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 #A0D428, stop:1 #7AB317);
                    border: 1px solid rgba(0,0,0,0.3);
                    border-top-color: rgba(180,240,60,0.45);
                    border-radius: 10px;
                    color: #0A1800;
                    font-size: {pt(11)}px;
                    font-weight: 700;
                    padding: 0 18px;
                    min-width: 110px;
                    min-height: 38px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 #B0E030, stop:1 #8DC21F);
                }}
            """)
            return
        btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.09);
                border-top-color: rgba(255,255,255,0.14);
                border-radius: 10px;
                color: {C_TEXT};
                font-size: {pt(11)}px;
                font-weight: 600;
                padding: 0 18px;
                min-width: 110px;
                min-height: 38px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10);
                border-color: rgba(255,255,255,0.18);
            }}
        """)

    def _connect_button(self, btn: QPushButton, result_value: int):
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self._finish(btn, result_value))

    def _finish(self, btn: QPushButton, result_value: int):
        self._clicked_button = btn
        self._result_value = result_value
        self.done(result_value)

    def addButton(self, button, role=None):
        if isinstance(button, QPushButton):
            btn = button
            result_value = self._ROLE_RESULT.get(role, QDialog.Accepted)
        else:
            btn = QPushButton(str(button), self._card)
            result_value = self._ROLE_RESULT.get(role, QDialog.Accepted)
        is_primary = role in (QMessageBox.AcceptRole, QMessageBox.YesRole)
        is_danger = role == QMessageBox.DestructiveRole
        self._style_button(btn, primary=is_primary, danger=is_danger)
        self._connect_button(btn, result_value)
        self._button_layout.addWidget(btn)
        self._buttons.append(btn)
        return btn

    def setStandardButtons(self, buttons):
        self._clear_buttons()
        for code in self._STANDARD_BUTTONS:
            if buttons & code:
                btn = QPushButton(self._STANDARD_TEXT.get(code, str(code)), self._card)
                primary = code in (QMessageBox.Ok, QMessageBox.Yes)
                self._style_button(btn, primary=primary)
                self._connect_button(btn, code)
                self._button_layout.addWidget(btn)
                self._buttons.append(btn)

    def setDefaultButton(self, button):
        target = button
        if isinstance(button, int):
            target = None
            for btn in self._buttons:
                if btn.text() == self._STANDARD_TEXT.get(button):
                    target = btn
                    break
        self._default_button = target
        if target in self._buttons:
            for btn in self._buttons:
                self._style_button(btn, primary=(btn is target))

    def buttons(self):
        return list(self._buttons)

    def clickedButton(self):
        return self._clicked_button

    def exec_(self):
        self._reposition()
        return super().exec_()

    def _reposition(self):
        self.adjustSize()
        screen = QApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)
        max_w = int(geo.width() * 0.90)
        max_h = int(geo.height() * 0.85)
        if self.width() > max_w or self.height() > max_h:
            self.resize(min(self.width(), max_w), min(self.height(), max_h))
        # 用 mapToGlobal 获取父窗口在屏幕上的真实中心坐标
        if self.parentWidget() is not None:
            p = self.parentWidget()
            center = p.mapToGlobal(p.rect().center())
            x = center.x() - self.width() // 2
            y = center.y() - self.height() // 2
        else:
            x = geo.center().x() - self.width() // 2
            y = geo.center().y() - self.height() // 2
        x = max(geo.x() + 12, min(x, geo.right()  - self.width()  - 12))
        y = max(geo.y() + 12, min(y, geo.bottom() - self.height() - 12))
        self.move(x, y)

    def reject(self):
        self._result_value = QMessageBox.Cancel
        return super().reject()


def create_themed_message_box(
    parent: QWidget | None,
    title: str,
    text: str,
    *,
    icon=QMessageBox.Information,
    informative_text: str = "",
    buttons=QMessageBox.Ok,
    default_button=None,
) -> ThemedMessageBox:
    msg = ThemedMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setIcon(icon)
    msg.setText(text)
    if informative_text:
        msg.setInformativeText(informative_text)
    msg.setStandardButtons(buttons)
    if default_button is not None:
        msg.setDefaultButton(default_button)
    return msg


def show_info_message(parent: QWidget | None, title: str, text: str, informative_text: str = "") -> int:
    return create_themed_message_box(
        parent, title, text,
        icon=QMessageBox.Information,
        informative_text=informative_text,
    ).exec_()


def show_warning_message(parent: QWidget | None, title: str, text: str, informative_text: str = "") -> int:
    return create_themed_message_box(
        parent, title, text,
        icon=QMessageBox.Warning,
        informative_text=informative_text,
    ).exec_()


def show_error_message(parent: QWidget | None, title: str, text: str, informative_text: str = "") -> int:
    return create_themed_message_box(
        parent, title, text,
        icon=QMessageBox.Critical,
        informative_text=informative_text,
    ).exec_()


def ask_question_message(
    parent: QWidget | None,
    title: str,
    text: str,
    *,
    informative_text: str = "",
    buttons=QMessageBox.Yes | QMessageBox.No,
    default_button=QMessageBox.No,
) -> int:
    return create_themed_message_box(
        parent, title, text,
        icon=QMessageBox.Question,
        informative_text=informative_text,
        buttons=buttons,
        default_button=default_button,
    ).exec_()


# ── 自定义下拉选择器（替代 QComboBox，解决 Linux 下 popup 无法限高的问题）────────

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QListWidget, QListWidgetItem


class DropdownButton(QWidget):
    """点击后在按钮正下方弹出固定高度的列表，带滚动条，跨平台一致。"""

    currentTextChanged = pyqtSignal(str)

    def __init__(self, parent=None, max_popup_height: int = 300):
        super().__init__(parent)
        self._items: list[str] = []
        self._data: dict[str, object] = {}   # label -> user data
        self._current: str = ""
        self._max_h = max_popup_height
        self._popup: QWidget | None = None
        self._list: QListWidget | None = None

        self._btn = QPushButton("", self)
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.clicked.connect(self._toggle_popup)
        self._btn.setStyleSheet(self._btn_style())

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._btn)

    # ── public API ──────────────────────────────────────────────────────────

    def addItems(self, items: list[str]):
        self._items = list(items)
        if self._items and not self._current:
            self._set_current(self._items[0])
        elif self._items and self._current not in self._items:
            self._set_current(self._items[0])
        if self._list is not None:
            self._list.clear()
            for item in self._items:
                self._list.addItem(QListWidgetItem(item))

    def addItem(self, label: str, data: object = None):
        self._items.append(label)
        if data is not None:
            self._data[label] = data
        if len(self._items) == 1:
            self._set_current(label)
        if self._list is not None:
            self._list.addItem(QListWidgetItem(label))

    def clear(self):
        self._items = []
        self._data = {}
        self._current = ""
        self._btn.setText("  ▾")
        if self._list is not None:
            self._list.clear()

    def count(self) -> int:
        return len(self._items)

    def itemData(self, index: int) -> object:
        if 0 <= index < len(self._items):
            return self._data.get(self._items[index])
        return None

    def setCurrentIndex(self, index: int):
        if 0 <= index < len(self._items):
            self._set_current(self._items[index])

    def blockSignals(self, block: bool) -> bool:
        return super().blockSignals(block)

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._btn.setEnabled(enabled)

    def currentText(self) -> str:
        return self._current

    def setCurrentText(self, text: str):
        if text in self._items:
            self._set_current(text)

    def setMinimumWidth(self, w: int):
        super().setMinimumWidth(w)
        self._btn.setMinimumWidth(w)

    # ── internals ───────────────────────────────────────────────────────────

    def _set_current(self, text: str):
        self._current = text
        self._btn.setText(f"  {text}  ▾")
        if not self.signalsBlocked():
            self.currentTextChanged.emit(text)

    def _btn_style(self) -> str:
        return (
            f"QPushButton {{"
            f" background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"   stop:0 #1E2D40, stop:1 {C_CARD_LIGHT});"
            f" border: 1px solid rgba(255,255,255,0.10);"
            f" border-top-color: rgba(255,255,255,0.16);"
            f" border-radius: 10px;"
            f" color: {C_TEXT};"
            f" font-size: {pt(12)}px;"
            f" text-align: left;"
            f" padding: 0 {pt(12)}px;"
            f" min-height: {pt(36)}px;"
            f"}}"
            f" QPushButton:hover {{ border-color: rgba(255,255,255,0.22); }}"
            f" QPushButton:pressed {{ background: {C_CARD_LIGHT}; }}"
        )

    def _toggle_popup(self):
        if self._popup and self._popup.isVisible():
            self._popup.hide()
            return
        self._show_popup()

    def _show_popup(self):
        if self._popup is None:
            self._popup = QWidget(self.window(), Qt.Popup | Qt.FramelessWindowHint)
            self._popup.setAttribute(Qt.WA_StyledBackground, True)
            self._popup.setStyleSheet(
                f"background:{C_CARD_LIGHT}; border:1px solid rgba(255,255,255,0.12);"
                f" border-radius:10px;"
            )
            pop_lay = QVBoxLayout(self._popup)
            pop_lay.setContentsMargins(4, 4, 4, 4)
            pop_lay.setSpacing(0)

            self._list = QListWidget()
            self._list.setStyleSheet(
                f"QListWidget {{ background:transparent; border:none; color:{C_TEXT};"
                f" font-size:{pt(13)}px; outline:none; }}"
                f" QListWidget::item {{ padding:{pt(7)}px {pt(12)}px; border-radius:6px; }}"
                f" QListWidget::item:hover {{ background:rgba(255,255,255,0.08); }}"
                f" QListWidget::item:selected {{ background:rgba(141,194,31,0.18); color:{C_GREEN}; }}"
                f" QScrollBar:vertical {{ background:transparent; width:{pt(6)}px; }}"
                f" QScrollBar::handle:vertical {{ background:rgba(255,255,255,0.20);"
                f"   border-radius:{pt(3)}px; min-height:{pt(20)}px; }}"
                f" QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}"
            )
            for item in self._items:
                self._list.addItem(QListWidgetItem(item))
            self._list.itemClicked.connect(self._on_item_clicked)
            pop_lay.addWidget(self._list)

        # 选中当前项
        for i in range(self._list.count()):
            self._list.item(i).setSelected(self._list.item(i).text() == self._current)

        # 定位到按钮正下方
        btn_global = self._btn.mapToGlobal(self._btn.rect().bottomLeft())
        w = max(self._btn.width(), pt(260))
        h = min(self._max_h, self._list.sizeHintForRow(0) * len(self._items) + 12)
        self._popup.setFixedWidth(w)
        self._popup.setFixedHeight(h)
        self._popup.move(btn_global)
        self._popup.show()
        self._popup.raise_()

    def _on_item_clicked(self, item: QListWidgetItem):
        self._set_current(item.text())
        if self._popup:
            self._popup.hide()

    def hideEvent(self, event):
        if self._popup:
            self._popup.hide()
        super().hideEvent(event)
