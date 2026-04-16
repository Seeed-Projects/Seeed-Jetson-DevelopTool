"""Remote desktop dialog."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

from seeed_jetson_develop.core.runner import SSHRunner
from seeed_jetson_develop.gui.i18n_binding import I18nBinding
from seeed_jetson_develop.gui.i18n import get_language, t
from seeed_jetson_develop.gui.theme import (
    C_BG,
    C_CARD_LIGHT,
    C_GREEN,
    C_ORANGE,
    C_RED,
    C_TEXT,
    C_TEXT2,
    C_TEXT3,
    apply_shadow,
    make_button,
    make_card,
    make_label,
    pt,
    show_info_message,
)
from seeed_jetson_develop.modules.remote import desktop_remote as dr


def _tt(key: str, **kwargs) -> str:
    return t(key, lang=get_language(), **kwargs)


class _SshCmdThread(QThread):
    line_out = pyqtSignal(str)
    finished_ = pyqtSignal(int, str)

    def __init__(self, runner: SSHRunner, commands: list[tuple[str, int]]):
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


class _StatusThread(QThread):
    result = pyqtSignal(dict)

    def __init__(self, runner: SSHRunner):
        super().__init__()
        self._runner = runner

    def run(self):
        self.result.emit(
            {
                "vnc_installed": dr.check_vnc_installed(self._runner),
                "novnc_installed": dr.check_novnc_installed(self._runner),
                "vnc_running": dr.check_vnc_running(self._runner)[0],
                "vnc_pid": dr.check_vnc_running(self._runner)[1],
                "novnc_running": dr.check_novnc_running(self._runner)[0],
                "novnc_pid": dr.check_novnc_running(self._runner)[1],
            }
        )


class DesktopRemoteDialog(QDialog):
    def __init__(self, runner: SSHRunner, ip: str, parent=None):
        super().__init__(parent)
        self._runner = runner
        self._ip = ip
        self._thread: _SshCmdThread | None = None
        self._status_thread: _StatusThread | None = None
        self._i18n = I18nBinding()
        self._last_status: dict | None = None

        self.setWindowTitle(_tt("remote.desktop.title"))
        self.setMinimumSize(pt(680), pt(560))
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        self._header_lbl = make_label(_tt("remote.desktop.header"), 16, C_TEXT, bold=True)
        root.addWidget(self._header_lbl)
        self._desc_lbl = make_label(_tt("remote.desktop.desc", ip=ip), 11, C_TEXT2, wrap=True)
        root.addWidget(self._desc_lbl)

        status_card = make_card(12)
        apply_shadow(status_card, blur=18, y=4, alpha=60)
        sc = QVBoxLayout(status_card)
        sc.setContentsMargins(18, 16, 18, 16)
        sc.setSpacing(10)
        self._service_status_lbl = make_label(_tt("remote.desktop.service_status"), 13, C_TEXT, bold=True)
        sc.addWidget(self._service_status_lbl)

        vnc_row = QHBoxLayout()
        self._vnc_service_lbl = make_label(_tt("remote.desktop.vnc_service"), 12, C_TEXT2)
        vnc_row.addWidget(self._vnc_service_lbl)
        self._vnc_status = make_label(_tt("remote.desktop.status.checking"), 12, C_TEXT3)
        vnc_row.addWidget(self._vnc_status)
        vnc_row.addStretch()
        sc.addLayout(vnc_row)

        novnc_row = QHBoxLayout()
        self._novnc_service_lbl = make_label(_tt("remote.desktop.novnc_service"), 12, C_TEXT2)
        novnc_row.addWidget(self._novnc_service_lbl)
        self._novnc_status = make_label(_tt("remote.desktop.status.checking"), 12, C_TEXT3)
        novnc_row.addWidget(self._novnc_status)
        novnc_row.addStretch()
        sc.addLayout(novnc_row)

        addr_row = QHBoxLayout()
        self._browser_access_lbl = make_label(_tt("remote.desktop.browser_access"), 11, C_TEXT3)
        addr_row.addWidget(self._browser_access_lbl)
        self._novnc_url = make_label(dr.format_novnc_url(ip), 11, C_GREEN)
        self._novnc_url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        addr_row.addWidget(self._novnc_url)
        addr_row.addSpacing(20)
        self._vnc_direct_lbl = make_label(_tt("remote.desktop.vnc_direct"), 11, C_TEXT3)
        addr_row.addWidget(self._vnc_direct_lbl)
        self._vnc_addr = make_label(dr.format_vnc_address(ip), 11, C_TEXT2)
        self._vnc_addr.setTextInteractionFlags(Qt.TextSelectableByMouse)
        addr_row.addWidget(self._vnc_addr)
        addr_row.addStretch()
        sc.addLayout(addr_row)

        # VNC password is unified with login password; hide manual input to reduce confusion.
        self._vnc_password_lbl = make_label(_tt("remote.desktop.vnc_password"), 11, C_TEXT3)
        self._vnc_password_lbl.setVisible(False)
        self._vnc_pwd = QLineEdit()
        self._vnc_pwd.setVisible(False)
        root.addWidget(status_card)

        op_row = QHBoxLayout()
        op_row.setSpacing(10)
        self._deploy_btn = make_button(_tt("remote.desktop.btn.deploy"), primary=True, small=True)
        self._stop_btn = make_button(_tt("remote.desktop.btn.stop"), small=True)
        self._refresh_btn = make_button(_tt("remote.desktop.btn.refresh"), small=True)
        op_row.addWidget(self._deploy_btn)
        op_row.addWidget(self._stop_btn)
        op_row.addWidget(self._refresh_btn)
        op_row.addStretch()
        root.addLayout(op_row)

        access_row = QHBoxLayout()
        access_row.setSpacing(10)
        self._open_browser_btn = make_button(_tt("remote.desktop.btn.open_browser"), primary=True, small=True)
        self._open_vnc_btn = make_button(_tt("remote.desktop.btn.open_vnc"), small=True)
        access_row.addWidget(self._open_browser_btn)
        access_row.addWidget(self._open_vnc_btn)
        access_row.addStretch()
        root.addLayout(access_row)

        log_card = make_card(12)
        ll = QVBoxLayout(log_card)
        ll.setContentsMargins(18, 14, 18, 14)
        ll.setSpacing(8)
        self._log_title_lbl = make_label(_tt("remote.desktop.log"), 12, C_TEXT, bold=True)
        ll.addWidget(self._log_title_lbl)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(pt(120))
        self._log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._log.setStyleSheet(
            f"QTextEdit {{ background:{C_CARD_LIGHT}; border:none; border-radius:8px;"
            f" color:{C_TEXT2}; padding:10px; font-size:{pt(10)}px; }}"
        )
        ll.addWidget(self._log)
        root.addWidget(log_card, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        self._close_btn = make_button(_tt("common.close"))
        self._close_btn.clicked.connect(self.accept)
        close_row.addWidget(self._close_btn)
        root.addLayout(close_row)

        self._deploy_btn.clicked.connect(self._do_deploy_all)
        self._stop_btn.clicked.connect(self._do_stop)
        self._refresh_btn.clicked.connect(self._do_refresh)
        self._open_vnc_btn.clicked.connect(self._do_open_vnc)
        self._open_browser_btn.clicked.connect(self._do_open_browser)
        self._bind_i18n()
        self._do_refresh()

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

    def _bind_i18n(self):
        self._i18n.bind_text(self._header_lbl, "remote.desktop.header")
        self._i18n.bind_text(self._desc_lbl, "remote.desktop.desc", ip=lambda: self._ip)
        self._i18n.bind_text(self._service_status_lbl, "remote.desktop.service_status")
        self._i18n.bind_text(self._vnc_service_lbl, "remote.desktop.vnc_service")
        self._i18n.bind_text(self._novnc_service_lbl, "remote.desktop.novnc_service")
        self._i18n.bind_text(self._browser_access_lbl, "remote.desktop.browser_access")
        self._i18n.bind_text(self._vnc_direct_lbl, "remote.desktop.vnc_direct")
        self._i18n.bind_text(self._vnc_password_lbl, "remote.desktop.vnc_password")
        self._i18n.bind_placeholder(self._vnc_pwd, "remote.desktop.vnc_password_placeholder")
        self._i18n.bind_text(self._deploy_btn, "remote.desktop.btn.deploy")
        self._i18n.bind_text(self._stop_btn, "remote.desktop.btn.stop")
        self._i18n.bind_text(self._refresh_btn, "remote.desktop.btn.refresh")
        self._i18n.bind_text(self._open_browser_btn, "remote.desktop.btn.open_browser")
        self._i18n.bind_text(self._open_vnc_btn, "remote.desktop.btn.open_vnc")
        self._i18n.bind_text(self._log_title_lbl, "remote.desktop.log")
        self._i18n.bind_text(self._close_btn, "common.close")
        self._i18n.bind_callable(lambda: self.setWindowTitle(_tt("remote.desktop.title")))

    def retranslate_ui(self, lang: str | None = None):
        self._i18n.apply(lang)
        if self._last_status is not None:
            self._on_status(self._last_status)

    def _append(self, line: str):
        self._log.append(line)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _do_refresh(self):
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText(_tt("remote.desktop.status.checking"))
        self._vnc_status.setText(_tt("remote.desktop.status.checking"))
        self._novnc_status.setText(_tt("remote.desktop.status.checking"))
        self._status_thread = _StatusThread(self._runner)
        self._status_thread.result.connect(self._on_status)
        self._status_thread.start()

    def _on_status(self, s: dict):
        self._last_status = s
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText(_tt("remote.desktop.btn.refresh"))
        if s["vnc_running"]:
            self._vnc_status.setText(_tt("remote.desktop.status.running_pid", pid=s["vnc_pid"]))
            self._vnc_status.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(12)}px; font-weight:700; background:transparent;")
        elif s["vnc_installed"]:
            self._vnc_status.setText(_tt("remote.desktop.status.installed_not_running"))
            self._vnc_status.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(12)}px; background:transparent;")
        else:
            self._vnc_status.setText(_tt("remote.desktop.status.not_installed"))
            self._vnc_status.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}px; background:transparent;")

        if s["novnc_running"]:
            self._novnc_status.setText(_tt("remote.desktop.status.running_pid", pid=s["novnc_pid"]))
            self._novnc_status.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(12)}px; font-weight:700; background:transparent;")
        elif s["novnc_installed"]:
            self._novnc_status.setText(_tt("remote.desktop.status.installed_not_running"))
            self._novnc_status.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(12)}px; background:transparent;")
        else:
            self._novnc_status.setText(_tt("remote.desktop.status.not_installed"))
            self._novnc_status.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(12)}px; background:transparent;")

    def _do_deploy_all(self):
        pwd = self._runner.sudo_password
        vnc_pwd = self._runner.password or self._runner.sudo_password
        self._append("[info] VNC password is unified with login password.")
        cmds = [
            (dr.build_enable_autologin_cmd(pwd, self._runner.username), 30),
            (dr.build_install_vnc_cmd(pwd), 180),
            (dr.build_prepare_vnc_password_cmd(vnc_pwd), 20),
            (dr.build_write_headless_xvfb_unit_cmd(self._runner.username), 20),
            (dr.build_write_headless_session_unit_cmd(self._runner.username), 20),
            (dr.build_write_x11vnc_unit_cmd(self._runner.username), 20),
            (dr.build_write_novnc_unit_cmd(), 20),
            (dr.build_install_enable_units_cmd(pwd), 60),
            (dr.build_install_novnc_cmd(pwd), 180),
            (dr.build_start_novnc_cmd(), 15),
        ]
        self._run_cmds(cmds, self._deploy_btn, _tt("remote.desktop.btn.deploy_short"), self._on_deploy_all_done)

    def _on_deploy_all_done(self, rc: int, out: str):
        self._deploy_btn.setEnabled(True)
        self._deploy_btn.setText(_tt("remote.desktop.btn.deploy"))
        if rc == 0:
            url = dr.format_novnc_url(self._ip)
            self._append(_tt("remote.desktop.deploy.success"))
            self._append(_tt("remote.desktop.deploy.autologin"))
            self._append(_tt("remote.desktop.deploy.browser", url=url))
            self._append(_tt("remote.desktop.deploy.vnc", addr=dr.format_vnc_address(self._ip)))
        else:
            self._append(_tt("remote.desktop.deploy.failed", rc=rc))
            self._append(_tt("remote.desktop.deploy.troubleshoot"))
            self._append(_tt("remote.desktop.deploy.tip1"))
            self._append(_tt("remote.desktop.deploy.tip2"))
            self._append(_tt("remote.desktop.deploy.tip3"))
            self._append(_tt("remote.desktop.deploy.tip4"))
            self._append(_tt("remote.desktop.deploy.tip5"))
            self._append(_tt("remote.desktop.deploy.tip6"))
            self._append("")
            self._append("Diagnostics:")
            self._append(f"$ {dr.build_diagnose_cmd()}")
            self._append("Rollback:")
            self._append(f"$ {dr.build_rollback_cmd(self._runner.sudo_password)}")
        self._do_refresh()

    def _do_stop(self):
        self._run_cmds([(dr.build_stop_cmd(), 10)], self._stop_btn, _tt("remote.desktop.btn.stop"), self._on_stop_done)

    def _on_stop_done(self, rc: int, out: str):
        self._stop_btn.setEnabled(True)
        self._stop_btn.setText(_tt("remote.desktop.btn.stop"))
        self._append(_tt("remote.desktop.stop.ok") if rc == 0 else _tt("remote.desktop.stop.failed", rc=rc))
        self._do_refresh()

    def _do_open_browser(self):
        url = dr.format_novnc_url(self._ip)
        dr.open_in_browser(url)
        self._append(_tt("remote.desktop.browser_opened", url=url))

    def _do_open_vnc(self):
        if dr.launch_vnc_viewer(self._ip):
            return
        show_info_message(
            self,
            _tt("remote.desktop.vnc_client.title"),
            _tt("remote.desktop.vnc_client.body", addr=dr.format_vnc_address(self._ip)),
        )

    def _run_cmds(self, cmds, btn, label, callback):
        btn.setEnabled(False)
        btn.setText(_tt("remote.desktop.btn.running", label=label))
        self._log.clear()
        self._thread = _SshCmdThread(self._runner, cmds)
        self._thread.line_out.connect(self._append)
        self._thread.finished_.connect(callback)
        self._thread.start()


def open_desktop_dialog(runner: SSHRunner, ip: str, parent=None):
    dlg = DesktopRemoteDialog(runner, ip, parent)
    dlg.exec_()
