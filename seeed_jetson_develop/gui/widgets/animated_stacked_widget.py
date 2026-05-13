"""
AnimatedStackedWidget — 带动画过渡效果的 QStackedWidget

用法：直接替换 QStackedWidget，setCurrentIndex() 自动带有淡入淡出动画。
支持方向：水平滑动（默认）、淡入淡出、缩放。
"""
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QStackedWidget, QGraphicsOpacityEffect, QWidget


class AnimatedStackedWidget(QStackedWidget):
    """带动画过渡的堆叠窗口部件。"""

    animation_finished = pyqtSignal(int)

    def __init__(self, parent=None, duration: int = 250, mode: str = "fade"):
        """
        mode: "fade" | "slide" | "scale"
        """
        super().__init__(parent)
        self._duration = duration
        self._mode = mode
        self._animating = False
        self._target_idx = 0
        self._active_animations = []

    def _remember_animations(self, *animations):
        self._active_animations = [anim for anim in animations if anim is not None]

    def _clear_animations(self):
        self._active_animations.clear()

    def setCurrentIndex(self, index: int):
        if index == self.currentIndex() or self._animating:
            super().setCurrentIndex(index)
            return
        self._target_idx = index
        self._animating = True

        if self._mode == "fade":
            self._animate_fade(index)
        elif self._mode == "slide":
            self._animate_slide(index)
        elif self._mode == "scale":
            self._animate_scale(index)
        else:
            super().setCurrentIndex(index)
            self._animating = False

    def _animate_fade(self, target_idx: int):
        """淡入淡出切换"""
        old_w = self.currentWidget()
        new_w = self.widget(target_idx)
        if old_w is None or new_w is None:
            super().setCurrentIndex(target_idx)
            self._animating = False
            return

        # 旧页面淡出
        old_effect = QGraphicsOpacityEffect(old_w)
        old_effect.setOpacity(1.0)
        old_w.setGraphicsEffect(old_effect)
        old_anim = QPropertyAnimation(old_effect, b"opacity", self)
        old_anim.setDuration(self._duration // 2)
        old_anim.setStartValue(1.0)
        old_anim.setEndValue(0.0)
        old_anim.setEasingCurve(QEasingCurve.InCubic)
        old_anim.start()

        # 切换到新页面
        super().setCurrentIndex(target_idx)

        # 新页面淡入
        new_effect = QGraphicsOpacityEffect(new_w)
        new_effect.setOpacity(0.0)
        new_w.setGraphicsEffect(new_effect)
        new_anim = QPropertyAnimation(new_effect, b"opacity", self)
        new_anim.setDuration(self._duration)
        new_anim.setStartValue(0.0)
        new_anim.setEndValue(1.0)
        new_anim.setEasingCurve(QEasingCurve.OutCubic)
        new_anim.start()
        self._remember_animations(old_anim, new_anim)

        def _done():
            self._cleanup_effect(old_w)
            self._cleanup_effect(new_w)
            self._clear_animations()
            self._animating = False
            self.animation_finished.emit(target_idx)

        from PyQt5.QtCore import QTimer
        QTimer.singleShot(self._duration, _done)

    def _animate_slide(self, target_idx: int):
        """水平滑动切换（简化版：新页面从右侧滑入）"""
        new_w = self.widget(target_idx)
        if new_w is None:
            super().setCurrentIndex(target_idx)
            self._animating = False
            return

        # 预切换，确保新页面有正确尺寸
        super().setCurrentIndex(target_idx)

        new_effect = QGraphicsOpacityEffect(new_w)
        new_effect.setOpacity(1.0)
        new_w.setGraphicsEffect(new_effect)

        # 位置动画（通过 geometry 偏移模拟）
        geo = new_w.geometry()
        start_geo = geo.translated(geo.width() // 4, 0)
        end_geo = geo

        new_w.setGeometry(start_geo)
        slide_anim = QPropertyAnimation(new_w, b"geometry", self)
        slide_anim.setDuration(self._duration)
        slide_anim.setStartValue(start_geo)
        slide_anim.setEndValue(end_geo)
        slide_anim.setEasingCurve(QEasingCurve.OutCubic)
        slide_anim.start()

        # 同时淡入
        fade_anim = QPropertyAnimation(new_effect, b"opacity", self)
        fade_anim.setDuration(self._duration)
        fade_anim.setStartValue(0.3)
        fade_anim.setEndValue(1.0)
        fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        fade_anim.start()
        self._remember_animations(slide_anim, fade_anim)

        def _done():
            self._cleanup_effect(new_w)
            self._clear_animations()
            self._animating = False
            self.animation_finished.emit(target_idx)

        from PyQt5.QtCore import QTimer
        QTimer.singleShot(self._duration, _done)

    def _animate_scale(self, target_idx: int):
        """缩放切换"""
        new_w = self.widget(target_idx)
        if new_w is None:
            super().setCurrentIndex(target_idx)
            self._animating = False
            return

        super().setCurrentIndex(target_idx)

        new_effect = QGraphicsOpacityEffect(new_w)
        new_effect.setOpacity(1.0)
        new_w.setGraphicsEffect(new_effect)

        # 缩放动画（通过 size + pos 模拟）
        geo = new_w.geometry()
        cx, cy = geo.x() + geo.width() // 2, geo.y() + geo.height() // 2
        start_w, start_h = int(geo.width() * 0.96), int(geo.height() * 0.96)
        start_geo = new_w.geometry()
        start_geo.setSize(start_w, start_h)
        start_geo.moveCenter(new_w.geometry().center())

        new_w.setGeometry(start_geo)
        scale_anim = QPropertyAnimation(new_w, b"geometry", self)
        scale_anim.setDuration(self._duration)
        scale_anim.setStartValue(start_geo)
        scale_anim.setEndValue(geo)
        scale_anim.setEasingCurve(QEasingCurve.OutBack)
        scale_anim.start()

        fade_anim = QPropertyAnimation(new_effect, b"opacity", self)
        fade_anim.setDuration(self._duration)
        fade_anim.setStartValue(0.5)
        fade_anim.setEndValue(1.0)
        fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        fade_anim.start()
        self._remember_animations(scale_anim, fade_anim)

        def _done():
            self._cleanup_effect(new_w)
            self._clear_animations()
            self._animating = False
            self.animation_finished.emit(target_idx)

        from PyQt5.QtCore import QTimer
        QTimer.singleShot(self._duration, _done)

    def _cleanup_effect(self, w: QWidget):
        if w:
            w.setGraphicsEffect(None)
