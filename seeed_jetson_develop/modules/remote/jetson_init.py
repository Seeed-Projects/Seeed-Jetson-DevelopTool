"""Jetson initialization dialogs over serial."""
from __future__ import annotations

import os
import queue
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

import serial
import serial.tools.list_ports
from PyQt5.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from seeed_jetson_develop.gui.i18n import get_language, t
from seeed_jetson_develop.gui.i18n_binding import I18nBinding
from seeed_jetson_develop.gui.theme import (
    C_BG,
    C_CARD_LIGHT,
    C_GREEN,
    C_ORANGE,
    C_RED,
    C_TEXT,
    C_TEXT2,
    C_TEXT3,
    apply_shadow,
    ask_question_message,
    make_button,
    make_card,
    make_label,
    pt,
    show_info_message,
    show_warning_message,
)
from seeed_jetson_develop.modules.remote.native_terminal import NativeTerminalWidget

INIT_PENDING_KEYWORDS = (
    "System Configuration",
    "NVIDIA Driver License Agreement",
    "License For Customer Use of NVIDIA Software",
    "oem-config",
)
INIT_DONE_PATTERNS = (r"\blogin:\s*$", r"\bPassword:\s*$", r"[A-Za-z0-9._-]+@[\w.-]+:")
KNOWN_SERIAL_HOLDER_TOOLS = ("screen", "picocom", "tio", "minicom", "putty", "plink")


def _tr(key: str, default: str, lang: str | None = None, **kwargs) -> str:
    value = t(key, lang=lang, **kwargs)
    if value == key:
        return default.format(**kwargs) if kwargs else default
    return value


def list_serial_ports() -> list[str]:
    return sorted([p.device for p in serial.tools.list_ports.comports()])


def _strip_ansi(text: str) -> str:
    text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)
    return re.sub(r"\x1B[@-_]", "", text)


def _classify_serial_output(raw_text: str) -> dict:
    clean = _strip_ansi(raw_text).strip()
    compact = "\n".join(line.rstrip() for line in clean.splitlines() if line.strip())
    if not compact:
        return {"state": "unknown", "detail": "No clear serial output detected."}
    if any(k in compact for k in INIT_PENDING_KEYWORDS):
        return {"state": "not_initialized", "detail": "First-boot wizard detected. Continue setup over serial."}
    if any(re.search(p, compact, re.MULTILINE) for p in INIT_DONE_PATTERNS):
        return {"state": "initialized", "detail": "Login prompt detected. Device is likely initialized."}
    return {"state": "unknown", "detail": "Serial connected, but state is unclear."}


def probe_serial_status(port: str, timeout: float = 4.0) -> dict:
    try:
        ser = serial.Serial(port, baudrate=115200, timeout=0.25)
        ser.write(b"\r\n")
        chunks: list[bytes] = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = ser.read(4096)
            if data:
                chunks.append(data)
        ser.close()
        return _classify_serial_output(b"".join(chunks).decode("utf-8", errors="ignore"))
    except Exception as exc:
        return {"state": "error", "detail": str(exc)}


def _looks_like_port_busy(error_text: str) -> bool:
    text = (error_text or "").lower()
    return any(
        p in text
        for p in ("could not open port", "resource busy", "device or resource busy", "access is denied", "permission denied")
    )


def _linux_ps_value(pid: int, field: str) -> str:
    try:
        r = subprocess.run(["ps", "-p", str(pid), f"-o{field}="], capture_output=True, text=True, timeout=2)
        return r.stdout.strip()
    except Exception:
        return ""


def _linux_find_port_holder(port: str) -> dict | None:
    if shutil.which("lsof"):
        try:
            r = subprocess.run(["lsof", "-F", "pcu", "--", port], capture_output=True, text=True, timeout=3)
            pid = None
            command = ""
            user = ""
            for line in r.stdout.splitlines():
                if line.startswith("p") and line[1:].isdigit():
                    pid = int(line[1:])
                elif line.startswith("c") and pid and not command:
                    command = line[1:].strip()
                elif line.startswith("u") and pid and not user:
                    user = line[1:].strip()
                if pid and command:
                    return {"pid": pid, "command": command, "user": user}
        except Exception:
            pass
    if shutil.which("fuser"):
        try:
            r = subprocess.run(["fuser", port], capture_output=True, text=True, timeout=3)
            digits = re.findall(r"\d+", r.stdout or "")
            if digits:
                pid = int(digits[0])
                return {"pid": pid, "command": _linux_ps_value(pid, "comm"), "user": _linux_ps_value(pid, "user")}
        except Exception:
            pass
    return None


def inspect_serial_port_lock(port: str, error_text: str = "") -> dict:
    info = {"busy": False, "pid": None, "command": "", "releasable": False, "detail": ""}
    if sys.platform.startswith("linux"):
        holder = _linux_find_port_holder(port)
        if holder:
            command = holder.get("command", "") or "unknown process"
            pid = holder.get("pid")
            info.update(holder)
            info["busy"] = True
            info["releasable"] = any(tool in command.lower() for tool in KNOWN_SERIAL_HOLDER_TOOLS)
            info["detail"] = f"Detected {command} (PID {pid}) holding {port}."
            return info
    if _looks_like_port_busy(error_text):
        info["busy"] = True
        info["detail"] = f"{port} may be occupied by another process."
    return info


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def release_serial_port_lock(lock_info: dict) -> tuple[bool, str]:
    if not lock_info.get("busy"):
        return True, "No serial port lock detected."
    if not sys.platform.startswith("linux"):
        return False, "Auto release is only supported on Linux."
    if not lock_info.get("releasable"):
        return False, "Locking process is not a supported serial terminal."
    pid = lock_info.get("pid")
    command = lock_info.get("command", "external serial tool")
    if not pid:
        return False, "Cannot identify holder PID."
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True, f"{command} has exited."
    except Exception as exc:
        return False, f"Release failed: {exc}"
    deadline = time.time() + 1.5
    while time.time() < deadline:
        if not _pid_exists(pid):
            return True, f"Stopped {command} (PID {pid})."
        time.sleep(0.1)
    return False, f"Could not stop {command} (PID {pid}) automatically."


