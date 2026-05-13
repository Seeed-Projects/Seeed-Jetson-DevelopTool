"""
EmptyStateWidget — 空状态插图

当列表/页面无数据时，显示精美的几何风格插图 + 引导文案。
使用 QPainter 绘制，无需外部图片资源。
"""
import math

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QFont, QPen, QBrush, QLinearGradient
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

from seeed_jetson_develop.gui.theme import C_BG, C_CARD, C_GREEN, C_TEXT2, C_TEXT3, pt


class EmptyStateWidget(QWidget):
    """空状态组件：几何风格插图 + 文案"""

    def __init__(self, title: str = "", subtitle: str = "", icon_type: str = "box", parent=None):
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._icon_type = icon_type
        self._time = 0.0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(pt(40), pt(32), pt(40), pt(32))
        layout.setSpacing(pt(16))
        layout.setAlignment(Qt.AlignCenter)

        # 插图区域
        self._canvas = _EmptyStateCanvas(self._icon_type, self)
        self._canvas.setFixedSize(pt(180), pt(140))
        layout.addWidget(self._canvas, alignment=Qt.AlignCenter)

        # 标题
        if self._title:
            title_lbl = QLabel(self._title)
            title_lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:{pt(15)}px; font-weight:600; background:transparent;")
            title_lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(title_lbl)

        # 副标题
        if self._subtitle:
            sub_lbl = QLabel(self._subtitle)
            sub_lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}px; background:transparent;")
            sub_lbl.setAlignment(Qt.AlignCenter)
            sub_lbl.setWordWrap(True)
            sub_lbl.setMaximumWidth(pt(400))
            layout.addWidget(sub_lbl)

        layout.addStretch()


class _EmptyStateCanvas(QWidget):
    """空状态插图画布 — 用 QPainter 绘制几何图形，带缓慢飘动动画"""

    ICONS = {
        "box":    "box",      # 空盒子
        "search": "search",   # 搜索放大镜
        "wifi":   "wifi",     # 断开连接
        "tools":  "tools",     # 工具
    }

    def __init__(self, icon_type: str, parent=None):
        super().__init__(parent)
        self._icon_type = icon_type
        self.setStyleSheet("background:transparent;")
        self._time = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _tick(self):
        self._time = (self._time + 0.006) % 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2

        # 整体轻微上下浮动
        float_y = int(math.sin(self._time * math.pi * 2) * 3)

        if self._icon_type == "box":
            self._draw_box(painter, cx, cy + float_y, w, h)
        elif self._icon_type == "search":
            self._draw_search(painter, cx, cy + float_y, w, h)
        elif self._icon_type == "wifi":
            self._draw_wifi(painter, cx, cy + float_y, w, h)
        else:
            self._draw_box(painter, cx, cy + float_y, w, h)

    def _draw_box(self, p: QPainter, cx: int, cy: int, w: int, h: int):
        """绘制打开的盒子"""
        t = self._time
        # 盒子底部（轻微摇摆）
        box_w, box_h = pt(70), pt(40)
        sway = math.sin(t * math.pi * 2) * 1.5
        bx, by = cx - box_w // 2 + int(sway), cy + pt(10)
        p.setPen(QPen(QColor(141, 194, 31, 120), pt(2)))
        p.setBrush(QColor(141, 194, 31, 15))
        p.drawRoundedRect(bx, by, box_w, box_h, pt(6), pt(6))

        # 盒盖（打开状态，V形）
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(141, 194, 31, 160), pt(2)))
        lid_left = [(bx + pt(4), by), (cx + int(sway), by - pt(20))]
        lid_right = [(cx + int(sway), by - pt(20)), (bx + box_w - pt(4), by)]
        for line in [lid_left, lid_right]:
            p.drawLine(line[0][0], line[0][1], line[1][0], line[1][1])

        # 内部虚线（表示空）
        p.setPen(QPen(QColor(C_TEXT3), pt(1), Qt.DashLine))
        p.drawLine(cx - pt(15), cy + pt(5), cx + pt(15), cy + pt(5))
        p.drawLine(cx - pt(10), cy + pt(15), cx + pt(10), cy + pt(15))

        # 漂浮粒子（做圆周运动）
        p.setBrush(QColor(141, 194, 31, 80))
        p.setPen(Qt.NoPen)
        particles_base = [
            (cx - pt(35), cy - pt(15), pt(4)),
            (cx + pt(30), cy - pt(25), pt(3)),
            (cx + pt(40), cy + pt(5), pt(2.5)),
        ]
        for i, (px, py, pr) in enumerate(particles_base):
            phase = i * 2.1
            orbit_r = 3
            ox = int(math.sin(t * math.pi * 2 + phase) * orbit_r)
            oy = int(math.cos(t * math.pi * 2 + phase) * orbit_r)
            alpha = int(60 + 40 * math.sin(t * math.pi * 2 + phase + 1))
            p.setBrush(QColor(141, 194, 31, alpha))
            p.drawEllipse(int(px + ox - pr), int(py + oy - pr), int(pr * 2), int(pr * 2))

    def _draw_search(self, p: QPainter, cx: int, cy: int, w: int, h: int):
        """绘制搜索放大镜"""
        t = self._time
        # 圆圈（轻微脉动）
        r = pt(28) + int(math.sin(t * math.pi * 2) * 1.5)
        p.setPen(QPen(QColor(141, 194, 31, 140), pt(2.5)))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(cx - r, cy - pt(10) - r, r * 2, r * 2)

        # 手柄
        p.setPen(QPen(QColor(141, 194, 31, 140), pt(3)))
        handle_len = pt(18)
        angle = math.pi / 4 + math.sin(t * math.pi * 2) * 0.05
        hx1 = cx + int(r * math.cos(angle)) - pt(2)
        hy1 = cy - pt(10) + int(r * math.sin(angle)) - pt(2)
        hx2 = hx1 + int(handle_len * math.cos(angle))
        hy2 = hy1 + int(handle_len * math.sin(angle))
        p.drawLine(hx1, hy1, hx2, hy2)

        # 内部小点（呼吸）
        breath = 0.5 + 0.5 * math.sin(t * math.pi * 2)
        p.setBrush(QColor(141, 194, 31, int(60 * breath)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - pt(3), cy - pt(10) - pt(3), pt(6), pt(6))

    def _draw_wifi(self, p: QPainter, cx: int, cy: int, w: int, h: int):
        """绘制断开的 WiFi"""
        t = self._time
        # 底部小圆（呼吸）
        breath = 0.6 + 0.4 * math.sin(t * math.pi * 2)
        p.setBrush(QColor(141, 194, 31, int(100 * breath)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - pt(4), cy + pt(15) - pt(4), pt(8), pt(8))

        # 弧线（从下到上，逐渐变细变透明，带轻微脉动）
        arcs = [(pt(20), 180), (pt(32), 150), (pt(44), 120)]
        for i, (r, alpha_base) in enumerate(arcs):
            alpha = int(alpha_base * (0.7 + 0.3 * math.sin(t * math.pi * 2 + i * 0.8)))
            p.setPen(QPen(QColor(141, 194, 31, alpha), pt(2)))
            p.setBrush(Qt.NoBrush)
            p.drawArc(cx - r, cy + pt(5) - r, r * 2, r * 2, 30 * 16, 120 * 16)

        # 断开标记（斜线，闪烁）
        blink = 0.7 + 0.3 * math.sin(t * math.pi * 2 * 2)
        p.setPen(QPen(QColor(229, 62, 62, int(180 * blink)), pt(2.5)))
        p.drawLine(cx + pt(15), cy - pt(20), cx + pt(35), cy + pt(10))
