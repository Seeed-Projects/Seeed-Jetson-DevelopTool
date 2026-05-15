"""Running task tray — shows in-progress background tasks at sidebar bottom.

Any long-running dialog (torch install, app install, demo run) can call
`task_registry.register(name, on_restore, on_cancel)` to appear as a row here,
then `update_status(...)` while running, and `finish(...)` when done.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional
import uuid

from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from seeed_jetson_develop.gui.theme import (
    C_BG_DEEP, C_CARD, C_CARD_LIGHT, C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3, pt,
)


STATUS_COLOR = {
    "running":  C_BLUE,
    "success":  C_GREEN,
    "failed":   C_RED,
    "warning":  C_ORANGE,
}


@dataclass
class TaskHandle:
    task_id: str
    name: str
    sub_text: str = ""
    status: str = "running"
    on_restore: Optional[Callable[[], None]] = None
    on_cancel: Optional[Callable[[], None]] = None


class _TaskRegistry(QObject):
    task_added   = pyqtSignal(object)
    task_updated = pyqtSignal(str)
    task_removed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._tasks: dict[str, TaskHandle] = {}

    def register(self, name: str, on_restore=None, on_cancel=None, sub_text: str = "") -> TaskHandle:
        handle = TaskHandle(
            task_id=str(uuid.uuid4())[:8],
            name=name,
            sub_text=sub_text,
            on_restore=on_restore,
            on_cancel=on_cancel,
        )
        self._tasks[handle.task_id] = handle
        self.task_added.emit(handle)
        return handle

    def update(self, task_id: str, *, sub_text: Optional[str] = None, status: Optional[str] = None):
        handle = self._tasks.get(task_id)
        if not handle:
            return
        if sub_text is not None:
            handle.sub_text = sub_text
        if status is not None:
            handle.status = status
        self.task_updated.emit(task_id)

    def remove(self, task_id: str):
        if task_id in self._tasks:
            del self._tasks[task_id]
            self.task_removed.emit(task_id)

    def all_tasks(self) -> list[TaskHandle]:
        return list(self._tasks.values())


task_registry = _TaskRegistry()


class _PulseDot(QWidget):
    """Tiny 8px dot with a gentle pulse animation."""
    def __init__(self, color: str = C_BLUE, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(pt(14), pt(14))

    def start(self):
        self._timer.start(50)

    def stop(self):
        self._timer.stop()
        self._phase = 0.0
        self.update()

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def _tick(self):
        try:
            self._phase = (self._phase + 0.05) % 1.0
            self.update()
        except RuntimeError:
            pass

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        import math
        alpha = 180 + int(75 * math.sin(self._phase * math.pi * 2))
        c = QColor(self._color)
        c.setAlpha(alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        sz = pt(6)
        x = (self.width() - sz) // 2
        y = (self.height() - sz) // 2
        p.drawEllipse(x, y, sz, sz)
        p.end()


class _TaskRow(QFrame):
    def __init__(self, handle: TaskHandle, parent=None):
        super().__init__(parent)
        self.handle = handle
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("TaskRow")
        self.setFixedHeight(pt(40))
        self._apply_style()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(pt(10), 0, pt(6), 0)
        lay.setSpacing(pt(8))

        self._dot = _PulseDot(color=STATUS_COLOR.get(handle.status, C_BLUE))
        self._dot.start()
        lay.addWidget(self._dot, 0, Qt.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        text_col.setContentsMargins(0, 0, 0, 0)

        self._name_lbl = QLabel(handle.name)
        self._name_lbl.setStyleSheet(
            f"color:{C_TEXT}; font-size:{pt(10)}pt; font-weight:600; background:transparent;"
        )
        self._name_lbl.setFixedHeight(pt(16))
        text_col.addWidget(self._name_lbl)

        self._sub_lbl = QLabel(handle.sub_text)
        self._sub_lbl.setStyleSheet(
            f"color:{C_TEXT3}; font-size:{pt(8)}pt; background:transparent;"
        )
        self._sub_lbl.setFixedHeight(pt(14))
        self._sub_lbl.setVisible(bool(handle.sub_text))
        text_col.addWidget(self._sub_lbl)
        lay.addLayout(text_col, 1)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(pt(20), pt(20))
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {C_TEXT3}; font-size: {pt(11)}pt;
            }}
            QPushButton:hover {{ color: {C_RED}; }}
        """)
        self._close_btn.clicked.connect(self._on_close_clicked)
        lay.addWidget(self._close_btn, 0, Qt.AlignVCenter)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QFrame#TaskRow {{
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: {pt(8)}px;
            }}
            QFrame#TaskRow:hover {{
                background: rgba(141,194,31,0.08);
                border-color: rgba(141,194,31,0.20);
            }}
        """)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.handle.on_restore:
            try:
                self.handle.on_restore()
            except Exception:
                pass
        super().mousePressEvent(ev)

    def _on_close_clicked(self):
        if self.handle.status == "running" and self.handle.on_cancel:
            try:
                self.handle.on_cancel()
            except Exception:
                pass
        else:
            task_registry.remove(self.handle.task_id)

    def apply_update(self):
        h = self.handle
        self._sub_lbl.setText(h.sub_text)
        self._sub_lbl.setVisible(bool(h.sub_text))
        color = STATUS_COLOR.get(h.status, C_BLUE)
        self._dot.set_color(color)
        if h.status != "running":
            self._dot.stop()


class RunningTaskPanel(QWidget):
    """Stack of TaskRow widgets, listens to task_registry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(pt(12), pt(4), pt(12), pt(4))
        self._lay.setSpacing(pt(4))

        self._header = QLabel("Tasks")
        self._header.setStyleSheet(
            f"color:{C_TEXT3}; font-size:{pt(9)}pt; font-weight:500; "
            f"background:transparent; padding-left:{pt(2)}px;"
        )
        self._header.setFixedHeight(pt(16))
        self._header.setVisible(False)
        self._lay.addWidget(self._header)

        self._rows: dict[str, _TaskRow] = {}

        task_registry.task_added.connect(self._on_added)
        task_registry.task_updated.connect(self._on_updated)
        task_registry.task_removed.connect(self._on_removed)

    def _on_added(self, handle: TaskHandle):
        row = _TaskRow(handle, parent=self)
        self._rows[handle.task_id] = row
        self._lay.addWidget(row)
        self._refresh_visibility()

    def _on_updated(self, task_id: str):
        row = self._rows.get(task_id)
        if row:
            row.apply_update()

    def _on_removed(self, task_id: str):
        row = self._rows.pop(task_id, None)
        if row:
            self._lay.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self._refresh_visibility()

    def _refresh_visibility(self):
        has_tasks = bool(self._rows)
        self._header.setVisible(has_tasks)
        self.setVisible(has_tasks)
