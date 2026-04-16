"""App marketplace page."""
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QDialog, QTextEdit, QMessageBox, QSizePolicy,
)

from seeed_jetson_develop.core.runner import Runner, SSHRunner, get_runner
from seeed_jetson_develop.core.events import bus
from seeed_jetson_develop.core.platform_detect import is_jetson
from seeed_jetson_develop.gui.i18n import get_language, t


def _at(key: str, **kwargs) -> str:
    return t(key, lang=get_language(), **kwargs)


def _can_execute_from_current_env(parent: QWidget) -> bool:
    if is_jetson() or isinstance(get_runner(), SSHRunner):
        return True
    _show_info_message(
        parent,
        _at("apps.msg.remote_required.title"),
        _at("apps.msg.remote_required.body"),
    )
    return False


from seeed_jetson_develop.modules.apps.registry import load_apps
from seeed_jetson_develop.gui.runtime_i18n import apply_dialog_language as _apply_dlg_lang
from seeed_jetson_develop.gui.widgets.list_page_base import ListPageBase
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, make_input_card as _input_card,
    apply_shadow as _shadow,
    show_error_message as _show_error_message,
    show_info_message as _show_info_message,
    show_warning_message as _show_warning_message,
)


def _ask_yes_no_localized(parent: QWidget, title: str, text: str) -> int:
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Question)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

    def _apply_btn_text():
        yes_btn = msg.button(QMessageBox.Yes)
        no_btn = msg.button(QMessageBox.No)
        if yes_btn is not None:
            yes_btn.setText(_at("common.yes"))
            yes_btn.setAutoDefault(False)
            yes_btn.setDefault(False)
        if no_btn is not None:
            no_btn.setText(_at("common.no"))
            no_btn.setAutoDefault(False)
            no_btn.setDefault(False)

    _apply_btn_text()
    # Qt 在 exec_() 初始化时可能重置按钮文字，延迟再设置一次保证生效
    QTimer.singleShot(0, _apply_btn_text)
    return msg.exec_()


class _ResponsiveScrollArea(QScrollArea):
    def __init__(self, *args, on_resize=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_resize = on_resize
        self._resize_timer = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._on_resize:
            # Debounce list rebuild on resize.
            from PyQt5.QtCore import QTimer
            if self._resize_timer:
                self._resize_timer.stop()
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._on_resize)
            self._resize_timer.start(100)


# Background install status detection thread
class _StatusCheckThread(QThread):
    single_result = pyqtSignal(str, str)   # app_id, status
    all_done      = pyqtSignal(dict)

    def __init__(self, apps: list[dict]):
        super().__init__()
        self._apps = apps

    def run(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        runner = get_runner()
        results = {}
        if not isinstance(runner, SSHRunner):
            self.all_done.emit(results)
            return

        def _check(app):
            cmd = app.get("check_cmd")
            if not cmd:
                return app["id"], None
            rc, _ = runner.run(cmd, timeout=6)
            return app["id"], "installed" if rc == 0 else "available"

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(_check, a): a for a in self._apps}
            for fut in as_completed(futures):
                app_id, status = fut.result()
                if status is not None:
                    results[app_id] = status
                    self.single_result.emit(app_id, status)

        self.all_done.emit(results)


