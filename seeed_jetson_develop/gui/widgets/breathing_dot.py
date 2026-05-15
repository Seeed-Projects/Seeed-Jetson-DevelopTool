"""
BreathingDot — 呼吸指示灯

用于状态指示（在线/离线/检测中）的呼吸发光圆点。
原理同 Onboarding 动画：QTimer + paintEvent 循环重绘。
"""
import math

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QRadialGradient
from PyQt5.QtWidgets import QWidget


class BreathingDot(QWidget):
    """呼吸发光状态指示灯

    用法：
        dot = BreathingDot(color="#8DC21F", size=10)
        dot.start()
    """
    def __init__(self, color: str = "#8DC21F", size: int = 10, parent=None):
        super().__init__(parent)
        self._base_color = QColor(color)
        self._size = size
        self._time = 0.0
        self._speed = 0.015
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(size * 3, size * 3)
        self.setStyleSheet("background:transparent;")

    def _tick(self):
        try:
            self._time = (self._time + self._speed) % 1.0
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2

        # 呼吸光晕
        breath = 0.6 + 0.4 * math.sin(self._time * math.pi * 2)
        glow_r = int(self._size * 1.8 * breath)
        grad = QRadialGradient(cx, cy, glow_r)
        alpha = int(60 * breath)
        grad.setColorAt(0, QColor(self._base_color.red(), self._base_color.green(), self._base_color.blue(), alpha))
        grad.setColorAt(1, QColor(self._base_color.red(), self._base_color.green(), self._base_color.blue(), 0))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2)

        # 核心圆点
        core_r = int(self._size * 0.5)
        p.setBrush(self._base_color)
        p.drawEllipse(cx - core_r, cy - core_r, core_r * 2, core_r * 2)

        # 高光点
        p.setBrush(QColor(255, 255, 255, 120))
        p.drawEllipse(cx - core_r // 3, cy - core_r // 2, core_r // 2, core_r // 2)

    def start(self):
        self._timer.start(16)

    def stop(self):
        self._timer.stop()

    def setColor(self, color: str):
        self._base_color = QColor(color)
        self.update()
