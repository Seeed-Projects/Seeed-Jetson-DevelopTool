"""Application icon helpers."""
from __future__ import annotations

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget

from ..resources import resolve_runtime_path


APP_ICON_PNG = "assets/seeed-jetson-develop-icon.png"
APP_ICON_ICO = "assets/seeed-jetson-develop-icon.ico"


def app_icon() -> QIcon:
    """Return the shared app icon for windows, launchers, and shortcuts."""
    icon = QIcon()
    for rel in (APP_ICON_PNG, APP_ICON_ICO):
        path = resolve_runtime_path(rel)
        if path and path.exists():
            icon.addFile(str(path))
    return icon


def apply_app_icon(widget: QWidget | None = None) -> QIcon:
    """Apply the shared app icon to QApplication and optionally a widget."""
    icon = app_icon()
    if icon.isNull():
        return icon
    app = QApplication.instance()
    if app is not None:
        app.setWindowIcon(icon)
    if widget is not None:
        widget.setWindowIcon(icon)
    return icon
