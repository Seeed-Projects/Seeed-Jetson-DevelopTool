"""Skills 页 UI"""
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from seeed_jetson_flash.core.events import bus


def build_page() -> QWidget:
    """
    返回 Skills 页 QWidget。
    TODO: 将 main_window_v2._build_skills_page() 迁移到此处，
          并接入 engine.load_skills() + engine.run_skill()。
    """
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.addWidget(QLabel("🤖 Skills 模块 — 开发中，逻辑见 main_window_v2._build_skills_page()"))
    return page
