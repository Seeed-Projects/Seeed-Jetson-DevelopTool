"""
AnimatedCheckBox — 带动画勾号的复选框

选中/取消选中时，勾号有一个"从无到有"的绘制动画过程。
原理：QTimer 驱动 check_progress → paintEvent 根据进度绘制部分勾号。
不涉及 QGraphicsEffect / Layout，100% 安全。
"""
from qtpy.QtCore import Qt, QTimer, QRect
from qtpy.QtGui import QColor, QPainter, QPen, QFontMetrics
from qtpy.QtWidgets import QCheckBox


class AnimatedCheckBox(QCheckBox):
    """带动画勾号的复选框

    用法和普通 QCheckBox 相同：
        cb = AnimatedCheckBox("启用功能")
        cb.setChecked(True)
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._check_progress = 0.0
        self._target_progress = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._checked_color = QColor(141, 194, 31)
        self._unchecked_border = QColor(255, 255, 255, 40)
        self._unchecked_bg = QColor(30, 43, 60)

    def setChecked(self, checked):
        super().setChecked(checked)
        self._target_progress = 1.0 if checked else 0.0
        if not self._timer.isActive():
            self._timer.start(16)

    def _tick(self):
        try:
            step = 0.18
            if self._target_progress > self._check_progress:
                self._check_progress = min(self._target_progress, self._check_progress + step)
            elif self._target_progress < self._check_progress:
                self._check_progress = max(self._target_progress, self._check_progress - step)
            else:
                self._timer.stop()
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        sz = 18
        margin = 2
        indicator = QRect(margin, (rect.height() - sz) // 2, sz, sz)

        prog = self._check_progress

        # ── 方框背景 ──
        if prog > 0:
            # 选中态：绿色渐变填充
            p.setBrush(QColor(
                int(30 + 111 * prog),
                int(43 + 151 * prog),
                int(60 - 29 * prog),
                255
            ))
            p.setPen(QPen(QColor(
                int(255 * prog * 0.8),
                int(255 * prog),
                int(255 * prog * 0.2),
                int(200 * prog + 40 * (1 - prog))
            ), 1))
        else:
            p.setBrush(self._unchecked_bg)
            p.setPen(QPen(self._unchecked_border, 1))
        p.drawRoundedRect(indicator, 4, 4)

        # ── 勾号 ──
        if prog > 0.05:
            p.setPen(QPen(QColor(10, 24, 0, int(255 * prog)), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            # 勾号路径：从左下到中点，再到右上
            left_x = indicator.x() + 4
            left_y = indicator.y() + sz // 2 + 2
            mid_x = indicator.x() + sz // 2 - 1
            mid_y = indicator.y() + sz - 4
            right_x = indicator.x() + sz - 3
            right_y = indicator.y() + 4

            # 第一段：左下 → 中点
            seg1_len = ((mid_x - left_x) ** 2 + (mid_y - left_y) ** 2) ** 0.5
            if prog <= 0.5:
                t = prog / 0.5
                cur_x = left_x + (mid_x - left_x) * t
                cur_y = left_y + (mid_y - left_y) * t
                p.drawLine(int(left_x), int(left_y), int(cur_x), int(cur_y))
            else:
                p.drawLine(int(left_x), int(left_y), int(mid_x), int(mid_y))
                # 第二段：中点 → 右上
                t = (prog - 0.5) / 0.5
                cur_x = mid_x + (right_x - mid_x) * t
                cur_y = mid_y + (right_y - mid_y) * t
                p.drawLine(int(mid_x), int(mid_y), int(cur_x), int(cur_y))

        # ── 文字 ──
        text_x = indicator.right() + 8
        fm = QFontMetrics(self.font())
        text_rect = QRect(text_x, 0, rect.width() - text_x, rect.height())
        p.setPen(QColor(184, 204, 220) if not self.isChecked() else QColor(244, 248, 252))
        p.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self.text())

        # ── hover 高亮边框 ──
        if self.underMouse() and prog < 0.5:
            p.setPen(QPen(QColor(141, 194, 31, 60), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(indicator, 4, 4)
