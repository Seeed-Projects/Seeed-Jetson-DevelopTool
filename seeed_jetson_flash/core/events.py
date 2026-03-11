"""全局事件总线 — 模块间通信，避免直接 import 耦合"""
from PyQt5.QtCore import QObject, pyqtSignal


class EventBus(QObject):
    # devices 模块
    device_connected    = pyqtSignal(dict)   # payload: {ip, name, model}
    device_disconnected = pyqtSignal(str)    # payload: ip
    diagnostics_done    = pyqtSignal(dict)   # payload: {item: status}

    # flash 模块
    flash_started       = pyqtSignal(str, str)  # product, l4t
    flash_completed     = pyqtSignal(bool, str)  # success, message

    # skills 模块
    skill_run_requested = pyqtSignal(str)    # skill_id
    skill_completed     = pyqtSignal(str, bool, str)  # skill_id, success, log

    # apps 模块
    app_install_requested = pyqtSignal(str)  # app_id
    app_installed         = pyqtSignal(str, bool)  # app_id, success

    # 导航
    navigate_to         = pyqtSignal(int)    # page index


# 全局单例，所有模块 from seeed_jetson_flash.core import bus
bus = EventBus()
