"""全局事件总线 — 模块间通信，避免直接 import 耦合"""
from qtpy.QtCore import QObject, Signal


class EventBus(QObject):
    # devices 模块
    device_connected    = Signal(dict)   # payload: {ip, name, model}
    device_disconnected = Signal(str)    # payload: ip
    diagnostics_done    = Signal(dict)   # payload: {item: status}

    # flash 模块
    flash_started       = Signal(str, str)  # product, l4t
    flash_completed     = Signal(bool, str)  # success, message

    # skills 模块
    skill_run_requested = Signal(str)    # skill_id
    skill_completed     = Signal(str, bool, str)  # skill_id, success, log

    # apps 模块
    app_install_requested = Signal(str)  # app_id
    app_installed         = Signal(str, bool)  # app_id, success

    # 导航
    navigate_to         = Signal(int)    # page index

    # 状态栏
    status_busy         = Signal(str)    # message
    status_idle         = Signal(str)    # message


# 全局单例，所有模块 from seeed_jetson_develop.core import bus
bus = EventBus()
