"""应用市场页 — 无边框大气风格
包含：分类筛选、搜索、后台安装检测、安装对话框。
"""
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QDialog, QTextEdit, QMessageBox, QSizePolicy,
)

from seeed_jetson_develop.core.runner import Runner, SSHRunner, get_runner
from seeed_jetson_develop.core.events import bus
from seeed_jetson_develop.core.platform_detect import is_jetson


def _can_execute_from_current_env(parent: QWidget) -> bool:
    if is_jetson() or isinstance(get_runner(), SSHRunner):
        return True
    QMessageBox.information(
        parent,
        "需要远程连接",
        "当前运行在 PC 上，安装或部署前必须先在「远程开发」页连接 Jetson 设备。",
    )
    return False


from seeed_jetson_develop.modules.apps.registry import load_apps
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, make_input_card as _input_card,
    apply_shadow as _shadow,
)


class _ResponsiveScrollArea(QScrollArea):
    def __init__(self, *args, on_resize=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_resize = on_resize
        self._resize_timer = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._on_resize:
            # 防抖：延迟 100ms 再重建，避免频繁刷新
            from PyQt5.QtCore import QTimer
            if self._resize_timer:
                self._resize_timer.stop()
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._on_resize)
            self._resize_timer.start(100)


# ── 后台安装状态检测线程 ──────────────────────────────────────────────────────
class _StatusCheckThread(QThread):
    all_done = pyqtSignal(dict)

    def __init__(self, apps: list[dict]):
        super().__init__()
        self._apps = apps

    def run(self):
        runner = get_runner()
        results = {}
        if not isinstance(runner, SSHRunner):
            self.all_done.emit(results)
            return
        for app in self._apps:
            cmd = app.get("check_cmd")
            if cmd:
                rc, _ = runner.run(cmd, timeout=6)
                results[app["id"]] = "installed" if rc == 0 else "available"
        self.all_done.emit(results)


# ── 应用安装线程 ──────────────────────────────────────────────────────────────
class _InstallThread(QThread):
    log  = pyqtSignal(str)
    done = pyqtSignal(bool)

    def __init__(self, cmds: list[str]):
        super().__init__()
        self._cmds   = cmds
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        runner = get_runner()
        for cmd in self._cmds:
            if self._cancel:
                self.log.emit("⚠ 已取消")
                self.done.emit(False)
                return
            self.log.emit(f"\n$ {cmd}")
            rc, _ = runner.run(cmd, timeout=600, on_output=lambda l: self.log.emit(l))
            if rc != 0:
                self.log.emit(f"\n✖ 命令失败 (rc={rc})")
                self.done.emit(False)
                return
        self.done.emit(True)


