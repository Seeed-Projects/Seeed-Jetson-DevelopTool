"""
ScanLineOverlay — 页面切换扫描线过场动画

在 QStackedWidget 或任意容器上方叠加，页面切换时绿色光带从左到右扫过，
营造"数据刷新"的科技感。

原理：QTimer(16ms) → update() → paintEvent 根据 progress 绘制光带位置。
不涉及 QGraphicsEffect / Layout 操作，100% 安全。
"""
from qtpy.QtCore import Qt, QTimer, QEvent
from qtpy.QtGui import QColor, QPainter, QLinearGradient, QPen
from qtpy.QtWidgets import QWidget


class ScanLineOverlay(QWidget):
    """扫描线过场动画层

    用法：
        overlay = ScanLineOverlay(parent=stacked_widget.parent())
        overlay.start()  # geometry follows parent/stack on resize
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet("background:transparent;")
        self._progress = 0.0
        self._step = 16 / 350
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._target = None
        self.hide()
        if parent is not None:
            parent.installEventFilter(self)

    def set_target(self, widget: QWidget | None):
        """Optional widget whose geometry (in parent coords) should be matched."""
        if self._target is not None:
            try:
                self._target.removeEventFilter(self)
            except RuntimeError:
                pass
        self._target = widget
        if widget is not None:
            widget.installEventFilter(self)
        self._sync_geometry()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Resize, QEvent.Show, QEvent.Move):
            if obj is self.parent() or obj is self._target:
                self._sync_geometry()
        return super().eventFilter(obj, event)

    def _sync_geometry(self):
        parent = self.parentWidget()
        if parent is None:
            return
        if self._target is not None:
            geo = self._target.geometry()
            if geo.width() > 0 and geo.height() > 0:
                self.setGeometry(geo)
                return
        self.setGeometry(0, 0, max(0, parent.width()), max(0, parent.height()))

    def start(self, duration_ms: int = 350):
        """启动扫描线动画。duration_ms: 扫描线从左到右的总时长。"""
        self._sync_geometry()
        self._progress = 0.0
        self._step = 16 / max(1, duration_ms)
        self.show()
        self.raise_()
        self._timer.start(16)

    def _tick(self):
        try:
            self._progress += self._step
            if self._progress >= 1.0:
                self._progress = 1.0
                self._timer.stop()
                self.hide()
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if w < 10 or h < 10:
            return

        x = int(w * self._progress)
        # Band width scales with viewport so the sweep stays proportional.
        band_w = max(80, min(280, w // 4))

        # 光带渐变（宽色散）
        grad = QLinearGradient(x - band_w, 0, x + band_w, 0)
        grad.setColorAt(0, QColor(141, 194, 31, 0))
        grad.setColorAt(0.35, QColor(141, 194, 31, 12))
        grad.setColorAt(0.5, QColor(141, 194, 31, 35))
        grad.setColorAt(0.65, QColor(141, 194, 31, 12))
        grad.setColorAt(1, QColor(141, 194, 31, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawRect(x - band_w, 0, band_w * 2, h)

        # 核心亮线
        p.setPen(QPen(QColor(141, 194, 31, 70), 1))
        p.drawLine(x, 0, x, h)

        # 核心高亮细线
        p.setPen(QPen(QColor(180, 240, 80, 40), 2))
        p.drawLine(x - 1, 0, x - 1, h)
