"""Floating AI assistant entry — edge-docked ball that opens the Agent page.

The floating ball keeps its drag / edge-peek behavior. Clicking it navigates
to the Agent page (local claude/codex CLI chat inside DevelopTool) instead of
opening the legacy LLM-API floating panel (removed).

The ``inject_*`` API is kept for module pages (skills/apps): it forwards the
payload to the Agent page after navigating to it.
"""
from __future__ import annotations

import logging

from qtpy.QtCore import (
    Qt, QTimer, QObject, QEvent, QPoint, QRect,
    QPropertyAnimation, QEasingCurve,
)
from qtpy.QtWidgets import QWidget

from seeed_jetson_develop.gui.i18n import get_language, t as _t_raw
from seeed_jetson_develop.gui.theme import pt as _pt


log = logging.getLogger("seeed.gui.ai_chat")


def _t(key: str, **kwargs) -> str:
    """Translate key using current language."""
    return _t_raw(key, lang=get_language(), **kwargs)


class FloatingAIAssistant(QObject):
    """Edge-docked floating ball: peek-hide, hover-reveal, free drag.

    The ball may be docked on the left sidebar edge or the right content edge.
    A click (press+release without moving) navigates to the Agent page.
    """

    _PEEK_RATIO = 0.32
    _HOVER_PAD = 36
    _HIDE_DELAY_MS = 900
    _SLIDE_MS = 220

    def __init__(self, host: QWidget, nav_index: int = 0, title: str = "AI Bot"):
        super().__init__(host)
        self._host = host
        self._title = title
        self._nav_index = nav_index
        self._ball_w = _pt(112)
        self._ball_h = _pt(72)
        self._margin = _pt(16)
        self._top_safe = _pt(84)
        self._dragging = False
        self._drag_moved = False
        self._drag_offset = QPoint()
        self._ball_pos = QPoint()
        self._dock_side = "left"
        self._peeking = True
        self._hovering = False
        self._initialized = False
        self._slide_anim: QPropertyAnimation | None = None
        # Compat: main window's frameless-resize filter reads these attrs.
        self._panel = None
        self._expanded = False

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._start_peek)

        self._build_ui()
        self._host.installEventFilter(self)
        self._ball.installEventFilter(self)
        QTimer.singleShot(0, self._bootstrap_position)

    def _build_ui(self):
        from seeed_jetson_develop.gui.widgets.breathing_button import BreathingButton
        self._ball = BreathingButton(self._title, self._host)
        self._ball.setFixedSize(self._ball_w, self._ball_h)
        self._ball.setCursor(Qt.SizeAllCursor)
        self._ball.setToolTip(_t("agent.ball.tooltip"))
        self._ball.setAttribute(Qt.WA_Hover, True)
        self._ball.show()
        self._ball.raise_()
        self._ball.start()
        # Need host mouse moves for proximity reveal while peeked.
        try:
            self._host.setMouseTracking(True)
        except Exception:
            pass
        cw = self._host.centralWidget() if hasattr(self._host, "centralWidget") else None
        if cw is not None:
            cw.setMouseTracking(True)

    def retranslate_ui(self, _lang: str | None = None):
        self._ball.setToolTip(_t("agent.ball.tooltip"))

    # ── navigation / injection ───────────────────────────────────────────

    def _navigate_to_agent(self):
        try:
            from seeed_jetson_develop.core.events import bus
            bus.navigate_to.emit(self._nav_index)
        except Exception:
            pass

    def _agent_page(self):
        stack = getattr(self._host, "stack", None)
        if stack is None or not (0 <= self._nav_index < stack.count()):
            return None
        return stack.widget(self._nav_index)

    def toggle_panel(self):
        """Ball click entry — kept name for compatibility."""
        self._navigate_to_agent()

    def show_panel(self):
        self._navigate_to_agent()

    def hide_panel(self):
        pass

    def _inject(self, method: str, *args):
        self._navigate_to_agent()
        page = self._agent_page()
        fn = getattr(page, method, None)
        if callable(fn):
            fn(*args)

    def inject_context(self, skill_name: str, skill_desc: str, commands: list):
        self._inject("inject_context", skill_name, skill_desc, commands)

    def inject_topic(self, title: str, summary: str, details=None):
        self._inject("inject_topic", title, summary, details)

    def inject_error(self, title: str, log_text: str):
        self._inject("inject_error", title, log_text)

    # ── ball geometry / behavior ─────────────────────────────────────────

    def _safe_ball_rect(self) -> QRect:
        """Whole window — left sidebar is a valid dock target."""
        left = self._margin
        top = self._top_safe
        right = max(left, self._host.width() - self._margin - self._ball_w)
        bottom = max(top, self._host.height() - self._margin - self._ball_h)
        return QRect(left, top, max(1, right - left + 1), max(1, bottom - top + 1))

    def _clamp_y(self, y: int) -> int:
        rect = self._safe_ball_rect()
        return min(max(y, rect.top()), rect.bottom())

    def _edge_x(self, side: str, peek: bool) -> int:
        host_w = self._host.width()
        peek_px = max(_pt(28), int(self._ball_w * self._PEEK_RATIO))
        if side == "left":
            return -self._ball_w + peek_px if peek else self._margin
        return host_w - peek_px if peek else host_w - self._margin - self._ball_w

    def _docked_pos(self, peek: bool | None = None) -> QPoint:
        if peek is None:
            peek = self._peeking
        return QPoint(self._edge_x(self._dock_side, peek), self._clamp_y(self._ball_pos.y()))

    def _bootstrap_position(self):
        if self._host.width() < 100 or self._host.height() < 100:
            QTimer.singleShot(50, self._bootstrap_position)
            return
        self._dock_side = "left"
        self._peeking = True
        self._ball_pos = QPoint(
            self._edge_x("left", True),
            self._clamp_y(self._host.height() - self._margin - self._ball_h),
        )
        self._initialized = True
        self._ball.move(self._ball_pos)
        self._ball.raise_()

    def _animate_to(self, pos: QPoint, duration: int | None = None):
        duration = self._SLIDE_MS if duration is None else duration
        if self._slide_anim is not None:
            self._slide_anim.stop()
            self._slide_anim.deleteLater()
            self._slide_anim = None
        self._ball_pos = QPoint(pos)
        anim = QPropertyAnimation(self._ball, b"pos", self)
        anim.setDuration(duration)
        anim.setStartValue(self._ball.pos())
        anim.setEndValue(pos)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._slide_anim = anim

    def _start_peek(self):
        if self._dragging or self._hovering:
            return
        self._peeking = True
        self._animate_to(self._docked_pos(True))

    def _reveal(self):
        if self._dragging:
            return
        self._hide_timer.stop()
        need = self._peeking or abs(self._ball.pos().x() - self._edge_x(self._dock_side, False)) > 2
        if need:
            self._peeking = False
            self._animate_to(self._docked_pos(False))

    def _near_ball(self, host_pos: QPoint) -> bool:
        pad = self._HOVER_PAD
        geo = self._ball.geometry().adjusted(-pad, -pad, pad, pad)
        if geo.contains(host_pos):
            return True
        if not self._peeking:
            return False
        y0 = self._clamp_y(self._ball_pos.y()) - pad
        y1 = y0 + self._ball_h + pad * 2
        if not (y0 <= host_pos.y() <= y1):
            return False
        if self._dock_side == "right":
            return host_pos.x() >= self._host.width() - self._HOVER_PAD * 2
        return host_pos.x() <= self._HOVER_PAD * 2

    def eventFilter(self, obj, event):
        et = event.type()

        if obj is self._host:
            if et in {QEvent.Resize, QEvent.Show}:
                if self._initialized:
                    self._ball_pos = self._docked_pos(self._peeking)
                    self._ball.move(self._ball_pos)
                    self._ball.raise_()
                return False
            if et == QEvent.MouseMove and not self._dragging:
                try:
                    gp = event.globalPosition().toPoint()
                except AttributeError:
                    gp = event.globalPos()
                local = self._host.mapFromGlobal(gp)
                near = self._near_ball(local)
                if near and not self._hovering:
                    self._hovering = True
                    self._reveal()
                elif not near and self._hovering:
                    self._hovering = False
                    self._hide_timer.start(self._HIDE_DELAY_MS)

        elif obj is self._ball:
            if et == QEvent.Enter:
                self._hovering = True
                self._reveal()
            elif et == QEvent.Leave and not self._dragging:
                self._hovering = False
                self._hide_timer.start(self._HIDE_DELAY_MS)
            elif et == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._dragging = True
                self._drag_moved = False
                self._drag_offset = event.pos()
                self._peeking = False
                self._hide_timer.stop()
                if self._slide_anim is not None:
                    self._slide_anim.stop()
                self._ball.grabMouse()
                self._ball.start()
                return True
            elif et == QEvent.MouseMove and self._dragging:
                new_pos = self._ball.mapToParent(event.pos() - self._drag_offset)
                if (new_pos - self._ball_pos).manhattanLength() > 3:
                    self._drag_moved = True
                self._set_ball_pos(new_pos)
                return True
            elif et == QEvent.MouseButtonRelease and self._dragging:
                self._dragging = False
                try:
                    self._ball.releaseMouse()
                except RuntimeError:
                    pass
                if self._drag_moved:
                    self._snap_to_side(animate=True)
                else:
                    self.toggle_panel()
                return True

        return super().eventFilter(obj, event)

    def _set_ball_pos(self, pos: QPoint):
        rect = self._safe_ball_rect()
        x = min(max(pos.x(), -self._ball_w // 2), self._host.width() - self._ball_w // 2)
        y = min(max(pos.y(), rect.top()), rect.bottom())
        self._ball_pos = QPoint(x, y)
        self._ball.move(self._ball_pos)
        self._ball.raise_()

    def _snap_to_side(self, animate: bool = True):
        center_x = self._ball_pos.x() + self._ball_w / 2
        self._dock_side = "left" if center_x < self._host.width() / 2 else "right"
        self._peeking = True
        target = self._docked_pos(True)
        if animate:
            self._animate_to(target)
        else:
            self._ball_pos = target
            self._ball.move(target)
        self._hovering = False

    def _constrain_ball(self):
        if not self._initialized:
            return
        self._ball_pos = self._docked_pos(self._peeking)
        self._ball.move(self._ball_pos)
        self._ball.raise_()
