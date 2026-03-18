"""远程开发页 — 无边框大气风格
包含：Claude API Key 配置、局域网扫描、SSH 连接检测、开发工具入口。
"""
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout,
    QScrollArea, QDialog, QTextEdit, QMessageBox, QProgressBar,
)

from seeed_jetson_develop.core import config as _cfg
from seeed_jetson_develop.core.events import bus
from seeed_jetson_develop.core.runner import SSHRunner, set_runner, get_runner
from seeed_jetson_develop.modules.remote import connector
from seeed_jetson_develop.modules.remote.jetson_init import (
    list_serial_ports,
    open_jetson_init_dialog,
    open_jetson_net_config_dialog,
)
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, make_input_card as _input_card,
    apply_shadow as _shadow,
)


# ── 局域网扫描线程 ────────────────────────────────────────────────────────────
class _ScanThread(QThread):
    found    = pyqtSignal(list)
    status   = pyqtSignal(str)
    progress = pyqtSignal(int, int)   # scanned, total

    def __init__(self, subnet: str | None = None):
        super().__init__()
        self._subnet = subnet

    def run(self):
        self.status.emit("正在扫描局域网…")
        hosts = connector.scan_local_network(
            self._subnet,
            on_progress=lambda s, t: self.progress.emit(s, t),
        )
        self.found.emit(hosts)


# ── SSH 认证线程 ──────────────────────────────────────────────────────────────
class _SSHCheckThread(QThread):
    result = pyqtSignal(bool, str)

    def __init__(self, host: str, username: str = "seeed", password: str = ""):
        super().__init__()
        self._host     = host
        self._username = username
        self._password = password

    def run(self):
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                self._host, port=22,
                username=self._username,
                password=self._password or None,
                timeout=10,
                look_for_keys=True,
                allow_agent=True,
            )
            _, stdout, _ = client.exec_command("echo ok", timeout=5)
            stdout.read()
            client.close()
            self.result.emit(True, "")
        except Exception as e:
            self.result.emit(False, str(e))


