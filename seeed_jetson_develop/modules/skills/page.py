"""Skills center page."""
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
from seeed_jetson_develop.gui.i18n import get_language, t


def _can_execute_from_current_env(parent: QWidget) -> bool:
    if is_jetson() or isinstance(get_runner(), SSHRunner):
        return True
    _show_info_message(
        parent,
        _t("skills.msg.remote_required.title"),
        _t("skills.msg.remote_required.body"),
    )
    return False


from seeed_jetson_develop.modules.skills.engine import (
    load_all_variants, Skill, CATEGORY_ICONS, normalize_category,
)
from seeed_jetson_develop.gui.ai_chat import _DEFAULT_SYSTEM
from seeed_jetson_develop.gui.i18n_binding import I18nBinding
from seeed_jetson_develop.gui.runtime_i18n import apply_dialog_language as _apply_dlg_lang
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, make_input_card as _input_card,
    apply_shadow as _shadow,
    show_info_message as _show_info_message,
)


# SkillGroup: aggregate multi-source variants by skill id
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
    wiki_url:      str = ""
    builtin:       _Optional[Skill] = None          # Featured built-in (no file install)
    variants:      dict = _field(default_factory=dict)  # source -> Skill


def _group_skills(skills: list) -> list:
    """Aggregate skills by id into SkillGroup list."""
    groups: dict = {}
    for s in skills:
        category_key = normalize_category(s.category)
        if s.id not in groups:
            groups[s.id] = SkillGroup(
                id=s.id, name=s.name, desc=s.desc,
                category=category_key, duration_hint=s.duration_hint,
                verified=s.verified, risk=s.risk,
                wiki_url=s.wiki_url,
            )
        g = groups[s.id]
        # Prefer source with wiki_url.
        if s.wiki_url and not g.wiki_url:
            g.wiki_url = s.wiki_url
        if s.source == "builtin":
            g.builtin = s
        else:
            g.variants[s.source] = s
    return list(groups.values())


# Skills background loader thread
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


# Skill install thread (SFTP copy to Jetson)
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
            self.done.emit(False, _t("skills.install.err.ssh_not_connected"))
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
            self.done.emit(False, _t("skills.install.err.empty_dir"))
            return

        # Create remote directory.
        self.log.emit(_t("skills.install.log.create_dir", path=self._dest))
        rc, _ = runner.run(f"mkdir -p {self._dest}", timeout=10)
        if rc != 0:
            self.done.emit(False, _t("skills.install.err.mkdir_failed", rc=rc))
            return

        # SFTP does not expand "~"; resolve actual home path.
        dest = self._dest
        if dest.startswith("~"):
            rc2, home = runner.run("echo $HOME", timeout=5)
            home = home.strip() if rc2 == 0 and home.strip() else "/home/seeed"
            dest = home + dest[1:]

        try:
            sftp_client, sftp = runner.open_sftp()
        except Exception as e:
            self.done.emit(False, _t("skills.install.err.sftp_open_failed", error=e))
            return

        try:
            for i, (local_path, rel) in enumerate(files, 1):
                if self._cancel:
                    self.done.emit(False, "Cancelled")
                    return
                remote_path = f"{dest}/{rel}".replace("\\", "/")
                # Ensure subdirectory exists.
                remote_dir = remote_path.rsplit("/", 1)[0]
                try:
                    sftp.stat(remote_dir)
                except IOError:
                    runner.run(f"mkdir -p {remote_dir}", timeout=10)
                self.log.emit(_t("skills.install.log.uploading", path=rel))
                sftp.put(str(local_path), remote_path)
                self.progress.emit(i, total)
        except Exception as e:
            self.done.emit(False, _t("skills.install.err.upload_failed", error=e))
            return
        finally:
            sftp.close()
            sftp_client.close()

        self.done.emit(True, _t("skills.install.done.ok", name=self._skill.name, dest=dest))


