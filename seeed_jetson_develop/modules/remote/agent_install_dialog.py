"""AI agent install dialog for Jetson."""
from __future__ import annotations

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout,
    QSizePolicy, QTextEdit, QVBoxLayout,
)

from seeed_jetson_develop.core.runner import SSHRunner
from seeed_jetson_develop.gui.i18n_binding import I18nBinding
from seeed_jetson_develop.gui.i18n import get_language, t
from seeed_jetson_develop.gui.theme import (
    C_BG, C_CARD_LIGHT, C_GREEN, C_ORANGE,
    C_TEXT, C_TEXT2, C_TEXT3,
    apply_shadow, make_button, make_card, make_label, pt,
    show_warning_message,
)


# Agent definitions

AGENTS = [
    {
        "id": "claude",
        "name": "Claude Code CLI",
        "desc": "Anthropic official terminal AI coding assistant",
        "check": "claude --version 2>/dev/null",
        "install": "npm install -g @anthropic-ai/claude-code",
        "icon": "🟣",
    },
    {
        "id": "codex",
        "name": "Codex CLI",
        "desc": "OpenAI official terminal AI coding assistant",
        "check": "codex --version 2>/dev/null",
        "install": "npm install -g @openai/codex",
        "icon": "🟢",
    },
    {
        "id": "openclaw",
        "name": "OpenClaw",
        "desc": "Open-source AI agent framework (formerly ClawdBot)",
        "check": "openclaw --version 2>/dev/null",
        "install": "npm install -g openclaw@latest",
        "icon": "🦀",
    },
]

CHECK_NODE_CMD = "node --version 2>/dev/null"


