"""Backup & Restore page — full-system image backup/restore for Seeed Jetson.

Wraps the bundled ``jetson-backup-restore.sh`` (official ``l4t_backup_restore.sh``
plus pre-checks) and the bundled ``setup-workspace.sh`` (one-click download &
assemble of a backup-ready ``Linux_for_Tegra`` tree) in the design system:
PageBase layout, theme factories, DropdownButton / StatusBadge / LoadingSpinner /
StepIndicator, themed dialogs, key-based i18n.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from seeed_jetson_develop.data_update import load_json_data
from seeed_jetson_develop.gui.i18n import get_language, t
from seeed_jetson_develop.core.config import get_backup_state, set_backup_state
from seeed_jetson_develop.gui.theme import (
    C_GREEN,
    C_TEXT,
    C_TEXT2,
    C_TEXT3,
    DropdownButton,
    ShinyProgressBar,
    StatusBadge,
    StepIndicator,
    input_qss,
    make_button as _btn,
    make_card as _card,
    make_label as _lbl,
    make_log_view as _log_view,
    pt as _pt,
    show_error_message as _show_error,
    show_info_message as _show_info,
    show_warning_message as _show_warning,
    ask_question_message as _ask_question,
)
from seeed_jetson_develop.gui.widgets.toast_notification import Toast
from seeed_jetson_develop.gui.widgets.loading_spinner import LoadingSpinner
from seeed_jetson_develop.gui.widgets.page_base import PageBase
from seeed_jetson_develop.resources import resolve_runtime_path

from .thread import (
    BackupRestoreThread,
    PrepareThread,
    discover_boards,
    discover_l4t_dirs,
    is_valid_l4t_dir,
)

_SCRIPT_REL = "modules/backup_restore/scripts/jetson-backup-restore.sh"
_SETUP_SCRIPT_REL = "modules/backup_restore/scripts/setup-workspace.sh"
_DEFAULT_DEVICE = "nvme0n1"
_DEFAULT_VERSION = "36.4.3"

class _AdaptiveStackedWidget(QStackedWidget):
    """Stack whose height follows the *current* page only.

    QStackedLayout's sizeHint/minimumSize are still max(all pages). That leaks
    into QLayout.totalSizeHint() and keeps QScrollArea permanently tall (and
    leaves a vertical gap). Fix: zero-height non-current pages + fixed height
    pinned to the current page's sizeHint.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def sizeHint(self):
        w = self.currentWidget()
        return w.sizeHint() if w is not None else super().sizeHint()

    def minimumSizeHint(self):
        return self.sizeHint()

    def sync_height(self):
        idx = self.currentIndex()
        for i in range(self.count()):
            w = self.widget(i)
            if w is None:
                continue
            # Non-current pages must not inflate QStackedLayout minimumSize.
            w.setMaximumHeight(16777215 if i == idx else 0)
        # 高度 = 内容自适应; 卡片间的间距由固定 spacing 保证统一
        current = self.currentWidget()
        natural = current.sizeHint().height() if current is not None else 0
        self.setFixedHeight(max(0, natural))
        self.updateGeometry()

    def setCurrentIndex(self, index: int):
        super().setCurrentIndex(index)
        self.sync_height()

    def setCurrentWidget(self, widget: QWidget):
        super().setCurrentWidget(widget)
        self.sync_height()


def _pin_height(widget: QWidget) -> QWidget:
    """Keep widget at its sizeHint height — do not absorb leftover layout space."""
    widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
    return widget


def _pack_top(layout: QVBoxLayout) -> QVBoxLayout:
    """Keep children packed to the top; leftover space stays below, not between."""
    layout.setAlignment(Qt.AlignTop)
    return layout


_SECTION_STEPS = ("backup.step.prepare", "backup.step.configure", "backup.step.run")