def _external_serial_commands(port: str) -> list[str]:
    if sys.platform == "win32":
        cmds = []
        if shutil.which("putty"):
            cmds.append(f"putty -serial {port} -sercfg 115200,8,n,1,N")
        if shutil.which("tio"):
            cmds.append(f"tio {port} -b 115200")
        return cmds
    quoted = shlex.quote(port)
    cmds: list[str] = []
    for tool, cmd in [
        ("screen", f"screen {quoted} 115200"),
        ("picocom", f"picocom -b 115200 {quoted}"),
        ("tio", f"tio {quoted} -b 115200"),
        ("minicom", f"minicom -D {quoted} -b 115200"),
    ]:
        if shutil.which(tool):
            cmds.append(cmd)
    return cmds


class _ProbeThread(QThread):
    finished_probe = pyqtSignal(dict)

    def __init__(self, port: str):
        super().__init__()
        self._port = port

    def run(self):
        self.finished_probe.emit(probe_serial_status(self._port))


class _EmbeddedSerialThread(QThread):
    opened = pyqtSignal()
    closed = pyqtSignal()
    output = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, port: str, baudrate: int = 115200):
        super().__init__()
        self._port = port
        self._baudrate = baudrate
        self._stop = False
        self._tx_queue: "queue.Queue[bytes]" = queue.Queue()
        self._ser: serial.Serial | None = None

    def send(self, data: bytes):
        if data:
            self._tx_queue.put(data)

    def stop(self):
        self._stop = True
        self._tx_queue.put(b"")

    def run(self):
        try:
            self._ser = serial.Serial(self._port, baudrate=self._baudrate, timeout=0.1, write_timeout=0.5)
            self.opened.emit()
        except Exception as exc:
            self.error.emit(str(exc))
            self.closed.emit()
            return
        try:
            while not self._stop:
                try:
                    while True:
                        payload = self._tx_queue.get_nowait()
                        if payload:
                            self._ser.write(payload)
                            self._ser.flush()
                except queue.Empty:
                    pass
                if self._ser.in_waiting:
                    chunk = self._ser.read(self._ser.in_waiting)
                    if chunk:
                        self.output.emit(chunk.decode("utf-8", errors="replace"))
                time.sleep(0.03)
        except Exception as exc:
            if not self._stop:
                self.error.emit(str(exc))
        finally:
            try:
                if self._ser and self._ser.is_open:
                    self._ser.close()
            finally:
                self.closed.emit()


class _SerialCmdThread(QThread):
    output = pyqtSignal(str)
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, port: str, username: str, password: str, command: str):
        super().__init__()
        self._port = port
        self._username = username
        self._password = password
        self._command = command
        self._stop = False
        self._ser: serial.Serial | None = None

    def _write(self, data: bytes):
        if self._ser and self._ser.is_open:
            self._ser.write(data)

    def _read_until(self, patterns: list[str], timeout: float) -> str:
        buf = ""
        deadline = time.time() + timeout
        while time.time() < deadline and not self._stop:
            if self._ser and self._ser.in_waiting:
                chunk = self._ser.read(self._ser.in_waiting).decode("utf-8", errors="ignore")
                if chunk:
                    buf += chunk
                    self.output.emit(chunk)
            else:
                time.sleep(0.05)
            for p in patterns:
                if re.search(p, buf):
                    return buf
        return buf

    def run(self):
        try:
            self._ser = serial.Serial(self._port, baudrate=115200, timeout=0.1)
            for _ in range(3):
                self._write(b"\r\n")
                time.sleep(0.3)
            buf = self._read_until([r"login:", r"[$#]\s*"], 8.0)
            if re.search(r"login:", buf):
                self._write((self._username + "\r\n").encode())
                buf = self._read_until([r"[Pp]assword:", r"[$#]\s*"], 8.0)
            if re.search(r"[Pp]assword:", buf):
                self._write((self._password + "\r\n").encode())
                buf = self._read_until([r"[$#]\s*", r"[Ll]ogin incorrect", r"[Aa]uthentication failure"], 10.0)
            if not re.search(r"[$#]\s*", buf):
                self.failed.emit("Login failed.")
                return
            self._write((self._command + "\r\n").encode())
            self.done.emit(self._read_until([r"[$#]\s*"], 20.0))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self._ser and self._ser.is_open:
                self._ser.close()

    def stop(self):
        self._stop = True


