"""Agent page — drive Jetson / Physical AI development with local Claude/Codex CLI.

The page reuses the local PC's `claude` / `codex` CLI as the agent backend
and provides the chat interaction inside DevelopTool. Quick scenario cards
seed prompts for Physical AI workflows (camera, radar/lidar, robot arm).
"""
from __future__ import annotations

import logging
import os
import json
import shutil
import sys
from pathlib import Path

from qtpy.QtCore import Qt, QThread, Signal, QTimer
from qtpy.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QApplication, QGridLayout, QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

from seeed_jetson_develop.core.events import bus
from seeed_jetson_develop.core.runner import SSHRunner, get_runner
from seeed_jetson_develop.gui.i18n import get_language, t as _t_raw
from seeed_jetson_develop.gui.i18n_binding import I18nBinding
from seeed_jetson_develop.gui.theme import (
    C_BG_DEEP, C_CARD, C_CARD_LIGHT, C_GREEN, C_ORANGE, C_TEXT, C_TEXT2,
    C_TEXT3, build_mono_font,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, make_input_field, make_section_header,
    set_emoji_font_for_label, StatusBadge,
)
from seeed_jetson_develop.gui.widgets.empty_state_widget import EmptyStateWidget
from seeed_jetson_develop.gui.widgets.page_base import PageBase
from seeed_jetson_develop.gui.widgets.toast_notification import Toast
from seeed_jetson_develop.modules.agent.backend import AgentCliSession
from seeed_jetson_develop.modules.agent.cli_tools import (
    AGENT_INFO, SUPPORTED_AGENTS, detect_local_agents, find_cli,
)
from .device_bridge import DeviceBridge, device_target
from .task_context import ICONS, PRESETS, match_task, resolve_skills, shell_command
from .visual_panel import VisualPanel

log = logging.getLogger("seeed.agent.page")


def _t(key: str, **kwargs) -> str:
    return _t_raw(key, lang=get_language(), **kwargs)


_SCENARIO_KEYS = PRESETS
_SCENARIO_ICONS = ICONS


class _DetectThread(QThread):
    result = Signal(dict)

    def run(self):
        self.result.emit(detect_local_agents())


class _MsgBubble(QFrame):
    """Chat message bubble (user / agent)."""

    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        bg = "rgba(122,179,23,0.12)" if is_user else C_CARD
        color = C_TEXT if is_user else C_TEXT2
        self.setStyleSheet(
            f"QFrame {{ background:{bg}; border-radius:{_pt(10)}px; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(_pt(12), _pt(8), _pt(12), _pt(8))
        self._lbl = _lbl(text, 13, color, wrap=True)
        self._lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self._lbl)

    def append_text(self, text: str):
        self._lbl.setText(self._lbl.text() + text)

    def set_text(self, text: str):
        self._lbl.setText(text)


