"""Jetson 初始化对话框与串口检测辅助。"""
from __future__ import annotations

import glob
import os
import re
import select
import shlex
import shutil
import subprocess
import termios
import time
import tty
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

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
    make_button,
    make_card,
    make_label,
    pt,
)


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


def list_serial_ports() -> list[str]:
    return sorted(set(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")))


def _strip_ansi(text: str) -> str:
    text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"\x1B[@-_]", "", text)
    return text


def _configure_serial_fd(fd: int):
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = attrs[2] | termios.CLOCAL | termios.CREAD | termios.CS8
    attrs[3] = 0
    attrs[4] = termios.B115200
    attrs[5] = termios.B115200
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 1
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    tty.setraw(fd)
    termios.tcflush(fd, termios.TCIOFLUSH)


def _classify_serial_output(raw_text: str) -> dict:
    clean = _strip_ansi(raw_text).strip()
    compact = "\n".join(line.rstrip() for line in clean.splitlines() if line.strip())
    if not compact:
        return {
            "state": "unknown",
            "title": "未读取到明确串口输出",
            "detail": "请确认设备已上电，并按回车后重试。",
            "excerpt": "",
        }
    if any(keyword in compact for keyword in INIT_PENDING_KEYWORDS):
        return {
            "state": "not_initialized",
            "title": "检测到首次启动初始化向导",
            "detail": "这台 Jetson 还未完成系统初始化，需要通过串口继续配置用户名、密码和基础系统设置。",
            "excerpt": compact,
        }
    if any(re.search(pattern, compact, re.MULTILINE) for pattern in INIT_DONE_PATTERNS):
        return {
            "state": "initialized",
            "title": "检测到正常登录提示",
            "detail": "设备大概率已经完成初始化，可以直接通过串口登录或继续配置 SSH。",
            "excerpt": compact,
        }
    return {
        "state": "unknown",
        "title": "串口已连通，但未识别到明确状态",
        "detail": "可能处于启动中、停留在其他菜单，或输出较少。建议继续查看串口终端。",
        "excerpt": compact,
    }


def probe_serial_status(port: str, timeout: float = 4.0) -> dict:
    original = None
    fd = None
    try:
        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        original = termios.tcgetattr(fd)
        _configure_serial_fd(fd)
        os.write(fd, b"\r\n")
        deadline = time.time() + timeout
        chunks: list[bytes] = []
        while time.time() < deadline:
            readable, _, _ = select.select([fd], [], [], 0.25)
            if fd not in readable:
                continue
            try:
                data = os.read(fd, 4096)
            except BlockingIOError:
                data = b""
            if data:
                chunks.append(data)
        raw = b"".join(chunks).decode("utf-8", errors="ignore")
        return _classify_serial_output(raw)
    except Exception as exc:
        return {"state": "error", "title": "串口检测失败", "detail": str(exc), "excerpt": ""}
    finally:
        if fd is not None:
            if original is not None:
                try:
                    termios.tcsetattr(fd, termios.TCSANOW, original)
                except Exception:
                    pass
            os.close(fd)


def _external_serial_commands(port: str) -> list[str]:
    quoted = shlex.quote(port)
    cmds: list[str] = []
    if shutil.which("screen"):
        cmds.append(f"screen {quoted} 115200")
    if shutil.which("picocom"):
        cmds.append(f"picocom -b 115200 {quoted}")
    if shutil.which("tio"):
        cmds.append(f"tio {quoted} -b 115200")
    if shutil.which("minicom"):
        cmds.append(f"minicom -D {quoted} -b 115200")
    return cmds


def launch_serial_terminal(port: str) -> tuple[bool, str]:
    commands = _external_serial_commands(port)
    if not commands:
        return False, "未找到可用的外部串口终端工具（screen / picocom / tio / minicom）。"

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


class _ProbeThread(QThread):
    finished_probe = pyqtSignal(dict)

    def __init__(self, port: str):
        super().__init__()
        self._port = port

    def run(self):
        self.finished_probe.emit(probe_serial_status(self._port))


class JetsonInitDialog(QDialog):
    def __init__(self, parent=None, preferred_port: str = ""):
        super().__init__(parent)
        self._probe_thread: _ProbeThread | None = None

        self.setWindowTitle("Jetson 初始化")
        self.setMinimumSize(720, 560)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        root.addWidget(make_label("Jetson 初始化", 16, C_TEXT, bold=True))
        root.addWidget(make_label(
            "烧录完成后，通过串口终端进入首次启动配置。选择串口后点击'打开串口终端'即可开始。",
            11, C_TEXT2, wrap=True,
        ))

        # 串口选择卡片
        top_card = make_card(12)
        apply_shadow(top_card, blur=18, y=4, alpha=60)
        top_lay = QVBoxLayout(top_card)
        top_lay.setContentsMargins(18, 16, 18, 16)
        top_lay.setSpacing(12)

        port_row = QHBoxLayout()
        port_row.setSpacing(10)
        port_row.addWidget(make_label("串口设备", 12, C_TEXT2))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(220)
        port_row.addWidget(self.port_combo)
        self.refresh_btn = make_button("刷新串口", small=True)
        self.detect_btn = make_button("检测初始化状态", small=True)
        self.open_btn = make_button("打开串口终端", primary=True, small=True)
        port_row.addWidget(self.refresh_btn)
        port_row.addWidget(self.detect_btn)
        port_row.addWidget(self.open_btn)
        port_row.addStretch()
        top_lay.addLayout(port_row)

        self.cmd_preview = make_label("", 10, C_TEXT3, wrap=True)
        top_lay.addWidget(self.cmd_preview)

        self.status_badge = QLabel("待检测")
        self.status_badge.setStyleSheet(f"""
            background:{C_CARD_LIGHT}; color:{C_TEXT3};
            border-radius:8px; padding:6px 12px;
            font-size:{pt(11)}pt; font-weight:700;
        """)
        top_lay.addWidget(self.status_badge, alignment=Qt.AlignLeft)

        self.status_text = make_label("选择串口后点击'检测初始化状态'，或直接打开串口终端。", 11, C_TEXT2, wrap=True)
        top_lay.addWidget(self.status_text)
        root.addWidget(top_card)

        # 状态摘录
        excerpt_card = make_card(12)
        excerpt_lay = QVBoxLayout(excerpt_card)
        excerpt_lay.setContentsMargins(18, 16, 18, 16)
        excerpt_lay.setSpacing(10)
        excerpt_lay.addWidget(make_label("状态摘录", 12, C_TEXT, bold=True))
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setMinimumHeight(100)
        self.output_box.setLineWrapMode(QTextEdit.WidgetWidth)
        self.output_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.output_box.setStyleSheet(f"""
            QTextEdit {{
                background: {C_CARD_LIGHT}; border: none; border-radius: 10px;
                color: {C_TEXT2}; padding: 12px;
                font-size: {pt(10)}pt; font-family: 'JetBrains Mono', 'Consolas', monospace;
            }}
        """)
        self.output_box.setPlaceholderText("检测初始化状态后，这里会显示关键状态摘录。")
        excerpt_lay.addWidget(self.output_box)
        root.addWidget(excerpt_card, 1)

        # 使用说明
        guide_card = make_card(12)
        guide_lay = QVBoxLayout(guide_card)
        guide_lay.setContentsMargins(18, 14, 18, 14)
        guide_lay.setSpacing(6)
        guide_lay.addWidget(make_label("使用说明", 12, C_TEXT, bold=True))
        for idx, text in enumerate([
            "确认 Jetson 已上电，并通过 USB 线连接到主机。",
            "选择串口设备，点击'打开串口终端'，在弹出的终端窗口中完成初始化配置。",
            "按照向导完成 License 确认、用户名、密码、时区、网络等设置。",
            "看到 login: 提示后说明初始化完成，可关闭此窗口。",
        ], 1):
            guide_lay.addWidget(make_label(f"{idx}. {text}", 11, C_TEXT2, wrap=True))
        root.addWidget(guide_card)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = make_button("关闭")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.detect_btn.clicked.connect(self.detect_status)
        self.open_btn.clicked.connect(self.open_terminal)
        self.port_combo.currentTextChanged.connect(self._on_port_changed)

        self.refresh_ports(preferred_port)

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
            self._set_state("warn", "未发现串口设备", "当前未检测到 /dev/ttyACM* 或 /dev/ttyUSB*。")

    def _current_port(self) -> str:
        return self.port_combo.currentText().strip()

    def _update_ui(self, port: str):
        commands = _external_serial_commands(port) if port else []
        if port and commands:
            self.cmd_preview.setText(f"将执行：{commands[0]}")
        elif port:
            self.cmd_preview.setText("未检测到可用的外部终端工具（screen / picocom / tio / minicom）。")
        else:
            self.cmd_preview.setText("等待检测到可用串口设备")
        has_port = bool(port)
        self.open_btn.setEnabled(has_port)
        self.detect_btn.setEnabled(has_port)

    def _on_port_changed(self, port: str):
        self._update_ui(port)

    def _set_state(self, level: str, badge: str, detail: str):
        color = {"ok": C_GREEN, "warn": C_ORANGE, "error": C_RED}.get(level, C_TEXT2)
        self.status_badge.setText(badge)
        self.status_badge.setStyleSheet(f"""
            background:{C_CARD_LIGHT}; color:{color};
            border-radius:8px; padding:6px 12px;
            font-size:{pt(11)}pt; font-weight:700;
        """)
        self.status_text.setText(detail)

    def detect_status(self):
        port = self._current_port()
        if not port:
            QMessageBox.warning(self, "提示", "请先选择串口。")
            return
        self.detect_btn.setEnabled(False)
        self.detect_btn.setText("检测中…")
        self._set_state("info", "检测中", f"正在读取 {port} 的串口输出…")
        self.output_box.clear()
        self._probe_thread = _ProbeThread(port)
        self._probe_thread.finished_probe.connect(self._on_probe_result)
        self._probe_thread.start()

    def _on_probe_result(self, result: dict):
        self.detect_btn.setEnabled(True)
        self.detect_btn.setText("检测初始化状态")
        state = result.get("state", "unknown")
        if state == "not_initialized":
            self._set_state("warn", "未初始化", result.get("detail", ""))
        elif state == "initialized":
            self._set_state("ok", "已初始化", result.get("detail", ""))
        elif state == "error":
            self._set_state("error", "检测失败", result.get("detail", ""))
        else:
            self._set_state("info", "状态未知", result.get("detail", ""))
        excerpt = result.get("excerpt", "").strip()
        self.output_box.setPlainText(excerpt or result.get("detail", ""))

    def open_terminal(self):
        port = self._current_port()
        if not port:
            QMessageBox.warning(self, "提示", "请先选择串口。")
            return
        ok, info = launch_serial_terminal(port)
        if ok:
            QMessageBox.information(
                self, "已打开串口终端",
                f"已在外部终端中打开：\n{info}\n\n请在终端窗口中完成 Jetson 初始化配置。",
            )
        else:
            QMessageBox.warning(
                self, "无法打开外部终端",
                f"{info}\n\n请手动在终端中执行上方显示的命令。",
            )


def open_jetson_init_dialog(parent=None, preferred_port: str = ""):
    dlg = JetsonInitDialog(parent=parent, preferred_port=preferred_port)
    dlg.exec_()


# ─────────────────────────────────────────────────────────────────────────────
# 串口网络配置对话框
# 流程：串口登录 Jetson → 列出网口 → 填写 IP → 发 nmcli 命令配置
# ─────────────────────────────────────────────────────────────────────────────

class _SerialLoginThread(QThread):
    """通过串口发送登录序列，返回登录后的 shell 提示符。"""
    output   = pyqtSignal(str)   # 实时输出
    success  = pyqtSignal()      # 登录成功（检测到 shell prompt）
    failed   = pyqtSignal(str)   # 登录失败原因

    _PROMPT_RE = re.compile(r"[$#]\s*$", re.MULTILINE)

    def __init__(self, port: str, username: str, password: str):
        super().__init__()
        self._port     = port
        self._username = username
        self._password = password
        self._fd: int | None = None
        self._stop = False

    def _write(self, data: bytes):
        if self._fd is not None:
            os.write(self._fd, data)

    def _read_until(self, patterns: list[str], timeout: float) -> str:
        """读取串口直到匹配任一 pattern 或超时，返回累积文本。"""
        buf = ""
        deadline = time.time() + timeout
        while time.time() < deadline and not self._stop:
            r, _, _ = select.select([self._fd], [], [], 0.2)
            if self._fd in r:
                try:
                    chunk = os.read(self._fd, 4096).decode("utf-8", errors="ignore")
                except BlockingIOError:
                    chunk = ""
                if chunk:
                    buf += chunk
                    self.output.emit(chunk)
            for p in patterns:
                if re.search(p, buf):
                    return buf
        return buf

    def run(self):
        try:
            self._fd = os.open(self._port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            orig = termios.tcgetattr(self._fd)
            _configure_serial_fd(self._fd)

            # 多次唤醒
            for _ in range(3):
                self._write(b"\r\n")
                time.sleep(0.3)
            buf = self._read_until([r"login:", r"[$#]\s*", r"[Pp]assword:"], 8.0)

            # 如果已经在 shell，直接成功
            if re.search(r"[$#]\s*", buf):
                self.success.emit()
                return

            # 发用户名
            if re.search(r"login:", buf):
                time.sleep(0.2)
                self._write((self._username + "\r\n").encode())
                buf = self._read_until([r"[Pp]assword:", r"[$#]\s*"], 8.0)

            # 发密码
            if re.search(r"[Pp]assword:", buf):
                time.sleep(0.2)
                self._write((self._password + "\r\n").encode())
                buf = self._read_until([r"[$#]\s*", r"[Ll]ogin incorrect", r"[Aa]uthentication failure"], 10.0)

            if re.search(r"[$#]\s*", buf):
                self.success.emit()
            else:
                self.failed.emit("登录失败：用户名或密码错误，或设备未就绪。")
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self._fd is not None:
                try:
                    termios.tcsetattr(self._fd, termios.TCSANOW, orig)
                except Exception:
                    pass
                os.close(self._fd)
                self._fd = None

    def stop(self):
        self._stop = True


class _SerialCmdThread(QThread):
    """登录后执行一条命令，返回输出。"""
    output   = pyqtSignal(str)
    done     = pyqtSignal(str)   # 命令完整输出
    failed   = pyqtSignal(str)

    def __init__(self, port: str, username: str, password: str, command: str):
        super().__init__()
        self._port     = port
        self._username = username
        self._password = password
        self._command  = command
        self._stop     = False

    def _write(self, data: bytes):
        if self._fd is not None:
            os.write(self._fd, data)

    def _read_until(self, patterns: list[str], timeout: float) -> str:
        buf = ""
        deadline = time.time() + timeout
        while time.time() < deadline and not self._stop:
            r, _, _ = select.select([self._fd], [], [], 0.2)
            if self._fd in r:
                try:
                    chunk = os.read(self._fd, 4096).decode("utf-8", errors="ignore")
                except BlockingIOError:
                    chunk = ""
                if chunk:
                    buf += chunk
                    self.output.emit(chunk)
            for p in patterns:
                if re.search(p, buf):
                    return buf
        return buf

    def run(self):
        self._fd = None
        try:
            self._fd = os.open(self._port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            orig = termios.tcgetattr(self._fd)
            _configure_serial_fd(self._fd)

            # 多发几次回车唤醒，等待 login: 提示
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
                buf = self._read_until([r"[$#]\s*", r"[Ll]ogin incorrect", r"[Aa]uthentication failure"], 10.0)

            if not re.search(r"[$#]\s*", buf):
                if re.search(r"[Ll]ogin incorrect|[Aa]uthentication failure", buf):
                    self.failed.emit("用户名或密码错误（Login incorrect）。")
                else:
                    self.failed.emit("登录失败，未检测到 shell 提示符。")
                return

            # 执行命令，等待提示符返回
            time.sleep(0.2)
            self._write((self._command + "\r\n").encode())
            result = self._read_until([r"[$#]\s*"], 20.0)
            self.done.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self._fd is not None:
                try:
                    termios.tcsetattr(self._fd, termios.TCSANOW, orig)
                except Exception:
                    pass
                os.close(self._fd)
                self._fd = None

    def stop(self):
        self._stop = True


def _parse_interfaces(ip_link_output: str) -> list[str]:
    """从 ip link show 输出中提取以太网口名称（排除 lo、docker、virbr 等）。"""
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

        # ── 串口 & 登录 ──
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
        self._user_edit = QLineEdit("ubuntu")
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
        root.addWidget(login_card)

        # ── 网口 & IP 配置 ──
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

        # ── 日志 ──
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
        return f"""
            QLineEdit {{
                background:{C_CARD_LIGHT}; border:none; border-radius:8px;
                padding:6px 10px; color:{C_TEXT}; font-size:{pt(11)}pt;
            }}
            QLineEdit:focus {{ background:#2a3040; }}
        """

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

    def _log_append(self, text: str):
        clean = _strip_ansi(text).replace("\r\n", "\n").replace("\r", "\n")
        if clean.strip():
            self._log.append(clean.rstrip())
            self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _do_scan(self):
        port = self._port_combo.currentText().strip()
        if not port:
            QMessageBox.warning(self, "提示", "请先选择串口。")
            return
        user = self._user_edit.text().strip() or "ubuntu"
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
        ifaces = _parse_interfaces(output)
        if not ifaces:
            self._login_status.setText("未找到可用网口")
            self._login_status.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(11)}pt; background:transparent;")
            return
        self._iface_combo.clear()
        self._iface_combo.addItems(ifaces)
        self._iface_combo.setEnabled(True)
        self._apply_btn.setEnabled(True)
        self._login_status.setText(f"登录成功，找到 {len(ifaces)} 个网口")
        self._login_status.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(11)}pt; background:transparent; font-weight:700;")

    def _on_scan_failed(self, err: str):
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("登录并获取网口列表")
        self._login_status.setText(f"失败：{err}")
        self._login_status.setStyleSheet(f"color:{C_RED}; font-size:{pt(11)}pt; background:transparent;")

    def _do_apply(self):
        port  = self._port_combo.currentText().strip()
        user  = self._user_edit.text().strip() or "ubuntu"
        pwd   = self._pass_edit.text()
        iface = self._iface_combo.currentText().strip()
        ip    = self._ip_edit.text().strip()
        mask  = self._mask_edit.text().strip() or "24"
        # 支持点分格式（255.255.255.0 → 24）
        if "." in mask:
            try:
                mask = str(sum(bin(int(x)).count("1") for x in mask.split(".")))
            except Exception:
                pass
        gw    = self._gw_edit.text().strip()

        if not ip:
            QMessageBox.warning(self, "提示", "请填写 IP 地址。")
            return
        if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
            QMessageBox.warning(self, "提示", "IP 地址格式不正确。")
            return

        # 构造 nmcli 命令，用 sudo -S 从 stdin 传密码，合并为一次 sudo 调用
        con_name = f"static-{iface}"
        ip_cidr  = f"{ip}/{mask}"
        pwd_escaped = self._pass_edit.text().replace("'", "'\\''")
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
        self._log.append(f"\n[配置] {iface} → {ip_cidr}" + (f" gw {gw}" if gw else "") + "\n")

        self._cmd_thread = _SerialCmdThread(port, user, pwd, command)
        self._cmd_thread.output.connect(self._log_append)
        self._cmd_thread.done.connect(self._on_apply_done)
        self._cmd_thread.failed.connect(self._on_apply_failed)
        self._cmd_thread.start()

    def _on_apply_done(self, output: str):
        self._apply_btn.setEnabled(True)
        self._apply_btn.setText("应用配置")
        ip = self._ip_edit.text().strip()
        if "Error" in output or "error" in output:
            self._apply_status.setText("配置可能失败，请查看日志")
            self._apply_status.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(11)}pt; background:transparent;")
        else:
            self._apply_status.setText(f"配置完成，设备 IP：{ip}")
            self._apply_status.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(11)}pt; background:transparent; font-weight:700;")

    def _on_apply_failed(self, err: str):
        self._apply_btn.setEnabled(True)
        self._apply_btn.setText("应用配置")
        self._apply_status.setText(f"失败：{err}")
        self._apply_status.setStyleSheet(f"color:{C_RED}; font-size:{pt(11)}pt; background:transparent;")


def open_jetson_net_config_dialog(parent=None, preferred_port: str = ""):
    dlg = JetsonNetConfigDialog(parent=parent, preferred_port=preferred_port)
    dlg.exec_()
