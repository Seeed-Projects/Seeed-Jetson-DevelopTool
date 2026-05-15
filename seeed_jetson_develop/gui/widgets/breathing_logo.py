"""
BreathingLogo — 呼吸发光 Logo

用 QPainter 绘制带呼吸光晕的 Seeed 品牌标识。
原理：QTimer(16ms) → update() → paintEvent 根据时间变量绘制。
不涉及 QGraphicsEffect / QPropertyAnimation，100% 安全。
"""
import math

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QFont, QRadialGradient, QLinearGradient
from PyQt5.QtWidgets import QWidget

from seeed_jetson_develop.gui.theme import C_GREEN, C_TEXT2, pt


class BreathingLogo(QWidget):
    """呼吸发光的 Seeed Logo 组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._time = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self.setFixedSize(pt(140), pt(40))
        self.setStyleSheet("background:transparent;")

    def _tick(self):
        try:
            self._time = (self._time + 0.012) % 1.0
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        w, h = self.width(), self.height()

        # 呼吸光晕（仅在 Logo 左侧）
        breath = 0.75 + 0.25 * math.sin(self._time * math.pi * 2)
        glow_r = int(min(w, h) * 0.6 * breath)
        grad = QRadialGradient(pt(30), h // 2, glow_r)
        grad.setColorAt(0, QColor(141, 194, 31, int(25 * breath)))
        grad.setColorAt(1, QColor(141, 194, 31, 0))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(pt(30) - glow_r, h // 2 - glow_r, glow_r * 2, glow_r * 2)

        # "seeed" 文字 — 绿色渐变 + 轻微发光
        font = QFont("Arial", pt(14))
        font.setBold(True)
        p.setFont(font)
        seeed_text = "seeed"
        fm = p.fontMetrics()
        text_w = fm.horizontalAdvance(seeed_text)

        # 文字发光层
        glow_alpha = int(40 + 30 * math.sin(self._time * math.pi * 2 + 0.5))
        p.setPen(QColor(141, 194, 31, glow_alpha))
        p.drawText(pt(4), pt(2), text_w + pt(4), h, Qt.AlignLeft | Qt.AlignVCenter, seeed_text)

        # 文字主体 — 绿色渐变
        text_grad = QLinearGradient(0, 0, 0, h)
        text_grad.setColorAt(0, QColor("#B0E030"))
        text_grad.setColorAt(1, QColor("#7AB317"))
        p.setPen(QColor(C_GREEN))
        p.drawText(pt(2), 0, text_w + pt(4), h, Qt.AlignLeft | Qt.AlignVCenter, seeed_text)

        # "studio" 文字 — 灰色，无发光
        studio_text = " studio"
        p.setPen(QColor(C_TEXT2))
        p.drawText(pt(2) + text_w, 0, w - text_w, h, Qt.AlignLeft | Qt.AlignVCenter, studio_text)

    def stop(self):
        self._timer.stop()

    def start(self):
        self._timer.start(16)
