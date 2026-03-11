"""Skills 中心页 — 完整实现
包含：分类筛选、搜索、精选/全部切换、运行对话框（含风险确认）、文档查看。
"""
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QTextCursor
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QScrollArea,
    QGraphicsDropShadowEffect, QDialog, QTextEdit,
    QMessageBox, QSizePolicy,
)

def _pt(px: int) -> int:
    return max(8, round(px * 0.75))

from seeed_jetson_develop.core.runner import Runner, get_runner
from seeed_jetson_develop.modules.skills.engine import (
    load_skills, run_skill, Skill, CATEGORY_ICONS,
)

C_BG     = "#0F1923"
C_CARD   = "#162030"
C_CARD2  = "#1A2840"
C_BORDER = "#1E3048"
C_GREEN  = "#8DC21F"
C_GREEN2 = "#76B900"
C_BLUE   = "#2C7BE5"
C_ORANGE = "#F5A623"
C_RED    = "#E53E3E"
C_TEXT   = "#E8F0F8"
C_TEXT2  = "#8BA0B8"
C_TEXT3  = "#4A6278"


def _shadow(w, blur=16, y=3, alpha=70):
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(blur)
    fx.setOffset(0, y)
    fx.setColor(QColor(0, 0, 0, alpha))
    w.setGraphicsEffect(fx)
    return w


def _lbl(text, size=13, color=C_TEXT, bold=False, wrap=False):
    l = QLabel(text)
    l.setStyleSheet(
        f"color:{color}; font-size:{_pt(size)}pt;"
        f" font-weight:{'700' if bold else '400'}; background:transparent;"
    )
    if wrap:
        l.setWordWrap(True)
    return l


