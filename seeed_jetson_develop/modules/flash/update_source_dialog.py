"""Dialog for comparing and selectively updating BSP download sources."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)

from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD_LIGHT, C_TEXT, C_TEXT2, C_TEXT3,
    C_GREEN, C_ORANGE, C_BLUE, pt,
)
from seeed_jetson_develop.gui.i18n import get_language, t


_STATUS_LABELS = {
    "new": {"zh": "新增", "en": "New"},
    "modified": {"zh": "有变更", "en": "Modified"},
    "identical": {"zh": "无变化", "en": "Identical"},
    "local_only": {"zh": "本地独有", "en": "Local Only"},
}

_FIELD_LABELS = {
    "mainlink": "mainlink",
    "mirrorlink": "mirrorlink",
    "filename": "filename",
    "foldername": "foldername",
    "sha256": "sha256",
}


def _status_text(status: str) -> str:
    lang = get_language()
    return _STATUS_LABELS.get(status, {}).get(lang, _STATUS_LABELS.get(status, {}).get("en", status))


def _fields_text(fields: List[str]) -> str:
    return ", ".join(_FIELD_LABELS.get(f, f) for f in fields)


class UpdateSourceDialog(QDialog):
    """Dialog that lets the user compare local vs remote BSP data and pick updates."""

    def __init__(self, diffs: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self._diffs = diffs
        self._selected_keys: List[Tuple[str, str]] = []
        self._setup_ui()

    def _setup_ui(self):
        lang = get_language()
        self.setWindowTitle("Update Download Source")
        self.setMinimumSize(780, 520)
        self.setStyleSheet(f"background:{C_BG};")

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 20, 20, 20)

        # Header
        header_lbl = QLabel(title)
        header_lbl.setStyleSheet(
            f"color:{C_TEXT}; font-size:{pt(15)}px; font-weight:700;"
        )
        root.addWidget(header_lbl)

        hint = "Check the items you want to replace with remote data."
        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:{pt(11)}px;")
        hint_lbl.setWordWrap(True)
        root.addWidget(hint_lbl)

        # Stats row
        new_count = sum(1 for d in self._diffs if d["status"] == "new")
        mod_count = sum(1 for d in self._diffs if d["status"] == "modified")
        local_count = sum(1 for d in self._diffs if d["status"] == "local_only")
        stats_text = f"New: {new_count}   Modified: {mod_count}   Local only: {local_count}"
        stats_lbl = QLabel(stats_text)
        stats_lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:{pt(11)}px;")
        root.addWidget(stats_lbl)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Select", "Product", "L4T", "Status", "Changed Fields",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {C_BG_DEEP};
                border: none;
                border-radius: 8px;
                gridline-color: rgba(255,255,255,0.05);
                color: {C_TEXT2};
                font-size: {pt(12)}px;
            }}
            QTableWidget::item {{
                padding: 8px 10px;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }}
            QTableWidget::item:selected {{
                background: rgba(255,255,255,0.06);
                color: {C_TEXT};
            }}
            QHeaderView::section {{
                background: {C_BG_DEEP};
                color: {C_TEXT};
                font-size: {pt(11)}px;
                font-weight: 600;
                padding: 8px 10px;
                border: none;
                border-bottom: 2px solid rgba(255,255,255,0.08);
            }}
        """)

        self._populate_table()
        root.addWidget(self.table, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.select_all_btn = QPushButton("Select All")
        self.select_none_btn = QPushButton("Select None")
        for btn in (self.select_all_btn, self.select_none_btn):
            btn.setStyleSheet(
                f"QPushButton {{ background: {C_CARD_LIGHT}; color: {C_TEXT2}; "
                f"border: none; border-radius: 6px; padding: 6px 14px; "
                f"font-size: {pt(11)}px; }}"
                f"QPushButton:hover {{ background: rgba(255,255,255,0.10); color: {C_TEXT}; }}"
            )

        self.select_all_btn.clicked.connect(self._select_all)
        self.select_none_btn.clicked.connect(self._select_none)
        btn_row.addWidget(self.select_all_btn)
        btn_row.addWidget(self.select_none_btn)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {C_CARD_LIGHT}; color: {C_TEXT2}; "
            f"border: none; border-radius: 6px; padding: 6px 18px; "
            f"font-size: {pt(12)}px; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.10); color: {C_TEXT}; }}"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.ok_btn = QPushButton("Apply Selected")
        self.ok_btn.setStyleSheet(
            f"QPushButton {{ background: {C_BLUE}; color: #FFFFFF; "
            f"border: none; border-radius: 6px; padding: 6px 18px; "
            f"font-size: {pt(12)}px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: #3D8EF0; }}"
            f"QPushButton:pressed {{ background: #1A6ACC; }}"
            f"QPushButton:disabled {{ background: #1A232E; color: #5A6B7A; }}"
        )
        self.ok_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(self.ok_btn)

        root.addLayout(btn_row)

    def _populate_table(self):
        visible_diffs = [d for d in self._diffs if d["status"] != "identical"]
        self.table.setRowCount(len(visible_diffs))

        status_colors = {
            "new": C_GREEN,
            "modified": C_ORANGE,
            "local_only": C_TEXT3,
        }

        for row, diff in enumerate(visible_diffs):
            status = diff["status"]
            product, l4t = diff["key"]

            # Select checkbox
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            default_checked = status in ("new", "modified")
            chk.setCheckState(Qt.Checked if default_checked else Qt.Unchecked)
            self.table.setItem(row, 0, chk)

            # Product
            prod_item = QTableWidgetItem(product)
            prod_item.setData(Qt.UserRole, diff["key"])
            self.table.setItem(row, 1, prod_item)

            # L4T
            l4t_item = QTableWidgetItem(l4t)
            self.table.setItem(row, 2, l4t_item)

            # Status
            status_item = QTableWidgetItem(_status_text(status))
            status_item.setForeground(Qt.GlobalColor)  # placeholder
            # We can't easily set color on QTableWidgetItem foreground with hex strings,
            # so we use stylesheet on the cell via delegate or just accept default.
            self.table.setItem(row, 3, status_item)

            # Changed fields
            changes = _fields_text(diff.get("fields_changed", []))
            if status == "local_only":
                changes = "-"
            self.table.setItem(row, 4, QTableWidgetItem(changes))

            # Store diff reference
            for col in range(5):
                item = self.table.item(row, col)
                if item:
                    item.setData(Qt.UserRole + 1, diff)

    def _select_all(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked)

    def _select_none(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Unchecked)

    def _on_confirm(self):
        self._selected_keys = []
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            if chk and chk.checkState() == Qt.Checked:
                key = self.table.item(row, 1).data(Qt.UserRole)
                if key:
                    self._selected_keys.append(key)
        self.accept()

    def selected_keys(self) -> List[Tuple[str, str]]:
        return self._selected_keys
