"""Device management page with info cards, quick diagnostics, and peripheral checks."""
from __future__ import annotations

import json
import shlex

from qtpy.QtCore import Qt, QThread, Signal, QTimer
from qtpy.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QDialog, QTextEdit,
    QLineEdit, QFormLayout, QDialogButtonBox, QSizePolicy,
)

from seeed_jetson_develop.core.runner import Runner, SSHRunner, SerialRunner, get_runner
from seeed_jetson_develop.core.events import bus
from seeed_jetson_develop.gui.i18n import get_language, t
from seeed_jetson_develop.gui.runtime_i18n import apply_dialog_language as _apply_dlg_lang
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, make_input_card as _input_card,
    apply_shadow as _shadow, DropdownButton, input_qss,
    show_warning_message as _show_warning_message,
)
from seeed_jetson_develop.core.platform_detect import is_jetson
from seeed_jetson_develop.modules.remote.jetson_init import open_jetson_init_dialog
from .diagnostics import DIAG_ITEMS, PERIPH_ITEMS, run_all, run_periph, collect_info
from .torch_install_support import (
    TorchProfile, TorchTarget,
    select_profiles_for_l4t, compatible_targets_for_profile, build_install_commands,
)
from seeed_jetson_develop.gui.widgets.page_base import PageBase

COLOR_MAP = {
    "ok":    C_GREEN,
    "warn":  C_ORANGE,
    "error": C_RED,
    "info":  C_BLUE,
}

_DIAG_NAME_KEYS = {
    "network": "devices.diag.network",
    "torch": "devices.diag.torch",
    "docker": "devices.diag.docker",
    "jtop": "devices.diag.jtop",
    "camera": "devices.diag.camera",
    "disk": "devices.diag.disk",
}

_PERIPH_NAME_KEYS = {
    "usb_wifi": "devices.periph.usb_wifi",
    "5g": "devices.periph.5g",
    "bluetooth": "devices.periph.bluetooth",
    "nvme": "devices.periph.nvme",
    "cam_dev": "devices.periph.cam_dev",
    "hdmi": "devices.periph.hdmi",
}

_STATUS_KEYS = {
    "Normal": "devices.status.ok",
    "Unreachable": "devices.status.unreachable",
    "CUDA Available": "devices.status.cuda_ok",
    "CPU Only": "devices.status.cpu_only",
    "Not Installed": "devices.status.not_installed",
    "Installed": "devices.status.installed",
    "Running": "devices.status.running",
    "Not Running": "devices.status.not_running",
    "Detected": "devices.status.detected",
    "Connected": "devices.status.connected",
    "Disconnected": "devices.status.disconnected",
    "Check Failed": "devices.status.check_failed",
    "Not Detected": "devices.status.not_detected",
}


def _lang() -> str:
    return get_language()


def _tt(key: str, **kwargs) -> str:
    fallbacks = {
        "devices.torch_install.probing": "Probing Python / conda environments on Jetson...",
        "devices.torch_install.no_profile": "No compatible PyTorch profile found for this Jetson release.",
        "devices.torch_install.no_target": "No Python target matching Python {py} was found. Install conda first or create a compatible environment.",
        "devices.torch_install.target_hint": "Install target: {target}",
    }
    text = t(key, lang=_lang(), **kwargs)
    if text == key:
        text = fallbacks.get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except Exception:
                pass
    return text


def _display_status(status: str) -> str:
    if status in _STATUS_KEYS:
        return _tt(_STATUS_KEYS[status])
    import re as _re
    m = _re.match(r'^Found (\d+)$', status)
    if m:
        return _tt("devices.status.found_n", count=m.group(1))
    return status


