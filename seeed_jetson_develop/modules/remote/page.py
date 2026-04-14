"""Remote development page."""

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from seeed_jetson_develop.core import config as _cfg
from seeed_jetson_develop.core.config import DEFAULT_ANTHROPIC_BASE_URL
from seeed_jetson_develop.core.config import get_runtime_anthropic_settings as _get_runtime_anthropic_settings
from seeed_jetson_develop.core.events import bus
from seeed_jetson_develop.core.runner import SSHRunner, get_runner, set_runner
from seeed_jetson_develop.gui.i18n_binding import I18nBinding
from seeed_jetson_develop.gui.i18n import get_language, t
from seeed_jetson_develop.gui.runtime_i18n import apply_dialog_language as _apply_dlg_lang
from seeed_jetson_develop.gui.theme import (
    C_BG,
    C_CARD,
    C_CARD_LIGHT,
    C_GREEN,
    C_ORANGE,
    C_RED,
    C_TEXT,
    C_TEXT2,
    C_TEXT3,
    ask_question_message as _ask_question_message,
    make_button as _btn,
    make_card as _card,
    make_input_card as _input_card,
    make_label as _lbl,
    pt as _pt,
    show_error_message as _show_error_message,
    show_info_message as _show_info_message,
    show_warning_message as _show_warning_message,
    apply_shadow as _shadow,
)
from seeed_jetson_develop.gui.widgets.page_base import PageBase
from seeed_jetson_develop.modules.remote import connector
from seeed_jetson_develop.modules.remote.agent_install_dialog import open_agent_install_dialog
from seeed_jetson_develop.modules.remote.desktop_dialog import open_desktop_dialog
from seeed_jetson_develop.modules.remote.jetson_init import (
    list_serial_ports,
    open_jetson_init_dialog,
    open_jetson_net_config_dialog,
)
from seeed_jetson_develop.modules.remote.net_share_dialog import open_net_share_dialog


def _tt(key: str, **kwargs) -> str:
    return t(key, lang=get_language(), **kwargs)


def _show_need_connection_dialog(parent: QWidget, tool_name: str):
    dlg = QDialog(parent)
    dlg.setWindowTitle(_tt("remote.need_conn.title"))
    dlg.setModal(True)
    dlg.setMinimumWidth(_pt(460))
    dlg.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 22, 24, 20)
    lay.setSpacing(16)
    row = QHBoxLayout()
    row.setSpacing(12)
    icon = QLabel("⚠")
    icon.setAlignment(Qt.AlignTop)
    icon.setStyleSheet(f"color:{C_ORANGE}; font-size:{_pt(26)}px; background:transparent;")
    row.addWidget(icon)
    col = QVBoxLayout()
    col.addWidget(_lbl(_tt("remote.need_conn.header"), 15, C_TEXT, bold=True))
    col.addWidget(_lbl(_tt("remote.need_conn.desc", tool_name=tool_name), 11, C_TEXT2, wrap=True))
    row.addLayout(col, 1)
    lay.addLayout(row)
    hint = QFrame()
    hint.setStyleSheet(f"background:{C_CARD_LIGHT}; border:none; border-radius:12px;")
    hint_lay = QVBoxLayout(hint)
    hint_lay.setContentsMargins(16, 14, 16, 14)
    hint_lay.addWidget(_lbl(_tt("remote.need_conn.next_steps"), 12, C_GREEN, bold=True))
    hint_lay.addWidget(_lbl(_tt("remote.need_conn.steps"), 11, C_TEXT2, wrap=True))
    lay.addWidget(hint)
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    ok_btn = _btn(_tt("remote.need_conn.ok"), primary=True, small=True)
    ok_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(ok_btn)
    lay.addLayout(btn_row)
    _apply_dlg_lang(dlg, parent)
    dlg.exec_()


class _ScanThread(QThread):
    found = pyqtSignal(list)
    progress = pyqtSignal(int, int)

    def __init__(self, subnet: str | None = None):
        super().__init__()
        self._subnet = subnet

    def run(self):
        hosts = connector.scan_local_network(self._subnet, on_progress=lambda s, t: self.progress.emit(s, t))
        self.found.emit(hosts)


class _SSHCheckThread(QThread):
    result = pyqtSignal(bool, str)

    def __init__(self, host: str, username: str, password: str):
        super().__init__()
        self._host = host
        self._username = username
        self._password = password

    def run(self):
        try:
            import paramiko

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                self._host,
                port=22,
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


