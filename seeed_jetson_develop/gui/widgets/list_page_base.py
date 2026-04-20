"""列表页面基类

提供筛选、标签页、批量渲染等通用功能，用于 apps/skills 等列表页面。
继承自 PageBase，复用统一的页面结构。
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer
from seeed_jetson_develop.gui.widgets.page_base import PageBase
from seeed_jetson_develop.gui.theme import (
    C_TEXT, C_TEXT3, pt as _pt, make_label as _lbl,
    make_tab_button, make_input_field
)
from seeed_jetson_develop.gui.i18n import t


class ListPageBase(PageBase):
    """列表页面基类

    继承 PageBase，添加筛选、搜索、批量渲染功能。
    子类需要实现：
    - load_data() -> list: 加载数据源
    - get_categories() -> list[str]: 返回分类列表
    - build_item_widget(item: dict) -> QWidget: 构建单个列表项
    - filter_item(item: dict) -> bool: 判断 item 是否匹配筛选条件
    """

    def __init__(self):
        # 先初始化状态
        self.filter_state = {"category": "", "search": ""}
        self.batch_generation = 0
        self.items_data = []
        self.tab_buttons = {}
        self.search_input = None

        # 调用父类初始化（构建基础结构）
        super().__init__(
            title=self.get_page_title(),
            subtitle=self.get_page_subtitle()
        )

        # 构建筛选行和列表容器
        self._build_filter_and_list()

        # 加载数据并渲染
        self._load_and_render()

    # ========== 抽象方法（子类必须实现） ==========

    def load_data(self) -> list:
        """加载数据源，返回 item 列表"""
        raise NotImplementedError("子类必须实现 load_data()")

    def get_categories(self) -> list[str]:
        """返回分类列表，第一项通常为'全部'"""
        raise NotImplementedError("子类必须实现 get_categories()")

    def build_item_widget(self, item: dict) -> QWidget:
        """构建单个列表项的 widget"""
        raise NotImplementedError("子类必须实现 build_item_widget()")

    def filter_item(self, item: dict) -> bool:
        """判断 item 是否匹配当前筛选条件"""
        raise NotImplementedError("子类必须实现 filter_item()")

    # ========== 可选方法（子类可覆盖） ==========

    def get_page_title(self) -> str:
        """页面标题"""
        return "列表"

    def get_page_subtitle(self) -> str:
        """页面副标题"""
        return ""

    def get_batch_size(self) -> int:
        """批量渲染的批次大小"""
        return 6

    def on_category_changed(self, category: str):
        """分类切换回调（子类可覆盖以添加额外逻辑）"""
        pass

    def on_search_changed(self, text: str):
        """搜索输入回调（子类可覆盖以添加额外逻辑）"""
        pass

    def format_category_label(self, category: str) -> str:
        """Map internal category key to displayed text."""
        return category

    # ========== 内部实现（子类无需关心） ==========

    def _build_filter_and_list(self):
        """构建筛选行和列表容器"""
        content_layout = self.get_content_layout()

        # 1. 筛选行（标签页 + 搜索框）
        filter_row = self._build_filter_row()
        content_layout.addWidget(filter_row)

        # 2. 列表容器
        self.list_container = QWidget()
        self.list_outer_layout = QVBoxLayout(self.list_container)
        self.list_outer_layout.setContentsMargins(0, 0, 0, 0)
        self.list_outer_layout.setSpacing(_pt(12))
        content_layout.addWidget(self.list_container, 1)  # stretch factor=1 让列表容器占据剩余空间

    def _build_filter_row(self) -> QWidget:
        """构建筛选行（标签页 + 搜索框）"""
        from PyQt5.QtWidgets import QScrollArea
        from PyQt5.QtCore import Qt

        container = QWidget()
        container_lay = QHBoxLayout(container)
        container_lay.setContentsMargins(0, 0, 0, 0)
        container_lay.setSpacing(_pt(12))

        # 左侧：可滚动的标签页区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(_pt(48))
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        tabs_widget = QWidget()
        tabs_lay = QHBoxLayout(tabs_widget)
        tabs_lay.setContentsMargins(0, 0, 0, 0)
        tabs_lay.setSpacing(_pt(12))

        # 标签页按钮
        categories = self.get_categories()
        # 若初始分类未设置，则取第一项
        if not self.filter_state["category"] and categories:
            self.filter_state["category"] = categories[0]
        for cat in categories:
            btn = make_tab_button(self.format_category_label(cat), active=(cat == self.filter_state["category"]))
            btn.clicked.connect(lambda checked, c=cat: self._on_category_clicked(c))
            btn.setProperty("category_key", cat)
            self.tab_buttons[cat] = btn
            tabs_lay.addWidget(btn)

        tabs_lay.addStretch()
        scroll.setWidget(tabs_widget)
        container_lay.addWidget(scroll, 1)

        # 右侧：搜索框（固定位置）
        self.search_input = make_input_field(t("common.search_placeholder"))
        self.search_input.setFixedWidth(_pt(200))
        self.search_input.textChanged.connect(self._on_search_input_changed)
        container_lay.addWidget(self.search_input)

        return container

    def _load_and_render(self):
        """加载数据并首次渲染"""
        self.items_data = self.load_data()
        self._rebuild_list()

    def _on_category_clicked(self, category: str):
        """分类标签点击处理"""
        self.filter_state["category"] = category

        # 更新按钮样式
        for cat, btn in self.tab_buttons.items():
            btn.setStyleSheet(make_tab_button(self.format_category_label(cat), active=(cat == category)).styleSheet())

        # 回调
        self.on_category_changed(category)

        # 重新渲染
        self._rebuild_list()

    def _on_search_input_changed(self, text: str):
        """搜索框输入处理"""
        self.filter_state["search"] = text
        self.on_search_changed(text)
        self._rebuild_list()

    def _rebuild_list(self):
        """重新筛选并批量渲染列表"""
        # 增加 generation，取消旧的渲染任务
        self.batch_generation += 1
        current_gen = self.batch_generation

        # 清空现有列表
        self._clear_list()

        # 筛选数据
        filtered = [item for item in self.items_data if self.filter_item(item)]

        if not filtered:
            # 无数据提示
            empty_label = _lbl(t("common.no_data"), 14, C_TEXT3)
            empty_label.setAlignment(Qt.AlignCenter)
            self.list_outer_layout.addWidget(empty_label)
            self.list_outer_layout.addStretch()
            return

        # 批量渲染：先填充 container，完成后一次性挂载，避免布局抖动
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(_pt(12))
        container.setVisible(False)  # 填充完成前保持隐藏

        batch_size = self.get_batch_size()
        idx_ref = [0]

        def _add_batch():
            if self.batch_generation != current_gen:
                container.deleteLater()
                return  # 已被新的渲染任务取消

            for _ in range(batch_size):
                if idx_ref[0] >= len(filtered):
                    break
                item_widget = self.build_item_widget(filtered[idx_ref[0]])
                container_layout.addWidget(item_widget)
                idx_ref[0] += 1

            if idx_ref[0] < len(filtered):
                QTimer.singleShot(10, _add_batch)
            else:
                container_layout.addStretch()
                # 全部填充完毕，一次性挂载并显示
                self.list_outer_layout.addWidget(container, 1)
                container.setVisible(True)

        QTimer.singleShot(0, _add_batch)

    def _clear_list(self):
        """清空列表容器"""
        while self.list_outer_layout.count():
            item = self.list_outer_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def retranslate_ui(self, _lang_code: str | None = None):
        self.set_header_text(self.get_page_title(), self.get_page_subtitle())
        if self.search_input is not None:
            self.search_input.setPlaceholderText(t("common.search_placeholder"))
        for cat, btn in self.tab_buttons.items():
            btn.setText(self.format_category_label(cat))
            btn.setStyleSheet(
                make_tab_button(
                    self.format_category_label(cat),
                    active=(cat == self.filter_state["category"]),
                ).styleSheet()
            )
        self._rebuild_list()