# Serial credential dialog.
class _SerialCredDialog(QDialog):
    """Prompt for serial credentials when SSH runner is unavailable."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lang = get_language()
        self.setWindowTitle(t("devices.serial_cred.title", lang=lang))
        self.setMinimumWidth(_pt(380))
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        lay.addWidget(_lbl(t("devices.serial_cred.description", lang=lang), 12, C_TEXT2, wrap=True))

        form = QFormLayout()
        form.setSpacing(10)

        # Serial port selection.
        self.port_combo = DropdownButton(max_popup_height=_pt(200))
        self.port_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._refresh_ports()
        refresh_btn = _btn(t("devices.serial_cred.refresh", lang=lang), small=True)
        refresh_btn.clicked.connect(self._refresh_ports)
        port_row = QHBoxLayout()
        port_row.addWidget(self.port_combo, 1)
        port_row.addWidget(refresh_btn)
        port_widget = QWidget()
        port_widget.setLayout(port_row)
        form.addRow(_lbl(t("devices.serial_cred.port", lang=lang), 12, C_TEXT2), port_widget)

        # Username.
        self.user_edit = QLineEdit("seeed")
        self.user_edit.setStyleSheet(input_qss(radius=6, font_size=12))
        form.addRow(_lbl(t("devices.serial_cred.username", lang=lang), 12, C_TEXT2), self.user_edit)

        # Password.
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setPlaceholderText(t("devices.serial_cred.password_placeholder", lang=lang))
        self.pass_edit.setStyleSheet(input_qss(radius=6, font_size=12))
        form.addRow(_lbl(t("devices.serial_cred.password", lang=lang), 12, C_TEXT2), self.pass_edit)

        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText(t("common.ok", lang=lang))
        btns.button(QDialogButtonBox.Cancel).setText(t("common.cancel", lang=lang))
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _refresh_ports(self):
        try:
            import serial.tools.list_ports
            ports = sorted(p.device for p in serial.tools.list_ports.comports())
        except Exception:
            ports = []
        current = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(ports or [""])
        if current in ports:
            self.port_combo.setCurrentText(current)

    def get_runner(self) -> SerialRunner | None:
        port = self.port_combo.currentText().strip()
        user = self.user_edit.text().strip() or "seeed"
        pwd  = self.pass_edit.text()
        if not port:
            return None
        return SerialRunner(port=port, username=user, password=pwd)




def _status_tag(text=None, color=C_TEXT3) -> QLabel:
    if text is None:
        text = _tt("devices.status.pending")
    """Status tag with borderless style."""
    l = QLabel(text)
    l.setStyleSheet(f"""
        background: {C_CARD_LIGHT};
        color: {color};
        border-radius: 6px;
        padding: 4px 12px;
        font-size: {_pt(11)}pt;
        font-weight: 500;
    """)
    l.setAlignment(Qt.AlignCenter)
    return l


# Background diagnostic thread.
class _DiagThread(QThread):
    result   = Signal(str, str, str)   # item_id, status_text, color_key
    info_ready = Signal(dict)          # Device info dictionary.
    finished_all = Signal()

    def __init__(self, mode="full", runner: Runner = None):
        super().__init__()
        self._runner = runner if runner is not None else get_runner()
        self._mode = mode

    def run(self):
        if self._mode in ("full", "info"):
            info = collect_info(self._runner)
            self.info_ready.emit(info)
        if self._mode in ("full", "diag"):
            run_all(self._runner, lambda id, st, co: self.result.emit(id, st, co))
        if self._mode in ("full", "periph"):
            run_periph(self._runner, lambda id, st, co: self.result.emit(id, st, co))
        self.finished_all.emit()


class _InstallThread(QThread):
    log = Signal(str)
    done = Signal(bool)

    def __init__(self, commands: list[str]):
        super().__init__()
        self._commands = commands
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        runner = get_runner()
        for cmd in self._commands:
            if self._cancel:
                self.log.emit(f"⚠ {_tt('devices.torch_install.cancelled')}")
                self.done.emit(False)
                return
            self.log.emit(f"\n$ {cmd}")
            rc, _ = runner.run(cmd, timeout=3600, on_output=lambda l: self.log.emit(l))
            if rc != 0:
                self.log.emit(f"\n✖ {_tt('devices.torch_install.cmd_failed', rc=rc)}")
                self.done.emit(False)
                return
        self.done.emit(True)


# PyTorch install dialog.
class _TorchInstallDialog(QDialog):
    install_succeeded = Signal()

    def __init__(self, l4t: str, parent=None):
        super().__init__(parent)
        self._l4t = l4t
        self._thread = None
        self._targets: list[TorchTarget] = []
        self._profiles: list[TorchProfile] = select_profiles_for_l4t(l4t)
        self._commands: list[str] = []
        self._conda_bin = ""
        lang = get_language()
        self.setWindowTitle(t("devices.torch_install.title", lang=lang))
        self.setMinimumSize(_pt(640), _pt(480))
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")

        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── 可滚动主体 ──
        from qtpy.QtWidgets import QScrollArea
        from qtpy.QtCore import Qt
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(24, 20, 24, 12)
        lay.setSpacing(16)
        scroll.setWidget(inner)
        root_lay.addWidget(scroll, 1)

        # Version hint.
        jp = "JetPack 6.x (R36)" if "R36" in l4t else "JetPack 5.x (R35)"
        info_row = QHBoxLayout()
        info_row.addWidget(_lbl(t("devices.torch_install.detected", lang=lang, jp=jp), 12, C_TEXT2))
        info_row.addStretch()
        lay.addLayout(info_row)

        self._profile_combo = DropdownButton(max_popup_height=_pt(220))
        self._profile_combo.currentTextChanged.connect(lambda _text: self._refresh_target_options())
        lay.addWidget(_lbl("PyTorch / TorchVision", 12, C_TEXT2))
        lay.addWidget(self._profile_combo)

        self._target_combo = DropdownButton(max_popup_height=_pt(220))
        self._target_combo.currentTextChanged.connect(lambda _text: self._refresh_preview())
        lay.addWidget(_lbl("Python Target", 12, C_TEXT2))
        lay.addWidget(self._target_combo)

        self._env_hint = _lbl("", 11, C_TEXT3, wrap=True)
        lay.addWidget(self._env_hint)

        # Command preview.
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setFixedHeight(_pt(120))
        preview.setStyleSheet(f"""
            background:{C_CARD_LIGHT};
            border:none;
            border-radius:10px;
            color:{C_TEXT2};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(11)}px;
            padding:12px;
        """)
        preview.setPlainText(_tt("devices.torch_install.probing"))
        lay.addWidget(preview)
        self._preview = preview

        # Log area.
        lay.addWidget(_lbl(t("devices.torch_install.log_label", lang=lang), 12, C_TEXT2))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(f"""
            background:{C_CARD};
            border:none;
            border-radius:10px;
            color:{C_GREEN};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(11)}px;
            padding:12px;
        """)
        self._log.setMinimumHeight(_pt(160))
        lay.addWidget(self._log, 1)
        lay.addStretch()

        # ── 底部按钮栏（固定，不随滚动） ──
        btn_frame = QWidget()
        btn_frame.setStyleSheet(f"background:{C_BG}; border-top:1px solid rgba(255,255,255,0.06);")
        btn_row = QHBoxLayout(btn_frame)
        btn_row.setContentsMargins(24, 12, 24, 16)
        btn_row.setSpacing(12)
        root_lay.addWidget(btn_frame)

        # Button row.
        self._start_btn = _btn(t("devices.torch_install.start_btn", lang=lang), primary=True)
        self._stop_btn  = _btn(t("devices.torch_install.stop_btn", lang=lang))
        self._stop_btn.setEnabled(False)
        self._bg_btn    = _btn(t("common.run_in_background", lang=lang))
        self._bg_btn.setEnabled(False)
        close_btn = _btn(t("common.close", lang=lang))
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addWidget(self._bg_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)

        self._start_btn.clicked.connect(self._start)
        self._stop_btn.clicked.connect(self._stop)
        self._bg_btn.clicked.connect(self._send_to_background)
        close_btn.clicked.connect(self.close)
        self._start_btn.setEnabled(False)
        self._task_handle = None
        self._probe_targets()

    def showEvent(self, event):
        super().showEvent(event)
        from qtpy.QtWidgets import QApplication
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

    def _append(self, text: str):
        from qtpy.QtGui import QTextCursor
        self._log.moveCursor(QTextCursor.End)
        self._log.insertPlainText(text + "\n")
        self._log.ensureCursorVisible()

    def _probe_targets(self):
        runner = get_runner()
        probe = r"""python3 - <<'PY'
