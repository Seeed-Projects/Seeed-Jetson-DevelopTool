"""页面基类 - 所有页面的统一基础

提供统一的头部、滚动区域、内容容器，适用于所有类型的页面。
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea
from seeed_jetson_develop.gui.i18n_binding import I18nBinding
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_TEXT, C_TEXT3,
    pt as _pt, make_label as _lbl,
)


class PageBase(QWidget):
    """所有页面的基类

    提供统一的页面结构：
    - 固定头部（标题 + 副标题 + 右侧可选内容）
    - 滚动区域
    - 内容容器（供子类添加内容）
    """

    def __init__(self, title: str = "", subtitle: str = ""):
        super().__init__()
        self.setStyleSheet(f"background:{C_BG};")
        self._title_label = None
        self._subtitle_label = None
        self.i18n = I18nBinding()

        # 设置 size policy 让页面能够扩展填充空间
        from PyQt5.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 头部
        self._header = self._build_header(title, subtitle)
        root.addWidget(self._header)

        # 滚动区域
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background:transparent; border:none;")

        self._inner = QWidget()
        self._inner.setStyleSheet(f"background:{C_BG};")
        self._content_layout = QVBoxLayout(self._inner)
        self._content_layout.setContentsMargins(_pt(28), _pt(24), _pt(28), _pt(24))
        self._content_layout.setSpacing(_pt(20))

        self._scroll.setWidget(self._inner)
        root.addWidget(self._scroll, 1)

    def _build_header(self, title: str, subtitle: str) -> QWidget:
        """构建页面头部"""
        header = QWidget()
        header.setStyleSheet(f"background:{C_BG_DEEP};")
        header.setFixedHeight(_pt(64))

        self._header_layout = QHBoxLayout(header)
        self._header_layout.setContentsMargins(_pt(28), _pt(10), _pt(28), _pt(10))
        self._header_layout.setSpacing(0)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        text_col.setContentsMargins(0, 0, 0, 0)
        if title:
            self._title_label = _lbl(title, 18, C_TEXT, bold=True)
            text_col.addWidget(self._title_label)
        if subtitle:
            self._subtitle_label = _lbl(subtitle, 12, C_TEXT3)
            text_col.addWidget(self._subtitle_label)
        self._header_layout.addLayout(text_col)

        self._header_layout.addStretch()
        return header

    def add_header_widget(self, widget: QWidget):
        """在头部右侧添加 widget（按钮等），右对齐"""
        self._header_layout.addSpacing(_pt(8))
        self._header_layout.addWidget(widget)

    def get_content_layout(self) -> QVBoxLayout:
        """获取内容区域的 layout，供子类添加内容"""
        return self._content_layout

    def get_scroll_area(self) -> QScrollArea:
        """获取滚动区域，供子类自定义"""
        return self._scroll

    def set_header_text(self, title: str = "", subtitle: str = ""):
        """Update page header title/subtitle text."""
        if self._title_label is not None:
            self._title_label.setText(title or "")
            self._title_label.setVisible(bool(title))
        if self._subtitle_label is not None:
            self._subtitle_label.setText(subtitle or "")
            self._subtitle_label.setVisible(bool(subtitle))

    def register_i18n(self, binding: I18nBinding):
        """Merge external i18n binding registrations into this page."""
        self.i18n.extend(binding)

    def retranslate_ui(self, lang: str | None = None):
        """Default page i18n refresh entry."""
        self.i18n.apply(lang)