class JetsonInitDialog(QDialog):
    def __init__(self, parent=None, preferred_port: str = "", auto_open_terminal: bool = False):
        super().__init__(parent)
        self._lang = get_language()
        self._i18n = I18nBinding()
        self._probe_thread: _ProbeThread | None = None
        self._serial_thread: _EmbeddedSerialThread | None = None
        self._lock_info: dict | None = None
        self._auto_open_terminal_pending = auto_open_terminal

        self.setWindowTitle(_tr("remote.jetson_init.window_title", "Jetson Init", self._lang))
        self.setMinimumSize(pt(980), pt(680))
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        root.addWidget(self._scroll)

        body = QWidget()
        self._scroll.setWidget(body)

        root = QVBoxLayout(body)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        self._title_lbl = make_label(_tr("remote.jetson_init.title", "Jetson Init", self._lang), 16, C_TEXT, bold=True)
        self._subtitle_lbl = make_label(
            _tr(
                "remote.jetson_init.subtitle",
                "After flashing, complete first-boot setup via serial.",
                self._lang,
            ),
            11,
            C_TEXT2,
            wrap=True,
        )
        root.addWidget(self._title_lbl)
        root.addWidget(self._subtitle_lbl)

        content = QHBoxLayout()
        content.setSpacing(16)

        left_card = make_card(12)
        apply_shadow(left_card, blur=18, y=4, alpha=60)
        left = QVBoxLayout(left_card)
        left.setContentsMargins(18, 16, 18, 16)
        left.setSpacing(10)
        self._serial_port_lbl = make_label(_tr("remote.jetson_init.serial_port", "Serial Port", self._lang), 12, C_TEXT2)
        left.addWidget(self._serial_port_lbl)
        self.port_combo = QComboBox()
        left.addWidget(self.port_combo)

        row = QHBoxLayout()
        self.refresh_btn = make_button(_tr("remote.jetson_init.refresh_ports", "Refresh Ports", self._lang), small=True)
        self.detect_btn = make_button(_tr("remote.jetson_init.check_init_status", "Check Init Status", self._lang), small=True)
        self.open_btn = make_button(_tr("remote.jetson_init.connect_terminal", "Connect Terminal", self._lang), primary=True, small=True)
        row.addWidget(self.refresh_btn)
        row.addWidget(self.detect_btn)
        row.addWidget(self.open_btn)
        left.addLayout(row)

        self.cmd_preview = make_label("", 10, C_TEXT3, wrap=True)
        left.addWidget(self.cmd_preview)
        self.status_badge = QLabel(_tr("remote.jetson_init.status.pending", "Pending", self._lang))
        self.status_badge.setStyleSheet(f"background:{C_CARD_LIGHT}; color:{C_TEXT3}; border-radius:8px; padding:6px 12px; font-size:{pt(11)}pt; font-weight:700;")
        left.addWidget(self.status_badge, alignment=Qt.AlignLeft)
        self.status_text = make_label(_tr("remote.jetson_init.status.hint", "Select a port to begin.", self._lang), 11, C_TEXT2, wrap=True)
        left.addWidget(self.status_text)

        lock_row = QHBoxLayout()
        self.lock_hint = make_label("", 10, C_ORANGE, wrap=True)
        self.lock_hint.hide()
        self.release_lock_btn = make_button(_tr("remote.jetson_init.release_port", "Release Port", self._lang), small=True)
        self.release_lock_btn.hide()
        self.release_lock_btn.clicked.connect(self._release_port_lock)
        lock_row.addWidget(self.lock_hint, 1)
        lock_row.addWidget(self.release_lock_btn)
        left.addLayout(lock_row)

        right_card = make_card(12)
        right = QVBoxLayout(right_card)
        right.setContentsMargins(18, 16, 18, 16)
        right.setSpacing(10)
        top_row = QHBoxLayout()
        self._builtin_terminal_lbl = make_label(_tr("remote.jetson_init.builtin_terminal", "Built-in Terminal", self._lang), 12, C_TEXT, bold=True)
        top_row.addWidget(self._builtin_terminal_lbl)
        top_row.addStretch()
        self.terminal_status = make_label(_tr("remote.jetson_init.status.disconnected", "Disconnected", self._lang), 10, C_TEXT3)
        top_row.addWidget(self.terminal_status)
        right.addLayout(top_row)
        self.terminal_view = NativeTerminalWidget()
        self.terminal_view.setMinimumHeight(pt(280))
        self.terminal_view.setStyleSheet(f"QPlainTextEdit {{ background:{C_CARD_LIGHT}; border:none; border-radius:10px; color:{C_TEXT}; padding:12px; font-size:{pt(10)}pt; font-family:'Consolas','JetBrains Mono',monospace; }}")
        right.addWidget(self.terminal_view, 1)
        btn_row = QHBoxLayout()
        self.disconnect_btn = make_button(_tr("remote.jetson_init.disconnect", "Disconnect", self._lang), small=True)
        self.disconnect_btn.setEnabled(False)
        self.clear_terminal_btn = make_button(_tr("remote.jetson_init.clear", "Clear", self._lang), small=True)
        self.send_enter_btn = make_button(_tr("remote.jetson_init.send_enter", "Send Enter", self._lang), small=True)
        btn_row.addWidget(self.disconnect_btn)
        btn_row.addWidget(self.clear_terminal_btn)
        btn_row.addWidget(self.send_enter_btn)
        right.addLayout(btn_row)

        content.addWidget(left_card, 4)
        content.addWidget(right_card, 6)
        root.addLayout(content, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        self._close_btn = make_button(_tr("common.close", "Close", self._lang))
        self._close_btn.clicked.connect(self.accept)
        close_row.addWidget(self._close_btn)
        root.addLayout(close_row)

        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.detect_btn.clicked.connect(self.detect_status)
        self.open_btn.clicked.connect(self.open_terminal)
        self.disconnect_btn.clicked.connect(self.close_terminal)
        self.clear_terminal_btn.clicked.connect(self.terminal_view.clear_terminal)
        self.send_enter_btn.clicked.connect(lambda: self._send_terminal_bytes(b"\r"))
        self.terminal_view.input_bytes.connect(self._send_terminal_bytes)
        self.port_combo.currentTextChanged.connect(self._on_port_changed)
        self._bind_i18n()
        self.refresh_ports(preferred_port)
        if self._auto_open_terminal_pending and self._current_port():
            QTimer.singleShot(0, self.open_terminal)

    def showEvent(self, event):
        super().showEvent(event)
        from PyQt5.QtWidgets import QApplication
        geo = QApplication.primaryScreen().availableGeometry()
        max_w = int(geo.width()  * 0.95)
        max_h = int(geo.height() * 0.92)
        # 先把 minimumSize 约束到屏幕范围，否则 resize 无效
        self.setMinimumSize(min(self.minimumWidth(), max_w),
                            min(self.minimumHeight(), max_h))
        w = min(max(self.width(),  self.minimumWidth()),  max_w)
        h = min(max(self.height(), self.minimumHeight()), max_h)
        self.resize(w, h)
        x = geo.x() + (geo.width()  - self.width())  // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    def _bind_i18n(self):
        self._i18n.bind_callable(lambda: self.setWindowTitle(_tr("remote.jetson_init.window_title", "Jetson Init", self._lang)))
        self._i18n.bind_text(self._title_lbl, "remote.jetson_init.title")
        self._i18n.bind_text(self._subtitle_lbl, "remote.jetson_init.subtitle")
        self._i18n.bind_text(self._serial_port_lbl, "remote.jetson_init.serial_port")
        self._i18n.bind_text(self.refresh_btn, "remote.jetson_init.refresh_ports")
        self._i18n.bind_text(self.detect_btn, "remote.jetson_init.check_init_status")
        self._i18n.bind_text(self.open_btn, "remote.jetson_init.connect_terminal")
        self._i18n.bind_text(self.release_lock_btn, "remote.jetson_init.release_port")
        self._i18n.bind_text(self._builtin_terminal_lbl, "remote.jetson_init.builtin_terminal")
        self._i18n.bind_text(self.disconnect_btn, "remote.jetson_init.disconnect")
        self._i18n.bind_text(self.clear_terminal_btn, "remote.jetson_init.clear")
        self._i18n.bind_text(self.send_enter_btn, "remote.jetson_init.send_enter")
        self._i18n.bind_text(self._close_btn, "common.close")

    def retranslate_ui(self, lang: str | None = None):
        if lang:
            self._lang = lang
        self._i18n.apply(self._lang)
        self._update_ui(self._current_port())

    def _current_port(self) -> str:
        return self.port_combo.currentText().strip()

    def _set_lock_info(self, info: dict | None):
        self._lock_info = info if info and info.get("busy") else None
        if self._lock_info:
            self.lock_hint.setText(self._lock_info.get("detail", ""))
            self.lock_hint.show()
            self.release_lock_btn.setVisible(bool(self._lock_info.get("releasable")))
        else:
            self.lock_hint.hide()
            self.release_lock_btn.hide()

    def _set_state(self, level: str, badge: str, detail: str):
        color = {"ok": C_GREEN, "warn": C_ORANGE, "error": C_RED}.get(level, C_TEXT2)
        self.status_badge.setText(badge)
        self.status_badge.setStyleSheet(f"background:{C_CARD_LIGHT}; color:{color}; border-radius:8px; padding:6px 12px; font-size:{pt(11)}pt; font-weight:700;")
        self.status_text.setText(detail)

    def refresh_ports(self, preferred_port: str = ""):
        ports = list_serial_ports()
        old = self.port_combo.currentText()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItems(ports or [""])
        self.port_combo.blockSignals(False)
        target = preferred_port or old
        if target and target in ports:
            self.port_combo.setCurrentText(target)
        elif ports:
            self.port_combo.setCurrentIndex(0)
        self._update_ui(self._current_port())
        if not ports:
            self._set_state("warn", _tr("remote.jetson_init.status.no_ports", "No serial ports found", self._lang), _tr("remote.jetson_init.status.no_devices", "No serial devices detected.", self._lang))

    def _update_ui(self, port: str):
        commands = _external_serial_commands(port) if port else []
        if port and commands:
            self.cmd_preview.setText(_tr("remote.jetson_init.external_terminal", "External terminal: {command}", self._lang, command=commands[0]))
        elif port:
            self.cmd_preview.setText(_tr("remote.jetson_init.no_external_terminal", "No external terminal tool found. Use built-in terminal.", self._lang))
        else:
            self.cmd_preview.setText(_tr("remote.jetson_init.waiting_port", "Waiting for serial port...", self._lang))
        has_port = bool(port)
        self.open_btn.setEnabled(has_port and self._serial_thread is None)
        self.disconnect_btn.setEnabled(self._serial_thread is not None)
        self.detect_btn.setEnabled(has_port)

    def _on_port_changed(self, port: str):
        self._update_ui(port)

    def _release_port_lock(self):
        if not self._lock_info:
            return
        reply = ask_question_message(self, _tr("remote.jetson_init.release_port", "Release Port", self._lang), self._lock_info.get("detail", "") + "\n\n" + _tr("remote.jetson_init.release_confirm", "Try to release this port lock?", self._lang), buttons=QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        ok, msg = release_serial_port_lock(self._lock_info)
        if ok:
            show_info_message(self, _tr("remote.jetson_init.release_ok", "Released", self._lang), msg)
            self._set_lock_info(None)
            self.refresh_ports(self._current_port())
        else:
            show_warning_message(self, _tr("remote.jetson_init.release_failed", "Release failed", self._lang), msg)

    def detect_status(self):
        port = self._current_port()
        if not port:
            show_warning_message(self, _tr("common.notice", "Notice", self._lang), _tr("remote.jetson_init.select_port_first", "Please select a serial port first.", self._lang))
            return
        self.detect_btn.setEnabled(False)
        self.detect_btn.setText(_tr("common.checking", "Checking...", self._lang))
        self._set_state("info", _tr("common.checking_short", "Checking", self._lang), _tr("remote.jetson_init.reading_output", "Reading serial output from {port}...", self._lang, port=port))
        self._probe_thread = _ProbeThread(port)
        self._probe_thread.finished_probe.connect(self._on_probe_result)
        self._probe_thread.start()

    def _on_probe_result(self, result: dict):
        self.detect_btn.setEnabled(True)
        self.detect_btn.setText(_tr("remote.jetson_init.check_init_status", "Check Init Status", self._lang))
        state = result.get("state", "unknown")
        detail = result.get("detail", "")
        if state == "not_initialized":
            self._set_state("warn", _tr("remote.jetson_init.badge.not_initialized", "Not Initialized", self._lang), detail)
            self._set_lock_info(None)
        elif state == "initialized":
            self._set_state("ok", _tr("remote.jetson_init.badge.initialized", "Initialized", self._lang), detail)
            self._set_lock_info(None)
        elif state == "error":
            self._set_state("error", _tr("remote.jetson_init.badge.check_failed", "Check Failed", self._lang), detail)
            self._set_lock_info(inspect_serial_port_lock(self._current_port(), detail))
        else:
            self._set_state("info", _tr("remote.jetson_init.badge.unknown", "Unknown", self._lang), detail)
            self._set_lock_info(None)

    def _append_terminal(self, text: str):
        if text:
            self.terminal_view.feed(text)

    def open_terminal(self):
        port = self._current_port()
        if not port:
            show_warning_message(self, _tr("common.notice", "Notice", self._lang), _tr("remote.jetson_init.select_port_first", "Please select a serial port first.", self._lang))
            return
        if self._serial_thread is not None:
            self.terminal_view.focus_terminal()
            return
        self._append_terminal(f"\n[connecting] {port} @ 115200\n")
        th = _EmbeddedSerialThread(port)
        th.opened.connect(self._on_terminal_opened)
        th.output.connect(self._append_terminal)
        th.error.connect(self._on_terminal_error)
        th.closed.connect(self._on_terminal_closed)
        self._serial_thread = th
        self.terminal_status.setText(_tr("remote.jetson_init.status.connecting", "Connecting", self._lang))
        self.terminal_status.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(10)}pt; background:transparent; font-weight:700;")
        self._update_ui(port)
        th.start()

    def close_terminal(self):
        if self._serial_thread:
            self._serial_thread.stop()

    def _send_terminal_bytes(self, payload: bytes):
        if self._serial_thread:
            self._serial_thread.send(payload)
            self.terminal_view.focus_terminal()

    def _on_terminal_opened(self):
        self.terminal_status.setText(_tr("remote.jetson_init.status.connected", "Connected", self._lang))
        self.terminal_status.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(10)}pt; background:transparent; font-weight:700;")
        self._update_ui(self._current_port())
        self._send_terminal_bytes(b"\r")
        QTimer.singleShot(1000, lambda: self._send_terminal_bytes(b"export TERM=xterm-256color\r\n"))

    def _on_terminal_error(self, err: str):
        self._append_terminal(f"\n[error] {err}\n")
        self._set_lock_info(inspect_serial_port_lock(self._current_port(), err))
        self.terminal_status.setText(_tr("remote.jetson_init.status.failed", "Failed", self._lang))
        self.terminal_status.setStyleSheet(f"color:{C_RED}; font-size:{pt(10)}pt; background:transparent; font-weight:700;")

    def _on_terminal_closed(self):
        self._serial_thread = None
        if self.terminal_status.text() != _tr("remote.jetson_init.status.failed", "Failed", self._lang):
            self.terminal_status.setText(_tr("remote.jetson_init.status.disconnected", "Disconnected", self._lang))
            self.terminal_status.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(10)}pt; background:transparent;")
        self._update_ui(self._current_port())

    def closeEvent(self, event):
        self.close_terminal()
        if self._serial_thread and not self._serial_thread.wait(1200):
            self._serial_thread.terminate()
            self._serial_thread.wait(500)
        super().closeEvent(event)


