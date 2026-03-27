"""远程桌面对话框 — 一键部署 x11vnc + noVNC，访问 Jetson 图形桌面。"""
from __future__ import annotations

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from seeed_jetson_develop.core.runner import SSHRunner
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT, C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    apply_shadow, make_button, make_card, make_input_card, make_label, pt,
)
from seeed_jetson_develop.modules.remote import desktop_remote as dr


# ── 后台 SSH 命令线程 ─────────────────────────────────────────────────────────
class _SshCmdThread(QThread):
    line_out  = pyqtSignal(str)
    finished_ = pyqtSignal(int, str)  # rc, last_output

    def __init__(self, runner: SSHRunner, commands: list[tuple[str, int]]):
        super().__init__()
        self._runner = runner
        self._commands = commands
        self._last_out = ""

    def run(self):
        for cmd, timeout in self._commands:
            self.line_out.emit(f"$ {cmd}")
            rc, out = self._runner.run(
                cmd, timeout=timeout,
                on_output=lambda l: self.line_out.emit(l),
            )
            self._last_out = out
            if rc != 0:
                self.finished_.emit(rc, out)
                return
        self.finished_.emit(0, self._last_out)


# ── 状态检测线程 ──────────────────────────────────────────────────────────────
class _StatusThread(QThread):
    result = pyqtSignal(dict)

    def __init__(self, runner: SSHRunner):
        super().__init__()
        self._runner = runner

    def run(self):
        vnc_inst = dr.check_vnc_installed(self._runner)
        novnc_inst = dr.check_novnc_installed(self._runner)
        vnc_run, vnc_pid = dr.check_vnc_running(self._runner)
        novnc_run, novnc_pid = dr.check_novnc_running(self._runner)
        self.result.emit({
            "vnc_installed": vnc_inst,
            "vnc_running": vnc_run,
            "vnc_pid": vnc_pid,
            "novnc_installed": novnc_inst,
            "novnc_running": novnc_run,
            "novnc_pid": novnc_pid,
        })


