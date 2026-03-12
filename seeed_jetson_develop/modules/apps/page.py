"""应用市场页 — 无边框大气风格
包含：分类筛选、搜索、后台安装检测、安装对话框。
"""
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QDialog, QTextEdit, QMessageBox,
)

from seeed_jetson_develop.core.runner import Runner, get_runner
from seeed_jetson_develop.core.events import bus
from seeed_jetson_develop.modules.apps.registry import load_apps
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, make_input_card as _input_card,
    apply_shadow as _shadow,
)


# ── 后台安装状态检测线程 ──────────────────────────────────────────────────────
class _StatusCheckThread(QThread):
    all_done = pyqtSignal(dict)

    def __init__(self, apps: list[dict]):
        super().__init__()
        self._apps = apps

    def run(self):
        runner = get_runner()
        results = {}
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


# ── 安装对话框 ────────────────────────────────────────────────────────────────
class _InstallDialog(QDialog):
    install_done = pyqtSignal(str, bool)

    def __init__(self, app: dict, cmds: list[str], parent=None):
        super().__init__(parent)
        self._app    = app
        self._cmds   = cmds
        self._thread = None

        self.setWindowTitle(f"安装  {app['name']}")
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
        lay.addWidget(_lbl("安装步骤", 12, C_TEXT3))
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
        lay.addWidget(_lbl("安装日志", 12, C_TEXT3))
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setStyleSheet(f"""
            background:{C_CARD};
            border:none;
            border-radius:10px;
            color:{C_GREEN};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:11px;
            padding:12px;
        """)
        lay.addWidget(self._log_edit, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self._start_btn = _btn("▶  开始安装", primary=True)
        self._stop_btn  = _btn("■  停止")
        self._stop_btn.setEnabled(False)
        close_btn = _btn("关闭")
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
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
        if success:
            self._append("\n✅ 安装成功！")
            self.install_done.emit(self._app["id"], True)
        else:
            self._append("\n❌ 安装失败，请检查日志。")
            self.install_done.emit(self._app["id"], False)


# ── 主页面 ────────────────────────────────────────────────────────────────────
def build_page() -> QWidget:
    page = QWidget()
    page.setStyleSheet(f"background:{C_BG};")
    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    # ── 页头 - 无边框 ──
    header = QWidget()
    header.setStyleSheet(f"background:{C_BG_DEEP};")
    header.setFixedHeight(_pt(64))
    hl = QHBoxLayout(header)
    hl.setContentsMargins(28, 0, 28, 0)
    hl.addWidget(_lbl("应用市场", 18, C_TEXT, bold=True))
    hl.addSpacing(12)
    hl.addWidget(_lbl("浏览、安装和管理 Jetson 应用与 Demo", 12, C_TEXT3))
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

    # ── 滚动区域 ──
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setStyleSheet("background:transparent; border:none;")
    inner = QWidget()
    inner.setStyleSheet(f"background:{C_BG};")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(28, 24, 28, 24)
    lay.setSpacing(20)

    # ── 数据 & 状态 ──
    apps_data = load_apps()
    _statuses: dict[str, str] = {}
    _filter   = {"cat": "全部", "search": ""}
    _grid_ref = [None]

    for a in apps_data:
        _statuses[a["id"]] = "checking" if a.get("check_cmd") else "available"

    # 分类列表
    _seen, _cats = set(), ["全部"]
    for a in apps_data:
        c = a["category"]
        if c not in _seen:
            _seen.add(c)
            _cats.append(c)
    _cats.append("已安装")

    # ── 筛选行：分类 Tab + 搜索框 - 无边框 ──
    filter_row = QHBoxLayout()
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
        for lbl, b in _tab_btns.items():
            b.setStyleSheet(_tab_style(lbl == label))
        _rebuild_grid()

    for cat in _cats:
        b = QPushButton(cat)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(_tab_style(cat == "全部"))
        b.clicked.connect(lambda _, c=cat: _on_tab(c))
        _tab_btns[cat] = b
        filter_row.addWidget(b)

    filter_row.addStretch()

    search_edit = QLineEdit()
    search_edit.setPlaceholderText("🔍  搜索应用…")
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
    search_edit.setMaximumWidth(280)
    search_edit.textChanged.connect(
        lambda t: (_filter.update({"search": t}), _rebuild_grid())
    )
    filter_row.addWidget(search_edit)
    lay.addLayout(filter_row)

    # ── 计数 + 刷新 ──
    ctrl_row = QHBoxLayout()
    _count_lbl = _lbl("", 12, C_TEXT3)
    ctrl_row.addWidget(_count_lbl)
    ctrl_row.addStretch()
    refresh_btn = _btn("↻  刷新状态", small=True)
    ctrl_row.addWidget(refresh_btn)
    lay.addLayout(ctrl_row)

    # ── 网格容器 ──
    grid_outer = QVBoxLayout()
    grid_outer.setSpacing(0)
    lay.addLayout(grid_outer)

    # ── 获取安装命令 ──
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
                    "加载 skill '%s' 失败:\n%s", skill_id, traceback.format_exc()
                )
        return app.get("install_cmds") or []

    # ── 安装对话框 ──
    def _open_install(app_id: str):
        import logging, traceback as _tb
        try:
            app = next((a for a in apps_data if a["id"] == app_id), None)
            if not app:
                return
            cmds = _get_cmds(app)
            if not cmds:
                QMessageBox.information(
                    page, "提示",
                    f"「{app['name']}」的安装脚本暂未配置，敬请期待。"
                )
                return
            dlg = _InstallDialog(app, cmds, parent=page)
            dlg.install_done.connect(_on_install_done)
            dlg.exec_()
        except Exception:
            msg = _tb.format_exc()
            logging.getLogger("seeed").error("打开安装对话框失败:\n%s", msg)
            QMessageBox.critical(page, "错误", f"打开安装对话框时发生异常：\n\n{msg[-600:]}")

    def _on_install_done(app_id: str, success: bool):
        if success:
            _statuses[app_id] = "installed"
            _rebuild_grid()

    # ── 构建卡片 ──
    def _make_status_lbl(status: str) -> QLabel:
        cfg = {
            "installed": ("已安装", C_GREEN, "rgba(122,179,23,0.15)"),
            "checking":  ("检测中…", C_TEXT3, C_CARD_LIGHT),
        }.get(status, ("可安装", C_BLUE, "rgba(44,123,229,0.12)"))
        text, color, bg = cfg
        l = QLabel(text)
        l.setStyleSheet(f"""
            background:{bg};
            color:{color};
            border-radius:6px;
            padding:4px 12px;
            font-size:{_pt(10)}pt;
            font-weight:600;
        """)
        return l

    def _make_action_btn(app_id: str, status: str) -> QPushButton:
        if status == "installed":
            b = _btn("已安装", small=True)
            b.setEnabled(False)
        else:
            b = _btn("安装", primary=True, small=True)
            b.setEnabled(status != "checking")
            b.clicked.connect(lambda: _open_install(app_id))
        return b

    def _build_card(app: dict) -> QFrame:
        app_id = app["id"]
        status = _statuses.get(app_id, "available")

        # 分类颜色映射
        _cat_colors = {
            "CV / 视觉":   "#2C7BE5",
            "大语言模型":  "#7AB317",
            "TTS 语音":    "#F5A623",
            "机器人":      "#E040FB",
            "开发工具":    "#00BCD4",
        }
        cat_color = _cat_colors.get(app.get("category", ""), "#5A6B7A")

        c = _card(12)
        c.setMinimumWidth(180)
        cl = QVBoxLayout(c)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(12)

        # 顶部：彩色图标块 + 分类 badge
        top = QHBoxLayout()
        top.setSpacing(12)

        # 分类颜色图标容器 - 无边框
        icon_block = QFrame()
        icon_block.setFixedSize(_pt(48), _pt(48))
        icon_block.setStyleSheet(f"""
            QFrame {{
                background: {cat_color}20;
                border: none;
                border-radius: 12px;
            }}
        """)
        icon_inner = QHBoxLayout(icon_block)
        icon_inner.setContentsMargins(0, 0, 0, 0)
        icon_emoji = QLabel(app["icon"])
        icon_emoji.setAlignment(Qt.AlignCenter)
        icon_emoji.setStyleSheet(f"font-size:{_pt(24)}pt; background:transparent;")
        icon_inner.addWidget(icon_emoji)
        top.addWidget(icon_block)

        top.addStretch()
        cat_l = QLabel(app["category"])
        cat_l.setStyleSheet(f"""
            background:{cat_color}15;
            color:{cat_color};
            border: none;
            border-radius: 6px;
            padding: 3px 10px;
            font-size:{_pt(9)}pt;
            font-weight:600;
        """)
        top.addWidget(cat_l, 0, Qt.AlignTop)
        cl.addLayout(top)

        # 名称
        name_lbl = _lbl(app["name"], 14, C_TEXT, bold=True)
        cl.addWidget(name_lbl)

        # 描述
        desc_l = _lbl(app["desc"], 11, C_TEXT2, wrap=True)
        desc_l.setMinimumHeight(_pt(44))
        cl.addWidget(desc_l)

        cl.addStretch()

        # 底部行：状态 + 操作按钮
        bot = QHBoxLayout()
        bot.setSpacing(10)
        bot.addWidget(_make_status_lbl(status))
        bot.addStretch()
        bot.addWidget(_make_action_btn(app_id, status))
        cl.addLayout(bot)

        _shadow(c, blur=16)
        return c

    # ── 重建网格 ──
    def _rebuild_grid():
        if _grid_ref[0] is not None:
            grid_outer.removeWidget(_grid_ref[0])
            _grid_ref[0].deleteLater()
            _grid_ref[0] = None

        cat = _filter["cat"]
        kw  = _filter["search"].lower()

        filtered = [
            a for a in apps_data
            if (cat == "全部"
                or (cat == "已安装" and _statuses.get(a["id"]) == "installed")
                or a["category"] == cat)
            and (not kw
                 or kw in a["name"].lower()
                 or kw in a["desc"].lower())
        ]

        _count_lbl.setText(f"共 {len(filtered)} 个应用")

        if not filtered:
            empty = QWidget()
            empty.setStyleSheet("background:transparent;")
            vl = QVBoxLayout(empty)
            vl.setContentsMargins(0, 40, 0, 0)
            vl.addWidget(_lbl("暂无符合条件的应用", 14, C_TEXT3))
            vl.addStretch()
            grid_outer.addWidget(empty)
            _grid_ref[0] = empty
            return

        w  = QWidget()
        w.setStyleSheet("background:transparent;")
        gl = QGridLayout(w)
        gl.setSpacing(16)
        gl.setContentsMargins(0, 0, 0, 0)

        cols = 3
        for i, app in enumerate(filtered):
            gl.addWidget(_build_card(app), i // cols, i % cols)

        # 补齐末行
        remainder = len(filtered) % cols
        if remainder:
            for j in range(cols - remainder):
                ph = QWidget()
                ph.setStyleSheet("background:transparent;")
                gl.addWidget(ph, len(filtered) // cols, remainder + j)

        grid_outer.addWidget(w)
        _grid_ref[0] = w

    # ── 后台状态检测 ──
    _check_thread = [None]

    def _start_check():
        if _check_thread[0] and _check_thread[0].isRunning():
            return
        for a in apps_data:
            if a.get("check_cmd"):
                _statuses[a["id"]] = "checking"
        refresh_btn.setEnabled(False)
        refresh_btn.setText("检测中…")
        _rebuild_grid()
        t = _StatusCheckThread(apps_data)
        t.all_done.connect(_on_check_done)
        t.start()
        _check_thread[0] = t

    def _on_check_done(results: dict):
        for app_id, status in results.items():
            _statuses[app_id] = status
        refresh_btn.setEnabled(True)
        refresh_btn.setText("↻  刷新状态")
        _rebuild_grid()

    refresh_btn.clicked.connect(_start_check)

    # ── 初始化 ──
    _rebuild_grid()
    lay.addStretch()
    scroll.setWidget(inner)
    root.addWidget(scroll, 1)
    _start_check()

    return page
