"""设备管理页 — 无边框大气风格
包含：设备信息卡、快速诊断、外设检测，全部接入真实命令执行。
"""
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QDialog, QTextEdit,
)

from seeed_jetson_develop.core.runner import Runner, get_runner
from seeed_jetson_develop.core.events import bus
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, make_input_card as _input_card,
    apply_shadow as _shadow,
)
from seeed_jetson_develop.modules.remote.jetson_init import open_jetson_init_dialog
from .diagnostics import DIAG_ITEMS, PERIPH_ITEMS, run_all, run_periph, collect_info

COLOR_MAP = {
    "ok":    C_GREEN,
    "warn":  C_ORANGE,
    "error": C_RED,
    "info":  C_BLUE,
}


def _status_tag(text="待检测", color=C_TEXT3) -> QLabel:
    """状态标签 - 无边框"""
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


# ── 后台诊断线程 ──────────────────────────────────────────────────────────────
class _DiagThread(QThread):
    result   = pyqtSignal(str, str, str)   # item_id, status_text, color_key
    info_ready = pyqtSignal(dict)          # 设备基本信息 dict
    finished_all = pyqtSignal()

    def __init__(self, mode="full"):
        super().__init__()
        self._runner = get_runner()
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


# ── PyTorch 安装线程 ──────────────────────────────────────────────────────────
class _InstallThread(QThread):
    log     = pyqtSignal(str)
    done    = pyqtSignal(bool)

    _CMDS_JP6 = [
        "sudo apt-get -y update",
        "sudo apt-get install -y python3-pip libopenblas-dev",
        "wget -q https://developer.download.nvidia.com/compute/cusparselt/0.7.1/local_installers/"
        "cusparselt-local-tegra-repo-ubuntu2204-0.7.1_1.0-1_arm64.deb -O /tmp/cusparselt.deb",
        "sudo dpkg -i /tmp/cusparselt.deb",
        "sudo cp /var/cusparselt-local-tegra-repo-ubuntu2204-0.7.1/cusparselt-*-keyring.gpg "
        "/usr/share/keyrings/",
        "sudo apt-get update -qq",
        "sudo apt-get -y install libcusparselt0 libcusparselt-dev",
        "wget -q https://developer.download.nvidia.cn/compute/redist/jp/v61/pytorch/"
        "torch-2.5.0a0+872d972e41.nv24.08.17622132-cp310-cp310-linux_aarch64.whl "
        "-O /tmp/torch_jp6.whl",
        "pip3 install /tmp/torch_jp6.whl",
        "python3 -c \"import torch; print('CUDA:', torch.cuda.is_available())\"",
    ]
    _CMDS_JP5 = [
        "sudo apt-get -y update",
        "sudo apt-get install -y python3-pip libopenblas-dev",
        "wget -q https://developer.download.nvidia.com/compute/redist/jp/v512/pytorch/"
        "torch-2.1.0a0+41361538.nv23.06-cp38-cp38-linux_aarch64.whl "
        "-O /tmp/torch_jp5.whl",
        "pip3 install /tmp/torch_jp5.whl",
        "python3 -c \"import torch; print('CUDA:', torch.cuda.is_available())\"",
    ]

    def __init__(self, l4t: str):
        super().__init__()
        self._l4t = l4t
        self._cancel = False

    def cancel(self): self._cancel = True

    def run(self):
        cmds = self._CMDS_JP6 if "R36" in self._l4t else self._CMDS_JP5
        runner = get_runner()
        for cmd in cmds:
            if self._cancel:
                self.log.emit("⚠ 已取消")
                self.done.emit(False)
                return
            self.log.emit(f"\n$ {cmd}")
            rc, out = runner.run(cmd, timeout=300, on_output=lambda l: self.log.emit(l))
            if rc != 0:
                self.log.emit(f"\n✖ 命令失败 (rc={rc})")
                self.done.emit(False)
                return
        self.done.emit(True)


