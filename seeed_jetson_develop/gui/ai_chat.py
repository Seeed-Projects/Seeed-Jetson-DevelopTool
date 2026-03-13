"""可复用的 AI 对话面板组件

Skills 页面右侧面板和 AI 终端页面共用此组件。
"""
import os

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy,
)

from seeed_jetson_develop.core.config import load as load_config, save as save_config
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
)


_DEFAULT_SYSTEM = (
    "你是 Seeed Jetson Develop Tool 的 AI 助手，专注于 NVIDIA Jetson 开发板的"
    "开发、配置和问题排查。你了解 Jetson Nano、Orin Nano、Orin NX 等型号，"
    "熟悉 JetPack、L4T、CUDA、TensorRT、ROS 等技术。"
    "回答简洁，当需要提供命令时使用代码块格式（```bash ... ```）。中文回答。"
)


def _get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        key = load_config().get("anthropic_api_key", "")
    return key


def _get_base_url() -> str:
    url = os.environ.get("ANTHROPIC_BASE_URL", "")
    if not url:
        url = load_config().get("anthropic_base_url", "")
    return url


# ── 流式 API 调用线程 ──────────────────────────────────────────────────────────
class _AiThread(QThread):
    token = pyqtSignal(str)
    done  = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, messages: list, system: str, api_key: str, base_url: str = ""):
        super().__init__()
        self._messages = messages
        self._system   = system
        self._api_key  = api_key
        self._base_url = base_url
        self._cancel   = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            import anthropic
            base_url = self._base_url or "https://api.anthropic.com"
            client = anthropic.Anthropic(
                api_key=self._api_key,
                base_url=base_url,
            )
            with client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                system=self._system,
                messages=self._messages,
            ) as stream:
                for text in stream.text_stream:
                    if self._cancel:
                        break
                    self.token.emit(text)
        except Exception as e:
            base_url = self._base_url or "https://api.anthropic.com"
            self.error.emit(f"{e}\n[base_url: {base_url}]")
        finally:
            self.done.emit()


# ── 单条消息气泡 ───────────────────────────────────────────────────────────────
class _MsgBubble(QFrame):
    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self._is_user = is_user
        if is_user:
            self.setStyleSheet(
                "background:rgba(122,179,23,0.12); border:none; border-radius:10px;"
            )
        else:
            self.setStyleSheet(
                f"background:{C_CARD}; border:none; border-radius:10px;"
            )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(0)

        self._lbl = QLabel(text)
        self._lbl.setWordWrap(True)
        self._lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        color = C_TEXT if is_user else C_TEXT2
        self._lbl.setStyleSheet(
            f"color:{color}; font-size:{_pt(11)}pt; background:transparent; border:none;"
        )
        lay.addWidget(self._lbl)

    def set_text(self, text: str):
        self._lbl.setText(text)

    def append_text(self, token: str):
        self._lbl.setText(self._lbl.text() + token)