# App install thread
class _InstallThread(QThread):
    log  = pyqtSignal(str)
    done = pyqtSignal(bool)

    def __init__(self, cmds: list[str], app: dict | None = None):
        super().__init__()
        self._cmds   = cmds
        self._app    = app or {}
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        runner = get_runner()
        # For Depth Anything V3 custom docker flow, upload launcher script only when commands require it.
        needs_da3_launcher_upload = any(
            "run_camera_depth_rtsp.sh" in (c or "") for c in self._cmds
        )
        if (
            isinstance(runner, SSHRunner)
            and self._app.get("id") == "jx-depth-anything-v3"
            and needs_da3_launcher_upload
        ):
            try:
                import base64
                import shlex
                from pathlib import Path
                remote_asset_dir = "$HOME/.seeed_da3_assets"
                remote_script_path = f"{remote_asset_dir}/run_camera_depth_rtsp.sh"
                local_script = (
                    Path(__file__).resolve().parents[3]
                    / "depth_anything_v3"
                    / "depth_anything_v3"
                    / "assets"
                    / "jetson"
                    / "run_camera_depth_rtsp.sh"
                )
                if not local_script.exists():
                    self.log.emit(f"[failed] missing local script: {local_script}")
                    self.done.emit(False)
                    return
                rc, _ = runner.run(f"mkdir -p {remote_asset_dir}", timeout=20)
                if rc != 0:
                    self.log.emit(f"[failed] cannot create {remote_asset_dir} on remote")
                    self.done.emit(False)
                    return
                # Recover from a bad previous state where the target file path became a directory.
                runner.run(
                    "bash -lc 'set -e; "
                    f"if [ -d {remote_script_path} ]; then "
                    f"rm -rf {remote_script_path}; "
                    "fi'",
                    timeout=20,
                )
                upload_ok = False
                try:
                    client, sftp = runner.open_sftp()
                    try:
                        sftp.put(str(local_script), remote_script_path)
                        upload_ok = True
                    finally:
                        try:
                            sftp.close()
                        except Exception:
                            pass
                        client.close()
                except Exception as sftp_err:
                    self.log.emit(
                        f"[warn] sftp upload failed ({type(sftp_err).__name__}: {sftp_err}), trying ssh fallback..."
                    )
                    encoded = base64.b64encode(local_script.read_bytes()).decode("ascii")
                    fallback_cmd = (
                        "set -e; "
                        f"mkdir -p {remote_asset_dir}; "
                        f"if [ -d {remote_script_path} ]; then "
                        f"rm -rf {remote_script_path}; "
                        "fi; "
                        "command -v base64 >/dev/null 2>&1 || { echo base64-not-found; exit 1; }; "
                        f"printf '%s' {shlex.quote(encoded)} | base64 -d > {remote_script_path}; "
                        f"chmod +x {remote_script_path}; "
                        f"test -s {remote_script_path}"
                    )
                    rc, out = runner.run(f"bash -lc {shlex.quote(fallback_cmd)}", timeout=90)
                    if rc == 0:
                        upload_ok = True
                        self.log.emit("[ok] uploaded run_camera_depth_rtsp.sh via ssh fallback")
                    else:
                        self.log.emit(f"[failed] fallback upload rc={rc}: {out}")
                        self.done.emit(False)
                        return
                if not upload_ok:
                    self.log.emit("[failed] upload did not complete")
                    self.done.emit(False)
                    return
                rc, _ = runner.run(f"chmod +x {remote_script_path}", timeout=10)
                if rc != 0:
                    self.log.emit("[failed] chmod launcher script failed")
                    self.done.emit(False)
                    return
                self.log.emit(f"[ok] uploaded run_camera_depth_rtsp.sh to {remote_asset_dir}")
            except Exception as e:
                self.log.emit(f"[failed] upload depth_anything_v3 assets failed: {type(e).__name__}: {e}")
                self.done.emit(False)
                return

        for cmd in self._cmds:
            if self._cancel:
                self.log.emit("Cancelled")
                self.done.emit(False)
                return
            self.log.emit(f"\n$ {cmd}")
            rc, _ = runner.run(cmd, timeout=600, on_output=lambda l: self.log.emit(l))
            if rc != 0:
                self.log.emit(f"[failed] rc={rc}")
                self.log.emit(f"\nCommand failed (rc={rc})")
                self.done.emit(False)
                return
            self.log.emit(f"[ok] rc={rc}")
        self.done.emit(True)


