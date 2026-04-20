"""
烧录流程动画 Widget
支持两类场景：
- prep: 下载 / 解压 / 就绪 / 失败
- flash: 刷写中 / 成功 / 失败
"""
import math

from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QWidget


class FlashAnimationWidget(QWidget):
    MODES = ("idle", "downloading", "extracting", "ready", "flashing", "success", "error")

    def __init__(self, scene="flash", parent=None):
        super().__init__(parent)
        self._scene = scene
        self._mode = "idle"
        self._tick = 0
        self._progress = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._on_tick)
        self.setMinimumSize(220, 150)

    def set_mode(self, mode: str):
        if mode not in self.MODES:
            raise ValueError(f"unknown mode: {mode}")
        self._mode = mode
        self._tick = 0
        if mode in {"idle", "ready"}:
            self._timer.stop()
        else:
            self._timer.start()
        self.update()

    def set_progress(self, ratio: float):
        self._progress = max(0.0, min(1.0, float(ratio)))
        self.update()

    def set_download_progress(self, ratio: float):
        self.set_progress(ratio)

    def _on_tick(self):
        self._tick = (self._tick + 1) % 10000
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        panel = self.rect().adjusted(8, 8, -8, -8)
        bg = QLinearGradient(panel.topLeft(), panel.bottomLeft())
        bg.setColorAt(0.0, QColor("#13202B"))
        bg.setColorAt(1.0, QColor("#0F171F"))
        p.fillRect(self.rect(), QColor("#151D26"))
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(panel, 14, 14)

        inner = panel.adjusted(16, 14, -16, -14)
        if self._scene == "prep":
            self._paint_prep(p, inner)
        else:
            self._paint_flash(p, inner)

    def _rounded(self, p, x, y, w, h, color, radius=10, pen=Qt.NoPen):
        p.setPen(pen)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(x, y, w, h), radius, radius)

    def _circle(self, p, x, y, r, color, pen=Qt.NoPen):
        p.setPen(pen)
        p.setBrush(color)
        p.drawEllipse(QPointF(x, y), r, r)

    def _line(self, p, x1, y1, x2, y2, color, width=2, style=Qt.SolidLine):
        pen = QPen(color, width)
        pen.setStyle(style)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _draw_capsules(self, p, rect, color_on, color_tail=None):
        slots = 8
        color_tail = color_tail or color_on
        start_x = rect.left() + 118
        for idx in range(slots):
            color = QColor("#293947")
            if self._mode == "downloading":
                active = max(1, int(self._progress * slots) + 1)
                if idx < active:
                    color = color_on if idx < 5 else color_tail
            elif self._mode == "extracting":
                active = max(1, int(self._progress * slots) + 1)
                if idx < active:
                    color = QColor("#98DA77")
            elif self._mode == "ready":
                color = QColor("#98DA77")
            elif self._mode == "flashing":
                active = max(2, int(self._progress * slots) + 1)
                if idx < active:
                    color = color_on if idx < 6 else color_tail
            elif self._mode == "success":
                color = QColor("#98DA77")
            elif self._mode == "error":
                color = QColor("#D86A6A") if idx % 2 == (self._tick // 4) % 2 else QColor("#293947")
            self._rounded(p, start_x + idx * 16, rect.top(), 11, 5, color, 2)

    def _draw_cloud(self, p, x, y, body, detail):
        self._circle(p, x - 20, y + 8, 14, body)
        self._circle(p, x, y - 2, 18, body)
        self._circle(p, x + 20, y + 8, 13, body)
        self._rounded(p, x - 34, y + 8, 68, 22, body, 10)
        self._line(p, x - 18, y + 6, x + 12, y + 6, detail, 2)

    def _draw_archive(self, p, x, y, glow=False, lid_open=False):
        body = QColor("#8A6848") if glow else QColor("#735942")
        top = QColor("#B8895B")
        self._rounded(p, x, y + 14, 74, 30, body, 10)
        self._rounded(p, x + 8, y + 4, 58, 16, top, 8)
        self._line(p, x + 37, y + 18, x + 37, y + 38, QColor("#F4D6A2"), 2)
        if lid_open:
            p.save()
            p.translate(x + 14, y + 12)
            p.rotate(-16)
            self._rounded(p, 0, -10, 50, 12, top, 7)
            p.restore()

    def _draw_folder(self, p, x, y, glow=False):
        shell = QColor("#557B97") if glow else QColor("#46677E")
        self._rounded(p, x, y + 10, 54, 34, shell, 9)
        self._rounded(p, x + 4, y, 24, 16, QColor("#7297B4"), 7)
        self._rounded(p, x + 8, y + 17, 38, 19, QColor("#28414F"), 7)

    def _draw_board(self, p, x, y, glow=False, error=False):
        shell = QColor("#4A6F84")
        if glow:
            shell = QColor("#4C775C")
        if error:
            shell = QColor("#7A5A5A")
        self._rounded(p, x, y + 18, 84, 44, shell, 11)
        screen = QColor("#D8F4F0")
        if glow:
            screen = QColor("#D7EFC2")
        if error:
            screen = QColor("#D5A2A2")
        self._rounded(p, x + 12, y + 28, 44, 16, screen, 6)
        self._rounded(p, x + 62, y + 30, 10, 14, QColor("#233A47"), 4)
        for idx in range(4):
            self._rounded(p, x + 14 + idx * 14, y + 66, 7, 4, QColor("#C1D3DF"), 2)

    def _paint_prep(self, p, rect):
        teal = QColor("#75D8CE")
        teal2 = QColor("#A1EEE8")
        blue = QColor("#6C8DA7")
        blue2 = QColor("#B4C6D4")
        green = QColor("#98DA77")
        red = QColor("#D96A6A")
        yellow = QColor("#E4B85E")

        self._draw_capsules(p, rect, teal, teal2)
        baseline = rect.bottom() - 16
        self._line(p, rect.left() + 12, baseline, rect.right() - 12, baseline, QColor("#31434F"), 2)

        if self._mode in {"idle", "downloading"}:
            self._draw_cloud(p, rect.left() + 100, rect.top() + 36, blue, blue2)
            self._draw_archive(p, rect.left() + 34, rect.top() + 56, glow=self._mode == "downloading")
            self._draw_board(p, rect.right() - 118, rect.top() + 60)
            self._line(p, rect.left() + 100, rect.top() + 66, rect.left() + 100, rect.top() + 92,
                       teal if self._mode == "downloading" else blue, 3)
            arrow = QPainterPath()
            arrow.moveTo(rect.left() + 93, rect.top() + 88)
            arrow.lineTo(rect.left() + 107, rect.top() + 88)
            arrow.lineTo(rect.left() + 100, rect.top() + 100)
            arrow.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(teal if self._mode == "downloading" else blue)
            p.drawPath(arrow)
            if self._mode == "downloading":
                for idx in range(4):
                    yy = rect.top() + 72 + ((self._tick * 7 + idx * 18) % 30)
                    self._circle(p, rect.left() + 100, yy, 3 + (idx % 2), teal if idx % 2 == 0 else teal2)

        elif self._mode in {"extracting", "ready"}:
            self._draw_archive(p, rect.left() + 26, rect.top() + 60, glow=True, lid_open=True)
            self._draw_folder(p, rect.left() + 172, rect.top() + 58, glow=True)
            self._draw_board(p, rect.right() - 112, rect.top() + 60, glow=self._mode == "ready")
            line_color = green if self._mode == "ready" else teal
            self._line(p, rect.left() + 114, rect.top() + 92, rect.left() + 174, rect.top() + 92, line_color, 3)
            for idx in range(4):
                xx = rect.left() + 120 + ((self._tick * 10 + idx * 28) % 70)
                yy = rect.top() + 92 + (-4 if idx % 2 == 0 else 4)
                self._circle(p, xx, yy, 4, green if self._mode == "ready" else teal)
            if self._mode == "ready":
                self._circle(p, rect.right() - 54, rect.top() + 34, 16, QColor(122, 179, 23, 40))
                self._line(p, rect.right() - 62, rect.top() + 34, rect.right() - 55, rect.top() + 41, green, 4)
                self._line(p, rect.right() - 55, rect.top() + 41, rect.right() - 44, rect.top() + 26, green, 4)

        elif self._mode == "error":
            self._draw_cloud(p, rect.left() + 92, rect.top() + 38, QColor("#596C79"), QColor("#7D90A0"))
            self._draw_archive(p, rect.left() + 32, rect.top() + 62)
            self._draw_board(p, rect.right() - 118, rect.top() + 60, error=True)
            self._line(p, rect.left() + 122, rect.top() + 74, rect.left() + 150, rect.top() + 102, red, 3)
            self._line(p, rect.left() + 122, rect.top() + 102, rect.left() + 150, rect.top() + 74, red, 3)
            tri = QPainterPath()
            tri.moveTo(rect.right() - 64, rect.top() + 22)
            tri.lineTo(rect.right() - 44, rect.top() + 54)
            tri.lineTo(rect.right() - 84, rect.top() + 54)
            tri.closeSubpath()
            p.setBrush(yellow)
            p.setPen(Qt.NoPen)
            p.drawPath(tri)
            self._line(p, rect.right() - 64, rect.top() + 30, rect.right() - 64, rect.top() + 42, QColor("#5A430D"), 3)
            self._circle(p, rect.right() - 64, rect.top() + 48, 2.5, QColor("#5A430D"))

    def _paint_flash(self, p, rect):
        teal = QColor("#75D8CE")
        teal2 = QColor("#A1EEE8")
        green = QColor("#98DA77")
        red = QColor("#D86A6A")
        red_dark = QColor("#A74C4C")

        self._draw_capsules(p, rect, teal, teal2)
        self._rounded(p, rect.left(), rect.bottom() - 44, rect.width(), 44, QColor("#1E2D39"), 12)
        self._rounded(p, rect.left(), rect.bottom() - 50, rect.width(), 8, QColor("#375160"), 8)
        self._rounded(p, rect.left() + 18, rect.bottom() - 24, rect.width() - 36, 5, QColor("#7A6A52"), 2)

        house_x = rect.left() + 34
        house_y = rect.bottom() - 96
        roof = QPainterPath()
        roof.moveTo(house_x + 4, house_y + 24)
        roof.lineTo(house_x + 28, house_y)
        roof.lineTo(house_x + 52, house_y + 24)
        roof.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#8B744E"))
        p.drawPath(roof)
        self._rounded(p, house_x + 8, house_y + 22, 40, 40, QColor("#705C46"), 8)
        self._rounded(p, house_x + 22, house_y + 34, 12, 16,
                      QColor("#A8D67A") if self._mode in {"flashing", "success"} else QColor("#6A7562"), 4)
        flag = QPainterPath()
        flag.moveTo(house_x + 56, house_y + 8)
        flag.quadTo(house_x + 68, house_y + 2, house_x + 66, house_y + 18)
        flag.quadTo(house_x + 58, house_y + 16, house_x + 56, house_y + 8)
        p.setBrush(QColor("#7AB317"))
        p.drawPath(flag)

        dev_x = rect.right() - 122
        dev_y = rect.bottom() - 92
        self._draw_board(p, dev_x, dev_y, glow=self._mode == "success", error=self._mode == "error")

        path = QPainterPath(QPointF(house_x + 58, house_y + 42))
        path.cubicTo(house_x + 116, house_y + 10, dev_x - 40, dev_y + 18, dev_x + 10, dev_y + 38)
        glow_pen = QPen(QColor("#2C4756"), 4)
        glow_pen.setCapStyle(Qt.RoundCap)
        p.setPen(glow_pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        if self._mode in {"idle", "flashing", "success"}:
            count = 2 if self._mode == "idle" else max(4, min(9, int(self._progress * 10) + 2))
            for idx in range(count):
                if self._mode == "flashing":
                    t = ((self._tick / 28.0) + idx * 0.12) % 1.0
                    color = teal2 if idx % 3 == 1 else teal
                else:
                    t = min(0.1 + idx * 0.12, 0.98)
                    color = green if self._mode == "success" else QColor("#4A5E6D")
                point = path.pointAtPercent(t)
                self._circle(p, point.x(), point.y(), 4 if idx % 3 else 5, color)

        if self._mode == "flashing":
            ring = QRectF(dev_x + 94, dev_y + 10, 28, 28)
            p.setPen(QPen(QColor("#314958"), 4))
            p.drawArc(ring, 0, 360 * 16)
            active_pen = QPen(teal, 4)
            active_pen.setCapStyle(Qt.RoundCap)
            p.setPen(active_pen)
            p.drawArc(ring, -(self._tick * 18) * 16, -110 * 16)
            for idx in range(3):
                point = path.pointAtPercent(((self._tick / 38.0) + idx * 0.18) % 1.0)
                self._circle(p, point.x(), point.y() - 12, 2.5, teal2)

        elif self._mode == "success":
            self._circle(p, dev_x + 98, dev_y + 20, 18, QColor(122, 179, 23, 45))
            self._line(p, dev_x + 90, dev_y + 20, dev_x + 97, dev_y + 27, green, 4)
            self._line(p, dev_x + 97, dev_y + 27, dev_x + 108, dev_y + 12, green, 4)
            for idx in range(8):
                ang = idx * 0.78 + (self._tick / 20.0)
                sx = dev_x + 98 + 24 * math.cos(ang)
                sy = dev_y + 20 + 24 * math.sin(ang)
                self._circle(p, sx, sy, 2.5, QColor("#D9F7B6"))

        elif self._mode == "error":
            error_pen = QPen(red_dark, 4, Qt.DashLine)
            error_pen.setCapStyle(Qt.RoundCap)
            p.setPen(error_pen)
            p.drawPath(path)
            self._line(p, house_x + 122, house_y + 24, house_x + 150, house_y + 50, red, 3)
            self._line(p, house_x + 122, house_y + 50, house_x + 150, house_y + 24, red, 3)
            tri = QPainterPath()
            tri.moveTo(dev_x + 98, dev_y + 2)
            tri.lineTo(dev_x + 114, dev_y + 30)
            tri.lineTo(dev_x + 82, dev_y + 30)
            tri.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#E4B85E"))
            p.drawPath(tri)
            self._line(p, dev_x + 98, dev_y + 10, dev_x + 98, dev_y + 20, QColor("#5A430D"), 3)
            self._circle(p, dev_x + 98, dev_y + 24, 2.5, QColor("#5A430D"))