import json, os, pathlib, shutil, subprocess
def probe(exe):
    code = 'import json,sys\\nresult={\"py\":f\"{sys.version_info[0]}.{sys.version_info[1]}\",\"torch\":\"\",\"torchvision\":\"\",\"cuda\":\"\"}\\ntry:\\n import torch\\n result[\"torch\"]=getattr(torch,\"__version__\",\"\")\\n result[\"cuda\"]=str(bool(torch.cuda.is_available()))\\nexcept Exception:\\n pass\\ntry:\\n import torchvision\\n result[\"torchvision\"]=getattr(torchvision,\"__version__\",\"\")\\nexcept Exception:\\n pass\\nprint(json.dumps(result))'
    p = subprocess.run([exe, '-c', code], text=True, capture_output=True)
    if p.returncode != 0:
        return None
    try:
        return json.loads((p.stdout or p.stderr or '').strip().splitlines()[-1])
    except Exception:
        return None
targets=[]; seen=set(); conda_bin=''
for c in ['python3','python3.8','python3.10','python3.11','python3.12','/usr/bin/python3','/usr/bin/python3.8','/usr/bin/python3.10','/usr/local/bin/python3','/usr/local/bin/python3.8','/usr/local/bin/python3.10']:
    exe = c if c.startswith('/') else (shutil.which(c) or '')
    if not exe or not pathlib.Path(exe).exists():
        continue
    meta = probe(exe)
    if not meta or ('python', exe) in seen:
        continue
    seen.add(('python', exe))
    targets.append({'id':f'python:{exe}','label':f'System {exe} (Python {meta.get(\"py\", \"\")})','kind':'python','python_version':meta.get('py',''),'python_cmd':exe,'installed_torch':meta.get('torch',''),'installed_torchvision':meta.get('torchvision',''),'cuda_available':meta.get('cuda','')})