# Install / uninstall dialog
class _InstallDialog(QDialog):
    install_done = pyqtSignal(str, bool)

    def __init__(self, app: dict, cmds: list[str], parent=None, mode: str = "install"):
        super().__init__(parent)
        self._app    = app
        self._cmds   = cmds
        self._thread = None
        self._mode   = mode  # "install" or "uninstall"

        title_map = {
            "install": _at("apps.action.install"),
            "uninstall": _at("apps.action.uninstall"),
            "run": _at("apps.action.run"),
            "clean": _at("apps.action.clean"),
        }
        title = title_map.get(mode, _at("apps.action.execute"))
        self.setWindowTitle(f"{title}  {app['name']}")
        self.setMinimumSize(_pt(640), _pt(480))
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")

        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── 可滚动主体 ──
        from PyQt5.QtWidgets import QScrollArea
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

        # App info row
        info_row = QHBoxLayout()
        info_row.addWidget(_lbl(app["icon"], 32))
        info_row.addSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(4)
        from seeed_jetson_develop.gui.runtime_i18n import get_current_lang, translate_text as _tr
        _lang = get_current_lang(parent)
        col.addWidget(_lbl(_tr(app["name"], _lang), 15, C_TEXT, bold=True))
        col.addWidget(_lbl(_tr(app["desc"], _lang), 12, C_TEXT2, wrap=True))
        info_row.addLayout(col, 1)
        lay.addLayout(info_row)

        # Step preview
        step_label = _at("apps.dialog.steps", action=title)
        lay.addWidget(_lbl(step_label, 12, C_TEXT3))
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
        preview.setPlainText("\n".join(f"$ {c}" for c in cmds))
        lay.addWidget(preview)

        # Log area
        log_label = _at("apps.dialog.log", action=title)
        lay.addWidget(_lbl(log_label, 12, C_TEXT3))
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        log_color = C_RED if mode == "uninstall" else C_GREEN
        self._log_edit.setStyleSheet(f"""
            background:{C_CARD};
            border:none;
            border-radius:10px;
            color:{log_color};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(11)}px;
            padding:12px;
        """)
        self._log_edit.setMinimumHeight(_pt(160))
        lay.addWidget(self._log_edit, 1)
        lay.addStretch()

        # ── 底部按钮栏（固定，不随滚动） ──
        btn_frame = QWidget()
        btn_frame.setStyleSheet(f"background:{C_BG}; border-top:1px solid rgba(255,255,255,0.06);")
        btn_frame_lay = QHBoxLayout(btn_frame)
        btn_frame_lay.setContentsMargins(24, 12, 24, 16)
        btn_frame_lay.setSpacing(12)
        root_lay.addWidget(btn_frame)

        # Action row
        btn_row = btn_frame_lay
        start_label = _at("apps.dialog.start_action", action=title)
        self._start_btn = _btn(start_label, primary=(mode in {"install", "run"}))
        if mode == "uninstall":
            self._start_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{C_RED};
                    color:#fff;
                    border:none;
                    border-radius:8px;
                    padding:8px 20px;
                    font-size:{_pt(12)}pt;
                    font-weight:600;
                }}
                QPushButton:hover {{ background:#c0392b; }}
                QPushButton:disabled {{ background:#555; color:#888; }}
            """)
        self._stop_btn  = _btn("■  Stop")
        self._stop_btn = _btn(_at("apps.dialog.stop"))
        self._stop_btn.setEnabled(False)
        close_btn = _btn(_at("common.close"))
        self._ai_btn = _btn(_at("common.ask_ai"), primary=False, small=True)
        self._ai_btn.setVisible(False)
        self._ai_btn.clicked.connect(self._ask_ai)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._ai_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(close_btn)

        self._start_btn.clicked.connect(self._start)
        self._stop_btn.clicked.connect(self._stop)
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

    def _append(self, text: str):
        from PyQt5.QtGui import QTextCursor
        self._log_edit.moveCursor(QTextCursor.End)
        self._log_edit.insertPlainText(text + "\n")
        self._log_edit.ensureCursorVisible()

    def _start(self):
        self._log_edit.clear()
        self._ai_btn.setVisible(False)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        t = _InstallThread(self._cmds, app=self._app)
        t.log.connect(self._append)
        t.done.connect(self._on_done)
        t.start()
        self._thread = t

    def _stop(self):
        if self._thread:
            self._thread.cancel()

    def _on_done(self, success: bool):
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        action_text = {
            "install": (_at("apps.dialog.done.install_ok"), _at("apps.dialog.done.install_fail")),
            "uninstall": (_at("apps.dialog.done.uninstall_ok"), _at("apps.dialog.done.uninstall_fail")),
            "run": (_at("apps.dialog.done.run_ok"), _at("apps.dialog.done.run_fail")),
            "clean": (_at("apps.dialog.done.clean_ok"), _at("apps.dialog.done.clean_fail")),
        }.get(self._mode, (_at("apps.dialog.done.exec_ok"), _at("apps.dialog.done.exec_fail")))
        if success:
            self._append(f"\n??{action_text[0]}")
        else:
            self._append(f"\n??{action_text[1]}")
            self._ai_btn.setVisible(True)
        self.install_done.emit(self._app["id"], success)

    def _ask_ai(self):
        host = self.parent().window() if self.parent() else None
        assistant = getattr(host, "_floating_ai", None)
        if assistant:
            log_text = self._log_edit.toPlainText()
            assistant.inject_error(self._app["name"], log_text)


# Main page
class AppsPage(ListPageBase):
    """App marketplace list page."""

    def __init__(self):
        self._statuses: dict[str, str] = {}
        self._device_meta: dict = {"l4t": None}
        self._check_thread = None
        self._status_labels: dict[str, QLabel] = {}  # app_id -> status QLabel for in-place updates
        self._banner_title_lbl: QLabel | None = None
        self._banner_sub_lbl: QLabel | None = None
        super().__init__()
        # Device connection event
        bus.device_connected.connect(lambda _: (self._device_meta.update({"l4t": None}), self._start_check()))
        QTimer.singleShot(200, self._start_check)

    def retranslate_ui(self, _lang_code: str | None = None):
        super().retranslate_ui(_lang_code)
        if self._banner_title_lbl is not None:
            self._banner_title_lbl.setText(_at("apps.banner.title"))
        self._update_banner_summary()
        for app_id, status in self._statuses.items():
            self._update_status_lbl(app_id, status)

    def _insert_intro_banner(self):
        content = self.get_content_layout()
        banner = _card(12)
        banner.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(122,179,23,0.10), stop:1 rgba(44,123,229,0.06));"
            "border: 1px solid rgba(255,255,255,0.05); border-radius:12px;"
        )
        row = QHBoxLayout(banner)
        row.setContentsMargins(20, 16, 20, 16)
        row.addWidget(_lbl("📦", 24))
        row.addSpacing(12)

        col = QVBoxLayout()
        col.setSpacing(4)
        self._banner_title_lbl = _lbl(_at("apps.banner.title"), 14, C_TEXT, bold=True)
        self._banner_sub_lbl = _lbl("", 11, C_TEXT3)
        col.addWidget(self._banner_title_lbl)
        col.addWidget(self._banner_sub_lbl)
        row.addLayout(col, 1)
        content.insertWidget(0, banner)

    def _update_banner_summary(self):
        if self._banner_sub_lbl is None:
            return
        total = len(self.items_data)
        installed = sum(1 for s in self._statuses.values() if s == "installed")
        checking = sum(1 for s in self._statuses.values() if s == "checking")
        self._banner_sub_lbl.setText(
            _at("apps.banner.summary", total=total, installed=installed, checking=checking)
        )

    # ListPageBase abstract methods

    def get_page_title(self) -> str:
        return t("apps.page.title", lang=get_language())

    def get_page_subtitle(self) -> str:
        return t("apps.page.subtitle", lang=get_language())

    def load_data(self) -> list:
        apps = load_apps()
        for a in apps:
            self._statuses[a["id"]] = "checking" if a.get("check_cmd") else "available"
        return apps

    def get_categories(self) -> list[str]:
        cats = ["All"]
        for a in self.items_data:
            cat = a.get("category") or "Other"
            if cat not in cats:
                cats.append(cat)
        cats.append("Installed")
        return cats

    def format_category_label(self, category: str) -> str:
        lang = get_language()
        if category == "All":
            return t("apps.category.all", lang=lang)
        if category == "Installed":
            return t("apps.category.installed", lang=lang)
        return category

    def filter_item(self, item: dict) -> bool:
        cat = self.filter_state["category"]
        kw = self.filter_state["search"].lower()
        cat_ok = (
            cat == "All"
            or (cat == "Installed" and self._statuses.get(item["id"]) == "installed")
            or item.get("category") == cat
        )
        kw_ok = not kw or any(
            kw in (item.get(f) or "").lower() for f in ("name", "desc", "id")
        )
        return cat_ok and kw_ok

    def build_item_widget(self, item: dict) -> QWidget:
        return self._build_row(item)

    # Status detection

    def _start_check(self):
        if self._check_thread and self._check_thread.isRunning():
            return
        if not isinstance(get_runner(), SSHRunner):
            for a in self.items_data:
                self._statuses[a["id"]] = "available"
            self._rebuild_list()
            self._update_banner_summary()
            return
        for a in self.items_data:
            if a.get("check_cmd"):
                self._statuses[a["id"]] = "checking"
        self._rebuild_list()
        self._update_banner_summary()
        t = _StatusCheckThread(self.items_data)
        t.single_result.connect(self._on_single_check)
        t.all_done.connect(self._on_check_done)
        t.start()
        self._check_thread = t

    def _on_single_check(self, app_id: str, status: str):
        self._statuses[app_id] = status
        self._update_status_lbl(app_id, status)  # In-place update without rebuilding list
        self._update_banner_summary()

    def _on_check_done(self, results: dict):
        for app_id, status in results.items():
            self._statuses[app_id] = status
        self._rebuild_list()
        self._update_banner_summary()

    # Command helpers

    def _get_cmds(self, app: dict) -> list[str]:
        skill_id = app.get("skill_id")
        if skill_id:
            try:
                from seeed_jetson_develop.modules.skills.engine import load_skills
                skill_map = {s.id: s for s in load_skills()}
                skill = skill_map.get(skill_id)
                if skill:
                    return skill.commands
            except Exception:
                import logging, traceback
                logging.getLogger("seeed").error(
                    "load skill '%s' failed:\n%s", skill_id, traceback.format_exc()
                )
        return app.get("install_cmds") or []

    def _get_run_cmds(self, app: dict) -> list[str]:
        return app.get("run_cmds") or []

    def _get_clean_cmds(self, app: dict) -> list[str]:
        return app.get("clean_cmds") or []

    def _get_ai_details(self, app: dict) -> list[str]:
        details = [f"Category: {app.get('category', '-')}"]
        req = app.get("requirements") or {}
        if req.get("jetpack_versions"):
            details.append(f"L4T：{', '.join(req['jetpack_versions'])}")
        if req.get("required_disk_gb") is not None:
            details.append(f"Disk: {req['required_disk_gb']}GB")
        if req.get("required_mem_gb") is not None:
            details.append(f"Memory: {req['required_mem_gb']}GB")
        cmds = self._get_cmds(app)
        run_cmds = self._get_run_cmds(app)
        if cmds and cmds != run_cmds:
            details.append("Install:")
            details.extend(cmds[:4])
        if run_cmds:
            details.append("Run:")
            details.extend(run_cmds[:2])
        return details

    # L4T compatibility checks

    def _get_current_l4t(self, force: bool = False) -> str:
        if self._device_meta["l4t"] and not force:
            return self._device_meta["l4t"]
        runner = get_runner()
        cmd = (
            "head -1 /etc/nv_tegra_release 2>/dev/null | "
            "awk '{gsub(\",\",\"\",$5); print $2\".\"$5}'"
        )
        rc, out = runner.run(cmd, timeout=5)
        l4t = (out or "").strip().splitlines()[-1].strip() if rc == 0 and (out or "").strip() else ""
        self._device_meta["l4t"] = l4t
        return l4t

    def _l4t_matches(self, current: str, allowed: str) -> bool:
        import re
        current = (current or "").strip()
        allowed = (allowed or "").strip()
        if not current or not allowed:
            return False
        # Normalize forms like "R36.4.4" to "36.4.4" for wildcard matching.
        current = re.sub(r"^[Rr]", "", current)
        allowed = re.sub(r"^[Rr]", "", allowed)
        if allowed.endswith(".x"):
            return current.startswith(allowed[:-1])
        return current == allowed

    def _ensure_l4t_compatible(self, app: dict) -> bool:
        req = app.get("requirements") or {}
        allowed = req.get("jetpack_versions") or []
        if not allowed:
            return True
        current_l4t = self._get_current_l4t()
        if not current_l4t:
            _show_info_message(
                self,
                _at("apps.msg.l4t_detect_failed.title"),
                _at("apps.msg.l4t_detect_failed.body", name=app["name"], versions=", ".join(allowed)),
            )
            return True
        if any(self._l4t_matches(current_l4t, v) for v in allowed):
            return True
        _show_warning_message(
            self,
            _at("apps.msg.l4t_incompatible.title"),
            _at("apps.msg.l4t_incompatible.body", name=app["name"], l4t=current_l4t, versions=", ".join(allowed)),
        )
        return False

    # Dialog operations

    def _open_dialog(self, app_id: str, mode: str, cmds: list[str], done_cb):
        import logging, traceback as _tb
        try:
            app = next((a for a in self.items_data if a["id"] == app_id), None)
            if not app:
                return
            if not _can_execute_from_current_env(self):
                return
            if not cmds:
                _show_info_message(
                    self,
                    _at("common.notice"),
                    _at("apps.msg.no_exec_cmd", name=app["name"]),
                )
                return
            dlg = _InstallDialog(app, cmds, parent=self, mode=mode)
            dlg.install_done.connect(done_cb)
            _apply_dlg_lang(dlg, self)
            dlg.exec_()
        except Exception:
            msg = _tb.format_exc()
            logging.getLogger("seeed").error("Failed to open app dialog:\n%s", msg)
            _show_error_message(
                self,
                _at("common.error"),
                _at("apps.msg.open_dialog_error", detail=msg[-600:]),
            )

    def _open_install(self, app_id: str):
        app = next(a for a in self.items_data if a["id"] == app_id)
        self._open_dialog(app_id, "install", self._get_cmds(app), self._on_install_done)

    def _open_run(self, app_id: str):
        app = next(a for a in self.items_data if a["id"] == app_id)
        if not self._ensure_l4t_compatible(app):
            return
        self._open_dialog(app_id, "run", self._get_run_cmds(app), self._on_run_done)

    def _open_clean(self, app_id: str):
        app = next((a for a in self.items_data if a["id"] == app_id), None)
        if not app:
            return
        ret = _ask_yes_no_localized(
            self,
            _at("apps.msg.confirm_clean.title"),
            _at("apps.msg.confirm_clean.body", name=app["name"]),
        )
        if ret == QMessageBox.Yes:
            self._open_dialog(app_id, "clean", self._get_clean_cmds(app), self._on_clean_done)

    def _open_uninstall(self, app_id: str):
        app = next((a for a in self.items_data if a["id"] == app_id), None)
        if not app:
            return
        cmds = app.get("uninstall_cmds") or []
        if not cmds:
            _show_info_message(
                self,
                _at("common.notice"),
                _at("apps.msg.no_uninstall_cmd", name=app["name"]),
            )
            return
        ret = _ask_yes_no_localized(
            self,
            _at("apps.msg.confirm_uninstall.title"),
            _at("apps.msg.confirm_uninstall.body", name=app["name"]),
        )
        if ret == QMessageBox.Yes:
            self._open_dialog(app_id, "uninstall", cmds, self._on_uninstall_done)

    def _on_install_done(self, app_id: str, success: bool):
        if success:
            self._statuses[app_id] = "installed"
            self._rebuild_list()
            self._update_banner_summary()

    def _on_run_done(self, app_id: str, success: bool):
        if success:
            self._statuses[app_id] = "installed"
        self._rebuild_list()
        self._update_banner_summary()

    def _on_clean_done(self, app_id: str, success: bool):
        self._rebuild_list()
        self._update_banner_summary()

    def _on_uninstall_done(self, app_id: str, success: bool):
        if success:
            self._statuses[app_id] = "available"
            self._rebuild_list()
        self._update_banner_summary()

    # List row builder

    def _clear_list(self):
        """Clear the list container and reset the status-label registry."""
        self._status_labels.clear()
        super()._clear_list()

    def _update_status_lbl(self, app_id: str, status: str):
        """Update status label on rendered card in place without rebuilding."""
        lbl = self._status_labels.get(app_id)
        if lbl is None:
            return
        lang = get_language()
        cfg = {
            "installed": (t("apps.status.installed", lang=lang), C_GREEN, "rgba(122,179,23,0.15)"),
            "checking":  (t("apps.status.checking",  lang=lang), C_TEXT3, C_CARD_LIGHT),
        }.get(status, (t("apps.status.available", lang=lang), C_BLUE, "rgba(44,123,229,0.12)"))
        text, color, bg = cfg
        lbl.setText(text)
        lbl.setStyleSheet(f"""
            background:{bg}; color:{color};
            border:none; border-radius:6px; padding:4px 12px;
            font-size:{_pt(10)}pt; font-weight:600;
        """)

    def _make_status_lbl(self, status: str) -> QLabel:
        lang = get_language()
        cfg = {
            "installed": (t("apps.status.installed", lang=lang), C_GREEN, "rgba(122,179,23,0.15)"),
            "checking":  (t("apps.status.checking", lang=lang), C_TEXT3, C_CARD_LIGHT),
        }.get(status, (t("apps.status.available", lang=lang), C_BLUE, "rgba(44,123,229,0.12)"))
        text, color, bg = cfg
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            background:{bg}; color:{color};
            border:none; border-radius:6px; padding:4px 12px;
            font-size:{_pt(10)}pt; font-weight:600;
        """)
        return lbl

    def _build_row(self, app: dict) -> QFrame:
        from PyQt5.QtWidgets import QFrame
        from seeed_jetson_develop.gui.runtime_i18n import get_current_lang, translate_text as _tr
        status = self._statuses.get(app["id"], "available")
        row = QFrame()
        row.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #1E2D40, stop:1 #192333);"
            "border: 1px solid rgba(255,255,255,0.05);"
            "border-top-color: rgba(255,255,255,0.07); border-radius:10px;"
        )
        outer = QVBoxLayout(row)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        icon_box = QFrame()
        icon_box.setFixedSize(_pt(48), _pt(48))
        icon_box.setStyleSheet("background:rgba(122,179,23,0.20); border:none; border-radius:12px;")
        icon_lay = QHBoxLayout(icon_box)
        icon_lay.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel(app.get("icon", "APP"))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(f"font-size:{_pt(18)}pt; color:{C_TEXT}; background:transparent;")
        icon_lay.addWidget(icon_lbl)
        top_row.addWidget(icon_box)

        info = QVBoxLayout()
        info.setSpacing(4)
        _lang = get_current_lang(self)
        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        title_lbl = _lbl(_tr(app["name"], _lang), 13, C_TEXT, bold=True)
        title_lbl.setWordWrap(True)
        name_row.addWidget(title_lbl, 1)
        cat_lbl = QLabel(_tr(app.get("category", "App"), _lang))
        cat_lbl.setStyleSheet(f"""
            background:rgba(44,123,229,0.10); color:{C_BLUE};
            border:none; border-radius:4px; padding:2px 10px; font-size:{_pt(9)}pt;
        """)
        name_row.addWidget(cat_lbl)
        info.addLayout(name_row)
        desc_lbl = _lbl(_tr(app.get("desc", ""), _lang), 11, C_TEXT2, wrap=True)
        desc_lbl.setWordWrap(True)
        info.addWidget(desc_lbl)
        top_row.addLayout(info, 1)
        status_lbl = self._make_status_lbl(status)
        self._status_labels[app["id"]] = status_lbl   # Register for in-place status updates
        top_row.addWidget(status_lbl, 0, Qt.AlignTop)
        outer.addLayout(top_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addStretch()
        is_example = bool(app.get("example_name"))

        if status == "installed" and self._get_clean_cmds(app):
            b = _btn(_at("apps.action.clean"), small=True)
            b.clicked.connect(lambda _, aid=app["id"]: self._open_clean(aid))
            action_row.addWidget(b)

        if status == "installed" and app.get("uninstall_cmds"):
            b = _btn(_at("apps.action.uninstall"), danger=True, small=True)
            b.clicked.connect(lambda _, aid=app["id"]: self._open_uninstall(aid))
            action_row.addWidget(b)

        if (is_example or status == "installed") and self._get_run_cmds(app):
            b = _btn(_at("apps.action.run"), primary=True, small=True)
            b.clicked.connect(lambda _, aid=app["id"]: self._open_run(aid))
            action_row.addWidget(b)
        elif not is_example and status != "installed":
            b = _btn(_at("apps.action.install"), primary=True, small=True)
            b.setEnabled(status != "checking")
            b.clicked.connect(lambda _, aid=app["id"]: self._open_install(aid))
            action_row.addWidget(b)

        ai_b = _btn(_at("common.ai_short"), small=True)
        ai_b.setFixedWidth(_pt(44))
        ai_b.setStyleSheet(f"""
            QPushButton {{
                background:rgba(44,123,229,0.15); border:none; border-radius:8px;
                color:{C_BLUE}; font-size:{_pt(10)}pt; font-weight:600;
                padding:0 6px; min-height:{_pt(32)}px;
            }}
            QPushButton:hover {{ background:rgba(44,123,229,0.28); }}
        """)
        ai_b.clicked.connect(lambda _, a=app: self._open_ai(a))
        action_row.addWidget(ai_b)
        outer.addLayout(action_row)
        return row

    def _open_ai(self, app: dict):
        assistant = getattr(self.window(), "_floating_ai", None)
        if assistant:
            assistant.inject_topic(app["name"], app["desc"], self._get_ai_details(app))


def build_page() -> QWidget:
    return AppsPage()
