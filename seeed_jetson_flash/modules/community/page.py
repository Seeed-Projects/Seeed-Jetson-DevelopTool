"""社区页 UI"""
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from seeed_jetson_flash.core.events import bus


def build_page(recovery_guides: dict, products: dict) -> QWidget:
    """
    返回社区页 QWidget。
    TODO: 将 main_window_v2._build_community_page() 迁移到此处。
    """
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.addWidget(QLabel("💬 社区模块 — 开发中，逻辑见 main_window_v2._build_community_page()"))
    return page