# ── API Key 配置对话框 ────────────────────────────────────────────────────────
class _ApiKeyDialog(QDialog):
    key_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置 Anthropic API Key")
        self.setMinimumSize(560, 400)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        lay.addWidget(_lbl("🤖 Claude API Key 配置", 16, C_TEXT, bold=True))
        lay.addWidget(_lbl(
            "API Key 用于 Skills AI 执行（通过 claude-sonnet 执行操作手册）。\n"
            "获取地址：console.anthropic.com",
            11, C_TEXT2, wrap=True
        ))

        # API Key 输入行
        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("sk-ant-api03-…")
        self._key_edit.setEchoMode(QLineEdit.Password)
        self._key_edit.setStyleSheet(f"""
            QLineEdit {{
                background:{C_CARD_LIGHT};
                border:none;
                border-radius:10px;
                padding:10px 16px;
                color:{C_TEXT};
                font-size:{_pt(12)}pt;
                font-family:'JetBrains Mono','Consolas',monospace;
            }}
            QLineEdit:focus {{ background:{C_CARD}; }}
        """)
        self._key_edit.setFixedHeight(_pt(48))

        self._toggle_btn = _btn("👁", small=True)
        self._toggle_btn.setFixedWidth(_pt(50))
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.toggled.connect(self._toggle_echo)

        input_row.addWidget(self._key_edit, 1)
        input_row.addWidget(self._toggle_btn)
        lay.addLayout(input_row)

        # Base URL 输入行
        lay.addWidget(_lbl("Base URL（可选，留空使用默认）", 11, C_TEXT3))
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://api.anthropic.com")
        self._url_edit.setStyleSheet(f"""
            QLineEdit {{
                background:{C_CARD_LIGHT};
                border:none;
                border-radius:10px;
                padding:10px 16px;
                color:{C_TEXT};
                font-size:{_pt(11)}pt;
                font-family:'JetBrains Mono','Consolas',monospace;
            }}
            QLineEdit:focus {{ background:{C_CARD}; }}
        """)
        self._url_edit.setFixedHeight(_pt(44))
        lay.addWidget(self._url_edit)

        # 当前状态提示
        cfg = _cfg.load()
        existing = cfg.get("anthropic_api_key", "")
        existing_url = cfg.get("anthropic_base_url", "")
        if existing:
            self._key_edit.setPlaceholderText(f"当前: {existing[:12]}••••••")
            status_text = f"✅ 已配置（前缀：{existing[:12]}…）"
            status_color = C_GREEN
        else:
            status_text = "⚠ 尚未配置"
            status_color = C_ORANGE
        if existing_url:
            self._url_edit.setText(existing_url)
        self._status_lbl = _lbl(status_text, 11, status_color)
        lay.addWidget(self._status_lbl)

        lay.addStretch()

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        save_btn  = _btn("💾  保存", primary=True)
        clear_btn = _btn("🗑  清除", danger=True)
        close_btn = _btn("取消")
        btn_row.addWidget(save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        save_btn.clicked.connect(self._save)
        clear_btn.clicked.connect(self._clear)
        close_btn.clicked.connect(self.close)

    def _toggle_echo(self, checked: bool):
        self._key_edit.setEchoMode(
            QLineEdit.Normal if checked else QLineEdit.Password
        )
        self._toggle_btn.setText("🙈" if checked else "👁")

    def _save(self):
        key = self._key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "提示", "请输入 API Key。")
            return
        if len(key) < 20:
            QMessageBox.warning(self, "提示", "API Key 格式不正确（长度过短）。")
            return
        url = self._url_edit.text().strip()
        data = _cfg.load()
        data["anthropic_api_key"] = key
        data["anthropic_base_url"] = url
        _cfg.save(data)
        status = f"✅ 已保存（前缀：{key[:12]}…）"
        if url and url != "https://api.anthropic.com":
            status += f"  Base URL: {url}"
        self._status_lbl.setText(status)
        self._status_lbl.setStyleSheet(
            f"color:{C_GREEN}; font-size:{_pt(11)}pt; background:transparent;"
        )
        self.key_saved.emit()
        QMessageBox.information(self, "成功", "API Key 已保存到本地配置文件。")
        self.close()

    def _clear(self):
        reply = QMessageBox.question(
            self, "确认清除",
            "确定要清除已保存的 API Key 吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            data = _cfg.load()
            data["anthropic_api_key"] = ""
            data["anthropic_base_url"] = ""
            _cfg.save(data)
            self._key_edit.clear()
            self._url_edit.clear()
            self._status_lbl.setText("⚠ 已清除")
            self._status_lbl.setStyleSheet(
                f"color:{C_ORANGE}; font-size:{_pt(11)}pt; background:transparent;"
            )
            self.key_saved.emit()



# ── SSH 命令执行线程（通用，供 Web 对话框复用）────────────────────────────────
class _SshCmdThread(QThread):
    line_out  = pyqtSignal(str)
    finished_ = pyqtSignal(int, str)   # rc, last_output

    def __init__(self, runner, commands):
        """commands: [(cmd, timeout), ...]"""
        super().__init__()
        self._runner   = runner
        self._commands = commands
        self._last_out = ""

    def run(self):
        for cmd, timeout in self._commands:
            self.line_out.emit(f"$ {cmd}")
            rc, out = self._runner.run(cmd, timeout=timeout,
                                       on_output=lambda l: self.line_out.emit(l))
            self._last_out = out
            if rc != 0:
                self.finished_.emit(rc, out)
                return
        self.finished_.emit(0, self._last_out)


# ── VS Code Server (Web) 对话框 ───────────────────────────────────────────────
class _VscodeWebDialog(QDialog):
    def __init__(self, runner, ip, parent=None):
        super().__init__(parent)
        self._runner = runner
        self._ip     = ip
        self._thread = None
        self.setWindowTitle("VS Code Server (Web) 部署")
        self.setMinimumSize(640, 500)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        lay.addWidget(_lbl("🌐 VS Code Server (Web) 部署", 16, C_TEXT, bold=True))
        lay.addWidget(_lbl(
            f"将在 Jetson ({ip}) 上安装并启动 code-server，完成后可通过浏览器访问。",
            11, C_TEXT2, wrap=True
        ))

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(f"""
            background:{C_CARD}; border:none; border-radius:10px;
            color:{C_TEXT2}; font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(10)}pt; padding:12px;
        """)
        lay.addWidget(self._log, 1)

        self._result_lbl = _lbl("", 12, C_TEXT2, wrap=True)
        lay.addWidget(self._result_lbl)

        btn_row = QHBoxLayout()
        self._run_btn   = _btn("开始部署", primary=True)
        self._close_btn = _btn("关闭")
        btn_row.addWidget(self._run_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._close_btn)
        lay.addLayout(btn_row)

        self._run_btn.clicked.connect(self._start)
        self._close_btn.clicked.connect(self.close)

    def _append(self, line):
        self._log.append(line)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _start(self):
        self._run_btn.setEnabled(False)
        self._log.clear()
        self._result_lbl.setText("")
        # 多镜像降级下载：依次尝试直到成功，验证文件大小后安装
        install_cmd = (
            "CS_VER=4.96.2 && "
            "ARCH=$(dpkg --print-architecture) && "
            "DEB=code-server_${CS_VER}_${ARCH}.deb && "
            "CACHE=~/.cache/code-server && "
            "mkdir -p $CACHE && "
            "rm -f ${CACHE}/${DEB} && "
            "RELEASE_PATH=\"coder/code-server/releases/download/v${CS_VER}/${DEB}\" && "
            "for MIRROR in "
            "  https://gh.ddlc.top/https://github.com "
            "  https://ghproxy.cfd/https://github.com "
            "  https://hub.gitmirror.com/https://github.com; do "
            "  echo \"尝试镜像: ${MIRROR}\" && "
            "  wget -q --show-progress --timeout=60 --tries=1 "
            "    ${MIRROR}/${RELEASE_PATH} -O ${CACHE}/${DEB} && break; "
            "  echo '失败，尝试下一个…' && rm -f ${CACHE}/${DEB}; "
            "done && "
            "[ -f ${CACHE}/${DEB} ] && [ $(stat -c%s ${CACHE}/${DEB}) -gt 52428800 ] || "
            "  { echo '下载失败，文件不完整'; exit 1; } && "
            "echo '安装中…' && "
            f"echo {self._runner.password!r} | sudo -S dpkg -i ${{CACHE}}/${{DEB}} 2>&1"
        )
        cmds = [
            (install_cmd, 600),
            ("code-server --bind-addr 0.0.0.0:8080 --auth password > /tmp/code-server.log 2>&1 & echo started", 10),
            ("sleep 2 && grep password ~/.config/code-server/config.yaml 2>/dev/null || echo 'config not found yet'", 10),
        ]
        self._thread = _SshCmdThread(self._runner, cmds)
        self._thread.line_out.connect(self._append)
        self._thread.finished_.connect(self._on_done)
        self._thread.start()

    def _on_done(self, rc, last_out):
        self._run_btn.setEnabled(True)
        if rc == 0:
            url = f"http://{self._ip}:8080"
            self._result_lbl.setText(f"✅ 部署完成！访问地址：{url}\n密码见上方日志 password 行。")
            self._result_lbl.setStyleSheet(
                f"color:{C_GREEN}; font-size:{_pt(12)}pt; background:transparent;"
            )
        else:
            self._result_lbl.setText(f"❌ 部署失败（rc={rc}）：{last_out[:200]}")
            self._result_lbl.setStyleSheet(
                f"color:{C_RED}; font-size:{_pt(12)}pt; background:transparent;"
            )


# ── Jupyter Lab 启动对话框 ────────────────────────────────────────────────────
class _JupyterLaunchDialog(QDialog):
    def __init__(self, runner, ip, parent=None):
        super().__init__(parent)
        self._runner = runner
        self._ip     = ip
        self._thread = None
        self.setWindowTitle("Jupyter Lab 安装 & 启动")
        self.setMinimumSize(640, 500)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        lay.addWidget(_lbl("📓 Jupyter Lab 安装 & 启动", 16, C_TEXT, bold=True))
        lay.addWidget(_lbl(
            f"将在 Jetson ({ip}) 上安装并启动 Jupyter Lab，完成后可通过浏览器访问。",
            11, C_TEXT2, wrap=True
        ))

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(f"""
            background:{C_CARD}; border:none; border-radius:10px;
            color:{C_TEXT2}; font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(10)}pt; padding:12px;
        """)
        lay.addWidget(self._log, 1)

        self._result_lbl = _lbl("", 12, C_TEXT2, wrap=True)
        lay.addWidget(self._result_lbl)

        btn_row = QHBoxLayout()
        self._run_btn   = _btn("安装并启动", primary=True)
        self._close_btn = _btn("关闭")
        btn_row.addWidget(self._run_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._close_btn)
        lay.addLayout(btn_row)

        self._run_btn.clicked.connect(self._start)
        self._close_btn.clicked.connect(self.close)

    def _append(self, line):
        self._log.append(line)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _start(self):
        self._run_btn.setEnabled(False)
        self._log.clear()
        self._result_lbl.setText("")
        cmds = [
            ("PYTHONUNBUFFERED=1 pip3 install jupyterlab 2>&1", 300),
            (
                "nohup ~/.local/bin/jupyter lab --ip=0.0.0.0 --port=8888 --no-browser "
                "--NotebookApp.token='' --NotebookApp.password='' "
                "> /tmp/jupyter.log 2>&1 & echo started",
                10,
            ),
            ("sleep 3 && cat /tmp/jupyter.log 2>/dev/null | head -20", 15),
        ]
        self._thread = _SshCmdThread(self._runner, cmds)
        self._thread.line_out.connect(self._append)
        self._thread.finished_.connect(self._on_done)
        self._thread.start()

    def _on_done(self, rc, last_out):
        self._run_btn.setEnabled(True)
        url = f"http://{self._ip}:8888"
        if rc == 0:
            self._result_lbl.setText(f"✅ 启动完成！访问地址：{url}")
            self._result_lbl.setStyleSheet(
                f"color:{C_GREEN}; font-size:{_pt(12)}pt; background:transparent;"
            )
        else:
            self._result_lbl.setText(f"❌ 启动失败（rc={rc}）：{last_out[:200]}")
            self._result_lbl.setStyleSheet(
                f"color:{C_RED}; font-size:{_pt(12)}pt; background:transparent;"
            )


# ── Claude API 连通性测试线程 ─────────────────────────────────────────────────
class _ApiTestThread(QThread):
    result = pyqtSignal(bool, str)   # ok, message

    def __init__(self, api_key, base_url):
        super().__init__()
        self._key      = api_key
        self._base_url = base_url or "https://api.anthropic.com"

    def run(self):
        try:
            import anthropic
            client = anthropic.Anthropic(
                api_key=self._key,
                base_url=self._base_url,
            )
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{"role": "user", "content": "hi"}],
            )
            model_id = getattr(msg, "model", "claude-haiku-4-5")
            self.result.emit(True, f"API 连通正常，模型：{model_id}")
        except Exception as e:
            self.result.emit(False, str(e))