class _ApiKeyDialog(QDialog):
    key_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_tt("remote.api_key.title"))
        self.setMinimumSize(_pt(560), _pt(400))
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)
        lay.addWidget(_lbl(_tt("remote.api_key.header"), 16, C_TEXT, bold=True))
        lay.addWidget(_lbl(_tt("remote.api_key.desc"), 11, C_TEXT2, wrap=True))

        key_row = QHBoxLayout()
        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("sk-ant-api03-...")
        self._key_edit.setEchoMode(QLineEdit.Password)
        self._key_edit.setStyleSheet(
            f"QLineEdit {{background:{C_CARD_LIGHT}; border:none; border-radius:10px; padding:10px 16px; color:{C_TEXT}; font-size:{_pt(12)}px;}}"
        )
        self._toggle_btn = _btn("👁", small=True)
        self._toggle_btn.setFixedWidth(_pt(50))
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.toggled.connect(lambda checked: self._key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password))
        self._toggle_btn.toggled.connect(lambda checked: self._toggle_btn.setText("🙈" if checked else "👁"))
        key_row.addWidget(self._key_edit, 1)
        key_row.addWidget(self._toggle_btn)
        lay.addLayout(key_row)

        lay.addWidget(_lbl(_tt("remote.api_key.base_url_label"), 11, C_TEXT3))
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://api.anthropic.com")
        self._url_edit.setStyleSheet(
            f"QLineEdit {{background:{C_CARD_LIGHT}; border:none; border-radius:10px; padding:10px 16px; color:{C_TEXT}; font-size:{_pt(11)}px;}}"
        )
        lay.addWidget(self._url_edit)

        cfg = _cfg.load()
        existing = (cfg.get("anthropic_api_key") or "").strip()
        existing_url = (cfg.get("anthropic_base_url") or "").strip()
        if existing:
            self._key_edit.setPlaceholderText(_tt("remote.api_key.placeholder.current", prefix=existing[:12]))
            status_text = _tt("remote.api_key.status.configured", prefix=existing[:12])
            status_color = C_GREEN
        else:
            status_text = _tt("remote.api_key.status.not_configured")
            status_color = C_ORANGE
        if existing_url:
            self._url_edit.setText(existing_url)
        self._status_lbl = _lbl(status_text, 11, status_color)
        lay.addWidget(self._status_lbl)
        lay.addStretch()

        btn_row = QHBoxLayout()
        save_btn = _btn(_tt("remote.api_key.btn.save"), primary=True)
        clear_btn = _btn(_tt("remote.api_key.btn.clear"), danger=True)
        close_btn = _btn(_tt("common.cancel"))
        btn_row.addWidget(save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        save_btn.clicked.connect(self._save)
        clear_btn.clicked.connect(self._clear)
        close_btn.clicked.connect(self.close)

    def _save(self):
        key = self._key_edit.text().strip()
        if not key:
            _show_warning_message(self, _tt("remote.api_key.warn.title"), _tt("remote.api_key.warn.empty"))
            return
        if len(key) < 20:
            _show_warning_message(self, _tt("remote.api_key.warn.title"), _tt("remote.api_key.warn.short"))
            return
        url = self._url_edit.text().strip()
        data = _cfg.load()
        data["anthropic_api_key"] = key
        data["anthropic_base_url"] = url
        _cfg.save(data)
        status = _tt("remote.api_key.status.saved", prefix=key[:12])
        if url and url != DEFAULT_ANTHROPIC_BASE_URL:
            status += "  " + _tt("remote.api_key.status.saved_url", url=url)
        self._status_lbl.setText(status)
        self._status_lbl.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(11)}px; background:transparent;")
        self.key_saved.emit()
        _show_info_message(self, _tt("remote.api_key.info.saved_title"), _tt("remote.api_key.info.saved_body"))
        self.close()

    def _clear(self):
        reply = _ask_question_message(
            self,
            _tt("remote.api_key.confirm_clear_title"),
            _tt("remote.api_key.confirm_clear_body"),
            buttons=QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            data = _cfg.load()
            data["anthropic_api_key"] = ""
            data["anthropic_base_url"] = ""
            _cfg.save(data)
            self._key_edit.clear()
            self._url_edit.clear()
            self._status_lbl.setText(_tt("remote.api_key.status.cleared"))
            self._status_lbl.setStyleSheet(f"color:{C_ORANGE}; font-size:{_pt(11)}px; background:transparent;")
            self.key_saved.emit()


class _SshCmdThread(QThread):
    line_out = pyqtSignal(str)
    finished_ = pyqtSignal(int, str)

    def __init__(self, runner, commands):
        super().__init__()
        self._runner = runner
        self._commands = commands
        self._last_out = ""

    def run(self):
        for cmd, timeout in self._commands:
            self.line_out.emit(f"$ {cmd}")
            rc, out = self._runner.run(cmd, timeout=timeout, on_output=lambda l: self.line_out.emit(l))
            self._last_out = out
            if rc != 0:
                self.finished_.emit(rc, out)
                return
        self.finished_.emit(0, self._last_out)


class _VscodeWebDialog(QDialog):
    def __init__(self, runner, ip, parent=None):
        super().__init__(parent)
        self._runner = runner
        self._ip = ip
        self._thread = None
        self.setWindowTitle(_tt("remote.vscode_web.window_title"))
        self.setMinimumSize(_pt(640), _pt(500))
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(_lbl(_tt("remote.vscode_web.title"), 16, C_TEXT, bold=True))
        lay.addWidget(_lbl(_tt("remote.vscode_web.desc", ip=self._ip), 11, C_TEXT2, wrap=True))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            f"background:{C_CARD}; border:none; border-radius:10px; color:{C_TEXT2}; font-size:{_pt(10)}px; padding:12px;"
        )
        lay.addWidget(self._log, 1)
        self._result = QLabel("")
        self._result.setWordWrap(True)
        self._result.setOpenExternalLinks(True)
        self._result.setTextFormat(Qt.RichText)
        self._result.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self._result.setStyleSheet(f"color:{C_TEXT2}; font-size:{_pt(12)}px; background:transparent;")
        lay.addWidget(self._result)
        row = QHBoxLayout()
        self._run_btn = _btn(_tt("remote.vscode_web.btn.deploy"), primary=True)
        close_btn = _btn(_tt("common.close"))
        row.addWidget(self._run_btn)
        row.addStretch()
        row.addWidget(close_btn)
        lay.addLayout(row)
        self._run_btn.clicked.connect(self._start)
        close_btn.clicked.connect(self.close)

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

    def _append(self, line):
        self._log.append(line)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _start(self):
        self._run_btn.setEnabled(False)
        self._log.clear()
        self._result.setText("")
        install_cmd = (
            "CS_VER=4.96.2 && "
            "ARCH=$(dpkg --print-architecture) && "
            "DEB=code-server_${CS_VER}_${ARCH}.deb && "
            "CACHE=~/.cache/code-server && mkdir -p $CACHE && rm -f ${CACHE}/${DEB} && "
            "RELEASE_PATH=\"coder/code-server/releases/download/v${CS_VER}/${DEB}\" && "
            "for MIRROR in https://gh.ddlc.top/https://github.com https://ghproxy.cfd/https://github.com https://hub.gitmirror.com/https://github.com; do "
            "echo \"Try mirror: ${MIRROR}\" && wget -q --show-progress --timeout=60 --tries=1 ${MIRROR}/${RELEASE_PATH} -O ${CACHE}/${DEB} && break; "
            "echo 'Failed, trying next...' && rm -f ${CACHE}/${DEB}; done && "
            "[ -f ${CACHE}/${DEB} ] && [ $(stat -c%s ${CACHE}/${DEB}) -gt 52428800 ] || { echo 'Download failed'; exit 1; } && "
            "echo 'Installing...' && "
            f"echo {self._runner.sudo_password!r} | sudo -S dpkg -i ${{CACHE}}/${{DEB}} 2>&1"
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
            self._result.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(12)}px; background:transparent;")
            self._result.setText(
                f"{_tt('remote.vscode_web.done.prefix')} <a href=\"{url}\">{url}</a><br>{_tt('remote.vscode_web.done.hint')}"
            )
        else:
            self._result.setStyleSheet(f"color:{C_RED}; font-size:{_pt(12)}px; background:transparent;")
            self._result.setText(_tt("remote.vscode_web.done.failed", rc=rc, reason=last_out[:200]))


