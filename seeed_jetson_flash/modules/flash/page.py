"""烧录页 UI — 从 main_window_v2 迁移，后续在此独立开发"""
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from seeed_jetson_flash.core.events import bus


def build_page(products: dict, product_images: dict) -> QWidget:
    """
    返回烧录页 QWidget。
    products: {product_name: [l4t_version, ...]}
    product_images: {product_name: {name, wiki}}
    """
    # TODO: 将 main_window_v2._build_flash_page() 的逻辑迁移到此处
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.addWidget(QLabel("⚡ 烧录模块 — 开发中，逻辑见 main_window_v2._build_flash_page()"))
    return page
