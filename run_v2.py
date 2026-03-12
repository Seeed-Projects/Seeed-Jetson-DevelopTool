#!/usr/bin/env python3
"""快速启动新版 UI"""
import os
import sys
import logging
import traceback
from pathlib import Path

# ── 日志文件（~/.cache/seeed-jetson/app.log）──────────────────────────────
_log_dir = Path.home() / ".cache" / "seeed-jetson"
_log_dir.mkdir(parents=True, exist_ok=True)
_log_file = _log_dir / "app.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger("seeed")
log.info("=== 启动 seeed-jetson-develop ===")
log.info("日志文件: %s", _log_file)

# ── 全局未捕获异常 → 写日志 + 弹窗 ──────────────────────────────────────────
def _excepthook(exc_type, exc_value, exc_tb):
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log.critical("未捕获异常:\n%s", msg)
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        if QApplication.instance():
            QMessageBox.critical(None, "程序错误",
                f"发生未捕获异常，详情已写入:\n{_log_file}\n\n{msg[-800:]}")
    except Exception:
        pass

sys.excepthook = _excepthook

# 彻底禁用 AT-SPI / DBus 无障碍接口
# QT_ACCESSIBILITY=0  只禁用 Qt 层
# NO_AT_BRIDGE=1      禁止 GTK/Qt 加载 at-spi2-bridge（根本原因）
# DBUS_SESSION_BUS_ADDRESS 保持不动，避免影响其他进程
os.environ["NO_AT_BRIDGE"]    = "1"
os.environ["QT_ACCESSIBILITY"] = "0"

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

# 高 DPI 支持（必须在 QApplication 创建之前设置）
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

from seeed_jetson_develop.gui.main_window_v2 import main
from seeed_jetson_develop.gui.theme import apply_app_theme
apply_app_theme()
main()