class _JupyterLaunchDialog(QDialog):
    def __init__(self, runner, ip, parent=None):
        super().__init__(parent)
        self._runner = runner
        self._ip = ip
        self._thread = None
        self.setWindowTitle(_tt("remote.jupyter_launch.window_title"))
        self.setMinimumSize(_pt(640), _pt(500))
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(_lbl(_tt("remote.jupyter_launch.title"), 16, C_TEXT, bold=True))
        lay.addWidget(_lbl(_tt("remote.jupyter_launch.desc", ip=self._ip), 11, C_TEXT2, wrap=True))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            f"background:{C_CARD}; border:none; border-radius:10px; color:{C_TEXT2}; font-size:{_pt(10)}px; padding:12px;"
        )
        lay.addWidget(self._log, 1)
        self._result = QLabel("")
        self._result.setWordWrap(True)
        self._result.setOpenExternalLinks(True)
        self._result.setTextFormat(Qt.RichText)
        self._result.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self._result.setStyleSheet(f"color:{C_TEXT2}; font-size:{_pt(12)}px; background:transparent;")
        lay.addWidget(self._result)
        row = QHBoxLayout()
        self._run_btn = _btn(_tt("remote.jupyter_launch.btn.start"), primary=True)
        close_btn = _btn(_tt("common.close"))
        row.addWidget(self._run_btn)
        row.addStretch()
        row.addWidget(close_btn)
        lay.addLayout(row)
        self._run_btn.clicked.connect(self._start)
        close_btn.clicked.connect(self.close)

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

    def _append(self, line):
        self._log.append(line)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _start(self):
        self._run_btn.setEnabled(False)
        self._log.clear()
        self._result.setText("")
        cmds = [
            ("PYTHONUNBUFFERED=1 pip3 install jupyterlab 2>&1", 300),
            (
                "nohup ~/.local/bin/jupyter lab --ip=0.0.0.0 --port=8888 --no-browser "
                "--NotebookApp.token='' --NotebookApp.password='' > /tmp/jupyter.log 2>&1 & echo started",
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
        if rc == 0:
            url = f"http://{self._ip}:8888"
            self._result.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(12)}px; background:transparent;")
            self._result.setText(f"{_tt('remote.jupyter_launch.done.prefix')} <a href=\"{url}\">{url}</a>")
        else:
            self._result.setStyleSheet(f"color:{C_RED}; font-size:{_pt(12)}px; background:transparent;")
            self._result.setText(_tt("remote.jupyter_launch.done.failed", rc=rc, reason=last_out[:200]))


class _ApiTestThread(QThread):
    result = pyqtSignal(bool, str)

    def __init__(self, api_key, base_url):
        super().__init__()
        self._key = api_key
        self._base_url = base_url or DEFAULT_ANTHROPIC_BASE_URL

    def run(self):
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self._key, base_url=self._base_url)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{"role": "user", "content": "hi"}],
            )
            self.result.emit(True, getattr(msg, "model", "claude-haiku-4-5"))
        except Exception as e:
            self.result.emit(False, str(e))


