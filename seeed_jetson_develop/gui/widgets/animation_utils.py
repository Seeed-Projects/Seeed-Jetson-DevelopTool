"""
通用动画工具函数

为任意 QWidget 添加交错的入场动画和状态变化动画。
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QGraphicsOpacityEffect, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLayout,
)


# ── 入场动画 ──────────────────────────────────────────────────────────────────

def apply_fade_in(widget: QWidget, delay_ms: int = 0, duration_ms: int = 350,
                  start_y_offset: int = 15):
    """
    为 widget 添加淡入 + 上浮入场动画。
    如果 widget 尚未显示，动画会在 showEvent 后自动触发。
    """
    effect = widget.graphicsEffect()
    if isinstance(effect, QGraphicsOpacityEffect):
        effect.setOpacity(0.0)
    else:
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)

    def _play():
        # 淡入
        fade = QPropertyAnimation(effect, b"opacity")
        fade.setDuration(duration_ms)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.start()

        # 上浮（通过 geometry 偏移模拟）
        if start_y_offset > 0:
            geo = widget.geometry()
            slide = QPropertyAnimation(widget, b"geometry")
            slide.setDuration(duration_ms)
            slide.setStartValue(geo.translated(0, start_y_offset))
            slide.setEndValue(geo)
            slide.setEasingCurve(QEasingCurve.OutCubic)
            slide.start()

    if delay_ms > 0:
        QTimer.singleShot(delay_ms, _play)
    else:
        _play()


def stagger_animate_children(container: QWidget, stagger_ms: int = 50,
                             duration_ms: int = 350, start_y_offset: int = 15,
                             max_items: int = 50):
    """
    遍历 container 中的所有直接子 widget，为每个添加交错入场动画。
    常用于列表/卡片容器在 setVisible(True) 后的统一动画触发。
    """
    children = [c for c in container.children() if isinstance(c, QWidget) and c.isWidgetType()]
    for i, child in enumerate(children[:max_items]):
        apply_fade_in(child, delay_ms=i * stagger_ms, duration_ms=duration_ms,
                      start_y_offset=start_y_offset)


def stagger_animate_layout_items(layout: QLayout, stagger_ms: int = 50,
                                  duration_ms: int = 350, start_y_offset: int = 15,
                                  max_items: int = 50):
    """
    遍历 layout 中的所有 item，为每个 widget 添加交错入场动画。
    """
    widgets = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item and item.widget():
            widgets.append(item.widget())
    for i, w in enumerate(widgets[:max_items]):
        apply_fade_in(w, delay_ms=i * stagger_ms, duration_ms=duration_ms,
                      start_y_offset=start_y_offset)


# ── 状态变化动画 ──────────────────────────────────────────────────────────────

def apply_pop_bounce(widget: QWidget, duration_ms: int = 280, scale: float = 1.06):
    """
    为 widget 添加一个放大再缩回的弹跳动画，适合状态标签变化时使用。
    """
    geo = widget.geometry()
    if geo.width() <= 0 or geo.height() <= 0:
        return

    # 计算中心点不变的目标 geometry
    cx = geo.x() + geo.width() // 2
    cy = geo.y() + geo.height() // 2
    dw = int(geo.width() * (scale - 1.0))
    dh = int(geo.height() * (scale - 1.0))

    big_geo = geo.adjusted(-dw // 2, -dh // 2, dw // 2, dh // 2)

    anim = QPropertyAnimation(widget, b"geometry")
    anim.setDuration(duration_ms)
    anim.setKeyValueAt(0.0, geo)
    anim.setKeyValueAt(0.35, big_geo)
    anim.setKeyValueAt(1.0, geo)
    anim.setEasingCurve(QEasingCurve.OutBack)
    anim.start()


def apply_shake(widget: QWidget, duration_ms: int = 350, distance: int = 6):
    """
    为 widget 添加水平摇晃动画，适合错误/警告提示时使用。
    """
    geo = widget.geometry()
    anim = QPropertyAnimation(widget, b"geometry")
    anim.setDuration(duration_ms)
    anim.setKeyValueAt(0.0, geo)
    anim.setKeyValueAt(0.20, geo.translated(-distance, 0))
    anim.setKeyValueAt(0.40, geo.translated(distance, 0))
    anim.setKeyValueAt(0.60, geo.translated(-distance // 2, 0))
    anim.setKeyValueAt(0.80, geo.translated(distance // 2, 0))
    anim.setKeyValueAt(1.0, geo)
    anim.setEasingCurve(QEasingCurve.InOutCubic)
    anim.start()


# ── 颜色过渡动画（用于自定义绘制 widget）────────────────────────────────────────

class _ColorProperty:
    """辅助类：通过 pyqtProperty 实现 QColor 动画"""
    def __init__(self, widget, initial_color: str):
        self._widget = widget
        self._color = QColor(initial_color)

    def get(self) -> QColor:
        return self._color

    def set(self, color: QColor):
        self._color = color
        self._widget.update()


def create_color_animator(widget: QWidget, property_name: str, initial_color: str):
    """
    为 widget 创建一个可动画化的颜色属性。
    返回 (pyqtProperty, animator_obj)，可用于 QPropertyAnimation。
    """
    prop = _ColorProperty(widget, initial_color)
    pyqt_prop = pyqtProperty(QColor, prop.get, prop.set)
    setattr(widget.__class__, property_name, pyqt_prop)
    return prop
