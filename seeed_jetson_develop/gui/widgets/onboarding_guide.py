"""
首次启动引导界面 (Onboarding Guide) — 循环绘制动画版

设计特点：
- 深色无边框模态对话框，与主窗口主题一致
- 5 步引导流程，每步有独立的循环绘制动画场景
- 支持 Next / Back / Close 导航
- 支持 "不再显示" 复选框
- 支持键盘导航 (→ ← Esc)
"""
from __future__ import annotations

import math
import time
from pathlib import Path

from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, QPoint, QTimer
from PyQt5.QtGui import (
    QColor, QPixmap, QPainter, QFont, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPainterPath,
)
from PyQt5.QtWidgets import (
    QDialog, QWidget, QFrame, QStackedWidget, QSizePolicy,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGraphicsOpacityEffect,
)

from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_BG_LIGHT, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_GREEN2, C_GREEN_DIM, C_GREEN_GLOW, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    C_BORDER_SUBTLE, C_BORDER_CARD, C_BORDER_FOCUS,
    pt, make_label, make_button,
    apply_shadow,
)
from seeed_jetson_develop.gui.i18n import t, set_language as _save_language
from seeed_jetson_develop.resources import resolve_runtime_path

TOTAL_STEPS = 5
ANIM_DURATION = 350  # ms


