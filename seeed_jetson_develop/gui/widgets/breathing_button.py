"""
BreathingButton — 带呼吸光晕效果的按钮

用 QPainter 绘制带呼吸发光外圈的按钮。
原理同 Onboarding：QTimer(16ms) → update() → paintEvent 循环重绘。
100% 安全，不涉及 QGraphicsEffect / Layout。
"""
import math

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QFont, QRadialGradient, QPen
from PyQt5.QtWidgets import QPushButton

from seeed_jetson_develop.gui.theme import pt


class BreathingButton(QPushButton):
    """呼吸发光按钮"""
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._time = 0.0
        self._speed = 0.018
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self.setCursor(Qt.PointingHandCursor)

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

        # 呼吸光晕（外圈）
        breath = 0.6 + 0.4 * math.sin(self._time * math.pi * 2)
        glow_r = int(max(w, h) * 0.55 * breath)
        cx, cy = w // 2, h // 2
        grad = QRadialGradient(cx, cy, glow_r)
        alpha = int(50 * breath)
        grad.setColorAt(0, QColor(141, 194, 31, alpha))
        grad.setColorAt(1, QColor(141, 194, 31, 0))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2)

        # 按钮主体（圆角矩形）
        radius = h // 2
        p.setPen(QPen(QColor(255, 255, 255, 50), 1))
        p.setBrush(QColor(141, 194, 31))
        p.drawRoundedRect(1, 1, w - 2, h - 2, radius, radius)

        # 高光（左上角）
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(180, 230, 60, 80))
        p.drawRoundedRect(2, 2, w - 4, h // 2, radius, radius)

        # 文字
        p.setPen(QColor(10, 20, 0))
        font = QFont("Arial", pt(11))
        font.setBold(True)
        p.setFont(font)
        p.drawText(0, 0, w, h, Qt.AlignCenter, self.text())

    def start(self):
        self._timer.start(16)

    def stop(self):
        self._timer.stop()