# ── 安装/卸载对话框 ───────────────────────────────────────────────────────────
class _InstallDialog(QDialog):
    install_done = pyqtSignal(str, bool)

    def __init__(self, app: dict, cmds: list[str], parent=None, mode: str = "install"):
        super().__init__(parent)
        self._app    = app
        self._cmds   = cmds
        self._thread = None
        self._mode   = mode  # "install" or "uninstall"

        title_map = {
            "install": "安装",
            "uninstall": "卸载",
            "run": "运行",
            "clean": "清理",
        }
        title = title_map.get(mode, "执行")
        self.setWindowTitle(f"{title}  {app['name']}")
        self.setMinimumSize(640, 520)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        # 应用信息行
        info_row = QHBoxLayout()
        info_row.addWidget(_lbl(app["icon"], 32))
        info_row.addSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(_lbl(app["name"], 15, C_TEXT, bold=True))
        col.addWidget(_lbl(app["desc"], 12, C_TEXT2, wrap=True))
        info_row.addLayout(col, 1)
        lay.addLayout(info_row)

        # 步骤预览
        step_label = f"{title}步骤"
        lay.addWidget(_lbl(step_label, 12, C_TEXT3))
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setFixedHeight(120)
        preview.setStyleSheet(f"""
            background:{C_CARD_LIGHT};
            border:none;
            border-radius:10px;
            color:{C_TEXT2};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:11px;
            padding:12px;
        """)
        preview.setPlainText("\n".join(f"$ {c}" for c in cmds))
        lay.addWidget(preview)

        # 日志区
        log_label = f"{title}日志"
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
            font-size:11px;
            padding:12px;
        """)
        lay.addWidget(self._log_edit, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        start_label = f"▶  开始{title}"
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
        self._stop_btn  = _btn("■  停止")
        self._stop_btn.setEnabled(False)
        close_btn = _btn("关闭")
        self._ai_btn = _btn("问 AI", primary=False, small=True)
        self._ai_btn.setVisible(False)
        self._ai_btn.clicked.connect(self._ask_ai)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._ai_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._start_btn.clicked.connect(self._start)
        self._stop_btn.clicked.connect(self._stop)
        close_btn.clicked.connect(self.close)

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
        t = _InstallThread(self._cmds)
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
            "install": ("安装成功！", "安装失败，请检查日志。"),
            "uninstall": ("卸载成功！", "卸载失败，请检查日志。"),
            "run": ("运行完成。", "运行失败，请检查日志。"),
            "clean": ("清理完成。", "清理失败，请检查日志。"),
        }.get(self._mode, ("执行成功。", "执行失败，请检查日志。"))
        if success:
            self._append(f"\n✅ {action_text[0]}")
        else:
            self._append(f"\n❌ {action_text[1]}")
            self._ai_btn.setVisible(True)
        self.install_done.emit(self._app["id"], success)

    def _ask_ai(self):
        host = self.parent().window() if self.parent() else None
        assistant = getattr(host, "_floating_ai", None)
        if assistant:
            log_text = self._log_edit.toPlainText()
            assistant.inject_error(self._app["name"], log_text)


# ── 主页面 ────────────────────────────────────────────────────────────────────
def build_page() -> QWidget:
    page = QWidget()
    page.setStyleSheet(f"background:{C_BG};")
    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    header = QWidget()
    header.setStyleSheet(f"background:{C_BG_DEEP};")
    header.setFixedHeight(_pt(64))
    hl = QHBoxLayout(header)
    hl.setContentsMargins(28, 0, 28, 0)
    hl.addWidget(_lbl("应用市场", 18, C_TEXT, bold=True))
    hl.addSpacing(12)
    hl.addWidget(_lbl("浏览、安装、运行并管理 Jetson 应用与示例", 12, C_TEXT3))
    hl.addStretch()
    badge = QLabel("Beta")
    badge.setStyleSheet(f"""
        background:{C_BLUE};
        color:#071200;
        border-radius:6px;
        padding:4px 12px;
        font-size:{_pt(10)}pt;
        font-weight:700;
    """)
    hl.addWidget(badge)
    root.addWidget(header)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setStyleSheet("background:transparent; border:none;")
    inner = QWidget()
    inner.setStyleSheet(f"background:{C_BG};")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(28, 24, 28, 24)
    lay.setSpacing(20)

    apps_data = load_apps()
    _statuses: dict[str, str] = {}
    _filter = {"cat": "全部", "search": ""}
    _list_ref = [None]
    _device_meta = {"l4t": None}

    for a in apps_data:
        _statuses[a["id"]] = "checking" if a.get("check_cmd") else "available"

    _cats = ["全部"]
    for a in apps_data:
        cat = a.get("category") or "其他"
        if cat not in _cats:
            _cats.append(cat)
    _cats.append("已安装")

    tabs_scroll = QScrollArea()
    tabs_scroll.setWidgetResizable(True)
    tabs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    tabs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    tabs_scroll.setStyleSheet("""
        QScrollArea { background:transparent; border:none; }
        QScrollBar:horizontal { height:0px; background:transparent; }
    """)
    tabs_wrap = QWidget()
    tabs_wrap.setStyleSheet("background:transparent;")
    filter_row = QHBoxLayout(tabs_wrap)
    filter_row.setContentsMargins(0, 0, 0, 0)
    filter_row.setSpacing(10)
    _tab_btns: dict[str, QPushButton] = {}

    def _tab_style(active: bool) -> str:
        return f"""
            QPushButton {{
                background: {'rgba(122,179,23,0.15)' if active else 'transparent'};
                border: none;
                border-radius: 20px;
                color: {C_GREEN if active else C_TEXT2};
                font-size: {_pt(11)}pt;
                font-weight: {'600' if active else '400'};
                padding: 6px 18px;
                min-height: {_pt(36)}px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.06); color:{C_TEXT}; }}
        """

    def _on_tab(label: str):
        _filter["cat"] = label
        for lbl, btn in _tab_btns.items():
            btn.setStyleSheet(_tab_style(lbl == label))
        _rebuild()

    for cat in _cats:
        btn = QPushButton(cat)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(_tab_style(cat == _filter["cat"]))
        btn.clicked.connect(lambda _, c=cat: _on_tab(c))
        _tab_btns[cat] = btn
        filter_row.addWidget(btn)
    filter_row.addStretch()
    tabs_scroll.setWidget(tabs_wrap)
    tabs_scroll.setFixedHeight(_pt(52))
    lay.addWidget(tabs_scroll)

    search_row = QHBoxLayout()
    search_row.setSpacing(10)
    search_row.addStretch()
    search_edit = QLineEdit()
    search_edit.setPlaceholderText("搜索应用...")
    search_edit.setStyleSheet(f"""
        QLineEdit {{
            background:{C_CARD_LIGHT};
            border:none;
            border-radius:24px;
            padding:8px 20px;
            color:{C_TEXT};
            font-size:{_pt(12)}pt;
        }}
        QLineEdit:focus {{ background:{C_CARD}; }}
    """)
    search_edit.setFixedHeight(_pt(44))
    search_edit.setMaximumWidth(260)
    search_edit.textChanged.connect(lambda t: (_filter.update({"search": t}), _rebuild()))
    search_row.addWidget(search_edit)
    lay.addLayout(search_row)

    ctrl_row = QHBoxLayout()
    _count_lbl = _lbl("", 12, C_TEXT3)
    ctrl_row.addWidget(_count_lbl)
    ctrl_row.addStretch()
    refresh_btn = _btn("刷新状态", small=True)
    ctrl_row.addWidget(refresh_btn)
    lay.addLayout(ctrl_row)

    list_container = QWidget()
    list_container.setStyleSheet("background:transparent;")
    list_outer = QVBoxLayout(list_container)
    list_outer.setContentsMargins(0, 0, 0, 0)
    list_outer.setSpacing(10)
    lay.addWidget(list_container)

    def _get_cmds(app: dict) -> list[str]:
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

    def _get_run_cmds(app: dict) -> list[str]:
        return app.get("run_cmds") or []

    def _get_clean_cmds(app: dict) -> list[str]:
        return app.get("clean_cmds") or []

    def _get_ai_details(app: dict) -> list[str]:
        details = [f"分类：{app.get('category', '-')}"]
        req = app.get("requirements") or {}
        if req.get("jetpack_versions"):
            details.append(f"L4T：{', '.join(req['jetpack_versions'])}")
        if req.get("required_disk_gb") is not None:
            details.append(f"磁盘：{req['required_disk_gb']}GB")
        if req.get("required_mem_gb") is not None:
            details.append(f"内存：{req['required_mem_gb']}GB")
        cmds = _get_cmds(app)
        run_cmds = _get_run_cmds(app)
        if cmds and cmds != run_cmds:
            details.append("安装：")
            details.extend(cmds[:4])
        if run_cmds:
            details.append("运行：")
            details.extend(run_cmds[:2])
        return details

    def _open_ai(app: dict):
        host = page.window()
        assistant = getattr(host, "_floating_ai", None)
        if assistant:
            assistant.inject_topic(app["name"], app["desc"], _get_ai_details(app))

    def _get_current_l4t(force: bool = False) -> str:
        if _device_meta["l4t"] and not force:
            return _device_meta["l4t"]
        runner = get_runner()
        cmd = (
            "head -1 /etc/nv_tegra_release 2>/dev/null | "
            "awk '{gsub(\",\",\"\",$5); print $2\".\"$5}'"
        )
        rc, out = runner.run(cmd, timeout=5)
        l4t = (out or "").strip().splitlines()[-1].strip() if rc == 0 and (out or "").strip() else ""
        _device_meta["l4t"] = l4t
        return l4t

    def _l4t_matches(current_l4t: str, allowed_version: str) -> bool:
        current = (current_l4t or "").strip().lstrip("R")
        allowed = (allowed_version or "").strip().lstrip("R")
        if not current or not allowed:
            return False
        if allowed.endswith(".x"):
            return current.startswith(allowed[:-1])
        return current == allowed

    def _ensure_l4t_compatible(app: dict) -> bool:
        req = app.get("requirements") or {}
        allowed = req.get("jetpack_versions") or []
        if not allowed:
            return True
        current_l4t = _get_current_l4t()
        if not current_l4t:
            QMessageBox.information(
                page,
                "L4T 检测失败",
                f"无法读取当前设备的 L4T 版本，已跳过兼容性拦截。\n\n"
                f"{app['name']} 支持版本：{', '.join(allowed)}",
            )
            return True
        if any(_l4t_matches(current_l4t, item) for item in allowed):
            return True
        QMessageBox.warning(
            page,
            "L4T 版本不兼容",
            f"{app['name']} 不支持当前设备的 L4T {current_l4t}。\n\n"
            f"支持版本：{', '.join(allowed)}\n"
            "已拦截本次运行，避免进入 demo 初始化后再失败。",
        )
        return False

    def _open_dialog(app_id: str, mode: str, cmds: list[str], done_cb):
        import logging, traceback as _tb
        try:
            app = next((a for a in apps_data if a["id"] == app_id), None)
            if not app:
                return
            if not _can_execute_from_current_env(page):
                return
            if not cmds:
                QMessageBox.information(page, "提示", f"《{app['name']}》暂未配置可执行命令。")
                return
            dlg = _InstallDialog(app, cmds, parent=page, mode=mode)
            dlg.install_done.connect(done_cb)
            dlg.exec_()
        except Exception:
            msg = _tb.format_exc()
            logging.getLogger("seeed").error("打开应用对话框失败:\n%s", msg)
            QMessageBox.critical(page, "错误", f"打开应用对话框时发生异常：\n\n{msg[-600:]}")

    def _open_install(app_id: str):
        app = next(a for a in apps_data if a["id"] == app_id)
        _open_dialog(app_id, "install", _get_cmds(app), _on_install_done)

    def _open_run(app_id: str):
        app = next(a for a in apps_data if a["id"] == app_id)
        if not _ensure_l4t_compatible(app):
            return
        _open_dialog(app_id, "run", _get_run_cmds(app), _on_run_done)

    def _open_clean(app_id: str):
        app = next((a for a in apps_data if a["id"] == app_id), None)
        if not app:
            return
        ret = QMessageBox.question(
            page, "确认清理",
            f"确认清理《{app['name']}》生成的数据吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            _open_dialog(app_id, "clean", _get_clean_cmds(app), _on_clean_done)

    def _open_uninstall(app_id: str):
        app = next((a for a in apps_data if a["id"] == app_id), None)
        if not app:
            return
        cmds = app.get("uninstall_cmds") or []
        if not cmds:
            QMessageBox.information(page, "提示", f"《{app['name']}》暂未配置卸载命令。")
            return
        ret = QMessageBox.question(
            page, "确认卸载",
            f"确认卸载《{app['name']}》吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            _open_dialog(app_id, "uninstall", cmds, _on_uninstall_done)

    def _on_install_done(app_id: str, success: bool):
        if success:
            _statuses[app_id] = "installed"
            _rebuild()

    def _on_run_done(app_id: str, success: bool):
        if success:
            _statuses[app_id] = "installed"
        _rebuild()

    def _on_clean_done(app_id: str, success: bool):
        _rebuild()

    def _on_uninstall_done(app_id: str, success: bool):
        if success:
            _statuses[app_id] = "available"
            _rebuild()

    def _make_status_lbl(status: str) -> QLabel:
        cfg = {
            "installed": ("已安装", C_GREEN, "rgba(122,179,23,0.15)"),
            "checking": ("检测中", C_TEXT3, C_CARD_LIGHT),
        }.get(status, ("可安装", C_BLUE, "rgba(44,123,229,0.12)"))
        text, color, bg = cfg
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            background:{bg};
            color:{color};
            border-radius:6px;
            padding:4px 12px;
            font-size:{_pt(10)}pt;
            font-weight:600;
        """)
        return lbl

    def _build_row(app: dict) -> QFrame:
        status = _statuses.get(app["id"], "available")
        row = _input_card(10)
        row.setStyleSheet(f"""
            background:{C_CARD};
            border:none;
            border-radius:10px;
        """)
        outer = QVBoxLayout(row)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        icon_box = QFrame()
        icon_box.setFixedSize(_pt(48), _pt(48))
        icon_box.setStyleSheet("background: rgba(122,179,23,0.20); border:none; border-radius:12px;")
        icon_lay = QHBoxLayout(icon_box)
        icon_lay.setContentsMargins(0, 0, 0, 0)
        icon = QLabel(app.get("icon", "APP"))
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"font-size:{_pt(18)}pt; color:{C_TEXT}; background:transparent;")
        icon_lay.addWidget(icon)
        top_row.addWidget(icon_box)

        info = QVBoxLayout()
        info.setSpacing(4)
        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        title_lbl = _lbl(app["name"], 13, C_TEXT, bold=True)
        title_lbl.setWordWrap(True)
        name_row.addWidget(title_lbl, 1)
        cat = QLabel(app.get("category", "应用"))
        cat.setStyleSheet(f"""
            background:rgba(44,123,229,0.10);
            color:{C_BLUE};
            border-radius:4px;
            padding:2px 10px;
            font-size:{_pt(9)}pt;
        """)
        name_row.addWidget(cat)
        info.addLayout(name_row)
        desc_lbl = _lbl(app.get("desc", ""), 11, C_TEXT2, wrap=True)
        desc_lbl.setWordWrap(True)
        info.addWidget(desc_lbl)
        top_row.addLayout(info, 1)

        top_row.addWidget(_make_status_lbl(status), 0, Qt.AlignTop)
        outer.addLayout(top_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addStretch()

        is_example = bool(app.get("example_name"))

        if status == "installed" and _get_clean_cmds(app):
            clean_b = _btn("清理", small=True)
            clean_b.clicked.connect(lambda _, app_id=app["id"]: _open_clean(app_id))
            action_row.addWidget(clean_b)

        # 卸载按钮：已安装 + 有卸载命令时，独立显示（不与运行互斥）
        if status == "installed" and app.get("uninstall_cmds"):
            uninstall_b = _btn("卸载", danger=True, small=True)
            uninstall_b.clicked.connect(lambda _, app_id=app["id"]: _open_uninstall(app_id))
            action_row.addWidget(uninstall_b)

        # 运行 / 安装按钮
        if (is_example or status == "installed") and _get_run_cmds(app):
            run_b = _btn("运行", primary=True, small=True)
            run_b.clicked.connect(lambda _, app_id=app["id"]: _open_run(app_id))
            action_row.addWidget(run_b)
        elif not is_example and status != "installed":
            install_b = _btn("安装", primary=True, small=True)
            install_b.setEnabled(status != "checking")
            install_b.clicked.connect(lambda _, app_id=app["id"]: _open_install(app_id))
            action_row.addWidget(install_b)

        ai_b = _btn("AI", small=True)
        ai_b.setFixedWidth(_pt(44))
        ai_b.setStyleSheet(f"""
            QPushButton {{
                background: rgba(44,123,229,0.15);
                border: none;
                border-radius: 8px;
                color: {C_BLUE};
                font-size: {_pt(10)}pt;
                font-weight: 600;
                padding: 0 6px;
                min-height: {_pt(32)}px;
            }}
            QPushButton:hover {{ background: rgba(44,123,229,0.28); }}
        """)
        ai_b.clicked.connect(lambda _, a=app: _open_ai(a))
        action_row.addWidget(ai_b)
        outer.addLayout(action_row)
        return row

    def _clear_list_outer():
        while list_outer.count():
            item = list_outer.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    _batch_gen = [0]

    def _rebuild():
        _batch_gen[0] += 1
        gen = _batch_gen[0]

        _clear_list_outer()
        cat = _filter["cat"]
        kw = _filter["search"].lower()
        filtered = [
            a for a in apps_data
            if (cat == "全部" or (cat == "已安装" and _statuses.get(a["id"]) == "installed") or a.get("category") == cat)
            and (not kw or kw in a.get("name", "").lower() or kw in a.get("desc", "").lower() or kw in a.get("id", "").lower())
        ]
        _count_lbl.setText(f"共 {len(filtered)} 个应用")

        # 脱离 layout 树构建，完成后一次性挂入
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(10)

        if not filtered:
            wl.addWidget(_lbl("暂无符合当前筛选条件的应用", 14, C_TEXT3))
            wl.addStretch()
            list_outer.addWidget(w)
            _list_ref[0] = w
            return

        idx_ref = [0]
        BATCH = 6

        def _add_batch():
            if _batch_gen[0] != gen:
                return
            for _ in range(BATCH):
                if idx_ref[0] >= len(filtered):
                    break
                wl.addWidget(_build_row(filtered[idx_ref[0]]))
                idx_ref[0] += 1
            if idx_ref[0] < len(filtered):
                QTimer.singleShot(10, _add_batch)
            else:
                wl.addStretch()
                list_outer.addWidget(w)
                _list_ref[0] = w

        QTimer.singleShot(0, _add_batch)

    _check_thread = [None]

    def _start_check():
        if _check_thread[0] and _check_thread[0].isRunning():
            return
        if not isinstance(get_runner(), SSHRunner):
            for a in apps_data:
                _statuses[a["id"]] = "available"
            refresh_btn.setEnabled(True)
            refresh_btn.setText("刷新状态")
            _rebuild()
            return
        for a in apps_data:
            if a.get("check_cmd"):
                _statuses[a["id"]] = "checking"
        refresh_btn.setEnabled(False)
        refresh_btn.setText("检测中...")
        _rebuild()
        t = _StatusCheckThread(apps_data)
        t.all_done.connect(_on_check_done)
        t.start()
        _check_thread[0] = t

    def _on_check_done(results: dict):
        for app_id, status in results.items():
            _statuses[app_id] = status
        refresh_btn.setEnabled(True)
        refresh_btn.setText("刷新状态")
        _rebuild()

    refresh_btn.clicked.connect(_start_check)
    bus.device_connected.connect(lambda _: (_device_meta.update({"l4t": None}), _start_check()))

    lay.addStretch()
    scroll.setWidget(inner)
    root.addWidget(scroll, 1)
    QTimer.singleShot(200, _start_check)
    return page