# Install dialog
_SOURCE_LABEL = {
    "openclaw": "skills.source.openclaw",
    "claude":   "skills.source.claude",
    "codex":    "skills.source.codex",
    "builtin":  "skills.source.featured",
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

        self.setWindowTitle(_t("skills.install.dialog.title", name=skill.name))
        self.setMinimumSize(_pt(680), _pt(480))
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

        # Header
        title_row = QHBoxLayout()
        cat_icon = CATEGORY_ICONS.get(skill.category, "🔧")
        title_row.addWidget(_lbl(f"{cat_icon}  {skill.name}", 16, C_TEXT, bold=True))
        title_row.addStretch()
        # Source badge
        fg, bg = _SOURCE_COLOR.get(skill.source, ("#8DC21F", "rgba(141,194,31,0.15)"))
        src_badge = QLabel(_t(_SOURCE_LABEL.get(skill.source, "skills.source.featured")))
        src_badge.setStyleSheet(f"""
            background:{bg}; color:{fg};
            border-radius:4px; padding:2px 10px;
            font-size:{_pt(9)}pt; font-weight:600;
        """)
        title_row.addWidget(src_badge)
        lay.addLayout(title_row)

        lay.addWidget(_lbl(skill.desc, 12, C_TEXT2, wrap=True))

        # File list
        skill_dir = Path(skill.md_path).parent if skill.md_path else None
        file_list: list[str] = []
        if skill_dir and skill_dir.exists():
            import os
            for root, _, fnames in os.walk(str(skill_dir)):
                for fn in fnames:
                    lp = Path(root) / fn
                    rel = str(lp.relative_to(skill_dir)).replace("\\", "/")
                    file_list.append(rel)

        lay.addWidget(_lbl(_t("skills.install.files_to_copy", count=len(file_list)), 11, C_TEXT3))
        file_view = QTextEdit()
        file_view.setReadOnly(True)
        file_view.setFixedHeight(_pt(100))
        file_view.setPlainText("\n".join(f"  📄 {f}" for f in sorted(file_list)) or "  (No files)")
        if not file_list:
            file_view.setPlainText(_t("skills.install.no_files_hint"))
        file_view.setStyleSheet(f"""
            background:{C_CARD_LIGHT}; border:none; border-radius:10px;
            color:{C_TEXT2};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(10)}pt; padding:12px;
        """)
        lay.addWidget(file_view)

        # Install path hint (read-only)
        _DEST_MAP = {
            "claude":   f"~/.claude/skills/{skill.id}/",
            "openclaw": f"~/.openclaw/skills/{skill.id}/",
            "codex":    f"~/.codex/skills/{skill.id}/",
        }
        self._dest = _DEST_MAP.get(skill.source, f"~/skills/{skill.id}/")
        dest_lbl = _lbl(_t("skills.install.path", path=self._dest), 11, C_TEXT3)
        lay.addWidget(dest_lbl)

        # Progress bar
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

        # Log area
        lay.addWidget(_lbl(_t("skills.install.log_title"), 11, C_TEXT3))
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setStyleSheet(f"""
            background:{C_CARD}; border:none; border-radius:10px;
            color:{C_GREEN};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:{_pt(10)}pt; padding:12px;
        """)
        self._log_edit.setMinimumHeight(_pt(140))
        lay.addWidget(self._log_edit, 1)
        lay.addStretch()

        # ── 底部按钮栏（固定，不随滚动） ──
        btn_frame = QWidget()
        btn_frame.setStyleSheet(f"background:{C_BG}; border-top:1px solid rgba(255,255,255,0.06);")
        btn_row = QHBoxLayout(btn_frame)
        btn_row.setContentsMargins(24, 12, 24, 16)
        btn_row.setSpacing(12)
        root_lay.addWidget(btn_frame)

        # Action row
        self._install_btn = _btn(_t("skills.install.btn.start"), primary=True)
        self._stop_btn    = _btn(_t("common.stop"), danger=True)
        self._stop_btn.setEnabled(False)
        close_btn = _btn(_t("common.close"))
        self._ai_btn = _btn(_t("common.ask_ai"), primary=False, small=True)
        self._ai_btn.setVisible(False)
        self._ai_btn.clicked.connect(self._ask_ai)
        btn_row.addWidget(self._install_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._ai_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(close_btn)

        self._install_btn.clicked.connect(self._start)
        self._stop_btn.clicked.connect(self._stop)
        close_btn.clicked.connect(self.close)

        if not file_list:
            self._install_btn.setEnabled(False)
            self._install_btn.setText(_t("skills.install.no_files"))

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
        self.setMinimumSize(_pt(720), _pt(580))
        self.setWindowTitle(_t("skills.doc.title", name=skill.name))
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
            md_text = _t("skills.doc.command_list_header") + "\n\n```bash\n" + "\n".join(skill.commands) + "\n```"

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

        close_btn = _btn(_t("common.close"))
        close_btn.clicked.connect(self.close)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

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


from seeed_jetson_develop.gui.widgets.page_base import PageBase

_ALL_CATEGORY = "all"
_CAT_TO_KEY = {
    _ALL_CATEGORY: "skills.category.all",
    "reference": "skills.category.reference",
    "network_remote": "skills.category.network_remote",
    "app_env_deploy": "skills.category.app_env_deploy",
    "system_tuning": "skills.category.system_tuning",
    "ai_llm": "skills.category.ai_llm",
    "vision_yolo": "skills.category.vision_yolo",
    "driver_repair": "skills.category.driver_repair",
}


def _t(key: str, **kwargs) -> str:
    return t(key, lang=get_language(), **kwargs)


def _cat_text(cat: str) -> str:
    return _t(_CAT_TO_KEY.get(cat, cat))

# Main page
class SkillsPage(PageBase):
    """Skills center list page."""

    def __init__(self):
        self._groups: list = []
        self._completed: set = set()
        self._filter = {"cat": _ALL_CATEGORY, "search": ""}
        self._tab_btns: dict = {}
        self._tab_count = 0
        self._batch_gen = 0
        self._load_thread = None
        self._banner_sub = None
        self._banner_title = None
        self._search_edit = None
        self._count_lbl = None
        self._list_outer = None
        self._filter_row = None
        self._tab_container = None

        super().__init__(
            title=_t("skills.page.title"),
            subtitle=_t("skills.page.subtitle"),
        )
        self._build_content()
        self._bind_i18n()
        QTimer.singleShot(50, self._start_load)

    def _build_content(self):
        lay = self.get_content_layout()

        # Intro banner
        banner = _card(12)
        banner.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(122,179,23,0.10), stop:1 rgba(44,123,229,0.06));"
            "border: 1px solid rgba(255,255,255,0.05); border-radius:12px;"
        )
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(20, 16, 20, 16)
        bl.addWidget(_lbl("💡", 24))
        bl.addSpacing(12)
        tc = QVBoxLayout()
        tc.setSpacing(4)
        self._banner_title = _lbl(_t("skills.banner.title"), 14, C_TEXT, bold=True)
        tc.addWidget(self._banner_title)
        self._banner_sub = _lbl(_t("skills.loading"), 11, C_TEXT3)
        tc.addWidget(self._banner_sub)
        bl.addLayout(tc, 1)
        lay.addWidget(banner)

        # Search box
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("🔍  " + _t("skills.search.placeholder"))
        search_edit.setStyleSheet(
            f"QLineEdit {{ background:{C_CARD_LIGHT}; border:none; border-radius:24px;"
            f"padding:8px 20px; color:{C_TEXT}; font-size:{_pt(12)}pt; }}"
            f"QLineEdit:focus {{ background:{C_CARD}; }}"
        )
        search_edit.setFixedHeight(_pt(40))
        search_edit.textChanged.connect(
            lambda t: (self._filter.update({"search": t}), self._rebuild())
        )
        lay.addWidget(search_edit)
        self._search_edit = search_edit

        # Category tab row
        self._tab_container = QWidget()
        self._tab_container.setStyleSheet("background:transparent;")
        self._filter_row = QHBoxLayout(self._tab_container)
        self._filter_row.setContentsMargins(0, 0, 0, 0)
        self._filter_row.setSpacing(6)

        tab_scroll = QScrollArea()
        tab_scroll.setWidgetResizable(True)
        tab_scroll.setFixedHeight(_pt(48))
        tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tab_scroll.setStyleSheet("background:transparent; border:none;")
        tab_scroll.setWidget(self._tab_container)
        lay.addWidget(tab_scroll)

        self._add_tab_btn(_ALL_CATEGORY)
        self._filter_row.addStretch()
        self._tab_count = len(self._tab_btns)

        # Count row
        count_row = QHBoxLayout()
        self._count_lbl = _lbl("", 12, C_TEXT3)
        count_row.addWidget(self._count_lbl)
        count_row.addStretch()
        lay.addLayout(count_row)

        # List container
        list_container = QWidget()
        list_container.setStyleSheet("background:transparent;")
        self._list_outer = QVBoxLayout(list_container)
        self._list_outer.setContentsMargins(0, 0, 0, 0)
        self._list_outer.setSpacing(0)
        lay.addWidget(list_container)

        loading_lbl = _lbl(_t("skills.loading"), 13, C_TEXT3)
        loading_lbl.setAlignment(Qt.AlignCenter)
        self._list_outer.addWidget(loading_lbl)
        self._list_outer.addStretch()
        lay.addStretch()

    # ── Tab ──

    def _tab_style(self, active: bool) -> str:
        return (
            f"QPushButton {{ background:{'rgba(122,179,23,0.15)' if active else 'transparent'};"
            f"border:none; border-radius:0px; color:{C_GREEN if active else C_TEXT2};"
            f"font-size:{_pt(11)}px; font-weight:{'600' if active else '400'};"
            f"padding:6px 16px; min-height:{_pt(32)}px; }}"
            f"QPushButton:hover {{ background:rgba(255,255,255,0.06); color:{C_TEXT}; }}"
        )

    def _add_tab_btn(self, cat: str):
        b = QPushButton(_cat_text(cat))
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(self._tab_style(cat == self._filter["cat"]))
        b.clicked.connect(lambda _, c=cat: self._on_tab(c))
        self._tab_btns[cat] = b
        self._filter_row.insertWidget(len(self._tab_btns) - 1, b)

    def _on_tab(self, label: str):
        self._filter["cat"] = label
        for lbl, b in self._tab_btns.items():
            b.setStyleSheet(self._tab_style(lbl == label))
        self._rebuild()

    # Background loading

    def _start_load(self):
        self._load_thread = _LoadThread()
        self._load_thread.setParent(self)
        self._load_thread.loaded.connect(self._on_variants_loaded)
        self._load_thread.loaded.connect(self._on_load_complete)
        self._load_thread.start()

    def _on_variants_loaded(self, variants: list):
        self._groups = _group_skills(variants)
        for g in self._groups:
            if g.category not in self._tab_btns:
                b = QPushButton(_cat_text(g.category))
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(self._tab_style(False))
                b.clicked.connect(lambda _, c=g.category: self._on_tab(c))
                self._tab_btns[g.category] = b
                self._filter_row.insertWidget(self._tab_count, b)
                self._tab_count += 1
        self._rebuild()

    def _on_load_complete(self, variants: list):
        total = len(self._groups)
        installable = len([g for g in self._groups if g.variants])
        self._banner_sub.setText(_t("skills.banner.summary", total=total, installable=installable))

    def _bind_i18n(self):
        self.i18n.bind_callable(lambda: self.set_header_text(_t("skills.page.title"), _t("skills.page.subtitle")))
        self.i18n.bind_text(self._banner_title, "skills.banner.title")
        self.i18n.bind_callable(lambda: self._search_edit.setPlaceholderText("🔍  " + _t("skills.search.placeholder")))
        self.i18n.bind_callable(self._apply_dynamic_i18n)

    def _apply_dynamic_i18n(self):
        for cat, b in self._tab_btns.items():
            b.setText(_cat_text(cat))
        if self._groups:
            total = len(self._groups)
            installable = len([g for g in self._groups if g.variants])
            self._banner_sub.setText(_t("skills.banner.summary", total=total, installable=installable))
        else:
            self._banner_sub.setText(_t("skills.loading"))

    def retranslate_ui(self, _lang_code: str | None = None):
        self.i18n.apply(_lang_code)
        self._rebuild()
        return
        self.set_header_text(_t("skills.page.title"), _t("skills.page.subtitle"))
        if self._banner_title:
            self._banner_title.setText(_t("skills.banner.title"))
        if self._search_edit:
            self._search_edit.setPlaceholderText("🔍  " + _t("skills.search.placeholder"))
        for cat, b in self._tab_btns.items():
            b.setText(_cat_text(cat))
        if self._groups:
            total = len(self._groups)
            installable = len([g for g in self._groups if g.variants])
            self._banner_sub.setText(_t("skills.banner.summary", total=total, installable=installable))
        else:
            self._banner_sub.setText(_t("skills.loading"))
        self._rebuild()

    # Dialogs

    def _open_install(self, skill: Skill):
        if not _can_execute_from_current_env(self):
            return
        dlg = _InstallDialog(skill, parent=self)
        dlg.install_done.connect(self._on_install_done)
        _apply_dlg_lang(dlg, self)
        dlg.exec_()

    def _open_doc(self, group: SkillGroup):
        ref = (group.variants.get("openclaw") or group.variants.get("claude")
               or group.variants.get("codex") or group.builtin)
        if ref:
            dlg = _DocDialog(ref, parent=self)
            _apply_dlg_lang(dlg, self)
            dlg.exec_()

    def _open_ai(self, group: SkillGroup):
        ref = (group.variants.get("openclaw") or group.variants.get("claude")
               or group.variants.get("codex") or group.builtin)
        if not ref:
            return
        assistant = getattr(self.window(), "_floating_ai", None)
        if assistant:
            assistant.inject_context(ref.name, ref.desc, ref.commands or [])

    def _on_install_done(self, skill_id: str, source: str, success: bool):
        if success:
            self._completed.add((skill_id, source))
            self._rebuild()

    # Row building

    def _install_btn_css(self, source: str, done: bool) -> str:
        STYLES = {
            "openclaw": ("rgba(76,130,255,0.15)",  "#4C82FF", "rgba(76,130,255,0.28)"),
            "claude":   ("rgba(168,100,255,0.15)", "#A864FF", "rgba(168,100,255,0.28)"),
            "codex":    ("rgba(255,180,60,0.15)",  "#FFB43C", "rgba(255,180,60,0.28)"),
        }
        if done:
            return (
                f"QPushButton {{ background:rgba(122,179,23,0.15); color:#8DC21F;"
                f"border:none; border-radius:6px; font-size:{_pt(10)}pt; font-weight:600;"
                f"padding:0 10px; min-height:{_pt(28)}px; }}"
                f"QPushButton:hover {{ background:rgba(122,179,23,0.25); }}"
                f"QPushButton:disabled {{ opacity:0.6; }}"
            )
        bg, fg, hbg = STYLES[source]
        return (
            f"QPushButton {{ background:{bg}; color:{fg};"
            f"border:none; border-radius:6px; font-size:{_pt(10)}pt; font-weight:600;"
            f"padding:0 10px; min-height:{_pt(28)}px; }}"
            f"QPushButton:hover {{ background:{hbg}; color:{fg}; }}"
            f"QPushButton:disabled {{ opacity:0.6; }}"
        )

    def _make_install_btn(self, source: str, skill: Skill, is_done: bool) -> QPushButton:
        source_label = _t(_SOURCE_LABEL[source])
        label = _t("skills.action.source_installed", source=source_label) if is_done else _t("skills.action.source_install", source=source_label)
        b = QPushButton(label)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(self._install_btn_css(source, is_done))
        if is_done:
            b.setEnabled(False)
        else:
            b.clicked.connect(lambda _, s=skill: self._open_install(s))
        return b

    def _build_row(self, group: SkillGroup) -> QFrame:
        any_done = any((group.id, src) in self._completed for src in group.variants)
        cat_icon = CATEGORY_ICONS.get(group.category, "🔧")
        BTN_W = _pt(40)

        row = QFrame()
        if any_done:
            row.setStyleSheet(
                "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 #203246, stop:1 #19293B);"
                "border: 1px solid rgba(122,179,23,0.22);"
                "border-radius:10px;"
            )
        else:
            row.setStyleSheet(
                "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 #1E2D40, stop:1 #192333);"
                "border: 1px solid rgba(255,255,255,0.05);"
                "border-radius:10px;"
            )
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        outer = QVBoxLayout(row)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(4)

        parts = [f'<span style="font-size:{_pt(15)}pt">{cat_icon}</span>',
                 f'&nbsp;<b style="font-size:{_pt(13)}pt;color:{C_TEXT}">{group.name}</b>']
        if group.verified:
            parts.append(f'&nbsp;<span style="font-size:{_pt(9)}pt;color:{C_GREEN};font-weight:700"> {_t("skills.badge.verified")}</span>')
        if any_done:
            parts.append(f'&nbsp;<span style="font-size:{_pt(9)}pt;color:{C_GREEN};font-weight:600"> {_t("skills.badge.installed")}</span>')
        if group.risk:
            parts.append(f'&nbsp;<span style="font-size:{_pt(9)}pt;color:{C_ORANGE}"> {_t("skills.badge.risk")}</span>')
        parts.append(f'<span style="float:right;font-size:{_pt(10)}pt;color:{C_TEXT3}">{group.duration_hint}</span>')
        top_lbl = QLabel("".join(parts))
        top_lbl.setTextFormat(Qt.RichText)
        top_lbl.setFrameShape(QFrame.NoFrame)
        top_lbl.setFrameShadow(QFrame.Plain)
        top_lbl.setLineWidth(0)
        top_lbl.setMidLineWidth(0)
        top_lbl.setContentsMargins(0, 0, 0, 0)
        top_lbl.setStyleSheet("QLabel { background:transparent; border:none; padding:0; margin:0; }")
        outer.addWidget(top_lbl)
        outer.addWidget(_lbl(group.desc, 11, C_TEXT2, wrap=True))

        btn_line = QHBoxLayout()
        btn_line.setSpacing(6)
        if group.wiki_url:
            wiki_b = QPushButton(_t("skills.btn.wiki"))
            wiki_b.setCursor(Qt.PointingHandCursor)
            wiki_b.setFixedWidth(BTN_W)
            wiki_b.setStyleSheet(
                f"QPushButton {{ background:rgba(255,180,60,0.12); border:none; border-radius:6px;"
                f"color:{C_ORANGE}; font-size:{_pt(10)}pt; font-weight:600; min-height:{_pt(28)}px; }}"
                f"QPushButton:hover {{ background:rgba(255,180,60,0.25); }}"
            )
            wiki_b.setToolTip(group.wiki_url)
            wiki_b.clicked.connect(lambda _, url=group.wiki_url: __import__("webbrowser").open(url))
            btn_line.addWidget(wiki_b)
        btn_line.addStretch()
        for src in ("openclaw", "claude", "codex"):
            skill = group.variants.get(src)
            if skill:
                btn_line.addWidget(self._make_install_btn(src, skill, (group.id, src) in self._completed))
        doc_b = _btn("📖", small=True)
        doc_b.setFixedWidth(BTN_W)
        doc_b.clicked.connect(lambda _, g=group: self._open_doc(g))
        btn_line.addWidget(doc_b)
        ai_b = QPushButton(_t("common.ai_short"))
        ai_b.setCursor(Qt.PointingHandCursor)
        ai_b.setFixedWidth(BTN_W)
        ai_b.setStyleSheet(
            f"QPushButton {{ background:rgba(44,123,229,0.15); border:none; border-radius:6px;"
            f"color:{C_BLUE}; font-size:{_pt(10)}pt; font-weight:600; min-height:{_pt(28)}px; }}"
            f"QPushButton:hover {{ background:rgba(44,123,229,0.28); }}"
        )
        ai_b.clicked.connect(lambda _, g=group: self._open_ai(g))
        btn_line.addWidget(ai_b)
        outer.addLayout(btn_line)
        return row

    # List rebuild

    def _clear_list(self):
        while self._list_outer.count():
            item = self._list_outer.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rebuild(self):
        self._batch_gen += 1
        gen = self._batch_gen
        self._clear_list()

        cat = self._filter["cat"]
        kw  = self._filter["search"].lower()
        filtered = [
            g for g in self._groups
        if (cat == _ALL_CATEGORY or g.category == cat)
            and (not kw or kw in g.name.lower() or kw in g.desc.lower() or kw in g.id.lower())
        ]
        self._count_lbl.setText(_t("skills.count.total", count=len(filtered)))

        w = QWidget()
        w.setStyleSheet("background:transparent;")
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(10)

        if not filtered:
            wl.addWidget(_lbl(_t("skills.empty.no_match"), 14, C_TEXT3))
            wl.addStretch()
            self._list_outer.addWidget(w)
            return

        PAGE_SIZE = 15
        LOAD_MORE_STEP = 15
        cat_groups: dict = {}
        for g in filtered:
            cat_groups.setdefault(g.category, []).append(g)
        rendered_groups = [0]

        def _build_chunk(start: int, take: int):
            items = []
            end = min(start + take, len(filtered))
            global_idx = 0
            for cname, groups in cat_groups.items():
                cs, ce = global_idx, global_idx + len(groups)
                os_, oe = max(start, cs), min(end, ce)
                if os_ < oe:
                    if os_ == cs:
                        items.append(("header", cname, len(groups)))
                    for g in groups[os_ - cs: oe - cs]:
                        items.append(("group", g))
                    if oe == ce:
                        items.append(("spacing",))
                global_idx = ce
            return items, end

        render_queue, initial_rendered = _build_chunk(0, PAGE_SIZE)
        rendered_groups[0] = initial_rendered
        has_more = rendered_groups[0] < len(filtered)

        def _render_items(items, target_layout, on_done=None):
            ridx = [0]
            BATCH = 6
            def _batch():
                if self._batch_gen != gen:
                    return
                end = min(ridx[0] + BATCH, len(items))
                for i in range(ridx[0], end):
                    it = items[i]
                    if it[0] == "header":
                        _, cname, cnt = it
                        icon = CATEGORY_ICONS.get(cname, "🔧")
                        tr = QHBoxLayout()
                        tr.addWidget(_lbl(f"{icon}  {_cat_text(cname)}", 14, C_TEXT2, bold=True))
                        tr.addWidget(_lbl("  " + _t("skills.count.items_short", count=cnt), 10, C_TEXT3))
                        tr.addStretch()
                        tw = QWidget()
                        tw.setStyleSheet("background:transparent;")
                        tw.setLayout(tr)
                        target_layout.addWidget(tw)
                    elif it[0] == "group":
                        target_layout.addWidget(self._build_row(it[1]))
                    elif it[0] == "spacing":
                        target_layout.addSpacing(10)
                ridx[0] = end
                if ridx[0] < len(items):
                    QTimer.singleShot(10, _batch)
                elif on_done:
                    on_done()
            QTimer.singleShot(0, _batch)

        def _on_first_page_done():
            if has_more:
                more_btn = QPushButton()
                more_btn.setCursor(Qt.PointingHandCursor)
                more_btn.setStyleSheet(
                    f"QPushButton {{ background:rgba(122,179,23,0.10); border:none; border-radius:8px;"
                    f"color:{C_GREEN}; font-size:{_pt(12)}pt; font-weight:600;"
                    f"padding:12px; min-height:{_pt(36)}px; }}"
                    f"QPushButton:hover {{ background:rgba(122,179,23,0.20); }}"
                )

                def _refresh_more():
                    remaining = len(filtered) - rendered_groups[0]
                    nxt = min(LOAD_MORE_STEP, remaining)
                    more_btn.setText(
                        _t("skills.load_more", count=nxt, shown=rendered_groups[0], total=len(filtered))
                    )

                def _load_more():
                    more_btn.setEnabled(False)
                    more_btn.setText(_t("skills.loading"))
                    rest, next_rendered = _build_chunk(rendered_groups[0], LOAD_MORE_STEP)
                    wl.removeWidget(more_btn)
                    more_btn.setParent(None)

                    def _on_chunk_done():
                        rendered_groups[0] = next_rendered
                        if rendered_groups[0] >= len(filtered):
                            more_btn.deleteLater()
                            wl.addStretch()
                        else:
                            _refresh_more()
                            more_btn.setParent(w)
                            wl.addWidget(more_btn)
                            more_btn.setEnabled(True)

                    _render_items(rest, wl, on_done=_on_chunk_done)

                _refresh_more()
                more_btn.clicked.connect(_load_more)
                wl.addWidget(more_btn)
            else:
                wl.addStretch()
            self._list_outer.addWidget(w)

        _render_items(render_queue, wl, on_done=_on_first_page_done)



def build_page() -> QWidget:
    return SkillsPage()
