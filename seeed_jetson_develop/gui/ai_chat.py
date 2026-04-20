"""Reusable AI chat panel and floating assistant entry."""

import os
import re

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject, QEvent, QPoint, QRect
from PyQt5.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
)

from seeed_jetson_develop.core.config import (
    DEFAULT_ANTHROPIC_BASE_URL,
    get_runtime_anthropic_settings,
    load as load_config,
    save as save_config,
)
from seeed_jetson_develop.gui.theme import (
    C_BG_DEEP,
    C_CARD,
    C_CARD_LIGHT,
    C_GREEN,
    C_BLUE,
    C_ORANGE,
    C_TEXT,
    C_TEXT2,
    C_TEXT3,
    pt as _pt,
    make_label as _lbl,
    make_button as _btn,
)
from seeed_jetson_develop.gui.i18n import get_language, t as _t_raw


def _t(key: str, **kwargs) -> str:
    """Translate key using current language."""
    return _t_raw(key, lang=get_language(), **kwargs)


# 安全命令黑名单：只拦截真正破坏性的操作
_DANGEROUS_PATTERNS = re.compile(
    r"\brm\s+-[rf]+\s+/|\bdd\b.*of=|\bmkfs\b|>\s*/dev/[sh]d",
    re.IGNORECASE,
)


def _is_safe_cmd(cmd: str) -> bool:
    return not _DANGEROUS_PATTERNS.search(cmd)


def _get_tool_def() -> dict:
    """Build tool definition using current language."""
    return {
        "name": "run_ssh_command",
        "description": _t("ai_chat.tool_def.description"),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": _t("ai_chat.tool_def.cmd_desc"),
                },
                "reason": {
                    "type": "string",
                    "description": _t("ai_chat.tool_def.reason_desc"),
                },
            },
            "required": ["command", "reason"],
        },
    }


def build_ai_system_prompt(limit: int = 30) -> str:
    """Build system prompt in current language, injecting Skills/Apps context."""
    system = _t("ai_chat.system")
    try:
        from seeed_jetson_develop.modules.skills.engine import load_builtin_skills
        skills = load_builtin_skills()
        skills_text = "\n".join(
            f"- {s.name}（{s.category}）：{s.desc}"
            for s in skills[:limit]
        )
        if skills_text:
            system += _t("ai_chat.system.skills_header") + skills_text
    except Exception:
        pass
    try:
        from seeed_jetson_develop.modules.apps.registry import load_apps
        apps = load_apps()
        apps_text = "\n".join(
            f"- {a['name']}（{a['category']}）：{a['desc']}"
            for a in apps[:20]
        )
        if apps_text:
            system += _t("ai_chat.system.apps_header") + apps_text
    except Exception:
        pass
    return system


# Keep _DEFAULT_SYSTEM as a lazy accessor for backwards-compat imports
def _get_default_system() -> str:
    return _t("ai_chat.system")

_DEFAULT_SYSTEM = _get_default_system()


def _get_api_key() -> str:
    return get_runtime_anthropic_settings()["api_key"]


def _get_base_url() -> str:
    return get_runtime_anthropic_settings()["base_url"]


# ── AI 线程（支持 tool_use 循环） ─────────────────────────────────────────────

