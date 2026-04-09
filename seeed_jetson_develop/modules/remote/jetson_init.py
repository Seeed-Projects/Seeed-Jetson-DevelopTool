"""Jetson 初始化对话框与串口检测辅助。跨平台实现（pyserial）。"""
from __future__ import annotations

import os
import queue
import re
import signal
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import serial
import serial.tools.list_ports

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from seeed_jetson_develop.modules.remote.native_terminal import NativeTerminalWidget

from seeed_jetson_develop.gui.theme import (
    C_BG, C_CARD_LIGHT, C_GREEN, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    apply_shadow, ask_question_message, make_button, make_card,
    make_label, pt, show_info_message, show_warning_message,
)

# ── 常量 ──────────────────────────────────────────────────────────────────────

INIT_PENDING_KEYWORDS = (
    "System Configuration",
    "NVIDIA Driver License Agreement",
    "License For Customer Use of NVIDIA Software",
    "oem-config",
)

INIT_DONE_PATTERNS = (
    r"\blogin:\s*$",
    r"\bPassword:\s*$",
    r"[A-Za-z0-9._-]+@[\w.-]+:",
)

KNOWN_SERIAL_HOLDER_TOOLS = ("screen", "picocom", "tio", "minicom", "putty", "plink")

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def list_serial_ports() -> list[str]:
    """跨平台列出串口：Linux /dev/ttyACM* /dev/ttyUSB*，Windows COM*。"""
    ports = [p.device for p in serial.tools.list_ports.comports()]
    return sorted(ports)


def _strip_ansi(text: str) -> str:
    text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"\x1B[@-_]", "", text)
    return text

def _classify_serial_output(raw_text: str) -> dict:
    clean = _strip_ansi(raw_text).strip()
    compact = "\n".join(line.rstrip() for line in clean.splitlines() if line.strip())
    if not compact:
        return {"state": "unknown", "title": "未读取到明确串口输出",
                "detail": "请确认设备已上电，并按回车后重试。", "excerpt": ""}
    if any(k in compact for k in INIT_PENDING_KEYWORDS):
        return {"state": "not_initialized", "title": "检测到首次启动初始化向导",
                "detail": "这台 Jetson 还未完成系统初始化，需要通过串口继续配置用户名、密码和基础系统设置。",
                "excerpt": compact}
    if any(re.search(p, compact, re.MULTILINE) for p in INIT_DONE_PATTERNS):
        return {"state": "initialized", "title": "检测到正常登录提示",
                "detail": "设备大概率已经完成初始化，可以直接通过串口登录或继续配置 SSH。",
                "excerpt": compact}
    return {"state": "unknown", "title": "串口已连通，但未识别到明确状态",
            "detail": "可能处于启动中、停留在其他菜单，或输出较少。建议继续查看串口终端。",
            "excerpt": compact}


def probe_serial_status(port: str, timeout: float = 4.0) -> dict:
    """用 pyserial 探测串口状态，跨平台。"""
    try:
        ser = serial.Serial(port, baudrate=115200, timeout=0.25,
                            bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                            stopbits=serial.STOPBITS_ONE)
        ser.write(b"\r\n")
        chunks: list[bytes] = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = ser.read(4096)
            if data:
                chunks.append(data)
        ser.close()
        raw = b"".join(chunks).decode("utf-8", errors="ignore")
        return _classify_serial_output(raw)
    except Exception as exc:
        return {"state": "error", "title": "串口检测失败", "detail": str(exc), "excerpt": ""}


def _looks_like_port_busy(error_text: str) -> bool:
    text = (error_text or "").lower()
    return any(pattern in text for pattern in (
        "could not open port",
        "resource busy",
        "device or resource busy",
        "access is denied",
        "permission denied",
        "errno 16",
        "errno 13",
        "设备或资源忙",
        "拒绝访问",
    ))


def _linux_ps_value(pid: int, field: str) -> str:
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), f"-o{field}="],
            capture_output=True, text=True, timeout=2,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _linux_find_port_holder(port: str) -> dict | None:
    if shutil.which("lsof"):
        try:
            result = subprocess.run(
                ["lsof", "-F", "pcu", "--", port],
                capture_output=True, text=True, timeout=3,
            )
            pid = None
            command = ""
            user = ""
            for line in result.stdout.splitlines():
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
            result = subprocess.run(
                ["fuser", port],
                capture_output=True, text=True, timeout=3,
            )
            digits = re.findall(r"\d+", result.stdout or "")
            if digits:
                pid = int(digits[0])
                return {
                    "pid": pid,
                    "command": _linux_ps_value(pid, "comm"),
                    "user": _linux_ps_value(pid, "user"),
                }
        except Exception:
            pass
    return None


