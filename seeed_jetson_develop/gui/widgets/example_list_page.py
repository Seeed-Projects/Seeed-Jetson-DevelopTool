"""ListPageBase 使用示例

演示如何使用 ListPageBase 创建一个简单的列表页面。
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from seeed_jetson_develop.gui.widgets.list_page_base import ListPageBase
from seeed_jetson_develop.gui.theme import make_list_card, make_label as _lbl, C_TEXT, pt as _pt


class ExampleListPage(ListPageBase):
    """示例列表页面"""

    def load_data(self) -> list:
        """加载示例数据"""
        return [
            {"id": 1, "name": "示例应用 1", "category": "工具", "desc": "这是一个示例应用"},
            {"id": 2, "name": "示例应用 2", "category": "开发", "desc": "另一个示例"},
            {"id": 3, "name": "测试应用", "category": "工具", "desc": "用于测试的应用"},
        ]

    def get_categories(self) -> list[str]:
        """返回分类列表"""
        return ["全部", "工具", "开发"]

    def build_item_widget(self, item: dict) -> QWidget:
        """构建单个列表项"""
        card = make_list_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(_pt(16), _pt(12), _pt(16), _pt(12))

        layout.addWidget(_lbl(item["name"], 14, C_TEXT, bold=True))
        layout.addWidget(_lbl(item["desc"], 12))

        return card

    def filter_item(self, item: dict) -> bool:
        """筛选逻辑"""
        # 分类筛选
        cat = self.filter_state["category"]
        if cat != "全部" and item.get("category") != cat:
            return False

        # 搜索筛选
        kw = self.filter_state["search"].lower()
        if kw and kw not in item["name"].lower() and kw not in item.get("desc", "").lower():
            return False

        return True

    def get_page_title(self) -> str:
        return "示例列表"

    def get_page_subtitle(self) -> str:
        return "演示 ListPageBase 的使用"


def build_example_page() -> QWidget:
    """构建示例页面"""
    return ExampleListPage()
