"""Skills 中心页 — 无边框大气风格
包含：分类筛选、搜索、精选/全部切换、运行对话框（含风险确认）、文档查看、右侧 AI 面板。
"""
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QScrollArea,
    QDialog, QTextEdit, QMessageBox, QSizePolicy,
    QStackedWidget, QProgressBar,
)

from seeed_jetson_develop.core.runner import Runner, SSHRunner, get_runner
from seeed_jetson_develop.core.platform_detect import is_jetson


def _can_execute_from_current_env(parent: QWidget) -> bool:
    if is_jetson() or isinstance(get_runner(), SSHRunner):
        return True
    _show_info_message(
        parent,
        "需要远程连接",
        "当前运行在 PC 上，运行 Skill 前必须先在「远程开发」页连接 Jetson 设备。",
    )
    return False


from seeed_jetson_develop.modules.skills.engine import (
    load_all_variants, Skill, CATEGORY_ICONS,
)
from seeed_jetson_develop.gui.ai_chat import _DEFAULT_SYSTEM
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, make_input_card as _input_card,
    apply_shadow as _shadow,
    show_info_message as _show_info_message,
)


# ── SkillGroup：同一 slug 的多版本聚合 ───────────────────────────────────────
from dataclasses import dataclass, field as _field
from typing import Optional as _Optional

@dataclass
class SkillGroup:
    id:            str
    name:          str
    desc:          str
    category:      str
    duration_hint: str
    verified:      bool
    risk:          str
    builtin:       _Optional[Skill] = None          # 精选内置（无文件安装）
    variants:      dict = _field(default_factory=dict)  # source -> Skill


def _group_skills(skills: list) -> list:
    """将 Skill 列表按 id 聚合为 SkillGroup 列表。"""
    groups: dict = {}
    for s in skills:
        if s.id not in groups:
            groups[s.id] = SkillGroup(
                id=s.id, name=s.name, desc=s.desc,
                category=s.category, duration_hint=s.duration_hint,
                verified=s.verified, risk=s.risk,
            )
        g = groups[s.id]
        if s.source == "builtin":
            g.builtin = s
        else:
            g.variants[s.source] = s
    return list(groups.values())


# ── Skills 数据加载线程 ───────────────────────────────────────────────────────
import logging as _logging
_log = _logging.getLogger("seeed.skills.page")

class _LoadThread(QThread):
    partial = pyqtSignal(list)
    loaded  = pyqtSignal(list)

    def run(self):
        import time as _t
        _t0 = _t.time()
        import seeed_jetson_develop.modules.skills.engine as _eng
        from seeed_jetson_develop.modules.skills.engine import (
            _scan_skill_dir, _OPENCLAW, _CLAUDE, _CODEX,
        )
        _log.info("[skills-thread] start, cache=%s", _eng._variants_cache is not None)
        if _eng._variants_cache is not None:
            self.loaded.emit(_eng._variants_cache)
            _log.info("[skills-thread] cache hit, emit in %.0fms", (_t.time()-_t0)*1000)
            return
        all_skills: list = []
        for root, filename, source, cap in [
            (_OPENCLAW, "SKILL.md",  "openclaw", 100),
            (_CLAUDE,   "CLAUDE.md", "claude",   100),
            (_CODEX,    "AGENTS.md", "codex",    100),
        ]:
            _ts = _t.time()
            batch = _scan_skill_dir(root, filename, source, cap, fast=True)
            _log.info("[skills-thread] scan %s: %d skills in %.0fms", source, len(batch), (_t.time()-_ts)*1000)
            all_skills.extend(batch)
            if batch:
                self.partial.emit(list(all_skills))
        _eng._variants_cache = all_skills
        self.loaded.emit(all_skills)
        _log.info("[skills-thread] done, total %d skills in %.0fms", len(all_skills), (_t.time()-_t0)*1000)