# ──────────────────────────────────────────────────────────────────────────────
#  动画场景基类 — 使用 QTimer 驱动循环绘制
# ──────────────────────────────────────────────────────────────────────────────
class AnimationScene(QWidget):
    """循环动画场景基类。子类重写 paint_scene() 绘制内容，
    _timer 以 60fps 驱动 repaint，time 变量自动循环 [0, 1]。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._time = 0.0          # 动画相位 [0, 1)
        self._speed = 0.015       # 每帧增量 (~1 cycle / 1.1s)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)     # ~60 fps
        self.setMinimumSize(pt(380), pt(230))
        self.setMaximumSize(pt(500), pt(300))

    def sizeHint(self):
        return QSize(pt(480), pt(280))

    def _tick(self):
        self._time = (self._time + self._speed) % 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        self.paint_scene(painter, self._time)
        painter.end()

    def paint_scene(self, painter: QPainter, t: float):
        """子类重写此方法来绘制动画。"""
        pass

    def stop(self):
        self._timer.stop()

    def start(self):
        self._timer.start(16)


# ──────────────────────────────────────────────────────────────────────────────
#  Step 1: 欢迎 — Logo 呼吸脉动 + 粒子光点
# ──────────────────────────────────────────────────────────────────────────────
class WelcomeScene(AnimationScene):
    def paint_scene(self, p: QPainter, t: float):
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2

        # 背景光晕 — 呼吸效果
        breath = 0.85 + 0.15 * math.sin(t * math.pi * 2)
        radius = int(min(w, h) * 0.35 * breath)
        grad = QRadialGradient(cx, cy, radius)
        grad.setColorAt(0, QColor(141, 194, 31, int(40 * breath)))
        grad.setColorAt(1, QColor(141, 194, 31, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

        # 六边形 Seeed Logo 风格图标
        size = int(min(w, h) * 0.22)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C_GREEN))
        self._draw_hexagon(p, cx, cy, int(size * (0.95 + 0.05 * math.sin(t * math.pi * 4))))

        # 内部高光
        p.setBrush(QColor("#A8E030"))
        self._draw_hexagon(p, cx, cy - 2, int(size * 0.55))

        # 环绕粒子
        for i in range(6):
            angle = (i / 6 + t) * math.pi * 2
            px = cx + math.cos(angle) * size * 1.8
            py = cy + math.sin(angle) * size * 1.8
            pr = 2 + 2 * abs(math.sin(t * math.pi * 3 + i))
            alpha = int(120 + 80 * math.sin(t * math.pi * 2 + i))
            p.setBrush(QColor(141, 194, 31, alpha))
            p.drawEllipse(int(px - pr), int(py - pr), int(pr * 2), int(pr * 2))

    def _draw_hexagon(self, p: QPainter, cx: int, cy: int, r: int):
        pts = []
        for i in range(6):
            a = (i * 60 - 30) * math.pi / 180
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        path = QPainterPath()
        path.moveTo(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            path.lineTo(x, y)
        path.closeSubpath()
        p.drawPath(path)


# ──────────────────────────────────────────────────────────────────────────────
#  Step 2: Type-C 连接 — Jetson 设备连接笔记本
# ──────────────────────────────────────────────────────────────────────────────
class TypeCScene(AnimationScene):
    def paint_scene(self, p: QPainter, t: float):
        w, h = self.width(), self.height()
        base_y = h // 2

        # 笔记本
        lw, lh = pt(140), pt(90)
        lx = int(w * 0.15)
        ly = base_y - lh // 2
        self._draw_laptop(p, lx, ly, lw, lh, t)

        # Jetson 设备
        jw, jh = pt(80), pt(55)
        jx = int(w * 0.65)
        jy = base_y - jh // 2
        self._draw_jetson(p, jx, jy, jw, jh, t)

        # Type-C 线缆 — 数据流动画
        cable_y = base_y + pt(10)
        start_x = lx + lw
        end_x = jx
        mid_x = (start_x + end_x) // 2

        # 线缆主体
        pen = QPen(QColor(C_TEXT3))
        pen.setWidth(pt(3))
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(start_x, cable_y)
        path.cubicTo(mid_x - pt(20), cable_y - pt(15), mid_x + pt(20), cable_y + pt(15), end_x, cable_y)
        p.drawPath(path)

        # 数据流动点
        dot_count = 5
        for i in range(dot_count):
            phase = (t + i / dot_count) % 1.0
            # 沿贝塞尔曲线插值（简化用直线插值 + 正弦偏移）
            dx = start_x + (end_x - start_x) * phase
            dy = cable_y + math.sin(phase * math.pi) * pt(12)
            alpha = int(200 * math.sin(phase * math.pi))
            r = pt(3) + pt(1.5) * math.sin(t * math.pi * 4 + i)
            p.setBrush(QColor(141, 194, 31, max(0, alpha)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(int(dx - r), int(dy - r), int(r * 2), int(r * 2))

        # 连接成功闪烁提示
        if 0.7 < (t * 2) % 1.0 < 0.9:
            p.setPen(QPen(QColor(C_GREEN), pt(2)))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(int(jx - pt(6)), int(jy - pt(6)), jw + pt(12), jh + pt(12), pt(6), pt(6))

    def _draw_laptop(self, p: QPainter, x: int, y: int, w: int, h: int, t: float):
        # 屏幕
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C_CARD))
        p.drawRoundedRect(x, y, w, h, pt(6), pt(6))
        # 屏幕内容
        p.setBrush(QColor(C_BG_DEEP))
        p.drawRoundedRect(x + pt(4), y + pt(4), w - pt(8), h - pt(12), pt(4), pt(4))
        # 代码行闪烁
        line_colors = [C_GREEN, C_BLUE, C_ORANGE, C_TEXT2]
        for i, col in enumerate(line_colors):
            alpha = int(150 + 100 * math.sin(t * math.pi * 3 + i * 0.8))
            p.setBrush(QColor(col))
            lw = int((w - pt(16)) * (0.4 + 0.35 * math.sin(t * math.pi * 2 + i)))
            p.drawRoundedRect(x + pt(8), y + pt(10) + i * pt(10), lw, pt(4), pt(2), pt(2))
        # 底座
        p.setBrush(QColor(C_CARD_LIGHT))
        p.drawRoundedRect(x - pt(8), y + h - pt(4), w + pt(16), pt(8), pt(4), pt(4))
        # Type-C 接口闪烁
        p.setBrush(QColor(C_GREEN if (t * 2) % 1.0 > 0.5 else C_TEXT3))
        p.drawRoundedRect(x + w - pt(6), y + h - pt(12), pt(8), pt(4), pt(2), pt(2))

    def _draw_jetson(self, p: QPainter, x: int, y: int, w: int, h: int, t: float):
        # 设备外壳
        p.setPen(QPen(QColor(C_BORDER_SUBTLE), pt(1)))
        p.setBrush(QColor(C_CARD))
        p.drawRoundedRect(x, y, w, h, pt(6), pt(6))
        # 散热器鳍片
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C_BG_DEEP))
        for i in range(4):
            p.drawRoundedRect(x + pt(6), y + pt(6) + i * pt(11), w - pt(12), pt(7), pt(3), pt(3))
        # LED 指示灯 — 呼吸
        led_alpha = int(100 + 155 * abs(math.sin(t * math.pi * 2)))
        p.setBrush(QColor(141, 194, 31, led_alpha))
        p.drawEllipse(x + w - pt(14), y + h - pt(14), pt(8), pt(8))
        # Type-C 接口
        p.setBrush(QColor(C_TEXT3))
        p.drawRoundedRect(x - pt(2), y + h - pt(12), pt(6), pt(4), pt(2), pt(2))


# ──────────────────────────────────────────────────────────────────────────────
#  Step 3: 网线连接 + 刷机
# ──────────────────────────────────────────────────────────────────────────────
class EthernetScene(AnimationScene):
    def paint_scene(self, p: QPainter, t: float):
        w, h = self.width(), self.height()
        base_y = h // 2

        # 路由器/交换机
        rw, rh = pt(110), pt(55)
        rx = int(w * 0.12)
        ry = base_y - rh // 2
        self._draw_router(p, rx, ry, rw, rh, t)

        # Jetson 设备
        jw, jh = pt(85), pt(58)
        jx = int(w * 0.62)
        jy = base_y - jh // 2
        self._draw_jetson_box(p, jx, jy, jw, jh, t)

        # 网线连接 — 数据流动画
        cable_y = base_y + pt(12)
        start_x = rx + rw
        end_x = jx
        mid_y = cable_y + math.sin(t * math.pi * 2) * pt(8)

        pen = QPen(QColor("#5C7A99"))
        pen.setWidth(pt(3))
        p.setPen(pen)
        path = QPainterPath()
        path.moveTo(start_x, cable_y)
        path.lineTo(start_x + pt(30), cable_y)
        path.cubicTo(start_x + pt(60), cable_y, end_x - pt(40), mid_y, end_x - pt(10), cable_y)
        path.lineTo(end_x, cable_y)
        p.drawPath(path)

        # 数据包流动
        pkt_count = 4
        for i in range(pkt_count):
            phase = (t + i / pkt_count) % 1.0
            px = start_x + (end_x - start_x - pt(10)) * phase + pt(5)
            py = cable_y + math.sin(phase * math.pi) * pt(6) * math.sin(t * math.pi * 2 + i)
            alpha = int(180 * math.sin(phase * math.pi))
            sz = pt(5)
            p.setBrush(QColor(61, 142, 240, max(0, alpha)))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(int(px - sz // 2), int(py - sz // 2), sz, sz, pt(2), pt(2))

        # 绿色对勾闪烁（连接成功）
        if (t * 1.5) % 1.0 > 0.5:
            p.setPen(QPen(QColor(C_GREEN), pt(3)))
            p.setBrush(Qt.NoBrush)
            check_x = end_x + pt(10)
            check_y = cable_y
            p.drawLine(int(check_x), int(check_y), int(check_x + pt(5)), int(check_y + pt(6)))
            p.drawLine(int(check_x + pt(5)), int(check_y + pt(6)), int(check_x + pt(14)), int(check_y - pt(8)))

    def _draw_router(self, p: QPainter, x: int, y: int, w: int, h: int, t: float):
        p.setPen(QPen(QColor(C_BORDER_SUBTLE), pt(1)))
        p.setBrush(QColor(C_CARD))
        p.drawRoundedRect(x, y, w, h, pt(6), pt(6))
        # 天线
        p.setPen(QPen(QColor(C_TEXT3), pt(2)))
        p.drawLine(x + pt(15), y, x + pt(10), y - pt(25))
        p.drawLine(x + w - pt(15), y, x + w - pt(10), y - pt(25))
        # 网口灯闪烁
        for i in range(4):
            alpha = int(80 + 120 * abs(math.sin(t * math.pi * 3 + i * 0.7)))
            p.setBrush(QColor(61, 142, 240, alpha))
            p.drawEllipse(x + pt(12) + i * pt(22), y + h - pt(14), pt(6), pt(6))
        # 标签
        p.setPen(QColor(C_TEXT3))
        p.setFont(QFont("Sans", pt(8)))
        p.drawText(x, y + h + pt(14), w, pt(16), Qt.AlignCenter, "Router/Switch")

    def _draw_jetson_box(self, p: QPainter, x: int, y: int, w: int, h: int, t: float):
        p.setPen(QPen(QColor(C_BORDER_SUBTLE), pt(1)))
        p.setBrush(QColor(C_CARD))
        p.drawRoundedRect(x, y, w, h, pt(6), pt(6))
        # 网口
        p.setBrush(QColor("#3A4A5A"))
        p.drawRoundedRect(x + pt(8), y + h - pt(18), pt(20), pt(12), pt(3), pt(3))
        # LED
        led_alpha = int(80 + 175 * abs(math.sin(t * math.pi * 2.5)))
        p.setBrush(QColor(141, 194, 31, led_alpha))
        p.drawEllipse(x + w - pt(16), y + pt(10), pt(8), pt(8))
        # 标签
        p.setPen(QColor(C_TEXT2))
        p.setFont(QFont("Sans", pt(9)))
        p.drawText(x, y + h + pt(14), w, pt(16), Qt.AlignCenter, "Jetson")


# ──────────────────────────────────────────────────────────────────────────────
#  Step 4: 远程桌面 / SSH
# ──────────────────────────────────────────────────────────────────────────────
class RemoteScene(AnimationScene):
    def paint_scene(self, p: QPainter, t: float):
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2

        # 笔记本屏幕（左侧）
        sw, sh = pt(130), pt(90)
        sx = cx - sw - pt(20)
        sy = cy - sh // 2
        self._draw_monitor(p, sx, sy, sw, sh, t, is_ssh=False)

        # 终端窗口（右侧）
        tw, th = pt(130), pt(90)
        tx = cx + pt(20)
        ty = cy - th // 2
        self._draw_monitor(p, tx, ty, tw, th, t, is_ssh=True)

        # 连接波浪
        mid_x = cx
        wave_y = cy + pt(8)
        p.setPen(Qt.NoPen)
        for i in range(5):
            phase = (t + i / 5) % 1.0
            px = sx + sw + (tx - sx - sw) * phase
            py = wave_y + math.sin(phase * math.pi * 2 + t * math.pi * 4) * pt(8)
            alpha = int(150 * (1 - abs(phase - 0.5) * 2))
            r = pt(3) + pt(2) * math.sin(t * math.pi * 4 + i)
            p.setBrush(QColor(141, 194, 31, max(0, alpha)))
            p.drawEllipse(int(px - r), int(py - r), int(r * 2), int(r * 2))

        # 交换箭头
        arrow_alpha = int(150 + 100 * math.sin(t * math.pi * 2))
        p.setPen(QPen(QColor(141, 194, 31, arrow_alpha), pt(2)))
        ax = mid_x
        ay = cy - pt(35)
        p.drawLine(int(ax - pt(10)), int(ay), int(ax + pt(10)), int(ay))
        p.drawLine(int(ax + pt(6)), int(ay - pt(4)), int(ax + pt(10)), int(ay))
        p.drawLine(int(ax + pt(6)), int(ay + pt(4)), int(ax + pt(10)), int(ay))
        # 下箭头
        ay2 = cy + pt(35)
        p.drawLine(int(ax - pt(10)), int(ay2), int(ax + pt(10)), int(ay2))
        p.drawLine(int(ax - pt(6)), int(ay2 - pt(4)), int(ax - pt(10)), int(ay2))
        p.drawLine(int(ax - pt(6)), int(ay2 + pt(4)), int(ax - pt(10)), int(ay2))

    def _draw_monitor(self, p: QPainter, x: int, y: int, w: int, h: int, t: float, is_ssh: bool):
        # 屏幕外壳
        p.setPen(QPen(QColor(C_BORDER_SUBTLE), pt(1)))
        p.setBrush(QColor(C_CARD))
        p.drawRoundedRect(x, y, w, h, pt(5), pt(5))
        # 屏幕区域
        p.setBrush(QColor(C_BG_DEEP))
        p.drawRoundedRect(x + pt(3), y + pt(3), w - pt(6), h - pt(10), pt(3), pt(3))

        if is_ssh:
            # 终端效果
            colors = [C_GREEN, C_TEXT2, C_BLUE, C_ORANGE, C_TEXT3]
            for i, col in enumerate(colors):
                alpha = int(180 + 70 * math.sin(t * math.pi * 2 + i * 0.6))
                p.setBrush(QColor(col))
                lw = int((w - pt(14)) * (0.3 + 0.25 * math.sin(t * math.pi * 1.5 + i * 0.9)))
                p.drawRoundedRect(x + pt(7), y + pt(10) + i * pt(11), lw, pt(4), pt(2), pt(2))
            # 光标闪烁
            if (t * 2) % 1.0 > 0.3:
                p.setBrush(QColor(C_GREEN))
                cx = x + pt(7) + int((w - pt(14)) * 0.3)
                cy = y + pt(10) + 5 * pt(11) - pt(2)
                p.drawRect(cx, cy, pt(6), pt(10))
        else:
            # 桌面效果 — 窗口
            p.setBrush(QColor(C_CARD))
            p.drawRoundedRect(x + pt(8), y + pt(8), w - pt(16), h - pt(24), pt(3), pt(3))
            # 标题栏
            p.setBrush(QColor(C_BG_LIGHT))
            p.drawRoundedRect(x + pt(8), y + pt(8), w - pt(16), pt(14), pt(3), pt(3))
            p.setBrush(QColor(C_RED))
            p.drawEllipse(x + pt(14), y + pt(12), pt(5), pt(5))
            p.setBrush(QColor(C_ORANGE))
            p.drawEllipse(x + pt(24), y + pt(12), pt(5), pt(5))
            p.setBrush(QColor(C_GREEN))
            p.drawEllipse(x + pt(34), y + pt(12), pt(5), pt(5))
            # 桌面内容
            for i in range(3):
                row_alpha = int(100 + 80 * math.sin(t * math.pi * 1.5 + i * 0.7))
                p.setBrush(QColor(61, 142, 240, row_alpha))
                rw = int((w - pt(24)) * (0.5 + 0.3 * math.sin(t * math.pi * 2 + i)))
                p.drawRoundedRect(x + pt(14), y + pt(28) + i * pt(14), rw, pt(6), pt(3), pt(3))

        # 底座
        p.setBrush(QColor(C_CARD_LIGHT))
        p.drawRoundedRect(x + pt(20), y + h - pt(2), w - pt(40), pt(6), pt(3), pt(3))


# ──────────────────────────────────────────────────────────────────────────────
#  Step 5: App & Skills 浮动图标
# ──────────────────────────────────────────────────────────────────────────────
class AppsScene(AnimationScene):
    def paint_scene(self, p: QPainter, t: float):
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2

        # 中心火箭/发射台
        rocket_y = cy + int(math.sin(t * math.pi * 2) * pt(10))
        self._draw_rocket(p, cx, rocket_y, t)

        # 环绕浮动的 App 图标
        icons = [
            ("AI", C_BLUE), ("CV", C_ORANGE), ("NLP", C_GREEN),
            ("IoT", C_TEXT2), ("ROS", C_RED), ("GPU", C_BLUE),
        ]
        radius = min(w, h) * 0.32
        for i, (name, color) in enumerate(icons):
            angle = (i / len(icons) + t * 0.15) * math.pi * 2
            px = cx + math.cos(angle) * radius
            py = cy + math.sin(angle) * radius + math.sin(t * math.pi * 2 + i) * pt(8)
            float_scale = 0.9 + 0.1 * math.sin(t * math.pi * 3 + i * 0.8)
            self._draw_app_icon(p, int(px), int(py), name, color, float_scale)

        # 粒子尾迹
        p.setPen(Qt.NoPen)
        for i in range(8):
            phase = (t + i / 8) % 1.0
            px = cx + (phase - 0.5) * w * 0.8
            py = cy + pt(50) + math.sin(phase * math.pi * 4 + t * math.pi * 6) * pt(15)
            alpha = int(60 * (1 - phase))
            r = pt(2) + pt(2) * phase
            p.setBrush(QColor(141, 194, 31, max(0, alpha)))
            p.drawEllipse(int(px - r), int(py - r), int(r * 2), int(r * 2))

    def _draw_rocket(self, p: QPainter, cx: int, cy: int, t: float):
        # 火箭主体
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C_GREEN))
        body_w, body_h = pt(16), pt(40)
        bx, by = cx - body_w // 2, cy - body_h
        p.drawRoundedRect(bx, by, body_w, body_h, pt(8), pt(8))
        # 火箭头
        p.setBrush(QColor("#A8E030"))
        path = QPainterPath()
        path.moveTo(bx, by)
        path.lineTo(cx, by - pt(16))
        path.lineTo(bx + body_w, by)
        path.closeSubpath()
        p.drawPath(path)
        # 尾焰
        flame_h = pt(12) + int(pt(8) * abs(math.sin(t * math.pi * 6)))
        grad = QLinearGradient(cx, cy, cx, cy + flame_h)
        grad.setColorAt(0, QColor(255, 200, 50, 200))
        grad.setColorAt(1, QColor(255, 100, 30, 0))
        p.setBrush(QBrush(grad))
        path2 = QPainterPath()
        path2.moveTo(bx + pt(2), cy)
        path2.lineTo(cx, cy + flame_h)
        path2.lineTo(bx + body_w - pt(2), cy)
        path2.closeSubpath()
        p.drawPath(path2)

    def _draw_app_icon(self, p: QPainter, x: int, y: int, name: str, color: str, scale: float):
        sz = int(pt(32) * scale)
        p.setPen(QPen(QColor(color), pt(1)))
        p.setBrush(QColor(color))
        p.setOpacity(0.15)
        p.drawRoundedRect(x - sz // 2, y - sz // 2, sz, sz, pt(8), pt(8))
        p.setOpacity(1.0)
        p.setPen(QPen(QColor(color), pt(2)))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(x - sz // 2, y - sz // 2, sz, sz, pt(8), pt(8))
        # 文字
        p.setPen(QColor(color))
        p.setFont(QFont("Sans", pt(8)))
        p.drawText(x - sz // 2, y - sz // 2, sz, sz, Qt.AlignCenter, name)


# ──────────────────────────────────────────────────────────────────────────────
#  单步页面 — 包含动画场景 + 文字
# ──────────────────────────────────────────────────────────────────────────────
class StepPage(QWidget):
    """单步引导页面：上方动画场景 + 下方文字"""
    SCENES = [WelcomeScene, TypeCScene, EthernetScene, RemoteScene, AppsScene]

    def __init__(self, step_index: int, lang: str = "zh-CN", parent=None):
        super().__init__(parent)
        self.step_index = step_index
        self._lang = lang
        self._scene = None
        self._desc_labels: list[QLabel] = []
        self._tip_lbl: QLabel | None = None
        self._tip_container: QFrame | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(pt(40), pt(20), pt(40), pt(16))
        layout.setSpacing(pt(6))
        layout.setAlignment(Qt.AlignCenter)

        # 标题
        self._title = make_label(
            t(f"onboarding.step{self.step_index}.title", lang=self._lang),
            size=18, bold=True, color=C_TEXT
        )
        self._title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title)

        # 分隔装饰线
        sep = QWidget(self)
        sep.setFixedSize(pt(32), pt(2))
        sep.setStyleSheet(f"background:{C_GREEN}; border-radius:2px;")
        sep_layout = QHBoxLayout()
        sep_layout.setContentsMargins(0, 0, 0, 0)
        sep_layout.addStretch()
        sep_layout.addWidget(sep)
        sep_layout.addStretch()
        layout.addLayout(sep_layout)

        # 动画场景
        SceneClass = self.SCENES[self.step_index - 1]
        self._scene = SceneClass(self)
        layout.addWidget(self._scene, alignment=Qt.AlignCenter)

        # 内容区域（可扩展）
        content_widget = QWidget(self)
        content_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(pt(12), pt(2), pt(12), pt(2))
        content_layout.setSpacing(pt(5))
        content_layout.setAlignment(Qt.AlignCenter)

        # 描述文字（支持多行）
        self._desc_labels: list[QLabel] = []
        desc_key_base = f"onboarding.step{self.step_index}.desc"
        for i in range(1, 6):
            key = f"{desc_key_base}{i}"
            text = t(key, lang=self._lang)
            if text == key:
                break
            lbl = make_label(text, size=12, color=C_TEXT2, wrap=True)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(True)
            content_layout.addWidget(lbl)
            self._desc_labels.append(lbl)

        # 提示标签
        tip_key = f"onboarding.step{self.step_index}.tip"
        tip_text = t(tip_key, lang=self._lang)
        self._tip_lbl: QLabel | None = None
        self._tip_container: QFrame | None = None
        if tip_text != tip_key:
            tip_container = QFrame(content_widget)
            tip_container.setStyleSheet(f"""
                QFrame {{
                    background: {C_GREEN_GLOW};
                    border: 1px solid {C_BORDER_FOCUS};
                    border-radius: 6px;
                }}
            """)
            tip_layout = QHBoxLayout(tip_container)
            tip_layout.setContentsMargins(pt(12), pt(6), pt(12), pt(6))
            tip_lbl = make_label(tip_text, size=11, color=C_GREEN)
            tip_lbl.setWordWrap(True)
            tip_lbl.setAlignment(Qt.AlignCenter)
            tip_layout.addWidget(tip_lbl)
            content_layout.addWidget(tip_container, alignment=Qt.AlignCenter)
            self._tip_container = tip_container
            self._tip_lbl = tip_lbl

        layout.addWidget(content_widget, stretch=1)
        layout.addStretch()

    def stop_animation(self):
        if self._scene:
            self._scene.stop()

    def start_animation(self):
        if self._scene:
            self._scene.start()

    def set_language(self, lang: str):
        self._lang = lang
        self._title.setText(t(f"onboarding.step{self.step_index}.title", lang=lang))
        desc_key_base = f"onboarding.step{self.step_index}.desc"
        for i, lbl in enumerate(self._desc_labels, start=1):
            key = f"{desc_key_base}{i}"
            text = t(key, lang=lang)
            if text != key:
                lbl.setText(text)
        if self._tip_lbl is not None:
            tip_key = f"onboarding.step{self.step_index}.tip"
            tip_text = t(tip_key, lang=lang)
            if tip_text != tip_key:
                self._tip_lbl.setText(tip_text)

    def sizeHint(self):
        return QSize(pt(640), pt(480))

    def minimumSizeHint(self):
        return QSize(pt(560), pt(400))


# ──────────────────────────────────────────────────────────────────────────────
#  步骤指示器
# ──────────────────────────────────────────────────────────────────────────────
class StepIndicator(QWidget):
    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self._total = total
        self._current = 0
        self._dots: list[QLabel] = []
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(pt(10))
        layout.setAlignment(Qt.AlignCenter)
        for i in range(self._total):
            dot = QLabel(self)
            dot.setFixedSize(pt(10), pt(10))
            dot.setAlignment(Qt.AlignCenter)
            layout.addWidget(dot)
            self._dots.append(dot)
        self._update_style()

    def _update_style(self):
        for i, dot in enumerate(self._dots):
            if i == self._current:
                dot.setStyleSheet(f"""
                    QLabel {{ background: {C_GREEN}; border-radius: {pt(5)}px;
                             border: 2px solid {C_GREEN}; }}
                """)
            elif i < self._current:
                dot.setStyleSheet(f"""
                    QLabel {{ background: {C_GREEN_DIM}; border-radius: {pt(5)}px;
                             border: 2px solid {C_GREEN_DIM}; }}
                """)
            else:
                dot.setStyleSheet(f"""
                    QLabel {{ background: transparent; border-radius: {pt(5)}px;
                             border: 2px solid {C_TEXT3}; }}
                """)

    def set_current(self, index: int):
        if 0 <= index < self._total:
            self._current = index
            self._update_style()
            self._animate_dot(self._dots[index])

    def _animate_dot(self, dot: QLabel):
        anim = QPropertyAnimation(dot, b"minimumSize")
        anim.setDuration(300)
        anim.setEasingCurve(QEasingCurve.OutBack)
        big = QSize(pt(14), pt(14))
        normal = QSize(pt(10), pt(10))
        anim.setStartValue(normal)
        anim.setKeyValueAt(0.5, big)
        anim.setEndValue(normal)
        anim.start()


# ──────────────────────────────────────────────────────────────────────────────
#  主引导对话框
# ──────────────────────────────────────────────────────────────────────────────
class OnboardingGuide(QDialog):
    def __init__(self, lang: str = "zh-CN", parent=None):
        super().__init__(parent)
        self._lang = lang
        self._current_step = 0
        self._is_animating = False
        self._dismiss_checked = False

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        self._build_ui()
        self._update_buttons()

    def _build_ui(self):
        self._container = QFrame(self)
        self._container.setObjectName("onboardingContainer")
        self._container.setStyleSheet(f"""
            QFrame#onboardingContainer {{
                background: {C_BG_LIGHT};
                border: 1px solid {C_BORDER_CARD};
                border-radius: {pt(16)}px;
            }}
        """)
        apply_shadow(self._container, blur=30, y=8, alpha=80)

        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 标题栏
        header = QWidget(self._container)
        header.setFixedHeight(pt(48))
        header.setStyleSheet("background:transparent; border:none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(pt(12), 0, pt(12), 0)
        header_layout.setSpacing(pt(8))

        # 语言切换按钮
        self._lang_btn = QPushButton("EN / 中文", header)
        self._lang_btn.setCursor(Qt.PointingHandCursor)
        self._lang_btn.setFlat(True)
        self._lang_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                border: 1px solid {C_BORDER_SUBTLE};
                border-radius: {pt(6)}px;
                color: {C_TEXT2};
                font-size: {pt(11)}px;
                padding: {pt(4)}px {pt(10)}px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10);
                border-color: rgba(255,255,255,0.15);
                color: {C_TEXT};
            }}
        """)
        self._lang_btn.clicked.connect(self._toggle_language)
        header_layout.addWidget(self._lang_btn)
        header_layout.addStretch()

        self._close_btn = QPushButton("✕", header)
        self._close_btn.setFixedSize(pt(32), pt(32))
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_TEXT3};
                font-size: {pt(14)}px; font-weight: bold;
                border: none; border-radius: {pt(6)}px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.08); color: {C_TEXT}; }}
            QPushButton:pressed {{ background: rgba(255,255,255,0.12); }}
        """)
        self._close_btn.setToolTip(t("common.close", lang=self._lang))
        self._close_btn.clicked.connect(self._on_close)
        header_layout.addWidget(self._close_btn)
        container_layout.addWidget(header)

        # 页面栈
        self._stack = QStackedWidget(self._container)
        self._pages: list[StepPage] = []
        for i in range(1, TOTAL_STEPS + 1):
            page = StepPage(i, lang=self._lang, parent=self._stack)
            self._stack.addWidget(page)
            self._pages.append(page)
        container_layout.addWidget(self._stack, stretch=1)

        # 底部控制栏
        footer = QWidget(self._container)
        footer.setStyleSheet("background:transparent; border:none;")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(pt(32), pt(10), pt(32), pt(18))
        footer_layout.setSpacing(pt(10))

        self._indicator = StepIndicator(TOTAL_STEPS, footer)
        footer_layout.addWidget(self._indicator, alignment=Qt.AlignCenter)

        # 按钮行
        btn_row = QWidget(footer)
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(pt(12))

        self._back_btn = QPushButton(t("onboarding.back", lang=self._lang), btn_row)
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setFixedHeight(pt(36))
        self._back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {C_BORDER_SUBTLE};
                border-radius: 8px; color: {C_TEXT2};
                font-size: {pt(12)}px; font-weight: 600;
                padding: 0 {pt(20)}px; min-width: {pt(90)}px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.05);
                border-color: rgba(255,255,255,0.12); color: {C_TEXT}; }}
            QPushButton:pressed {{ background: rgba(255,255,255,0.08); }}
            QPushButton:disabled {{ color: {C_TEXT3};
                border-color: rgba(255,255,255,0.03); }}
        """)
        self._back_btn.clicked.connect(self._on_back)
        btn_row_layout.addWidget(self._back_btn)
        btn_row_layout.addStretch()

        self._next_btn = QPushButton(t("onboarding.next", lang=self._lang), btn_row)
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setFixedHeight(pt(36))
        self._next_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #A0D428, stop:1 #7AB317);
                border: 1px solid rgba(0,0,0,0.35);
                border-top-color: rgba(180,240,60,0.45);
                border-radius: 8px; color: #0A1800;
                font-size: {pt(12)}px; font-weight: 700;
                padding: 0 {pt(24)}px; min-width: {pt(110)}px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #B0E030, stop:1 #8DC21F);
                border-top-color: rgba(200,255,80,0.55);
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #6BA30F, stop:1 #7AB317);
            }}
        """)
        self._next_btn.clicked.connect(self._on_next)
        btn_row_layout.addWidget(self._next_btn)
        footer_layout.addWidget(btn_row)

        # 附加行
        extra_row = QWidget(footer)
        extra_row_layout = QHBoxLayout(extra_row)
        extra_row_layout.setContentsMargins(0, 0, 0, 0)
        extra_row_layout.setSpacing(0)

        self._dismiss_cb = QCheckBox(t("onboarding.dismiss", lang=self._lang), extra_row)
        self._dismiss_cb.setCursor(Qt.PointingHandCursor)
        self._dismiss_cb.setStyleSheet(f"""
            QCheckBox {{
                color: {C_TEXT3}; font-size: {pt(11)}px;
                spacing: {pt(6)}px; background: transparent;
            }}
            QCheckBox::indicator {{
                width: {pt(14)}px; height: {pt(14)}px;
                border-radius: {pt(3)}px; border: 1px solid {C_TEXT3};
                background: transparent;
            }}
            QCheckBox::indicator:checked {{
                background: {C_GREEN}; border-color: {C_GREEN};
            }}
            QCheckBox::indicator:hover {{ border-color: {C_TEXT2}; }}
        """)
        self._dismiss_cb.stateChanged.connect(self._on_dismiss_changed)
        extra_row_layout.addWidget(self._dismiss_cb)
        extra_row_layout.addStretch()

        self._skip_btn = QPushButton(t("onboarding.skip", lang=self._lang), extra_row)
        self._skip_btn.setCursor(Qt.PointingHandCursor)
        self._skip_btn.setFlat(True)
        self._skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {C_TEXT3}; font-size: {pt(11)}px;
                text-decoration: underline;
                padding: {pt(4)}px {pt(8)}px;
            }}
            QPushButton:hover {{ color: {C_TEXT2}; }}
        """)
        self._skip_btn.clicked.connect(self._on_close)
        extra_row_layout.addWidget(self._skip_btn)
        footer_layout.addWidget(extra_row)
        container_layout.addWidget(footer)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(pt(40), pt(40), pt(40), pt(40))
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self._container)

        self.setMinimumSize(pt(720), pt(540))
        self.resize(pt(780), pt(600))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_container'):
            margin = pt(40)
            self._container.setGeometry(
                margin, margin,
                self.width() - margin * 2,
                self.height() - margin * 2,
            )

    def showEvent(self, event):
        super().showEvent(event)
        self._pages[self._current_step].start_animation()

    def hideEvent(self, event):
        super().hideEvent(event)
        for page in self._pages:
            page.stop_animation()

    def _toggle_language(self):
        new_lang = "zh-CN" if self._lang == "en" else "en"
        self._lang = _save_language(new_lang)
        # 刷新所有页面文字
        for page in self._pages:
            page.set_language(self._lang)
        self._update_buttons()

    def _update_buttons(self):
        is_first = self._current_step == 0
        is_last = self._current_step == TOTAL_STEPS - 1

        self._back_btn.setEnabled(not is_first)
        self._back_btn.setVisible(not is_first)

        if is_last:
            self._next_btn.setText(t("onboarding.get_started", lang=self._lang))
            self._skip_btn.setVisible(False)
        else:
            self._next_btn.setText(t("onboarding.next", lang=self._lang))
            self._skip_btn.setVisible(True)

        self._indicator.set_current(self._current_step)

    def _on_next(self):
        if self._is_animating:
            return
        if self._current_step >= TOTAL_STEPS - 1:
            self._finish()
            return
        self._go_to_step(self._current_step + 1, forward=True)

    def _on_back(self):
        if self._is_animating or self._current_step <= 0:
            return
        self._go_to_step(self._current_step - 1, forward=False)

    def _go_to_step(self, target: int, forward: bool):
        if target < 0 or target >= TOTAL_STEPS:
            return

        self._is_animating = True
        old_page = self._pages[self._current_step]
        new_page = self._pages[target]

        # 页面淡入淡出切换
        old_effect = QGraphicsOpacityEffect(old_page)
        old_effect.setOpacity(1.0)
        old_page.setGraphicsEffect(old_effect)
        fade_out = QPropertyAnimation(old_effect, b"opacity")
        fade_out.setDuration(ANIM_DURATION)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.InCubic)
        fade_out.start()

        old_page.stop_animation()
        self._current_step = target
        self._stack.setCurrentIndex(target)
        new_page.start_animation()

        new_effect = QGraphicsOpacityEffect(new_page)
        new_effect.setOpacity(0.0)
        new_page.setGraphicsEffect(new_effect)
        fade_in = QPropertyAnimation(new_effect, b"opacity")
        fade_in.setDuration(ANIM_DURATION)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)
        fade_in.start()

        self._update_buttons()

        def _on_transition_done():
            self._is_animating = False
            # 清理临时 opacity effect，避免影响后续绘制性能
            old_page.setGraphicsEffect(None)
            new_page.setGraphicsEffect(None)

        QTimer.singleShot(ANIM_DURATION, _on_transition_done)

    def _on_close(self):
        self._save_dismiss_state()
        self.reject()

    def _finish(self):
        self._save_dismiss_state()
        self.accept()

    def _on_dismiss_changed(self, state):
        self._dismiss_checked = (state == Qt.Checked)

    def _save_dismiss_state(self):
        if self._dismiss_checked:
            from seeed_jetson_develop.core.config import set_onboarding_dismissed
            set_onboarding_dismissed(True)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right or event.key() == Qt.Key_Space:
            self._on_next()
        elif event.key() == Qt.Key_Left:
            self._on_back()
        elif event.key() == Qt.Key_Escape:
            self._on_close()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 180))
        super().paintEvent(event)

    def set_language(self, lang: str):
        self._lang = lang
        for page in self._pages:
            page.set_language(lang)
        self._back_btn.setText(t("onboarding.back", lang=lang))
        self._next_btn.setText(
            t("onboarding.get_started" if self._current_step == TOTAL_STEPS - 1 else "onboarding.next", lang=lang)
        )
        self._dismiss_cb.setText(t("onboarding.dismiss", lang=lang))
        self._skip_btn.setText(t("onboarding.skip", lang=lang))
        self._close_btn.setToolTip(t("common.close", lang=lang))


# ──────────────────────────────────────────────────────────────────────────────
#  便捷入口
# ──────────────────────────────────────────────────────────────────────────────
def show_onboarding(parent=None, lang: str = "zh-CN") -> bool:
    dlg = OnboardingGuide(lang=lang, parent=parent)
    if parent:
        dlg.resize(int(parent.width() * 0.75), int(parent.height() * 0.75))
        geo = parent.geometry()
        dlg.move(
            geo.x() + (geo.width() - dlg.width()) // 2,
            geo.y() + (geo.height() - dlg.height()) // 2,
        )
    result = dlg.exec_()
    return result == QDialog.Accepted