class BackupRestorePage(PageBase):
    """Page that runs a full-disk backup or restore for the connected Jetson."""

    def __init__(self):
        self._thread: BackupRestoreThread | PrepareThread | None = None
        self._prepare_ctx: tuple[str, str] | None = None  # (version, root) at launch
        super().__init__(
            title=_tt("backup.page.title"),
            subtitle=_tt("backup.page.subtitle"),
        )
        self._build_header_btns()
        self._build_content()

    # ── helpers ──────────────────────────────────────────────────────────
    def _tr(self, key: str, **kwargs) -> str:
        return t(key, lang=get_language(), **kwargs)

    def _field_row(self, label: str, widget: QWidget, hint: str = "") -> QWidget:
        row = QWidget()
        row.setStyleSheet("background:transparent; border:none;")
        lay = QVBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(_pt(6))
        top = QHBoxLayout()
        top.setSpacing(_pt(8))
        top.addWidget(_lbl(label, 12, C_TEXT2, bold=True))
        top.addStretch()
        lay.addLayout(top)
        lay.addWidget(widget)
        if hint:
            lay.addWidget(_lbl(hint, 10, C_TEXT3))
        return row

    @staticmethod
    def _sep() -> QFrame:
        """Subtle horizontal separator for grouping inside cards."""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("border:none; background:rgba(255,255,255,0.06); max-height:1px;")
        return line

    def _section_head(self, text: str) -> QWidget:
        """Small bold section label + trailing hairline — scannable grouping."""
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(_pt(10))
        lay.addWidget(_lbl(text, 11, C_TEXT2, bold=True))
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("border:none; background:rgba(255,255,255,0.06); max-height:1px;")
        line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay.addWidget(line, 1)
        return row

    def _status_check_row(self, label: str, detail: str = "", state: str = "pending") -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(_pt(8))
        dot = QLabel("●")
        dot.setStyleSheet(self._status_dot_style(state))
        lay.addWidget(dot)
        text = _lbl(label, 11, C_TEXT if state == "ok" else C_TEXT2, bold=(state == "ok"))
        lay.addWidget(text)
        if detail:
            lay.addWidget(_lbl(detail, 11, C_TEXT2))
        lay.addStretch()
        row._dot = dot  # type: ignore[attr-defined]
        row._state = state  # type: ignore[attr-defined]
        return row

    def _status_dot_style(self, state: str) -> str:
        if state == "ok":
            color = "#22c55e"
        elif state == "running":
            color = "#facc15"
        else:
            color = C_TEXT3
        return f"color:{color}; font-size:10px;"

    def _update_status_check(self, widget: QWidget, state: str, detail: str = ""):
        widget._state = state  # type: ignore[attr-defined]
        dot = widget._dot  # type: ignore[attr-defined]
        dot.setStyleSheet(self._status_dot_style(state))
        labels = [c for c in widget.findChildren(QLabel) if c is not dot]
        if labels:
            labels[0].setStyleSheet(f"color:{C_TEXT if state == 'ok' else C_TEXT2}; font-size:{_pt(11)}px;")
        if detail and len(labels) >= 2:
            labels[1].setText(detail)

    _PHASE_RUN_DETAIL = {
        0: "backup.prepare.status.downloading",
        1: "backup.prepare.status.assembling",
        2: "backup.prepare.status.preparing",
        3: "backup.prepare.status.ready",
    }
    _PHASE_DONE_DETAIL = {
        0: "backup.prepare.status.done",
        1: "backup.prepare.status.done",
        2: "backup.prepare.status.ready",
        3: "backup.prepare.status.ready",
    }

    def _is_env_ready(self) -> bool:
        return bool(self._l4t_dir) and is_valid_l4t_dir(self._l4t_dir) and (Path(self._l4t_dir) / "rootfs").is_dir()

    def _set_phase(self, idx: int):
        for i, row in self._phase_rows.items():
            if i < idx:
                self._update_status_check(row, "ok", _tt(self._PHASE_DONE_DETAIL[i]))
            elif i == idx:
                if idx == 3:
                    self._update_status_check(row, "ok", _tt(self._PHASE_DONE_DETAIL[i]))
                else:
                    self._update_status_check(row, "running", _tt(self._PHASE_RUN_DETAIL[idx]))
            else:
                self._update_status_check(row, "pending", _tt("backup.prepare.status.pending"))
        self._phase_state = idx
        ready = (idx == 3) or self._is_env_ready()
        self._status_summary.set_status("ok" if ready else "default",
                                        _tt("backup.prepare.status.ready" if ready else "backup.prepare.status.pending"))
        self._next0.setEnabled(ready)

    def _on_phase(self, name: str):
        idx = {"download": 0, "assemble": 1, "rootfs": 2, "done": 3}.get(name)
        if idx is not None:
            self._set_phase(idx)

    # ── build ──────────────────────────────────────────────────────────
    def _build_header_btns(self):
        self._status_badge = StatusBadge(_tt("backup.status.idle"), "default")
        self._status_badge.setVisible(False)
        self.add_header_widget(self._status_badge)

    def _build_content(self):
        content = self.get_content_layout()

        # ── 步骤指示卡: 准备 → 配置 → 执行 ─────────────────────────────
        wizard_card = _pin_height(_card(12))
        wizard_lay = QVBoxLayout(wizard_card)
        wizard_lay.setContentsMargins(0, 0, 0, 0)
        self._step_indicator = StepIndicator([_tt(k) for k in _SECTION_STEPS])
        wizard_lay.addWidget(self._step_indicator)
        content.addWidget(wizard_card)

        # ── 内容栈: 一次只显示一步 ─────────────────────────────────────
        self._stack = _AdaptiveStackedWidget()
        self._stack.setStyleSheet("background:transparent; border:none;")

        # ══ step0: 准备 ═════════════════════════════════════════════════
        step0 = _pin_height(QWidget())
        s0_lay = _pack_top(QVBoxLayout(step0))
        s0_lay.setSpacing(_pt(12))

        # 主内容：左侧配置卡 + 右侧状态卡
        main_row = QWidget()
        main_lay = QHBoxLayout(main_row)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(_pt(12))

        # ── 左侧配置卡 ────────────────────────────────────────────────────
        left_card = _card(12)
        left_lay = QVBoxLayout(left_card)
        left_lay.setContentsMargins(_pt(22), _pt(18), _pt(22), _pt(18))
        left_lay.setSpacing(_pt(14))

        # 1. 基本配置
        left_lay.addWidget(self._section_head("1. " + _tt("backup.prepare.section.basic")))
        basic_row = QWidget()
        basic_lay = QHBoxLayout(basic_row)
        basic_lay.setContentsMargins(0, 0, 0, 0)
        basic_lay.setSpacing(_pt(10))

        # version 子卡
        version_sub = _card(8)
        version_lay = QVBoxLayout(version_sub)
        version_lay.setContentsMargins(_pt(14), _pt(12), _pt(14), _pt(12))
        version_lay.setSpacing(_pt(8))
        version_header = QHBoxLayout()
        version_header.setContentsMargins(0, 0, 0, 0)
        version_header.setSpacing(_pt(8))
        version_icon = QLabel("⚙")
        version_icon.setStyleSheet("color:#4ade80; font-size:18px;")
        version_header.addWidget(version_icon)
        version_header.addWidget(_lbl(_tt("backup.prepare.version"), 12, C_TEXT, bold=True))
        version_header.addStretch()
        version_lay.addLayout(version_header)
        self._version_combo = DropdownButton(max_popup_height=_pt(220))
        self._version_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        version_lay.addWidget(self._version_combo)
        version_lay.addWidget(_lbl(_tt("backup.prepare.version_hint"), 10, C_TEXT3, wrap=True))
        basic_lay.addWidget(version_sub, 1)

        # workspace 子卡
        workspace_sub = _card(8)
        workspace_lay = QVBoxLayout(workspace_sub)
        workspace_lay.setContentsMargins(_pt(14), _pt(12), _pt(14), _pt(12))
        workspace_lay.setSpacing(_pt(8))
        workspace_header = QHBoxLayout()
        workspace_header.setContentsMargins(0, 0, 0, 0)
        workspace_header.setSpacing(_pt(8))
        folder_icon = QLabel("▥")
        folder_icon.setStyleSheet(f"color:{C_TEXT}; font-size:18px;")
        workspace_header.addWidget(folder_icon)
        workspace_header.addWidget(_lbl(_tt("backup.prepare.workspace"), 12, C_TEXT, bold=True))
        workspace_header.addStretch()
        workspace_lay.addLayout(workspace_header)
        self._workspace_path = str(Path.home() / "jetson_bsp")
        self._workspace_btn = _btn(
            f"{self._workspace_path}", small=True)
        self._workspace_btn.clicked.connect(self._browse_workspace)
        workspace_lay.addWidget(self._workspace_btn)
        workspace_lay.addWidget(_lbl(_tt("backup.prepare.disk_hint"), 10, C_TEXT3, wrap=True))
        basic_lay.addWidget(workspace_sub, 1)

        left_lay.addWidget(basic_row)

        # 2. 环境检测
        left_lay.addWidget(self._section_head(_tt("backup.prepare.section.env")))
        env_card = _card(8)
        env_lay = QVBoxLayout(env_card)
        env_lay.setContentsMargins(_pt(14), _pt(12), _pt(14), _pt(12))
        env_lay.setSpacing(_pt(8))
        env_header = QHBoxLayout()
        env_header.setContentsMargins(0, 0, 0, 0)
        env_header.setSpacing(_pt(8))
        env_icon = QLabel("◼")
        env_icon.setStyleSheet("color:#4ade80; font-size:18px;")
        env_header.addWidget(env_icon)
        env_header.addWidget(_lbl(_tt("backup.prepare.section.env"), 12, C_TEXT, bold=True))
        env_header.addStretch()
        self._env_badge = StatusBadge(_tt("backup.env.missing"), "error")
        env_header.addWidget(self._env_badge)
        env_lay.addLayout(env_header)

        self._l4t_dir = ""
        self._env_path_lbl = _lbl(_tt("backup.env.missing"), 11, C_TEXT2, wrap=True)
        env_lay.addWidget(self._env_path_lbl)

        # 准备/停止/检测 操作行
        env_action_row = QHBoxLayout()
        env_action_row.setSpacing(_pt(8))
        self._prepare_btn = _btn(_tt("backup.prepare.start"), primary=True)
        self._prepare_btn.setMinimumWidth(_pt(110))
        self._prepare_btn.clicked.connect(self._start_prepare)
        self._stop_prepare_btn = _btn(_tt("backup.prepare.stop"))
        self._stop_prepare_btn.setMinimumWidth(_pt(96))
        self._stop_prepare_btn.setEnabled(False)
        self._stop_prepare_btn.clicked.connect(self._stop_prepare)
        self._prepare_spinner = LoadingSpinner(size=_pt(20))
        self._prepare_spinner.hide()
        env_action_row.addWidget(self._prepare_btn)
        env_action_row.addWidget(self._stop_prepare_btn)
        env_action_row.addWidget(self._prepare_spinner)
        env_action_row.addStretch()
        detect_btn = _btn(_tt("backup.env.detect"), small=True)
        detect_btn.setMinimumWidth(_pt(80))
        detect_btn.clicked.connect(self._auto_detect_l4t)
        env_action_row.addWidget(detect_btn)
        env_lay.addLayout(env_action_row)

        # 进度 + 下载
        self._progress_bar = ShinyProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(_pt(6))
        self._progress_bar.setMinimumWidth(_pt(120))
        self._progress_bar.hide()
        env_lay.addWidget(self._progress_bar)

        self._progress_badge = StatusBadge("", status="info")
        self._progress_badge.hide()
        env_lay.addWidget(self._progress_badge)

        left_lay.addWidget(env_card)

        # 3. sudo
        left_lay.addWidget(self._section_head(_tt("backup.prepare.section.sudo")))
        sudo_card = _card(8)
        sudo_lay = QVBoxLayout(sudo_card)
        sudo_lay.setContentsMargins(_pt(14), _pt(12), _pt(14), _pt(12))
        sudo_lay.setSpacing(_pt(8))
        sudo_header = QHBoxLayout()
        sudo_header.setContentsMargins(0, 0, 0, 0)
        sudo_header.setSpacing(_pt(8))
        lock_icon = QLabel("▣")
        lock_icon.setStyleSheet(f"color:{C_TEXT}; font-size:18px;")
        sudo_header.addWidget(lock_icon)
        sudo_header.addWidget(_lbl(_tt("backup.prepare.sudo"), 12, C_TEXT, bold=True))
        sudo_header.addStretch()
        sudo_lay.addLayout(sudo_header)
        self._sudo_edit = QLineEdit()
        self._sudo_edit.setStyleSheet(input_qss())
        self._sudo_edit.setEchoMode(QLineEdit.Password)
        self._sudo_edit.setPlaceholderText(_tt("backup.prepare.sudo_placeholder"))
        sudo_lay.addWidget(self._sudo_edit)
        sudo_lay.addWidget(_lbl(_tt("backup.prepare.sudo_hint"), 10, C_TEXT3, wrap=True))
        left_lay.addWidget(sudo_card)

        left_lay.addStretch()

        # 底部提示
        left_lay.addWidget(_lbl(_tt("backup.prepare.action_hint"), 10, C_TEXT3, wrap=True))

        main_lay.addWidget(left_card, 3)

        # ── 右侧状态卡 ────────────────────────────────────────────────────
        right_card = _card(12)
        right_lay = QVBoxLayout(right_card)
        right_lay.setContentsMargins(_pt(22), _pt(18), _pt(22), _pt(18))
        right_lay.setSpacing(_pt(12))

        right_header = QHBoxLayout()
        right_header.setContentsMargins(0, 0, 0, 0)
        right_header.setSpacing(_pt(8))
        check_icon = QLabel("✓")
        check_icon.setStyleSheet("color:#4ade80; font-size:18px;")
        right_header.addWidget(check_icon)
        right_header.addWidget(_lbl(_tt("backup.prepare.status.title"), 14, C_TEXT, bold=True))
        right_header.addStretch()
        right_lay.addLayout(right_header)

        self._is_preparing = False
        self._downloads_done = False
        self._phase_state = -1

        # 环境流水线（① 下载 → ② 装配 → ③ rootfs → ④ 就绪）
        self._phase_rows: dict[int, QWidget] = {}
        _idxs = ("①", "②", "③", "④")
        for i, key in enumerate(("download", "assemble", "rootfs", "done")):
            label = f"{_idxs[i]} {_tt(f'backup.prepare.phase.{key}')}"
            row = self._status_check_row(label)
            right_lay.addWidget(row)
            self._phase_rows[i] = row
            if i == 0:
                self._download_panel = QWidget()
        self._download_layout = QVBoxLayout(self._download_panel)
        self._download_layout.setContentsMargins(_pt(16), 0, 0, 0)
        self._download_layout.setSpacing(_pt(4))
        self._download_items: dict[str, tuple[StatusBadge, QLabel]] = {}
        right_lay.addWidget(self._download_panel)

        right_lay.addStretch()

        self._status_summary = StatusBadge(_tt("backup.prepare.status.pending"), "default")
        right_lay.addWidget(self._status_summary)

        main_lay.addWidget(right_card, 1)

        s0_lay.addWidget(main_row)

        # 导航
        s0_nav = QHBoxLayout()
        s0_nav.setContentsMargins(0, _pt(8), 0, 0)
        s0_nav.addStretch()
        self._next0 = _btn(_tt("backup.nav.next"), primary=True)
        self._next0.clicked.connect(self._go_next)
        s0_nav.addWidget(self._next0)
        s0_lay.addLayout(s0_nav)

        self._stack.addWidget(step0)

        # ═ step1: 配置 ══════════════════════════════════════════════════
        step1 = _pin_height(QWidget())
        s1_lay = _pack_top(QVBoxLayout(step1))
        s1_lay.setSpacing(_pt(12))
        s1_card = _card(12)
        s1_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        s1_card_lay = QVBoxLayout(s1_card)
        s1_card_lay.setContentsMargins(_pt(22), _pt(18), _pt(22), _pt(18))
        s1_card_lay.setSpacing(_pt(12))

        s1_card_lay.addWidget(_lbl(_tt("backup.step.configure"), 14, C_TEXT, bold=True))
        s1_card_lay.addWidget(_lbl(
            _tt("backup.task.subtitle"), 12, C_TEXT2, wrap=True))

        self._board_combo = DropdownButton(max_popup_height=_pt(220))
        self._board_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        refresh_btn = _btn(_tt("backup.task.board_refresh"), small=True)
        refresh_btn.clicked.connect(self._refresh_boards)

        board_row = QHBoxLayout()
        board_row.setSpacing(_pt(8))
        board_row.addWidget(self._board_combo, 1)
        board_row.addWidget(refresh_btn)
        board_widget = QWidget()
        board_widget.setLayout(board_row)
        s1_card_lay.addWidget(self._field_row(
            _tt("backup.task.board"), board_widget, _tt("backup.task.board_hint")))

        self._device_edit = QLineEdit(_DEFAULT_DEVICE)
        self._device_edit.setStyleSheet(input_qss())
        s1_card_lay.addWidget(self._field_row(
            _tt("backup.task.device"), self._device_edit,
            _tt("backup.task.device_hint")))

        self._wait_apx_cb = QCheckBox(_tt("backup.task.wait_apx"))
        self._wait_apx_cb.setChecked(True)
        s1_card_lay.addWidget(self._wait_apx_cb)

        s1_lay.addWidget(s1_card)

        # nav footer (卡外, 与其它步骤一致)
        s1_nav = QHBoxLayout()
        s1_nav.setContentsMargins(0, _pt(8), 0, 0)
        prev1 = _btn(_tt("backup.nav.prev"))
        prev1.clicked.connect(self._go_prev)
        s1_nav.addWidget(prev1)
        s1_nav.addStretch()
        next1 = _btn(_tt("backup.nav.next"), primary=True)
        next1.clicked.connect(self._go_next)
        s1_nav.addWidget(next1)
        s1_lay.addLayout(s1_nav)
        self._stack.addWidget(step1)

        # ══ step2: 执行 ══════════════════════════════════════════════════
        step2 = _pin_height(QWidget())
        s2_lay = _pack_top(QVBoxLayout(step2))
        s2_lay.setSpacing(_pt(12))
        s2_card = _card(12)
        s2_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        s2_card_lay = QVBoxLayout(s2_card)
        s2_card_lay.setContentsMargins(_pt(22), _pt(18), _pt(22), _pt(18))
        s2_card_lay.setSpacing(_pt(12))

        s2_card_lay.addWidget(_lbl(_tt("backup.step.run"), 14, C_TEXT, bold=True))
        s2_card_lay.addWidget(_lbl(
            _tt("backup.run.subtitle"), 12, C_TEXT2, wrap=True))

        self._backup_btn = _btn(_tt("backup.run.backup"), primary=True)
        self._backup_btn.clicked.connect(lambda: self._start("backup"))
        self._restore_btn = _btn(_tt("backup.run.restore"), danger=True)
        self._restore_btn.clicked.connect(lambda: self._start("restore"))
        self._stop_btn = _btn(_tt("backup.run.stop"))
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(_pt(10))
        btn_row.addWidget(self._backup_btn)
        btn_row.addWidget(self._restore_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        s2_card_lay.addLayout(btn_row)

        # 恢复源: 默认 images 或历史备份集子目录
        source_row = QHBoxLayout()
        source_row.setSpacing(_pt(8))
        source_row.addWidget(_lbl(_tt("backup.task.backup_set"), 11, C_TEXT2, bold=True))
        self._backup_source_combo = DropdownButton(max_popup_height=_pt(220))
        self._backup_source_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        source_row.addWidget(self._backup_source_combo, 1)
        s2_card_lay.addLayout(source_row)

        # 容量要求提示: 恢复目标盘必须 ≥ 备份源盘容量
        self._capacity_hint_lbl = _lbl("", 10, C_TEXT3, wrap=True)
        s2_card_lay.addWidget(self._capacity_hint_lbl)

        # 上次任务结果(含产物路径)直接显示在卡片内
        self._last_result_lbl = _lbl("", 11, C_GREEN)
        self._last_result_lbl.setWordWrap(True)
        self._last_result_lbl.hide()
        s2_card_lay.addWidget(self._last_result_lbl)

        s2_lay.addWidget(s2_card)

        # nav footer (卡外, 与其它步骤一致)
        s2_nav = QHBoxLayout()
        s2_nav.setContentsMargins(0, _pt(8), 0, 0)
        prev2 = _btn(_tt("backup.nav.prev"))
        prev2.clicked.connect(self._go_prev)
        s2_nav.addWidget(prev2)
        s2_nav.addStretch()
        s2_lay.addLayout(s2_nav)
        self._stack.addWidget(step2)

        content.addWidget(self._stack)

        self._stack.sync_height()

        # ── 日志: 常驻栈外, 准备与执行两阶段都需 streaming ─────────────
        self._log_view = _log_view(read_only=True, min_height=200)
        self._log_view.setVisible(False)
        self._log_toggle = _btn(_tt("backup.prepare.show_details"), small=True)
        self._log_toggle.clicked.connect(self._toggle_log_view)
        content.addWidget(self._log_toggle)
        content.addWidget(self._log_view)
        # 底部 stretch 吸收多余空间: 卡片全部顶对齐, 间距恒定不漂移
        content.addStretch()

        # 初始化状态
        self._populate_versions()

        # 恢复上次记住的状态: 工作区 / L4T 目录 / sudo 密码
        remembered = get_backup_state()
        workspace = (remembered.get("workspace") or "").strip()
        if workspace and Path(workspace).is_dir():
            self._workspace_path = workspace
            self._workspace_btn.setText(
                f"{_tt('backup.prepare.workspace')}: {workspace}")
        l4t = (remembered.get("l4t_dir") or "").strip()
        ws = (self._workspace_path or "").strip().rstrip("/")
        # 记住的树必须属于当前工作区, 否则重新探测 (避免混用本机其它旧树)
        if l4t and is_valid_l4t_dir(l4t) and (not ws or l4t.startswith(ws + "/")):
            self._set_l4t_dir(l4t)
        else:
            self._auto_detect_l4t()
        sudo_pass = (remembered.get("sudo_pass") or "")
        if sudo_pass:
            self._sudo_edit.setText(sudo_pass)
        # 恢复上次任务结果: 按当前语言重新翻译显示 (兼容旧的纯文本存档)
        last_result_mode = (remembered.get("last_result_mode") or "").strip()
        last_result_path = (remembered.get("last_result_path") or "").strip()
        if last_result_mode in ("backup", "restore"):
            if last_result_mode == "backup":
                text = _tt("backup.run.backup_done", path=last_result_path or "—")
            else:
                text = _tt("backup.run.restore_done")
            self._last_result_lbl.setText(
                "✓ " + _tt("backup.run.last_result") + text)
            self._last_result_lbl.show()
        else:
            legacy = (remembered.get("last_result") or "").strip()
            if legacy:
                self._last_result_lbl.setText(
                    "✓ " + _tt("backup.run.last_result") + legacy)
                self._last_result_lbl.show()
        # 恢复上次选中的板型 (combo 已由 _refresh_boards 填充)
        rem_board = (remembered.get("board") or "").strip()
        if rem_board and rem_board in self._board_combo._items:
            self._board_combo.setCurrentText(rem_board)
        self._refresh_backup_sets()
        self._set_phase(3 if self._is_env_ready() else -1)

    # ── 版本列表 ─────────────────────────────────────────────────────────
    @staticmethod
    def _load_versions() -> list[str]:
        """L4T versions >= 35.0.0 from the bundled software list, descending."""
        data = load_json_data("l4t_data.json") or []
        versions: set[str] = set()
        for item in data:
            raw = str(item.get("l4t", "")) if isinstance(item, dict) else ""
            m = re.search(r"(\d+\.\d+\.\d+)", raw)
            if m and tuple(int(x) for x in m.group(1).split(".")) >= (35, 0, 0):
                versions.add(m.group(1))
        return sorted(
            versions,
            key=lambda s: tuple(int(x) for x in s.split(".")),
            reverse=True,
        )

    def _populate_versions(self):
        versions = self._load_versions()
        self._version_combo.clear()
        self._version_combo.addItems(versions or [""])
        if _DEFAULT_VERSION in versions:
            self._version_combo.setCurrentText(_DEFAULT_VERSION)

    def _browse_workspace(self):
        chosen = QFileDialog.getExistingDirectory(
            self, _tt("backup.prepare.workspace"), self._workspace_path or str(Path.home()))
        if chosen:
            self._workspace_path = chosen
            self._workspace_btn.setText(
                f"{_tt('backup.prepare.workspace')}: {chosen}")
            set_backup_state(workspace=chosen)
            # 工作区变了 => 重新定位该工作区下的装配树
            self._auto_detect_l4t()

    # ── 环境探测 ─────────────────────────────────────────────────────────
    def _set_l4t_dir(self, text: str):
        """记录已选/探测到的 L4T 树路径并同步 badge、路径标签与状态面板。"""
        text = text.strip()
        self._l4t_dir = text
        if text:
            set_backup_state(l4t_dir=text)
        if not text:
            self._env_badge.set_status("error", _tt("backup.env.missing"))
            self._env_path_lbl.setText(_tt("backup.env.missing"))
        elif is_valid_l4t_dir(text):
            self._env_badge.set_status("ok", _tt("backup.env.found"))
            self._env_path_lbl.setText(text)
        else:
            self._env_badge.set_status("warn", _tt("backup.env.invalid"))
            self._env_path_lbl.setText(text)
        if self._is_preparing:
            self._set_phase(self._phase_state)
        else:
            self._set_phase(3 if self._is_env_ready() else -1)
        self._refresh_boards()

    def _auto_detect_l4t(self):
        # 优先: 当前工作区下装配好的树 <工作区>/bsp/<版本>/Linux_for_Tegra
        # (全盘扫描会命中本机其它旧树, 与所选工作区不一致)
        base = (self._workspace_path or "").strip()
        if base:
            bsp_dir = Path(base) / "bsp"
            try:
                candidates = sorted(
                    (p for p in bsp_dir.glob("*/Linux_for_Tegra") if is_valid_l4t_dir(p)),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            except OSError:
                candidates = []
            if candidates:
                self._set_l4t_dir(str(candidates[0]))
                return
        # 回退: 全盘探测
        dirs = discover_l4t_dirs()
        if dirs:
            self._set_l4t_dir(dirs[0])
        else:
            # 客户机通常没有现成树：明确指向一键准备区，不静默失败
            self._set_l4t_dir("")
            self._env_badge.set_status("warn", _tt("backup.env.not_found_msg"))

    def _browse_l4t(self):
        chosen = QFileDialog.getExistingDirectory(
            self, _tt("backup.env.use_existing"), self._l4t_dir or str(Path.home()))
        if chosen:
            self._set_l4t_dir(chosen)

    def _refresh_boards(self):
        boards = discover_boards(self._l4t_dir) if is_valid_l4t_dir(self._l4t_dir) else []
        current = self._board_combo.currentText()
        self._board_combo.clear()
        self._board_combo.addItems(boards or [""])
        if current in boards:
            self._board_combo.setCurrentText(current)

    # ── 向导导航 ────────────────────────────────────────────────────────
    def _goto_step(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self._step_indicator.set_current(idx)

    def _go_prev(self):
        cur = self._stack.currentIndex()
        if cur > 0:
            self._goto_step(cur - 1)

    def _go_next(self):
        cur = self._stack.currentIndex()
        if cur == 0:
            if not is_valid_l4t_dir(self._l4t_dir):
                _show_warning(self, _tt("backup.env.invalid_title"),
                              _tt("backup.env.invalid_msg"))
                return
        elif cur == 1:
            if not self._board_combo.currentText().strip():
                _show_warning(self, _tt("backup.task.board_required_title"),
                              _tt("backup.task.board_required_msg"))
                return
        self._goto_step(cur + 1)

    # ── 一键准备 ─────────────────────────────────────────────────────────
    def _setup_script_path(self) -> str | None:
        path = resolve_runtime_path(_SETUP_SCRIPT_REL)
        if path is not None and path.is_file():
            return str(path)
        return None

    def _start_prepare(self):
        if self._thread is not None and self._thread.isRunning():
            _show_warning(self, _tt("backup.run.busy_title"),
                          _tt("backup.run.busy_msg"))
            return

        script = self._setup_script_path()
        if script is None:
            _show_error(self, _tt("backup.prepare.script_missing_title"),
                        _tt("backup.prepare.script_missing_msg"))
            return

        import shutil
        missing = [name for name in ("curl", "git") if shutil.which(name) is None]
        if missing:
            _show_error(self, _tt("backup.prepare.tool_missing_title"),
                        _tt("backup.prepare.tool_missing_msg",
                            tools=", ".join(missing)))
            return

        version = self._version_combo.currentText().strip()
        if not version:
            _show_warning(self, _tt("backup.prepare.version_required_title"),
                          _tt("backup.prepare.version_required_msg"))
            return

        root = self._workspace_path
        if not root:
            _show_warning(self, _tt("backup.prepare.workspace_required_title"),
                          _tt("backup.prepare.workspace_required_msg"))
            return

        sudo_pass = self._sudo_edit.text().strip()
        set_backup_state(workspace=root, sudo_pass=sudo_pass)

        self._log_view.clear()
        self._prepare_ctx = (version, root)
        self._set_prepare_running(True)

        self._thread = PrepareThread(
            script=script,
            version=version,
            root=root,
            sudo_pass=self._sudo_edit.text().strip(),
            minimal=True,
        )
        self._thread.log.connect(self._append_log)
        self._thread.progress.connect(self._on_prepare_progress)
        self._thread.download_list.connect(self._on_download_list)
        self._thread.download_start.connect(self._on_download_start)
        self._thread.download_done.connect(self._on_download_done)
        self._thread.phase.connect(self._on_phase)
        self._thread.download_progress.connect(self._on_download_progress)
        self._thread.done.connect(lambda ok, msg: self._on_prepare_done(ok, msg))
        self._set_phase(0)
        self._thread.start()

    def _stop_prepare(self):
        if self._thread is not None and self._thread.isRunning():
            self._thread.cancel()
            self._append_log("── prepare cancel requested ──")

    def _on_prepare_progress(self, cur: int, total: int, msg: str):
        if total > 0:
            self._progress_bar.setValue(int(cur * 100 / total))
        self._progress_badge.setText(f"[{cur}/{total}] {msg}")
        self._progress_badge.set_status("info")
        self._progress_bar.show()
        self._progress_badge.show()

    def _on_download_list(self, items: list[str]):
        # 清空旧项
        while self._download_layout.count():
            w = self._download_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._download_items.clear()
        self._downloads_done = False
        if not items:
            self._download_panel.hide()
            return
        self._download_panel.show()
        for name in items:
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(_pt(8))
            name_label = _lbl(name, 11, C_TEXT, wrap=True)
            name_label.setMaximumWidth(_pt(180))
            badge = StatusBadge(_tt("backup.prepare.pending"))
            badge.set_status("default")
            progress = _lbl("", 10, C_TEXT3)
            lay.addWidget(name_label)
            lay.addWidget(progress)
            lay.addStretch()
            lay.addWidget(badge)
            self._download_layout.addWidget(row)
            self._download_items[name] = (badge, progress)

    def _on_download_start(self, name: str):
        item = self._download_items.get(name)
        if item is not None:
            badge, _ = item
            badge.set_status("info", _tt("backup.prepare.downloading"))

    def _on_download_progress(self, name: str, percent: str):
        item = self._download_items.get(name)
        if item is not None:
            badge, progress = item
            progress.setText(f"{percent}%")

    def _on_download_done(self, name: str):
        item = self._download_items.get(name)
        if item is not None:
            badge, progress = item
            badge.set_status("ok", _tt("backup.prepare.done"))
            progress.setText("100%")
        # 全部完成?
        if all(badge._status == "ok" for badge, _ in self._download_items.values()):
            self._downloads_done = True

    def _on_prepare_done(self, ok: bool, msg: str):
        self._set_prepare_running(False)
        if ok:
            ctx = self._prepare_ctx
            if ctx is None:
                self._thread = None
                return
            version, root = ctx
            l4t = Path(root) / "bsp" / f"R{version}" / "Linux_for_Tegra"
            self._set_l4t_dir(str(l4t))
            self._set_phase(3)
            self._refresh_boards()
            self._status_badge.setVisible(True)
            self._status_badge.set_status("ok", _tt("backup.status.ok"))
        else:
            self._status_badge.setVisible(True)
            self._status_badge.set_status("error", _tt("backup.status.error"))
            Toast.error(self, _tt("backup.prepare.failed_toast"))
            if msg != "Cancelled":
                self._append_log(f"── prepare failed: {msg} ──")
            self._set_phase(max(self._phase_state, 0) if self._phase_state >= 0 else -1)
            if self._phase_state in self._phase_rows:
                self._update_status_check(self._phase_rows[self._phase_state], "error",
                                          _tt("backup.prepare.status.failed"))
        self._prepare_ctx = None
        self._thread = None

    def _set_prepare_running(self, running: bool):
        self._is_preparing = running
        if not running:
            self._downloads_done = False
        self._prepare_btn.setEnabled(not running)
        self._stop_prepare_btn.setEnabled(running)
        self._prepare_spinner.setVisible(running)
        if not running:
            self._progress_bar.hide()
            self._progress_badge.hide()
            if self._is_env_ready():
                self._set_phase(3)
            elif self._phase_state >= 0:
                self._set_phase(self._phase_state)
            else:
                self._set_phase(-1)
        else:
            self._next0.setEnabled(False)
        # 准备进行中, 备份/恢复不可并行 (依赖准备产物)
        self._backup_btn.setEnabled(not running)
        self._restore_btn.setEnabled(not running)
        self._stop_btn.setEnabled(False)
        if running:
            self._status_badge.setVisible(True)
            self._status_badge.set_status("info", _tt("backup.status.running"))
        else:
            self._status_badge.setVisible(False)

    # ── 执行 ─────────────────────────────────────────────────────────────
    def _script_path(self) -> str | None:
        path = resolve_runtime_path(_SCRIPT_REL)
        if path is not None and path.is_file():
            return str(path)
        return None

    def _start(self, mode: str):
        if self._thread is not None and self._thread.isRunning():
            _show_warning(self, _tt("backup.run.busy_title"),
                          _tt("backup.run.busy_msg"))
            return

        script = self._script_path()
        if script is None:
            _show_error(self, _tt("backup.env.missing_script_title"),
                        _tt("backup.env.missing_script_msg"))
            return

        l4t_dir = self._l4t_dir
        if not l4t_dir or not is_valid_l4t_dir(l4t_dir):
            _show_warning(self, _tt("backup.env.invalid_title"),
                          _tt("backup.env.invalid_msg"))
            return

        board = self._board_combo.currentText().strip()
        if not board:
            _show_warning(self, _tt("backup.task.board_required_title"),
                          _tt("backup.task.board_required_msg"))
            return

        device = self._device_edit.text().strip() or _DEFAULT_DEVICE

        # 勾选了"等待 Recovery"时, 先立即探测设备是否已在 Recovery,
        # 不在则直接提醒, 不启动流程 (避免空跑/60s 后才报超时)
        if self._wait_apx_cb.isChecked() and not self._device_in_recovery():
            _show_warning(
                self,
                _tt("backup.run.not_recovery_title"),
                _tt("backup.run.not_recovery_msg"),
            )
            return

        if mode == "restore":
            answer = _ask_question(
                self,
                _tt("backup.restore.confirm_title"),
                _tt("backup.restore.confirm_msg", board=board, device=device),
                buttons=QMessageBox.Yes | QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        sudo_pass = self._sudo_edit.text().strip()
        set_backup_state(sudo_pass=sudo_pass, l4t_dir=l4t_dir, board=board)

        self._log_view.clear()
        self._set_running(True)

        source_dir = ""
        if mode == "restore":
            sel = self._backup_source_combo.currentText().strip()
            src = str(self._backup_source_combo._data.get(sel, "") or "")
            # 第一项就是 images 本身, 直接默认恢复; 仅历史子目录才传 --source
            if src and src != (self._images_dir() or ""):
                source_dir = src

        self._thread = BackupRestoreThread(
            script=script,
            mode=mode,
            board=board,
            l4t_dir=l4t_dir,
            device=device,
            wait_apx=self._wait_apx_cb.isChecked(),
            sudo_pass=sudo_pass,
            source_dir=source_dir,
        )
        self._thread.log.connect(self._append_log)
        self._thread.done.connect(lambda ok, msg: self._on_finished(mode, ok, msg))
        self._thread.start()

    def _stop(self):
        if self._thread is not None and self._thread.isRunning():
            self._thread.cancel()
            self._append_log("── cancel requested ──")

    def _set_running(self, running: bool):
        self._backup_btn.setEnabled(not running)
        self._restore_btn.setEnabled(not running)
        # 备份/恢复进行中, 一键准备不可并行
        self._prepare_btn.setEnabled(not running)
        self._stop_prepare_btn.setEnabled(False)
        self._stop_btn.setEnabled(running)
        if running:
            self._status_badge.setVisible(True)
            self._status_badge.set_status("info", _tt("backup.status.running"))
        else:
            self._status_badge.setVisible(False)

    def _append_log(self, line: str):
        self._log_view.append(line)

    def _toggle_log_view(self):
        self._log_view.setVisible(not self._log_view.isVisible())
        self._log_toggle.setText(
            _tt("backup.prepare.hide_details") if self._log_view.isVisible() else _tt("backup.prepare.show_details")
        )

    def _on_finished(self, mode: str, ok: bool, msg: str):
        self._set_running(False)
        # 任务结束后立刻刷新备份集下拉: 备份刚落盘时 combo 还是旧列表
        self._refresh_backup_sets()
        if ok:
            self._status_badge.setVisible(True)
            self._status_badge.set_status("ok", _tt("backup.status.ok"))
            if mode == "backup":
                text = _tt("backup.run.backup_done", path=self._images_dir() or "—")
            else:
                text = _tt("backup.run.restore_done")
            self._last_result_lbl.setText("✓ " + text)
            self._last_result_lbl.show()
            # 只存 key+参数, 显示时按当前语言重新翻译, 避免残留旧语言文本
            set_backup_state(last_result_mode=mode,
                             last_result_path=self._images_dir() or "")
            self._append_log("")
            self._append_log("  ── " + _tt("backup.status.ok") + " ──")
            self._append_log(" " + text)
            _show_info(self, _tt("backup.run.success_title"), text)
        else:
            self._status_badge.setVisible(True)
            self._status_badge.set_status("error", _tt("backup.status.error"))
            if msg != "Cancelled":
                _show_error(self, _tt("backup.run.failed_title"),
                            _tt("backup.run.failed_msg", detail=msg))
        self._thread = None

    def _images_dir(self) -> str | None:
        if not self._l4t_dir:
            return None
        d = Path(self._l4t_dir) / "tools/backup_restore/images"
        return str(d) if d.is_dir() else None

    def _device_in_recovery(self) -> bool:
        """快速探测设备是否已处于 Recovery (APX) 模式。探测失败时不拦流程。"""
        apx_ids = ("7323", "7423", "7523", "7623", "7023")
        try:
            out = subprocess.check_output(
                ["lsusb"], text=True, timeout=3, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            return True
        return any(f"0955:{apx}" in out for apx in apx_ids)

    def _required_capacity_sectors(self, img_dir: str | None) -> int:
        """从 nvpartitionmap.txt 计算恢复所需的最小扇区数 (布局最大终点)。"""
        if not img_dir:
            return 0
        map_file = Path(img_dir) / "nvpartitionmap.txt"
        try:
            lines = [ln for ln in map_file.read_text(encoding="utf-8").splitlines()
                     if ln.strip() and not ln.startswith("#")]
        except OSError:
            return 0
        need = 0
        for ln in lines:
            parts = ln.split(",")
            if len(parts) < 5:
                continue
            try:
                start, count = int(parts[2]), int(parts[3])
            except ValueError:
                continue
            end = start + count
            if end > need:
                need = end
        return need

    def _refresh_backup_sets(self):
        """备份集列表: 第一项为当前 images (默认选中), 其后为历史备份集子目录。

        条目显示 板型 · 备份时间 · 大小 (取自 nvpartitionmap.txt), 完整路径存 data。
        """
        self._backup_source_combo.clear()
        img = self._images_dir()
        if not img:
            return
        boards = tuple(self._board_combo._items or ())
        # images 根有 map 才作为「最新备份」列出; 已归档后根是空的, 只列归档集
        if (Path(img) / "nvpartitionmap.txt").is_file():
            self._backup_source_combo.addItem(self._backup_set_label(str(img), boards), data=str(img))
        try:
            subs = sorted(
                (p for p in Path(img).iterdir()
                 if p.is_dir() and (p / "nvpartitionmap.txt").is_file()),
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
        except OSError:
            subs = []
        for s in subs:
            self._backup_source_combo.addItem(self._backup_set_label(str(s), boards), data=str(s))

        # 更新容量要求提示 (从备份清单计算需要的最小容量)
        need_sectors = self._required_capacity_sectors(img)
        if need_sectors:
            need_gb = need_sectors * 512 / 1024 / 1024 / 1024
            self._capacity_hint_lbl.setText(
                _tt("backup.task.capacity_hint", gb=f"{need_gb:.1f}"))
        else:
            self._capacity_hint_lbl.setText(_tt("backup.task.capacity_generic"))

    @staticmethod
    def _backup_set_label(img_dir: str, boards: tuple = ()) -> str:
        """备份集可读标签: 板型 · 备份时间 · 大小。

        板型: 用已知板型列表 (recomputer-orin-j401 等名字本身含 '-') 对
        board_spec 行做子串匹配; 无匹配/解析失败回退目录名, 条目永不空。
        时间取 map 文件 mtime, 大小按文件 stat 求和 (不遍历子目录, 快)。
        """
        map_file = Path(img_dir) / "nvpartitionmap.txt"
        board = ""
        mtime = 0.0
        try:
            spec = ""
            for line in map_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("board_spec,"):
                    spec = line.split(",", 1)[-1]
                    break
            # 板名含 '-' (如 reserver-industrial-orin-j401), 不能按 '-' 拆段
            board = next((b for b in boards if b and b in spec), "")
            mtime = map_file.stat().st_mtime
        except OSError:
            pass
        import time
        parts = [board or Path(img_dir).name]
        if mtime:
            parts.append(time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)))
        try:
            size = sum(p.stat().st_size for p in Path(img_dir).iterdir()
                       if p.is_file())
            if size:
                parts.append(f"{size / 1024**3:.1f}G")
        except OSError:
            pass
        return " · ".join(parts)


def build_page() -> QWidget:
    """Build and return the Backup & Restore page widget."""
    return BackupRestorePage()


def _tt(key: str, **kwargs) -> str:
    """Translate with fallback: return the key itself when missing from locales."""
    return t(key, lang=get_language(), **kwargs)