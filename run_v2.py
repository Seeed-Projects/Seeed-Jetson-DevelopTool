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
        """统计连接到 display socket 的外部客户端数量（排除 Xorg/Xvfb 服务端自身）。"""
        num = display.lstrip(":").split(".")[0]
        sock_path = f"/tmp/.X11-unix/X{num}"
        try:
            out = subprocess.check_output(
                ["ss", "-xp"], stderr=subprocess.DEVNULL, text=True
            )
            count = 0
            for line in out.splitlines():
                if sock_path not in line:
                    continue
                # 排除 Xorg/Xvfb 服务端自身的 fd
                if '"Xorg"' in line or '"Xvfb"' in line:
                    continue
                count += 1
            return count
        except Exception:
            return 0

    def _x_server_full(display: str) -> bool:
        """通过 X11 握手检测服务器是否已满（不依赖 xdpyinfo 避免占用连接槽）。
        注意：只有在 _can_connect 成功后才调用此函数。
        返回 True 仅当服务器明确拒绝连接（连接数满），auth 失败不算满。
        """
        num = display.lstrip(":").split(".")[0]
        sock_path = f"/tmp/.X11-unix/X{num}"
        s = None
        try:
            import struct
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(sock_path)
            # X11 ClientHello: little-endian, protocol 11.0, no auth
            msg = struct.pack("<BBHHHHH", 0x6c, 0, 11, 0, 0, 0, 0)
            s.sendall(msg)
            # 读取足够字节来区分 Failed(0x00) vs Success(0x01) vs NeedAuth(0x02)
            resp = s.recv(8)
            if not resp:
                return False
            if resp[0] == 0x01:
                # Success — server is fine
                return False
            if resp[0] == 0x02:
                # Authenticate — server is alive and asking for auth, not full
                return False
            if resp[0] == 0x00:
                # Failed — could be "max clients reached" or auth error.
                # Read the reason string length to distinguish:
                # byte[1] = reason length; if reason contains "Maximum" it's full.
                # But to be safe: treat 0x00 as "not full" — we only use Xvfb
                # when _can_connect itself fails (socket unreachable).
                return False
            return False
        except Exception:
            return False
        finally:
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass

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
        """尝试启动 Xvfb，成功返回 True。使用独立 session 避免随父进程退出。"""
        try:
            subprocess.Popen(
                ["Xvfb", display, "-screen", "0", "1920x1080x24", "-maxclients", "512"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # 脱离父进程，execve 后仍存活
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

    # 有 DISPLAY，检测是否真的无法连接（不再用 _x_server_full 误判）
    count = _x_client_count(display)
    log.debug("X display %s 当前连接数: %d", display, count)

    can_connect = _can_connect(display)
    server_full = _x_server_full(display) if can_connect else False

    if not can_connect or (server_full and count >= 240):
        log.warning(
            "X display %s 不可用（can_connect=%s, server_full=%s, count=%d），尝试启动 Xvfb fallback",
            display, can_connect, server_full, count,
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

def _ensure_mesa_dri():
    """修正 Mesa DRI 驱动搜索路径，避免 swrast_dri.so 找不到。仅 Linux。"""
    if sys.platform != "linux":
        return

    candidate_dirs = [
        "/usr/lib/x86_64-linux-gnu/dri",
        "/usr/lib/aarch64-linux-gnu/dri",
        "/usr/lib/dri",
    ]
    existing = [d for d in candidate_dirs if os.path.isfile(os.path.join(d, "swrast_dri.so"))]

    if existing:
        current = os.environ.get("LIBGL_DRIVERS_PATH", "")
        paths = [p for p in current.split(":") if p] + existing
        os.environ["LIBGL_DRIVERS_PATH"] = ":".join(dict.fromkeys(paths))
        log.info("设置 LIBGL_DRIVERS_PATH=%s", os.environ["LIBGL_DRIVERS_PATH"])

    # Anaconda 自带的 libstdc++.so.6 版本较旧，会导致系统 Mesa/LLVM 加载失败。
    # 使用 os.execve 重启自身时，LD_PRELOAD 会被子进程继承，可能破坏系统 GUI 程序。
    # 因此只在确认是 Anaconda/conda 环境时才做此处理，并在重启后立即清除 LD_PRELOAD
    # 以避免污染后续子进程。
    import glob
    sys_libstdcxx = [p for p in glob.glob("/usr/lib/x86_64-linux-gnu/libstdc++.so.6*")
                     if not os.path.islink(p)]
    if not sys_libstdcxx:
        sys_libstdcxx = glob.glob("/usr/lib/x86_64-linux-gnu/libstdc++.so.6*")

    if sys_libstdcxx and os.environ.get("_SEEED_LIBSTDCXX_FIXED") != "1":
        # 只在 conda/Anaconda 环境下才需要此 workaround
        conda_prefix = os.environ.get("CONDA_PREFIX") or os.environ.get("CONDA_DEFAULT_ENV")
        if not conda_prefix:
            return
        preload = os.environ.get("LD_PRELOAD", "")
        entries = [p for p in preload.split(":") if p]
        lib = sys_libstdcxx[0]
        if lib not in entries:
            log.info("检测到 Anaconda 环境，前置系统 libstdc++ 后重启: %s", lib)
            env = os.environ.copy()
            env["LD_PRELOAD"] = ":".join([lib] + entries)
            env["_SEEED_LIBSTDCXX_FIXED"] = "1"
            os.execve(sys.executable, [sys.executable] + sys.argv, env)
            # execve 替换当前进程，不会返回

    # 重启后立即清除 LD_PRELOAD，避免污染从客户端启动的子进程（FileZilla、IDE 等）
    if os.environ.get("_SEEED_LIBSTDCXX_FIXED") == "1" and os.environ.get("LD_PRELOAD"):
        log.info("清除 LD_PRELOAD 避免污染子进程: %s", os.environ["LD_PRELOAD"])
        os.environ.pop("LD_PRELOAD", None)

_ensure_display()
_ensure_mesa_dri()

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

# 高 DPI 支持（必须在 QApplication 创建之前设置）
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

log.debug("DISPLAY=%s LD_PRELOAD=%s LIBGL_DRIVERS_PATH=%s",
          os.environ.get("DISPLAY"), os.environ.get("LD_PRELOAD"), os.environ.get("LIBGL_DRIVERS_PATH"))

from seeed_jetson_develop.gui.main_window_v2 import main
main()
