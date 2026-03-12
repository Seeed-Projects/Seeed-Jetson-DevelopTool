"""Skills 中心页 — 无边框大气风格
包含：分类筛选、搜索、精选/全部切换、运行对话框（含风险确认）、文档查看。
"""
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QScrollArea,
    QDialog, QTextEdit, QMessageBox, QSizePolicy,
)

from seeed_jetson_develop.core.runner import Runner, get_runner
from seeed_jetson_develop.modules.skills.engine import (
    load_skills, run_skill, Skill, CATEGORY_ICONS,
)
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, make_input_card as _input_card,
    apply_shadow as _shadow,
)


# ── Skill 执行线程 ────────────────────────────────────────────────────────────
class _RunThread(QThread):
    log    = pyqtSignal(str)
    done   = pyqtSignal(bool, str)

    def __init__(self, skill: Skill):
        super().__init__()
        self._skill  = skill
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        runner = get_runner()
        success, msg = run_skill(
            self._skill, runner,
            on_log=lambda l: self.log.emit(l),
        )
        if not self._cancel:
            self.done.emit(success, msg)
        else:
            self.done.emit(False, "已取消")


# ── 文档查看对话框 ────────────────────────────────────────────────────────────
class _DocDialog(QDialog):
    def __init__(self, skill: Skill, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"📖  {skill.name}")
        self.setMinimumSize(720, 580)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        lay.addWidget(_lbl(skill.name, 16, C_TEXT, bold=True))
        lay.addWidget(_lbl(skill.desc, 12, C_TEXT2, wrap=True))

        from pathlib import Path
        md_text = ""
        if skill.md_path and Path(skill.md_path).exists():
            md_text = Path(skill.md_path).read_text(encoding="utf-8", errors="replace")
        elif skill.commands:
            md_text = "## 命令列表\n\n```bash\n" + "\n".join(skill.commands) + "\n```"

        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(md_text)
        viewer.setStyleSheet(f"""
            background:{C_CARD};
            border:none;
            border-radius:10px;
            color:{C_TEXT2};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(11)}pt;
            padding:14px;
        """)
        lay.addWidget(viewer, 1)

        close_btn = _btn("关闭")
        close_btn.clicked.connect(self.close)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)


