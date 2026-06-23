"""
AnimatedStackedWidget — 带动画过渡效果的 QStackedWidget

安全设计：不使用 QGraphicsOpacityEffect（可能导致页面透明问题），
仅使用 QPropertyAnimation 操作 geometry 实现滑入效果。
"""
from qtpy.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, Signal
from qtpy.QtWidgets import QStackedWidget


class AnimatedStackedWidget(QStackedWidget):
    """带动画过渡的堆叠窗口部件。使用 geometry 滑入效果，无 opacity effect。"""

    animation_finished = Signal(int)

    def __init__(self, parent=None, duration: int = 220):
        super().__init__(parent)
        self._duration = duration
        self._animating = False

    def setCurrentIndex(self, index: int):
        if index == self.currentIndex() or self._animating or index < 0 or index >= self.count():
            super().setCurrentIndex(index)
            return
        self._animate_slide(index)

    def _animate_slide(self, target_idx: int):
        """新页面从右侧轻微滑入，旧页面保持不动。安全，不操作 opacity。"""
        new_w = self.widget(target_idx)
        if new_w is None:
            super().setCurrentIndex(target_idx)
            return

        self._animating = True

        # 先切换到新页面（瞬间切换）
        super().setCurrentIndex(target_idx)

        # 获取新页面当前 geometry（布局后的正确尺寸）
        geo = new_w.geometry()
        if geo.width() <= 0 or geo.height() <= 0:
            # 如果尺寸无效，跳过动画
            self._animating = False
            self.animation_finished.emit(target_idx)
            return

        # 从右侧 30px 处开始，淡入滑入效果通过位置偏移实现
        start_geo = geo.translated(30, 0)
        new_w.setGeometry(start_geo)

        # 位置滑入动画
        slide_anim = QPropertyAnimation(new_w, b"geometry")
        slide_anim.setDuration(self._duration)
        slide_anim.setStartValue(start_geo)
        slide_anim.setEndValue(geo)
        slide_anim.setEasingCurve(QEasingCurve.OutCubic)
        slide_anim.finished.connect(lambda: self._on_done(target_idx))
        slide_anim.start()

    def _on_done(self, target_idx: int):
        self._animating = False
        self.animation_finished.emit(target_idx)
