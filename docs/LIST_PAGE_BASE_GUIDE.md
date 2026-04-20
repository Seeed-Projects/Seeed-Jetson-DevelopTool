# ListPageBase 使用指南

## 适用场景

ListPageBase 适合以下类型的页面：

1. **应用市场** - 有分类、搜索、动态列表
2. **技能中心** - 有分类、搜索、动态列表
3. **设备列表** - 有筛选、搜索
4. **日志查看** - 有筛选、搜索

## 不适用场景

- **静态卡片页面**（如 community 的快速链接）- 无需筛选和搜索
- **向导式页面**（如 flash 的多步骤流程）- 不是列表结构
- **表单页面**（如设置页）- 不是列表结构

## 如何让 ListPageBase 更通用

### 方案 1: 禁用筛选功能

如果页面不需要分类筛选，返回单一分类：

```python
def get_categories(self) -> list[str]:
    return ["全部"]  # 只有一个分类，标签行会很简洁
```

### 方案 2: 覆盖 UI 构建

如果需要自定义布局，覆盖 `_init_ui()`：

```python
def _init_ui(self):
    # 调用父类构建基础结构
    super()._init_ui()

    # 在列表上方添加自定义内容
    custom_widget = QWidget()
    # ... 自定义内容
    self.list_outer_layout.insertWidget(0, custom_widget)
```

### 方案 3: 网格布局而非列表

覆盖 `_rebuild_list()` 使用网格：

```python
def _rebuild_list(self):
    self.batch_generation += 1
    current_gen = self.batch_generation
    self._clear_list()

    filtered = [item for item in self.items_data if self.filter_item(item)]

    # 使用网格布局
    grid_widget = QWidget()
    grid_layout = QGridLayout(grid_widget)

    for i, item in enumerate(filtered):
        widget = self.build_item_widget(item)
        grid_layout.addWidget(widget, i // 3, i % 3)

    self.list_outer_layout.addWidget(grid_widget)
```

## 总结

ListPageBase 是为**动态列表 + 筛选搜索**场景设计的。对于静态内容页面（如 community），直接用传统方式更简单。
