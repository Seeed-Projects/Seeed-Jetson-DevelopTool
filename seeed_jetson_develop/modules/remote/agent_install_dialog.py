"""AI Agent 安装对话框 — 在 Jetson 上安装 Claude Code / Codex / OpenClaw CLI。"""
from __future__ import annotations

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout,
    QMessageBox, QSizePolicy, QTextEdit, QVBoxLayout,
)

from seeed_jetson_develop.core.runner import SSHRunner
from seeed_jetson_develop.gui.theme import (
    C_BG, C_CARD_LIGHT, C_GREEN, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    apply_shadow, make_button, make_card, make_label, pt,
)


# ── Agent 定义 ────────────────────────────────────────────────────────────────

AGENTS = [
    {
        "id": "claude",
        "name": "Claude Code CLI",
        "desc": "Anthropic 官方终端 AI 编程助手",
        "check": "claude --version 2>/dev/null",
        "install": "npm install -g @anthropic-ai/claude-code",
        "icon": "🟣",
    },
    {
        "id": "codex",
        "name": "Codex CLI",
        "desc": "OpenAI 官方终端 AI 编程助手",
        "check": "codex --version 2>/dev/null",
        "install": "npm install -g @openai/codex",
        "icon": "🟢",
    },
    {
        "id": "openclaw",
        "name": "OpenClaw",
        "desc": "开源 AI Agent 框架（原 ClawdBot）",
        "check": "openclaw --version 2>/dev/null",
        "install": "npm install -g openclaw@latest",
        "icon": "🦀",
    },
]

# Node.js 检测 + 安装命令
CHECK_NODE_CMD = "node --version 2>/dev/null"
INSTALL_NODE_TPL = (
    "echo '{pwd}' | sudo -S apt-get update -qq "
    "&& echo '{pwd}' | sudo -S apt-get install -y nodejs npm "
    "&& node --version && npm --version"
)


# ── 后台线程 ──────────────────────────────────────────────────────────────────

class _SshCmdThread(QThread):
    line_out  = pyqtSignal(str)
    finished_ = pyqtSignal(int, str)

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


class _DetectThread(QThread):
    """检测 Node.js 和各 Agent 安装状态。"""
    result = pyqtSignal(dict)  # {node: bool, agents: {id: bool}}

    def __init__(self, runner: SSHRunner):
        super().__init__()
        self._runner = runner

    def run(self):
        rc, out = self._runner.run(CHECK_NODE_CMD, timeout=10)
        node_ok = rc == 0 and out.strip().startswith("v")
        agents = {}
        for a in AGENTS:
            rc2, out2 = self._runner.run(a["check"], timeout=10)
            agents[a["id"]] = rc2 == 0 and bool(out2.strip())
        self.result.emit({"node": node_ok, "agents": agents})