# ── AI 对话面板（可复用） ──────────────────────────────────────────────────────
class AIChatPanel(QWidget):
    """
    可独立嵌入任意页面的 AI 对话面板。

    用法:
        panel = AIChatPanel(system_prompt="...", title="AI 助手")
        panel.inject_context("YOLOv8 安装", "安装 ultralytics", ["pip install ultralytics"])
    """

    def __init__(self, system_prompt: str = "", title: str = "AI 助手", parent=None):
        super().__init__(parent)
        self._system   = system_prompt or _DEFAULT_SYSTEM
        self._history  = []
        self._thread   = None
        self._cur_bubble: _MsgBubble | None = None
        self._cur_text  = ""
        self._setup_ui(title)

    # ── UI 构建 ──────────────────────────────────────────────────────────────
    def _setup_ui(self, title: str):
        self.setStyleSheet(f"background:{C_BG_DEEP}; border:none;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # 标题栏
        title_row = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(8)}pt; background:transparent;")
        title_row.addWidget(dot)
        title_row.addSpacing(6)
        title_row.addWidget(_lbl(title, 13, C_TEXT, bold=True))
        title_row.addStretch()

        has_key = bool(_get_api_key())
        if not has_key:
            key_btn = QPushButton("配置 Key")
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
        lay.addLayout(title_row)

        # 消息滚动区
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background:transparent; border:none;")

        self._msg_widget = QWidget()
        self._msg_widget.setStyleSheet("background:transparent;")
        self._msg_lay = QVBoxLayout(self._msg_widget)
        self._msg_lay.setContentsMargins(0, 4, 0, 4)
        self._msg_lay.setSpacing(8)
        self._msg_lay.addStretch()

        self._scroll.setWidget(self._msg_widget)
        lay.addWidget(self._scroll, 1)

        # API Key 配置框（默认隐藏）
        self._key_frame = QFrame()
        self._key_frame.setStyleSheet(
            f"background:{C_CARD}; border:none; border-radius:8px;"
        )
        kl = QHBoxLayout(self._key_frame)
        kl.setContentsMargins(10, 6, 10, 6)
        kl.setSpacing(8)
        kl.addWidget(_lbl("API Key:", 10, C_TEXT3))
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("sk-ant-...")
        self._key_input.setEchoMode(QLineEdit.Password)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background:{C_CARD_LIGHT}; border:none; border-radius:6px;
                padding:4px 10px; color:{C_TEXT}; font-size:{_pt(10)}pt;
            }}
        """)
        self._key_input.setFixedHeight(_pt(30))
        save_btn = _btn("保存", primary=True, small=True)
        save_btn.setFixedWidth(_pt(52))
        save_btn.clicked.connect(self._save_key)
        kl.addWidget(self._key_input, 1)
        kl.addWidget(save_btn)
        self._key_frame.setVisible(False)
        lay.addWidget(self._key_frame)

        # 输入区
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self._input = QLineEdit()
        self._input.setPlaceholderText("输入问题，按 Enter 发送…")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background:{C_CARD_LIGHT}; border:none; border-radius:8px;
                padding:8px 14px; color:{C_TEXT}; font-size:{_pt(11)}pt;
            }}
            QLineEdit:focus {{ background:{C_CARD}; }}
        """)
        self._input.setFixedHeight(_pt(40))
        self._input.returnPressed.connect(self._on_send)

        self._send_btn = _btn("发送", primary=True, small=True)
        self._send_btn.setFixedWidth(_pt(60))
        self._send_btn.clicked.connect(self._on_send)

        input_row.addWidget(self._input, 1)
        input_row.addWidget(self._send_btn)
        lay.addLayout(input_row)

        # 欢迎消息
        if not has_key:
            self._add_ai_bubble("请先点击「配置 Key」输入 Anthropic API Key 以使用 AI 功能。")
        else:
            self._add_ai_bubble("你好！我是 Jetson 开发助手，可以帮你了解和使用 Skills、排查问题。")

    # ── 公开接口 ──────────────────────────────────────────────────────────────
    def set_system(self, prompt: str):
        """更新系统提示词"""
        self._system = prompt

    def inject_context(self, skill_name: str, skill_desc: str, commands: list):
        """Skills 页面点击 skill 时调用，自动发起一轮对话"""
        cmds_part = ""
        if commands:
            cmds_str = "\n".join(commands[:8])
            cmds_part = f"\n\n命令预览：\n```bash\n{cmds_str}\n```"
        text = f"帮我介绍一下这个 Skill：**{skill_name}**\n\n描述：{skill_desc}{cmds_part}"
        self._add_user_bubble(text)
        self._fire_ai()

    # ── 内部方法 ──────────────────────────────────────────────────────────────
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
        self._add_ai_bubble("API Key 已保存，现在可以开始对话了！")

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

    def _add_ai_bubble(self, text: str = "") -> _MsgBubble:
        bubble = self._insert_bubble(text, is_user=False)
        return bubble

    def _insert_bubble(self, text: str, is_user: bool) -> _MsgBubble:
        bubble = _MsgBubble(text, is_user, self._msg_widget)
        count = self._msg_lay.count()
        self._msg_lay.insertWidget(count - 1, bubble)
        QTimer.singleShot(30, self._scroll_to_bottom)
        return bubble

    def _scroll_to_bottom(self):
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        )

    def _fire_ai(self):
        api_key = _get_api_key()
        if not api_key:
            self._add_ai_bubble("未找到 API Key，请先点击「配置 Key」。")
            return
        if self._thread and self._thread.isRunning():
            return

        self._cur_bubble = self._add_ai_bubble("")
        self._cur_text   = ""
        self._send_btn.setEnabled(False)
        self._input.setEnabled(False)

        self._thread = _AiThread(
            messages=list(self._history),
            system=self._system,
            api_key=api_key,
            base_url=_get_base_url(),
        )
        self._thread.token.connect(self._on_token)
        self._thread.done.connect(self._on_done)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_token(self, token: str):
        self._cur_text += token
        if self._cur_bubble:
            self._cur_bubble.set_text(self._cur_text)
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
            self._cur_bubble.set_text(f"请求失败：{msg}")
        self._send_btn.setEnabled(True)
        self._input.setEnabled(True)
