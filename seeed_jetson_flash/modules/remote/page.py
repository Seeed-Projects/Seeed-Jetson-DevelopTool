"""远程开发页 UI"""
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from seeed_jetson_flash.core.events import bus


def build_page() -> QWidget:
    """
    返回远程开发页 QWidget。
    TODO: 将 main_window_v2._build_remote_page() 迁移到此处，
          并接入 connector.check_ssh() 实现真实连接检测。
    """
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.addWidget(QLabel("💻 远程开发模块 — 开发中，逻辑见 main_window_v2._build_remote_page()"))
    return page