# ── VS Code Remote SSH 说明对话框 ─────────────────────────────────────────────
class _VscodeSSHDialog(QDialog):
    def __init__(self, ip: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("VS Code Remote SSH 配置")
        self.setMinimumSize(620, 480)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        lay.addWidget(_lbl("🔵 VS Code Remote SSH 配置指南", 16, C_TEXT, bold=True))

        ssh_addr = f"ssh seeed@{ip}" if ip else "ssh seeed@<设备 IP>"
        steps = f"""步骤 1：确保本机已安装 VS Code
步骤 2：在 VS Code 中安装扩展「Remote - SSH」（ms-vscode-remote.remote-ssh）
步骤 3：按 F1 → 「Remote-SSH: Connect to Host…」→ 输入以下地址：

    {ssh_addr}

步骤 4：输入 Jetson 设备密码（默认 seeed 或 jetson）
步骤 5：连接成功后，在 VS Code 中打开远程文件夹即可编辑代码

提示：
• 确保 Jetson 设备已启动 SSH 服务（sudo systemctl start ssh）
• 可在设备上运行以下命令检查 SSH 状态：
    sudo systemctl status ssh
"""
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(steps)
        viewer.setStyleSheet(f"""
            background:{C_CARD};
            border:none;
            border-radius:10px;
            color:{C_TEXT2};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(11)}pt;
            padding:14px;
        """)
        lay.addWidget(viewer, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = _btn("关闭")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)


# ── Jupyter Lab 对话框 ────────────────────────────────────────────────────────
class _JupyterDialog(QDialog):
    def __init__(self, ip: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Jupyter Lab 启动")
        self.setMinimumSize(580, 400)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        lay.addWidget(_lbl("📓 Jupyter Lab 使用指南", 16, C_TEXT, bold=True))

        port = "8888"
        url  = f"http://{ip}:{port}" if ip else f"http://<设备 IP>:{port}"
        steps = f"""步骤 1：在 Jetson 设备上安装 Jupyter Lab（若未安装）：
    pip3 install jupyterlab

步骤 2：启动 Jupyter Lab（允许远程访问）：
    jupyter lab --ip=0.0.0.0 --port={port} --no-browser

步骤 3：在本机浏览器中访问：
    {url}

步骤 4：首次访问需要 token，从 Jetson 终端输出中复制 token 并粘贴

提示：
• 若需要后台运行，可使用：
    nohup jupyter lab --ip=0.0.0.0 --port={port} --no-browser &
• 通过 Skills 市场可一键安装 Jupyter Lab
"""
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(steps)
        viewer.setStyleSheet(f"""
            background:{C_CARD};
            border:none;
            border-radius:10px;
            color:{C_TEXT2};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(11)}pt;
            padding:14px;
        """)
        lay.addWidget(viewer, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = _btn("关闭")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)


# ── 主页面 ────────────────────────────────────────────────────────────────────
def build_page() -> QWidget:
    page = QWidget()
    page.setStyleSheet(f"background:{C_BG};")
    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    # ── 页头 - 无边框 ──
    header = QWidget()
    header.setStyleSheet(f"background:{C_BG_DEEP};")
    header.setFixedHeight(_pt(64))
    hl = QHBoxLayout(header)
    hl.setContentsMargins(28, 0, 28, 0)
    hl.addWidget(_lbl("远程开发", 18, C_TEXT, bold=True))
    hl.addSpacing(12)
    hl.addWidget(_lbl("通过 VS Code / Web IDE / AI 辅助建立远程开发环境", 12, C_TEXT3))
    hl.addStretch()
    root.addWidget(header)

    # ── 滚动区域 ──
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setStyleSheet("background:transparent; border:none;")
    inner = QWidget()
    inner.setStyleSheet(f"background:{C_BG};")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(28, 24, 28, 24)
    lay.setSpacing(20)

    # ─────────────────────────────────────────────────────────────
    # 卡片 A：Claude API 配置
    # ─────────────────────────────────────────────────────────────
    api_card = _card(12)
    api_lay  = QVBoxLayout(api_card)
    api_lay.setContentsMargins(24, 20, 24, 20)
    api_lay.setSpacing(14)

    api_title_row = QHBoxLayout()
    api_title_row.addWidget(_lbl("🤖 Claude API 配置", 15, C_TEXT, bold=True))
    api_title_row.addStretch()

    _api_status_lbl = QLabel()
    _api_status_lbl.setStyleSheet(f"font-size:{_pt(11)}pt; background:transparent;")
    api_title_row.addWidget(_api_status_lbl)
    api_lay.addLayout(api_title_row)

    api_info_row = QHBoxLayout()
    api_info_row.setSpacing(14)
    _api_key_preview = _lbl("", 11, C_TEXT3)
    api_info_row.addWidget(_api_key_preview, 1)
    api_config_btn = _btn("配置 / 修改", small=True)
    api_info_row.addWidget(api_config_btn)
    api_lay.addLayout(api_info_row)

    api_lay.addWidget(_lbl(
        "用途说明：用于 Skills AI 执行（通过 claude-sonnet 执行操作手册）",
        11, C_TEXT3, wrap=True
    ))
    _shadow(api_card)
    lay.addWidget(api_card)

    def _refresh_api_status():
        cfg = _cfg.load()
        key = cfg.get("anthropic_api_key", "")
        url = cfg.get("anthropic_base_url", "")
        if key:
            _api_status_lbl.setText("✅ 已配置")
            _api_status_lbl.setStyleSheet(
                f"color:{C_GREEN}; font-size:{_pt(11)}pt; background:transparent; font-weight:700;"
            )
            preview = f"API Key: {key[:12]}••••••••"
            if url and url != "https://api.anthropic.com":
                preview += f"  |  Base URL: {url}"
            _api_key_preview.setText(preview)
            _api_key_preview.setStyleSheet(
                f"color:{C_TEXT2}; font-size:{_pt(11)}pt; background:transparent;"
                f" font-family:'JetBrains Mono','Consolas',monospace;"
            )
        else:
            _api_status_lbl.setText("⚠ 未配置")
            _api_status_lbl.setStyleSheet(
                f"color:{C_ORANGE}; font-size:{_pt(11)}pt; background:transparent; font-weight:700;"
            )
            _api_key_preview.setText("尚未配置 API Key")
            _api_key_preview.setStyleSheet(
                f"color:{C_TEXT3}; font-size:{_pt(11)}pt; background:transparent;"
            )

    def _open_api_dialog():
        dlg = _ApiKeyDialog(parent=page)
        dlg.key_saved.connect(_refresh_api_status)
        dlg.exec_()

    api_config_btn.clicked.connect(_open_api_dialog)
    _refresh_api_status()

    # ─────────────────────────────────────────────────────────────
    # 卡片 B：设备连接
    # ─────────────────────────────────────────────────────────────
    conn_card = _card(12)
    conn_lay  = QVBoxLayout(conn_card)
    conn_lay.setContentsMargins(24, 20, 24, 20)
    conn_lay.setSpacing(14)

    conn_title_row = QHBoxLayout()
    conn_title_row.addWidget(_lbl("🔗 设备连接", 15, C_TEXT, bold=True))
    conn_title_row.addStretch()
    _conn_status_lbl = QLabel("● 未连接")
    _conn_status_lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:{_pt(11)}pt; background:transparent;")
    conn_title_row.addWidget(_conn_status_lbl)
    conn_lay.addLayout(conn_title_row)

    ip_row = QHBoxLayout()
    ip_row.setSpacing(10)
    ip_row.addWidget(_lbl("设备 IP / 主机名", 12, C_TEXT2))
    _ip_input = QLineEdit()
    _ip_input.setPlaceholderText("192.168.1.xxx 或 jetson.local")
    _ip_input.setStyleSheet(f"""
        QLineEdit {{
            background:{C_CARD_LIGHT};
            border:none;
            border-radius:10px;
            padding:8px 16px;
            color:{C_TEXT};
            font-size:{_pt(12)}pt;
        }}
        QLineEdit:focus {{ background:{C_CARD}; }}
    """)
    _ip_input.setFixedHeight(_pt(44))
    ip_row.addWidget(_ip_input, 1)
    ssh_test_btn = _btn("连接", primary=True, small=True)
    scan_btn     = _btn("扫描局域网", small=True)
    ip_row.addWidget(ssh_test_btn)
    ip_row.addWidget(scan_btn)
    conn_lay.addLayout(ip_row)

    # 用户名 / 密码行
    auth_row = QHBoxLayout()
    auth_row.setSpacing(10)
    auth_row.addWidget(_lbl("用户名", 11, C_TEXT3))
    _user_input = QLineEdit()
    _user_input.setText("seeed")
    _user_input.setFixedHeight(_pt(40))
    _user_input.setStyleSheet(f"""
        QLineEdit {{
            background:{C_CARD_LIGHT};
            border:none;
            border-radius:8px;
            padding:6px 12px;
            color:{C_TEXT};
            font-size:{_pt(11)}pt;
        }}
    """)
    auth_row.addWidget(_user_input)
    auth_row.addSpacing(14)
    auth_row.addWidget(_lbl("密码", 11, C_TEXT3))
    _pass_input = QLineEdit()
    _pass_input.setPlaceholderText("留空则使用密钥认证")
    _pass_input.setEchoMode(QLineEdit.Password)
    _pass_input.setFixedHeight(_pt(40))
    _pass_input.setStyleSheet(f"""
        QLineEdit {{
            background:{C_CARD_LIGHT};
            border:none;
            border-radius:8px;
            padding:6px 12px;
            color:{C_TEXT};
            font-size:{_pt(11)}pt;
        }}
    """)
    auth_row.addWidget(_pass_input)
    conn_lay.addLayout(auth_row)

    # 扫描子网输入
    subnet_row = QHBoxLayout()
    subnet_row.addWidget(_lbl("扫描网段", 11, C_TEXT3))
    _subnet_input = QLineEdit()
    _subnet_input.setText("192.168.1")
    _subnet_input.setPlaceholderText("192.168.x")
    _subnet_input.setStyleSheet(f"""
        QLineEdit {{
            background:{C_CARD_LIGHT};
            border:none;
            border-radius:8px;
            padding:6px 12px;
            color:{C_TEXT2};
            font-size:{_pt(11)}pt;
        }}
    """)
    _subnet_input.setFixedWidth(160)
    _subnet_input.setFixedHeight(_pt(40))
    subnet_row.addWidget(_subnet_input)
    subnet_row.addStretch()
    conn_lay.addLayout(subnet_row)

    # 扫描结果区
    _scan_result_lbl = _lbl("", 11, C_TEXT2, wrap=True)
    conn_lay.addWidget(_scan_result_lbl)

    _shadow(conn_card)
    lay.addWidget(conn_card)

    # 扫描线程持有
    _scan_thread = [None]

    def _do_scan():
        if _scan_thread[0] and _scan_thread[0].isRunning():
            return
        raw = _subnet_input.text().strip()
        subnet = raw if raw else None   # None → 自动检测本机子网
        scan_btn.setEnabled(False)
        scan_btn.setText("扫描中…")
        _scan_result_lbl.setText("正在扫描局域网…")
        t = _ScanThread(subnet)
        t.found.connect(_on_scan_done)
        t.progress.connect(lambda s, total: _scan_result_lbl.setText(
            f"扫描中… {s}/{total}"
        ))
        t.start()
        _scan_thread[0] = t

    def _on_scan_done(hosts: list):
        scan_btn.setEnabled(True)
        scan_btn.setText("扫描局域网")
        if hosts:
            _scan_result_lbl.setText("发现设备：" + "  |  ".join(hosts))
            _ip_input.setText(hosts[0])
        else:
            _scan_result_lbl.setText("未在局域网内发现可达的 SSH 主机")

    scan_btn.clicked.connect(_do_scan)

    # SSH 测试线程持有
    _ssh_thread = [None]

    def _do_ssh_test():
        ip   = _ip_input.text().strip()
        user = _user_input.text().strip() or "seeed"
        pwd  = _pass_input.text()
        if not ip:
            QMessageBox.warning(page, "提示", "请先输入设备 IP 或主机名。")
            return
        ssh_test_btn.setEnabled(False)
        ssh_test_btn.setText("连接中…")
        _conn_status_lbl.setText("● 检测中…")
        _conn_status_lbl.setStyleSheet(
            f"color:{C_TEXT3}; font-size:{_pt(11)}pt; background:transparent;"
        )
        t = _SSHCheckThread(ip, user, pwd)
        t.result.connect(_on_ssh_result)
        t.start()
        _ssh_thread[0] = t

    def _on_ssh_result(ok: bool, err: str):
        ssh_test_btn.setEnabled(True)
        ssh_test_btn.setText("连接")
        ip   = _ip_input.text().strip()
        user = _user_input.text().strip() or "seeed"
        pwd  = _pass_input.text()
        if ok:
            _conn_status_lbl.setText("● 已连通")
            _conn_status_lbl.setStyleSheet(
                f"color:{C_GREEN}; font-size:{_pt(11)}pt; background:transparent; font-weight:700;"
            )
            set_runner(SSHRunner(ip, username=user, password=pwd))
            bus.device_connected.emit({"ip": ip, "name": "Jetson", "model": ""})
        else:
            _conn_status_lbl.setText("● 连接失败")
            _conn_status_lbl.setStyleSheet(
                f"color:{C_RED}; font-size:{_pt(11)}pt; background:transparent; font-weight:700;"
            )
            _conn_status_lbl.setToolTip(err)
            set_runner(None)
            bus.device_disconnected.emit(ip)

    ssh_test_btn.clicked.connect(_do_ssh_test)

    # ─────────────────────────────────────────────────────────────
    # 卡片 C：Jetson 初始化
    # ─────────────────────────────────────────────────────────────
    init_card = _card(12)
    init_lay  = QVBoxLayout(init_card)
    init_lay.setContentsMargins(24, 20, 24, 20)
    init_lay.setSpacing(14)

    init_title_row = QHBoxLayout()
    init_title_row.addWidget(_lbl("🧭 Jetson 初始化", 15, C_TEXT, bold=True))
    init_title_row.addStretch()
    _init_status_lbl = QLabel("等待检测")
    _init_status_lbl.setStyleSheet(
        f"color:{C_TEXT3}; font-size:{_pt(11)}pt; background:transparent;"
    )
    init_title_row.addWidget(_init_status_lbl)
    init_lay.addLayout(init_title_row)

    init_lay.addWidget(_lbl(
        "刷写完成后，可先通过串口进入首次开机向导，完成用户名、密码、时区和网络配置，再继续 SSH 或远程开发。",
        11, C_TEXT3, wrap=True
    ))

    _init_ports_lbl = _lbl("", 11, C_TEXT2, wrap=True)
    _init_hint_lbl = _lbl("", 10, C_TEXT3, wrap=True)
    init_lay.addWidget(_init_ports_lbl)
    init_lay.addWidget(_init_hint_lbl)

    init_btn_row = QHBoxLayout()
    init_btn_row.setSpacing(10)
    init_refresh_btn = _btn("刷新串口", small=True)
    init_open_btn = _btn("打开初始化面板", primary=True, small=True)
    init_net_btn  = _btn("配置网络 IP", small=True)
    init_btn_row.addWidget(init_refresh_btn)
    init_btn_row.addWidget(init_open_btn)
    init_btn_row.addWidget(init_net_btn)
    init_btn_row.addStretch()
    init_lay.addLayout(init_btn_row)

    def _refresh_init_summary():
        ports = list_serial_ports()
        if ports:
            preview = " / ".join(ports[:3])
            suffix = " ..." if len(ports) > 3 else ""
            _init_status_lbl.setText("● 已发现串口")
            _init_status_lbl.setStyleSheet(
                f"color:{C_GREEN}; font-size:{_pt(11)}pt; background:transparent; font-weight:700;"
            )
            _init_ports_lbl.setText(f"当前检测到 {len(ports)} 个串口设备：{preview}{suffix}")
            _init_hint_lbl.setText(f"推荐先从 {ports[0]} 打开初始化面板，检测当前是否仍处于首次启动配置。")
        else:
            _init_status_lbl.setText("● 未发现串口")
            _init_status_lbl.setStyleSheet(
                f"color:{C_ORANGE}; font-size:{_pt(11)}pt; background:transparent; font-weight:700;"
            )
            _init_ports_lbl.setText("当前未检测到 /dev/ttyACM* 或 /dev/ttyUSB* 设备。")
            _init_hint_lbl.setText("连接 Jetson 串口线并重新上电后，可在这里直接进入初始化面板。")

    init_refresh_btn.clicked.connect(_refresh_init_summary)
    init_open_btn.clicked.connect(lambda: open_jetson_init_dialog(parent=page))
    init_net_btn.clicked.connect(lambda: open_jetson_net_config_dialog(parent=page))

    _shadow(init_card)
    lay.addWidget(init_card)
    _refresh_init_summary()

    # ─────────────────────────────────────────────────────────────
    # 卡片 D：开发工具
    # ─────────────────────────────────────────────────────────────
    tools_card = _card(12)
    tools_lay  = QVBoxLayout(tools_card)
    tools_lay.setContentsMargins(24, 20, 24, 20)
    tools_lay.setSpacing(14)
    tools_lay.addWidget(_lbl("🛠 开发工具", 15, C_TEXT, bold=True))

    tool_defs = [
        (
            "🔵",
            "VS Code Remote SSH",
            "通过 SSH 远程连接，在本机 VS Code 中编辑 Jetson 代码",
            "ℹ  需要本机安装 VS Code + Remote SSH 插件",
            "打开配置",
            "vscode_ssh",
        ),
        (
            "🌐",
            "VS Code Server (Web)",
            "在 Jetson 上运行 code-server，浏览器直接访问开发环境",
            "ℹ  需要先连接设备，点击「部署」自动安装并启动",
            "部署",
            "vscode_web",
        ),
        (
            "🤖",
            "Claude / AI 辅助",
            "接入 Claude API，在远程开发中获得 AI 代码辅助",
            "ℹ  需要配置 Anthropic API Key，点击「测试连接」验证",
            "测试连接",
            "claude_api",
        ),
        (
            "📓",
            "Jupyter Lab",
            "在 Jetson 上运行 Jupyter，浏览器访问交互式开发",
            "ℹ  需要先连接设备，点击「启动」自动安装并启动",
            "启动",
            "jupyter",
        ),
    ]

    # API 测试线程持有
    _api_test_thread = [None]

    def _make_tool_row(icon, name, desc, note, action_text, tool_id):
        row = _input_card(10)
        row.setStyleSheet(f"""
            background: {C_CARD_LIGHT};
            border: none;
            border-radius: 10px;
        """)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(16, 14, 16, 14)
        rl.setSpacing(16)

        ic = QLabel(icon)
        ic.setStyleSheet(f"font-size:{_pt(24)}pt; background:transparent;")
        ic.setFixedWidth(_pt(40))
        rl.addWidget(ic)

        info = QVBoxLayout()
        info.setSpacing(4)
        info.addWidget(_lbl(name, 13, C_TEXT, bold=True))
        info.addWidget(_lbl(desc, 11, C_TEXT2))
        info.addWidget(_lbl(note, 10, C_TEXT3))
        rl.addLayout(info, 1)

        act_btn = _btn(action_text, primary=True, small=True)

        def _on_click(checked=False, tid=tool_id, btn=act_btn):
            ip = _ip_input.text().strip()
            runner = get_runner()
            if tid == "vscode_ssh":
                dlg = _VscodeSSHDialog(ip=ip, parent=page)
                dlg.exec_()
            elif tid == "vscode_web":
                if not isinstance(runner, SSHRunner):
                    QMessageBox.warning(page, "提示", "请先在「设备连接」中连接 Jetson 设备。")
                    return
                dlg = _VscodeWebDialog(runner=runner, ip=runner.host, parent=page)
                dlg.exec_()
            elif tid == "claude_api":
                cfg = _cfg.load()
                key = cfg.get("anthropic_api_key", "")
                if not key:
                    QMessageBox.warning(page, "提示", "请先点击「配置 / 修改」配置 API Key。")
                    return
                base_url = cfg.get("anthropic_base_url", "")
                btn.setEnabled(False)
                btn.setText("测试中…")
                t = _ApiTestThread(key, base_url)
                def _on_api_result(ok, msg, b=btn):
                    b.setEnabled(True)
                    b.setText("测试连接")
                    if ok:
                        QMessageBox.information(page, "API 测试", msg)
                    else:
                        QMessageBox.critical(page, "API 测试失败", msg)
                t.result.connect(_on_api_result)
                t.start()
                _api_test_thread[0] = t
            elif tid == "jupyter":
                if not isinstance(runner, SSHRunner):
                    QMessageBox.warning(page, "提示", "请先在「设备连接」中连接 Jetson 设备。")
                    return
                dlg = _JupyterLaunchDialog(runner=runner, ip=runner.host, parent=page)
                dlg.exec_()

        act_btn.clicked.connect(_on_click)
        rl.addWidget(act_btn)
        return row

    for icon, name, desc, note, action_text, tool_id in tool_defs:
        tools_lay.addWidget(_make_tool_row(icon, name, desc, note, action_text, tool_id))

    _shadow(tools_card)
    lay.addWidget(tools_card)

    lay.addStretch()
    scroll.setWidget(inner)
    root.addWidget(scroll, 1)
    return page
