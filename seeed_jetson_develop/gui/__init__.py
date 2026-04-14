"""GUI module exports."""

# Lazy imports to avoid importing PyQt5 at module import time.
__all__ = ["MainWindow", "main"]


def __getattr__(name):
    if name == "MainWindow":
        from .main_window_v2 import MainWindowV2

        return MainWindowV2
    if name == "main":
        from .main_window_v2 import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