# ── Skill 安装线程（SFTP 文件拷贝到 Jetson） ─────────────────────────────────
class _InstallThread(QThread):
    log      = pyqtSignal(str)
    progress = pyqtSignal(int, int)   # current, total
    done     = pyqtSignal(bool, str)

    def __init__(self, skill: Skill, dest_path: str):
        super().__init__()
        self._skill     = skill
        self._dest      = dest_path.rstrip("/")
        self._cancel    = False

    def cancel(self):
        self._cancel = True

    def run(self):
        from pathlib import Path
        from seeed_jetson_develop.core.runner import get_runner, SSHRunner
        runner = get_runner()
        if not isinstance(runner, SSHRunner):
            self.done.emit(False, "未连接 SSH，无法安装")
            return

        skill_dir = Path(self._skill.md_path).parent
        files = []
        for root, _, fnames in __import__("os").walk(str(skill_dir)):
            for fn in fnames:
                lp = Path(root) / fn
                rel = lp.relative_to(skill_dir)
                files.append((lp, str(rel)))

        total = len(files)
        if total == 0:
            self.done.emit(False, "skill 目录为空")
            return

        # 创建远端目录
        self.log.emit(f"创建目录 {self._dest} …")
        rc, _ = runner.run(f"mkdir -p {self._dest}", timeout=10)
        if rc != 0:
            self.done.emit(False, f"mkdir 失败 (rc={rc})")
            return

        # SFTP 不展开 ~，需要获取真实 home 路径
        dest = self._dest
        if dest.startswith("~"):
            rc2, home = runner.run("echo $HOME", timeout=5)
            home = home.strip() if rc2 == 0 and home.strip() else "/home/seeed"
            dest = home + dest[1:]

        try:
            sftp_client, sftp = runner.open_sftp()
        except Exception as e:
            self.done.emit(False, f"SFTP 打开失败: {e}")
            return

        try:
            for i, (local_path, rel) in enumerate(files, 1):
                if self._cancel:
                    self.done.emit(False, "已取消")
                    return
                remote_path = f"{dest}/{rel}".replace("\\", "/")
                # 确保子目录存在
                remote_dir = remote_path.rsplit("/", 1)[0]
                try:
                    sftp.stat(remote_dir)
                except IOError:
                    runner.run(f"mkdir -p {remote_dir}", timeout=10)
                self.log.emit(f"上传 {rel}")
                sftp.put(str(local_path), remote_path)
                self.progress.emit(i, total)
        except Exception as e:
            self.done.emit(False, f"上传失败: {e}")
            return
        finally:
            sftp.close()
            sftp_client.close()

        self.done.emit(True, f"{self._skill.name} 已安装到 {dest}")


# ── 安装对话框 ────────────────────────────────────────────────────────────────
_SOURCE_LABEL = {
    "openclaw": "OpenClaw",
    "claude":   "Claude",
    "codex":    "Codex",
    "builtin":  "精选",
}
_SOURCE_COLOR = {
    "openclaw": ("#4C82FF", "rgba(76,130,255,0.15)"),
    "claude":   ("#A864FF", "rgba(168,100,255,0.15)"),
    "codex":    ("#FFB43C", "rgba(255,180,60,0.15)"),
    "builtin":  ("#8DC21F", "rgba(141,194,31,0.15)"),
}