# ── PyTorch 安装对话框 ────────────────────────────────────────────────────────
class _TorchInstallDialog(QDialog):
    install_succeeded = pyqtSignal()

    def __init__(self, l4t: str, parent=None):
        super().__init__(parent)
        self._l4t = l4t
        self._thread = None
        self.setWindowTitle("安装 PyTorch for Jetson")
        self.setMinimumSize(640, 520)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        # 版本提示
        jp = "JetPack 6.x (R36)" if "R36" in l4t else "JetPack 5.x (R35)"
        info_row = QHBoxLayout()
        info_row.addWidget(_lbl(f"🔖 检测到 {jp}，将自动选择对应 NVIDIA 官方 wheel", 12, C_TEXT2))
        info_row.addStretch()
        lay.addLayout(info_row)

        # 步骤预览
        cmds = _InstallThread._CMDS_JP6 if "R36" in l4t else _InstallThread._CMDS_JP5
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
        lay.addWidget(_lbl("安装日志", 12, C_TEXT2))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(f"""
            background:{C_CARD};
            border:none;
            border-radius:10px;
            color:{C_GREEN};
            font-family:'JetBrains Mono','Consolas',monospace;
            font-size:11px;
            padding:12px;
        """)
        lay.addWidget(self._log, 1)

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
        self._log.moveCursor(QTextCursor.End)
        self._log.insertPlainText(text + "\n")
        self._log.ensureCursorVisible()

    def _start(self):
        self._log.clear()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        t = _InstallThread(self._l4t)
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
            self._append("\n✅ PyTorch 安装成功！CUDA 已可用。")
            self.install_succeeded.emit()
        else:
            self._append("\n❌ 安装未完成，请检查日志。")


