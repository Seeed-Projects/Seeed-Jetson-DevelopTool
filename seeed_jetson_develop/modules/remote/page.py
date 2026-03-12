"""远程开发页 — 无边框大气风格
包含：Claude API Key 配置、局域网扫描、SSH 连接检测、开发工具入口。
"""
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout,
    QScrollArea, QDialog, QTextEdit, QMessageBox,
)

from seeed_jetson_develop.core import config as _cfg
from seeed_jetson_develop.core.events import bus
from seeed_jetson_develop.core.runner import SSHRunner, set_runner
from seeed_jetson_develop.modules.remote import connector
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
    found  = pyqtSignal(list)
    status = pyqtSignal(str)

    def __init__(self, subnet: str = "192.168.1"):
        super().__init__()
        self._subnet = subnet

    def run(self):
        self.status.emit("正在扫描局域网，请稍候…")
        hosts = connector.scan_local_network(self._subnet)
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
        self.setMinimumSize(560, 340)
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

        # 输入行
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

        # 当前状态提示
        existing = _cfg.load().get("anthropic_api_key", "")
        if existing:
            self._key_edit.setPlaceholderText(f"当前: {existing[:12]}••••••")
            status_text = f"✅ 已配置（前缀：{existing[:12]}…）"
            status_color = C_GREEN
        else:
            status_text = "⚠ 尚未配置"
            status_color = C_ORANGE
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
        data = _cfg.load()
        data["anthropic_api_key"] = key
        _cfg.save(data)
        self._status_lbl.setText(f"✅ 已保存（前缀：{key[:12]}…）")
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
            _cfg.save(data)
            self._key_edit.clear()
            self._status_lbl.setText("⚠ 已清除")
            self._status_lbl.setStyleSheet(
                f"color:{C_ORANGE}; font-size:{_pt(11)}pt; background:transparent;"
            )
            self.key_saved.emit()


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
        key = _cfg.load().get("anthropic_api_key", "")
        if key:
            _api_status_lbl.setText("✅ 已配置")
            _api_status_lbl.setStyleSheet(
                f"color:{C_GREEN}; font-size:{_pt(11)}pt; background:transparent; font-weight:700;"
            )
            _api_key_preview.setText(f"API Key: {key[:12]}••••••••")
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
    scan_btn     = _btn("🔍 扫描局域网", small=True)
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
        subnet = _subnet_input.text().strip() or "192.168.1"
        scan_btn.setEnabled(False)
        scan_btn.setText("扫描中…")
        _scan_result_lbl.setText("正在扫描局域网，请稍候…")
        t = _ScanThread(subnet)
        t.found.connect(_on_scan_done)
        t.start()
        _scan_thread[0] = t

    def _on_scan_done(hosts: list):
        scan_btn.setEnabled(True)
        scan_btn.setText("🔍 扫描局域网")
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
    # 卡片 C：开发工具
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
            "ℹ  需要先通过 Skills 安装 code-server",
            "部署说明",
            "vscode_web",
        ),
        (
            "🤖",
            "Claude / AI 辅助",
            "接入 Claude API，在远程开发中获得 AI 代码辅助",
            "ℹ  需要配置 Anthropic API Key",
            "配置 API Key",
            "claude_api",
        ),
        (
            "📓",
            "Jupyter Lab",
            "在 Jetson 上运行 Jupyter，浏览器访问交互式开发",
            "ℹ  需要先安装 Jupyter Lab",
            "使用指南",
            "jupyter",
        ),
    ]

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

        def _on_click(tid=tool_id):
            ip = _ip_input.text().strip()
            if tid == "vscode_ssh":
                dlg = _VscodeSSHDialog(ip=ip, parent=page)
                dlg.exec_()
            elif tid == "vscode_web":
                msg = (
                    "VS Code Server（code-server）部署说明：\n\n"
                    "1. 在 Jetson 上安装 code-server：\n"
                    "   curl -fsSL https://code-server.dev/install.sh | sh\n\n"
                    "2. 启动服务：\n"
                    "   code-server --bind-addr 0.0.0.0:8080\n\n"
                    "3. 在本机浏览器访问：\n"
                    f"   http://{ip or '<设备 IP>'}:8080\n\n"
                    "4. 密码见 ~/.config/code-server/config.yaml"
                )
                QMessageBox.information(page, "VS Code Server 部署说明", msg)
            elif tid == "claude_api":
                _open_api_dialog()
            elif tid == "jupyter":
                dlg = _JupyterDialog(ip=ip, parent=page)
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
