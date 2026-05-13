"""
LoadingSpinner — 旋转加载动画

简洁的弧形旋转加载器，替代静态 "Loading..." 文字。
原理：QTimer(16ms) → update() → paintEvent 中根据角度绘制旋转弧线。
"""
import math

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen, QConicalGradient
from PyQt5.QtWidgets import QWidget


class LoadingSpinner(QWidget):
    """旋转加载动画组件"""
    def __init__(self, size: int = 32, color: str = "#8DC21F", parent=None):
        super().__init__(parent)
        self._size = size
        self._color = QColor(color)
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(size, size)
        self.setStyleSheet("background:transparent;")

    def _tick(self):
        self._angle = (self._angle + 8) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        r = (min(w, h) - 4) // 2

        # 背景轨道
        p.setPen(QPen(QColor(255, 255, 255, 20), 3, Qt.SolidLine, Qt.RoundCap))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # 旋转弧线
        pen = QPen(self._color, 3, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(cx - r, cy - r, r * 2, r * 2,
                  int(self._angle * 16), int(90 * 16))

        # 尾随渐隐弧线
        fade_pen = QPen(QColor(self._color.red(), self._color.green(), self._color.blue(), 80), 2, Qt.SolidLine, Qt.RoundCap)
        p.setPen(fade_pen)
        p.drawArc(cx - r, cy - r, r * 2, r * 2,
                  int((self._angle - 30) * 16), int(60 * 16))

    def start(self):
        self._timer.start(16)

    def stop(self):
        self._timer.stop()
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.stop()
