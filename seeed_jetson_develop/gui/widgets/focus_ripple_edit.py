"""
FocusRippleLineEdit — 带焦点波纹效果的输入框

获得焦点时底部出现绿色光条，失去焦点时平滑淡出。
原理：focusInEvent/focusOutEvent 触发目标值 → QTimer 逐步逼近 → paintEvent 绘制光条。
不涉及 QGraphicsEffect / Layout，100% 安全。
"""
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QColor, QPainter, QLinearGradient
from qtpy.QtWidgets import QLineEdit


class FocusRippleLineEdit(QLineEdit):
    """带焦点波纹效果的单行输入框

    用法和普通 QLineEdit 相同：
        edit = FocusRippleLineEdit()
        edit.setPlaceholderText("请输入...")
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._focus_progress = 0.0
        self._target_focus = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._target_focus = 1.0
        if not self._timer.isActive():
            self._timer.start(16)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._target_focus = 0.0
        if not self._timer.isActive():
            self._timer.start(16)

    def _tick(self):
        try:
            step = 0.10
            if self._target_focus > self._focus_progress:
                self._focus_progress = min(self._target_focus, self._focus_progress + step)
            elif self._target_focus < self._focus_progress:
                self._focus_progress = max(self._target_focus, self._focus_progress - step)
            else:
                self._timer.stop()
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._focus_progress < 0.01:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        prog = self._focus_progress

        # ── 底部绿色光条 ──
        bar_h = max(2, int(3 * prog))
        grad = QLinearGradient(0, h - bar_h, 0, h)
        grad.setColorAt(0, QColor(141, 194, 31, int(80 * prog)))
        grad.setColorAt(1, QColor(141, 194, 31, int(180 * prog)))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        # 圆角底部
        p.drawRoundedRect(2, h - bar_h, w - 4, bar_h, 1, 1)

        # ── 两侧 subtle 发光 ──
        side_alpha = int(25 * prog)
        p.setPen(QPen(QColor(141, 194, 31, side_alpha), 1))
        p.drawLine(2, h - bar_h - 1, 2, 2)           # 左
        p.drawLine(w - 3, h - bar_h - 1, w - 3, 2)   # 右