def open_jetson_init_dialog(parent=None, preferred_port: str = "", auto_open_terminal: bool = False):
    dlg = JetsonInitDialog(parent=parent, preferred_port=preferred_port, auto_open_terminal=auto_open_terminal)
    lang = getattr(getattr(parent, "window", lambda: None)(), "_lang", None) if parent else None
    if hasattr(dlg, "retranslate_ui"):
        dlg.retranslate_ui(lang)
    dlg.exec_()


def _parse_interfaces(output: str) -> list[str]:
    ifaces = re.findall(r"^\d+:\s+([\w@]+):", _strip_ansi(output), re.MULTILINE)
    result = []
    for iface in ifaces:
        name = iface.split("@")[0]
        if name == "lo" or name.startswith(("docker", "virbr", "br-", "veth", "dummy")):
            continue
        result.append(name)
    return result


class JetsonNetConfigDialog(QDialog):
    def __init__(self, parent=None, preferred_port: str = ""):
        super().__init__(parent)
        self._lang = get_language()
        self._i18n = I18nBinding()
        self._cmd_thread: _SerialCmdThread | None = None
        self._lock_info: dict | None = None
        self.setWindowTitle(_tr("remote.jetson_net_config.window_title", "Jetson Network Config (Serial)", self._lang))
        self.setMinimumSize(pt(760), pt(660))
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        root.addWidget(self._scroll)

        body = QWidget()
        self._scroll.setWidget(body)

        root = QVBoxLayout(body)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)
        self._title_lbl = make_label(_tr("remote.jetson_net_config.title", "Jetson Network Config", self._lang), 16, C_TEXT, bold=True)
        self._subtitle_lbl = make_label(_tr("remote.jetson_net_config.subtitle", "Login over serial and configure static IP.", self._lang), 11, C_TEXT2, wrap=True)
        root.addWidget(self._title_lbl)
        root.addWidget(self._subtitle_lbl)

        login_card = make_card(12)
        apply_shadow(login_card, blur=18, y=4, alpha=60)
        ll = QVBoxLayout(login_card)
        ll.setContentsMargins(18, 16, 18, 16)
        ll.setSpacing(10)
        self._serial_login_lbl = make_label(_tr("remote.jetson_net_config.serial_login", "Serial Login", self._lang), 13, C_TEXT, bold=True)
        ll.addWidget(self._serial_login_lbl)
        field_label_w = pt(96)

        # Port row
        row_port = QHBoxLayout()
        row_port.setSpacing(10)
        self._port_lbl = make_label(_tr("remote.jetson_net_config.port", "Port", self._lang), 11, C_TEXT2)
        self._port_lbl.setFixedWidth(field_label_w)
        self._port_combo = QComboBox()
        self._port_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._port_combo.setMinimumHeight(pt(34))
        self._port_combo.setMaximumWidth(pt(760))
        self._port_combo.setStyleSheet(self._combo_style())
        self._refresh_btn = make_button(_tr("common.refresh", "Refresh", self._lang), small=True)
        self._refresh_btn.setMinimumWidth(pt(100))
        row_port.addWidget(self._port_lbl)
        row_port.addWidget(self._port_combo, 1)
        row_port.addWidget(self._refresh_btn)
        ll.addLayout(row_port)

        # Username row
        row_user = QHBoxLayout()
        row_user.setSpacing(10)
        self._username_lbl = make_label(_tr("common.username", "Username", self._lang), 11, C_TEXT2)
        self._username_lbl.setFixedWidth(field_label_w)
        self._user_edit = QLineEdit("seeed")
        self._user_edit.setMinimumWidth(pt(100))
        self._user_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._user_edit.setMaximumWidth(pt(760))
        self._user_edit.setStyleSheet(self._input_style())
        self._user_edit.setMinimumHeight(pt(34))
        row_user.addWidget(self._username_lbl)
        row_user.addWidget(self._user_edit, 1)
        ll.addLayout(row_user)

        # Password row
        row_pass = QHBoxLayout()
        row_pass.setSpacing(10)
        self._password_lbl = make_label(_tr("common.password", "Password", self._lang), 11, C_TEXT2)
        self._password_lbl.setFixedWidth(field_label_w)
        self._pass_edit = QLineEdit()
        self._pass_edit.setEchoMode(QLineEdit.Password)
        self._pass_edit.setMinimumWidth(pt(260))
        self._pass_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._pass_edit.setMaximumWidth(pt(760))
        self._pass_edit.setMinimumHeight(pt(34))
        self._pass_edit.setPlaceholderText(_tr("remote.jetson_net_config.password_placeholder", "Login password (also used for sudo)", self._lang))
        self._pass_edit.setStyleSheet(self._input_style())
        row_pass.addWidget(self._password_lbl)
        row_pass.addWidget(self._pass_edit, 1)
        ll.addLayout(row_pass)

        row3 = QVBoxLayout()
        self._scan_btn = make_button(_tr("remote.jetson_net_config.scan_ifaces", "Login and Detect Interfaces", self._lang), primary=True, small=True)
        self._scan_btn.setMinimumWidth(pt(260))
        self._scan_btn.setMaximumWidth(pt(320))
        self._login_status = make_label("", 11, C_TEXT3, wrap=True)
        scan_row = QHBoxLayout()
        scan_row.addWidget(self._scan_btn)
        scan_row.addStretch()
        row3.addLayout(scan_row)
        row3.addWidget(self._login_status)
        ll.addLayout(row3)
        lock = QHBoxLayout()
        self._lock_hint = make_label("", 10, C_ORANGE, wrap=True)
        self._lock_hint.hide()
        self._release_btn = make_button(_tr("remote.jetson_net_config.release_port", "Release Port", self._lang), small=True)
        self._release_btn.hide()
        self._release_btn.clicked.connect(self._release_port_lock)
        lock.addWidget(self._lock_hint, 1)
        lock.addWidget(self._release_btn)
        ll.addLayout(lock)
        root.addWidget(login_card)

        net_card = make_card(12)
        nl = QVBoxLayout(net_card)
        nl.setContentsMargins(18, 16, 18, 16)
        nl.setSpacing(10)
        self._ip_config_lbl = make_label(_tr("remote.jetson_net_config.ip_config", "Interface IP Config", self._lang), 13, C_TEXT, bold=True)
        nl.addWidget(self._ip_config_lbl)

        # Interface row
        row_iface = QHBoxLayout()
        row_iface.setSpacing(10)
        self._iface_lbl = make_label(_tr("remote.jetson_net_config.interface", "Interface", self._lang), 11, C_TEXT2)
        self._iface_lbl.setFixedWidth(field_label_w)
        self._iface_combo = QComboBox()
        self._iface_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._iface_combo.setMinimumHeight(pt(34))
        self._iface_combo.setMaximumWidth(pt(760))
        self._iface_combo.setStyleSheet(self._combo_style())
        self._iface_combo.setEnabled(False)
        row_iface.addWidget(self._iface_lbl)
        row_iface.addWidget(self._iface_combo, 1)
        nl.addLayout(row_iface)

        # IP row
        row_ip = QHBoxLayout()
        row_ip.setSpacing(10)
        self._ip_address_lbl = make_label(_tr("remote.jetson_net_config.ip_address", "IP Address", self._lang), 11, C_TEXT2)
        self._ip_address_lbl.setFixedWidth(field_label_w)
        self._ip_edit = QLineEdit()
        self._ip_edit.setPlaceholderText("192.168.1.100")
        self._ip_edit.setMinimumWidth(pt(110))
        self._ip_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._ip_edit.setMaximumWidth(pt(760))
        self._ip_edit.setMinimumHeight(pt(34))
        self._ip_edit.setStyleSheet(self._input_style())
        row_ip.addWidget(self._ip_address_lbl)
        row_ip.addWidget(self._ip_edit, 1)
        nl.addLayout(row_ip)

        # Subnet + Gateway row
        row_mg = QHBoxLayout()
        row_mg.setSpacing(10)
        self._mask_lbl = make_label(_tr("remote.jetson_net_config.mask", "Subnet Mask", self._lang), 11, C_TEXT2)
        self._mask_lbl.setFixedWidth(field_label_w)
        self._mask_edit = QLineEdit("24")
        self._mask_edit.setPlaceholderText(_tr("remote.jetson_net_config.mask_placeholder", "24 or 255.255.255.0", self._lang))
        self._mask_edit.setMinimumWidth(pt(100))
        self._mask_edit.setMaximumWidth(pt(220))
        self._mask_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._mask_edit.setMinimumHeight(pt(34))
        self._mask_edit.setStyleSheet(self._input_style())
        self._mask_edit.setToolTip(_tr("remote.jetson_net_config.mask_tip", "Supports CIDR or dotted format", self._lang))
        self._gateway_lbl = make_label(_tr("remote.jetson_net_config.gateway", "Gateway", self._lang), 11, C_TEXT2)
        self._gateway_lbl.setFixedWidth(pt(86))
        self._gw_edit = QLineEdit()
        self._gw_edit.setPlaceholderText(_tr("remote.jetson_net_config.gateway_placeholder", "192.168.1.1 (optional)", self._lang))
        self._gw_edit.setMinimumWidth(pt(110))
        self._gw_edit.setMaximumWidth(pt(340))
        self._gw_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._gw_edit.setMinimumHeight(pt(34))
        self._gw_edit.setStyleSheet(self._input_style())
        row_mg.addWidget(self._mask_lbl)
        row_mg.addWidget(self._mask_edit, 1)
        row_mg.addSpacing(8)
        row_mg.addWidget(self._gateway_lbl)
        row_mg.addWidget(self._gw_edit, 1)
        nl.addLayout(row_mg)
        row6 = QVBoxLayout()
        self._apply_btn = make_button(_tr("remote.jetson_net_config.apply", "Apply Config", self._lang), primary=True, small=True)
        self._apply_btn.setEnabled(False)
        self._apply_btn.setMinimumWidth(pt(180))
        self._apply_btn.setMaximumWidth(pt(240))
        self._apply_status = make_label("", 11, C_TEXT3, wrap=True)
        apply_row = QHBoxLayout()
        apply_row.addWidget(self._apply_btn)
        apply_row.addStretch()
        row6.addLayout(apply_row)
        row6.addWidget(self._apply_status)
        nl.addLayout(row6)
        root.addWidget(net_card)

        log_card = make_card(12)
        log_l = QVBoxLayout(log_card)
        log_l.setContentsMargins(18, 14, 18, 14)
        self._log_title_lbl = make_label(_tr("remote.jetson_net_config.log", "Serial Log", self._lang), 12, C_TEXT, bold=True)
        log_l.addWidget(self._log_title_lbl)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(pt(160))
        self._log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._log.setStyleSheet(f"QTextEdit {{ background:{C_CARD_LIGHT}; border:none; border-radius:8px; color:{C_TEXT2}; padding:10px; font-size:{pt(10)}pt; font-family:'JetBrains Mono','Consolas',monospace; }}")
        log_l.addWidget(self._log)
        root.addWidget(log_card, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        self._close_btn = make_button(_tr("common.close", "Close", self._lang))
        self._close_btn.clicked.connect(self.accept)
        close_row.addWidget(self._close_btn)
        root.addLayout(close_row)

        self._refresh_btn.clicked.connect(self._refresh_ports)
        self._scan_btn.clicked.connect(self._do_scan)
        self._apply_btn.clicked.connect(self._do_apply)
        self._bind_i18n()
        self._refresh_ports(preferred_port)

    def showEvent(self, event):
        super().showEvent(event)
        from PyQt5.QtWidgets import QApplication
        geo = QApplication.primaryScreen().availableGeometry()
        max_w = int(geo.width()  * 0.95)
        max_h = int(geo.height() * 0.92)
        # 先把 minimumSize 约束到屏幕范围，否则 resize 无效
        self.setMinimumSize(min(self.minimumWidth(), max_w),
                            min(self.minimumHeight(), max_h))
        w = min(max(self.width(),  self.minimumWidth()),  max_w)
        h = min(max(self.height(), self.minimumHeight()), max_h)
        self.resize(w, h)
        x = geo.x() + (geo.width()  - self.width())  // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    def _bind_i18n(self):
        self._i18n.bind_callable(lambda: self.setWindowTitle(_tr("remote.jetson_net_config.window_title", "Jetson Network Config (Serial)", self._lang)))
        self._i18n.bind_text(self._title_lbl, "remote.jetson_net_config.title")
        self._i18n.bind_text(self._subtitle_lbl, "remote.jetson_net_config.subtitle")
        self._i18n.bind_text(self._serial_login_lbl, "remote.jetson_net_config.serial_login")
        self._i18n.bind_text(self._port_lbl, "remote.jetson_net_config.port")
        self._i18n.bind_text(self._refresh_btn, "common.refresh")
        self._i18n.bind_text(self._username_lbl, "common.username")
        self._i18n.bind_text(self._password_lbl, "common.password")
        self._i18n.bind_placeholder(self._pass_edit, "remote.jetson_net_config.password_placeholder")
        self._i18n.bind_text(self._scan_btn, "remote.jetson_net_config.scan_ifaces")
        self._i18n.bind_text(self._release_btn, "remote.jetson_net_config.release_port")
        self._i18n.bind_text(self._ip_config_lbl, "remote.jetson_net_config.ip_config")
        self._i18n.bind_text(self._iface_lbl, "remote.jetson_net_config.interface")
        self._i18n.bind_text(self._ip_address_lbl, "remote.jetson_net_config.ip_address")
        self._i18n.bind_text(self._mask_lbl, "remote.jetson_net_config.mask")
        self._i18n.bind_placeholder(self._mask_edit, "remote.jetson_net_config.mask_placeholder")
        self._i18n.bind_tooltip(self._mask_edit, "remote.jetson_net_config.mask_tip")
        self._i18n.bind_text(self._gateway_lbl, "remote.jetson_net_config.gateway")
        self._i18n.bind_placeholder(self._gw_edit, "remote.jetson_net_config.gateway_placeholder")
        self._i18n.bind_text(self._apply_btn, "remote.jetson_net_config.apply")
        self._i18n.bind_text(self._log_title_lbl, "remote.jetson_net_config.log")
        self._i18n.bind_text(self._close_btn, "common.close")

    def retranslate_ui(self, lang: str | None = None):
        if lang:
            self._lang = lang
        self._i18n.apply(self._lang)

    def _input_style(self) -> str:
        return (
            f"QLineEdit {{"
            f" background:{C_CARD_LIGHT}; border:none; border-radius:8px;"
            f" padding:6px 10px; color:{C_TEXT}; font-size:{pt(11)}pt;"
            f"}}"
            f" QLineEdit:focus {{ background:#2a3040; }}"
        )

    def _combo_style(self) -> str:
        return (
            f"QComboBox {{"
            f" background:{C_CARD_LIGHT}; border:1px solid rgba(255,255,255,0.08); border-radius:8px;"
            f" padding:6px 10px; color:{C_TEXT}; font-size:{pt(11)}pt;"
            f"}}"
            f" QComboBox QAbstractItemView {{"
            f" background:{C_BG}; color:{C_TEXT}; selection-background-color:{C_CARD_LIGHT};"
            f" border:1px solid rgba(255,255,255,0.08);"
            f"}}"
        )

    def _refresh_ports(self, preferred: str = ""):
        ports = list_serial_ports()
        self._port_combo.blockSignals(True)
        self._port_combo.clear()
        self._port_combo.addItems(ports or [""])
        self._port_combo.blockSignals(False)
        if preferred and preferred in ports:
            self._port_combo.setCurrentText(preferred)
        elif ports:
            self._port_combo.setCurrentIndex(0)

    def _set_lock_info(self, info: dict | None):
        self._lock_info = info if info and info.get("busy") else None
        if self._lock_info:
            self._lock_hint.setText(self._lock_info.get("detail", ""))
            self._lock_hint.show()
            self._release_btn.setVisible(bool(self._lock_info.get("releasable")))
        else:
            self._lock_hint.hide()
            self._release_btn.hide()

    def _stop_cmd_thread(self, wait_ms: int = 1800):
        th = self._cmd_thread
        if not th:
            return
        try:
            th.stop()
        except Exception:
            pass
        if not th.wait(wait_ms):
            th.terminate()
            th.wait(500)
        if self._cmd_thread is th:
            self._cmd_thread = None

    def _release_port_lock(self):
        if not self._lock_info:
            return
        reply = ask_question_message(self, _tr("remote.jetson_net_config.release_port", "Release Port", self._lang), self._lock_info.get("detail", "") + "\n\n" + _tr("remote.jetson_net_config.release_confirm", "Try to release this port lock?", self._lang), buttons=QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        ok, msg = release_serial_port_lock(self._lock_info)
        if ok:
            show_info_message(self, _tr("remote.jetson_net_config.release_ok", "Released", self._lang), msg)
            self._set_lock_info(None)
            self._refresh_ports(self._port_combo.currentText().strip())
        else:
            show_warning_message(self, _tr("remote.jetson_net_config.release_failed", "Release failed", self._lang), msg)

    def _log_append(self, text: str):
        clean = _strip_ansi(text).replace("\r\n", "\n").replace("\r", "\n")
        if clean.strip():
            self._log.append(clean.rstrip())
            self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _do_scan(self):
        port = self._port_combo.currentText().strip()
        if not port:
            show_warning_message(self, _tr("common.notice", "Notice", self._lang), _tr("remote.jetson_net_config.select_port_first", "Please select a serial port first.", self._lang))
            return
        user = self._user_edit.text().strip() or "seeed"
        pwd = self._pass_edit.text()
        self._scan_btn.setEnabled(False)
        self._scan_btn.setText(_tr("common.loading", "Loading...", self._lang))
        self._login_status.setText(_tr("remote.jetson_net_config.logging_in", "Logging in...", self._lang))
        self._iface_combo.setEnabled(False)
        self._apply_btn.setEnabled(False)
        self._log.clear()
        self._stop_cmd_thread(wait_ms=300)
        self._cmd_thread = _SerialCmdThread(port, user, pwd, "ip link show")
        self._cmd_thread.output.connect(self._log_append)
        self._cmd_thread.done.connect(self._on_scan_done)
        self._cmd_thread.failed.connect(self._on_scan_failed)
        self._cmd_thread.start()

    def _on_scan_done(self, output: str):
        self._cmd_thread = None
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText(_tr("remote.jetson_net_config.scan_ifaces", "Login and Detect Interfaces", self._lang))
        ifaces = _parse_interfaces(output)
        if not ifaces:
            self._login_status.setText(_tr("remote.jetson_net_config.no_ifaces", "No available interfaces found", self._lang))
            self._login_status.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(11)}pt; background:transparent;")
            return
        self._iface_combo.clear()
        self._iface_combo.addItems(ifaces)
        self._iface_combo.setEnabled(True)
        self._apply_btn.setEnabled(True)
        self._login_status.setText(_tr("remote.jetson_net_config.login_ok", "Login successful, found {count} interfaces", self._lang, count=len(ifaces)))
        self._login_status.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(11)}pt; background:transparent; font-weight:700;")

    def _on_scan_failed(self, err: str):
        self._cmd_thread = None
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText(_tr("remote.jetson_net_config.scan_ifaces", "Login and Detect Interfaces", self._lang))
        self._login_status.setText(_tr("remote.jetson_net_config.failed_with_error", "Failed: {err}", self._lang, err=err))
        self._login_status.setStyleSheet(f"color:{C_RED}; font-size:{pt(11)}pt; background:transparent;")
        self._set_lock_info(inspect_serial_port_lock(self._port_combo.currentText().strip(), err))

    def _do_apply(self):
        port = self._port_combo.currentText().strip()
        user = self._user_edit.text().strip() or "seeed"
        pwd = self._pass_edit.text()
        iface = self._iface_combo.currentText().strip()
        ip = self._ip_edit.text().strip()
        mask = self._mask_edit.text().strip() or "24"
        if "." in mask:
            try:
                mask = str(sum(bin(int(x)).count("1") for x in mask.split(".")))
            except Exception:
                pass
        gw = self._gw_edit.text().strip()
        if not ip:
            show_warning_message(self, _tr("common.notice", "Notice", self._lang), _tr("remote.jetson_net_config.ip_required", "Please enter an IP address.", self._lang))
            return
        if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
            show_warning_message(self, _tr("common.notice", "Notice", self._lang), _tr("remote.jetson_net_config.ip_invalid", "IP address format is invalid.", self._lang))
            return
        con_name = f"static-{iface}"
        ip_cidr = f"{ip}/{mask}"
        pwd_escaped = pwd.replace("'", "'\\''")
        inner = (
            f"nmcli con delete '{con_name}' 2>/dev/null; "
            f"nmcli con add type ethernet ifname {iface} con-name '{con_name}' "
            f"ipv4.method manual ipv4.addresses {ip_cidr}"
            + (f" ipv4.gateway {gw}" if gw else "")
            + f" && nmcli con up '{con_name}'"
        )
        command = f"echo '{pwd_escaped}' | sudo -S bash -c '{inner}'"
        self._apply_btn.setEnabled(False)
        self._apply_btn.setText(_tr("remote.jetson_net_config.applying", "Applying...", self._lang))
        self._apply_status.setText("")
        self._log.append(_tr("remote.jetson_net_config.apply_log", "\n[apply] {iface} -> {ip_cidr}{gw_part}\n", self._lang, iface=iface, ip_cidr=ip_cidr, gw_part=(f" gw {gw}" if gw else "")))
        self._stop_cmd_thread(wait_ms=300)
        self._cmd_thread = _SerialCmdThread(port, user, pwd, command)
        self._cmd_thread.output.connect(self._log_append)
        self._cmd_thread.done.connect(self._on_apply_done)
        self._cmd_thread.failed.connect(self._on_apply_failed)
        self._cmd_thread.start()

    def _on_apply_done(self, output: str):
        self._cmd_thread = None
        self._apply_btn.setEnabled(True)
        self._apply_btn.setText(_tr("remote.jetson_net_config.apply", "Apply Config", self._lang))
        ip = self._ip_edit.text().strip()
        if "Error" in output or "error" in output:
            self._apply_status.setText(_tr("remote.jetson_net_config.apply_maybe_failed", "Configuration may have failed. Check logs.", self._lang))
            self._apply_status.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(11)}pt; background:transparent;")
        else:
            self._apply_status.setText(_tr("remote.jetson_net_config.apply_done", "Configuration completed. Device IP: {ip}", self._lang, ip=ip))
            self._apply_status.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(11)}pt; background:transparent; font-weight:700;")

    def _on_apply_failed(self, err: str):
        self._cmd_thread = None
        self._apply_btn.setEnabled(True)
        self._apply_btn.setText(_tr("remote.jetson_net_config.apply", "Apply Config", self._lang))
        self._apply_status.setText(_tr("remote.jetson_net_config.failed_with_error", "Failed: {err}", self._lang, err=err))
        self._apply_status.setStyleSheet(f"color:{C_RED}; font-size:{pt(11)}pt; background:transparent;")
        self._set_lock_info(inspect_serial_port_lock(self._port_combo.currentText().strip(), err))

    def closeEvent(self, event):
        self._stop_cmd_thread()
        super().closeEvent(event)


def open_jetson_net_config_dialog(parent=None, preferred_port: str = ""):
    dlg = JetsonNetConfigDialog(parent=parent, preferred_port=preferred_port)
    lang = getattr(getattr(parent, "window", lambda: None)(), "_lang", None) if parent else None
    if hasattr(dlg, "retranslate_ui"):
        dlg.retranslate_ui(lang)
    dlg.exec_()