class AgentInstallDialog(QDialog):
    def __init__(self, runner: SSHRunner, parent=None):
        super().__init__(parent)
        self._runner = runner
        self._thread: _SshCmdThread | None = None
        self._detect_thread: _DetectThread | None = None

        self.setWindowTitle("AI Agent 安装")
        self.setMinimumSize(660, 540)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(f"background:{C_CARD}; color:{C_TEXT}; border-radius:12px;")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        root.addWidget(make_label("🤖 AI Agent 安装（Jetson 端）", 16, C_TEXT, bold=True))
        root.addWidget(make_label(
            "通过 SSH 在 Jetson 设备上安装 AI 编程助手 CLI。\n"
            "安装完成后可在 Jetson 终端中直接使用（如 claude、codex、openclaw 命令）。\n"
            "所有 Agent 均需要 Node.js 环境，会自动检测并安装。",
            11, C_TEXT2, wrap=True,
        ))

        # ── Node.js 状态 ──
        node_card = make_card(12)
        apply_shadow(node_card, blur=18, y=4, alpha=60)
        nc = QVBoxLayout(node_card)
        nc.setContentsMargins(18, 14, 18, 14)
        nc.setSpacing(8)
        node_row = QHBoxLayout()
        node_row.addWidget(make_label("📦 Node.js 环境", 13, C_TEXT, bold=True))
        self._node_status = make_label("检测中…", 12, C_TEXT3)
        node_row.addWidget(self._node_status)
        node_row.addStretch()
        nc.addLayout(node_row)
        root.addWidget(node_card)

        # ── Agent 选择卡片 ──
        agent_card = make_card(12)
        apply_shadow(agent_card, blur=18, y=4, alpha=60)
        ac = QVBoxLayout(agent_card)
        ac.setContentsMargins(18, 16, 18, 16)
        ac.setSpacing(12)
        ac.addWidget(make_label("选择要安装的 Agent", 13, C_TEXT, bold=True))

        self._checkboxes: dict[str, QCheckBox] = {}
        self._agent_statuses: dict[str, object] = {}

        for a in AGENTS:
            row = QHBoxLayout()
            row.setSpacing(10)
            cb = QCheckBox(f"{a['icon']}  {a['name']}")
            cb.setChecked(True)
            cb.setStyleSheet(f"QCheckBox {{ color:{C_TEXT}; font-size:{pt(12)}px; }}")
            row.addWidget(cb)
            status = make_label("检测中…", 11, C_TEXT3)
            row.addWidget(status)
            row.addStretch()
            desc = make_label(a["desc"], 10, C_TEXT3)
            row.addWidget(desc)
            ac.addLayout(row)
            self._checkboxes[a["id"]] = cb
            self._agent_statuses[a["id"]] = status

        root.addWidget(agent_card)

        # ── 操作按钮 ──
        op_row = QHBoxLayout()
        op_row.setSpacing(10)
        self._install_btn = make_button("🚀 安装选中的 Agent", primary=True, small=True)
        self._refresh_btn = make_button("刷新状态", small=True)
        op_row.addWidget(self._install_btn)
        op_row.addWidget(self._refresh_btn)
        op_row.addStretch()
        root.addLayout(op_row)

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

        # ── 信号 ──
        self._install_btn.clicked.connect(self._do_install)
        self._refresh_btn.clicked.connect(self._do_detect)

        self._do_detect()

    def _append(self, line: str):
        self._log.append(line)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── 检测 ──────────────────────────────────────────────────────────────────
    def _do_detect(self):
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("检测中…")
        self._node_status.setText("检测中…")
        self._node_status.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}px; background:transparent;")
        for sid, lbl in self._agent_statuses.items():
            lbl.setText("检测中…")
            lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(11)}px; background:transparent;")

        self._detect_thread = _DetectThread(self._runner)
        self._detect_thread.result.connect(self._on_detect)
        self._detect_thread.start()

    def _on_detect(self, s: dict):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("刷新状态")

        if s["node"]:
            self._node_status.setText("● 已安装")
            self._node_status.setStyleSheet(
                f"color:{C_GREEN}; font-size:{pt(12)}px; background:transparent; font-weight:700;")
        else:
            self._node_status.setText("● 未安装（安装时会自动安装）")
            self._node_status.setStyleSheet(
                f"color:{C_ORANGE}; font-size:{pt(12)}px; background:transparent;")

        for a in AGENTS:
            lbl = self._agent_statuses[a["id"]]
            if s["agents"].get(a["id"]):
                lbl.setText("✅ 已安装")
                lbl.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(11)}px; background:transparent;")
                self._checkboxes[a["id"]].setChecked(False)
            else:
                lbl.setText("未安装")
                lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(11)}px; background:transparent;")

    # ── 安装 ──────────────────────────────────────────────────────────────────
    def _do_install(self):
        selected = [a for a in AGENTS if self._checkboxes[a["id"]].isChecked()]
        if not selected:
            QMessageBox.warning(self, "提示", "请至少选择一个 Agent。")
            return

        pwd = self._runner.sudo_password
        escaped = pwd.replace("'", "'\\''")
        cmds: list[tuple[str, int]] = []

        # 先确保 Node.js 已安装
        cmds.append((
            f"node --version 2>/dev/null || "
            f"( echo '{escaped}' | sudo -S apt-get update -qq "
            f"&& echo '{escaped}' | sudo -S apt-get install -y nodejs npm "
            f"&& node --version )",
            180,
        ))

        # 安装选中的 Agent
        for a in selected:
            cmds.append((a["install"], 300))

        self._install_btn.setEnabled(False)
        self._install_btn.setText("🚀 安装中…")
        self._log.clear()
        self._thread = _SshCmdThread(self._runner, cmds)
        self._thread.line_out.connect(self._append)
        self._thread.finished_.connect(self._on_install_done)
        self._thread.start()

    def _on_install_done(self, rc: int, out: str):
        self._install_btn.setEnabled(True)
        self._install_btn.setText("🚀 安装选中的 Agent")
        if rc == 0:
            self._append("\n✅ 安装完成！可在 Jetson 终端中使用已安装的 Agent。")
        else:
            self._append(f"\n❌ 安装失败 (rc={rc})")
            self._append("排查建议：")
            self._append("  • 确认 Jetson 可以联网（npm 需要下载包）")
            self._append("  • 如果 npm 权限不足，可尝试在 Jetson 上手动执行安装命令")
        self._do_detect()


def open_agent_install_dialog(runner: SSHRunner, parent=None):
    """打开 AI Agent 安装对话框。"""
    dlg = AgentInstallDialog(runner, parent)
    dlg.exec_()