def inspect_serial_port_lock(port: str, error_text: str = "") -> dict:
    info = {
        "busy": False,
        "port": port,
        "pid": None,
        "command": "",
        "user": "",
        "releasable": False,
        "detail": "",
    }

    if sys.platform.startswith("linux"):
        holder = _linux_find_port_holder(port)
        if holder:
            command = holder.get("command", "") or "未知进程"
            pid = holder.get("pid")
            lower = command.lower()
            info.update(holder)
            info["busy"] = True
            info["releasable"] = any(tool in lower for tool in KNOWN_SERIAL_HOLDER_TOOLS)
            info["detail"] = f"检测到 {command} (PID {pid}) 正在占用 {port}。"
            if info["releasable"]:
                info["detail"] += " 可在客户端内尝试释放该占用。"
            else:
                info["detail"] += " 请先关闭占用该串口的程序后再重试。"
            return info

    if _looks_like_port_busy(error_text):
        info["busy"] = True
        if sys.platform == "win32":
            info["detail"] = (
                f"{port} 当前可能被其他串口工具占用。"
                "请先关闭 PuTTY、MobaXterm、串口调试助手等程序后重试。"
            )
        else:
            info["detail"] = f"{port} 当前可能被其他程序占用。请先关闭外部串口终端后重试。"
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
        return True, "当前未检测到串口占用。"
    if not sys.platform.startswith("linux"):
        return False, "当前平台暂不支持自动释放串口，请先关闭外部串口工具。"
    if not lock_info.get("releasable"):
        return False, "当前占用进程不属于受支持的串口终端，请手动关闭后再重试。"

    pid = lock_info.get("pid")
    command = lock_info.get("command", "外部串口工具")
    if not pid:
        return False, "未能识别占用进程 PID，请手动关闭对应程序。"

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True, f"{command} 已退出，串口占用已释放。"
    except Exception as exc:
        return False, f"释放失败：{exc}"

    deadline = time.time() + 1.5
    while time.time() < deadline:
        if not _pid_exists(pid):
            return True, f"已结束 {command} (PID {pid})，可重新尝试连接串口。"
        time.sleep(0.1)
    return False, f"未能自动结束 {command} (PID {pid})，请手动关闭后再重试。"


# ── 外部终端启动（Linux/Windows/macOS）────────────────────────────────────────

def _external_serial_commands(port: str) -> list[str]:
    if sys.platform == "win32":
        cmds = []
        if shutil.which("putty"):
            cmds.append(f"putty -serial {port} -sercfg 115200,8,n,1,N")
        if shutil.which("tio"):
            cmds.append(f"tio {port} -b 115200")
        return cmds
    # Linux / macOS
    quoted = shlex.quote(port)
    cmds: list[str] = []
    for tool, cmd in [
        ("screen",   f"screen {quoted} 115200"),
        ("picocom",  f"picocom -b 115200 {quoted}"),
        ("tio",      f"tio {quoted} -b 115200"),
        ("minicom",  f"minicom -D {quoted} -b 115200"),
    ]:
        if shutil.which(tool):
            cmds.append(cmd)
    return cmds


def launch_serial_terminal(port: str) -> tuple[bool, str]:
    commands = _external_serial_commands(port)
    if not commands:
        return False, "未找到可用的外部串口终端工具（screen / picocom / tio / minicom / putty）。"

    if sys.platform == "win32":
        try:
            subprocess.Popen(commands[0], shell=True)
            return True, commands[0]
        except Exception as e:
            return False, str(e)

    terminal_cmds = [
        ["x-terminal-emulator", "-e", "bash", "-lc", commands[0]],
        ["gnome-terminal", "--", "bash", "-lc", commands[0]],
        ["konsole", "-e", "bash", "-lc", commands[0]],
        ["xterm", "-e", "bash", "-lc", commands[0]],
    ]
    for argv in terminal_cmds:
        if not shutil.which(argv[0]):
            continue
        try:
            subprocess.Popen(argv)
            return True, commands[0]
        except Exception:
            continue
    return False, commands[0]

