"""
BreathingButton — 带呼吸光晕效果的按钮

用 QPainter 绘制带呼吸发光外圈的按钮。
原理同 Onboarding：QTimer(16ms) → update() → paintEvent 循环重绘。
100% 安全，不涉及 QGraphicsEffect / Layout。
"""
import math

from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QColor, QPainter, QFont, QRadialGradient, QPen
from qtpy.QtWidgets import QPushButton

from seeed_jetson_develop.gui.theme import pt


class BreathingButton(QPushButton):
    """呼吸发光按钮 — 外圈光晕在透明边距内绘制，避免被实体按钮挡住。"""

    _GLOW_PAD = 10

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._time = 0.0
        self._speed = 0.018
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")

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
        if w < 8 or h < 8:
            return

        pad = min(self._GLOW_PAD, max(4, min(w, h) // 6))
        breath = 0.55 + 0.45 * math.sin(self._time * math.pi * 2)
        cx, cy = w / 2.0, h / 2.0

        # Glow sits in the transparent padding so the pulse is actually visible.
        glow_r = max(w, h) * 0.48 * (0.85 + 0.35 * breath)
        grad = QRadialGradient(cx, cy, glow_r)
        alpha = int(28 + 55 * breath)
        grad.setColorAt(0.0, QColor(141, 194, 31, alpha))
        grad.setColorAt(0.55, QColor(141, 194, 31, int(alpha * 0.35)))
        grad.setColorAt(1.0, QColor(141, 194, 31, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawEllipse(int(cx - glow_r), int(cy - glow_r), int(glow_r * 2), int(glow_r * 2))

        # Solid pill inset — leaves a ring for the glow.
        bw = w - pad * 2
        bh = h - pad * 2
        radius = bh / 2.0
        p.setPen(QPen(QColor(255, 255, 255, int(40 + 30 * breath)), 1))
        p.setBrush(QColor(141, 194, 31))
        p.drawRoundedRect(pad, pad, bw, bh, radius, radius)

        # Top highlight
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(180, 230, 60, 80))
        p.drawRoundedRect(pad + 1, pad + 1, bw - 2, max(1, bh // 2), radius, radius)

        # Label
        p.setPen(QColor(10, 20, 0))
        font = QFont("Arial", pt(11))
        font.setBold(True)
        p.setFont(font)
        p.drawText(pad, pad, bw, bh, Qt.AlignCenter, self.text())

    def start(self):
        if not self._timer.isActive():
            self._timer.start(16)

    def stop(self):
        self._timer.stop()