def _btn(text, primary=False, small=False, danger=False):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    h  = f"{_pt(38)}px" if small else f"{_pt(46)}px"
    px = "8px 16px"     if small else "10px 22px"
    fs = f"{_pt(12)}pt" if small else f"{_pt(13)}pt"
    if primary:
        bg, bg2, border, tc = C_GREEN, C_GREEN2, "#6A9A18", "#0A1A00"
    elif danger:
        bg, bg2, border, tc = "#C53030", "#9B2C2C", "#7B1D1D", "#FFE0E0"
    else:
        bg, bg2, border, tc = C_CARD2, C_CARD, C_BORDER, C_TEXT2
    b.setStyleSheet(f"""
        QPushButton {{
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {bg},stop:1 {bg2});
            border: 1px solid {border}; border-radius: 7px;
            color: {tc}; font-size: {fs}; font-weight: 600;
            padding: {px}; min-height: {h};
        }}
        QPushButton:hover   {{ background: {bg}; }}
        QPushButton:pressed {{ background: {bg2}; }}
        QPushButton:disabled {{ opacity: 0.45; }}
    """)
    return b


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
        self.setMinimumSize(700, 560)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        lay.addWidget(_lbl(skill.name, 15, C_TEXT, bold=True))
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
            background:{C_CARD}; border:1px solid {C_BORDER};
            border-radius:6px; color:{C_TEXT2};
            font-family:'Consolas','Courier New',monospace; font-size:{_pt(11)}pt; padding:8px;
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
    run_done = pyqtSignal(str, bool)   # skill_id, success

    def __init__(self, skill: Skill, parent=None):
        super().__init__(parent)
        self._skill  = skill
        self._thread = None

        self.setWindowTitle(f"▶  运行  {skill.name}")
        self.setMinimumSize(640, 520)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        # 标题行
        title_row = QHBoxLayout()
        cat_icon = CATEGORY_ICONS.get(skill.category, "🔧")
        title_row.addWidget(_lbl(f"{cat_icon}  {skill.name}", 15, C_TEXT, bold=True))
        title_row.addStretch()
        if skill.verified:
            v = QLabel("✓ 已验证")
            v.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(10)}pt; background:transparent; font-weight:700;")
            title_row.addWidget(v)
        lay.addLayout(title_row)

        lay.addWidget(_lbl(skill.desc, 12, C_TEXT2, wrap=True))

        # 风险提示
        if skill.risk:
            risk_box = QFrame()
            risk_box.setStyleSheet(f"""
                QFrame {{
                    background: rgba(229,62,62,0.12);
                    border: 1px solid rgba(229,62,62,0.35);
                    border-radius: 6px;
                }}
            """)
            rl = QHBoxLayout(risk_box)
            rl.setContentsMargins(12, 8, 12, 8)
            rl.addWidget(_lbl("⚠", 14, C_RED))
            rl.addSpacing(6)
            rl.addWidget(_lbl(f"风险提示：{skill.risk}", 12, C_RED, wrap=True), 1)
            lay.addWidget(risk_box)

        # 命令预览
        if skill.commands:
            lay.addWidget(_lbl(f"将执行 {len(skill.commands)} 条命令：", 11, C_TEXT3))
            preview = QTextEdit()
            preview.setReadOnly(True)
            preview.setFixedHeight(90)
            preview.setPlainText("\n".join(f"$ {c}" for c in skill.commands))
            preview.setStyleSheet(f"""
                background:{C_CARD2}; border:1px solid {C_BORDER};
                border-radius:6px; color:{C_TEXT2};
                font-family:'Consolas','Courier New',monospace; font-size:{_pt(10)}pt; padding:6px;
            """)
            lay.addWidget(preview)

        # 日志区
        lay.addWidget(_lbl("执行日志", 11, C_TEXT3))
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setStyleSheet(f"""
            background:{C_CARD}; border:1px solid {C_BORDER};
            border-radius:6px; color:{C_GREEN};
            font-family:'Consolas','Courier New',monospace; font-size:{_pt(10)}pt; padding:6px;
        """)
        lay.addWidget(self._log_edit, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
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

        # 无命令时直接禁用
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

    # ── 页头 ──
    header = QFrame()
    header.setStyleSheet(f"background:{C_CARD}; border-bottom:1px solid {C_BORDER};")
    header.setFixedHeight(64)
    hl = QHBoxLayout(header)
    hl.setContentsMargins(28, 0, 28, 0)
    hl.addWidget(_lbl("🤖 Skills 中心", 18, C_TEXT, bold=True))
    hl.addSpacing(12)
    hl.addWidget(_lbl("自动化执行环境修复、驱动适配与应用部署任务", 12, C_TEXT2))
    hl.addStretch()
    root.addWidget(header)

    # ── 加载数据 ──
    all_skills  = load_skills()
    _completed: set[str] = set()   # 本次会话已成功运行的 skill_id
    _filter     = {"cat": "全部", "search": "", "source": "全部"}
    _list_ref   = [None]

    builtin_ids = {s.id for s in all_skills if s.source == "builtin"}
    # 分类列表（去重，保持顺序）
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
    lay.setContentsMargins(28, 20, 28, 24)
    lay.setSpacing(14)

    # ── 说明横幅 ──
    banner = QFrame()
    banner.setStyleSheet(f"""
        QFrame {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 rgba(141,194,31,0.1), stop:1 rgba(44,123,229,0.06));
            border: 1px solid rgba(141,194,31,0.2);
            border-radius: 10px;
        }}
    """)
    bl = QHBoxLayout(banner)
    bl.setContentsMargins(18, 12, 18, 12)
    bl.addWidget(_lbl("💡", 20))
    bl.addSpacing(10)
    tc = QVBoxLayout()
    tc.setSpacing(2)
    tc.addWidget(_lbl("Skills 是可编排的自动化执行单元", 13, C_TEXT, bold=True))
    tc.addWidget(_lbl(
        f"共 {len(all_skills)} 个 Skill，其中 {len(builtin_ids)} 个精选可直接运行，"
        f"{len(all_skills)-len(builtin_ids)} 个来自 OpenClaw 知识库",
        11, C_TEXT2
    ))
    bl.addLayout(tc, 1)
    lay.addWidget(banner)

    # ── 筛选行 ──
    filter_row = QHBoxLayout()
    filter_row.setSpacing(8)
    _tab_btns: dict[str, QPushButton] = {}

    def _tab_style(active: bool) -> str:
        return f"""
            QPushButton {{
                background: {'rgba(141,194,31,0.15)' if active else 'transparent'};
                border: 1px solid {'rgba(141,194,31,0.4)' if active else C_BORDER};
                border-radius: 16px;
                color: {C_GREEN if active else C_TEXT2};
                font-size: {_pt(11)}pt;
                font-weight: {'700' if active else '400'};
                padding: 5px 14px;
                min-height: {_pt(30)}px;
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
            background:{C_CARD2}; border:1px solid {C_BORDER};
            border-radius:20px; padding:7px 16px;
            color:{C_TEXT}; font-size:{_pt(12)}pt;
        }}
        QLineEdit:focus {{ border-color:{C_GREEN}; }}
    """)
    search_edit.setFixedHeight(_pt(42))
    search_edit.setMaximumWidth(240)
    search_edit.textChanged.connect(lambda t: (_filter.update({"search": t}), _rebuild()))
    filter_row.addWidget(search_edit)
    lay.addLayout(filter_row)

    # ── 来源切换 + 计数 ──
    src_row = QHBoxLayout()
    _count_lbl = _lbl("", 11, C_TEXT3)
    src_row.addWidget(_count_lbl)
    src_row.addStretch()

    def _src_btn_style(active):
        return f"""
            QPushButton {{
                background: {'rgba(141,194,31,0.15)' if active else 'transparent'};
                border: 1px solid {'rgba(141,194,31,0.35)' if active else C_BORDER};
                border-radius: 12px; color: {C_GREEN if active else C_TEXT3};
                font-size: {_pt(10)}pt; padding: 3px 12px; min-height: {_pt(24)}px;
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

    # ── 构建单条 Skill 行 ──
    def _build_row(skill: Skill) -> QFrame:
        done     = skill.id in _completed
        verified = skill.verified
        has_cmds = bool(skill.commands)
        cat_icon = CATEGORY_ICONS.get(skill.category, "🔧")

        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: {C_CARD2};
                border: 1px solid {'rgba(141,194,31,0.35)' if done else C_BORDER};
                border-radius: 8px;
            }}
            QFrame:hover {{ border-color: rgba(141,194,31,0.25); }}
        """)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(12)

        # 分类图标
        ic = QLabel(cat_icon)
        ic.setStyleSheet(f"font-size:{_pt(18)}pt; background:transparent;")
        ic.setFixedWidth(_pt(30))
        rl.addWidget(ic)

        # 信息列
        info = QVBoxLayout()
        info.setSpacing(3)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_row.addWidget(_lbl(skill.name, 13, C_TEXT, bold=True))
        if verified:
            vl = QLabel("✓ 已验证")
            vl.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(9)}pt; background:transparent; font-weight:700;")
            name_row.addWidget(vl)
        if done:
            dl = QLabel("✅ 已完成")
            dl.setStyleSheet(f"color:{C_GREEN}; font-size:{_pt(9)}pt; background:transparent;")
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
        dur.setFixedWidth(_pt(52))
        dur.setAlignment(Qt.AlignCenter)
        rl.addWidget(dur)

        # 来源标签
        if skill.source == "openclaw":
            src_l = QLabel("OpenClaw")
            src_l.setStyleSheet(f"""
                background:rgba(44,123,229,0.12); color:{C_BLUE};
                border-radius:4px; padding:1px 6px; font-size:{_pt(9)}pt;
            """)
            rl.addWidget(src_l)

        # 操作按钮
        if has_cmds:
            run_b = _btn("▶  运行", primary=True, small=True)
            run_b.clicked.connect(lambda _, s=skill: _open_run(s))
            rl.addWidget(run_b)
        doc_b = _btn("📖", small=True)
        doc_b.setFixedWidth(_pt(46))
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
        wl.setSpacing(8)

        if not filtered:
            wl.addWidget(_lbl("暂无符合条件的 Skill", 13, C_TEXT3))
        else:
            # 按分类分组
            groups: dict[str, list] = {}
            for s in filtered:
                groups.setdefault(s.category, []).append(s)

            for cat_name, skills in groups.items():
                icon = CATEGORY_ICONS.get(cat_name, "🔧")
                # 分组标题
                title_row = QHBoxLayout()
                title_row.addWidget(_lbl(f"{icon}  {cat_name}", 13, C_TEXT2, bold=True))
                title_row.addWidget(_lbl(f"  {len(skills)} 个", 10, C_TEXT3))
                title_row.addStretch()
                title_w = QWidget()
                title_w.setStyleSheet("background:transparent;")
                title_w.setLayout(title_row)
                wl.addWidget(title_w)

                for skill in skills:
                    wl.addWidget(_build_row(skill))

                wl.addSpacing(8)

        wl.addStretch()
        list_outer.addWidget(w)
        _list_ref[0] = w

    # ── 初始化 ──
    _rebuild()
    lay.addStretch()
    scroll.setWidget(inner)
    root.addWidget(scroll, 1)
    return page