for c in [shutil.which('conda') or '', os.path.expanduser('~/miniconda3/bin/conda'), os.path.expanduser('~/anaconda3/bin/conda'), os.path.expanduser('~/miniforge3/bin/conda'), os.path.expanduser('~/mambaforge/bin/conda'), '/opt/conda/bin/conda', '/usr/local/conda/bin/conda']:
    if c and pathlib.Path(c).exists():
        conda_bin = c
        break
if conda_bin:
    p = subprocess.run([conda_bin, 'env', 'list', '--json'], text=True, capture_output=True)
    envs = json.loads(p.stdout or '{}').get('envs', []) if p.returncode == 0 else []
    for env_path in envs:
        env_path = pathlib.Path(env_path)
        env_name = env_path.name
        exe = env_path / 'bin' / 'python3'
        if not exe.exists():
            exe = env_path / 'bin' / 'python'
        if not exe.exists():
            continue
        meta = probe(str(exe))
        if not meta or ('conda', env_name) in seen:
            continue
        seen.add(('conda', env_name))
        targets.append({'id':f'conda:{env_name}','label':f'Conda {env_name} (Python {meta.get(\"py\", \"\")})','kind':'conda','python_version':meta.get('py',''),'python_cmd':str(exe),'conda_bin':conda_bin,'env_name':env_name,'installed_torch':meta.get('torch',''),'installed_torchvision':meta.get('torchvision',''),'cuda_available':meta.get('cuda','')})