class _AiToolThread(QThread):
    token       = pyqtSignal(str)       # text token (simulated streaming)
    tool_call   = pyqtSignal(str, str)  # command, reason
    tool_result = pyqtSignal(str, str)  # command, output
    done        = pyqtSignal()
    error       = pyqtSignal(str)

    def __init__(self, messages: list, system: str, api_key: str,
                 base_url: str = "", runner=None, lang: str = "en"):
        super().__init__()
        self._messages = messages
        self._system   = system
        self._api_key  = api_key
        self._base_url = base_url
        self._runner   = runner
        self._cancel   = False
        self._lang     = lang

    def cancel(self):
        self._cancel = True

    def _emit_text(self, text: str):
        """Word-by-word simulated streaming output."""
        words = text.split(" ")
        for i, word in enumerate(words):
            if self._cancel:
                return
            self.token.emit(word if i == len(words) - 1 else word + " ")

    def run(self):
        base_url = self._base_url or DEFAULT_ANTHROPIC_BASE_URL
        no_output = _t_raw("ai_chat.tool.no_output", lang=self._lang)
        rejected  = _t_raw("ai_chat.tool.rejected",  lang=self._lang)
        try:
            import anthropic
            client   = anthropic.Anthropic(api_key=self._api_key, base_url=base_url)
            tool_def = _get_tool_def()
            tools    = [tool_def] if self._runner is not None else []
            messages = list(self._messages)

            while True:
                if self._cancel:
                    return

                resp = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=2048,
                    system=self._system,
                    messages=messages,
                    tools=tools,
                )

                text_parts: list[str] = []
                tool_uses: list = []
                for block in resp.content:
                    if block.type == "text":
                        text_parts.append(block.text)
                    elif block.type == "tool_use":
                        tool_uses.append(block)

                full_text = " ".join(text_parts)
                if full_text:
                    self._emit_text(full_text)

                if resp.stop_reason == "end_turn" or not tool_uses:
                    break

                # ── Execute tool calls ──
                messages.append({"role": "assistant", "content": resp.content})
                tool_results = []
                for tu in tool_uses:
                    if self._cancel:
                        return
                    cmd    = tu.input.get("command", "")
                    reason = tu.input.get("reason", "")
                    self.tool_call.emit(cmd, reason)

                    if _is_safe_cmd(cmd) and self._runner is not None:
                        _, output = self._runner.run(cmd, timeout=300)
                        if not output:
                            output = no_output
                    else:
                        output = rejected

                    self.tool_result.emit(cmd, output)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": output[:4000],
                    })

                messages.append({"role": "user", "content": tool_results})

        except Exception as exc:
            self.error.emit(f"{exc}\n[base_url: {base_url}]")
        finally:
            self.done.emit()


# ── 消息气泡 ──────────────────────────────────────────────────────────────────