class _InstallDialog(QDialog):
    install_done = pyqtSignal(str, str, bool)   # skill_id, source, success

    def __init__(self, skill: Skill, parent=None):
        super().__init__(parent)
        from pathlib import Path
        self._skill  = skill
        self._thread = None

        self.setWindowTitle(f"安装 Skill — {skill.name}")
        self.setMinimumSize(680, 580)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        # 标题行
        title_row = QHBoxLayout()
        cat_icon = CATEGORY_ICONS.get(skill.category, "🔧")
        title_row.addWidget(_lbl(f"{cat_icon}  {skill.name}", 16, C_TEXT, bold=True))
        title_row.addStretch()
        # 来源徽章
        fg, bg = _SOURCE_COLOR.get(skill.source, ("#8DC21F", "rgba(141,194,31,0.15)"))
        src_badge = QLabel(_SOURCE_LABEL.get(skill.source, skill.source))
        src_badge.setStyleSheet(f"""
            background:{bg}; color:{fg};
            border-radius:4px; padding:2px 10px;
            font-size:{_pt(9)}pt; font-weight:600;
        """)
        title_row.addWidget(src_badge)
        lay.addLayout(title_row)

        lay.addWidget(_lbl(skill.desc, 12, C_TEXT2, wrap=True))

        # 文件列表
        skill_dir = Path(skill.md_path).parent if skill.md_path else None
        file_list: list[str] = []
        if skill_dir and skill_dir.exists():
            import os
            for root, _, fnames in os.walk(str(skill_dir)):
                for fn in fnames:
                    lp = Path(root) / fn
                    rel = str(lp.relative_to(skill_dir)).replace("\\", "/")
                    file_list.append(rel)

        lay.addWidget(_lbl(f"将复制以下 {len(file_list)} 个文件到 Jetson：", 11, C_TEXT3))
        file_view = QTextEdit()
        file_view.setReadOnly(True)
        file_view.setFixedHeight(100)
        file_view.setPlainText("\n".join(f"  📄 {f}" for f in sorted(file_list)) or "  （无文件）")
        file_view.setStyleSheet(f"""
            background:{C_CARD_LIGHT}; border:none; border-radius:10px;
            color:{C_TEXT2};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(10)}pt; padding:12px;
        """)
        lay.addWidget(file_view)

        # 安装路径提示（只读展示）
        _DEST_MAP = {
            "claude":   f"~/.claude/skills/{skill.id}/",
            "openclaw": f"~/.openclaw/skills/{skill.id}/",
            "codex":    f"~/.codex/skills/{skill.id}/",
        }
        self._dest = _DEST_MAP.get(skill.source, f"~/skills/{skill.id}/")
        dest_lbl = _lbl(f"安装路径：{self._dest}", 11, C_TEXT3)
        lay.addWidget(dest_lbl)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(_pt(6))
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(f"""
            QProgressBar {{ background:{C_CARD_LIGHT}; border:none; border-radius:3px; }}
            QProgressBar::chunk {{ background:{C_GREEN}; border-radius:3px; }}
        """)
        lay.addWidget(self._progress)

        # 日志区
        lay.addWidget(_lbl("安装日志", 11, C_TEXT3))
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setStyleSheet(f"""
            background:{C_CARD}; border:none; border-radius:10px;
            color:{C_GREEN};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(10)}pt; padding:12px;
        """)
        lay.addWidget(self._log_edit, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self._install_btn = _btn("开始安装", primary=True)
        self._stop_btn    = _btn("停止", danger=True)
        self._stop_btn.setEnabled(False)
        close_btn = _btn("关闭")
        self._ai_btn = _btn("问 AI", primary=False, small=True)
        self._ai_btn.setVisible(False)
        self._ai_btn.clicked.connect(self._ask_ai)
        btn_row.addWidget(self._install_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._ai_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._install_btn.clicked.connect(self._start)
        self._stop_btn.clicked.connect(self._stop)
        close_btn.clicked.connect(self.close)

        if not file_list:
            self._install_btn.setEnabled(False)
            self._install_btn.setText("无可安装文件")

    def _append(self, text: str):
        self._log_edit.moveCursor(QTextCursor.End)
        self._log_edit.insertPlainText(text + "\n")
        self._log_edit.ensureCursorVisible()

    def _on_progress(self, cur: int, total: int):
        self._progress.setValue(int(cur / total * 100))

    def _start(self):
        self._log_edit.clear()
        self._ai_btn.setVisible(False)
        self._progress.setValue(0)
        self._install_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        t = _InstallThread(self._skill, self._dest)
        t.log.connect(self._append)
        t.progress.connect(self._on_progress)
        t.done.connect(self._on_done)
        t.start()
        self._thread = t

    def _stop(self):
        if self._thread:
            self._thread.cancel()

    def _on_done(self, success: bool, msg: str):
        self._install_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        if success:
            self._progress.setValue(100)
            self._append(f"\n✅ {msg}")
            self.install_done.emit(self._skill.id, self._skill.source, True)
        else:
            self._append(f"\n❌ {msg}")
            self._ai_btn.setVisible(True)
            self.install_done.emit(self._skill.id, self._skill.source, False)

    def _ask_ai(self):
        host = self.parent().window() if self.parent() else None
        assistant = getattr(host, "_floating_ai", None)
        if assistant:
            log_text = self._log_edit.toPlainText()
            assistant.inject_error(self._skill.name, log_text)


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


# ── 主页面 ───────────────────────────────────────────────────────────────────
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

    # ── AI 面板（右侧，供后续注入上下文） ──
    skills_system = _DEFAULT_SYSTEM + (
        "\n\n你当前在 Skills 中心页面。用户可以点击 Skill 行上的「问 AI」按钮，"
        "你会收到该 Skill 的名称、描述和命令，请帮用户理解它的用途、适用场景和注意事项。"
        "也可以根据用户的需求，推荐合适的 Skill。"
    )

    # ── 状态容器 ──
    # builtin skills 同步加载（JSON，极快），外部 variants 后台懒加载
    _groups_ref: list = [[]]   # SkillGroup 列表，后台加载后更新
    _variant_loaded  = [False]
    _completed: set  = set()
    _filter     = {"cat": "全部", "search": ""}
    _list_ref   = [None]

    # ── 滚动区域 ──
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setStyleSheet("background:transparent; border:none;")
    inner = QWidget()
    inner.setStyleSheet(f"background:{C_BG};")
    inner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
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
    _banner_sub = _lbl(
        "正在加载 OpenClaw / Claude / Codex 技能库…",
        11, C_TEXT3
    )
    tc.addWidget(_banner_sub)
    bl.addLayout(tc, 1)
    lay.addWidget(banner)

    # ── 搜索行 ──
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
    search_edit.setFixedHeight(_pt(40))
    search_edit.textChanged.connect(lambda t: (_filter.update({"search": t}), _rebuild()))
    lay.addWidget(search_edit)

    # ── 分类 tab 行（横向可滚动） ──
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

    # tab 容器放在横向 QScrollArea 里，避免溢出
    _tab_container = QWidget()
    _tab_container.setStyleSheet("background:transparent;")
    filter_row = QHBoxLayout(_tab_container)
    filter_row.setContentsMargins(0, 0, 0, 0)
    filter_row.setSpacing(6)

    tab_scroll = QScrollArea()
    tab_scroll.setWidgetResizable(True)
    tab_scroll.setFixedHeight(_pt(48))
    tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    tab_scroll.setStyleSheet("background:transparent; border:none;")
    tab_scroll.setWidget(_tab_container)
    lay.addWidget(tab_scroll)

    def _add_tab_btn(cat: str):
        b = QPushButton(cat)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(_tab_style(cat == _filter["cat"]))
        b.clicked.connect(lambda _, c=cat: _on_tab(c))
        _tab_btns[cat] = b
        filter_row.insertWidget(len(_tab_btns) - 1, b)

    _add_tab_btn("全部")
    filter_row.addStretch()
    _tab_count_ref = [len(_tab_btns)]

    # ── 计数行 ──
    count_row = QHBoxLayout()
    _count_lbl = _lbl("", 12, C_TEXT3)
    count_row.addWidget(_count_lbl)
    count_row.addStretch()
    lay.addLayout(count_row)

    def _on_variants_loaded(variants: list):
        import time as _t; _t0 = _t.time()
        _variant_loaded[0] = True
        _groups_ref[0] = _group_skills(variants)
        _log.info("[skills] _on_variants_loaded: %d variants -> %d groups", len(variants), len(_groups_ref[0]))
        # 补充新分类 tab
        for g in _groups_ref[0]:
            if g.category not in _tab_btns:
                b = QPushButton(g.category)
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(_tab_style(False))
                b.clicked.connect(lambda _, c=g.category: _on_tab(c))
                _tab_btns[g.category] = b
                filter_row.insertWidget(_tab_count_ref[0], b)
                _tab_count_ref[0] += 1
        _log.info("[skills] tabs done in %.0fms, calling _rebuild...", (_t.time()-_t0)*1000)
        _rebuild()

    def _on_load_complete(variants: list):
        total = len(_groups_ref[0])
        installable = len([g for g in _groups_ref[0] if g.variants])
        _banner_sub.setText(
            f"共 {total} 个 Skill，{installable} 个有 OpenClaw / Claude / Codex 版本可安装"
        )

    # 延迟 50ms 再启动加载线程（让页面先渲染出来）
    # 必须挂到 page 上防止 GC 回收（build_page 返回后局部变量会被释放）
    _load_thread = _LoadThread()
    _load_thread.setParent(page)
    _load_thread.loaded.connect(_on_variants_loaded)
    _load_thread.loaded.connect(_on_load_complete)
    QTimer.singleShot(50, _load_thread.start)

    # ── 列表容器：用 QWidget 包裹 QVBoxLayout，避免裸 layout 导致 setWidget 极慢 ──
    _list_container = QWidget()
    _list_container.setStyleSheet("background:transparent;")
    list_outer = QVBoxLayout(_list_container)
    list_outer.setContentsMargins(0, 0, 0, 0)
    list_outer.setSpacing(0)
    lay.addWidget(_list_container)

    # ── 对话框入口 ──
    def _open_install(skill: Skill):
        if not _can_execute_from_current_env(page):
            return
        dlg = _InstallDialog(skill, parent=page)
        dlg.install_done.connect(_on_install_done)
        dlg.exec_()

    def _open_doc(group: SkillGroup):
        # 优先显示 openclaw 版本，其次 claude/codex，最后 builtin
        ref = (group.variants.get("openclaw")
               or group.variants.get("claude")
               or group.variants.get("codex")
               or group.builtin)
        if ref:
            dlg = _DocDialog(ref, parent=page)
            dlg.exec_()

    def _open_ai(group: SkillGroup):
        ref = (group.variants.get("openclaw")
               or group.variants.get("claude")
               or group.variants.get("codex")
               or group.builtin)
        if not ref:
            return
        host = page.window()
        assistant = getattr(host, "_floating_ai", None)
        if assistant:
            assistant.inject_context(ref.name, ref.desc, ref.commands or [])

    def _on_install_done(skill_id: str, source: str, success: bool):
        if success:
            _completed.add((skill_id, source))
            _rebuild()

    # ── 构建单条 SkillGroup 行 ────────────────────────────────────────────────
    _INSTALL_BTN_STYLE = {
        "openclaw": (
            "rgba(76,130,255,0.15)", "#4C82FF",
            "rgba(76,130,255,0.28)", "#4C82FF",
        ),
        "claude": (
            "rgba(168,100,255,0.15)", "#A864FF",
            "rgba(168,100,255,0.28)", "#A864FF",
        ),
        "codex": (
            "rgba(255,180,60,0.15)", "#FFB43C",
            "rgba(255,180,60,0.28)", "#FFB43C",
        ),
    }
    _INSTALL_BTN_DONE_STYLE = (
        "rgba(122,179,23,0.15)", "#8DC21F",
        "rgba(122,179,23,0.25)", "#8DC21F",
    )

    # ── 预计算样式字符串（避免每行重复 f-string + CSS 解析） ──────────────────
    _S_ROW        = f"background:{C_CARD}; border:none; border-radius:10px;"
    _S_ROW_DONE   = "background:rgba(122,179,23,0.08); border:none; border-radius:10px;"
    _S_ICON       = f"font-size:{_pt(16)}pt; background:transparent;"
    _S_VERIFIED   = f"color:{C_GREEN}; font-size:{_pt(9)}pt; background:transparent; font-weight:700;"
    _S_INSTALLED  = f"color:{C_GREEN}; font-size:{_pt(9)}pt; background:rgba(122,179,23,0.12); border-radius:4px; padding:2px 8px; font-weight:600;"
    _S_RISK       = f"color:{C_ORANGE}; font-size:{_pt(9)}pt; background:transparent;"
    _S_AI_BTN     = f"""QPushButton {{
        background:rgba(44,123,229,0.15); border:none; border-radius:6px;
        color:{C_BLUE}; font-size:{_pt(10)}pt; font-weight:600;
        min-height:{_pt(28)}px;
    }}
    QPushButton:hover {{ background:rgba(44,123,229,0.28); }}"""
    _S_INSTALL_BTNS: dict = {}
    for _src_key, (_bg, _fg, _hbg, _hfg) in _INSTALL_BTN_STYLE.items():
        _S_INSTALL_BTNS[_src_key] = f"""QPushButton {{
            background:{_bg}; color:{_fg};
            border:none; border-radius:6px;
            font-size:{_pt(10)}pt; font-weight:600;
            padding:0 10px; min-height:{_pt(28)}px;
        }}
        QPushButton:hover {{ background:{_hbg}; color:{_hfg}; }}
        QPushButton:disabled {{ opacity:0.6; }}"""
    _dbg, _dfg, _dhbg, _dhfg = _INSTALL_BTN_DONE_STYLE
    _S_INSTALL_DONE = f"""QPushButton {{
        background:{_dbg}; color:{_dfg};
        border:none; border-radius:6px;
        font-size:{_pt(10)}pt; font-weight:600;
        padding:0 10px; min-height:{_pt(28)}px;
    }}
    QPushButton:hover {{ background:{_dhbg}; color:{_dhfg}; }}
    QPushButton:disabled {{ opacity:0.6; }}"""
    _S_TRANSPARENT = "background:transparent;"
    _ICON_W = _pt(26)
    _BTN_W  = _pt(40)
    _BTN_H  = _pt(28)

    def _make_install_btn(source: str, skill: Skill, is_done: bool) -> QPushButton:
        label = f"✓ {_SOURCE_LABEL[source]}" if is_done else f"⬇ {_SOURCE_LABEL[source]}"
        b = QPushButton(label)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(_S_INSTALL_DONE if is_done else _S_INSTALL_BTNS[source])
        if is_done:
            b.setEnabled(False)
        else:
            b.clicked.connect(lambda _, s=skill: _open_install(s))
        return b

    def _build_row(group: SkillGroup) -> QFrame:
        any_done = any((group.id, src) in _completed for src in group.variants)
        cat_icon = CATEGORY_ICONS.get(group.category, "🔧")

        row = QFrame()
        row.setStyleSheet(_S_ROW_DONE if any_done else _S_ROW)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        outer = QVBoxLayout(row)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(4)

        # ── 行1：图标+名称+徽章 合并为单个 rich-text QLabel（减少 widget 数量） ──
        parts = [
            f'<span style="font-size:{_pt(15)}pt">{cat_icon}</span>',
            f'&nbsp;<b style="font-size:{_pt(13)}pt;color:{C_TEXT}">{group.name}</b>',
        ]
        if group.verified:
            parts.append(f'&nbsp;<span style="font-size:{_pt(9)}pt;color:{C_GREEN};font-weight:700"> ✓ 已验证</span>')
        if any_done:
            parts.append(f'&nbsp;<span style="font-size:{_pt(9)}pt;color:{C_GREEN};font-weight:600"> ● 已安装</span>')
        if group.risk:
            parts.append(f'&nbsp;<span style="font-size:{_pt(9)}pt;color:{C_ORANGE}"> ⚠ 有风险</span>')
        parts.append(f'<span style="float:right;font-size:{_pt(10)}pt;color:{C_TEXT3}">{group.duration_hint}</span>')
        top_lbl = QLabel("".join(parts))
        top_lbl.setTextFormat(Qt.RichText)
        top_lbl.setStyleSheet(_S_TRANSPARENT)
        outer.addWidget(top_lbl)

        # ── 行2：描述 ──
        outer.addWidget(_lbl(group.desc, 11, C_TEXT2, wrap=True))

        # ── 行3：安装按钮 + 工具按钮 ──
        btn_line = QHBoxLayout()
        btn_line.setSpacing(6)
        btn_line.addStretch()

        for src in ("openclaw", "claude", "codex"):
            skill = group.variants.get(src)
            if skill:
                btn_line.addWidget(_make_install_btn(src, skill, (group.id, src) in _completed))

        doc_b = _btn("📖", small=True)
        doc_b.setFixedWidth(_BTN_W)
        doc_b.clicked.connect(lambda _, g=group: _open_doc(g))
        btn_line.addWidget(doc_b)

        ai_b = QPushButton("AI")
        ai_b.setCursor(Qt.PointingHandCursor)
        ai_b.setFixedWidth(_BTN_W)
        ai_b.setStyleSheet(_S_AI_BTN)
        ai_b.clicked.connect(lambda _, g=group: _open_ai(g))
        btn_line.addWidget(ai_b)

        outer.addLayout(btn_line)
        return row

    # ── 重建列表（同步渲染 + setUpdatesEnabled 抑制 layout 抖动） ──
    _batch_gen = [0]

    def _clear_list_outer():
        while list_outer.count():
            item = list_outer.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rebuild():
        import time as _t; _t0 = _t.time()
        _batch_gen[0] += 1
        gen = _batch_gen[0]
        _clear_list_outer()
        _log.info("[skills] _rebuild: gen=%d, clear done in %.0fms", gen, (_t.time()-_t0)*1000)

        cat = _filter["cat"]
        kw  = _filter["search"].lower()

        filtered = [g for g in _groups_ref[0]
                    if (cat == "全部" or g.category == cat)
                    and (not kw or kw in g.name.lower()
                         or kw in g.desc.lower() or kw in g.id.lower())]
        _count_lbl.setText(f"共 {len(filtered)} 个 Skill")

        # 在脱离 layout 树的 w 上构建，完成后一次性挂入 list_outer
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(10)

        if not filtered:
            wl.addWidget(_lbl("暂无符合条件的 Skill", 14, C_TEXT3))
            wl.addStretch()
            list_outer.addWidget(w)
            _list_ref[0] = w
            return

        # 展开为渲染队列
        PAGE_SIZE = 20   # 首次只渲染前 20 个 group
        render_queue: list = []
        cat_groups: dict[str, list] = {}
        for g in filtered:
            cat_groups.setdefault(g.category, []).append(g)

        shown_count = [0]
        all_render_queue: list = []   # 完整队列（用于"加载全部"）
        for cat_name, groups in cat_groups.items():
            all_render_queue.append(("header", cat_name, len(groups)))
            for g in groups:
                all_render_queue.append(("group", g))
            all_render_queue.append(("spacing",))

        # 首页只取前 PAGE_SIZE 个 group
        first_page: list = []
        cnt = 0
        for cat_name, groups in cat_groups.items():
            if cnt >= PAGE_SIZE:
                break
            first_page.append(("header", cat_name, len(groups)))
            for g in groups:
                if cnt >= PAGE_SIZE:
                    break
                first_page.append(("group", g))
                cnt += 1
            first_page.append(("spacing",))
        render_queue = first_page
        shown_count[0] = cnt
        has_more = len(filtered) > PAGE_SIZE

        _log.info("[skills] _rebuild: %d filtered, showing first %d, %d render_items", len(filtered), cnt, len(render_queue))

        idx = [0]
        BATCH = 6
        _t_batch_start = [_t.time()]

        def _render_items(items: list, target_layout, on_done=None):
            """分批渲染 items 到 target_layout（w 脱离 layout 树）"""
            ridx = [0]
            def _batch():
                if _batch_gen[0] != gen:
                    return
                end = min(ridx[0] + BATCH, len(items))
                for i in range(ridx[0], end):
                    item = items[i]
                    if item[0] == "header":
                        _, cname, cnt = item
                        icon = CATEGORY_ICONS.get(cname, "🔧")
                        tr = QHBoxLayout()
                        tr.addWidget(_lbl(f"{icon}  {cname}", 14, C_TEXT2, bold=True))
                        tr.addWidget(_lbl(f"  {cnt} 个", 10, C_TEXT3))
                        tr.addStretch()
                        tw = QWidget()
                        tw.setStyleSheet(_S_TRANSPARENT)
                        tw.setLayout(tr)
                        target_layout.addWidget(tw)
                    elif item[0] == "group":
                        target_layout.addWidget(_build_row(item[1]))
                    elif item[0] == "spacing":
                        target_layout.addSpacing(10)
                ridx[0] = end
                if ridx[0] < len(items):
                    QTimer.singleShot(10, _batch)
                elif on_done:
                    on_done()
            QTimer.singleShot(0, _batch)

        def _on_first_page_done():
            import time as _tb
            # "加载更多" 按钮
            if has_more:
                more_btn = QPushButton(f"加载全部 {len(filtered)} 个 Skill…")
                more_btn.setCursor(Qt.PointingHandCursor)
                more_btn.setStyleSheet(f"""QPushButton {{
                    background:rgba(122,179,23,0.10); border:none; border-radius:8px;
                    color:{C_GREEN}; font-size:{_pt(12)}pt; font-weight:600;
                    padding:12px; min-height:{_pt(36)}px;
                }}
                QPushButton:hover {{ background:rgba(122,179,23,0.20); }}""")

                def _load_all():
                    more_btn.setText("正在加载…")
                    more_btn.setEnabled(False)
                    # 渲染剩余 items（跳过已渲染的前 PAGE_SIZE 个 group）
                    rest: list = []
                    skip = PAGE_SIZE
                    for cat_name, groups in cat_groups.items():
                        rest_groups = []
                        for g in groups:
                            if skip > 0:
                                skip -= 1
                                continue
                            rest_groups.append(g)
                        if rest_groups:
                            rest.append(("header", cat_name, len(rest_groups)))
                            for g in rest_groups:
                                rest.append(("group", g))
                            rest.append(("spacing",))

                    def _on_rest_done():
                        more_btn.setParent(None)
                        more_btn.deleteLater()
                        wl.addStretch()
                        _log.info("[skills] load-all done, total %d groups", len(filtered))

                    _render_items(rest, wl, on_done=_on_rest_done)

                more_btn.clicked.connect(_load_all)
                wl.addWidget(more_btn)

            wl.addStretch()
            list_outer.addWidget(w)
            _list_ref[0] = w
            _log.info("[skills] first page done in %.0fms", (_tb.time()-_t_batch_start[0])*1000)

        _render_items(render_queue, wl, on_done=_on_first_page_done)

    # ── 初始占位：加载完成前显示提示 ──
    _loading_lbl = _lbl("正在扫描技能库，请稍候…", 13, C_TEXT3)
    _loading_lbl.setAlignment(Qt.AlignCenter)
    list_outer.addWidget(_loading_lbl)
    list_outer.addStretch()

    lay.addStretch()
    scroll.setWidget(inner)

    # ── 左右分栏：skills 列表 + AI 面板 ──
    root.addWidget(scroll, 1)
    return page