print(json.dumps({'conda_bin': conda_bin, 'targets': targets}))
PY"""
        rc, out = runner.run(probe, timeout=90)
        payload = {}
        if rc == 0 and out.strip():
            try:
                payload = json.loads(out.splitlines()[-1])
            except Exception:
                payload = {}
        self._conda_bin = str(payload.get("conda_bin", ""))
        self._targets = [TorchTarget(**item) for item in payload.get("targets", [])]
        self._profile_combo.clear()
        for profile in self._profiles:
            self._profile_combo.addItem(profile.label, profile)
        if self._profiles:
            self._profile_combo.setCurrentIndex(0)
        else:
            self._preview.setPlainText(_tt("devices.torch_install.no_profile"))

    def _current_profile(self) -> TorchProfile | None:
        return self._profile_combo.currentData()

    def _current_target(self) -> TorchTarget | None:
        return self._target_combo.currentData()

    def _refresh_target_options(self):
        profile = self._current_profile()
        self._target_combo.clear()
        if profile is None:
            self._start_btn.setEnabled(False)
            return
        compatible = compatible_targets_for_profile(self._targets, profile, self._conda_bin)
        for target in compatible:
            self._target_combo.addItem(target.label, target)
        if compatible:
            self._target_combo.setCurrentIndex(0)
        else:
            self._env_hint.setText(_tt("devices.torch_install.no_target", py=profile.python_version))
            self._preview.setPlainText(_tt("devices.torch_install.no_target", py=profile.python_version))
            self._start_btn.setEnabled(False)

    def _refresh_preview(self):
        profile = self._current_profile()
        target = self._current_target()
        if profile is None or target is None:
            self._start_btn.setEnabled(False)
            return
        self._commands = build_install_commands(profile, target)
        installed = []
        if target.installed_torch:
            installed.append(f"torch={target.installed_torch}")
        if target.installed_torchvision:
            installed.append(f"torchvision={target.installed_torchvision}")
        if target.cuda_available:
            installed.append(f"cuda={target.cuda_available}")
        extra = f" ({', '.join(installed)})" if installed else ""
        self._env_hint.setText(_tt("devices.torch_install.target_hint", target=target.label + extra))
        self._preview.setPlainText("\n".join(f"$ {c}" for c in self._commands))
        self._start_btn.setEnabled(True)

    def _start(self):
        from seeed_jetson_develop.gui.widgets.running_tasks import task_registry
        self._log.clear()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._bg_btn.setEnabled(True)
        self._cmd_step = 0
        self._cmd_total = len(self._commands)
        t = _InstallThread(self._commands)
        t.log.connect(self._append)
        t.log.connect(self._on_log_line)
        t.done.connect(self._on_done)
        t.start()
        self._thread = t
        profile = self._current_profile()
        name = "PyTorch install"
        if profile is not None:
            name = f"PyTorch {profile.torch_version.split('+')[0].split('a')[0]}"
        self._task_handle = task_registry.register(
            name=name,
            on_restore=self._restore_from_background,
            on_cancel=self._cancel_from_tray,
            sub_text=f"Step 1/{self._cmd_total}",
        )

    def _on_log_line(self, line: str):
        if not self._task_handle:
            return
        line = (line or "").strip()
        if line.startswith("$ "):
            self._cmd_step += 1
            from seeed_jetson_develop.gui.widgets.running_tasks import task_registry
            task_registry.update(
                self._task_handle.task_id,
                sub_text=f"Step {self._cmd_step}/{self._cmd_total}",
            )

    def _stop(self):
        if self._thread:
            self._thread.cancel()

    def _cancel_from_tray(self):
        """Called when user clicks ✕ on the sidebar tray row."""
        if self._thread and self._thread.isRunning():
            self._thread.cancel()

    def _send_to_background(self):
        if not (self._thread and self._thread.isRunning()):
            return
        self.hide()

    def _restore_from_background(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        # If task is still running, do not actually close — send to background so
        # the install keeps running and stays visible in the sidebar tray.
        if self._thread and self._thread.isRunning():
            self.hide()
            event.ignore()
            return
        # Task finished; if a tray entry is lingering (e.g. failed state), drop it.
        if self._task_handle:
            from seeed_jetson_develop.gui.widgets.running_tasks import task_registry
            task_registry.remove(self._task_handle.task_id)
            self._task_handle = None
        super().closeEvent(event)

    def _on_done(self, success: bool):
        from seeed_jetson_develop.gui.widgets.running_tasks import task_registry
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._bg_btn.setEnabled(False)
        if success:
            self._append(f"\n✅ {_tt('devices.torch_install.success')}")
            self.install_succeeded.emit()
            if self._task_handle:
                task_registry.update(
                    self._task_handle.task_id, status="success", sub_text="done — click to view"
                )
        else:
            self._append(f"\n❌ {_tt('devices.torch_install.failed')}")
            if self._task_handle:
                task_registry.update(
                    self._task_handle.task_id, status="failed", sub_text="failed — click to view"
                )


# Main page.
class DevicesPage(PageBase):
    """Device management page."""

    def __init__(self):
        self._thread = None
        self._info_cards: dict = {}
        self._info_caption_labels: dict = {}
        self._sys_caption_labels: dict = {}
        self._diag_name_labels: dict = {}
        self._periph_name_labels: dict = {}
        self._status_state: dict[str, tuple[str, str]] = {}
        self._diag_tags: dict = {}
        self._periph_tags: dict = {}
        self._sys_labels: dict = {}
        self._torch_install_btn = None
        self._l4t_ver = "R36"
        self._init_btn = None
        self._run_btn = None
        self._diag_only_btn = None
        self._periph_only_btn = None
        self._diag_title_lbl = None
        self._diag_desc_lbl = None
        self._periph_title_lbl = None

        super().__init__(
            title=_tt("devices.page.title"),
            subtitle=_tt("devices.page.subtitle"),
        )
        self._build_header_btns()
        self._build_content()
        bus.device_connected.connect(lambda: self._start("full", silent_no_runner=True))
        self._start("info", silent_no_runner=True)

    def _build_header_btns(self):
        self._init_btn = _btn(_tt("devices.btn.init"), small=True)
        self._init_btn.clicked.connect(lambda: open_jetson_init_dialog(parent=self))
        self.add_header_widget(self._init_btn)
        self._run_btn = _btn(_tt("devices.btn.run_all"), primary=True, small=True)
        self._run_btn.clicked.connect(lambda: self._start("full"))
        self.add_header_widget(self._run_btn)

    def _build_content(self):
        lay = self.get_content_layout()

        # 1. Device info cards (2x2 grid).
        info_grid = QGridLayout()
        info_grid.setSpacing(16)
        info_grid.setColumnStretch(0, 1)
        info_grid.setColumnStretch(1, 1)
        for idx, (key, icon, label_key) in enumerate([
            ("model",  "🖥",  "devices.info.model"),
            ("l4t",    "🔖", "devices.info.l4t"),
            ("memory", "🧠", "devices.info.memory"),
            ("ip",     "🌐", "devices.info.ip"),
        ]):
            c = _card(10)
            cl = QVBoxLayout(c)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(6)
            cl.addWidget(_lbl(icon, 20))

            if key == "ip":
                # Scrollable multi-line IP list
                from qtpy.QtWidgets import QScrollArea
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QScrollArea.NoFrame)
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                scroll.setFixedHeight(_pt(72))
                scroll.setStyleSheet("background:transparent; border:none;")
                ip_container = QWidget()
                ip_container.setStyleSheet("background:transparent;")
                ip_layout = QVBoxLayout(ip_container)
                ip_layout.setContentsMargins(0, 0, 0, 0)
                ip_layout.setSpacing(2)
                scroll.setWidget(ip_container)
                val_lbl = _lbl("—", 13, C_TEXT2, bold=False)
                val_lbl.setWordWrap(True)
                ip_layout.addWidget(val_lbl)
                ip_layout.addStretch()
                # Store both the scroll container layout and the placeholder label
                self._info_cards[key] = val_lbl
                self._info_cards["_ip_layout"] = ip_layout
                cl.addWidget(scroll, 1)
            else:
                val_lbl = _lbl("—", 14, C_TEXT2, bold=False)
                val_lbl.setWordWrap(True)
                cl.addWidget(val_lbl)
                self._info_cards[key] = val_lbl

            cap_lbl = _lbl(_tt(label_key), 11, C_TEXT3)
            cl.addWidget(cap_lbl)
            self._info_caption_labels[key] = cap_lbl
            _shadow(c, blur=16)
            info_grid.addWidget(c, idx // 2, idx % 2)
        lay.addLayout(info_grid)

        # 2. Quick diagnostics card.
        diag_card = _card(12)
        dc_lay = QVBoxLayout(diag_card)
        dc_lay.setContentsMargins(20, 18, 20, 18)
        dc_lay.setSpacing(14)
        dh = QHBoxLayout()
        self._diag_title_lbl = _lbl(_tt("devices.section.quick_diag"), 15, C_TEXT, bold=True)
        dh.addWidget(self._diag_title_lbl)
        dh.addStretch()
        self._diag_only_btn = _btn(_tt("devices.btn.diag_only"), small=True)
        self._diag_only_btn.clicked.connect(lambda: self._start("diag"))
        dh.addWidget(self._diag_only_btn)
        dc_lay.addLayout(dh)
        self._diag_desc_lbl = _lbl(_tt("devices.section.quick_diag_desc"), 12, C_TEXT3)
        dc_lay.addWidget(self._diag_desc_lbl)
        for item in DIAG_ITEMS:
            row = _input_card(8)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 10, 14, 10)
            rl.addWidget(_lbl(item.icon, 16))
            name_lbl = _lbl(_tt(_DIAG_NAME_KEYS.get(item.id, "devices.diag.network")), 13, C_TEXT)
            self._diag_name_labels[item.id] = name_lbl
            rl.addWidget(name_lbl)
            rl.addStretch()
            if item.id == "torch":
                inst_btn = _btn(_tt("devices.btn.install_torch"), small=True)
                inst_btn.hide()
                inst_btn.clicked.connect(self._open_torch_install)
                rl.addWidget(inst_btn)
                rl.addSpacing(10)
                self._torch_install_btn = inst_btn
            tag = _status_tag(_tt("devices.status.pending"))
            self._diag_tags[item.id] = tag
            rl.addWidget(tag)
            dc_lay.addWidget(row)
        _shadow(diag_card)
        lay.addWidget(diag_card)

        # 3. Peripheral status card.
        periph_card = _card(12)
        pc_lay = QVBoxLayout(periph_card)
        pc_lay.setContentsMargins(20, 18, 20, 18)
        pc_lay.setSpacing(14)
        ph = QHBoxLayout()
        self._periph_title_lbl = _lbl(_tt("devices.section.peripherals"), 15, C_TEXT, bold=True)
        ph.addWidget(self._periph_title_lbl)
        ph.addStretch()
        self._periph_only_btn = _btn(_tt("devices.btn.periph_only"), small=True)
        self._periph_only_btn.clicked.connect(lambda: self._start("periph"))
        ph.addWidget(self._periph_only_btn)
        pc_lay.addLayout(ph)
        periph_grid = QGridLayout()
        periph_grid.setSpacing(12)
        periph_grid.setColumnStretch(0, 1)
        periph_grid.setColumnStretch(1, 1)
        periph_grid.setColumnStretch(2, 1)
        for i, item in enumerate(PERIPH_ITEMS):
            c = _card(8)
            cl = QVBoxLayout(c)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(6)
            name_lbl = _lbl(f"{item.icon}  {_tt(_PERIPH_NAME_KEYS.get(item.id, 'devices.periph.usb_wifi'))}", 12, C_TEXT)
            self._periph_name_labels[item.id] = name_lbl
            cl.addWidget(name_lbl)
            tag = _status_tag(_tt("devices.status.pending"))
            self._periph_tags[item.id] = tag
            cl.addWidget(tag)
            periph_grid.addWidget(c, i // 3, i % 3)
        pc_lay.addLayout(periph_grid)
        _shadow(periph_card)
        lay.addWidget(periph_card)

        # 4. Storage and temperature row.
        sys_card = _card(10)
        sc_lay = QHBoxLayout(sys_card)
        sc_lay.setContentsMargins(20, 14, 20, 14)
        sc_lay.setSpacing(40)
        for key, icon, label_key in [("storage", "💾", "devices.info.storage"), ("temp", "🌡️", "devices.info.temp")]:
            pair = QHBoxLayout()
            pair.setSpacing(8)
            pair.addWidget(_lbl(icon, 16))
            cap_lbl = _lbl(_tt(label_key) + ":", 12, C_TEXT2)
            pair.addWidget(cap_lbl)
            self._sys_caption_labels[key] = cap_lbl
            val = _lbl("—", 12, C_TEXT)
            self._sys_labels[key] = val
            pair.addWidget(val)
            sc_lay.addLayout(pair)
        sc_lay.addStretch()
        _shadow(sys_card)
        lay.addWidget(sys_card)
        lay.addStretch()

    # Thread control.

    def _set_all_running(self, mode="full"):
        _checking = _tt("devices.status.checking")
        self._run_btn.setEnabled(False)
        self._run_btn.setText(_checking)
        if mode in ("full", "diag"):
            self._diag_only_btn.setEnabled(False)
            for t in self._diag_tags.values():
                t.setText(_checking)
                t.setStyleSheet(f"color:{C_TEXT3}; background:{C_CARD_LIGHT}; border-radius:6px; padding:4px 12px; font-size:{_pt(11)}px;")
        if mode in ("full", "periph"):
            self._periph_only_btn.setEnabled(False)
            for t in self._periph_tags.values():
                t.setText(_checking)
                t.setStyleSheet(f"color:{C_TEXT3}; background:{C_CARD_LIGHT}; border-radius:6px; padding:4px 12px; font-size:{_pt(11)}px;")

    def _reset_buttons(self):
        self._run_btn.setEnabled(True)
        self._run_btn.setText(_tt("devices.btn.run_all"))
        self._diag_only_btn.setEnabled(True)
        self._periph_only_btn.setEnabled(True)

    def _on_result(self, item_id: str, status: str, color_key: str):
        self._status_state[item_id] = (status, color_key)
        color = COLOR_MAP.get(color_key, C_TEXT2)
        tag = self._diag_tags.get(item_id) or self._periph_tags.get(item_id)
        if tag:
            tag.setText(_display_status(status))
            normal_bg = C_CARD_LIGHT
            flash_bg = {
                "ok":    "rgba(141,194,31,0.18)",
                "warn":  "rgba(245,166,35,0.18)",
                "error": "rgba(229,62,62,0.18)",
            }.get(color_key, C_CARD_LIGHT)
            # 先闪烁高亮背景
            tag.setStyleSheet(f"""
                background: {flash_bg}; color: {color};
                border-radius: 6px; padding: 4px 12px;
                font-size: {_pt(11)}px; font-weight: 500;
            """)
            # 150ms 后恢复常态背景
            from qtpy.QtCore import QTimer
            QTimer.singleShot(150, lambda t=tag, c=color: t.setStyleSheet(f"""
                background: {normal_bg}; color: {c};
                border-radius: 6px; padding: 4px 12px;
                font-size: {_pt(11)}px; font-weight: 500;
            """))
        if item_id == "torch" and self._torch_install_btn:
            if color_key in ("error", "warn"):
                self._torch_install_btn.show()
            else:
                self._torch_install_btn.hide()

    def _on_info(self, info: dict):
        for key, lbl in self._info_cards.items():
            if key.startswith("_"):
                continue
            if key == "ip":
                # Render each "iface ip" line as a separate label in the scroll container
                ip_layout = self._info_cards.get("_ip_layout")
                if ip_layout is not None:
                    # Remove previously-inserted row widgets, but keep the original
                    # placeholder lbl (index 0) and the trailing stretch — deleting the
                    # placeholder leaves a dangling QLabel reference that crashes on the
                    # next _on_info call.
                    for i in reversed(range(ip_layout.count())):
                        item = ip_layout.itemAt(i)
                        w = item.widget() if item else None
                        if w is not None and w is not lbl:
                            ip_layout.takeAt(i)
                            w.deleteLater()
                    raw = info.get("ip", "—").strip()
                    lines = [l.strip() for l in raw.splitlines() if l.strip()] if raw != "—" else []
                    if lines:
                        lbl.hide()
                        for line in lines:
                            parts = line.split()
                            if len(parts) >= 2:
                                iface, ip = parts[0], parts[1]
                                row_w = QWidget()
                                row_w.setStyleSheet("background:transparent;")
                                row_l = QHBoxLayout(row_w)
                                row_l.setContentsMargins(0, 0, 0, 0)
                                row_l.setSpacing(8)
                                ip_lbl = _lbl(ip, 13, C_TEXT)
                                ip_lbl.setStyleSheet(f"color:{C_TEXT}; font-size:{_pt(13)}px; background:transparent; font-weight:600;")
                                iface_lbl = _lbl(iface, 10, C_TEXT3)
                                iface_lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:{_pt(10)}px; background:transparent;")
                                row_l.addWidget(ip_lbl)
                                row_l.addWidget(iface_lbl)
                                row_l.addStretch()
                                ip_layout.insertWidget(ip_layout.count() - 1, row_w)
                    else:
                        lbl.setText("—")
                        lbl.setStyleSheet(f"color:{C_TEXT}; font-size:{_pt(13)}px; background:transparent; font-weight:600;")
                        lbl.show()
            else:
                lbl.setText(info.get(key, "—"))
                lbl.setStyleSheet(f"color:{C_TEXT}; font-size:{_pt(14)}px; background:transparent; font-weight:600;")
        for key, lbl in self._sys_labels.items():
            lbl.setText(info.get(key, "—"))
        self._l4t_ver = info.get("l4t", "R36")

    def _start(self, mode="full", silent_no_runner=False):
        if self._thread and self._thread.isRunning():
            return
        current_runner = get_runner()
        if not isinstance(current_runner, SSHRunner):
            if silent_no_runner:
                return
            dlg = _SerialCredDialog(parent=self)
            _apply_dlg_lang(dlg, self)
            if dlg.exec_() != QDialog.Accepted:
                return
            runner_to_use = dlg.get_runner()
            if runner_to_use is None:
                return
        else:
            runner_to_use = current_runner
        self._set_all_running(mode)
        t = _DiagThread(mode, runner=runner_to_use)
        t.result.connect(self._on_result)
        t.info_ready.connect(self._on_info)
        t.finished_all.connect(self._reset_buttons)
        t.start()
        self._thread = t

    def _open_torch_install(self):
        if not (is_jetson() or isinstance(get_runner(), SSHRunner)):
            _show_warning_message(
                self,
                _tt("devices.torch_install.title"),
                "PyTorch 安装命令需要在 Jetson 设备上运行。\n请先在 Remote 页面 SSH 连接到 Jetson 后再试。\n\n"
                "Installing PyTorch requires running on a Jetson device. "
                "Please connect to a Jetson via SSH (Remote page) first.",
            )
            return
        dlg = _TorchInstallDialog(self._l4t_ver, parent=self)
        dlg.install_succeeded.connect(lambda: self._start("diag"))
        _apply_dlg_lang(dlg, self)
        dlg.exec_()

    def retranslate_ui(self, _lang_code: str | None = None):
        self.set_header_text(_tt("devices.page.title"), _tt("devices.page.subtitle"))
        if self._init_btn:
            self._init_btn.setText(_tt("devices.btn.init"))
        if self._run_btn:
            self._run_btn.setText(_tt("devices.btn.run_all"))
        if self._diag_only_btn:
            self._diag_only_btn.setText(_tt("devices.btn.diag_only"))
        if self._periph_only_btn:
            self._periph_only_btn.setText(_tt("devices.btn.periph_only"))
        if self._diag_title_lbl:
            self._diag_title_lbl.setText(_tt("devices.section.quick_diag"))
        if self._diag_desc_lbl:
            self._diag_desc_lbl.setText(_tt("devices.section.quick_diag_desc"))
        if self._periph_title_lbl:
            self._periph_title_lbl.setText(_tt("devices.section.peripherals"))
        for item in DIAG_ITEMS:
            lbl = self._diag_name_labels.get(item.id)
            if lbl:
                lbl.setText(_tt(_DIAG_NAME_KEYS.get(item.id, "devices.diag.network")))
        for item in PERIPH_ITEMS:
            lbl = self._periph_name_labels.get(item.id)
            if lbl:
                lbl.setText(f"{item.icon}  {_tt(_PERIPH_NAME_KEYS.get(item.id, 'devices.periph.usb_wifi'))}")
        for key, lbl in self._info_caption_labels.items():
            label_key = {
                "model": "devices.info.model",
                "l4t": "devices.info.l4t",
                "memory": "devices.info.memory",
                "ip": "devices.info.ip",
            }.get(key)
            if label_key:
                lbl.setText(_tt(label_key))
        for key, lbl in self._sys_caption_labels.items():
            label_key = {"storage": "devices.info.storage", "temp": "devices.info.temp"}.get(key)
            if label_key:
                lbl.setText(_tt(label_key) + ":")
        if self._torch_install_btn:
            self._torch_install_btn.setText(_tt("devices.btn.install_torch"))
        for item_id, tag in {**self._diag_tags, **self._periph_tags}.items():
            if item_id in self._status_state:
                status, color_key = self._status_state[item_id]
                color = COLOR_MAP.get(color_key, C_TEXT2)
                tag.setText(_display_status(status))
                tag.setStyleSheet(
                    f"background: {C_CARD_LIGHT}; color: {color};"
                    " border-radius: 6px; padding: 4px 12px;"
                    f" font-size: {_pt(11)}px; font-weight: 500;"
                )
            else:
                tag.setText(_tt("devices.status.pending"))


def build_page() -> QWidget:
    return DevicesPage()
