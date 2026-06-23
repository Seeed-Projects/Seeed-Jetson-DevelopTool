"""
RippleButton — 带点击涟漪反馈的按钮

点击时在按钮表面产生 Material Design 风格的扩散涟漪效果。
原理：mousePressEvent 记录点击位置 → QTimer 驱动半径增长 → paintEvent
在 super().paintEvent() 绘制的按钮内容之上叠加半透明圆环。

不涉及 QGraphicsEffect / Layout 操作，100% 安全。
"""
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QColor, QPainter
from qtpy.QtWidgets import QPushButton


class RippleButton(QPushButton):
    """带涟漪点击反馈的按钮

    用法和普通 QPushButton 完全一致，只需设置样式表即可：
        btn = RippleButton("点击我")
        btn.setStyleSheet("...")
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._ripples = []  # 活跃的涟漪列表
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        # 默认不启动 timer，有涟漪时才启动

    def mousePressEvent(self, event):
        """记录点击位置并启动新涟漪。"""
        max_r = max(self.width(), self.height()) * 1.3
        self._ripples.append({
            "cx": event.x(),
            "cy": event.y(),
            "radius": 0.0,
            "max_radius": max_r,
            "speed": max_r / 10.0,      # 约 160ms 扩散完成
            "opacity": 0.28,
            "fade": 0.28 / 14.0,         # 约 224ms 淡出
        })
        if not self._timer.isActive():
            self._timer.start(16)
        super().mousePressEvent(event)

    def _tick(self):
        """每帧更新所有活跃涟漪。"""
        try:
            alive = []
            for r in self._ripples:
                r["radius"] += r["speed"]
                r["opacity"] -= r["fade"]
                if r["opacity"] > 0:
                    alive.append(r)
            self._ripples = alive
            if not alive:
                self._timer.stop()
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, event):
        """先绘制按钮本体（QSS 样式），再叠加涟漪层。"""
        super().paintEvent(event)
        if not self._ripples:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        for r in self._ripples:
            alpha = int(255 * r["opacity"])
            if alpha <= 0:
                continue
            radius = r["radius"]
            # 外圈（较透明）
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, int(alpha * 0.4)))
            p.drawEllipse(
                int(r["cx"] - radius), int(r["cy"] - radius),
                int(radius * 2), int(radius * 2)
            )
            # 内圈（较实）
            inner_r = radius * 0.7
            p.setBrush(QColor(255, 255, 255, int(alpha * 0.7)))
            p.drawEllipse(
                int(r["cx"] - inner_r), int(r["cy"] - inner_r),
                int(inner_r * 2), int(inner_r * 2)
            )
