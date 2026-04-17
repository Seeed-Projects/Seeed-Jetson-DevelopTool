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
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
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

# ── X display 健康检测 + 自动 Xvfb fallback（仅 Linux）─────────────────────
def _ensure_display():
    if sys.platform == "win32":
        return  # Windows 不需要处理

    import socket
    import subprocess
    import time

    def _x_client_count(display: str) -> int:
        """通过 ss 统计当前 display socket 的连接数，失败返回 0。"""
        num = display.lstrip(":").split(".")[0]
        sock_path = f"/tmp/.X11-unix/X{num}"
        try:
            out = subprocess.check_output(
                ["ss", "-xp"], stderr=subprocess.DEVNULL, text=True
            )
            return sum(1 for line in out.splitlines() if sock_path in line)
        except Exception:
            return 0

    def _can_connect(display: str) -> bool:
        num = display.lstrip(":").split(".")[0]
        sock_path = f"/tmp/.X11-unix/X{num}"
        if not os.path.exists(sock_path):
            return False
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(sock_path)
            s.close()
            return True
        except OSError:
            return False

    def _start_xvfb(display: str) -> bool:
        """尝试启动 Xvfb，成功返回 True。"""
        try:
            subprocess.Popen(
                ["Xvfb", display, "-screen", "0", "1920x1080x24", "-maxclients", "512"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(20):
                time.sleep(0.3)
                if _can_connect(display):
                    return True
            return False
        except FileNotFoundError:
            return False  # Xvfb 未安装

    display = os.environ.get("DISPLAY", "")

    # 没有 DISPLAY，直接尝试 Xvfb :10
    if not display:
        log.warning("未设置 DISPLAY，尝试启动 Xvfb :10 作为 fallback")
        if _start_xvfb(":10"):
            os.environ["DISPLAY"] = ":10"
            log.info("Xvfb :10 启动成功，使用 DISPLAY=:10")
            return
        log.error("Xvfb 启动失败且无可用 DISPLAY，请在图形桌面环境下运行")
        sys.exit(1)

    # 有 DISPLAY，检测连接数是否接近上限（>= 240 视为危险）
    count = _x_client_count(display)
    log.debug("X display %s 当前连接数: %d", display, count)

    if count >= 240 or not _can_connect(display):
        log.warning(
            "X display %s 连接数已满或不可用（count=%d），尝试启动 Xvfb fallback",
            display, count,
        )
        # 找一个空闲的 display 编号
        for n in range(10, 30):
            fb_display = f":{n}"
            if not os.path.exists(f"/tmp/.X11-unix/X{n}"):
                if _start_xvfb(fb_display):
                    os.environ["DISPLAY"] = fb_display
                    log.info("Xvfb %s 启动成功，使用 DISPLAY=%s", fb_display, fb_display)
                    return
                break
        log.error(
            "X display %s 不可用且 Xvfb fallback 失败。\n"
            "请注销重新登录桌面以释放 X 连接，或安装 Xvfb: sudo apt install xvfb",
            display,
        )
        sys.exit(1)

_ensure_display()

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

# 高 DPI 支持（必须在 QApplication 创建之前设置）
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

from seeed_jetson_develop.gui.main_window_v2 import main
from seeed_jetson_develop.gui.theme import apply_app_theme
apply_app_theme()
main()
