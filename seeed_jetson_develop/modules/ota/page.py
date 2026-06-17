"""OTA Update page for Jetson devices.

Workflow (4 steps):
  Step 1: Select device (product dropdown, like Flash page)
  Step 2: Connect & detect (SSH check, read current JP/L4T, match OTA path)
  Step 3: Download & pre-check (download payload to PC cache, backup list)
  Step 4: Execute OTA (transfer to device, run scripts, reboot)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QPushButton, QTextEdit, QScrollArea, QProgressBar,
    QMessageBox, QFrame, QSizePolicy, QButtonGroup, QRadioButton,
)

from seeed_jetson_develop.core.runner import get_runner, SSHRunner
from seeed_jetson_develop.core.events import bus
from seeed_jetson_develop.gui.i18n import get_language, t
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt, make_label as _lbl, make_button as _btn,
    make_card as _card, DropdownButton,
    show_error_message as _show_error_message,
    show_info_message as _show_info_message,
    show_warning_message as _show_warning_message,
    ShinyProgressBar,
)
from seeed_jetson_develop.data_update import load_json_data

_DATA_DIR = Path(__file__).resolve().parent / "data"
_OTA_PATHS_FILE = _DATA_DIR / "ota_paths.json"
_CACHE_DIR = Path.home() / ".cache" / "seeed-jetson" / "ota"


def _at(key: str, **kwargs) -> str:
    return t(key, lang=get_language(), **kwargs)


def _human_bytes(n: int) -> str:
    """Return a human-readable byte string; handle negative values gracefully."""
    n = int(n)
    if n < 0:
        return f"{_human_bytes(-n)} (invalid)"
    if n >= 1 << 30:
        return f"{n / (1 << 30):.2f} GB"
    if n >= 1 << 20:
        return f"{n / (1 << 20):.2f} MB"
    if n >= 1 << 10:
        return f"{n / (1 << 10):.2f} KB"
    return f"{n} B"


def _format_eta(seconds: int) -> str:
    """Format seconds into a concise ETA string."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


def _load_ota_data() -> dict:
    try:
        return json.loads(_OTA_PATHS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"ota_paths": [], "notes": {}}


def _get_cache_size() -> int:
    """Return total size of the OTA cache directory in bytes."""
    total = 0
    if not _CACHE_DIR.exists():
        return 0
    for path in _CACHE_DIR.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except Exception:
            pass
    return total


def _clear_cache_dir() -> tuple[bool, int, str]:
    """Clear the OTA cache directory. Returns (success, bytes_freed, error_message)."""
    freed = 0
    if not _CACHE_DIR.exists():
        return True, 0, ""
    errors = []
    for path in list(_CACHE_DIR.rglob("*")):
        try:
            if path.is_file():
                freed += path.stat().st_size
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        except Exception as e:
            errors.append(f"{path.name}: {e}")
    try:
        _CACHE_DIR.rmdir()
    except Exception:
        pass
    if errors:
        return False, freed, "; ".join(errors)
    return True, freed, ""


def _l4t_to_jetpack(l4t: str) -> str | None:
    mapping = {
        "35.5.0": "5.1.3", "35.5": "5.1.3",
        "36.4.3": "6.2", "36.4": "6.2",
        "36.3.0": "6.0", "36.3": "6.0",
        "36.2.0": "6.0 DP", "36.2": "6.0 DP",
        "39.2": "7.2", "39.2.0": "7.2",
    }
    return mapping.get(l4t) or mapping.get(l4t.rsplit(".", 1)[0] if "." in l4t else l4t)


def _product_display_name(product: str) -> str:
    """Return a user-facing product name (same logic as Flash page)."""
    raw = (product or "").strip()
    if not raw:
        return raw
    compact = raw.replace(" ", "").lower()
    suffix_map = {
        "classic": "Classic",
        "industrial": "Industrial",
        "mini": "Mini",
        "robotics": "Robotics",
        "s": "Super",
    }
    m = re.fullmatch(r"(j\d+)(classic|industrial|mini|robotics|reserver|s)", compact)
    if m:
        model, suffix = m.groups()
        if suffix == "reserver":
            return f"reServer {model.upper()}"
        return f"reComputer {model.upper()} {suffix_map[suffix]}"
    m = re.fullmatch(r"j501-carrieragx-orin(\d+)g", compact)
    if m:
        return f"reServer J501 Carrier AGX Orin {m.group(1)}G"
    m = re.fullmatch(r"j501mini-agx-orin-(\d+)g", compact)
    if m:
        return f"reComputer J501 Mini AGX Orin {m.group(1)}G"
    m = re.fullmatch(r"j501-agx-orin-(\d+)g", compact)
    if m:
        return f"reComputer J501 AGX Orin {m.group(1)}G"
    if compact == "orin-nano-devkit-super":
        return "Orin Nano Dev Kit Super"
    return f"reComputer {raw}"


