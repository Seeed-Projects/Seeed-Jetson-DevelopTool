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

from PyQt5.QtCore import Qt, QRect, QPoint, QPointF, QTimer
from PyQt5.QtGui import QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QDialog, QFrame, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QScrollArea, QWidget, QVBoxLayout,
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


# Emoji 字体栈：强制彩色 emoji 显示，避免 Linux 上 fallback 为黑白
# 仅在非 Windows 平台添加，Windows 系统不安装此字体
def _emoji_font_stack() -> str:
    base = pick_font_family(UI_FONT_CANDIDATES)
    if sys.platform != "win32":
        return f'"Noto Color Emoji", {base}'
    return base


def _set_emoji_font(lbl: QLabel, size: int | None = None):
    """为包含 emoji 的 QLabel 设置彩色 emoji 字体（不影响布局）。"""
    if sys.platform == "win32":
        return
    emoji_font = QFont("Noto Color Emoji")
    if size is not None:
        emoji_font.setPointSize(size)
    lbl.setFont(emoji_font)


# ── 通用组件工厂 ──────────────────────────────────────────────────────────────
def _has_emoji(text: str) -> bool:
    """检测字符串是否包含 emoji（非 ASCII 可见字符）。"""
    import re
    return bool(re.search(r"[\U0001F000-\U0001FFFF\u2600-\u27BF\u2300-\u23FF\u2B50]", text))


def set_emoji_font_for_label(lbl: QLabel, size_pt: int | None = None):
    """为已创建的 QLabel 设置彩色 emoji 字体（如果含 emoji）。"""
    if sys.platform == "win32":
        return
    text = lbl.text()
    if text and _has_emoji(text):
        f = QFont("Noto Color Emoji")
        if size_pt is not None:
            f.setPointSize(size_pt)
        lbl.setFont(f)


def make_label(text: str, size: int = 13, color: str = C_TEXT,
               bold: bool = False, wrap: bool = False) -> QLabel:
    """创建标签 - 无背景，纯文字"""
    lbl = QLabel(text)
    weight = 700 if bold else 400
    font = build_app_font()
    font.setPixelSize(pt(size))
    font.setWeight(weight)
    lbl.setFont(font)
    lbl.setStyleSheet(
        f"color:{color}; font-size:{pt(size)}px; font-weight:{weight}; "
        f"background:transparent; border:none;"
    )
    if wrap:
        lbl.setWordWrap(True)
    if text and _has_emoji(text):
        _set_emoji_font(lbl, size)
    return lbl


class RippleButton(QPushButton):
    """带涟漪点击反馈 + 按压缩放的按钮

    点击时在按钮表面产生 Material Design 风格的扩散涟漪，
    同时保留按压瞬间缩小 padding 的物理反馈。
    原理：QTimer 驱动半径增长 → paintEvent 在 super().paintEvent() 之上叠加半透明圆环。
    不涉及 QGraphicsEffect / Layout，100% 安全。
    """
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._ripples = []
        self._ripple_timer = QTimer(self)
        self._ripple_timer.timeout.connect(self._tick)

    def mousePressEvent(self, event):
        # 涟漪效果
        max_r = max(self.width(), self.height()) * 1.3
        self._ripples.append({
            "cx": event.x(), "cy": event.y(),
            "radius": 0.0, "max_radius": max_r,
            "speed": max_r / 10.0,
            "opacity": 0.28, "fade": 0.28 / 14.0,
        })
        if not self._ripple_timer.isActive():
            self._ripple_timer.start(16)

        # 按压瞬间缩小 padding
        ss = self.styleSheet()
        self._normal_ss = ss
        self.setStyleSheet(ss.replace(f'padding: 0 {pt(24)}px', f'padding: 0 {pt(26)}px')
                              .replace(f'padding: 0 {pt(20)}px', f'padding: 0 {pt(22)}px')
                              .replace(f'padding: 0 {pt(16)}px', f'padding: 0 {pt(18)}px'))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if hasattr(self, '_normal_ss'):
            self.setStyleSheet(self._normal_ss)
        super().mouseReleaseEvent(event)

    def _tick(self):
        try:
            alive = []
            for r in self._ripples:
                r["radius"] += r["speed"]
                r["opacity"] -= r["fade"]
                if r["opacity"] > 0:
                    alive.append(r)
            self._ripples = alive
            if not alive:
                self._ripple_timer.stop()
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._ripples:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for r in self._ripples:
            alpha = int(255 * r["opacity"])
            if alpha <= 0:
                continue
            radius = r["radius"]
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, int(alpha * 0.4)))
            p.drawEllipse(int(r["cx"] - radius), int(r["cy"] - radius),
                          int(radius * 2), int(radius * 2))
            inner_r = radius * 0.7
            p.setBrush(QColor(255, 255, 255, int(alpha * 0.7)))
            p.drawEllipse(int(r["cx"] - inner_r), int(r["cy"] - inner_r),
                          int(inner_r * 2), int(inner_r * 2))


