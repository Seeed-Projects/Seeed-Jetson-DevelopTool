"""设备管理页 UI"""
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from seeed_jetson_flash.core.events import bus


def build_page() -> QWidget:
    """
    返回设备管理页 QWidget。
    TODO: 将 main_window_v2._build_devices_page() 迁移到此处，
          并接入 diagnostics.run_all() 实现真实体检。
    """
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.addWidget(QLabel("🖥 设备管理模块 — 开发中，逻辑见 main_window_v2._build_devices_page()"))
    return page