def _load_product_data(ota_paths: list[dict]):
    """Load products that have OTA upgrade paths configured."""
    l4t_data = load_json_data("l4t_data.json", [])
    product_images = load_json_data("product_images.json", {})
    # Collect all product keys supported by any OTA path
    supported_keys = set()
    for path in ota_paths:
        supported_keys.update(path.get("product_keys", []))

    products = {}
    for item in l4t_data:
        p = item["product"]
        if p not in supported_keys:
            continue
        products.setdefault(p, []).append(item["l4t"])

    # Also include supported keys that have no entry in l4t_data yet
    # (e.g. new products whose firmware list hasn't been updated)
    for p in supported_keys:
        if p not in products:
            products[p] = []

    # Deduplicate and sort versions
    for p, l4ts in products.items():
        products[p] = sorted(set(l4ts))

    return products, product_images


# ── Page builder ─────────────────────────────────────────────────────────────

def build_page() -> QWidget:
    ota_data = _load_ota_data()
    ota_paths = ota_data.get("ota_paths", [])
    products, product_images = _load_product_data(ota_paths)

    page = QWidget()
    page.setObjectName("OtaPage")

    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    # ── Header ──
    header = QWidget()
    header.setFixedHeight(pt(56))
    header.setStyleSheet(f"background:{C_BG_DEEP};")
    hb = QHBoxLayout(header)
    hb.setContentsMargins(pt(28), 0, pt(28), 0)
    title_lbl = _lbl(_at("ota.page.title"), 18, C_TEXT, bold=True)
    sub_lbl = _lbl(_at("ota.page.subtitle"), 12, C_TEXT2)
    hb.addWidget(title_lbl)
    hb.addSpacing(pt(12))
    hb.addWidget(sub_lbl)
    hb.addStretch()
    root.addWidget(header)

    # ── Scrollable body ──
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setStyleSheet("background:transparent; border:none;")
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    inner = QWidget()
    inner.setStyleSheet("background:transparent;")
    inner_lay = QVBoxLayout(inner)
    inner_lay.setContentsMargins(pt(28), pt(24), pt(28), pt(24))
    inner_lay.setSpacing(pt(20))

    # ── Wizard step indicator ──
    _step_circles: list[QLabel] = []
    _step_labels: list[QLabel] = []
    _step_arrows: list[QLabel] = []

    wizard_card = _card(12)
    wizard_lay = QHBoxLayout(wizard_card)
    wizard_lay.setSpacing(0)
    wizard_lay.setContentsMargins(pt(16), pt(12), pt(16), pt(12))

    step_names = [
        _at("ota.step.device"),
        _at("ota.step.connect"),
        _at("ota.step.download"),
        _at("ota.step.execute"),
    ]

    def _apply_step_style(circle: QLabel, lbl: QLabel, state: str):
        if state == "done":
            circle.setStyleSheet(
                f"background:{C_GREEN}; color:#fff; border-radius:10px; "
                f"font-size:11px; font-weight:700; padding:2px 6px;"
            )
            lbl.setStyleSheet(f"color:{C_GREEN}; font-size:12px; font-weight:600;")
        elif state == "active":
            circle.setStyleSheet(
                f"background:{C_GREEN}; color:#fff; border-radius:10px; "
                f"font-size:11px; font-weight:700; padding:2px 6px;"
            )
            lbl.setStyleSheet(f"color:{C_TEXT}; font-size:12px; font-weight:600;")
        else:
            circle.setStyleSheet(
                f"background:{C_BG_DEEP}; color:{C_TEXT3}; border-radius:10px; "
                f"font-size:11px; font-weight:700; padding:2px 6px;"
            )
            lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:12px;")

    def _set_wizard_step(active_idx: int):
        for i, (c, l) in enumerate(zip(_step_circles, _step_labels)):
            if i < active_idx:
                _apply_step_style(c, l, "done")
            elif i == active_idx:
                _apply_step_style(c, l, "active")
            else:
                _apply_step_style(c, l, "pending")
        for a in _step_arrows:
            a.setStyleSheet(f"color:{C_TEXT3}; font-size:14px;")
        if 0 <= active_idx - 1 < len(_step_arrows):
            _step_arrows[active_idx - 1].setStyleSheet(f"color:{C_GREEN}; font-size:14px;")

    for idx, name in enumerate(step_names):
        c = QLabel(f"{idx + 1}")
        c.setAlignment(Qt.AlignCenter)
        c.setFixedSize(pt(24), pt(24))
        l = QLabel(name)
        l.setAlignment(Qt.AlignCenter)
        step_w = QWidget()
        step_lay = QVBoxLayout(step_w)
        step_lay.setContentsMargins(0, 0, 0, 0)
        step_lay.setSpacing(2)
        step_lay.addWidget(c, alignment=Qt.AlignCenter)
        step_lay.addWidget(l, alignment=Qt.AlignCenter)
        wizard_lay.addWidget(step_w)
        _step_circles.append(c)
        _step_labels.append(l)
        if idx < len(step_names) - 1:
            arrow = QLabel("›")
            arrow.setStyleSheet(f"color:{C_TEXT3}; font-size:14px; padding:0 8px;")
            wizard_lay.addWidget(arrow)
            _step_arrows.append(arrow)
    wizard_lay.addStretch()
    _set_wizard_step(0)
    inner_lay.addWidget(wizard_card)

    # ── Content stack ──
    content_stack = QStackedWidget()
    content_stack.setStyleSheet("background:transparent; border:none;")

    _state = {
        "current_l4t": "",
        "current_jp": "",
        "device_model": "",
        "selected_product": "",
        "selected_path": None,
        "ota_paths": ota_paths,
        "products": products,
        "product_images": product_images,
        "thread": None,
        "payload_local_path": "",
    }

    # ═══════════════════════════════════════════════════════════════════════
    #  Step 0: Select Device (like Flash)
    # ═══════════════════════════════════════════════════════════════════════
    step0 = QWidget()
    step0.setStyleSheet("background:transparent;")
    s0_lay = QVBoxLayout(step0)
    s0_lay.setContentsMargins(0, 0, 0, 0)
    s0_lay.setSpacing(pt(16))

    device_card = _card(12)
    device_lay = QVBoxLayout(device_card)
    device_lay.setSpacing(pt(12))

    device_title = _lbl(_at("ota.device.title"), 14, C_TEXT, bold=True)
    device_lay.addWidget(device_title)

    device_hint = _lbl(_at("ota.device.hint"), 12, C_TEXT2)
    device_lay.addWidget(device_hint)

    product_combo = DropdownButton()
    product_combo.setFixedHeight(pt(40))
    for pk in sorted(products.keys(), key=_product_display_name):
        product_combo.addItem(_product_display_name(pk), pk)
    device_lay.addWidget(product_combo)

    # Device image + info row
    dev_info_row = QHBoxLayout()
    dev_img = QLabel()
    dev_img.setFixedSize(pt(160), pt(100))
    dev_img.setScaledContents(True)
    dev_img.setStyleSheet(f"background:{C_CARD_LIGHT}; border-radius:8px;")
    dev_info_col = QVBoxLayout()
    dev_info_col.setSpacing(pt(8))
    dev_name_lbl = _lbl("", 14, C_TEXT, bold=True)
    dev_versions_lbl = _lbl("", 12, C_TEXT2)
    dev_versions_lbl.setWordWrap(True)
    dev_ota_hint = _lbl("", 12, C_ORANGE)
    dev_ota_hint.setWordWrap(True)
    dev_info_col.addWidget(dev_name_lbl)
    dev_info_col.addWidget(dev_versions_lbl)
    dev_info_col.addWidget(dev_ota_hint)
    dev_info_row.addWidget(dev_img)
    dev_info_row.addLayout(dev_info_col, 1)
    device_lay.addLayout(dev_info_row)

    s0_lay.addWidget(device_card)

    s0_nav = QHBoxLayout()
    s0_nav.addStretch()
    s0_next = _btn(_at("ota.nav.next"), primary=True)
    s0_nav.addWidget(s0_next)
    s0_lay.addLayout(s0_nav)

    content_stack.addWidget(step0)

    # ═══════════════════════════════════════════════════════════════════════
    #  Step 1: Connect & Detect
    # ═══════════════════════════════════════════════════════════════════════
    step1 = QWidget()
    step1.setStyleSheet("background:transparent;")
    s1_lay = QVBoxLayout(step1)
    s1_lay.setContentsMargins(0, 0, 0, 0)
    s1_lay.setSpacing(pt(16))

    conn_card = _card(12)
    conn_lay = QVBoxLayout(conn_card)
    conn_lay.setSpacing(pt(12))

    conn_title = _lbl(_at("ota.connect.title"), 14, C_TEXT, bold=True)
    conn_lay.addWidget(conn_title)

    conn_info = _lbl(_at("ota.connect.checking"), 12, C_TEXT2)
    conn_lay.addWidget(conn_info)

    conn_btn = _btn(_at("ota.connect.go_remote"), primary=True)
    conn_btn.setVisible(False)
    conn_lay.addWidget(conn_btn, alignment=Qt.AlignLeft)
    s1_lay.addWidget(conn_card)

    detect_card = _card(12)
    detect_card.setVisible(False)
    detect_lay = QVBoxLayout(detect_card)
    detect_lay.setSpacing(pt(12))

    detect_title = _lbl(_at("ota.connect.detect_title"), 14, C_TEXT, bold=True)
    detect_lay.addWidget(detect_title)

    detect_grid = QHBoxLayout()
    dev_ip_lbl = _lbl("IP: --", 12, C_TEXT2)
    dev_model_lbl = _lbl(_at("ota.device.model") + ": --", 12, C_TEXT2)
    dev_l4t_lbl = _lbl(_at("ota.device.l4t") + ": --", 12, C_TEXT2)
    dev_jp_lbl = _lbl(_at("ota.device.jetpack") + ": --", 12, C_TEXT2)
    for w in (dev_ip_lbl, dev_model_lbl, dev_l4t_lbl, dev_jp_lbl):
        detect_grid.addWidget(w)
    detect_lay.addLayout(detect_grid)

    match_lbl = _lbl("", 12, C_ORANGE)
    match_lbl.setWordWrap(True)
    detect_lay.addWidget(match_lbl)

    path_match_lbl = _lbl("", 12, C_TEXT2)
    path_match_lbl.setWordWrap(True)
    detect_lay.addWidget(path_match_lbl)

    detect_btn = _btn(_at("ota.device.detect"), primary=True)
    detect_lay.addWidget(detect_btn, alignment=Qt.AlignLeft)
    s1_lay.addWidget(detect_card)

    s1_nav = QHBoxLayout()
    s1_prev = _btn(_at("ota.nav.prev"), primary=False)
    s1_next = _btn(_at("ota.nav.next"), primary=True)
    s1_next.setEnabled(False)
    s1_nav.addWidget(s1_prev)
    s1_nav.addStretch()
    s1_nav.addWidget(s1_next)
    s1_lay.addLayout(s1_nav)

    content_stack.addWidget(step1)

    # ═══════════════════════════════════════════════════════════════════════
    #  Step 2: Download & Pre-check
    # ═══════════════════════════════════════════════════════════════════════
    step2 = QWidget()
    step2.setStyleSheet("background:transparent;")
    s2_lay = QVBoxLayout(step2)
    s2_lay.setContentsMargins(0, 0, 0, 0)
    s2_lay.setSpacing(pt(16))

    download_card = _card(12)
    dl_lay = QVBoxLayout(download_card)
    dl_lay.setSpacing(pt(12))

    dl_title = _lbl(_at("ota.download.title"), 14, C_TEXT, bold=True)
    dl_lay.addWidget(dl_title)

    dl_status = _lbl(_at("ota.download.ready"), 12, C_TEXT2)
    dl_lay.addWidget(dl_status)

    dl_progress = ShinyProgressBar()
    dl_progress.setFixedHeight(pt(8))
    dl_progress.setValue(0)
    dl_lay.addWidget(dl_progress)

    dl_info = _lbl("", 12, C_TEXT3)
    dl_lay.addWidget(dl_info)

    # Payload options radio group
    payload_group = QButtonGroup()
    payload_group_lay = QVBoxLayout()
    payload_group_lay.setSpacing(pt(8))
    lang = get_language()
    for opt in (_state["selected_path"] or {}).get("payload_options", []):
        label = opt.get("name" if lang == "zh" else "name_en", opt.get("name", ""))
        rb = QRadioButton(label)
        rb.setStyleSheet(f"color:{C_TEXT2}; font-size:{pt(12)}px;")
        payload_group.addButton(rb)
        rb.setProperty("payload_id", opt.get("id", ""))
        payload_group_lay.addWidget(rb)
    if payload_group.buttons():
        payload_group.buttons()[0].setChecked(True)
    dl_lay.addLayout(payload_group_lay)

    dl_btn = _btn(_at("ota.download.btn"), primary=True)
    dl_btn.setVisible(False)
    dl_lay.addWidget(dl_btn, alignment=Qt.AlignLeft)
    s2_lay.addWidget(download_card)

    # ── Cache management card ──
    cache_card = _card(12)
    cache_lay = QVBoxLayout(cache_card)
    cache_lay.setSpacing(pt(12))

    cache_title = _lbl(_at("ota.cache.title"), 14, C_TEXT, bold=True)
    cache_lay.addWidget(cache_title)

    cache_path_lbl = _lbl(_at("ota.cache.location", path=str(_CACHE_DIR)), 11, C_TEXT3, wrap=True)
    cache_lay.addWidget(cache_path_lbl)

    cache_size_lbl = _lbl(_at("ota.cache.size", size=_human_bytes(_get_cache_size())), 12, C_TEXT2)
    cache_lay.addWidget(cache_size_lbl)

    cache_clear_btn = _btn(_at("ota.cache.clear_btn"), primary=False)
    cache_lay.addWidget(cache_clear_btn, alignment=Qt.AlignLeft)
    s2_lay.addWidget(cache_card)

    def _update_cache_labels():
        cache_title.setText(_at("ota.cache.title"))
        cache_path_lbl.setText(_at("ota.cache.location", path=str(_CACHE_DIR)))
        cache_size_lbl.setText(_at("ota.cache.size", size=_human_bytes(_get_cache_size())))
        cache_clear_btn.setText(_at("ota.cache.clear_btn"))

    def _on_clear_cache():
        reply = QMessageBox.question(
            page,
            _at("common.notice"),
            _at("ota.cache.clear_confirm"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        ok, freed, err = _clear_cache_dir()
        _update_cache_labels()
        if ok:
            _show_info_message(
                page,
                _at("common.notice"),
                _at("ota.cache.clear_success", size=_human_bytes(freed)),
            )
        else:
            _show_error_message(
                page,
                _at("common.notice"),
                _at("ota.cache.clear_error", error=err),
            )

    cache_clear_btn.clicked.connect(_on_clear_cache)

    precheck_card = _card(12)
    pre_lay = QVBoxLayout(precheck_card)
    pre_lay.setSpacing(pt(12))

    pre_title = _lbl(_at("ota.precheck.title"), 14, C_TEXT, bold=True)
    pre_lay.addWidget(pre_title)

    backup_title = _lbl(_at("ota.precheck.backup_title"), 13, C_TEXT, bold=True)
    pre_lay.addWidget(backup_title)

    backup_hint = _lbl(_at("ota.precheck.backup_hint"), 11, C_TEXT3, wrap=True)
    pre_lay.addWidget(backup_hint)

    backup_edit = QTextEdit()
    backup_edit.setPlainText(
        "/home/seeed/.bashrc\n"
        "/home/seeed/.ssh\n"
        "/home/seeed/workspace\n"
    )
    backup_edit.setFixedHeight(pt(120))
    backup_edit.setStyleSheet(
        f"background:{C_CARD_LIGHT}; border:none; border-radius:8px; "
        f"color:{C_TEXT2}; font-family:'JetBrains Mono','Consolas',monospace; "
        f"font-size:{pt(11)}px; padding:8px;"
    )
    pre_lay.addWidget(backup_edit)

    note_card = QFrame()
    note_card.setStyleSheet(
        f"background:rgba(255,193,7,0.10); border:1px solid rgba(255,193,7,0.30); "
        f"border-radius:8px; padding:8px;"
    )
    note_lay = QHBoxLayout(note_card)
    note_lay.setContentsMargins(pt(12), pt(8), pt(12), pt(8))
    note_icon = _lbl("⚠", 16, "#FFC107")
    note_text = _lbl(_at("ota.precheck.warning"), 12, C_TEXT2, wrap=True)
    note_lay.addWidget(note_icon)
    note_lay.addWidget(note_text, 1)
    pre_lay.addWidget(note_card)

    s2_lay.addWidget(precheck_card)

    s2_nav = QHBoxLayout()
    s2_prev = _btn(_at("ota.nav.prev"), primary=False)
    s2_next = _btn(_at("ota.nav.next"), primary=True)
    s2_nav.addWidget(s2_prev)
    s2_nav.addStretch()
    s2_nav.addWidget(s2_next)
    s2_lay.addLayout(s2_nav)

    content_stack.addWidget(step2)

    # ═══════════════════════════════════════════════════════════════════════
    #  Step 3: Execute OTA
    # ═══════════════════════════════════════════════════════════════════════
    step3 = QWidget()
    step3.setStyleSheet("background:transparent;")
    s3_lay = QVBoxLayout(step3)
    s3_lay.setContentsMargins(0, 0, 0, 0)
    s3_lay.setSpacing(pt(16))

    exec_card = _card(12)
    exec_lay = QVBoxLayout(exec_card)
    exec_lay.setSpacing(pt(12))

    exec_title = _lbl(_at("ota.execute.title"), 14, C_TEXT, bold=True)
    exec_lay.addWidget(exec_title)

    exec_status = _lbl(_at("ota.execute.ready"), 12, C_TEXT2)
    exec_lay.addWidget(exec_status)

    progress = ShinyProgressBar()
    progress.setFixedHeight(pt(8))
    progress.setValue(0)
    exec_lay.addWidget(progress)

    exec_log = QTextEdit()
    exec_log.setReadOnly(True)
    exec_log.setStyleSheet(
        f"background:{C_CARD_LIGHT}; border:none; border-radius:8px; "
        f"color:{C_GREEN}; font-family:'JetBrains Mono','Consolas',monospace; "
        f"font-size:{pt(11)}px; padding:10px;"
    )
    exec_log.setMinimumHeight(pt(180))
    exec_lay.addWidget(exec_log)

    done_widget = QWidget()
    done_widget.setVisible(False)
    done_lay = QVBoxLayout(done_widget)
    done_lay.setContentsMargins(0, 0, 0, 0)
    done_lay.setSpacing(pt(8))
    done_icon = _lbl("✅", 32, C_GREEN)
    done_icon.setAlignment(Qt.AlignCenter)
    done_msg = _lbl(_at("ota.execute.done_msg"), 14, C_TEXT, bold=True)
    done_msg.setAlignment(Qt.AlignCenter)
    done_note = _lbl(_at("ota.execute.done_note"), 12, C_TEXT2, wrap=True)
    done_note.setAlignment(Qt.AlignCenter)
    done_lay.addWidget(done_icon)
    done_lay.addWidget(done_msg)
    done_lay.addWidget(done_note)
    exec_lay.addWidget(done_widget)

    s3_lay.addWidget(exec_card)

    s3_nav = QHBoxLayout()
    s3_prev = _btn(_at("ota.nav.prev"), primary=False)
    s3_prev.setEnabled(False)
    s3_cancel = _btn(_at("ota.nav.cancel"), primary=False, danger=True)
    s3_cancel.setVisible(False)
    s3_retry = _btn(_at("ota.nav.start"), primary=True)
    s3_retry.setVisible(True)
    s3_nav.addWidget(s3_prev)
    s3_nav.addWidget(s3_cancel)
    s3_nav.addStretch()
    s3_nav.addWidget(s3_retry)
    s3_lay.addLayout(s3_nav)

    content_stack.addWidget(step3)

    inner_lay.addWidget(content_stack, 1)
    scroll.setWidget(inner)
    root.addWidget(scroll, 1)

    # ═══════════════════════════════════════════════════════════════════════
    #  Interactions
    # ═══════════════════════════════════════════════════════════════════════

    def _goto_step(idx: int):
        content_stack.setCurrentIndex(idx)
        _set_wizard_step(idx)
        if idx == 3:
            s3_prev.setEnabled(True)

    def _on_product_changed(text: str):
        pk = product_combo.currentData()
        if not pk:
            return
        _state["selected_product"] = pk
        # Update image
        img_data = product_images.get(pk, {})
        img_path = img_data.get("local_image", "")
        if img_path:
            from PyQt5.QtGui import QPixmap
            pix = QPixmap(str(Path(__file__).resolve().parents[3] / img_path))
            if not pix.isNull():
                dev_img.setPixmap(pix.scaled(dev_img.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        # Update info
        dev_name_lbl.setText(img_data.get("name", _product_display_name(pk)))
        versions = products.get(pk, [])
        dev_versions_lbl.setText(_at("ota.device.versions", count=len(versions)))
        # Find matching OTA paths
        matched = [p for p in ota_paths if pk in p.get("product_keys", [])]
        if matched:
            names = ", ".join(p["name"] for p in matched)
            dev_ota_hint.setText(_at("ota.device.ota_available", paths=names))
            dev_ota_hint.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(12)}px;")
        else:
            dev_ota_hint.setText("")
            dev_ota_hint.setStyleSheet("")

    def _update_conn_status():
        runner = get_runner()
        if isinstance(runner, SSHRunner):
            conn_info.setText(_at("ota.connect.connected", ip=runner.host, user=runner.username))
            conn_btn.setVisible(False)
            detect_card.setVisible(True)
            dev_ip_lbl.setText(f"IP: {runner.host}")
        else:
            conn_info.setText(_at("ota.connect.no_ssh"))
            conn_btn.setVisible(True)
            detect_card.setVisible(False)

    def _detect_device():
        runner = get_runner()
        if not isinstance(runner, SSHRunner):
            _show_warning_message(page, _at("common.notice"), _at("ota.connect.no_ssh"))
            return
        detect_btn.setEnabled(False)
        detect_btn.setText(_at("ota.device.detecting"))

        def _do_detect():
            rc, out = runner.run(
                "head -1 /etc/nv_tegra_release 2>/dev/null | awk '{gsub(\",\",\"\",$5); print $2\".\"$5}'",
                timeout=10,
            )
            l4t = out.strip().lstrip("Rr") if rc == 0 else ""
            rc2, out2 = runner.run(
                "cat /proc/device-tree/model 2>/dev/null | tr '\\0' '\\n' | head -1",
                timeout=10,
            )
            model = out2.strip() if rc2 == 0 else ""
            return l4t, model

        class _DetectThread(QThread):
            result = pyqtSignal(str, str)

            def run(self):
                l4t, model = _do_detect()
                self.result.emit(l4t, model)

        t = _DetectThread()
        _state["detect_thread"] = t

        def _on_detect_done(l4t: str, model: str):
            _state.pop("detect_thread", None)
            detect_btn.setEnabled(True)
            detect_btn.setText(_at("ota.device.detect"))
            _state["current_l4t"] = l4t
            _state["current_jp"] = _l4t_to_jetpack(l4t) or _at("ota.unknown")
            _state["device_model"] = model
            dev_l4t_lbl.setText(_at("ota.device.l4t") + f": {l4t or '--'}")
            dev_jp_lbl.setText(_at("ota.device.jetpack") + f": {_state['current_jp']}")
            dev_model_lbl.setText(_at("ota.device.model") + f": {model or '--'}")
            # Match OTA path
            pk = _state.get("selected_product", "")
            matched = None
            for p in ota_paths:
                if pk in p.get("product_keys", []):
                    src_l4t = p.get("source_l4t", "")
                    if l4t == src_l4t or l4t.startswith(src_l4t):
                        matched = p
                        break
            if matched:
                _state["selected_path"] = matched
                match_lbl.setText(_at("ota.connect.match_ok"))
                match_lbl.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(12)}px;")
                path_match_lbl.setText(_at("ota.connect.path_matched", name=matched.get("name", "")))
                s1_next.setEnabled(True)
            else:
                _state["selected_path"] = None
                match_lbl.setText(_at("ota.connect.match_fail", current=l4t))
                match_lbl.setStyleSheet(f"color:{C_RED}; font-size:{pt(12)}px;")
                path_match_lbl.setText(_at("ota.connect.path_unavailable"))
                s1_next.setEnabled(False)

        t.result.connect(_on_detect_done)
        t.start()

    def _log_append(text: str):
        exec_log.append(text)
        scrollbar = exec_log.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _on_ota_log(msg: str):
        _log_append(msg)

    def _on_ota_progress(pct: int):
        progress.setValue(pct)

    _last_dl_log_ts = [0.0]
    _dl_start_ts = [0.0]
    _dl_start_bytes = [0]
    _dl_last_ts = [0.0]
    _dl_last_bytes = [0]

    def _on_ota_download_progress(current: int, total: int):
        import time
        now = time.time()
        current = max(0, int(current))
        total = max(0, int(total))

        if _dl_start_ts[0] == 0.0:
            _dl_start_ts[0] = now
            _dl_start_bytes[0] = current
            _dl_last_ts[0] = now
            _dl_last_bytes[0] = current

        delta_time = now - _dl_last_ts[0]
        delta_bytes = current - _dl_last_bytes[0]
        speed = int(delta_bytes / delta_time) if delta_time > 0 else 0

        if delta_time >= 1.0:
            _dl_last_ts[0] = now
            _dl_last_bytes[0] = current

        if total > 0:
            pct = int(current / total * 100)
            progress.setValue(pct)
            dl_info = f"{_human_bytes(current)} / {_human_bytes(total)} ({pct}%)"
            if speed > 0 and current < total:
                eta = (total - current) / speed
                dl_info += f"  {_human_bytes(speed)}/s  ETA: {_format_eta(int(eta))}"
            exec_status.setText(_at("ota.execute.downloading", info=dl_info))
            if now - _last_dl_log_ts[0] >= 2 or current == total:
                _last_dl_log_ts[0] = now
                _log_append(
                    f"[download] {_human_bytes(current)} / {_human_bytes(total)} "
                    f"({pct}%) {_human_bytes(speed)}/s"
                )
        else:
            dl_info = f"{_human_bytes(current)}"
            if speed > 0:
                dl_info += f"  {_human_bytes(speed)}/s"
            exec_status.setText(_at("ota.execute.downloading", info=dl_info))
            if now - _last_dl_log_ts[0] >= 2:
                _last_dl_log_ts[0] = now
                _log_append(f"[download] {_human_bytes(current)} {_human_bytes(speed)}/s")

    def _on_ota_stage(stage_name: str):
        stage_map = {
            "download": ("#2196F3", "#1565C0", _at("ota.stage.download")),
            "upload":   ("#FF9800", "#EF6C00", _at("ota.stage.upload")),
            "prepare":  ("#9C27B0", "#7B1FA2", _at("ota.stage.prepare")),
            "execute":  ("#B0E030", "#7AB317", _at("ota.stage.execute")),
        }
        top, bottom, text = stage_map.get(stage_name, stage_map["execute"])
        progress.set_color(top, bottom)
        exec_status.setText(text)
        exec_status.setStyleSheet(f"color:{top}; font-size:{pt(12)}px;")

    def _on_ota_done(success: bool, msg: str):
        _state["thread"] = None
        s3_cancel.setVisible(False)
        s3_prev.setEnabled(True)
        if success:
            exec_status.setText(_at("ota.execute.finished"))
            exec_status.setStyleSheet(f"color:{C_GREEN}; font-size:{pt(12)}px;")
            done_widget.setVisible(True)
            _log_append(_at("ota.execute.success", msg=msg))
        else:
            s3_retry.setText(_at("ota.nav.retry"))
            s3_retry.setVisible(True)
            exec_status.setText(_at("ota.execute.failed"))
            exec_status.setStyleSheet(f"color:{C_RED}; font-size:{pt(12)}px;")
            _log_append(_at("ota.execute.error", msg=msg))

    def _start_ota():
        runner = get_runner()
        if not isinstance(runner, SSHRunner):
            _show_warning_message(page, _at("common.notice"), _at("ota.connect.no_ssh"))
            return
        pk = _state.get("selected_product", "")
        path = _find_path_for_product(pk)
        if not path:
            _show_warning_message(page, _at("common.notice"), _at("ota.connect.no_path"))
            return

        # Find selected payload option
        selected_payload = None
        for btn in payload_group.buttons():
            if btn.isChecked():
                pid = btn.property("payload_id")
                for opt in path.get("payload_options", []):
                    if opt.get("id") == pid:
                        selected_payload = opt
                        break
                break
        if not selected_payload:
            _show_warning_message(page, _at("common.notice"), _at("ota.download.no_variant"))
            return
        if not selected_payload.get("url"):
            _show_warning_message(page, _at("common.notice"), _at("ota.download.url_missing"))
            return

        backup_files = [
            line.strip()
            for line in backup_edit.toPlainText().splitlines()
            if line.strip()
        ]

        s3_prev.setEnabled(False)
        s3_cancel.setVisible(True)
        s3_cancel.setEnabled(True)
        s3_retry.setVisible(False)
        done_widget.setVisible(False)
        exec_log.clear()
        progress.setValue(0)
        # Reset download progress tracking state for a fresh run.
        _dl_start_ts[0] = 0.0
        _dl_start_bytes[0] = 0
        _dl_last_ts[0] = 0.0
        _dl_last_bytes[0] = 0
        _last_dl_log_ts[0] = 0.0
        exec_status.setText(_at("ota.execute.running"))
        exec_status.setStyleSheet(f"color:{C_ORANGE}; font-size:{pt(12)}px;")
        _log_append(_at("ota.execute.started"))

        from seeed_jetson_develop.modules.ota.thread import OTAThread
        t = OTAThread(runner, path, selected_payload, backup_files)
        t.log.connect(_on_ota_log)
        t.progress.connect(_on_ota_progress)
        t.download_progress.connect(_on_ota_download_progress)
        t.stage.connect(_on_ota_stage)
        t.done.connect(_on_ota_done)
        _state["thread"] = t
        t.start()

    def _cancel_ota():
        t = _state.get("thread")
        if t is not None:
            _log_append(_at("ota.execute.cancelling"))
            t.cancel()
            s3_cancel.setEnabled(False)
        else:
            _show_warning_message(page, _at("common.notice"), _at("ota.execute.no_thread"))

    # Wire signals
    product_combo.currentTextChanged.connect(_on_product_changed)

    s0_next.clicked.connect(lambda: _goto_step(1))
    s1_prev.clicked.connect(lambda: _goto_step(0))
    def _find_path_for_product(pk: str) -> dict | None:
        """Look up the OTA path for a given product key by re-reading config."""
        ota_data = _load_ota_data()
        for p in ota_data.get("ota_paths", []):
            if pk in p.get("product_keys", []):
                return p
        return None

    def _enter_step2():
        pk = _state.get("selected_product", "")
        path = _find_path_for_product(pk)
        # fully clear layout + button group
        while payload_group_lay.count():
            item = payload_group_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for btn in list(payload_group.buttons()):
            payload_group.removeButton(btn)

        if path:
            _state["selected_path"] = path
            lang = get_language()
            all_opts = path.get("payload_options", [])
            valid_opts = [opt for opt in all_opts if opt.get("url")]
            display_opts = valid_opts if valid_opts else all_opts
            if not display_opts:
                _show_warning_message(page, _at("common.notice"), _at("ota.download.no_valid_variant"))
                return
            for opt in display_opts:
                label = opt.get("name" if lang == "zh" else "name_en", opt.get("name", ""))
                if not opt.get("url"):
                    label += " (URL unavailable)"

                btn = QPushButton(label)
                btn.setCheckable(True)
                btn.setAutoExclusive(True)
                btn.setProperty("payload_id", opt.get("id", ""))
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background:{C_CARD_LIGHT};"
                    f"  border:2px solid {C_CARD_LIGHT};"
                    f"  border-radius:8px;"
                    f"  color:{C_TEXT2};"
                    f"  font-size:{pt(13)}px;"
                    f"  padding:{pt(8)}px {pt(16)}px;"
                    f"  text-align:left;"
                    f"}}"
                    f"QPushButton:hover {{"
                    f"  border-color:{C_BLUE};"
                    f"  color:{C_TEXT};"
                    f"}}"
                    f"QPushButton:checked {{"
                    f"  background:{C_BLUE};"
                    f"  border-color:{C_BLUE};"
                    f"  color:#FFFFFF;"
                    f"  font-weight:bold;"
                    f"}}"
                )
                payload_group.addButton(btn)
                payload_group_lay.addWidget(btn)
            if payload_group.buttons():
                payload_group.buttons()[0].setChecked(True)
            dl_status.setText(_at("ota.download.ready"))
        else:
            _state["selected_path"] = None
            dl_status.setText(_at("ota.download.no_path"))
        _update_cache_labels()
        _goto_step(2)

    s1_next.clicked.connect(_enter_step2)
    s2_prev.clicked.connect(lambda: _goto_step(1))
    s2_next.clicked.connect(lambda: _goto_step(3))
    s3_prev.clicked.connect(lambda: _goto_step(2))
    s3_retry.clicked.connect(_start_ota)
    s3_cancel.clicked.connect(_cancel_ota)
    detect_btn.clicked.connect(_detect_device)
    conn_btn.clicked.connect(lambda: bus.navigate_to.emit(1))

    # Initial state
    _on_product_changed(product_combo.currentText())
    _update_conn_status()

    # Listen for SSH connection changes from Remote Dev page
    bus.device_connected.connect(_update_conn_status)
    bus.device_disconnected.connect(_update_conn_status)

    # Retranslate hook
    def retranslate_ui(lang: str):
        title_lbl.setText(t("ota.page.title", lang=lang))
        sub_lbl.setText(t("ota.page.subtitle", lang=lang))
        device_title.setText(t("ota.device.title", lang=lang))
        conn_title.setText(t("ota.connect.title", lang=lang))
        detect_title.setText(t("ota.connect.detect_title", lang=lang))
        dl_title.setText(t("ota.download.title", lang=lang))
        _update_cache_labels()
        pre_title.setText(t("ota.precheck.title", lang=lang))
        exec_title.setText(t("ota.execute.title", lang=lang))

    page.retranslate_ui = retranslate_ui

    return page