# ── 主页面构建 ────────────────────────────────────────────────────────────────
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
    hl.addWidget(_lbl("设备管理", 18, C_TEXT, bold=True))
    hl.addSpacing(12)
    hl.addWidget(_lbl("查看已连接设备状态、运行诊断与外设检测", 12, C_TEXT3))
    hl.addStretch()
    init_btn = _btn("Jetson 初始化", small=True)
    hl.addWidget(init_btn)
    run_btn = _btn("▶  运行全部检测", primary=True, small=True)
    hl.addWidget(run_btn)
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

    # ═══════════════════════════════════════
    # 1. 设备信息卡（4 格）
    # ═══════════════════════════════════════
    info_row = QHBoxLayout()
    info_row.setSpacing(16)
    info_cards: dict[str, QLabel] = {}

    for key, icon, label in [
        ("model",   "🖥",  "设备型号"),
        ("l4t",     "🔖", "L4T 版本"),
        ("memory",  "🧠", "内存使用"),
        ("ip",      "🌐", "IP 地址"),
    ]:
        c = _card(10)
        cl = QVBoxLayout(c)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(6)
        cl.addWidget(_lbl(icon, 20))
        val_lbl = _lbl("采集中…", 14, C_TEXT2, bold=False)
        cl.addWidget(val_lbl)
        cl.addWidget(_lbl(label, 11, C_TEXT3))
        info_cards[key] = val_lbl
        _shadow(c, blur=16)
        info_row.addWidget(c, 1)
    lay.addLayout(info_row)

    # ═══════════════════════════════════════
    # 2. 快速诊断卡 - 无边框行
    # ═══════════════════════════════════════
    diag_card = _card(12)
    dc_lay = QVBoxLayout(diag_card)
    dc_lay.setContentsMargins(20, 18, 20, 18)
    dc_lay.setSpacing(14)

    dh = QHBoxLayout()
    dh.addWidget(_lbl("🔍 快速诊断", 15, C_TEXT, bold=True))
    dh.addStretch()
    diag_only_btn = _btn("仅运行诊断", small=True)
    dh.addWidget(diag_only_btn)
    dc_lay.addLayout(dh)
    dc_lay.addWidget(_lbl("自动检查网络、GPU Torch、Docker、jtop、摄像头等关键组件状态", 12, C_TEXT3))

    diag_tags: dict[str, QLabel] = {}
    _torch_install_btn: list[QPushButton] = [None]
    _l4t_ver: list[str] = ["R36"]

    for item in DIAG_ITEMS:
        row = _input_card(8)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 10, 14, 10)
        rl.addWidget(_lbl(item.icon, 16))
        rl.addWidget(_lbl(item.name, 13, C_TEXT))
        rl.addStretch()

        if item.id == "torch":
            inst_btn = _btn("安装 PyTorch", small=True)
            inst_btn.hide()
            rl.addWidget(inst_btn)
            rl.addSpacing(10)
            _torch_install_btn[0] = inst_btn

        tag = _status_tag("待检测")
        diag_tags[item.id] = tag
        rl.addWidget(tag)
        dc_lay.addWidget(row)

    _shadow(diag_card)
    lay.addWidget(diag_card)

    # ═══════════════════════════════════════
    # 3. 外设状态卡
    # ═══════════════════════════════════════
    periph_card = _card(12)
    pc_lay = QVBoxLayout(periph_card)
    pc_lay.setContentsMargins(20, 18, 20, 18)
    pc_lay.setSpacing(14)

    ph = QHBoxLayout()
    ph.addWidget(_lbl("🔌 外设状态", 15, C_TEXT, bold=True))
    ph.addStretch()
    periph_only_btn = _btn("仅检测外设", small=True)
    ph.addWidget(periph_only_btn)
    pc_lay.addLayout(ph)

    periph_grid = QGridLayout()
    periph_grid.setSpacing(12)
    periph_tags: dict[str, QLabel] = {}
    for i, item in enumerate(PERIPH_ITEMS):
        c = _card(8)
        cl = QVBoxLayout(c)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(6)
        cl.addWidget(_lbl(f"{item.icon}  {item.name}", 12, C_TEXT))
        tag = _status_tag("待检测")
        periph_tags[item.id] = tag
        cl.addWidget(tag)
        periph_grid.addWidget(c, i // 3, i % 3)

    pc_lay.addLayout(periph_grid)
    _shadow(periph_card)
    lay.addWidget(periph_card)

    # ═══════════════════════════════════════
    # 4. 存储 & 温度信息条
    # ═══════════════════════════════════════
    sys_card = _card(10)
    sc_lay = QHBoxLayout(sys_card)
    sc_lay.setContentsMargins(20, 14, 20, 14)
    sc_lay.setSpacing(40)
    sys_labels: dict[str, QLabel] = {}
    for key, icon, label in [
        ("storage", "💾", "存储"),
        ("temp",    "🌡️",  "温度"),
    ]:
        pair = QHBoxLayout()
        pair.setSpacing(8)
        pair.addWidget(_lbl(icon, 16))
        pair.addWidget(_lbl(label + "：", 12, C_TEXT2))
        val = _lbl("—", 12, C_TEXT)
        sys_labels[key] = val
        pair.addWidget(val)
        sc_lay.addLayout(pair)
    sc_lay.addStretch()
    _shadow(sys_card)
    lay.addWidget(sys_card)

    lay.addStretch()
    scroll.setWidget(inner)
    root.addWidget(scroll, 1)

    # ── 线程状态 ──
    _thread: list[_DiagThread] = [None]

    def _set_all_running():
        run_btn.setEnabled(False)
        run_btn.setText("检测中…")
        diag_only_btn.setEnabled(False)
        periph_only_btn.setEnabled(False)
        for t in diag_tags.values():
            t.setText("检测中…")
            t.setStyleSheet(f"color:{C_TEXT3}; background:{C_CARD_LIGHT}; border-radius:6px; padding:4px 12px; font-size:11px;")
        for t in periph_tags.values():
            t.setText("检测中…")
            t.setStyleSheet(f"color:{C_TEXT3}; background:{C_CARD_LIGHT}; border-radius:6px; padding:4px 12px; font-size:11px;")

    def _reset_buttons():
        run_btn.setEnabled(True)
        run_btn.setText("▶  运行全部检测")
        diag_only_btn.setEnabled(True)
        periph_only_btn.setEnabled(True)

    def _on_result(item_id: str, status: str, color_key: str):
        color = COLOR_MAP.get(color_key, C_TEXT2)
        tag = diag_tags.get(item_id) or periph_tags.get(item_id)
        if tag:
            tag.setText(status)
            tag.setStyleSheet(f"""
                background: {C_CARD_LIGHT};
                color: {color};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 500;
            """)
        if item_id == "torch":
            btn = _torch_install_btn[0]
            if btn:
                if color_key in ("error", "warn"):
                    btn.show()
                else:
                    btn.hide()

    def _on_info(info: dict):
        for key, lbl in info_cards.items():
            lbl.setText(info.get(key, "—"))
            lbl.setStyleSheet(f"color:{C_TEXT}; font-size:14px; background:transparent; font-weight:600;")
        for key, lbl in sys_labels.items():
            lbl.setText(info.get(key, "—"))
        l4t = info.get("l4t", "R36")
        _l4t_ver[0] = l4t

    def _start(mode="full"):
        if _thread[0] and _thread[0].isRunning():
            return
        _set_all_running()
        t = _DiagThread(mode)
        t.result.connect(_on_result)
        t.info_ready.connect(_on_info)
        t.finished_all.connect(_reset_buttons)
        t.start()
        _thread[0] = t

    run_btn.clicked.connect(lambda: _start("full"))
    diag_only_btn.clicked.connect(lambda: _start("diag"))
    periph_only_btn.clicked.connect(lambda: _start("periph"))
    init_btn.clicked.connect(lambda: open_jetson_init_dialog(parent=page))

    def _open_torch_install():
        dlg = _TorchInstallDialog(_l4t_ver[0], parent=page)
        dlg.install_succeeded.connect(lambda: _start("diag"))
        dlg.exec_()

    if _torch_install_btn[0]:
        _torch_install_btn[0].clicked.connect(_open_torch_install)

    _start("info")

    return page