# Background threads

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
    """Check Node.js and agent install status."""
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
        self._lang = get_language()
        self._i18n = I18nBinding()

        self.setWindowTitle(t("remote.agent_install.window_title", lang=self._lang))
        self.setMinimumSize(pt(660), pt(540))
        self.setSizeGripEnabled(True)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        self._title_label = make_label("", 16, C_TEXT, bold=True)
        root.addWidget(self._title_label)
        self._desc_label = make_label("", 11, C_TEXT2, wrap=True)
        root.addWidget(self._desc_label)

        # Node.js status
        node_card = make_card(12)
        apply_shadow(node_card, blur=18, y=4, alpha=60)
        nc = QVBoxLayout(node_card)
        nc.setContentsMargins(18, 14, 18, 14)
        nc.setSpacing(8)
        node_row = QHBoxLayout()
        self._node_env_label = make_label("", 13, C_TEXT, bold=True)
        node_row.addWidget(self._node_env_label)
        self._node_status = make_label("", 12, C_TEXT3)
        node_row.addWidget(self._node_status)
        node_row.addStretch()
        nc.addLayout(node_row)
        root.addWidget(node_card)

        # Agent selector
        agent_card = make_card(12)
        apply_shadow(agent_card, blur=18, y=4, alpha=60)
        ac = QVBoxLayout(agent_card)
        ac.setContentsMargins(18, 16, 18, 16)
        ac.setSpacing(12)
        self._select_agents_label = make_label("", 13, C_TEXT, bold=True)
        ac.addWidget(self._select_agents_label)

        self._checkboxes: dict[str, QCheckBox] = {}
        self._agent_statuses: dict[str, object] = {}

        for a in AGENTS:
            row = QHBoxLayout()
            row.setSpacing(10)
            cb = QCheckBox(f"{a['icon']}  {a['name']}")
            cb.setChecked(True)
            cb.setStyleSheet(f"QCheckBox {{ color:{C_TEXT}; font-size:{pt(12)}px; }}")
            row.addWidget(cb)
            status = make_label("", 11, C_TEXT3)
            row.addWidget(status)
            row.addStretch()
            desc = make_label("", 10, C_TEXT3)
            row.addWidget(desc)
            ac.addLayout(row)
            self._checkboxes[a["id"]] = cb
            self._agent_statuses[a["id"]] = status
            a["desc_label"] = desc

        root.addWidget(agent_card)

        # Action buttons
        op_row = QHBoxLayout()
        op_row.setSpacing(10)
        self._install_btn = make_button("", primary=True, small=True)
        self._refresh_btn = make_button("", small=True)
        op_row.addWidget(self._install_btn)
        op_row.addWidget(self._refresh_btn)
        op_row.addStretch()
        root.addLayout(op_row)

        # Log view
        log_card = make_card(12)
        ll = QVBoxLayout(log_card)
        ll.setContentsMargins(18, 14, 18, 14)
        ll.setSpacing(8)
        self._log_title = make_label("", 12, C_TEXT, bold=True)
        ll.addWidget(self._log_title)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(pt(120))
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

        # Close row
        close_row = QHBoxLayout()
        close_row.addStretch()
        self._close_btn = make_button("")
        self._close_btn.clicked.connect(self.accept)
        close_row.addWidget(self._close_btn)
        root.addLayout(close_row)

        # Signals
        self._install_btn.clicked.connect(self._do_install)
        self._refresh_btn.clicked.connect(self._do_detect)

        self._bind_i18n()
        self.retranslate_ui(self._lang)
        self._do_detect()

    def showEvent(self, event):
        super().showEvent(event)
        from PyQt5.QtWidgets import QApplication
        geo = QApplication.primaryScreen().availableGeometry()
        max_w = int(geo.width()  * 0.95)
        max_h = int(geo.height() * 0.92)
        self.setMinimumSize(min(self.minimumWidth(), max_w),
                            min(self.minimumHeight(), max_h))
        w = min(max(self.width(),  self.minimumWidth()),  max_w)
        h = min(max(self.height(), self.minimumHeight()), max_h)
        self.resize(w, h)
        x = geo.x() + (geo.width()  - self.width())  // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    def _tr(self, key: str, **kwargs) -> str:
        return t(key, lang=self._lang, **kwargs)

    def retranslate_ui(self, lang: str | None = None):
        if lang:
            self._lang = lang
        self._i18n.apply(self._lang)

    def _bind_i18n(self):
        self._i18n.bind_callable(lambda: self.setWindowTitle(self._tr("remote.agent_install.window_title")))
        self._i18n.bind_text(self._title_label, "remote.agent_install.title")
        self._i18n.bind_text(self._desc_label, "remote.agent_install.description")
        self._i18n.bind_text(self._node_env_label, "remote.agent_install.node_env")
        self._i18n.bind_text(self._select_agents_label, "remote.agent_install.select_agents")
        self._i18n.bind_text(self._install_btn, "remote.agent_install.install_selected")
        self._i18n.bind_text(self._refresh_btn, "remote.agent_install.refresh_status")
        self._i18n.bind_text(self._log_title, "remote.agent_install.execution_log")
        self._i18n.bind_text(self._close_btn, "common.close")
        for agent in AGENTS:
            self._i18n.bind_text(agent["desc_label"], f"remote.agent_install.agent.{agent['id']}.desc")

    def _append(self, line: str):
        self._log.append(line)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    # Detection
    def _do_detect(self):
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText(self._tr("common.checking"))
        self._node_status.setText(self._tr("common.checking"))
        self._node_status.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}px; background:transparent;")
        for sid, lbl in self._agent_statuses.items():
            lbl.setText(self._tr("common.checking"))
            lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(11)}px; background:transparent;")

        self._detect_thread = _DetectThread(self._runner)
        self._detect_thread.result.connect(self._on_detect)
        self._detect_thread.start()

    def _on_detect(self, s: dict):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText(self._tr("remote.agent_install.refresh_status"))

        if s["node"]:
            self._node_status.setText(self._tr("remote.agent_install.status.installed"))
            self._node_status.setStyleSheet(
                f"color:{C_GREEN}; font-size:{pt(12)}px; background:transparent; font-weight:700;")
        else:
            self._node_status.setText(self._tr("remote.agent_install.status.not_installed_auto"))
            self._node_status.setStyleSheet(
                f"color:{C_ORANGE}; font-size:{pt(12)}px; background:transparent;")

        for a in AGENTS:
            lbl = self._agent_statuses[a["id"]]
            if s["agents"].get(a["id"]):
                lbl.setText(self._tr("remote.agent_install.status.installed_short"))
                lbl.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(11)}px; background:transparent;")
                self._checkboxes[a["id"]].setChecked(False)
            else:
                lbl.setText(self._tr("remote.agent_install.status.not_installed"))
                lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(11)}px; background:transparent;")

    # Install
    def _do_install(self):
        selected = [a for a in AGENTS if self._checkboxes[a["id"]].isChecked()]
        if not selected:
            show_warning_message(
                self,
                self._tr("common.notice"),
                self._tr("remote.agent_install.select_agent_required"),
            )
            return

        pwd = self._runner.sudo_password
        escaped = pwd.replace("'", "'\\''")
        cmds: list[tuple[str, int]] = []

        # Ensure Node.js first
        cmds.append((
            f"node --version 2>/dev/null || "
            f"( echo '{escaped}' | sudo -S apt-get update -qq "
            f"&& echo '{escaped}' | sudo -S apt-get install -y nodejs npm "
            f"&& node --version )",
            180,
        ))

        # Install selected agents
        for a in selected:
            cmds.append((a["install"], 300))

        self._install_btn.setEnabled(False)
        self._install_btn.setText(self._tr("remote.agent_install.installing"))
        self._log.clear()
        self._thread = _SshCmdThread(self._runner, cmds)
        self._thread.line_out.connect(self._append)
        self._thread.finished_.connect(self._on_install_done)
        self._thread.start()

    def _on_install_done(self, rc: int, out: str):
        self._install_btn.setEnabled(True)
        self._install_btn.setText(self._tr("remote.agent_install.install_selected"))
        if rc == 0:
            self._append("\n" + self._tr("remote.agent_install.install_complete"))
        else:
            self._append("\n" + self._tr("remote.agent_install.install_failed", rc=rc))
            self._append(self._tr("remote.agent_install.troubleshooting"))
            self._append(self._tr("remote.agent_install.tip.network"))
            self._append(self._tr("remote.agent_install.tip.permissions"))
        self._do_detect()


def open_agent_install_dialog(runner: SSHRunner, parent=None):
    """Open AI agent install dialog."""
    dlg = AgentInstallDialog(runner, parent)
    dlg.exec_()
