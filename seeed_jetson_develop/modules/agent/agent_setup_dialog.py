"""Local PC agent CLI setup dialog — detect and install Claude Code / Codex."""
from __future__ import annotations

import shutil
import subprocess

from qtpy.QtCore import Qt, QThread, Signal
from qtpy.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QVBoxLayout,
)

from seeed_jetson_develop.core.config import get_npm_registry
from seeed_jetson_develop.gui.i18n import get_language, t as _t_raw
from seeed_jetson_develop.gui.theme import (
    C_CARD, C_GREEN, C_ORANGE, C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, make_log_view,
    StatusBadge,
)
from seeed_jetson_develop.gui.widgets.toast_notification import Toast
from seeed_jetson_develop.modules.agent.cli_tools import (
    AGENT_INFO, SUPPORTED_AGENTS, detect_local_agents, node_version,
    npm_package,
)


def _t(key: str, **kwargs) -> str:
    return _t_raw(key, lang=get_language(), **kwargs)


class _DetectThread(QThread):
    result = Signal(dict, object)  # agents status, node version|None

    def run(self):
        self.result.emit(detect_local_agents(), node_version())


class _NpmInstallThread(QThread):
    log = Signal(str)
    done = Signal(str, bool)  # agent, success

    def __init__(self, agent: str):
        super().__init__()
        self._agent = agent
        self._proc = None

    def run(self):
        npm = shutil.which("npm")
        if not npm:
            self.log.emit("✗ npm not found\n")
            self.done.emit(self._agent, False)
            return
        pkg = npm_package(self._agent)
        self.log.emit(f"$ npm install -g {pkg}\n")
        try:
            import os
            env = os.environ.copy()
            env["NPM_CONFIG_REGISTRY"] = get_npm_registry()
            self._proc = subprocess.Popen(
                [npm, "install", "-g", pkg],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True,
                encoding="utf-8", errors="replace", env=env,
            )
            for line in self._proc.stdout:
                self.log.emit(line.rstrip("\n"))
            self._proc.wait(timeout=600)
            ok = self._proc.returncode == 0
            self.log.emit(("✓ " if ok else "✗ ") + pkg + "\n")
            self.done.emit(self._agent, ok)
        except Exception as exc:
            self.log.emit(f"✗ {exc}\n")
            self.done.emit(self._agent, False)


