"""远程桌面对话框 — 一键部署 x11vnc + noVNC，访问 Jetson 图形桌面。"""
from __future__ import annotations

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QLabel,
    QMessageBox, QSizePolicy, QTextEdit, QVBoxLayout,
)

from seeed_jetson_develop.core.runner import SSHRunner
from seeed_jetson_develop.gui.theme import (
    C_BG, C_CARD, C_CARD_LIGHT, C_GREEN, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    apply_shadow, make_button, make_card, make_label, pt,
    show_info_message,
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


class DesktopRemoteDialog(QDialog):
    def __init__(self, runner: SSHRunner, ip: str, parent=None):
        super().__init__(parent)
        self._runner = runner
        self._ip = ip
        self._thread: _SshCmdThread | None = None
        self._status_thread: _StatusThread | None = None

        self.setWindowTitle("远程桌面")
        self.setMinimumSize(680, 560)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        root.addWidget(make_label("🖥 远程桌面", 16, C_TEXT, bold=True))
        root.addWidget(make_label(
            f"一键在 Jetson ({ip}) 上部署 VNC + noVNC 远程桌面服务。\n"
            "部署完成后可通过浏览器直接访问 Jetson 图形桌面，也可用 VNC 客户端连接。\n"
            "未插 HDMI 时会自动尝试创建 headless 虚拟显示。",
            11, C_TEXT2, wrap=True,
        ))

        # ── 状态卡片 ──
        status_card = make_card(12)
        apply_shadow(status_card, blur=18, y=4, alpha=60)
        sc = QVBoxLayout(status_card)
        sc.setContentsMargins(18, 16, 18, 16)
        sc.setSpacing(10)

        sc.addWidget(make_label("服务状态", 13, C_TEXT, bold=True))

        vnc_row = QHBoxLayout()
        vnc_row.addWidget(make_label("x11vnc (VNC 服务)", 12, C_TEXT2))
        self._vnc_status = make_label("检测中…", 12, C_TEXT3)
        vnc_row.addWidget(self._vnc_status)
        vnc_row.addStretch()
        sc.addLayout(vnc_row)

        novnc_row = QHBoxLayout()
        novnc_row.addWidget(make_label("noVNC (浏览器访问)", 12, C_TEXT2))
        self._novnc_status = make_label("检测中…", 12, C_TEXT3)
        novnc_row.addWidget(self._novnc_status)
        novnc_row.addStretch()
        sc.addLayout(novnc_row)

        # 访问地址（可复制）
        addr_row = QHBoxLayout()
        addr_row.addWidget(make_label("浏览器访问:", 11, C_TEXT3))
        self._novnc_url = make_label(dr.format_novnc_url(ip), 11, C_GREEN)
        self._novnc_url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        addr_row.addWidget(self._novnc_url)
        addr_row.addSpacing(20)
        addr_row.addWidget(make_label("VNC 直连:", 11, C_TEXT3))
        self._vnc_addr = make_label(dr.format_vnc_address(ip), 11, C_TEXT2)
        self._vnc_addr.setTextInteractionFlags(Qt.TextSelectableByMouse)
        addr_row.addWidget(self._vnc_addr)
        addr_row.addStretch()
        sc.addLayout(addr_row)

        auth_row = QHBoxLayout()
        auth_row.addWidget(make_label("连接认证:", 11, C_TEXT3))
        auth_row.addWidget(make_label("当前版本固定为无密码访问", 11, C_GREEN))
        auth_row.addWidget(make_label("（会清理旧的 VNC 密码配置）", 10, C_TEXT3))
        auth_row.addStretch()
        sc.addLayout(auth_row)

        root.addWidget(status_card)

        # ── 操作按钮 ──
        op_row = QHBoxLayout()
        op_row.setSpacing(10)
        self._deploy_btn = make_button("🚀 一键部署", primary=True, small=True)
        self._stop_btn = make_button("停止服务", small=True)
        self._refresh_btn = make_button("刷新状态", small=True)
        op_row.addWidget(self._deploy_btn)
        op_row.addWidget(self._stop_btn)
        op_row.addWidget(self._refresh_btn)
        op_row.addStretch()
        root.addLayout(op_row)

        # ── 访问按钮 ──
        access_row = QHBoxLayout()
        access_row.setSpacing(10)
        self._open_browser_btn = make_button("🌐 打开浏览器桌面", primary=True, small=True)
        self._open_vnc_btn = make_button("打开 VNC 客户端", small=True)
        access_row.addWidget(self._open_browser_btn)
        access_row.addWidget(self._open_vnc_btn)
        access_row.addStretch()
        root.addLayout(access_row)

        # ── 日志 ──
        log_card = make_card(12)
        ll = QVBoxLayout(log_card)
        ll.setContentsMargins(18, 14, 18, 14)
        ll.setSpacing(8)
        ll.addWidget(make_label("执行日志", 12, C_TEXT, bold=True))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(120)
        self._log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._log.setStyleSheet(f"""
            QTextEdit {{
                background:{C_CARD_LIGHT}; border:none; border-radius:8px;
                color:{C_TEXT2}; padding:10px;
                font-size:{pt(10)}px; font-family:'JetBrains Mono','Consolas',monospace;
            }}
        """)
        ll.addWidget(self._log)
        root.addWidget(log_card, 1)

        # ── 关闭 ──
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

    # ── 状态刷新 ──────────────────────────────────────────────────────────────
    def _do_refresh(self):
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("检测中…")
        self._vnc_status.setText("检测中…")
        self._vnc_status.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}px; background:transparent;")
        self._novnc_status.setText("检测中…")
        self._novnc_status.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}px; background:transparent;")

        self._status_thread = _StatusThread(self._runner)
        self._status_thread.result.connect(self._on_status)
        self._status_thread.start()

    def _on_status(self, s: dict):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("刷新状态")

        if s["vnc_running"]:
            self._vnc_status.setText(f"● 运行中 (PID {s['vnc_pid']})")
            self._vnc_status.setStyleSheet(
                f"color:{C_GREEN}; font-size:{pt(12)}px; background:transparent; font-weight:700;")
        elif s["vnc_installed"]:
            self._vnc_status.setText("已安装，未运行")
            self._vnc_status.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(12)}px; background:transparent;")
        else:
            self._vnc_status.setText("未安装")
            self._vnc_status.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}px; background:transparent;")

        if s["novnc_running"]:
            self._novnc_status.setText(f"● 运行中 (PID {s['novnc_pid']})")
            self._novnc_status.setStyleSheet(
                f"color:{C_GREEN}; font-size:{pt(12)}px; background:transparent; font-weight:700;")
        elif s["novnc_installed"]:
            self._novnc_status.setText("已安装，未运行")
            self._novnc_status.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(12)}px; background:transparent;")
        else:
            self._novnc_status.setText("未安装")
            self._novnc_status.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}px; background:transparent;")

    # ── 一键部署（VNC + noVNC 全流程）─────────────────────────────────────────
    def _do_deploy_all(self):
        pwd = self._runner.sudo_password
        cmds = [
            # 0. 先确保图形登录为自动登录，避免重启后停在登录界面
            (dr.build_enable_autologin_cmd(pwd, self._runner.username), 30),
            # 1. 安装 x11vnc
            (dr.build_install_vnc_cmd(pwd), 180),
            # 2. 启动 x11vnc
            (dr.build_start_vnc_cmd(), 15),
            # 3. 安装 noVNC + websockify
            (dr.build_install_novnc_cmd(pwd), 180),
            # 4. 启动 websockify
            (dr.build_start_novnc_cmd(), 15),
        ]
        self._run_cmds(cmds, self._deploy_btn, "🚀 部署", self._on_deploy_all_done)

    def _on_deploy_all_done(self, rc: int, out: str):
        self._deploy_btn.setEnabled(True)
        self._deploy_btn.setText("🚀 一键部署")
        if rc == 0:
            url = dr.format_novnc_url(self._ip)
            self._append(f"\n✅ 全部部署成功！")
            self._append("   已自动确保 GDM 免登录配置开启。")
            self._append(f"   浏览器访问：{url}")
            self._append(f"   VNC 直连：{dr.format_vnc_address(self._ip)}")
            self._do_refresh()
        else:
            self._append(f"\n❌ 部署失败 (rc={rc})")
            self._append("\n排查建议：")
            self._append("  • x11vnc 需要 Jetson 有图形桌面环境（GNOME/XFCE）且已登录")
            self._append("  • 当前版本会在无 HDMI 时自动创建 :99 虚拟显示，可查看 /tmp/seeed-xvfb.log")
            self._append("  • 可 SSH 到 Jetson 手动运行：DISPLAY=:99 x11vnc -display :99 -nopw -forever")
            self._append("  • 查看日志：cat /tmp/x11vnc.log")
            self._append("  • 若 headless 桌面为空白，可查看：cat /tmp/seeed-headless-desktop.log")
            self._append("  • 确认 Jetson 可以联网（apt-get 需要下载软件包）")
            self._do_refresh()

    # ── 停止服务 ──────────────────────────────────────────────────────────────
    def _do_stop(self):
        cmds = [(dr.build_stop_cmd(), 10)]
        self._run_cmds(cmds, self._stop_btn, "停止服务", self._on_stop_done)

    def _on_stop_done(self, rc: int, out: str):
        self._stop_btn.setEnabled(True)
        self._stop_btn.setText("停止服务")
        self._append("\n✅ 服务已停止" if rc == 0 else f"\n❌ 停止失败 (rc={rc})")
        self._do_refresh()

    # ── 打开浏览器 ────────────────────────────────────────────────────────────
    def _do_open_browser(self):
        url = dr.format_novnc_url(self._ip)
        dr.open_in_browser(url)
        self._append(f"已打开浏览器：{url}")

    # ── 打开 VNC 客户端 ──────────────────────────────────────────────────────
    def _do_open_vnc(self):
        ok = dr.launch_vnc_viewer(self._ip)
        if not ok:
            show_info_message(
                self, "VNC 客户端",
                f"未找到 VNC 客户端。\n\n"
                f"VNC 地址：{dr.format_vnc_address(self._ip)}\n\n"
                f"推荐安装：\n"
                f"• Linux: sudo apt install tigervnc-viewer 或 remmina\n"
                f"• Windows: RealVNC Viewer (https://www.realvnc.com/)\n"
                f"• 或直接用「打开浏览器桌面」通过 noVNC 访问",
            )

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
