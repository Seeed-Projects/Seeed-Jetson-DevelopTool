"""
ContentBackground — 内容区背景装饰动画

用 QPainter 绘制 subtle 的科技风背景动效：
- 缓慢水平扫描线（带绿色光晕）
- subtle 网格点阵
- 四角 L 形装饰线（缓慢脉动）

原理：QTimer(16ms) → update() → paintEvent 循环重绘。
不涉及 QGraphicsEffect / Layout 操作，100% 安全。
"""
import math

from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QColor, QPainter, QLinearGradient, QPen
from qtpy.QtWidgets import QWidget


class ContentBackground(QWidget):
    """内容区背景装饰动画层

    用法：
        bg = ContentBackground(parent=content_area)
        bg.setGeometry(0, 0, content_area.width(), content_area.height())
        bg.show()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._time = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        # 鼠标事件穿透到下层 widget
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet("background:transparent;")

    def _tick(self):
        try:
            self._time = (self._time + 0.002) % 1.0
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if w < 10 or h < 10:
            return

        # ── 1. 水平扫描线（带绿色光晕） ──
        scan_y = int(h * self._time)
        # 光晕层
        glow_h = 60
        grad = QLinearGradient(0, scan_y - glow_h // 2, 0, scan_y + glow_h // 2)
        grad.setColorAt(0, QColor(141, 194, 31, 0))
        grad.setColorAt(0.5, QColor(141, 194, 31, 10))
        grad.setColorAt(1, QColor(141, 194, 31, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawRect(0, scan_y - glow_h // 2, w, glow_h)
        # 核心线
        p.setPen(QPen(QColor(141, 194, 31, 18), 1))
        p.drawLine(0, scan_y, w, scan_y)

        # ── 2. 逆向扫描线（更 subtle） ──
        scan_y2 = int(h * ((self._time + 0.5) % 1.0))
        p.setPen(QPen(QColor(61, 142, 240, 8), 1))
        p.drawLine(0, scan_y2, w, scan_y2)

        # ── 3. 网格点阵 ──
        spacing = 50
        dot_alpha = 6
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(141, 194, 31, dot_alpha))
        offset_x = int(self._time * spacing)
        for x in range(-spacing, w + spacing, spacing):
            for y in range(0, h, spacing):
                px = (x + offset_x) % (w + spacing) - spacing // 2
                p.drawEllipse(px, y, 1, 1)

        # ── 4. 四角 L 形装饰线（缓慢脉动） ──
        corner_len = 24
        corner_alpha = int(20 + 15 * math.sin(self._time * math.pi * 2))
        p.setPen(QPen(QColor(141, 194, 31, corner_alpha), 1))
        margin = 16
        # 左上
        p.drawLine(margin, margin, margin + corner_len, margin)
        p.drawLine(margin, margin, margin, margin + corner_len)
        # 右上
        p.drawLine(w - margin - corner_len, margin, w - margin, margin)
        p.drawLine(w - margin, margin, w - margin, margin + corner_len)
        # 左下
        p.drawLine(margin, h - margin, margin + corner_len, h - margin)
        p.drawLine(margin, h - margin - corner_len, margin, h - margin)
        # 右下
        p.drawLine(w - margin - corner_len, h - margin, w - margin, h - margin)
        p.drawLine(w - margin, h - margin - corner_len, w - margin, h - margin)

        # ── 5. 底部微妙波浪线 ──
        p.setPen(QPen(QColor(141, 194, 31, 6), 1))
        wave_y = h - 40
        points = []
        for x in range(0, w, 4):
            y = wave_y + 6 * math.sin((x + self._time * 200) * 0.02)
            points.append((x, y))
        for i in range(len(points) - 1):
            p.drawLine(int(points[i][0]), int(points[i][1]),
                       int(points[i+1][0]), int(points[i+1][1]))

    def start(self):
        self._timer.start(16)

    def stop(self):
        self._timer.stop()