def make_button(text: str, primary: bool = False,
                small: bool = False, danger: bool = False) -> QPushButton:
    """创建按钮 - 带涟漪点击反馈、按压缩放和主题样式"""
    b = RippleButton(text)
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


class HoverCard(QFrame):
    """带悬浮阴影的卡片

    hover 时阴影直接切换为较大值（无动画过渡），避免 QGraphicsDropShadowEffect
    与 QTimer 快速重绘在 Windows 下触发 painter 冲突导致段错误。
    """
    def __init__(self, radius: int = 12, with_shadow: bool = True, parent=None):
        super().__init__(parent)
        self._radius = radius
        self.setObjectName("SeeedCard")
        self.setStyleSheet(f"""
            QFrame#SeeedCard {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #1E2D40, stop:1 {C_CARD});
                border: none;
                border-radius: {radius}px;
            }}
            QFrame#SeeedCard:hover {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #24354A, stop:1 {C_CARD_HOVER});
                border: none;
            }}
        """)
        self._shadow = None
        if with_shadow:
            self._setup_shadow()

    def _setup_shadow(self):
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(28)
        self._shadow.setOffset(QPointF(0, 6))
        self._shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(self._shadow)
        self._shadow_effect = self._shadow  # 兼容 clear_shadow

    def enterEvent(self, event):
        try:
            if self._shadow is not None:
                self._shadow.setBlurRadius(42)
                self._shadow.setOffset(QPointF(0, 10))
                self._shadow.setColor(QColor(0, 0, 0, 100))
        except RuntimeError:
            self._shadow = None
        super().enterEvent(event)

    def leaveEvent(self, event):
        try:
            if self._shadow is not None:
                self._shadow.setBlurRadius(28)
                self._shadow.setOffset(QPointF(0, 6))
                self._shadow.setColor(QColor(0, 0, 0, 80))
        except RuntimeError:
            self._shadow = None
        super().leaveEvent(event)


def make_card(radius: int = 12, with_shadow: bool = True) -> QFrame:
    """创建卡片 - 带高光顶边、立体阴影和 hover 阴影呼吸动画"""
    return HoverCard(radius=radius, with_shadow=with_shadow)


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


def clear_shadow(w):
    """清除 widget 上的阴影效果，防止 deleteLater 后泄漏"""
    fx = getattr(w, "_shadow_effect", None)
    if fx is not None:
        w.setGraphicsEffect(None)
        try:
            fx.deleteLater()
        except RuntimeError:
            pass


def apply_shadow(w, blur: int = 20, y: int = 4, alpha: int = 60):
    """添加柔和阴影"""
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(blur)
    fx.setOffset(0, y)
    fx.setColor(QColor(0, 0, 0, alpha))
    w._shadow_effect = fx  # 记录引用，clear_shadow 时可正确清理
    w.setGraphicsEffect(fx)
    return w


def apply_glow(w, color: str = C_GREEN):
    """添加发光效果（用于选中状态）"""
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(15)
    fx.setOffset(0, 0)
    fx.setColor(QColor(int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16), 80))
    w._shadow_effect = fx
    w.setGraphicsEffect(fx)
    return w