# ── 串口探测线程 ──────────────────────────────────────────────────────────────

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
            self._ser = serial.Serial(
                self._port,
                baudrate=self._baudrate,
                timeout=0.1,
                write_timeout=0.5,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
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
                        continue

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


# ── 串口命令执行线程（pyserial，跨平台）──────────────────────────────────────

class _SerialCmdThread(QThread):
    """通过串口登录 Jetson 并执行一条命令，返回输出。跨平台（pyserial）。"""
    output = pyqtSignal(str)
    done   = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, port: str, username: str, password: str, command: str):
        super().__init__()
        self._port     = port
        self._username = username
        self._password = password
        self._command  = command
        self._stop     = False
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
            self._ser = serial.Serial(
                self._port, baudrate=115200, timeout=0.1,
                bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            # 唤醒：多发几次回车
            for _ in range(3):
                self._write(b"\r\n")
                time.sleep(0.3)
            buf = self._read_until([r"login:", r"[$#]\s*"], 8.0)

            if re.search(r"login:", buf):
                time.sleep(0.2)
                self._write((self._username + "\r\n").encode())
                buf = self._read_until([r"[Pp]assword:", r"[$#]\s*"], 8.0)

            if re.search(r"[Pp]assword:", buf):
                time.sleep(0.2)
                self._write((self._password + "\r\n").encode())
                buf = self._read_until(
                    [r"[$#]\s*", r"[Ll]ogin incorrect", r"[Aa]uthentication failure"], 10.0)

            if not re.search(r"[$#]\s*", buf):
                if re.search(r"[Ll]ogin incorrect|[Aa]uthentication failure", buf):
                    self.failed.emit("用户名或密码错误（Login incorrect）。")
                else:
                    self.failed.emit("登录失败，未检测到 shell 提示符。")
                return

            time.sleep(0.2)
            self._write((self._command + "\r\n").encode())
            result = self._read_until([r"[$#]\s*"], 20.0)
            self.done.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self._ser and self._ser.is_open:
                self._ser.close()

    def stop(self):
        self._stop = True

# ── Jetson 初始化对话框 ───────────────────────────────────────────────────────

class JetsonInitDialog(QDialog):
    def __init__(self, parent=None, preferred_port: str = "", auto_open_terminal: bool = False):
        super().__init__(parent)
        self._probe_thread: _ProbeThread | None = None
        self._serial_thread: _EmbeddedSerialThread | None = None
        self._lock_info: dict | None = None
        self._auto_open_terminal_pending = auto_open_terminal
        self.setWindowTitle("Jetson 初始化")
        self.setMinimumSize(980, 680)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        root.addWidget(make_label("Jetson 初始化", 16, C_TEXT, bold=True))
        root.addWidget(make_label(
            "烧录完成后，通过串口终端进入首次启动配置。选择串口后点击'连接串口终端'即可开始。",
            11, C_TEXT2, wrap=True,
        ))

        content_row = QHBoxLayout()
        content_row.setSpacing(16)

        left_col = QWidget()
        left_col.setStyleSheet("background:transparent;")
        left_lay = QVBoxLayout(left_col)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(16)

        right_col = QWidget()
        right_col.setStyleSheet("background:transparent;")
        right_lay = QVBoxLayout(right_col)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(16)

        top_card = make_card(12)
        apply_shadow(top_card, blur=18, y=4, alpha=60)
        top_lay = QVBoxLayout(top_card)
        top_lay.setContentsMargins(18, 16, 18, 16)
        top_lay.setSpacing(12)

        port_label_row = QHBoxLayout()
        port_label_row.setSpacing(10)
        port_label_row.addWidget(make_label("串口设备", 12, C_TEXT2))
        port_label_row.addStretch()
        top_lay.addLayout(port_label_row)

        port_row = QHBoxLayout()
        port_row.setSpacing(10)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(260)
        self.port_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        port_row.addWidget(self.port_combo, 1)
        top_lay.addLayout(port_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.refresh_btn  = make_button("刷新串口", small=True)
        self.detect_btn   = make_button("检测初始化状态", small=True)
        self.open_btn     = make_button("连接串口终端", primary=True, small=True)
        action_row.addWidget(self.refresh_btn)
        action_row.addWidget(self.detect_btn)
        action_row.addWidget(self.open_btn)
        action_row.addStretch()
        top_lay.addLayout(action_row)

        self.cmd_preview = make_label("", 10, C_TEXT3, wrap=True)
        top_lay.addWidget(self.cmd_preview)

        self.status_badge = QLabel("待检测")
        self.status_badge.setStyleSheet(f"""
            background:{C_CARD_LIGHT}; color:{C_TEXT3};
            border-radius:8px; padding:6px 12px;
            font-size:{pt(11)}pt; font-weight:700;
        """)
        top_lay.addWidget(self.status_badge, alignment=Qt.AlignLeft)
        self.status_text = make_label(
            "选择串口后点击'检测初始化状态'，或直接打开串口终端。", 11, C_TEXT2, wrap=True)
        top_lay.addWidget(self.status_text)

        lock_row = QHBoxLayout()
        lock_row.setSpacing(10)
        self.lock_hint = make_label("", 10, C_ORANGE, wrap=True)
        self.lock_hint.hide()
        self.release_lock_btn = make_button("释放串口占用", small=True)
        self.release_lock_btn.hide()
        self.release_lock_btn.clicked.connect(self._release_port_lock)
        lock_row.addWidget(self.lock_hint, 1)
        lock_row.addWidget(self.release_lock_btn)
        top_lay.addLayout(lock_row)
        left_lay.addWidget(top_card)

        # ── 内嵌串口终端 ──
        terminal_card = make_card(12)
        terminal_lay = QVBoxLayout(terminal_card)
        terminal_lay.setContentsMargins(18, 16, 18, 16)
        terminal_lay.setSpacing(10)

        terminal_title_row = QHBoxLayout()
        terminal_title_row.addWidget(make_label("内嵌串口终端", 12, C_TEXT, bold=True))
        terminal_title_row.addStretch()
        self.terminal_status = make_label("未连接", 10, C_TEXT3)
        terminal_title_row.addWidget(self.terminal_status)
        terminal_lay.addLayout(terminal_title_row)

        self.terminal_view = NativeTerminalWidget()
        self.terminal_view.setMinimumHeight(260)
        self.terminal_view.setStyleSheet(f"""
            QPlainTextEdit {{
                background:{C_CARD_LIGHT}; border:none; border-radius:10px;
                color:{C_TEXT}; padding:12px;
                font-size:{pt(10)}pt; font-family:'Consolas','JetBrains Mono',monospace;
            }}
            QScrollBar:vertical {{
                background:transparent; width:10px; margin:6px 2px 6px 0;
            }}
            QScrollBar::handle:vertical {{
                background:#4b5563; border-radius:5px; min-height:24px;
            }}
            QScrollBar::handle:vertical:hover {{ background:#64748b; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height:0px; background:transparent;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background:transparent;
            }}
            QScrollBar:horizontal {{
                background:transparent; height:10px; margin:0 6px 2px 6px;
            }}
            QScrollBar::handle:horizontal {{
                background:#4b5563; border-radius:5px; min-width:24px;
            }}
            QScrollBar::handle:horizontal:hover {{ background:#64748b; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width:0px; background:transparent;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background:transparent;
            }}
        """)
        terminal_lay.addWidget(self.terminal_view, 1)

        terminal_btn_row = QHBoxLayout()
        terminal_btn_row.setSpacing(10)
        self.disconnect_btn = make_button("断开", small=True)
        self.disconnect_btn.setEnabled(False)
        self.clear_terminal_btn = make_button("清屏", small=True)
        self.send_enter_btn = make_button("发送回车", small=True)
        terminal_btn_row.addWidget(self.disconnect_btn)
        terminal_btn_row.addWidget(self.clear_terminal_btn)
        terminal_btn_row.addWidget(self.send_enter_btn)
        terminal_btn_row.addStretch()
        terminal_lay.addLayout(terminal_btn_row)

        right_lay.addWidget(terminal_card, 1)

        guide_card = make_card(12)
        guide_lay = QVBoxLayout(guide_card)
        guide_lay.setContentsMargins(18, 14, 18, 14)
        guide_lay.setSpacing(6)
        guide_lay.addWidget(make_label("使用说明", 12, C_TEXT, bold=True))
        for idx, text in enumerate([
            "确认 Jetson 已上电，并通过 USB 线连接到主机。",
            "选择串口设备，点击'连接串口终端'，在右侧终端中完成初始化配置。",
            "按照向导完成 License 确认、用户名、密码、时区、网络等设置。",
            "看到 login: 提示后说明初始化完成，可关闭此窗口。",
        ], 1):
            guide_lay.addWidget(make_label(f"{idx}. {text}", 11, C_TEXT2, wrap=True))
        left_lay.addWidget(guide_card)
        left_lay.addStretch()

        content_row.addWidget(left_col, 4)
        content_row.addWidget(right_col, 6)
        root.addLayout(content_row, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = make_button("关闭")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.detect_btn.clicked.connect(self.detect_status)
        self.open_btn.clicked.connect(self.open_terminal)
        self.disconnect_btn.clicked.connect(self.close_terminal)
        self.clear_terminal_btn.clicked.connect(self._clear_terminal_surface)
        self.send_enter_btn.clicked.connect(lambda: self._send_terminal_bytes(b"\r"))
        self.terminal_view.input_bytes.connect(self._send_terminal_bytes)
        self.port_combo.currentTextChanged.connect(self._on_port_changed)
        self.refresh_ports(preferred_port)
        if self._auto_open_terminal_pending and self._current_port():
            QTimer.singleShot(0, self._open_terminal_from_entry)

    def refresh_ports(self, preferred_port: str = ""):
        ports = list_serial_ports()
        current = self.port_combo.currentText()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItems(ports or [""])
        self.port_combo.blockSignals(False)
        target = preferred_port or current
        if target and target in ports:
            self.port_combo.setCurrentText(target)
        elif ports:
            self.port_combo.setCurrentIndex(0)
        self._update_ui(self.port_combo.currentText())
        if not ports:
            self._set_state("warn", "未发现串口设备", "当前未检测到串口设备。")

    def _current_port(self) -> str:
        return self.port_combo.currentText().strip()

    def _update_ui(self, port: str):
        commands = _external_serial_commands(port) if port else []
        if port and commands:
            self.cmd_preview.setText(f"外部终端备选：{commands[0]}")
        elif port:
            self.cmd_preview.setText("未检测到可用的外部终端工具（可使用内嵌终端）。")
        else:
            self.cmd_preview.setText("等待检测到可用串口设备")
        has_port = bool(port)
        self.open_btn.setEnabled(has_port and self._serial_thread is None)
        self.disconnect_btn.setEnabled(self._serial_thread is not None)
        self.detect_btn.setEnabled(has_port)

    def _on_port_changed(self, port: str):
        self._update_ui(port)

    def _open_terminal_from_entry(self):
        if self._serial_thread is None and self._current_port():
            self.open_terminal()
        self._auto_open_terminal_pending = False

    def _set_state(self, level: str, badge: str, detail: str):
        color = {"ok": C_GREEN, "warn": C_ORANGE, "error": C_RED}.get(level, C_TEXT2)
        self.status_badge.setText(badge)
        self.status_badge.setStyleSheet(f"""
            background:{C_CARD_LIGHT}; color:{color};
            border-radius:8px; padding:6px 12px;
            font-size:{pt(11)}pt; font-weight:700;
        """)
        self.status_text.setText(detail)

    def _set_lock_info(self, info: dict | None):
        self._lock_info = info if info and info.get("busy") else None
        if self._lock_info:
            self.lock_hint.setText(self._lock_info.get("detail", ""))
            self.lock_hint.show()
            self.release_lock_btn.setVisible(bool(self._lock_info.get("releasable")))
        else:
            self.lock_hint.hide()
            self.lock_hint.setText("")
            self.release_lock_btn.hide()

    def _release_port_lock(self):
        if not self._lock_info:
            return
        reply = ask_question_message(
            self,
            "释放串口占用",
            self._lock_info.get("detail", "") + "\n\n是否尝试释放该串口占用？",
            buttons=QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        ok, msg = release_serial_port_lock(self._lock_info)
        if ok:
            show_info_message(self, "释放成功", msg)
            self._set_lock_info(None)
            self.refresh_ports(self._current_port())
        else:
            show_warning_message(self, "释放失败", msg)

    def detect_status(self):
        port = self._current_port()
        if not port:
            show_warning_message(self, "提示", "请先选择串口。")
            return
        self._set_lock_info(None)
        self.detect_btn.setEnabled(False)
        self.detect_btn.setText("检测中…")
        self._set_state("info", "检测中", f"正在读取 {port} 的串口输出…")
        self._probe_thread = _ProbeThread(port)
        self._probe_thread.finished_probe.connect(self._on_probe_result)
        self._probe_thread.start()

    def _on_probe_result(self, result: dict):
        self.detect_btn.setEnabled(True)
        self.detect_btn.setText("检测初始化状态")
        state = result.get("state", "unknown")
        if state == "not_initialized":
            self._set_state("warn", "未初始化", result.get("detail", ""))
            self._set_lock_info(None)
        elif state == "initialized":
            self._set_state("ok", "已初始化", result.get("detail", ""))
            self._set_lock_info(None)
        elif state == "error":
            self._set_state("error", "检测失败", result.get("detail", ""))
            self._set_lock_info(inspect_serial_port_lock(self._current_port(), result.get("detail", "")))
        else:
            self._set_state("info", "状态未知", result.get("detail", ""))
            self._set_lock_info(None)

    def _focus_terminal_surface(self):
        if self.terminal_view is not None:
            self.terminal_view.focus_terminal()

    def _clear_terminal_surface(self):
        if self.terminal_view is not None:
            self.terminal_view.clear_terminal()

    def _append_terminal_surface(self, text: str):
        if self.terminal_view is None or not text:
            return
        self.terminal_view.feed(text)

    def open_terminal(self):
        port = self._current_port()
        if not port:
            show_warning_message(self, "提示", "请先选择串口。")
            return
        if self._serial_thread is not None:
            self._focus_terminal_surface()
            return

        self._set_lock_info(None)
        self._append_terminal_surface(f"\n[connecting] {port} @ 115200\n")

        thread = _EmbeddedSerialThread(port)
        thread.opened.connect(self._on_terminal_opened)
        thread.output.connect(self._append_terminal_output)
        thread.error.connect(self._on_terminal_error)
        thread.closed.connect(self._on_terminal_closed)
        self._serial_thread = thread
        self.terminal_status.setText("连接中")
        self.terminal_status.setStyleSheet(
            f"color:{C_ORANGE}; font-size:{pt(10)}pt; background:transparent; font-weight:700;"
        )
        self._update_ui(port)
        thread.start()

    def close_terminal(self):
        if self._serial_thread:
            self._serial_thread.stop()

    def _send_terminal_bytes(self, payload: bytes):
        if self._serial_thread:
            self._serial_thread.send(payload)
            self._focus_terminal_surface()

    def _on_terminal_opened(self):
        self.terminal_status.setText("已连接")
        self.terminal_status.setStyleSheet(
            f"color:{C_GREEN}; font-size:{pt(10)}pt; background:transparent; font-weight:700;"
        )
        self._update_ui(self._current_port())
        self._focus_terminal_surface()
        self._send_terminal_bytes(b"\r")
        # 延迟设置 TERM，确保 shell 已就绪
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(1000, lambda: self._send_terminal_bytes(b"export TERM=xterm-256color\r\n"))

    def _append_terminal_output(self, text: str):
        self._append_terminal_surface(text)

    def _on_terminal_error(self, err: str):
        self._append_terminal_surface(f"\n[error] {err}\n")
        self._set_lock_info(inspect_serial_port_lock(self._current_port(), err))
        self.terminal_status.setText("连接失败")
        self.terminal_status.setStyleSheet(
            f"color:{C_RED}; font-size:{pt(10)}pt; background:transparent; font-weight:700;"
        )

    def _on_terminal_closed(self):
        self._serial_thread = None
        if self.terminal_status.text() != "连接失败":
            self.terminal_status.setText("未连接")
            self.terminal_status.setStyleSheet(
                f"color:{C_TEXT3}; font-size:{pt(10)}pt; background:transparent;"
            )
        self._update_ui(self._current_port())

    def closeEvent(self, event):
        self.close_terminal()
        if self._serial_thread and not self._serial_thread.wait(1200):
            self._serial_thread.terminate()
            self._serial_thread.wait(500)
        super().closeEvent(event)


def open_jetson_init_dialog(parent=None, preferred_port: str = "", auto_open_terminal: bool = False):
    dlg = JetsonInitDialog(
        parent=parent,
        preferred_port=preferred_port,
        auto_open_terminal=auto_open_terminal,
    )
    dlg.exec_()


# ── Jetson 网络配置对话框 ─────────────────────────────────────────────────────

def _parse_interfaces(ip_link_output: str) -> list[str]:
    clean = _strip_ansi(ip_link_output)
    ifaces = re.findall(r"^\d+:\s+([\w@]+):", clean, re.MULTILINE)
    result = []
    for iface in ifaces:
        name = iface.split("@")[0]
        if name in ("lo",) or name.startswith(("docker", "virbr", "br-", "veth", "dummy")):
            continue
        result.append(name)
    return result


class JetsonNetConfigDialog(QDialog):
    """通过串口登录 Jetson，配置指定网口的静态 IP。"""

    def __init__(self, parent=None, preferred_port: str = ""):
        super().__init__(parent)
        self._cmd_thread: _SerialCmdThread | None = None
        self._lock_info: dict | None = None
        self.setWindowTitle("Jetson 网络配置（串口）")
        self.setMinimumSize(680, 620)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        root.addWidget(make_label("Jetson 网络配置", 16, C_TEXT, bold=True))
        root.addWidget(make_label(
            "通过串口登录 Jetson，自动列出网口，填写 IP 后一键配置静态地址。",
            11, C_TEXT2, wrap=True,
        ))

        # 串口 & 登录
        login_card = make_card(12)
        apply_shadow(login_card, blur=18, y=4, alpha=60)
        ll = QVBoxLayout(login_card)
        ll.setContentsMargins(18, 16, 18, 16)
        ll.setSpacing(10)
        ll.addWidget(make_label("串口登录", 13, C_TEXT, bold=True))

        port_row = QHBoxLayout()
        port_row.setSpacing(8)
        port_row.addWidget(make_label("串口", 11, C_TEXT2))
        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(180)
        port_row.addWidget(self._port_combo)
        self._refresh_btn = make_button("刷新", small=True)
        port_row.addWidget(self._refresh_btn)
        port_row.addStretch()
        ll.addLayout(port_row)

        cred_row = QHBoxLayout()
        cred_row.setSpacing(8)
        cred_row.addWidget(make_label("用户名", 11, C_TEXT2))
        self._user_edit = QLineEdit("seeed")
        self._user_edit.setFixedWidth(120)
        self._user_edit.setStyleSheet(self._input_style())
        cred_row.addWidget(self._user_edit)
        cred_row.addSpacing(12)
        cred_row.addWidget(make_label("密码", 11, C_TEXT2))
        self._pass_edit = QLineEdit()
        self._pass_edit.setEchoMode(QLineEdit.Password)
        self._pass_edit.setPlaceholderText("登录密码（同时用于 sudo）")
        self._pass_edit.setFixedWidth(160)
        self._pass_edit.setStyleSheet(self._input_style())
        cred_row.addWidget(self._pass_edit)
        cred_row.addStretch()
        ll.addLayout(cred_row)

        scan_row = QHBoxLayout()
        self._scan_btn = make_button("登录并获取网口列表", primary=True, small=True)
        self._login_status = make_label("", 11, C_TEXT3)
        scan_row.addWidget(self._scan_btn)
        scan_row.addSpacing(12)
        scan_row.addWidget(self._login_status)
        scan_row.addStretch()
        ll.addLayout(scan_row)

        lock_row = QHBoxLayout()
        lock_row.setSpacing(10)
        self._lock_hint = make_label("", 10, C_ORANGE, wrap=True)
        self._lock_hint.hide()
        self._release_btn = make_button("释放串口占用", small=True)
        self._release_btn.hide()
        self._release_btn.clicked.connect(self._release_port_lock)
        lock_row.addWidget(self._lock_hint, 1)
        lock_row.addWidget(self._release_btn)
        ll.addLayout(lock_row)
        root.addWidget(login_card)

        # 网口 & IP 配置
        net_card = make_card(12)
        nl = QVBoxLayout(net_card)
        nl.setContentsMargins(18, 16, 18, 16)
        nl.setSpacing(10)
        nl.addWidget(make_label("网口 IP 配置", 13, C_TEXT, bold=True))

        iface_row = QHBoxLayout()
        iface_row.setSpacing(8)
        iface_row.addWidget(make_label("网口", 11, C_TEXT2))
        self._iface_combo = QComboBox()
        self._iface_combo.setMinimumWidth(160)
        self._iface_combo.setEnabled(False)
        iface_row.addWidget(self._iface_combo)
        iface_row.addStretch()
        nl.addLayout(iface_row)

        ip_row = QHBoxLayout()
        ip_row.setSpacing(8)
        ip_row.addWidget(make_label("IP 地址", 11, C_TEXT2))
        self._ip_edit = QLineEdit()
        self._ip_edit.setPlaceholderText("192.168.1.100")
        self._ip_edit.setFixedWidth(160)
        self._ip_edit.setStyleSheet(self._input_style())
        ip_row.addWidget(self._ip_edit)
        ip_row.addSpacing(12)
        ip_row.addWidget(make_label("子网掩码", 11, C_TEXT2))
        self._mask_edit = QLineEdit("24")
        self._mask_edit.setPlaceholderText("24 或 255.255.255.0")
        self._mask_edit.setFixedWidth(140)
        self._mask_edit.setStyleSheet(self._input_style())
        self._mask_edit.setToolTip("支持 CIDR（如 24）或点分格式（如 255.255.255.0）")
        ip_row.addWidget(self._mask_edit)
        ip_row.addSpacing(12)
        ip_row.addWidget(make_label("网关", 11, C_TEXT2))
        self._gw_edit = QLineEdit()
        self._gw_edit.setPlaceholderText("192.168.1.1（可选）")
        self._gw_edit.setFixedWidth(160)
        self._gw_edit.setStyleSheet(self._input_style())
        ip_row.addWidget(self._gw_edit)
        ip_row.addStretch()
        nl.addLayout(ip_row)

        apply_row = QHBoxLayout()
        self._apply_btn = make_button("应用配置", primary=True, small=True)
        self._apply_btn.setEnabled(False)
        self._apply_status = make_label("", 11, C_TEXT3)
        apply_row.addWidget(self._apply_btn)
        apply_row.addSpacing(12)
        apply_row.addWidget(self._apply_status)
        apply_row.addStretch()
        nl.addLayout(apply_row)
        root.addWidget(net_card)

        # 日志
        log_card = make_card(12)
        log_lay = QVBoxLayout(log_card)
        log_lay.setContentsMargins(18, 14, 18, 14)
        log_lay.setSpacing(8)
        log_lay.addWidget(make_label("串口日志", 12, C_TEXT, bold=True))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(160)
        self._log.setLineWrapMode(QTextEdit.WidgetWidth)
        self._log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._log.setStyleSheet(f"""
            QTextEdit {{
                background:{C_CARD_LIGHT}; border:none; border-radius:8px;
                color:{C_TEXT2}; padding:10px;
                font-size:{pt(10)}pt; font-family:'JetBrains Mono','Consolas',monospace;
            }}
        """)
        log_lay.addWidget(self._log)
        root.addWidget(log_card, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = make_button("关闭")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        self._refresh_btn.clicked.connect(self._refresh_ports)
        self._scan_btn.clicked.connect(self._do_scan)
        self._apply_btn.clicked.connect(self._do_apply)
        self._refresh_ports(preferred_port)

    def _input_style(self) -> str:
        return (f"QLineEdit {{ background:{C_CARD_LIGHT}; border:none; border-radius:8px;"
                f" padding:6px 10px; color:{C_TEXT}; font-size:{pt(11)}pt; }}"
                f" QLineEdit:focus {{ background:#2a3040; }}")

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
            self._lock_hint.setText("")
            self._release_btn.hide()

    def _release_port_lock(self):
        if not self._lock_info:
            return
        reply = ask_question_message(
            self,
            "释放串口占用",
            self._lock_info.get("detail", "") + "\n\n是否尝试释放该串口占用？",
            buttons=QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        ok, msg = release_serial_port_lock(self._lock_info)
        if ok:
            show_info_message(self, "释放成功", msg)
            self._set_lock_info(None)
            self._refresh_ports(self._port_combo.currentText().strip())
        else:
            show_warning_message(self, "释放失败", msg)

    def _log_append(self, text: str):
        clean = _strip_ansi(text).replace("\r\n", "\n").replace("\r", "\n")
        if clean.strip():
            self._log.append(clean.rstrip())
            self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _do_scan(self):
        port = self._port_combo.currentText().strip()
        if not port:
            show_warning_message(self, "提示", "请先选择串口。")
            return
        self._set_lock_info(None)
        user = self._user_edit.text().strip() or "seeed"
        pwd  = self._pass_edit.text()
        self._scan_btn.setEnabled(False)
        self._scan_btn.setText("获取中…")
        self._login_status.setText("正在登录…")
        self._iface_combo.setEnabled(False)
        self._apply_btn.setEnabled(False)
        self._log.clear()
        self._cmd_thread = _SerialCmdThread(port, user, pwd, "ip link show")
        self._cmd_thread.output.connect(self._log_append)
        self._cmd_thread.done.connect(self._on_scan_done)
        self._cmd_thread.failed.connect(self._on_scan_failed)
        self._cmd_thread.start()

    def _on_scan_done(self, output: str):
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("登录并获取网口列表")
        self._set_lock_info(None)
        ifaces = _parse_interfaces(output)
        if not ifaces:
            self._login_status.setText("未找到可用网口")
            self._login_status.setStyleSheet(
                f"color:{C_ORANGE}; font-size:{pt(11)}pt; background:transparent;")
            return
        self._iface_combo.clear()
        self._iface_combo.addItems(ifaces)
        self._iface_combo.setEnabled(True)
        self._apply_btn.setEnabled(True)
        self._login_status.setText(f"登录成功，找到 {len(ifaces)} 个网口")
        self._login_status.setStyleSheet(
            f"color:{C_GREEN}; font-size:{pt(11)}pt; background:transparent; font-weight:700;")

    def _on_scan_failed(self, err: str):
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("登录并获取网口列表")
        self._login_status.setText(f"失败：{err}")
        self._login_status.setStyleSheet(
            f"color:{C_RED}; font-size:{pt(11)}pt; background:transparent;")
        self._set_lock_info(inspect_serial_port_lock(self._port_combo.currentText().strip(), err))

    def _do_apply(self):
        port  = self._port_combo.currentText().strip()
        user  = self._user_edit.text().strip() or "seeed"
        pwd   = self._pass_edit.text()
        iface = self._iface_combo.currentText().strip()
        ip    = self._ip_edit.text().strip()
        mask  = self._mask_edit.text().strip() or "24"
        if "." in mask:
            try:
                mask = str(sum(bin(int(x)).count("1") for x in mask.split(".")))
            except Exception:
                pass
        gw = self._gw_edit.text().strip()

        if not ip:
            show_warning_message(self, "提示", "请填写 IP 地址。")
            return
        if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
            show_warning_message(self, "提示", "IP 地址格式不正确。")
            return
        self._set_lock_info(None)

        con_name    = f"static-{iface}"
        ip_cidr     = f"{ip}/{mask}"
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
        self._apply_btn.setText("配置中…")
        self._apply_status.setText("")
        self._log.append(f"\n[配置] {iface} -> {ip_cidr}" + (f" gw {gw}" if gw else "") + "\n")

        self._cmd_thread = _SerialCmdThread(port, user, pwd, command)
        self._cmd_thread.output.connect(self._log_append)
        self._cmd_thread.done.connect(self._on_apply_done)
        self._cmd_thread.failed.connect(self._on_apply_failed)
        self._cmd_thread.start()

    def _on_apply_done(self, output: str):
        self._apply_btn.setEnabled(True)
        self._apply_btn.setText("应用配置")
        self._set_lock_info(None)
        ip = self._ip_edit.text().strip()
        if "Error" in output or "error" in output:
            self._apply_status.setText("配置可能失败，请查看日志")
            self._apply_status.setStyleSheet(
                f"color:{C_ORANGE}; font-size:{pt(11)}pt; background:transparent;")
        else:
            self._apply_status.setText(f"配置完成，设备 IP：{ip}")
            self._apply_status.setStyleSheet(
                f"color:{C_GREEN}; font-size:{pt(11)}pt; background:transparent; font-weight:700;")

    def _on_apply_failed(self, err: str):
        self._apply_btn.setEnabled(True)
        self._apply_btn.setText("应用配置")
        self._apply_status.setText(f"失败：{err}")
        self._apply_status.setStyleSheet(
            f"color:{C_RED}; font-size:{pt(11)}pt; background:transparent;")
        self._set_lock_info(inspect_serial_port_lock(self._port_combo.currentText().strip(), err))


def open_jetson_net_config_dialog(parent=None, preferred_port: str = ""):
    dlg = JetsonNetConfigDialog(parent=parent, preferred_port=preferred_port)
    dlg.exec_()
