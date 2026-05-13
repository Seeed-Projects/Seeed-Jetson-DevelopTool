"""
ToastNotification — 全局浮动通知系统

用法：
    from seeed_jetson_develop.gui.widgets.toast_notification import Toast
    Toast.success(self, "安装成功！")
    Toast.error(self, "连接失败，请检查网络")
    Toast.info(self, "正在下载...")
    Toast.warning(self, "存储空间不足")

特性：
- 4 种类型：success / error / warning / info
- 从右上角滑入，停留 3 秒后自动淡出
- 支持手动关闭（× 按钮）
- 最多同时显示 4 条，超出时旧的通知提前消失
- 自动堆叠排列
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QPoint
from PyQt5.QtGui import QColor, QPainter, QFont
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect,
    QApplication,
)

from seeed_jetson_develop.gui.theme import (
    C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_ORANGE, C_RED, C_BLUE,
    C_TEXT, C_TEXT2, C_TEXT3,
    C_BORDER_CARD, pt,
)


class Toast(QWidget):
    """单条通知组件"""

    # 全局队列，管理所有活动的 Toast
    _active_toasts: list[Toast] = []
    _MAX_VISIBLE = 4
    _MARGIN_RIGHT = 20
    _MARGIN_TOP = 20
    _SPACING = 10

    def __init__(self, parent, message: str, toast_type: str = "info", duration: int = 3000):
        super().__init__(parent)
        self._duration = duration
        self._type = toast_type
        self._message = message

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._build_ui()
        self._setup_animations()

    def _build_ui(self):
        colors = {
            "success": (C_GREEN, "✓"),
            "error":   (C_RED,   "✕"),
            "warning": (C_ORANGE, "!"),
            "info":    (C_BLUE,  "i"),
        }
        accent, icon = colors.get(self._type, (C_BLUE, "i"))

        # 主容器
        self.setFixedWidth(pt(320))
        self.setStyleSheet(f"""
            QWidget {{
                background: {C_CARD};
                border: 1px solid {C_BORDER_CARD};
                border-left: 3px solid {accent};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(pt(12), pt(10), pt(8), pt(10))
        layout.setSpacing(pt(8))

        # 图标
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"color:{accent}; font-size:{pt(14)}px; font-weight:bold; background:transparent;")
        icon_lbl.setFixedWidth(pt(18))
        layout.addWidget(icon_lbl)

        # 消息文字
        msg_lbl = QLabel(self._message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(f"color:{C_TEXT}; font-size:{pt(12)}px; background:transparent;")
        layout.addWidget(msg_lbl, 1)

        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(pt(20), pt(20))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {C_TEXT3}; font-size: {pt(14)}px; font-weight: bold;
            }}
            QPushButton:hover {{ color: {C_TEXT}; }}
        """)
        close_btn.clicked.connect(self._dismiss)
        layout.addWidget(close_btn)

    def _setup_animations(self):
        # 淡入 + 从右侧滑入
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(250)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_in.start()

    def showEvent(self, event):
        super().showEvent(event)
        # 自动关闭计时器
        QTimer.singleShot(self._duration, self._dismiss)

    def _dismiss(self):
        """淡出并销毁"""
        if self in Toast._active_toasts:
            Toast._active_toasts.remove(self)

        fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        fade_out.setDuration(200)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.InCubic)
        fade_out.finished.connect(self.deleteLater)
        fade_out.start()

        # 重新排列剩余 Toast
        QTimer.singleShot(50, Toast._reposition_all)

    # ── 类方法：快捷创建 ──────────────────────────────────────────────────────

    @classmethod
    def _show(cls, parent, message: str, toast_type: str, duration: int = 3000):
        """显示一条通知"""
        # 如果超过最大数量，移除最旧的通知
        while len(cls._active_toasts) >= cls._MAX_VISIBLE:
            old = cls._active_toasts.pop(0)
            old.deleteLater()

        toast = Toast(parent, message, toast_type, duration)
        cls._active_toasts.append(toast)
        toast.show()
        cls._reposition_all()

    @classmethod
    def _reposition_all(cls):
        """重新排列所有活动通知的位置"""
        if not cls._active_toasts:
            return

        # 获取父窗口或屏幕的几何信息
        ref = cls._active_toasts[0].parent()
        if ref:
            ref_geo = ref.geometry()
        else:
            from PyQt5.QtWidgets import QDesktopWidget
            ref_geo = QDesktopWidget().availableGeometry()

        base_x = ref_geo.x() + ref_geo.width() - pt(320) - cls._MARGIN_RIGHT
        base_y = ref_geo.y() + cls._MARGIN_TOP

        for i, toast in enumerate(cls._active_toasts):
            y = base_y + i * (toast.height() + cls._SPACING)
            toast.move(base_x, y)

    @classmethod
    def success(cls, parent, message: str, duration: int = 3000):
        cls._show(parent, message, "success", duration)

    @classmethod
    def error(cls, parent, message: str, duration: int = 4000):
        cls._show(parent, message, "error", duration)

    @classmethod
    def warning(cls, parent, message: str, duration: int = 3500):
        cls._show(parent, message, "warning", duration)

    @classmethod
    def info(cls, parent, message: str, duration: int = 3000):
        cls._show(parent, message, "info", duration)

    @classmethod
    def clear_all(cls):
        """清除所有通知"""
        for t in cls._active_toasts[:]:
            t.deleteLater()
        cls._active_toasts.clear()
