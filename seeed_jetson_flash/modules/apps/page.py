"""应用市场页 UI"""
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from seeed_jetson_flash.core.events import bus


def build_page() -> QWidget:
    """
    返回应用市场页 QWidget。
    TODO: 将 main_window_v2._build_apps_page() 迁移到此处，
          并接入 registry.load_apps() 替换硬编码数据。
    """
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.addWidget(QLabel("📦 应用市场模块 — 开发中，逻辑见 main_window_v2._build_apps_page()"))
    return page