class _VscodeSSHDialog(QDialog):
    def __init__(self, ip: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(_tt("remote.vscode_ssh.window_title"))
        self.setMinimumSize(_pt(620), _pt(480))
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)
        lay.addWidget(_lbl(_tt("remote.vscode_ssh.title"), 16, C_TEXT, bold=True))
        ssh_addr = f"ssh seeed@{ip}" if ip else "ssh seeed@<DEVICE_IP>"
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(_tt("remote.vscode_ssh.steps", ssh_addr=ssh_addr))
        viewer.setStyleSheet(f"background:{C_CARD}; border:none; border-radius:10px; color:{C_TEXT2}; padding:14px;")
        lay.addWidget(viewer, 1)
        row = QHBoxLayout()
        row.addStretch()
        close_btn = _btn(_tt("common.close"))
        close_btn.clicked.connect(self.close)
        row.addWidget(close_btn)
        lay.addLayout(row)

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


def build_page() -> QWidget:
    page = PageBase(_tt("remote.page.title"), _tt("remote.page.subtitle"))
    page.i18n = I18nBinding()
    lay = page.get_content_layout()

    api_card = _card(12)
    api_lay = QVBoxLayout(api_card)
    api_lay.setContentsMargins(24, 20, 24, 20)
    api_lay.setSpacing(14)
    api_title = _lbl(_tt("remote.api.title"), 15, C_TEXT, bold=True)
    api_status = QLabel("")
    api_status.setStyleSheet(f"font-size:{_pt(11)}px; background:transparent;")
    api_head = QHBoxLayout()
    api_head.addWidget(api_title)
    api_head.addStretch()
    api_head.addWidget(api_status)
    api_lay.addLayout(api_head)
    api_preview = _lbl("", 11, C_TEXT3)
    api_btn = _btn(_tt("remote.api.btn.configure"), small=True)
    row = QHBoxLayout()
    row.addWidget(api_preview, 1)
    row.addWidget(api_btn)
    api_lay.addLayout(row)
    api_desc = _lbl(_tt("remote.api.desc"), 11, C_TEXT3, wrap=True)
    api_lay.addWidget(api_desc)

    def _refresh_api_status():
        cfg = _cfg.load()
        key = (cfg.get("anthropic_api_key") or "").strip()
        runtime = _get_runtime_anthropic_settings()
        active_url = runtime["base_url"]
        source = runtime["base_url_source"]
        source_label = {
            "config": _tt("remote.api.source.config"),
            "env": _tt("remote.api.source.env"),
            "default": _tt("remote.api.source.default"),
        }.get(source, source)
        if key:
            api_status.setText(_tt("remote.api.status.configured"))
            api_status.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(11)}px; background:transparent; font-weight:700;")
            text = _tt("remote.api.preview.key", prefix=key[:12])
            if active_url and active_url != DEFAULT_ANTHROPIC_BASE_URL:
                text += "  |  " + _tt("remote.api.preview.base_url", source=source_label, url=active_url)
            api_preview.setText(text)
            api_preview.setStyleSheet(f"color:{C_TEXT2}; font-size:{_pt(11)}px; background:transparent;")
        else:
            api_status.setText(_tt("remote.api.status.not_configured"))
            api_status.setStyleSheet(f"color:{C_ORANGE}; font-size:{_pt(11)}px; background:transparent; font-weight:700;")
            api_preview.setText(_tt("remote.api.preview.empty"))
            api_preview.setStyleSheet(f"color:{C_TEXT3}; font-size:{_pt(11)}px; background:transparent;")

    api_btn.clicked.connect(lambda: _open_api_dialog(page, _refresh_api_status))
    _refresh_api_status()
    _shadow(api_card)
    lay.addWidget(api_card)

    conn_cfg = _cfg.load()
    conn_card = _card(12)
    conn_lay = QVBoxLayout(conn_card)
    conn_lay.setContentsMargins(24, 20, 24, 20)
    conn_lay.setSpacing(14)

    conn_title = _lbl(_tt("remote.conn.title"), 15, C_TEXT, bold=True)
    conn_status = QLabel(_tt("remote.conn.status.disconnected"))
    conn_status.setStyleSheet(f"color:{C_TEXT2}; font-size:{_pt(11)}px; background:transparent;")
    conn_head = QHBoxLayout()
    conn_head.addWidget(conn_title)
    conn_head.addStretch()
    conn_head.addWidget(conn_status)
    conn_lay.addLayout(conn_head)

    ip_label = _lbl(_tt("remote.conn.ip_label"), 12, C_TEXT)
    ip_input = QLineEdit(conn_cfg.get("remote_last_host", ""))
    ip_input.setPlaceholderText(_tt("remote.conn.ip_placeholder"))
    ip_input.setStyleSheet(f"QLineEdit {{background:{C_CARD_LIGHT}; border:none; border-radius:10px; padding:8px 16px; color:{C_TEXT}; font-size:{_pt(12)}px;}}")
    ip_input.setFixedHeight(_pt(44))
    ssh_btn = _btn(_tt("remote.conn.btn.connect"), primary=True, small=True)
    scan_btn = _btn(_tt("remote.conn.btn.scan"), small=True)
    ip_row = QHBoxLayout()
    ip_row.addWidget(ip_label)
    ip_row.addWidget(ip_input, 1)
    ip_row.addWidget(ssh_btn)
    ip_row.addWidget(scan_btn)
    conn_lay.addLayout(ip_row)

    user_label = _lbl(_tt("remote.conn.username"), 11, C_TEXT2)
    user_input = QLineEdit(conn_cfg.get("remote_last_user", "seeed") or "seeed")
    pass_label = _lbl(_tt("remote.conn.password"), 11, C_TEXT2)
    pass_input = QLineEdit(conn_cfg.get("remote_last_password", ""))
    pass_input.setPlaceholderText(_tt("remote.conn.password_placeholder"))
    pass_input.setEchoMode(QLineEdit.Password)
    for e in (user_input, pass_input):
        e.setFixedHeight(_pt(40))
        e.setStyleSheet(f"QLineEdit {{background:{C_CARD_LIGHT}; border:none; border-radius:8px; padding:6px 12px; color:{C_TEXT}; font-size:{_pt(11)}px;}}")
    auth_row = QHBoxLayout()
    auth_row.addWidget(user_label)
    auth_row.addWidget(user_input)
    auth_row.addSpacing(14)
    auth_row.addWidget(pass_label)
    auth_row.addWidget(pass_input)
    conn_lay.addLayout(auth_row)

    sudo_label = _lbl(_tt("remote.conn.sudo_password"), 11, C_TEXT2)
    sudo_input = QLineEdit(conn_cfg.get("remote_last_sudo_password", ""))
    sudo_input.setPlaceholderText(_tt("remote.conn.sudo_placeholder"))
    sudo_input.setEchoMode(QLineEdit.Password)
    sudo_input.setFixedHeight(_pt(40))
    sudo_input.setStyleSheet(user_input.styleSheet())
    sudo_hint = _lbl(_tt("remote.conn.sudo_hint"), 10, C_TEXT2)
    sudo_row = QHBoxLayout()
    sudo_row.addWidget(sudo_label)
    sudo_row.addWidget(sudo_input, 1)
    sudo_row.addWidget(sudo_hint)
    conn_lay.addLayout(sudo_row)

    subnet_label = _lbl(_tt("remote.conn.subnet"), 11, C_TEXT2)
    subnet_input = QLineEdit(conn_cfg.get("remote_last_subnet", "192.168.1") or "192.168.1")
    subnet_input.setPlaceholderText("192.168.x")
    subnet_input.setFixedWidth(_pt(160))
    subnet_input.setFixedHeight(_pt(40))
    subnet_input.setStyleSheet(user_input.styleSheet())
    subnet_row = QHBoxLayout()
    subnet_row.addWidget(subnet_label)
    subnet_row.addWidget(subnet_input)
    subnet_row.addStretch()
    conn_lay.addLayout(subnet_row)

    scan_result = _lbl("", 11, C_TEXT2, wrap=True)
    conn_lay.addWidget(scan_result)
    _shadow(conn_card)
    lay.addWidget(conn_card)

    def _save_conn():
        data = _cfg.load()
        data["remote_last_host"] = ip_input.text().strip()
        data["remote_last_user"] = user_input.text().strip() or "seeed"
        data["remote_last_password"] = pass_input.text()
        data["remote_last_sudo_password"] = sudo_input.text()
        data["remote_last_subnet"] = subnet_input.text().strip()
        _cfg.save(data)

    for w in (ip_input, user_input, pass_input, subnet_input):
        w.editingFinished.connect(_save_conn)

    scan_holder = [None]
    ssh_holder = [None]

    def _scan_done(hosts):
        scan_btn.setEnabled(True)
        scan_btn.setText(_tt("remote.conn.btn.scan"))
        if hosts:
            scan_result.setText(_tt("remote.scan.found_prefix") + "  |  ".join(hosts))
            ip_input.setText(hosts[0])
            _save_conn()
        else:
            scan_result.setText(_tt("remote.scan.no_hosts"))

    def _do_scan():
        if scan_holder[0] and scan_holder[0].isRunning():
            return
        scan_btn.setEnabled(False)
        scan_btn.setText(_tt("remote.conn.btn.scanning"))
        scan_result.setText(_tt("remote.scan.scanning_lan"))
        t_scan = _ScanThread(subnet_input.text().strip() or None)
        t_scan.found.connect(_scan_done)
        t_scan.progress.connect(lambda s, total: scan_result.setText(_tt("remote.scan.progress", scanned=s, total=total)))
        t_scan.start()
        scan_holder[0] = t_scan

    scan_btn.clicked.connect(_do_scan)

    def _ssh_done(ok: bool, err: str):
        ssh_btn.setEnabled(True)
        ssh_btn.setText(_tt("remote.conn.btn.connect"))
        ip = ip_input.text().strip()
        user = user_input.text().strip() or "seeed"
        pwd = pass_input.text()
        if ok:
            conn_status.setText(_tt("remote.conn.status.connected"))
            conn_status.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(11)}px; background:transparent; font-weight:700;")
            _save_conn()
            set_runner(SSHRunner(ip, username=user, password=pwd, sudo_password=sudo_input.text().strip() or pwd))
            bus.device_connected.emit({"ip": ip, "name": "Jetson", "model": ""})
        else:
            conn_status.setText(_tt("remote.conn.status.failed"))
            conn_status.setStyleSheet(f"color:{C_RED}; font-size:{_pt(11)}px; background:transparent; font-weight:700;")
            conn_status.setToolTip(err)
            set_runner(None)
            bus.device_disconnected.emit(ip)

    def _do_ssh():
        ip = ip_input.text().strip()
        if not ip:
            _show_warning_message(page, _tt("common.notice"), _tt("remote.conn.warn.ip_required"))
            return
        ssh_btn.setEnabled(False)
        ssh_btn.setText(_tt("remote.conn.btn.connecting"))
        conn_status.setText(_tt("remote.conn.status.checking"))
        conn_status.setStyleSheet(f"color:{C_TEXT3}; font-size:{_pt(11)}px; background:transparent;")
        t_ssh = _SSHCheckThread(ip, user_input.text().strip() or "seeed", pass_input.text())
        t_ssh.result.connect(_ssh_done)
        t_ssh.start()
        ssh_holder[0] = t_ssh

    ssh_btn.clicked.connect(_do_ssh)

    init_card = _card(12)
    init_lay = QVBoxLayout(init_card)
    init_lay.setContentsMargins(24, 20, 24, 20)
    init_lay.setSpacing(14)
    init_title = _lbl(_tt("remote.init.title"), 15, C_TEXT, bold=True)
    init_status = QLabel(_tt("remote.init.status.waiting"))
    init_status.setStyleSheet(f"color:{C_TEXT3}; font-size:{_pt(11)}px; background:transparent;")
    init_head = QHBoxLayout()
    init_head.addWidget(init_title)
    init_head.addStretch()
    init_head.addWidget(init_status)
    init_lay.addLayout(init_head)
    init_desc = _lbl(_tt("remote.init.desc"), 11, C_TEXT3, wrap=True)
    init_lay.addWidget(init_desc)
    init_ports = _lbl("", 11, C_TEXT2, wrap=True)
    init_hint = _lbl("", 10, C_TEXT3, wrap=True)
    init_lay.addWidget(init_ports)
    init_lay.addWidget(init_hint)
    init_port_holder = [""]
    init_terminal_btn = _btn(_tt("remote.init.btn.terminal"), primary=True, small=True)
    init_net_btn = _btn(_tt("remote.init.btn.net_config"), small=True)
    init_share_btn = _btn(_tt("remote.init.btn.net_share"), small=True)
    init_btn_row = QHBoxLayout()
    init_btn_row.addWidget(init_terminal_btn)
    init_btn_row.addWidget(init_net_btn)
    init_btn_row.addWidget(init_share_btn)
    init_btn_row.addStretch()
    init_lay.addLayout(init_btn_row)
    _shadow(init_card)
    lay.addWidget(init_card)

    def _refresh_init():
        ports = list_serial_ports()
        init_port_holder[:] = ports[:]
        if ports:
            preview = " / ".join(ports[:3]) + (" ..." if len(ports) > 3 else "")
            init_status.setText(_tt("remote.init.status.port_found"))
            init_status.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(11)}px; background:transparent; font-weight:700;")
            init_ports.setText(_tt("remote.init.ports.detected", count=len(ports), preview=preview))
            init_hint.setText(_tt("remote.init.ports.hint", port=ports[0]))
            init_terminal_btn.setEnabled(True)
        else:
            init_status.setText(_tt("remote.init.status.no_port"))
            init_status.setStyleSheet(f"color:{C_ORANGE}; font-size:{_pt(11)}px; background:transparent; font-weight:700;")
            init_ports.setText(_tt("remote.init.ports.none"))
            init_hint.setText(_tt("remote.init.ports.none_hint"))
            init_terminal_btn.setEnabled(False)

    _refresh_init()
    init_terminal_btn.clicked.connect(lambda: open_jetson_init_dialog(parent=page, preferred_port=init_port_holder[0], auto_open_terminal=True))
    init_net_btn.clicked.connect(lambda: open_jetson_net_config_dialog(parent=page))
    init_share_btn.clicked.connect(lambda: open_net_share_dialog(parent=page, jetson_ip=ip_input.text().strip()))

    tools_card = _card(12)
    tools_lay = QVBoxLayout(tools_card)
    tools_lay.setContentsMargins(24, 20, 24, 20)
    tools_lay.setSpacing(14)
    tools_title = _lbl(_tt("remote.tools.title"), 15, C_TEXT, bold=True)
    tools_lay.addWidget(tools_title)
    tool_defs = [
        ("🔵", "remote.tools.vscode_ssh.name", "remote.tools.vscode_ssh.desc", "remote.tools.vscode_ssh.note", "remote.tools.vscode_ssh.action", "vscode_ssh"),
        ("🌐", "remote.tools.vscode_web.name", "remote.tools.vscode_web.desc", "remote.tools.vscode_web.note", "remote.tools.vscode_web.action", "vscode_web"),
        ("🤖", "remote.tools.claude_api.name", "remote.tools.claude_api.desc", "remote.tools.claude_api.note", "remote.tools.claude_api.action", "claude_api"),
        ("📓", "remote.tools.jupyter.name", "remote.tools.jupyter.desc", "remote.tools.jupyter.note", "remote.tools.jupyter.action", "jupyter"),
        ("🖼", "remote.tools.remote_desktop.name", "remote.tools.remote_desktop.desc", "remote.tools.remote_desktop.note", "remote.tools.remote_desktop.action", "remote_desktop"),
        ("🤖", "remote.tools.agent_install.name", "remote.tools.agent_install.desc", "remote.tools.agent_install.note", "remote.tools.agent_install.action", "agent_install"),
    ]
    tool_widgets = []
    api_test_holder = [None]

    def _add_tool(icon, name_key, desc_key, note_key, action_key, tid):
        row = _input_card(10)
        row.setStyleSheet(f"background:{C_CARD_LIGHT}; border:none; border-radius:10px;")
        rl = QHBoxLayout(row)
        ic = QLabel(icon)
        ic.setFixedWidth(_pt(40))
        rl.addWidget(ic)
        info = QVBoxLayout()
        name_lbl = _lbl(_tt(name_key), 13, C_TEXT, bold=True)
        desc_lbl = _lbl(_tt(desc_key), 11, C_TEXT2)
        note_lbl = _lbl(_tt(note_key), 10, C_TEXT3)
        info.addWidget(name_lbl)
        info.addWidget(desc_lbl)
        info.addWidget(note_lbl)
        rl.addLayout(info, 1)
        btn = _btn(_tt(action_key), primary=True, small=True)
        rl.addWidget(btn)
        tool_widgets.append((name_lbl, desc_lbl, note_lbl, btn, name_key, desc_key, note_key, action_key, tid))
        btn.clicked.connect(lambda checked=False: _on_tool_click(tid, name_key, btn))
        tools_lay.addWidget(row)

    def _on_tool_click(tid: str, name_key: str, btn):
        runner = get_runner()
        if tid == "vscode_ssh":
            dlg = _VscodeSSHDialog(ip=ip_input.text().strip(), parent=page)
            _apply_dlg_lang(dlg, page)
            dlg.exec_()
            return
        if tid in ("vscode_web", "jupyter", "remote_desktop", "agent_install") and not isinstance(runner, SSHRunner):
            _show_need_connection_dialog(page, _tt(name_key))
            return
        if tid == "vscode_web":
            dlg = _VscodeWebDialog(runner=runner, ip=runner.host, parent=page)
            _apply_dlg_lang(dlg, page)
            dlg.exec_()
        elif tid == "jupyter":
            dlg = _JupyterLaunchDialog(runner=runner, ip=runner.host, parent=page)
            _apply_dlg_lang(dlg, page)
            dlg.exec_()
        elif tid == "remote_desktop":
            open_desktop_dialog(runner=runner, ip=runner.host, parent=page)
        elif tid == "agent_install":
            open_agent_install_dialog(runner=runner, parent=page)
        elif tid == "claude_api":
            runtime = _get_runtime_anthropic_settings()
            key = runtime["api_key"]
            if not key:
                _show_warning_message(page, _tt("common.notice"), _tt("remote.api.warn.configure_first"))
                return
            btn.setEnabled(False)
            btn.setText(_tt("remote.tools.claude_api.testing"))
            t_api = _ApiTestThread(key, runtime["base_url"])
            t_api.result.connect(lambda ok, msg: _on_api_test_result(ok, msg, btn))
            t_api.start()
            api_test_holder[0] = t_api

    def _on_api_test_result(ok: bool, msg: str, btn):
        btn.setEnabled(True)
        btn.setText(_tt("remote.tools.claude_api.action"))
        if ok:
            _show_info_message(page, _tt("remote.api_test.title"), _tt("remote.api_test.ok", model=msg))
        else:
            _show_error_message(page, _tt("remote.api_test.fail_title"), msg)

    for definition in tool_defs:
        _add_tool(*definition)

    _shadow(tools_card)
    lay.addWidget(tools_card)
    lay.addStretch()

    def _refresh_tool_texts():
        for n, d, no, b, nk, dk, nok, bk, tid in tool_widgets:
            n.setText(_tt(nk))
            d.setText(_tt(dk))
            no.setText(_tt(nok))
            if tid != "claude_api" or b.isEnabled():
                b.setText(_tt(bk))

    page.i18n.bind_callable(lambda: page.set_header_text(_tt("remote.page.title"), _tt("remote.page.subtitle")))
    page.i18n.bind_text(api_title, "remote.api.title")
    page.i18n.bind_text(api_desc, "remote.api.desc")
    page.i18n.bind_text(api_btn, "remote.api.btn.configure")
    page.i18n.bind_text(conn_title, "remote.conn.title")
    page.i18n.bind_text(ip_label, "remote.conn.ip_label")
    page.i18n.bind_placeholder(ip_input, "remote.conn.ip_placeholder")
    page.i18n.bind_text(user_label, "remote.conn.username")
    page.i18n.bind_text(pass_label, "remote.conn.password")
    page.i18n.bind_placeholder(pass_input, "remote.conn.password_placeholder")
    page.i18n.bind_text(sudo_label, "remote.conn.sudo_password")
    page.i18n.bind_placeholder(sudo_input, "remote.conn.sudo_placeholder")
    page.i18n.bind_text(sudo_hint, "remote.conn.sudo_hint")
    page.i18n.bind_text(subnet_label, "remote.conn.subnet")
    page.i18n.bind_text(init_title, "remote.init.title")
    page.i18n.bind_text(init_desc, "remote.init.desc")
    page.i18n.bind_text(init_terminal_btn, "remote.init.btn.terminal")
    page.i18n.bind_text(init_net_btn, "remote.init.btn.net_config")
    page.i18n.bind_text(init_share_btn, "remote.init.btn.net_share")
    page.i18n.bind_text(tools_title, "remote.tools.title")
    page.i18n.bind_callable(_refresh_tool_texts)
    page.i18n.bind_callable(_refresh_api_status)
    page.i18n.bind_callable(_refresh_init)
    page.i18n.bind_callable(lambda: scan_btn.setText(_tt("remote.conn.btn.scan")) if scan_btn.isEnabled() else None)
    page.i18n.bind_callable(lambda: ssh_btn.setText(_tt("remote.conn.btn.connect")) if ssh_btn.isEnabled() else None)

    def _retranslate_ui(lang=None):
        page.i18n.apply(lang)

    page.retranslate_ui = _retranslate_ui
    return page


def _open_api_dialog(page: QWidget, on_saved):
    dlg = _ApiKeyDialog(parent=page)
    dlg.key_saved.connect(on_saved)
    _apply_dlg_lang(dlg, page)
    dlg.exec_()
