from __future__ import annotations

from collections.abc import Mapping

import pyte
from PyQt5.QtCore import QEvent, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import QApplication, QPlainTextEdit, QTextEdit

from seeed_jetson_develop.gui.theme import build_mono_font


class NativeTerminalWidget(QPlainTextEdit):
    input_bytes = pyqtSignal(bytes)

    def __init__(self, parent=None, columns: int = 100, lines: int = 28, history: int = 2000):
        super().__init__(parent)
        self._columns = max(40, columns)
        self._lines = max(10, lines)
        self._history = history
        self._screen = pyte.HistoryScreen(self._columns, self._lines, history=self._history)
        self._stream = pyte.Stream(self._screen)
        self._updating = False
        self._cursor_visible = True

        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setUndoRedoEnabled(False)
        self.setCursorWidth(0)
        self.setTabChangesFocus(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFrameShape(self.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setCenterOnScroll(False)
        font = build_mono_font(10)
        self.setFont(font)

    def clear_terminal(self):
        self._screen.reset()
        self._render()

    def focus_terminal(self):
        self.setFocus()

    def feed(self, text: str):
        if not text:
            return
        self._stream.feed(text)
        self._render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        metrics = QFontMetrics(self.font())
        char_width = max(1, metrics.horizontalAdvance("M"))
        char_height = max(1, metrics.lineSpacing())
        viewport = self.viewport().size()
        columns = max(40, viewport.width() // char_width)
        lines = max(10, viewport.height() // char_height)
        if columns != self._columns or lines != self._lines:
            self._columns = columns
            self._lines = lines
            self._screen.resize(lines=self._lines, columns=self._columns)
            self._render()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._cursor_visible = True
        self._render()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._cursor_visible = False
        self._render()

    def keyPressEvent(self, event):
        payload = self._encode_key(event)
        if payload is not None:
            event.accept()
            self.input_bytes.emit(payload)
            return
        super().keyPressEvent(event)

    def event(self, event):
        if event.type() == QEvent.ShortcutOverride and event.key() in (Qt.Key_Tab, Qt.Key_Backtab):
            event.accept()
            return True
        return super().event(event)

    def focusNextPrevChild(self, next_: bool) -> bool:
        return False

    def _encode_key(self, event) -> bytes | None:
        key = event.key()
        mods = event.modifiers()

        if mods & Qt.ControlModifier:
            if key == Qt.Key_C:
                return b"\x03"
            if key == Qt.Key_D:
                return b"\x04"
            if key == Qt.Key_L:
                return b"\x0c"
            if key == Qt.Key_V:
                text = QApplication.clipboard().text()
                if text:
                    return text.replace("\r\n", "\n").replace("\n", "\r").encode("utf-8")
                return b""
            if Qt.Key_A <= key <= Qt.Key_Z:
                return bytes([key - Qt.Key_A + 1])

        specials = {
            Qt.Key_Return: b"\r",
            Qt.Key_Enter: b"\r",
            Qt.Key_Backspace: b"\x7f",
            Qt.Key_Delete: b"\x1b[3~",
            Qt.Key_Tab: b"\t",
            Qt.Key_Escape: b"\x1b",
            Qt.Key_Up: b"\x1b[A",
            Qt.Key_Down: b"\x1b[B",
            Qt.Key_Right: b"\x1b[C",
            Qt.Key_Left: b"\x1b[D",
            Qt.Key_Home: b"\x1b[H",
            Qt.Key_End: b"\x1b[F",
            Qt.Key_PageUp: b"\x1b[5~",
            Qt.Key_PageDown: b"\x1b[6~",
        }
        if key in specials:
            if key == Qt.Key_Tab and mods & Qt.ShiftModifier:
                return b"\x1b[Z"
            return specials[key]

        text = event.text()
        if text:
            return text.encode("utf-8")
        return None

    def _line_to_text(self, line: Mapping[int, object]) -> str:
        chars: list[str] = []
        for idx in range(self._columns):
            char = line.get(idx)
            chars.append(getattr(char, "data", " ") if char is not None else " ")
        return "".join(chars).rstrip()

    def _render(self):
        if self._updating:
            return
        lines = [self._line_to_text(line) for line in list(self._screen.history.top)]
        lines.extend(self._screen.display)
        if not lines:
            lines = [""]

        cursor_selection = None
        if self._cursor_visible and 0 <= self._screen.cursor.y < len(self._screen.display):
            idx = len(lines) - len(self._screen.display) + self._screen.cursor.y
            row = lines[idx]
            cursor_x = max(0, self._screen.cursor.x)
            if cursor_x >= len(row):
                row = row.ljust(cursor_x + 1)
                lines[idx] = row
            cursor_selection = (idx, cursor_x)

        content = "\n".join(lines)
        self._updating = True
        try:
            scrollbar = self.verticalScrollBar()
            was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
            self.setPlainText(content)
            self.setExtraSelections(self._build_cursor_selections(cursor_selection))
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)
            if was_at_bottom:
                scrollbar.setValue(scrollbar.maximum())
        finally:
            self._updating = False

    def _build_cursor_selections(self, cursor_selection):
        if cursor_selection is None:
            return []

        line_no, column = cursor_selection
        block = self.document().findBlockByNumber(line_no)
        if not block.isValid():
            return []

        position = block.position() + min(column, block.length() - 1)
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)

        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format = QTextCharFormat()
        selection.format.setBackground(QColor("#7AB317"))
        selection.format.setForeground(QColor("#0B0F14"))
        return [selection]