class _ToolBubble(QFrame):
    """Tool execution bubble: orange header + mono output block."""

    def __init__(self, title: str, output: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background:{C_CARD}; border-radius:{_pt(10)}px; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(_pt(12), _pt(8), _pt(12), _pt(8))
        lay.setSpacing(_pt(6))
        lay.addWidget(_lbl(f"⚡ {title}", 11, C_ORANGE, wrap=True))
        out = QLabel(output or _t("agent.chat.no_output"))
        out.setFont(build_mono_font(_pt(11)))
        out.setStyleSheet(
            f"color:{C_TEXT3}; background:rgba(0,0,0,0.25);"
            f" border-radius:{_pt(6)}px; padding:{_pt(6)}px;"
        )
        out.setWordWrap(True)
        lines = (output or "").splitlines()
        if len(lines) > 20:
            out.setText("\n".join(lines[:20]) + f"\n… ({len(lines)} lines)")
        lay.addWidget(out)


class _ThinkBubble(QFrame):
    """Reasoning / thinking-chain bubble: dim, compact."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background:{C_CARD_LIGHT}; border-radius:{_pt(10)}px; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(_pt(12), _pt(6), _pt(12), _pt(8))
        lay.setSpacing(_pt(4))
        lay.addWidget(_lbl(_t("agent.chat.thinking"), 11, C_TEXT3))
        body = _lbl(text, 12, C_TEXT3, wrap=True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(body)


class AgentPage(PageBase):
    """Chat page that drives a local claude/codex CLI for Jetson development."""

    runtime_event = Signal(str, dict)

    def __init__(self):
        self._agent = SUPPORTED_AGENTS[0]
        self._agent_status: dict = {}
        self._session: AgentCliSession | None = None
        self._has_session = False
        self._cur_bubble: _MsgBubble | None = None
        self._msg_count = 0
        self._bridge = None
        self._preset = "free"
        self._preset_prompt = ""
        self._fingerprint = None
        self._resume_id = ""
        self._device_identity = device_target()
        super().__init__(title=_t("agent.page.title"),
                         subtitle=_t("agent.page.subtitle"))
        self._build_header_controls()
        self._subtitle_label.setWordWrap(False)
        self._subtitle_label.setMaximumWidth(_pt(280))
        self._build_content()
        self._connect_bus()
        self.runtime_event.connect(self._on_runtime_event)
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        QTimer.singleShot(0, self._refresh_agent_status)

    # ── header controls ──────────────────────────────────────────────────

    def _build_header_controls(self):
        # Agent switch (tab-style buttons)
        self._agent_btns: dict[str, QPushButton] = {}
        self._agent_bar = QWidget()
        bar = QHBoxLayout(self._agent_bar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(_pt(4))
        from seeed_jetson_develop.gui.theme import make_tab_button
        for agent in SUPPORTED_AGENTS:
            info = AGENT_INFO[agent]
            b = make_tab_button(f"{info['icon']} {info['name'].split()[0]}",
                                active=(agent == self._agent))
            b.clicked.connect(lambda _=False, a=agent: self._switch_agent(a))
            bar.addWidget(b)
            self._agent_btns[agent] = b
        self.add_header_widget(self._agent_bar)

        self._agent_badge = StatusBadge("", "default")
        self._agent_badge.setMaximumWidth(_pt(130))
        self.add_header_widget(self._agent_badge)

        self._setup_btn = _btn(_t("agent.page.setup"), small=True)
        self._setup_btn.clicked.connect(self._open_setup)
        self.add_header_widget(self._setup_btn)

        self._jetson_badge = StatusBadge("", "default")
        self._jetson_badge.setMaximumWidth(_pt(150))
        self.add_header_widget(self._jetson_badge)
        self._update_jetson_badge()

    # ── content ──────────────────────────────────────────────────────────

    def _build_content(self):
        lay = self.get_content_layout()

        # Scenario cards
        self._scenario_header = make_section_header(_t("agent.scenario.header"))
        self._scenario_header.setToolTip(_t("agent.scenario.subheader"))
        lay.addWidget(self._scenario_header)
        cards_row = QGridLayout()
        cards_row.setSpacing(_pt(12))
        self._scenario_widgets = []
        for index, key in enumerate(_SCENARIO_KEYS):
            button = self._make_scenario_card(key)
            cards_row.addWidget(button, index // 4, index % 4)
            self._scenario_widgets.append(button)
        lay.addLayout(cards_row)

        # Workspace + options row
        opts_card = _card(12, with_shadow=False)
        opts = QHBoxLayout(opts_card)
        opts.setContentsMargins(_pt(14), _pt(10), _pt(14), _pt(10))
        opts.setSpacing(_pt(10))
        self._workspace_lbl = _lbl(_t("agent.workspace.label"), 12, C_TEXT2)
        opts.addWidget(self._workspace_lbl)
        self._workspace_edit = make_input_field(
            _t("agent.workspace.placeholder"))
        self._workspace_edit.setText(str(Path.home() / "seeed-agent-workspace"))
        opts.addWidget(self._workspace_edit, 1)
        self._browse_btn = _btn(_t("agent.workspace.browse"), small=True)
        self._browse_btn.clicked.connect(self._browse_workspace)
        opts.addWidget(self._browse_btn)
        self._full_access_cb = QCheckBox(_t("agent.option.full_access"))
        self._full_access_cb.setChecked(True)
        self._full_access_cb.setToolTip(_t("agent.option.full_access_tip"))
        opts.addWidget(self._full_access_cb)
        lay.addWidget(opts_card)

        self._route_badge = StatusBadge(_t("agent.preset.ready"), "info")
        lay.addWidget(self._route_badge)

        # Chat area
        self._chat_header = make_section_header(_t("agent.chat.header"))

        self._workbench = QSplitter(Qt.Horizontal)
        conversation = QWidget()
        conversation_lay = QVBoxLayout(conversation)
        conversation_lay.setContentsMargins(0, 0, 0, 0)
        conversation_lay.setSpacing(_pt(12))
        self._workbench.addWidget(conversation)
        self._visual = VisualPanel()
        self._workbench.addWidget(self._visual)
        self._workbench.setChildrenCollapsible(False)
        self._workbench.setStretchFactor(0, 3)
        self._workbench.setStretchFactor(1, 2)
        lay.addWidget(self._workbench, 1)

        chat_card = _card(12, with_shadow=False)
        chat_lay = QVBoxLayout(chat_card)
        chat_lay.setContentsMargins(_pt(10), _pt(10), _pt(10), _pt(10))
        chat_lay.addWidget(self._chat_header)
        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setMinimumHeight(_pt(180))
        self._chat_scroll.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }")
        self._chat_host = QWidget()
        self._chat_host.setStyleSheet("background:transparent;")
        self._chat_layout = QVBoxLayout(self._chat_host)
        self._chat_layout.setContentsMargins(_pt(6), _pt(6), _pt(6), _pt(6))
        self._chat_layout.setSpacing(_pt(10))
        self._chat_layout.addStretch(1)
        self._chat_scroll.setWidget(self._chat_host)
        chat_lay.addWidget(self._chat_scroll)

        self._empty_state = EmptyStateWidget(
            title=_t("agent.chat.empty_title"),
            subtitle=_t("agent.chat.empty_subtitle"),
            icon_type="search",
        )
        self._empty_state.layout().setContentsMargins(_pt(12), _pt(12), _pt(12), _pt(12))
        self._empty_state._canvas.setFixedSize(_pt(80), _pt(64))
        self._chat_layout.insertWidget(0, self._empty_state)
        conversation_lay.addWidget(chat_card, 1)

        # Input row
        input_card = _card(12, with_shadow=False)
        il = QHBoxLayout(input_card)
        il.setContentsMargins(_pt(12), _pt(8), _pt(12), _pt(8))
        il.setSpacing(_pt(10))
        self._input = make_input_field(_t("agent.input.placeholder"))
        from seeed_jetson_develop.gui.theme import input_qss as _input_qss
        self._input.setStyleSheet(_input_qss(font_size=13))
        self._input.returnPressed.connect(self._send)
        il.addWidget(self._input, 1)
        self._send_btn = _btn(_t("agent.btn.send"), primary=True)
        self._send_btn.clicked.connect(self._send)
        il.addWidget(self._send_btn)
        self._stop_btn = _btn(_t("agent.btn.stop"), danger=True)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        il.addWidget(self._stop_btn)
        conversation_lay.addWidget(input_card)

    def _make_scenario_card(self, key: str):
        button = _btn(f"{_SCENARIO_ICONS[key]} " + _t(f"agent.scenario.{key}.title"), small=True)
        button.setToolTip(_t(f"agent.scenario.{key}.desc"))
        button.clicked.connect(lambda _=False, k=key: self._apply_scenario(k))
        return button

    # ── bus / status ─────────────────────────────────────────────────────

    def _connect_bus(self):
        try:
            bus.device_connected.connect(self._on_device_event)
            bus.device_disconnected.connect(self._on_device_event)
        except Exception:
            pass

    def _on_device_event(self, *_args):
        identity = device_target()
        if identity != self._device_identity or not isinstance(get_runner(), SSHRunner):
            self._stop()
            self._has_session = False
            self._resume_id = ""
            if self._bridge is not None:
                self._bridge.close()
                self._bridge = None
            self._visual.reset_device()
        self._device_identity = identity
        self._update_jetson_badge()

    def _update_jetson_badge(self):
        runner = get_runner()
        if isinstance(runner, SSHRunner):
            host = getattr(runner, "host", "") or ""
            self._jetson_badge.set_status(
                "ok", _t("agent.badge.jetson_ok", host=host))
        else:
            self._jetson_badge.set_status("warn", _t("agent.badge.jetson_none"))

    def _refresh_agent_status(self):
        if getattr(self, "_detect_thread", None) is not None \
                and self._detect_thread.isRunning():
            return
        self._detect_thread = _DetectThread()
        self._detect_thread.result.connect(self._on_agent_status)
        self._detect_thread.start()

    def _on_agent_status(self, status: dict):
        self._agent_status = status
        st = status.get(self._agent, {})
        if st.get("installed"):
            self._agent_badge.set_status(
                "ok", st.get("version") or _t("agent.setup.installed"))
        else:
            self._agent_badge.set_status("error", _t("agent.setup.not_installed"))
            Toast.warning(self, _t("agent.msg.agent_missing",
                                   name=AGENT_INFO[self._agent]["name"]))

    def _switch_agent(self, agent: str):
        if agent == self._agent or self._session is not None:
            return
        self._agent = agent
        self._has_session = False
        self._resume_id = ""
        for a, b in self._agent_btns.items():
            b.setActive(a == agent) if hasattr(b, "setActive") else None
        st = self._agent_status.get(agent, {})
        if st:
            self._on_agent_status(self._agent_status)

    # ── scenario / workspace ─────────────────────────────────────────────

    def _apply_scenario(self, key: str):
        self._preset = key
        self._preset_prompt = _t(f"agent.scenario.{key}.prompt")
        self._input.setText(self._preset_prompt)
        self._input.setFocus()
        self._show_route(key)

    def _show_route(self, key):
        skills = resolve_skills(self._agent, key)
        names = ", ".join(path.parent.name for path in skills)
        self._route_badge.set_status("info", _t("agent.preset.matched", skills=names))
        self._route_badge.setToolTip("\n".join(str(path) for path in skills))

    def _on_runtime_event(self, action: str, payload: dict):
        if payload.get("target") != device_target() or not isinstance(get_runner(), SSHRunner):
            return
        if action == "publish":
            self._visual.publish(payload["values"], payload["source"])
        elif action in ("camera", "monitor"):
            self._visual.control(action, payload)
        elif action == "network":
            bus.network_share_requested.emit(device_target()["host"])

    def _browse_workspace(self):
        d = QFileDialog.getExistingDirectory(
            self, _t("agent.workspace.browse"),
            self._workspace_edit.text() or str(Path.home()))
        if d:
            self._workspace_edit.setText(d)
            self._has_session = False

    # ── inject API (called by FloatingAIAssistant; signature-compatible) ──

    def inject_context(self, skill_name: str, skill_desc: str, commands: list):
        preview = "\n".join((commands or [])[:6])
        cmds_text = _t("ai_chat.inject.skill_cmds", preview=preview) if preview else ""
        self._prefill(_t("ai_chat.inject.skill",
                         name=skill_name, desc=skill_desc, cmds=cmds_text))

    def inject_topic(self, title: str, summary: str, details=None):
        detail_text = ""
        if details:
            preview = details if isinstance(details, str) else "\n".join(
                [str(d) for d in details][:6])
            detail_text = _t("ai_chat.inject.topic_detail", preview=preview)
        self._prefill(_t("ai_chat.inject.topic",
                         title=title, summary=summary, detail=detail_text))

    def inject_error(self, title: str, log_text: str):
        snippet = (log_text or "")[-1500:]
        self._prefill(_t("ai_chat.inject.error", title=title, snippet=snippet))

    def _prefill(self, text: str):
        self._preset = match_task(text)
        self._preset_prompt = ""
        self._input.setText(text)
        self._input.setFocus()
        self._show_route(self._preset)

    # ── chat ─────────────────────────────────────────────────────────────

    def _add_bubble(self, text: str, is_user: bool) -> _MsgBubble:
        self._empty_state.hide()
        bubble = _MsgBubble(text, is_user)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if is_user:
            row.addStretch(1)
            row.addWidget(bubble, 4)
        else:
            row.addWidget(bubble, 4)
            row.addStretch(1)
        self._chat_layout.insertLayout(self._chat_layout.count() - 1, row)
        self._msg_count += 1
        self._scroll_to_bottom()
        return bubble

    def _add_tool_bubble(self, title: str, output: str):
        self._empty_state.hide()
        bubble = _ToolBubble(title, output)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(bubble, 4)
        row.addStretch(1)
        self._chat_layout.insertLayout(self._chat_layout.count() - 1, row)
        self._scroll_to_bottom()

    def _add_think_bubble(self, text: str):
        self._empty_state.hide()
        bubble = _ThinkBubble(text)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(bubble, 4)
        row.addStretch(1)
        self._chat_layout.insertLayout(self._chat_layout.count() - 1, row)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(0, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()))

    # ── send / stop ──────────────────────────────────────────────────────

    def _open_setup(self):
        from seeed_jetson_develop.modules.agent.agent_setup_dialog import (
            LocalAgentSetupDialog,
        )
        dlg = LocalAgentSetupDialog(self)
        dlg.exec_()
        self._refresh_agent_status()

    def _build_first_turn_context(self, task="free") -> str:
        if self._bridge is None or self._bridge.target != device_target():
            if self._bridge is not None:
                self._bridge.close()
            self._bridge = DeviceBridge(self.runtime_event.emit, bus.device_connected.emit)
        self._bridge.allow_commands = self._full_access_cb.isChecked()
        python = (shutil.which("python3") or shutil.which("python")) if getattr(sys, "frozen", False) else sys.executable
        if not python:
            raise ValueError(_t("agent.msg.python_missing"))
        helper = shell_command([python, str(Path(__file__).with_name("bridge_client.py")),
                                "--runtime", str(self._bridge.manifest)])
        skills = resolve_skills(self._agent, task)
        return _t("agent.context.runtime", target=json.dumps(self._bridge.target, ensure_ascii=False),
                  helper=helper, skills="\n".join(str(path) for path in skills), task=task)

    def _send(self):
        prompt = self._input.text().strip()
        if not prompt or self._session is not None:
            return
        if not find_cli(self._agent):
            Toast.warning(self, _t("agent.msg.agent_missing",
                                   name=AGENT_INFO[self._agent]["name"]))
            self._open_setup()
            return
        workspace = os.path.expanduser(self._workspace_edit.text().strip())
        try:
            Path(workspace).mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            Toast.error(self, _t("agent.msg.workspace_error", msg=str(exc)))
            return

        task = self._preset if prompt == self._preset_prompt else match_task(prompt)
        fingerprint = (self._agent, workspace, json.dumps(device_target(), sort_keys=True))
        if fingerprint != self._fingerprint:
            self._has_session = False
            self._resume_id = ""
        self._fingerprint = fingerprint
        try:
            cli_prompt = self._build_first_turn_context(task) + "\n\n" + prompt
        except Exception as exc:
            # _build_first_turn_context 的 ValueError 本身已是本地化文案
            Toast.error(self, str(exc))
            return
        self._show_route(task)

        self._add_bubble(prompt, is_user=True)
        self._cur_bubble = self._add_bubble("", is_user=False)
        self._cur_bubble.set_text(_t("agent.chat.working"))
        self._turn_begun = False
        self._input.clear()
        self._send_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._workspace_edit.setEnabled(False)
        self._browse_btn.setEnabled(False)
        self._full_access_cb.setEnabled(False)
        for button in self._agent_btns.values():
            button.setEnabled(False)

        self._session = AgentCliSession(
            self._agent, cli_prompt, workspace,
            continue_session=self._has_session,
            full_access=self._full_access_cb.isChecked(),
            resume_id=self._resume_id,
            parent=self,
        )
        self._session.token.connect(self._on_token)
        self._session.tool_event.connect(self._on_tool_event)
        self._session.think.connect(self._add_think_bubble)
        self._session.done.connect(self._on_done)
        self._session.error.connect(self._on_error)
        self._session.session_id.connect(self._on_session_id)
        self._session.finished.connect(self._finish_turn)
        self._session.start()

    def _on_session_id(self, session_id):
        self._resume_id = session_id

    def _stop(self):
        if self._session is not None:
            self._session.cancel()
        if self._bridge is not None:
            self._bridge.allow_commands = False

    def _mark_turn_begun(self):
        if not getattr(self, "_turn_begun", True) and self._cur_bubble is not None:
            self._cur_bubble.set_text("")
        self._turn_begun = True

    def _on_token(self, text: str):
        if self._cur_bubble is not None:
            self._mark_turn_begun()
            self._cur_bubble.append_text(text)
            self._scroll_to_bottom()

    def _on_tool_event(self, title: str, output: str):
        self._add_tool_bubble(title, output)

    def _on_done(self, rc: int):
        if rc == 0:
            self._has_session = bool(self._resume_id)
            self._route_badge.set_status("ok", _t("agent.task.completed"))
            Toast.success(self, _t("agent.task.completed"))
            if not getattr(self, "_turn_begun", True) and self._cur_bubble is not None:
                self._cur_bubble.set_text(_t("agent.chat.no_output"))
        elif rc == -1:
            self._route_badge.set_status("warn", _t("agent.task.cancelled"))
            Toast.info(self, _t("agent.task.cancelled"))
            if self._cur_bubble is not None:
                self._mark_turn_begun()
                self._cur_bubble.append_text(_t("agent.chat.cancelled"))
        else:
            self._route_badge.set_status("error", _t("agent.task.failed"))
            Toast.error(self, _t("agent.chat.exit_code", rc=rc))
            if self._cur_bubble is not None and not getattr(self, "_turn_begun", True):
                self._cur_bubble.set_text(_t("agent.chat.exit_code", rc=rc))

    def _on_error(self, msg: str):
        self._route_badge.set_status("error", _t("agent.task.failed"))
        Toast.error(self, _t("agent.chat.error", msg=msg))
        if self._cur_bubble is not None:
            self._cur_bubble.set_text(_t("agent.chat.error", msg=msg))

    def _finish_turn(self):
        if self._session is not None:
            self._session.deleteLater()
            self._session = None
        self._cur_bubble = None
        self._send_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._workspace_edit.setEnabled(True)
        self._browse_btn.setEnabled(True)
        self._full_access_cb.setEnabled(True)
        for button in self._agent_btns.values():
            button.setEnabled(True)
        self._input.setFocus()
        self._scroll_to_bottom()

    def shutdown(self):
        self._stop()
        self._visual.shutdown()
        if self._bridge is not None:
            self._bridge.close()
        if self._session is not None:
            self._session.wait(3000)
        if getattr(self, "_detect_thread", None) is not None:
            self._detect_thread.wait(18000)

    # ── i18n ─────────────────────────────────────────────────────────────

    def retranslate_ui(self, lang: str | None = None):
        def _t(key, **kwargs):
            return _t_raw(key, lang=lang or get_language(), **kwargs)

        super().retranslate_ui(lang)
        self.set_header_text(_t("agent.page.title"), _t("agent.page.subtitle"))
        self._setup_btn.setText(_t("agent.page.setup"))
        self._workspace_lbl.setText(_t("agent.workspace.label"))
        self._browse_btn.setText(_t("agent.workspace.browse"))
        self._full_access_cb.setText(_t("agent.option.full_access"))
        self._full_access_cb.setToolTip(_t("agent.option.full_access_tip"))
        self._input.setPlaceholderText(_t("agent.input.placeholder"))
        self._send_btn.setText(_t("agent.btn.send"))
        self._stop_btn.setText(_t("agent.btn.stop"))
        self._scenario_header.layout().itemAt(0).widget().setText(_t("agent.scenario.header"))
        self._scenario_header.setToolTip(_t("agent.scenario.subheader"))
        self._chat_header.layout().itemAt(0).widget().setText(_t("agent.chat.header"))
        for key, button in zip(
                _SCENARIO_KEYS, self._scenario_widgets):
            button.setText(f"{_SCENARIO_ICONS[key]} " + _t(f"agent.scenario.{key}.title"))
            button.setToolTip(_t(f"agent.scenario.{key}.desc"))
        if self._msg_count == 0:
            self._empty_state.show()
        self._update_jetson_badge()
        self._visual.retranslate_ui(lang)
        self._show_route(self._preset)
        for label in self._empty_state.findChildren(QLabel):
            if label.wordWrap():
                label.setText(_t("agent.chat.empty_subtitle"))
            else:
                label.setText(_t("agent.chat.empty_title"))