def _status_pill(text: str = "检测中…", color: str = C_TEXT3) -> QLabel:
    """状态药丸标签。"""
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        f"background: rgba({_hex_to_rgba(color, 0.15)}); color: {color};"
        f" border-radius: {pt(4)}px; padding: {pt(3)}px {pt(10)}px;"
        f" font-size: {pt(11)}px; font-weight: 600;"
    )
    return lbl


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """#RRGGBB → 'R,G,B,alpha'"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b},{alpha}"


def _info_tile(icon: str, label: str, value: str, selectable: bool = False) -> QWidget:
    """小卡片：图标 + 标签 + 值。"""
    tile = make_input_card(8)
    lay = QVBoxLayout(tile)
    lay.setContentsMargins(pt(14), pt(12), pt(14), pt(12))
    lay.setSpacing(pt(4))
    top = QHBoxLayout()
    top.addWidget(make_label(icon, 14))
    top.addSpacing(pt(4))
    top.addWidget(make_label(label, 11, C_TEXT3))
    top.addStretch()
    lay.addLayout(top)
    val = make_label(value, 12, C_TEXT, bold=False)
    if selectable:
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        val.setCursor(Qt.IBeamCursor)
    val.setWordWrap(True)
    lay.addWidget(val)
    tile._val_label = val  # 存引用以便后续更新
    return tile


class DesktopRemoteDialog(QDialog):
    def __init__(self, runner: SSHRunner, ip: str, parent=None):
        super().__init__(parent)
        self._runner = runner
        self._ip = ip
        self._thread: _SshCmdThread | None = None
        self._status_thread: _StatusThread | None = None

        self.setWindowTitle("Remote Desktop")
        self.setMinimumSize(pt(780), pt(620))
        self.resize(pt(820), pt(680))
        self.setSizeGripEnabled(True)
        self.setStyleSheet(f"background:{C_CARD}; color:{C_TEXT}; border-radius:12px;")

        root = QVBoxLayout(self)
        root.setContentsMargins(pt(28), pt(24), pt(28), pt(20))
        root.setSpacing(pt(18))

        # ══════════════════════════════════════════
        #  标题区
        # ══════════════════════════════════════════
        hdr = QHBoxLayout()
        hdr.setSpacing(pt(12))
        hdr.addWidget(make_label("远程桌面", 18, C_TEXT, bold=True))
        hdr.addSpacing(pt(4))
        hdr.addWidget(make_label(
            f"Jetson @ {ip}", 12, C_TEXT3))
        hdr.addStretch()
        self._refresh_btn = make_button("刷新状态", small=True)
        hdr.addWidget(self._refresh_btn)
        root.addLayout(hdr)

        root.addWidget(make_label(
            "一键部署 VNC + noVNC 远程桌面服务。部署后可通过浏览器或 VNC 客户端访问 Jetson 图形桌面。",
            11, C_TEXT3, wrap=True,
        ))

        # ══════════════════════════════════════════
        #  服务状态 + 连接信息（2 列）
        # ══════════════════════════════════════════
        info_grid = QGridLayout()
        info_grid.setSpacing(pt(12))
        info_grid.setColumnStretch(0, 1)
        info_grid.setColumnStretch(1, 1)

        # 左列：服务状态卡
        status_card = make_card(10)
        apply_shadow(status_card, blur=16, y=3, alpha=50)
        sc = QVBoxLayout(status_card)
        sc.setContentsMargins(pt(18), pt(16), pt(18), pt(16))
        sc.setSpacing(pt(12))
        sc.addWidget(make_label("服务状态", 13, C_TEXT, bold=True))

        # x11vnc 行
        vnc_row = QHBoxLayout()
        vnc_row.addWidget(make_label("x11vnc", 12, C_TEXT2))
        vnc_row.addStretch()
        self._vnc_pill = _status_pill("检测中…")
        vnc_row.addWidget(self._vnc_pill)
        sc.addLayout(vnc_row)

        # noVNC 行
        novnc_row = QHBoxLayout()
        novnc_row.addWidget(make_label("noVNC / websockify", 12, C_TEXT2))
        novnc_row.addStretch()
        self._novnc_pill = _status_pill("检测中…")
        novnc_row.addWidget(self._novnc_pill)
        sc.addLayout(novnc_row)

        # VNC 密码
        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(pt(8))
        pwd_row.addWidget(make_label("VNC 密码", 11, C_TEXT3))
        self._vnc_pwd = QLineEdit()
        self._vnc_pwd.setPlaceholderText("留空则无密码")
        self._vnc_pwd.setEchoMode(QLineEdit.Password)
        self._vnc_pwd.setStyleSheet(
            f"QLineEdit {{ background:{C_CARD_LIGHT}; border:none; border-radius:6px;"
            f" padding:5px 10px; color:{C_TEXT}; font-size:{pt(11)}px; }}"
        )
        self._vnc_pwd.setFixedHeight(pt(32))
        pwd_row.addWidget(self._vnc_pwd, 1)
        sc.addLayout(pwd_row)
        sc.addStretch()

        info_grid.addWidget(status_card, 0, 0)

        # 右列：连接信息卡
        conn_card = make_card(10)
        apply_shadow(conn_card, blur=16, y=3, alpha=50)
        cc = QVBoxLayout(conn_card)
        cc.setContentsMargins(pt(18), pt(16), pt(18), pt(16))
        cc.setSpacing(pt(12))
        cc.addWidget(make_label("连接信息", 13, C_TEXT, bold=True))

        self._browser_tile = _info_tile(
            "🌐", "浏览器访问", dr.format_novnc_url(ip), selectable=True)
        cc.addWidget(self._browser_tile)

        self._vnc_tile = _info_tile(
            "🖥", "VNC 直连", dr.format_vnc_address(ip), selectable=True)
        cc.addWidget(self._vnc_tile)
        cc.addStretch()

        info_grid.addWidget(conn_card, 0, 1)
        root.addLayout(info_grid)

        # ══════════════════════════════════════════
        #  操作按钮
        # ══════════════════════════════════════════
        btn_row = QHBoxLayout()
        btn_row.setSpacing(pt(10))
        self._deploy_btn = make_button("一键部署", primary=True)
        self._stop_btn = make_button("停止服务")
        self._open_browser_btn = make_button("打开浏览器桌面", primary=True)
        self._open_vnc_btn = make_button("打开 VNC 客户端")
        self._ai_btn = make_button("问 AI", small=True)
        self._ai_btn.setStyleSheet(
            f"QPushButton {{ background:rgba(44,123,229,0.15); border:none;"
            f" border-radius:{pt(6)}px; color:{C_BLUE}; font-size:{pt(11)}px;"
            f" padding:{pt(4)}px {pt(12)}px; font-weight:600; }}"
            f"QPushButton:hover {{ background:rgba(44,123,229,0.25); }}"
        )
        self._ai_btn.setVisible(False)
        self._ai_btn.clicked.connect(self._do_ask_ai)
        btn_row.addWidget(self._deploy_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addSpacing(pt(12))
        btn_row.addWidget(self._open_browser_btn)
        btn_row.addWidget(self._open_vnc_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._ai_btn)
        root.addLayout(btn_row)

        # ══════════════════════════════════════════
        #  执行日志
        # ══════════════════════════════════════════
        log_card = make_card(10)
        apply_shadow(log_card, blur=14, y=2, alpha=40)
        ll = QVBoxLayout(log_card)
        ll.setContentsMargins(pt(18), pt(14), pt(18), pt(14))
        ll.setSpacing(pt(8))
        log_hdr = QHBoxLayout()
        log_hdr.addWidget(make_label("执行日志", 12, C_TEXT2, bold=True))
        log_hdr.addStretch()
        self._clear_log_btn = make_button("清空", small=True)
        self._clear_log_btn.clicked.connect(lambda: self._log.clear())
        log_hdr.addWidget(self._clear_log_btn)
        ll.addLayout(log_hdr)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(pt(100))
        self._log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._log.setStyleSheet(f"""
            QTextEdit {{
                background: {C_BG_DEEP}; border: none; border-radius: 8px;
                color: {C_GREEN}; padding: {pt(10)}px;
                font-size: {pt(11)}px;
                font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
            }}
        """)
        ll.addWidget(self._log)
        root.addWidget(log_card, 1)

        # ── 底部关闭 ──
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = make_button("关闭")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        # ── 信号连接 ──
        self._deploy_btn.clicked.connect(self._do_deploy_all)
        self._stop_btn.clicked.connect(self._do_stop)
        self._refresh_btn.clicked.connect(self._do_refresh)
        self._open_vnc_btn.clicked.connect(self._do_open_vnc)
        self._open_browser_btn.clicked.connect(self._do_open_browser)

        # 打开时自动检测
        self._do_refresh()

    # ── 日志 ──────────────────────────────────────────────────────────────────
    def _append(self, line: str):
        self._log.append(line)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── 状态药丸更新 ──────────────────────────────────────────────────────────
    def _set_pill(self, pill: QLabel, text: str, color: str):
        pill.setText(text)
        pill.setStyleSheet(
            f"background: rgba({_hex_to_rgba(color, 0.15)}); color: {color};"
            f" border-radius: {pt(4)}px; padding: {pt(3)}px {pt(10)}px;"
            f" font-size: {pt(11)}px; font-weight: 600;"
        )

    # ── 状态刷新 ──────────────────────────────────────────────────────────────
    def _do_refresh(self):
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("检测中…")
        self._set_pill(self._vnc_pill, "检测中…", C_TEXT3)
        self._set_pill(self._novnc_pill, "检测中…", C_TEXT3)

        self._status_thread = _StatusThread(self._runner)
        self._status_thread.result.connect(self._on_status)
        self._status_thread.start()

    def _on_status(self, s: dict):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("刷新状态")

        if s["vnc_running"]:
            self._set_pill(self._vnc_pill, f"运行中  PID {s['vnc_pid']}", C_GREEN)
        elif s["vnc_installed"]:
            self._set_pill(self._vnc_pill, "已安装 · 未运行", C_ORANGE)
        else:
            self._set_pill(self._vnc_pill, "未安装", C_TEXT3)

        if s["novnc_running"]:
            self._set_pill(self._novnc_pill, f"运行中  PID {s['novnc_pid']}", C_GREEN)
        elif s["novnc_installed"]:
            self._set_pill(self._novnc_pill, "已安装 · 未运行", C_ORANGE)
        else:
            self._set_pill(self._novnc_pill, "未安装", C_TEXT3)

    # ── 一键部署（VNC + noVNC 全流程）─────────────────────────────────────────
    def _do_deploy_all(self):
        pwd = self._runner.sudo_password
        cmds = [
            (dr.build_enable_autologin_cmd(pwd, self._runner.username), 30),
            (dr.build_install_vnc_cmd(pwd), 180),
            (dr.build_start_vnc_cmd(password=""), 45),
            (dr.build_install_novnc_cmd(pwd), 180),
            (dr.build_start_novnc_cmd(), 30),
        ]
        self._run_cmds(cmds, self._deploy_btn, "部署", self._on_deploy_all_done)

    def _on_deploy_all_done(self, rc: int, out: str):
        self._deploy_btn.setEnabled(True)
        self._deploy_btn.setText("一键部署")
        if rc == 0:
            url = dr.format_novnc_url(self._ip)
            self._append(f"\n--- 部署完成 ---")
            self._append(f"浏览器访问: {url}")
            self._append(f"VNC 直连:   {dr.format_vnc_address(self._ip)}")
            self._ai_btn.setVisible(False)
            self._do_refresh()
        else:
            self._append(f"\n--- 部署失败 (rc={rc}) ---")
            self._append("排查建议:")
            self._append("  优先接管现有 Jetson 桌面；没有 HDMI 时会自动尝试创建 :99 headless 显示")
            self._append("  如 headless 启动失败，确认已安装 xvfb / dbus-x11，且系统有 gnome-session、startxfce4 或 openbox-session 之一")
            self._append("  手动测试现有桌面: x11vnc -auth guess -display :0 -nopw -forever")
            self._append("  手动测试 headless: Xvfb :99 -screen 0 1920x1080x24 -ac & DISPLAY=:99 x11vnc -display :99 -nopw -forever")
            self._append("  查看日志: cat /tmp/x11vnc.log")
            self._append("  Headless 日志: cat /tmp/seeed-xvfb.log && cat /tmp/seeed-headless-desktop.log")
            self._ai_btn.setVisible(True)
            self._do_refresh()

    # ── 停止服务 ──────────────────────────────────────────────────────────────
    def _do_stop(self):
        cmds = [(dr.build_stop_cmd(), 10)]
        self._run_cmds(cmds, self._stop_btn, "停止", self._on_stop_done)

    def _on_stop_done(self, rc: int, out: str):
        self._stop_btn.setEnabled(True)
        self._stop_btn.setText("停止服务")
        self._append("\n--- 服务已停止 ---" if rc == 0 else f"\n--- 停止失败 (rc={rc}) ---")
        if rc != 0:
            self._ai_btn.setVisible(True)
        self._do_refresh()

    # ── 打开浏览器 ────────────────────────────────────────────────────────────
    def _do_open_browser(self):
        url = dr.format_novnc_url(self._ip)
        dr.open_in_browser(url)
        self._append(f"已打开浏览器: {url}")

    # ── 打开 VNC 客户端 ──────────────────────────────────────────────────────
    def _do_open_vnc(self):
        ok = dr.launch_vnc_viewer(self._ip)
        if not ok:
            QMessageBox.information(
                self, "VNC 客户端",
                f"未找到 VNC 客户端。\n\n"
                f"VNC 地址: {dr.format_vnc_address(self._ip)}\n\n"
                f"推荐安装:\n"
                f"  Linux: sudo apt install tigervnc-viewer\n"
                f"  Windows: RealVNC Viewer\n"
                f"  或直接用浏览器桌面 (noVNC)",
            )

    # ── 问 AI ─────────────────────────────────────────────────────────────────
    def _do_ask_ai(self):
        log_text = self._log.toPlainText()
        try:
            from seeed_jetson_develop.gui.main_window_v2 import MainWindowV2
            win = self.window()
            while win and not isinstance(win, MainWindowV2):
                win = win.parent()
            if win and hasattr(win, '_ai_assistant'):
                win._ai_assistant.inject_error("VNC 远程桌面部署", log_text)
                return
        except Exception:
            pass
        # fallback: 遍历所有顶级窗口
        from PyQt5.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if hasattr(w, '_ai_assistant'):
                w._ai_assistant.inject_error("VNC 远程桌面部署", log_text)
                return

    # ── 通用命令执行 ──────────────────────────────────────────────────────────
    def _run_cmds(self, cmds, btn, label, callback):
        btn.setEnabled(False)
        btn.setText(f"{label}中…")
        self._log.clear()
        self._thread = _SshCmdThread(self._runner, cmds)
        self._thread.line_out.connect(self._append)
        self._thread.finished_.connect(callback)
        self._thread.start()


def open_desktop_dialog(runner: SSHRunner, ip: str, parent=None):
    """打开远程桌面对话框。"""
    dlg = DesktopRemoteDialog(runner, ip, parent)
    dlg.exec_()