class AnimatedTabButton(QPushButton):
    """带动画下划线的标签按钮

    选中时底部绿色下划线从中间向两边展开，取消选中时收缩。
    原理：QTimer 驱动 underline_progress → paintEvent 绘制下划线。
    """
    def __init__(self, text: str, active: bool = False, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._active = active
        self._underline_progress = 1.0 if active else 0.0
        self._target_progress = 1.0 if active else 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._apply_style()

    def _apply_style(self):
        # 选中态：无背景块，仅用文字颜色 + 底部下划线标识，更 subtle
        color = C_GREEN if self._active else C_TEXT2
        weight = "500" if self._active else "400"
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {color};
                border: none;
                border-radius: 0px;
                padding: 0px {pt(18)}px;
                font-size: {pt(14)}px;
                font-weight: {weight};
                min-height: {pt(36)}px;
                text-align: center;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.04); color:{C_TEXT}; }}
        """)

    def setActive(self, active: bool):
        if self._active == active:
            return
        self._active = active
        self._target_progress = 1.0 if active else 0.0
        self._apply_style()
        if not self._timer.isActive():
            self._timer.start(16)

    def _tick(self):
        try:
            step = 0.18
            if self._target_progress > self._underline_progress:
                self._underline_progress = min(self._target_progress, self._underline_progress + step)
            elif self._target_progress < self._underline_progress:
                self._underline_progress = max(self._target_progress, self._underline_progress - step)
            else:
                self._timer.stop()
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, event):
        # 下划线由外部 _tab_slider 统一绘制，避免与跨按钮滑块重叠
        super().paintEvent(event)


def make_tab_button(text: str, active: bool = False) -> "QPushButton":
    """创建分类筛选标签按钮（带动画下划线）"""
    return AnimatedTabButton(text, active=active)


class ShinyProgressBar(QProgressBar):
    """带流动光泽的进度条，支持动态改色。

    默认绿色，可调用 set_color() 切换为蓝/橙/绿等，下载/上传/执行各阶段视觉区分。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._shine_pos = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self.setTextVisible(False)
        self._top_color = QColor(176, 224, 48)
        self._bottom_color = QColor(122, 179, 23)

    def set_color(self, top: QColor | str, bottom: QColor | str | None = None):
        """动态改变进度条颜色，top/bottom 可以是 QColor 或 #RRGGBB 字符串。"""
        if isinstance(top, str):
            top = QColor(top)
        if bottom is None:
            bottom = top.darker(120)
        elif isinstance(bottom, str):
            bottom = QColor(bottom)
        self._top_color = top
        self._bottom_color = bottom
        self.update()

    def _tick(self):
        try:
            self._shine_pos = (self._shine_pos + 0.02) % 1.0
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        val = self.value()
        min_v, max_v = self.minimum(), self.maximum()
        progress = 0.0 if max_v <= min_v else (val - min_v) / (max_v - min_v)
        radius = h // 2

        # 背景条
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 50))
        p.drawRoundedRect(0, 0, w, h, radius, radius)

        # 进度 chunk
        chunk_w = int((w - 4) * progress)
        if chunk_w > 2:
            chunk_grad = QLinearGradient(0, 0, 0, h)
            chunk_grad.setColorAt(0, self._top_color)
            chunk_grad.setColorAt(1, self._bottom_color)
            p.setBrush(chunk_grad)
            p.drawRoundedRect(2, 2, chunk_w, h - 4, (h - 4) // 2, (h - 4) // 2)

            # 流动光泽
            shine_w = min(50, chunk_w)
            shine_x = int(chunk_w * self._shine_pos - shine_w // 2) + 2
            if shine_x + shine_w > 2 and shine_x < chunk_w + 2:
                shine_grad = QLinearGradient(shine_x, 0, shine_x + shine_w, 0)
                shine_grad.setColorAt(0, QColor(255, 255, 255, 0))
                shine_grad.setColorAt(0.5, QColor(255, 255, 255, 120))
                shine_grad.setColorAt(1, QColor(255, 255, 255, 0))
                p.setBrush(shine_grad)
                # 限制在 chunk 区域内
                p.save()
                p.setClipRect(2, 2, chunk_w, h - 4)
                p.drawRoundedRect(shine_x, 2, shine_w, h - 4, (h - 4) // 2, (h - 4) // 2)
                p.restore()


def make_input_field(placeholder: str = "", multiline: bool = False) -> "QWidget":
    """创建统一样式的输入框（单行 FocusRippleLineEdit 或多行 QTextEdit）"""
    from PyQt5.QtWidgets import QTextEdit
    if multiline:
        w = QTextEdit()
        w.setPlaceholderText(placeholder)
    else:
        from seeed_jetson_develop.gui.widgets.focus_ripple_edit import FocusRippleLineEdit
        w = FocusRippleLineEdit()
        w.setPlaceholderText(placeholder)
    w.setStyleSheet(input_qss())
    return w


def input_qss(radius: int = 8, font_size: int = 12) -> str:
    """返回统一的 QLineEdit 样式字符串，供各模块内联 setStyleSheet 使用。
    使用深色背景 + 明显边框，确保输入框在深色主题下清晰可辨。
    """
    return (
        f"QLineEdit {{"
        f" background:#0D1520;"
        f" border:1px solid rgba(255,255,255,0.18);"
        f" border-radius:{radius}px;"
        f" padding:8px 14px;"
        f" color:{C_TEXT};"
        f" font-size:{pt(font_size)}px;"
        f" selection-background-color:rgba(141,194,31,0.25);"
        f"}}"
        f" QLineEdit:hover {{"
        f" border-color:rgba(255,255,255,0.30);"
        f" background:#0F1825;"
        f"}}"
        f" QLineEdit:focus {{"
        f" border-color:{C_BORDER_FOCUS};"
        f" background:#0D1520;"
        f"}}"
        f" QLineEdit:disabled {{"
        f" color:{C_TEXT3};"
        f" border-color:rgba(255,255,255,0.07);"
        f" background:#111820;"
        f"}}"
    )


# ── 应用级 QSS（惰性求值，避免 QApplication 创建前调用 QFontDatabase）─────────
def get_app_qss() -> str:
    base_font = pick_font_family(UI_FONT_CANDIDATES)
    return f"""
/* 全局滚动条 - 带圆角和悬停高亮 */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px 2px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.10);
    border-radius: 4px;
    min-height: 48px;
    border: 1px solid rgba(255,255,255,0.04);
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(141,194,31,0.40);
    border-color: rgba(141,194,31,0.25);
}}
QScrollBar::handle:vertical:pressed {{
    background: rgba(141,194,31,0.65);
    border-color: rgba(141,194,31,0.40);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 2px 4px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(255,255,255,0.10);
    border-radius: 4px;
    min-width: 48px;
    border: 1px solid rgba(255,255,255,0.04);
}}
QScrollBar::handle:horizontal:hover {{
    background: rgba(141,194,31,0.40);
    border-color: rgba(141,194,31,0.25);
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
        stop:0 {C_GREEN2}, stop:0.4 #B0E040, stop:0.6 #A0D428, stop:1 {C_GREEN});
    border-radius: 4px;
    border: 1px solid rgba(200,255,100,0.20);
    border-left: none; border-right: none;
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
    border-top-color: rgba(141,194,31,0.25);
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #0F1A0A, stop:1 #111A28);
}}

QLineEdit {{
    background: #0D1520;
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 8px;
    padding: 8px 14px;
    color: {C_TEXT};
    font-size: {pt(12)}px;
    selection-background-color: rgba(141,194,31,0.25);
}}
QLineEdit:hover {{
    border-color: rgba(255,255,255,0.30);
    background: #0F1825;
}}
QLineEdit:focus {{
    border-color: {C_BORDER_FOCUS};
    border-top-color: rgba(141,194,31,0.35);
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #0F1A0A, stop:1 #0D1520);
}}
QLineEdit:disabled {{
    color: {C_TEXT3};
    border-color: rgba(255,255,255,0.07);
    background: #111820;
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
        app.setStyleSheet(get_app_qss())
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

    def currentData(self) -> object:
        return self._data.get(self._current)

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

        # 滑入动画：从上方 10px 处滑落到最终位置
        final_pos = btn_global
        start_pos = QPoint(final_pos.x(), final_pos.y() - 10)
        self._popup.move(start_pos)
        self._popup.show()
        self._popup.raise_()

        from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
        anim = QPropertyAnimation(self._popup, b"pos")
        anim.setDuration(180)
        anim.setStartValue(start_pos)
        anim.setEndValue(final_pos)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._popup._anim = anim  # 保持引用防止 GC

    def _on_item_clicked(self, item: QListWidgetItem):
        self._set_current(item.text())
        if self._popup:
            self._popup.hide()

    def hideEvent(self, event):
        if self._popup:
            self._popup.hide()
        super().hideEvent(event)
