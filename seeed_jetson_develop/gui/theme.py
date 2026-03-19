"""集中主题定义 — 无边框、大气上位机风格

设计理念：
- 用背景色层次代替边框
- 用阴影代替硬边框
- 用留白代替分隔线
- 深色科技风，符合上位机气质
"""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect,
    QLabel, QPushButton, QWidget, QVBoxLayout,
)

# ── 颜色系统 ──────────────────────────────────────────────────────────────────
# 背景层次：从深到浅
C_BG_DEEP   = "#080C12"   # 最深背景（标题栏、侧边栏顶部）
C_BG        = "#0D1218"   # 主背景
C_BG_LIGHT  = "#111820"   # 内容区背景

# 卡片层次：从深到浅  
C_CARD      = "#151D26"   # 主卡片
C_CARD_HOVER= "#1A232E"   # 卡片悬停
C_CARD_LIGHT= "#1E2933"   # 次级卡片/输入框背景

# 强调色
C_GREEN     = "#7AB317"   # Seeed 绿（更沉稳）
C_GREEN2    = "#6BA30F"   # 深绿
C_GREEN_GLOW= "rgba(122,179,23,0.15)"  # 绿色光晕

C_BLUE      = "#2C7BE5"
C_ORANGE    = "#F5A623"
C_RED       = "#E53E3E"

# 文字颜色
C_TEXT      = "#F0F4F8"   # 主文字
C_TEXT2     = "#94A3B0"   # 次级文字
C_TEXT3     = "#5A6B7A"   # 辅助文字

# ── DPI-aware 字体缩放 ────────────────────────────────────────────────────────
def pt(px: int) -> int:
    """返回字体大小（px），stylesheet 中用 px 单位更可靠。
    保留函数名兼容现有调用，但直接返回 px 值（最小 10）。
    """
    return max(10, px)


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
    """创建按钮 - 无边框，用背景色区分"""
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    
    h  = pt(36) if small else pt(42)
    fs = pt(11) if small else pt(12)
    
    if primary:
        # 主按钮：绿色渐变，无实线边框
        b.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #8DC21F, stop:1 #7AB317);
                border: none;
                border-radius: 8px;
                color: #071200;
                font-size: {fs}px;
                font-weight: 600;
                padding: 0 {pt(24)}px;
                min-height: {h}px;
            }}
            QPushButton:hover {{ 
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #9CD62F, stop:1 #8BC520);
            }}
            QPushButton:pressed {{ background: #6BA30F; }}
            QPushButton:disabled {{ 
                background: #1A232E; 
                color: #5A6B7A; 
            }}
        """)
    elif danger:
        # 危险按钮：红色背景，无边框
        b.setStyleSheet(f"""
            QPushButton {{
                background: rgba(229,62,62,0.12);
                border: none;
                border-radius: 8px;
                color: #FF6B6B;
                font-size: {fs}px;
                font-weight: 600;
                padding: 0 {pt(20)}px;
                min-height: {h}px;
            }}
            QPushButton:hover {{ background: rgba(229,62,62,0.20); }}
            QPushButton:pressed {{ background: rgba(229,62,62,0.28); }}
        """)
    else:
        # 普通按钮：透明背景，悬停变亮
        b.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 8px;
                color: {C_TEXT2};
                font-size: {fs}px;
                font-weight: 500;
                padding: 0 {pt(16)}px;
                min-height: {h}px;
            }}
            QPushButton:hover {{ 
                background: rgba(255,255,255,0.06); 
                color: {C_TEXT};
            }}
            QPushButton:pressed {{ background: rgba(255,255,255,0.10); }}
        """)
    return b


def make_card(radius: int = 12, with_shadow: bool = True) -> QFrame:
    """创建卡片 - 无边框，用背景色和阴影区分层次"""
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background: {C_CARD};
            border: none;
            border-radius: {radius}px;
        }}
    """)
    if with_shadow:
        apply_shadow(f, blur=20, y=4, alpha=60)
    return f


def make_input_card(radius: int = 10) -> QFrame:
    """创建输入框容器 - 稍浅的背景"""
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background: {C_CARD_LIGHT};
            border: none;
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


# ── 应用级 QSS ────────────────────────────────────────────────────────────────
APP_QSS = f"""
/* 全局滚动条 - 极简 */
QScrollBar:vertical {{
    background: transparent;
    width: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #2A3A4A;
    border-radius: 2px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{
    background: #3A4A5A;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 4px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: #2A3A4A;
    border-radius: 2px;
    min-width: 40px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #3A4A5A;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* 下拉框 - 无边框，背景色区分 */
QComboBox {{
    background: {C_CARD_LIGHT};
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    color: {C_TEXT};
    min-height: {pt(20)}px;
}}
QComboBox:hover {{ background: #253340; }}
QComboBox:focus {{ 
    background: {C_CARD_LIGHT};
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    width: 8px; height: 8px;
    border-left: 2px solid {C_TEXT3};
    border-bottom: 2px solid {C_TEXT3};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {C_CARD_LIGHT};
    border: none;
    border-radius: 8px;
    selection-background-color: rgba(122,179,23,0.15);
    selection-color: {C_GREEN};
    color: {C_TEXT};
    outline: none;
    padding: 6px;
}}

/* 复选框 - 极简 */
QCheckBox {{
    color: {C_TEXT2};
    spacing: 10px;
    font-size: {pt(12)}px;
}}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border-radius: 5px;
    background: {C_CARD_LIGHT};
    border: none;
}}
QCheckBox::indicator:hover {{
    background: #253340;
}}
QCheckBox::indicator:checked {{
    background: {C_GREEN};
    image: none;
}}

/* 进度条 - 无边框 */
QProgressBar {{
    background: {C_CARD_LIGHT};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C_GREEN}, stop:1 {C_GREEN2});
    border-radius: 4px;
}}

/* 文本输入 - 背景色区分 */
QTextEdit {{
    background: {C_CARD_LIGHT};
    border: none;
    border-radius: 10px;
    color: {C_TEXT2};
    padding: 14px;
    font-family: "JetBrains Mono", "Consolas", "Courier New", monospace;
    font-size: {pt(11)}px;
    selection-background-color: rgba(122,179,23,0.25);
}}
QTextEdit:focus {{
    background: {C_CARD};
}}

QLineEdit {{
    background: {C_CARD_LIGHT};
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    color: {C_TEXT};
    font-size: {pt(12)}px;
    selection-background-color: rgba(122,179,23,0.25);
}}
QLineEdit:focus {{
    background: {C_CARD};
}}
QLineEdit:hover {{
    background: #253340;
}}

/* 工具提示 */
QToolTip {{
    background: {C_CARD};
    border: none;
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
