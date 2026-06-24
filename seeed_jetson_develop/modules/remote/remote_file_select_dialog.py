"""远程文件选择对话框：通过 SFTP 浏览 Jetson 文件并选择要下载到 PC 的文件。"""
from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from seeed_jetson_develop.core.runner import SSHRunner
from seeed_jetson_develop.gui.i18n import get_language, t
from seeed_jetson_develop.gui.runtime_i18n import apply_dialog_language as _apply_dlg_lang
from seeed_jetson_develop.gui.theme import (
    C_BG,
    C_CARD_LIGHT,
    C_GREEN,
    C_TEXT,
    C_TEXT2,
    C_TEXT3,
    input_qss,
    make_button as _btn,
    make_label as _lbl,
    pt as _pt,
)


def _tt(key: str, **kwargs) -> str:
    return t(key, lang=get_language(), **kwargs)


class RemoteFileSelectDialog(QDialog):
    """弹出式 SFTP 文件浏览器，返回用户选择的远端文件路径列表。"""

    def __init__(self, runner: SSHRunner, parent: QWidget | None = None):
        super().__init__(parent)
        self._runner = runner
        self._selected_remote_paths: list[str] = []
        self._local_dir: Path | None = None

        self.setWindowTitle(_tt("remote.transfer.download_dialog.title"))
        self.setMinimumSize(_pt(560), _pt(420))
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:none;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addWidget(_lbl(_tt("remote.transfer.download_dialog.header"), 15, C_TEXT, bold=True))
        layout.addWidget(_lbl(_tt("remote.transfer.download_dialog.hint"), 11, C_TEXT2, wrap=True))

        # Path row
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText(_tt("remote.transfer.download_dialog.path_placeholder"))
        self._path_edit.setStyleSheet(input_qss(radius=8, font_size=11))
        self._path_edit.setFixedHeight(_pt(38))
        self._refresh_btn = _btn(_tt("remote.transfer.download_dialog.refresh"), small=True)
        self._refresh_btn.clicked.connect(self._load_files)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(self._refresh_btn)
        layout.addLayout(path_row)

        # File list
        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{ background:{C_CARD_LIGHT}; color:{C_TEXT}; border:none; border-radius:8px; padding:6px; }}"
            f"QListWidget::item {{ padding:6px; border-radius:6px; }}"
            f"QListWidget::item:selected {{ background:{C_GREEN}; color:{C_BG}; }}"
        )
        layout.addWidget(self._list, 1)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)

        # Selection actions
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self._select_all_btn = _btn(_tt("remote.transfer.download_dialog.select_all"), small=True)
        self._select_none_btn = _btn(_tt("remote.transfer.download_dialog.select_none"), small=True)
        self._select_all_btn.clicked.connect(self._select_all)
        self._select_none_btn.clicked.connect(self._select_none)
        action_row.addWidget(self._select_all_btn)
        action_row.addWidget(self._select_none_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        # Status label
        self._status_lbl = QLabel(_tt("remote.transfer.download_dialog.status.ready"))
        self._status_lbl.setStyleSheet(f"color:{C_TEXT3}; font-size:{_pt(11)}px; background:transparent;")
        layout.addWidget(self._status_lbl)

        # Dialog buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = _btn(_tt("common.cancel"), small=True)
        self._download_btn = _btn(_tt("remote.transfer.download_dialog.download"), primary=True, small=True)
        self._cancel_btn.clicked.connect(self.reject)
        self._download_btn.clicked.connect(self._on_download)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._download_btn)
        layout.addLayout(btn_row)

        # Default path
        default_path = f"/home/{runner.username}/"
        self._path_edit.setText(default_path)
        self._load_files()

    def _load_files(self) -> None:
        self._list.clear()
        path = self._path_edit.text().strip() or "."
        client = None
        sftp = None
        try:
            client, sftp = self._runner.open_sftp()
            entries = sftp.listdir_attr(path)
            files = [e for e in entries if not e.filename.startswith(".")]
            files.sort(key=lambda e: (not e.st_mode & 0o40000, e.filename.lower()))

            for entry in files:
                name = entry.filename
                is_dir = bool(entry.st_mode & 0o40000)
                item = QListWidgetItem()
                item.setText(f"{'📁 ' if is_dir else '📄 '}{name}")
                item.setData(Qt.UserRole, name)
                item.setData(Qt.UserRole + 1, is_dir)
                if is_dir:
                    # Folders are navigable but not downloadable/checkable.
                    item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
                    item.setToolTip(_tt("remote.transfer.download_dialog.double_click_enter"))
                    item.setForeground(self.palette().color(self.palette().Disabled, self.palette().Text))
                else:
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                self._list.addItem(item)

            self._status_lbl.setText(_tt("remote.transfer.download_dialog.status.files", count=len(files)))
        except Exception as e:
            self._status_lbl.setText(_tt("remote.transfer.download_dialog.status.error", err=e))
        finally:
            if sftp is not None:
                try:
                    sftp.close()
                except Exception:
                    pass
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        is_dir = item.data(Qt.UserRole + 1)
        if not is_dir:
            return
        name = item.data(Qt.UserRole)
        current = self._path_edit.text().strip() or "."
        new_path = f"{current.rstrip('/')}/{name}"
        self._path_edit.setText(new_path)
        self._load_files()

    def _is_checkable_file(self, item: QListWidgetItem) -> bool:
        return bool(item.flags() & Qt.ItemIsUserCheckable) and not item.data(Qt.UserRole + 1)

    def _select_all(self) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if self._is_checkable_file(item):
                item.setCheckState(Qt.Checked)

    def _select_none(self) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if self._is_checkable_file(item):
                item.setCheckState(Qt.Unchecked)

    def _on_download(self) -> None:
        base_path = self._path_edit.text().strip() or "."
        selected: list[str] = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if not self._is_checkable_file(item):
                continue
            if item.checkState() == Qt.Checked or item.isSelected():
                name = item.data(Qt.UserRole)
                selected.append(f"{base_path.rstrip('/')}/{name}")

        if not selected:
            QMessageBox.warning(
                self,
                _tt("common.notice"),
                _tt("remote.transfer.download_dialog.no_selection"),
            )
            return

        local_dir = QFileDialog.getExistingDirectory(
            self,
            _tt("remote.transfer.download_dialog.choose_local_dir"),
            str(Path.home()),
        )
        if not local_dir:
            return

        self._selected_remote_paths = selected
        self._local_dir = Path(local_dir)
        self.accept()

    def selected_paths(self) -> list[str]:
        return self._selected_remote_paths

    def local_dir(self) -> Path | None:
        return self._local_dir

    def exec_(self) -> int:
        result = super().exec_()
        _apply_dlg_lang(self, self.parentWidget())
        return result