# ── 运行对话框 ────────────────────────────────────────────────────────────────
class _RunDialog(QDialog):
    run_done = pyqtSignal(str, bool)

    def __init__(self, skill: Skill, parent=None):
        super().__init__(parent)
        self._skill  = skill
        self._thread = None

        self.setWindowTitle(f"▶  运行  {skill.name}")
        self.setMinimumSize(680, 560)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        # 标题行
        title_row = QHBoxLayout()
        cat_icon = CATEGORY_ICONS.get(skill.category, "🔧")
        title_row.addWidget(_lbl(f"{cat_icon}  {skill.name}", 16, C_TEXT, bold=True))
        title_row.addStretch()
        if skill.verified:
            v = QLabel("✓ 已验证")
            v.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(10)}pt; background:transparent; font-weight:700;")
            title_row.addWidget(v)
        lay.addLayout(title_row)

        lay.addWidget(_lbl(skill.desc, 12, C_TEXT2, wrap=True))

        # 风险提示 - 无边框
        if skill.risk:
            risk_box = _input_card(8)
            risk_box.setStyleSheet(f"""
                background: rgba(229,62,62,0.10);
                border: none;
                border-radius: 10px;
            """)
            rl = QHBoxLayout(risk_box)
            rl.setContentsMargins(14, 12, 14, 12)
            rl.addWidget(_lbl("⚠", 16, C_RED))
            rl.addSpacing(10)
            rl.addWidget(_lbl(f"风险提示：{skill.risk}", 12, C_RED, wrap=True), 1)
            lay.addWidget(risk_box)

        # 命令预览
        if skill.commands:
            lay.addWidget(_lbl(f"将执行 {len(skill.commands)} 条命令：", 11, C_TEXT3))
            preview = QTextEdit()
            preview.setReadOnly(True)
            preview.setFixedHeight(100)
            preview.setPlainText("\n".join(f"$ {c}" for c in skill.commands))
            preview.setStyleSheet(f"""
                background:{C_CARD_LIGHT};
                border:none;
                border-radius:10px;
                color:{C_TEXT2};
                font-family:'JetBrains Mono','Consolas',monospace;
                font-size:{_pt(10)}pt;
                padding:12px;
            """)
            lay.addWidget(preview)

        # 日志区
        lay.addWidget(_lbl("执行日志", 11, C_TEXT3))
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setStyleSheet(f"""
            background:{C_CARD};
            border:none;
            border-radius:10px;
            color:{C_GREEN};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(10)}pt;
            padding:12px;
        """)
        lay.addWidget(self._log_edit, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self._run_btn  = _btn("▶  开始运行", primary=True)
        self._stop_btn = _btn("■  停止", danger=True)
        self._stop_btn.setEnabled(False)
        close_btn = _btn("关闭")
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._run_btn.clicked.connect(self._start)
        self._stop_btn.clicked.connect(self._stop)
        close_btn.clicked.connect(self.close)

        if not skill.commands:
            self._run_btn.setEnabled(False)
            self._run_btn.setText("无可执行命令")

    def _append(self, text: str):
        self._log_edit.moveCursor(QTextCursor.End)
        self._log_edit.insertPlainText(text + "\n")
        self._log_edit.ensureCursorVisible()

    def _start(self):
        self._log_edit.clear()
        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        t = _RunThread(self._skill)
        t.log.connect(self._append)
        t.done.connect(self._on_done)
        t.start()
        self._thread = t

    def _stop(self):
        if self._thread:
            self._thread.cancel()

    def _on_done(self, success: bool, msg: str):
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        if success:
            self._append(f"\n✅ {msg}")
            self.run_done.emit(self._skill.id, True)
        else:
            self._append(f"\n❌ {msg}")
            self.run_done.emit(self._skill.id, False)


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
    hl.addWidget(_lbl("Skills 中心", 18, C_TEXT, bold=True))
    hl.addSpacing(12)
    hl.addWidget(_lbl("自动化执行环境修复、驱动适配与应用部署任务", 12, C_TEXT3))
    hl.addStretch()
    root.addWidget(header)

    # ── 加载数据 ──
    all_skills  = load_skills()
    _completed: set[str] = set()
    _filter     = {"cat": "全部", "search": "", "source": "全部"}
    _list_ref   = [None]

    builtin_ids = {s.id for s in all_skills if s.source == "builtin"}
    _seen, _cats = set(), ["全部"]
    for s in all_skills:
        if s.category not in _seen:
            _seen.add(s.category)
            _cats.append(s.category)

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

    # ── 说明横幅 - 无边框 ──
    banner = _card(12)
    banner.setStyleSheet(f"""
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 rgba(122,179,23,0.10), stop:1 rgba(44,123,229,0.06));
        border: none;
        border-radius: 12px;
    """)
    bl = QHBoxLayout(banner)
    bl.setContentsMargins(20, 16, 20, 16)
    bl.addWidget(_lbl("💡", 24))
    bl.addSpacing(12)
    tc = QVBoxLayout()
    tc.setSpacing(4)
    tc.addWidget(_lbl("Skills 是可编排的自动化执行单元", 14, C_TEXT, bold=True))
    tc.addWidget(_lbl(
        f"共 {len(all_skills)} 个 Skill，其中 {len(builtin_ids)} 个精选可直接运行，"
        f"{len(all_skills)-len(builtin_ids)} 个来自 OpenClaw 知识库",
        11, C_TEXT3
    ))
    bl.addLayout(tc, 1)
    lay.addWidget(banner)

    # ── 筛选行 - 无边框 ──
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
                padding: 6px 16px;
                min-height: {_pt(32)}px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.06); color:{C_TEXT}; }}
        """

    def _on_tab(label: str):
        _filter["cat"] = label
        for lbl, b in _tab_btns.items():
            b.setStyleSheet(_tab_style(lbl == label))
        _rebuild()

    for cat in _cats:
        b = QPushButton(cat)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(_tab_style(cat == "全部"))
        b.clicked.connect(lambda _, c=cat: _on_tab(c))
        _tab_btns[cat] = b
        filter_row.addWidget(b)
    filter_row.addStretch()

    search_edit = QLineEdit()
    search_edit.setPlaceholderText("🔍  搜索 Skill…")
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
    filter_row.addWidget(search_edit)
    lay.addLayout(filter_row)

    # ── 来源切换 + 计数 ──
    src_row = QHBoxLayout()
    _count_lbl = _lbl("", 12, C_TEXT3)
    src_row.addWidget(_count_lbl)
    src_row.addStretch()

    def _src_btn_style(active):
        return f"""
            QPushButton {{
                background: {'rgba(122,179,23,0.15)' if active else 'transparent'};
                border: none;
                border-radius: 12px;
                color: {C_GREEN if active else C_TEXT3};
                font-size: {_pt(10)}pt;
                padding: 4px 14px;
                min-height: {_pt(28)}px;
            }}
        """

    _src_btns = {}
    for src_label in ["全部", "精选", "OpenClaw"]:
        sb = QPushButton(src_label)
        sb.setCursor(Qt.PointingHandCursor)
        sb.setStyleSheet(_src_btn_style(src_label == "全部"))
        _src_btns[src_label] = sb
        src_row.addWidget(sb)

    def _on_src(label: str):
        _filter["source"] = label
        for lbl, b in _src_btns.items():
            b.setStyleSheet(_src_btn_style(lbl == label))
        _rebuild()

    for lbl, sb in _src_btns.items():
        sb.clicked.connect(lambda _, l=lbl: _on_src(l))

    lay.addLayout(src_row)

    # ── 列表容器 ──
    list_outer = QVBoxLayout()
    list_outer.setSpacing(0)
    lay.addLayout(list_outer)

    # ── 对话框入口 ──
    def _open_run(skill: Skill):
        dlg = _RunDialog(skill, parent=page)
        dlg.run_done.connect(_on_run_done)
        dlg.exec_()

    def _open_doc(skill: Skill):
        dlg = _DocDialog(skill, parent=page)
        dlg.exec_()

    def _on_run_done(skill_id: str, success: bool):
        if success:
            _completed.add(skill_id)
            _rebuild()

    # ── 构建单条 Skill 行 - 无边框 ──
    def _build_row(skill: Skill) -> QFrame:
        done     = skill.id in _completed
        verified = skill.verified
        has_cmds = bool(skill.commands)
        cat_icon = CATEGORY_ICONS.get(skill.category, "🔧")

        # 背景色区分状态
        if done:
            bg_color = "rgba(122,179,23,0.08)"
        elif verified:
            bg_color = "rgba(122,179,23,0.04)"
        elif skill.risk:
            bg_color = "rgba(245,166,35,0.04)"
        else:
            bg_color = C_CARD

        row = _input_card(10)
        row.setStyleSheet(f"""
            background: {bg_color};
            border: none;
            border-radius: 10px;
        """)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(16, 14, 16, 14)
        rl.setSpacing(14)

        # 分类图标
        ic = QLabel(cat_icon)
        ic.setStyleSheet(f"font-size:{_pt(18)}pt; background:transparent;")
        ic.setFixedWidth(_pt(32))
        rl.addWidget(ic)

        # 信息列
        info = QVBoxLayout()
        info.setSpacing(4)

        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        name_row.addWidget(_lbl(skill.name, 13, C_TEXT, bold=True))
        if verified:
            vl = QLabel("✓ 已验证")
            vl.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(9)}pt; background:transparent; font-weight:700;")
            name_row.addWidget(vl)
        if done:
            dl = QLabel("● 已完成")
            dl.setStyleSheet(f"""
                color:{C_GREEN}; font-size:{_pt(9)}pt; background:rgba(122,179,23,0.12);
                border-radius:4px; padding:2px 8px; font-weight:600;
            """)
            name_row.addWidget(dl)
        if skill.risk:
            rl2 = QLabel("⚠ 有风险")
            rl2.setStyleSheet(f"color:{C_ORANGE}; font-size:{_pt(9)}pt; background:transparent;")
            name_row.addWidget(rl2)
        name_row.addStretch()
        info.addLayout(name_row)
        info.addWidget(_lbl(skill.desc, 11, C_TEXT2, wrap=True))
        rl.addLayout(info, 1)

        # 耗时
        dur = _lbl(skill.duration_hint, 10, C_TEXT3)
        dur.setFixedWidth(_pt(56))
        dur.setAlignment(Qt.AlignCenter)
        rl.addWidget(dur)

        # 来源标签
        if skill.source == "openclaw":
            src_l = QLabel("OpenClaw")
            src_l.setStyleSheet(f"""
                background:rgba(44,123,229,0.10);
                color:{C_BLUE};
                border-radius:4px;
                padding:2px 10px;
                font-size:{_pt(9)}pt;
            """)
            rl.addWidget(src_l)

        # 操作按钮
        if has_cmds:
            run_b = _btn("▶  运行", primary=True, small=True)
            run_b.clicked.connect(lambda _, s=skill: _open_run(s))
            rl.addWidget(run_b)
        doc_b = _btn("📖", small=True)
        doc_b.setFixedWidth(_pt(48))
        doc_b.clicked.connect(lambda _, s=skill: _open_doc(s))
        rl.addWidget(doc_b)

        return row

    # ── 重建列表 ──
    def _rebuild():
        if _list_ref[0] is not None:
            list_outer.removeWidget(_list_ref[0])
            _list_ref[0].deleteLater()
            _list_ref[0] = None

        cat    = _filter["cat"]
        kw     = _filter["search"].lower()
        src    = _filter["source"]

        filtered = [
            s for s in all_skills
            if (cat == "全部" or s.category == cat)
            and (src == "全部"
                 or (src == "精选"    and s.source == "builtin")
                 or (src == "OpenClaw" and s.source == "openclaw"))
            and (not kw
                 or kw in s.name.lower()
                 or kw in s.desc.lower()
                 or kw in s.id.lower())
        ]
        _count_lbl.setText(f"共 {len(filtered)} 个 Skill")

        w = QWidget()
        w.setStyleSheet("background:transparent;")
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(10)

        if not filtered:
            wl.addWidget(_lbl("暂无符合条件的 Skill", 14, C_TEXT3))
        else:
            # 按分类分组
            groups: dict[str, list] = {}
            for s in filtered:
                groups.setdefault(s.category, []).append(s)

            for cat_name, skills in groups.items():
                icon = CATEGORY_ICONS.get(cat_name, "🔧")
                # 分组标题
                title_row = QHBoxLayout()
                title_row.addWidget(_lbl(f"{icon}  {cat_name}", 14, C_TEXT2, bold=True))
                title_row.addWidget(_lbl(f"  {len(skills)} 个", 10, C_TEXT3))
                title_row.addStretch()
                title_w = QWidget()
                title_w.setStyleSheet("background:transparent;")
                title_w.setLayout(title_row)
                wl.addWidget(title_w)

                for skill in skills:
                    wl.addWidget(_build_row(skill))

                wl.addSpacing(10)

        wl.addStretch()
        list_outer.addWidget(w)
        _list_ref[0] = w

    # ── 初始化 ──
    _rebuild()
    lay.addStretch()
    scroll.setWidget(inner)
    root.addWidget(scroll, 1)
    return page