class _MsgBubble(QFrame):
    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        bg    = "rgba(122,179,23,0.12)" if is_user else C_CARD
        color = C_TEXT if is_user else C_TEXT2
        self.setStyleSheet(f"background:{bg}; border:none; border-radius:10px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(0)

        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._label.setStyleSheet(
            f"color:{color}; font-size:{_pt(11)}pt; background:transparent; border:none;"
        )
        layout.addWidget(self._label)

    def set_text(self, text: str):
        self._label.setText(text)

    def text(self) -> str:
        return self._label.text()


class _ToolCallBubble(QFrame):
    """Display AI tool call: command + execution result."""

    def __init__(self, cmd: str, reason: str, parent=None):
        super().__init__(parent)
        self._cmd = cmd
        self.setStyleSheet(
            f"background: rgba(255,165,0,0.08); border: 1px solid rgba(255,165,0,0.20);"
            f"border-radius:10px;"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(4)

        # Header row
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        icon = QLabel("⚡")
        icon.setStyleSheet(f"color:{C_ORANGE}; font-size:{_pt(10)}pt; background:transparent;")
        hdr.addWidget(icon)
        hdr.addWidget(_lbl(_t("ai_chat.tool.header", reason=reason), 10, C_ORANGE))
        hdr.addStretch()
        lay.addLayout(hdr)

        # Command line
        cmd_lbl = QLabel(f"$ {cmd}")
        cmd_lbl.setWordWrap(True)
        cmd_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        cmd_lbl.setStyleSheet(
            f"color:{C_TEXT3}; font-size:{_pt(10)}pt; font-family:monospace;"
            f"background:rgba(0,0,0,0.25); border:none; border-radius:4px; padding:4px 8px;"
        )
        lay.addWidget(cmd_lbl)

        # Output area (initially "Running…")
        self._output_lbl = QLabel(_t("ai_chat.tool.running"))
        self._output_lbl.setWordWrap(True)
        self._output_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._output_lbl.setStyleSheet(
            f"color:{C_TEXT2}; font-size:{_pt(10)}pt; font-family:monospace;"
            f"background:transparent; border:none;"
        )
        lay.addWidget(self._output_lbl)

    def set_output(self, output: str):
        lines = output.splitlines()
        preview = "\n".join(lines[:20])
        if len(lines) > 20:
            preview += "\n" + _t("ai_chat.tool.more_lines", total=len(lines))
        self._output_lbl.setText(preview or _t("ai_chat.tool.no_output"))


# ── 聊天面板 ──────────────────────────────────────────────────────────────────

class AIChatPanel(QWidget):
    def __init__(self, system_prompt: str = "", title: str = "AI Bot",
                 runner=None, parent=None):
        super().__init__(parent)
        self._system     = system_prompt or _t("ai_chat.system")
        self._runner     = runner
        self._history    = []
        self._thread     = None
        self._cur_bubble = None
        self._cur_text   = ""
        self._pending_tool_bubble: _ToolCallBubble | None = None
        self._runtime_hint = None
        self._initial_bubble: _MsgBubble | None = None
        self._setup_ui(title)

    def _setup_ui(self, title: str):
        self.setStyleSheet(f"background:{C_BG_DEEP}; border:none;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ── Title bar ──
        title_row = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(8)}pt; background:transparent;")
        title_row.addWidget(dot)
        title_row.addSpacing(6)
        title_row.addWidget(_lbl(title, 13, C_TEXT, bold=True))
        title_row.addStretch()

        # SSH status badge
        self._ssh_badge = QLabel(_t("ai_chat.badge.no_device"))
        self._ssh_badge.setStyleSheet(
            f"color:{C_TEXT3}; font-size:{_pt(9)}pt; background:rgba(255,255,255,0.06);"
            f"border:none; border-radius:6px; padding:2px 8px;"
        )
        title_row.addWidget(self._ssh_badge)
        self._update_ssh_badge()

        has_key = bool(_get_api_key())
        if not has_key:
            key_btn = QPushButton(_t("ai_chat.btn.config_key"))
            key_btn.setCursor(Qt.PointingHandCursor)
            key_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(44,123,229,0.15);
                    border: none;
                    border-radius: 6px;
                    color: {C_BLUE};
                    font-size: {_pt(10)}pt;
                    padding: 3px 8px;
                }}
                QPushButton:hover {{ background: rgba(44,123,229,0.25); }}
            """)
            key_btn.clicked.connect(self._toggle_key_frame)
            title_row.addWidget(key_btn)
        layout.addLayout(title_row)

        self._runtime_hint = _lbl("", 10, C_TEXT3, wrap=True)
        self._runtime_hint.setStyleSheet(
            f"color:{C_TEXT3}; font-size:{_pt(10)}px; background:transparent;"
        )
        layout.addWidget(self._runtime_hint)
        self._update_runtime_hint()

        # ── Message area ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background:transparent; border:none;")

        self._msg_widget = QWidget()
        self._msg_widget.setStyleSheet("background:transparent;")
        self._msg_layout = QVBoxLayout(self._msg_widget)
        self._msg_layout.setContentsMargins(0, 4, 0, 4)
        self._msg_layout.setSpacing(8)
        self._msg_layout.addStretch()
        self._scroll.setWidget(self._msg_widget)
        layout.addWidget(self._scroll, 1)

        # ── API Key config frame ──
        self._key_frame = QFrame()
        self._key_frame.setStyleSheet(f"background:{C_CARD}; border:none; border-radius:8px;")
        key_layout = QHBoxLayout(self._key_frame)
        key_layout.setContentsMargins(10, 6, 10, 6)
        key_layout.setSpacing(8)
        key_layout.addWidget(_lbl(_t("ai_chat.key_label"), 10, C_TEXT3))

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("sk-ant-...")
        self._key_input.setEchoMode(QLineEdit.Password)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background:{C_CARD_LIGHT};
                border:none;
                border-radius:6px;
                padding:4px 10px;
                color:{C_TEXT};
                font-size:{_pt(10)}pt;
            }}
        """)
        self._key_input.setFixedHeight(_pt(30))
        save_btn = _btn(_t("ai_chat.btn.save"), primary=True, small=True)
        save_btn.setFixedWidth(_pt(52))
        save_btn.clicked.connect(self._save_key)
        key_layout.addWidget(self._key_input, 1)
        key_layout.addWidget(save_btn)
        self._key_frame.setVisible(False)
        layout.addWidget(self._key_frame)

        # ── Input box ──
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText(_t("ai_chat.input.placeholder"))
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background:{C_CARD_LIGHT};
                border:none;
                border-radius:8px;
                padding:8px 14px;
                color:{C_TEXT};
                font-size:{_pt(11)}pt;
            }}
            QLineEdit:focus {{ background:{C_CARD}; }}
        """)
        self._input.setFixedHeight(_pt(40))
        self._input.returnPressed.connect(self._on_send)

        self._send_btn = _btn(_t("ai_chat.btn.send"), primary=True, small=True)
        self._send_btn.setMinimumWidth(_pt(52))
        self._send_btn.clicked.connect(self._on_send)

        input_row.addWidget(self._input, 1)
        input_row.addWidget(self._send_btn)
        layout.addLayout(input_row)

        if not has_key:
            self._initial_bubble = self._add_ai_bubble(_t("ai_chat.no_key_prompt"))
        else:
            self._initial_bubble = self._add_ai_bubble(_t("ai_chat.welcome"))

    # ── Public API ───────────────────────────────────────────────────────────

    def set_system(self, prompt: str):
        self._system = prompt

    def set_runner(self, runner):
        self._runner = runner
        self._update_ssh_badge()

    def retranslate_ui(self, _lang=None):
        """Update all UI text to reflect the current language. Called on language switch."""
        self._update_ssh_badge()
        self._update_runtime_hint()
        if hasattr(self, "_input"):
            self._input.setPlaceholderText(_t("ai_chat.input.placeholder"))
        if hasattr(self, "_send_btn"):
            self._send_btn.setText(_t("ai_chat.btn.send"))
        self._refresh_initial_message()

    def _refresh_initial_message(self):
        """Refresh the default first AI bubble when language switches.

        Only applies before user sends messages (history still empty),
        so it won't overwrite real conversation content.
        """
        if self._history:
            return
        if self._initial_bubble is None:
            return
        has_key = bool(_get_api_key())
        self._initial_bubble.set_text(
            _t("ai_chat.welcome") if has_key else _t("ai_chat.no_key_prompt")
        )

    def inject_context(self, skill_name: str, skill_desc: str, commands: list):
        cmds_text = ""
        if commands:
            preview = "\n".join(commands[:8])
            cmds_text = _t("ai_chat.inject.skill_cmds", preview=preview)
        text = _t("ai_chat.inject.skill", name=skill_name, desc=skill_desc, cmds=cmds_text)
        self._add_user_bubble(text)
        self._fire_ai()

    def inject_topic(self, title: str, summary: str, details=None):
        detail_text = ""
        if details:
            preview = "\n".join(details[:8])
            detail_text = _t("ai_chat.inject.topic_detail", preview=preview)
        text = _t("ai_chat.inject.topic", title=title, summary=summary, detail=detail_text)
        self._add_user_bubble(text)
        self._fire_ai()

    def inject_error(self, title: str, log_text: str):
        """Inject execution failure log for AI analysis."""
        snippet = log_text[-3000:].strip()
        text = _t("ai_chat.inject.error", title=title, snippet=snippet)
        self._add_user_bubble(text)
        self._fire_ai()

    # ── Internal methods ─────────────────────────────────────────────────────

    def _update_ssh_badge(self):
        from seeed_jetson_develop.core.runner import SSHRunner
        if isinstance(self._runner, SSHRunner):
            self._ssh_badge.setText(_t("ai_chat.badge.ssh_ok"))
            self._ssh_badge.setStyleSheet(
                f"color:{C_GREEN}; font-size:{_pt(9)}pt;"
                f"background:rgba(141,194,31,0.12);"
                f"border:none; border-radius:6px; padding:2px 8px;"
            )
        else:
            self._ssh_badge.setText(_t("ai_chat.badge.no_device"))
            self._ssh_badge.setStyleSheet(
                f"color:{C_TEXT3}; font-size:{_pt(9)}pt;"
                f"background:rgba(255,255,255,0.06);"
                f"border:none; border-radius:6px; padding:2px 8px;"
            )

    def _update_runtime_hint(self):
        settings = get_runtime_anthropic_settings()
        base_url = settings["base_url"]
        source   = settings["base_url_source"]
        source_label = _t(f"ai_chat.url_source.{source}") if source in ("config", "env", "default") else source
        self._runtime_hint.setText(_t("ai_chat.runtime_hint", url=base_url, source=source_label))

    def _toggle_key_frame(self):
        self._key_frame.setVisible(not self._key_frame.isVisible())

    def _save_key(self):
        key = self._key_input.text().strip()
        if not key:
            return
        cfg = load_config()
        cfg["anthropic_api_key"] = key
        save_config(cfg)
        self._key_frame.setVisible(False)
        self._key_input.clear()
        self._update_runtime_hint()
        self._add_ai_bubble(_t("ai_chat.key_saved"))

    def _on_send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._add_user_bubble(text)
        self._fire_ai()

    def _add_user_bubble(self, text: str):
        self._history.append({"role": "user", "content": text})
        self._insert_bubble(text, is_user=True)

    def _add_ai_bubble(self, text: str = ""):
        return self._insert_bubble(text, is_user=False)

    def _insert_bubble(self, text: str, is_user: bool):
        bubble = _MsgBubble(text, is_user, self._msg_widget)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, bubble)
        QTimer.singleShot(30, self._scroll_to_bottom)
        return bubble

    def _insert_tool_bubble(self, cmd: str, reason: str) -> _ToolCallBubble:
        bubble = _ToolCallBubble(cmd, reason, self._msg_widget)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, bubble)
        QTimer.singleShot(30, self._scroll_to_bottom)
        return bubble

    def _scroll_to_bottom(self):
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _fire_ai(self):
        api_key = _get_api_key()
        if not api_key:
            self._add_ai_bubble(_t("ai_chat.no_key_warn"))
            return
        if self._thread and self._thread.isRunning():
            return

        # Sync global runner before each request
        from seeed_jetson_develop.core.runner import get_runner, SSHRunner
        runner = get_runner()
        if isinstance(runner, SSHRunner):
            self.set_runner(runner)

        self._cur_bubble = self._add_ai_bubble("")
        self._cur_text   = ""
        self._send_btn.setEnabled(False)
        self._input.setEnabled(False)

        self._thread = _AiToolThread(
            messages=list(self._history),
            system=self._system,
            api_key=api_key,
            base_url=_get_base_url(),
            runner=self._runner,
            lang=get_language(),
        )
        self._thread.token.connect(self._on_token)
        self._thread.tool_call.connect(self._on_tool_call)
        self._thread.tool_result.connect(self._on_tool_result)
        self._thread.done.connect(self._on_done)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_token(self, token: str):
        if self._cur_bubble is None:
            self._cur_bubble = self._add_ai_bubble("")
            self._cur_text   = ""
        self._cur_text += token
        self._cur_bubble.set_text(self._cur_text)
        self._scroll_to_bottom()

    def _on_tool_call(self, cmd: str, reason: str):
        if self._cur_text:
            self._history.append({"role": "assistant", "content": self._cur_text})
        self._cur_bubble = None
        self._cur_text   = ""
        self._pending_tool_bubble = self._insert_tool_bubble(cmd, reason)

    def _on_tool_result(self, cmd: str, output: str):
        if self._pending_tool_bubble is not None:
            self._pending_tool_bubble.set_output(output)
            self._pending_tool_bubble = None
        self._scroll_to_bottom()

    def _on_done(self):
        self._send_btn.setEnabled(True)
        self._input.setEnabled(True)
        if self._cur_text:
            self._history.append({"role": "assistant", "content": self._cur_text})
        self._cur_bubble = None
        self._cur_text   = ""

    def _on_error(self, msg: str):
        if self._cur_bubble:
            self._cur_bubble.set_text(_t("ai_chat.request_failed", msg=msg))
        self._send_btn.setEnabled(True)
        self._input.setEnabled(True)


# ── 浮动 AI 球 ────────────────────────────────────────────────────────────────

class FloatingAIAssistant(QObject):
    def __init__(self, host: QWidget, system_prompt: str = "", title: str = "AI Bot"):
        super().__init__(host)
        self._host       = host
        self._title      = title
        self._system     = system_prompt or build_ai_system_prompt()
        self._ball_w     = _pt(92)
        self._ball_h     = _pt(56)
        self._panel_w    = _pt(420)
        self._panel_h    = _pt(560)
        self._margin     = _pt(24)
        self._gap        = _pt(14)
        self._top_safe   = _pt(84)
        self._dragging   = False
        self._drag_moved = False
        self._drag_offset = QPoint()
        self._ball_pos   = QPoint()
        self._expanded   = False
        self._build_ui()
        self._host.installEventFilter(self)
        self._ball.installEventFilter(self)
        self._snap_to_corner()
        self._update_positions()
        self._connect_bus()

    def _build_ui(self):
        from seeed_jetson_develop.core.runner import get_runner, SSHRunner
        init_runner = get_runner()
        if not isinstance(init_runner, SSHRunner):
            init_runner = None

        self._panel = QFrame(self._host)
        self._panel.setObjectName("FloatingAIPanel")
        self._panel.setStyleSheet(f"""
            QFrame#FloatingAIPanel {{
                background: {C_BG_DEEP};
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 18px;
            }}
        """)
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = QFrame(self._panel)
        header.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 12, 10)
        header_layout.setSpacing(8)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(9)}pt; background:transparent;")
        header_layout.addWidget(dot)
        header_layout.addWidget(_lbl(self._title, 13, C_TEXT, bold=True))
        header_layout.addWidget(_lbl("Jetson AI Bot", 10, C_TEXT3))
        header_layout.addStretch()

        close_btn = QPushButton("×")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(_pt(28), _pt(28))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.05);
                border: none;
                border-radius: 14px;
                color: {C_TEXT2};
                font-size: {_pt(14)}pt;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10);
                color: {C_TEXT};
            }}
        """)
        close_btn.clicked.connect(self.hide_panel)
        header_layout.addWidget(close_btn)
        panel_layout.addWidget(header)

        self._chat = AIChatPanel(
            system_prompt=self._system,
            title=self._title,
            runner=init_runner,
            parent=self._panel,
        )
        panel_layout.addWidget(self._chat, 1)
        self._panel.resize(self._panel_w, self._panel_h)
        self._panel.hide()

        self._ball = QPushButton("AI Bot", self._host)
        self._ball.setCursor(Qt.PointingHandCursor)
        self._ball.setFixedSize(self._ball_w, self._ball_h)
        self._ball.setStyleSheet(f"""
            QPushButton {{
                background: qradialgradient(cx:0.35, cy:0.30, radius:0.9,
                    fx:0.35, fy:0.30,
                    stop:0 #A8D93A,
                    stop:0.58 #7AB317,
                    stop:1 #496F0E);
                border: 1px solid rgba(255,255,255,0.20);
                border-radius: {self._ball_h // 2}px;
                color: #071200;
                font-size: {_pt(11)}pt;
                font-weight: 700;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background: qradialgradient(cx:0.35, cy:0.30, radius:0.9,
                    fx:0.35, fy:0.30,
                    stop:0 #B7E34B,
                    stop:0.58 #89C420,
                    stop:1 #587F14);
            }}
        """)
        self._ball.raise_()

    def _connect_bus(self):
        try:
            from seeed_jetson_develop.core.events import bus
            bus.device_connected.connect(self._on_device_connected)
            bus.device_disconnected.connect(self._on_device_disconnected)
        except Exception:
            pass

    def _on_device_connected(self, _info: dict):
        from seeed_jetson_develop.core.runner import get_runner
        self._chat.set_runner(get_runner())

    def _on_device_disconnected(self, _ip: str):
        self._chat.set_runner(None)

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() in {QEvent.Resize, QEvent.Show}:
            self._constrain_ball()
            self._update_positions()
        elif obj is self._ball:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._dragging   = True
                self._drag_moved = False
                self._drag_offset = event.pos()
                return True
            if event.type() == QEvent.MouseMove and self._dragging:
                new_pos = self._ball.mapToParent(event.pos() - self._drag_offset)
                if (new_pos - self._ball_pos).manhattanLength() > 3:
                    self._drag_moved = True
                self._set_ball_pos(new_pos)
                return True
            if event.type() == QEvent.MouseButtonRelease and self._dragging:
                self._dragging = False
                if self._drag_moved:
                    self._snap_to_side()
                else:
                    self.toggle_panel()
                return True
        return super().eventFilter(obj, event)

    def toggle_panel(self):
        if self._expanded:
            self.hide_panel()
        else:
            self.show_panel()

    def show_panel(self):
        from seeed_jetson_develop.core.runner import get_runner, SSHRunner
        runner = get_runner()
        self._chat.set_runner(runner if isinstance(runner, SSHRunner) else None)
        self._expanded = True
        self._panel.show()
        self._update_positions()
        self._panel.raise_()
        self._ball.raise_()

    def inject_context(self, skill_name: str, skill_desc: str, commands: list):
        self.show_panel()
        self._chat.inject_context(skill_name, skill_desc, commands)

    def inject_topic(self, title: str, summary: str, details=None):
        self.show_panel()
        self._chat.inject_topic(title, summary, details)

    def inject_error(self, title: str, log_text: str):
        self.show_panel()
        self._chat.inject_error(title, log_text)

    def hide_panel(self):
        self._expanded = False
        self._panel.hide()
        self._ball.raise_()

    def _set_ball_pos(self, pos: QPoint):
        rect = self._safe_ball_rect()
        x = min(max(pos.x(), rect.left()), rect.right())
        y = min(max(pos.y(), rect.top()), rect.bottom())
        self._ball_pos = QPoint(x, y)
        self._update_positions()

    def _snap_to_corner(self):
        rect = self._safe_ball_rect()
        self._ball_pos = QPoint(rect.left(), rect.bottom())

    def _snap_to_side(self):
        rect = self._safe_ball_rect()
        center_x = self._ball_pos.x() + self._ball_w / 2
        target_x = rect.left() if center_x < self._host.width() / 2 else rect.right()
        self._ball_pos = QPoint(target_x, min(max(self._ball_pos.y(), rect.top()), rect.bottom()))
        self._update_positions()

    def _constrain_ball(self):
        if self._ball_pos.isNull():
            self._snap_to_corner()
            return
        self._set_ball_pos(self._ball_pos)

    def _safe_ball_rect(self) -> QRect:
        left   = self._margin
        top    = self._top_safe
        right  = max(left, self._host.width()  - self._margin - self._ball_w)
        bottom = max(top,  self._host.height() - self._margin - self._ball_h)
        return QRect(left, top, max(1, right - left + 1), max(1, bottom - top + 1))

    def _update_positions(self):
        self._ball.move(self._ball_pos)
        self._ball.raise_()
        if not self._expanded:
            return

        ball_x = self._ball_pos.x()
        ball_y = self._ball_pos.y()
        host_w = self._host.width()
        host_h = self._host.height()

        avail_w = host_w - 2 * self._margin
        avail_h = host_h - self._top_safe - self._ball_h - self._gap - self._margin
        pw = max(_pt(280), min(self._panel_w, avail_w))
        ph = max(_pt(300), min(self._panel_h, avail_h))
        self._panel.resize(pw, ph)

        if ball_x + (self._ball_w // 2) >= host_w / 2:
            panel_x = ball_x + self._ball_w - pw
        else:
            panel_x = ball_x
        panel_y = ball_y - ph - self._gap

        panel_x = max(self._margin, min(panel_x, host_w - pw - self._margin))
        min_y   = self._top_safe
        max_y   = max(min_y, host_h - ph - self._ball_h - self._gap - self._margin)
        panel_y = max(min_y, min(panel_y, max_y))

        self._panel.move(panel_x, panel_y)
        self._panel.raise_()