class LocalAgentSetupDialog(QDialog):
    """Detect local claude/codex CLIs and install the missing ones via npm."""

    def __init__(self, parent=None, only_agents: list | None = None):
        super().__init__(parent)
        self._agents = list(only_agents) if only_agents else list(SUPPORTED_AGENTS)
        self._detect_thread = None
        self._install_threads: list = []
        self._rows: dict[str, dict] = {}
        self._node_ok = False
        self.setWindowTitle(_t("agent.setup.title"))
        self.setMinimumSize(560, 420)
        self.setStyleSheet(f"background:{C_CARD};")
        self._build_ui()
        self.refresh()

    # ── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(_pt(20), _pt(18), _pt(20), _pt(18))
        lay.setSpacing(_pt(12))

        lay.addWidget(_lbl(_t("agent.setup.title"), 15, C_TEXT, bold=True))
        lay.addWidget(_lbl(_t("agent.setup.subtitle"), 11, C_TEXT3, wrap=True))

        # Node.js status row
        node_card = _card(10, with_shadow=False)
        nl = QHBoxLayout(node_card)
        nl.setContentsMargins(_pt(14), _pt(10), _pt(14), _pt(10))
        nl.addWidget(_lbl("Node.js", 13, C_TEXT, bold=True))
        nl.addStretch()
        self._node_badge = StatusBadge(_t("agent.setup.checking"), "default")
        nl.addWidget(self._node_badge)
        lay.addWidget(node_card)

        # Node missing guidance (hidden by default)
        self._node_guide = _card(10, with_shadow=False)
        gl = QVBoxLayout(self._node_guide)
        gl.setContentsMargins(_pt(14), _pt(10), _pt(14), _pt(10))
        gl.setSpacing(_pt(6))
        gl.addWidget(_lbl(_t("agent.setup.node_missing"), 12, C_ORANGE, bold=True, wrap=True))
        self._node_cmd_lbl = _lbl(_t("agent.setup.node_install_cmd"), 11, C_TEXT2, wrap=True)
        gl.addWidget(self._node_cmd_lbl)
        self._node_guide.hide()
        lay.addWidget(self._node_guide)

        # Agent rows
        for agent in self._agents:
            info = AGENT_INFO[agent]
            card = _card(10, with_shadow=False)
            row = QHBoxLayout(card)
            row.setContentsMargins(_pt(14), _pt(10), _pt(14), _pt(10))
            row.setSpacing(_pt(10))
            row.addWidget(_lbl(f"{info['icon']} {info['name']}", 13, C_TEXT, bold=True))
            row.addStretch()
            badge = StatusBadge(_t("agent.setup.checking"), "default")
            row.addWidget(badge)
            btn = _btn(_t("agent.setup.install"), small=True)
            btn.setEnabled(False)
            btn.clicked.connect(lambda _=False, a=agent: self._install(a))
            row.addWidget(btn)
            lay.addWidget(card)
            self._rows[agent] = {"badge": badge, "btn": btn}

        # Log view
        self._log = make_log_view(read_only=True, min_height=120)
        lay.addWidget(self._log, 1)

        # Bottom buttons
        btns = QHBoxLayout()
        self._btn_refresh = _btn(_t("agent.setup.refresh"))
        self._btn_refresh.clicked.connect(self.refresh)
        self._btn_close = _btn(_t("agent.setup.close"), primary=True)
        self._btn_close.clicked.connect(self.accept)
        btns.addWidget(self._btn_refresh)
        btns.addStretch()
        btns.addWidget(self._btn_close)
        lay.addLayout(btns)

    # ── logic ────────────────────────────────────────────────────────────

    def refresh(self):
        self._btn_refresh.setEnabled(False)
        for row in self._rows.values():
            row["badge"].set_status("default", _t("agent.setup.checking"))
            row["btn"].setEnabled(False)
        self._node_badge.set_status("default", _t("agent.setup.checking"))
        self._detect_thread = _DetectThread()
        self._detect_thread.result.connect(self._on_detected)
        self._detect_thread.start()

    def _on_detected(self, agents: dict, node_ver):
        self._btn_refresh.setEnabled(True)
        self._node_ok = bool(node_ver)
        if node_ver:
            self._node_badge.set_status("ok", node_ver)
            self._node_guide.hide()
        else:
            self._node_badge.set_status("error", _t("agent.setup.not_installed"))
            self._node_guide.show()
        for agent, row in self._rows.items():
            st = agents.get(agent, {})
            if st.get("installed"):
                row["badge"].set_status("ok", st.get("version") or _t("agent.setup.installed"))
                row["btn"].setEnabled(False)
                row["btn"].setText(_t("agent.setup.installed"))
            else:
                row["badge"].set_status("warn", _t("agent.setup.not_installed"))
                row["btn"].setText(_t("agent.setup.install"))
                row["btn"].setEnabled(self._node_ok)

    def _install(self, agent: str):
        row = self._rows[agent]
        row["btn"].setEnabled(False)
        th = _NpmInstallThread(agent)
        th.log.connect(self._log.append)
        th.done.connect(self._on_install_done)
        self._install_threads.append(th)
        th.start()

    def _on_install_done(self, agent: str, ok: bool):
        if ok:
            Toast.success(self, _t("agent.setup.install_ok",
                                   name=AGENT_INFO[agent]["name"]))
        else:
            Toast.error(self, _t("agent.setup.install_fail",
                                 name=AGENT_INFO[agent]["name"]))
        self.refresh()
