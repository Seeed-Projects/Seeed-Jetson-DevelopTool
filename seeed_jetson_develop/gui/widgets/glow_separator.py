"""
GlowSeparator — 微光分割线

用渐变 QLabel 代替生硬的纯色分割线，营造更有层次感的光效。
纯样式表实现，100% 安全。
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel

from seeed_jetson_develop.gui.theme import C_GREEN, pt


def make_glow_separator(parent=None, width: int = None, height: int = 1) -> QLabel:
    """创建水平微光分割线。中间亮、两端渐隐。"""
    lbl = QLabel(parent)
    h = pt(height)
    lbl.setFixedHeight(h)
    if width:
        lbl.setFixedWidth(pt(width))
    lbl.setStyleSheet(f"""
        QLabel {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 transparent,
                stop:0.15 rgba(141,194,31,0.25),
                stop:0.50 rgba(141,194,31,0.45),
                stop:0.85 rgba(141,194,31,0.25),
                stop:1 transparent);
            border: none;
            border-radius: {h // 2}px;
        }}
    """)
    return lbl


def make_subtle_separator(parent=None, width: int = None) -> QLabel:
    """创建更柔和的白色微光分割线。"""
    lbl = QLabel(parent)
    h = pt(1)
    lbl.setFixedHeight(h)
    if width:
        lbl.setFixedWidth(pt(width))
    lbl.setStyleSheet(f"""
        QLabel {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 transparent,
                stop:0.10 rgba(255,255,255,0.04),
                stop:0.50 rgba(255,255,255,0.10),
                stop:0.90 rgba(255,255,255,0.04),
                stop:1 transparent);
            border: none;
            border-radius: {h // 2}px;
        }}
    """)
    return lbl
