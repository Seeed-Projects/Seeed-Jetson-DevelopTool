# 页面模块重构计划：提取基类和 UI 工厂函数

## Context

当前项目的页面模块存在严重的代码重复和维护困难：

- **巨型函数**：5 个页面模块（apps, skills, community, devices, flash）都使用单一 `build_page()` 函数，代码量 783-1366 行，嵌套闭包深度 8-10 层
- **高度重复**：apps/skills/community 三个模块共享 60%+ 相同代码（筛选、标签页、批量渲染、列表卡片）
- **状态管理混乱**：使用闭包捕获的可变容器（`_filter`, `_state`, `_batch_gen`）而非实例变量，难以测试和重构
- **样式重复**：每个页面都重复定义相似的 tab/button/card 样式，缺少统一的 UI 工厂函数

**目标**：通过提取基类和补充 UI 工厂函数，减少重复代码，提升可维护性，同时保持向后兼容。

## 重构策略：分三阶段渐进式重构

### Phase 1: 补充 theme.py 中缺失的 UI 工厂函数

**目标**：为重复的 UI 模式提供统一的工厂函数

**新增函数**：

1. `make_tab_button(text: str, active: bool = False) -> QPushButton`
   - 用于筛选/分类标签按钮
   - 自动处理 active/inactive 状态样式

2. `make_list_card() -> QWidget`
   - 用于列表项的卡片容器
   - 统一圆角、背景色、边距

3. `make_input_field(placeholder: str = "", multiline: bool = False) -> QWidget`
   - 返回 QLineEdit 或 QTextEdit
   - 统一输入框样式

4. `make_status_label(text: str, status: str = "info") -> QLabel`
   - status 可选值：info/success/warning/error
   - 自动映射颜色：C_TEXT2/C_GREEN/C_ORANGE/C_RED

**文件**：`seeed_jetson_develop/gui/theme.py`

**实现要点**：
- 保持与现有工厂函数风格一致
- 使用已有的颜色常量（C_BG, C_CARD, C_GREEN 等）
- 返回已配置好样式的 widget，调用方无需额外设置

---

### Phase 2: 创建 ListPageBase 基类

**目标**：提取 apps/skills/community 的公共模式

**类设计**：

```python
class ListPageBase(QWidget):
    """列表页面基类，提供筛选、标签页、批量渲染等通用功能"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 状态管理（替代闭包）
        self.filter_state = {"category": "全部", "search": ""}
        self.batch_generation = 0
        self.items_data = []

        # UI 组件引用
        self.tab_buttons = {}
        self.list_container = None
        self.search_input = None

        self._init_ui()

    # === 抽象方法（子类必须实现） ===

    def load_data(self) -> list:
        """加载数据源，返回 item 列表"""
        raise NotImplementedError

    def get_categories(self) -> list[str]:
        """返回分类列表，第一项为"全部"或等效值"""
        raise NotImplementedError

    def build_item_widget(self, item: dict) -> QWidget:
        """构建单个列表项的 widget"""
        raise NotImplementedError

    def filter_item(self, item: dict) -> bool:
        """判断 item 是否匹配当前筛选条件"""
        raise NotImplementedError

    # === 可选覆盖方法 ===

    def get_page_title(self) -> str:
        return "列表"

    def get_page_subtitle(self) -> str:
        return ""

    def get_batch_size(self) -> int:
        return 6

    # === 内部实现（子类无需关心） ===

    def _init_ui(self):
        """构建页面结构：header + tabs + search + scroll list"""
        ...

    def _rebuild_list(self):
        """重新筛选并批量渲染列表"""
        ...

    def _on_category_changed(self, category: str):
        """分类标签点击回调"""
        ...

    def _on_search_changed(self, text: str):
        """搜索框输入回调"""
        ...
```

**关键改进**：

1. **状态管理**：用实例变量替代闭包，便于测试和调试
2. **清晰职责**：抽象方法定义子类必须实现的部分，具体实现封装在基类
3. **灵活扩展**：可选方法允许子类定制行为（如 batch size）

**文件**：`seeed_jetson_develop/gui/widgets/list_page_base.py`（新建）

---

### Phase 3: 重构 community/page.py 作为概念验证

**目标**：将最简单的页面（community, 186 行）转换为使用 ListPageBase

**原因选择 community**：
- 代码量最小（186 行）
- 无复杂的线程/对话框逻辑
- 无事件总线集成
- 适合验证基类设计是否合理

**重构步骤**：

1. 创建 `CommunityPage(ListPageBase)` 类
2. 实现必需的抽象方法：
   - `load_data()` — 加载 product_images.json
   - `get_categories()` — 返回 ["全部"]（无分类）
   - `build_item_widget()` — 构建产品卡片
   - `filter_item()` — 搜索匹配逻辑
3. 保持 `build_page()` 函数签名不变，内部返回 `CommunityPage()` 实例
4. 验证功能一致性

**文件**：`seeed_jetson_develop/modules/community/page.py`

---

## 详细实现方案

### 1. theme.py 新增工厂函数

在 `seeed_jetson_develop/gui/theme.py` 末尾添加 4 个新函数：

```python
def make_tab_button(text: str, active: bool = False) -> QPushButton:
    """创建标签页按钮"""
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    bg = "rgba(122,179,23,0.15)" if active else "transparent"
    color = C_GREEN if active else C_TEXT2
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {bg};
            color: {color};
            border: none;
            border-radius: {pt(20)}px;
            padding: {pt(8)}px {pt(20)}px;
            font-size: {pt(13)}px;
        }}
        QPushButton:hover {{
            background: rgba(122,179,23,0.10);
        }}
    """)
    return btn
```

其余 3 个函数类似，保持简洁。

### 2. ListPageBase 基类实现

创建 `seeed_jetson_develop/gui/widgets/list_page_base.py`：

**核心结构**：

```python
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QPushButton
from PyQt5.QtCore import Qt, QTimer
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_tab_button, make_input_field
)

class ListPageBase(QWidget):
    """列表页面基类"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filter_state = {"category": "全部", "search": ""}
        self.batch_generation = 0
        self.items_data = []
        self.tab_buttons = {}
        self.list_container = None
        self.search_input = None

        self._init_ui()
        self._load_and_render()

    # === 抽象方法 ===
    def load_data(self) -> list:
        raise NotImplementedError

    def get_categories(self) -> list[str]:
        raise NotImplementedError

    def build_item_widget(self, item: dict) -> QWidget:
        raise NotImplementedError

    def filter_item(self, item: dict) -> bool:
        raise NotImplementedError

    # === 可选方法 ===
    def get_page_title(self) -> str:
        return "列表"

    def get_page_subtitle(self) -> str:
        return ""

    def get_batch_size(self) -> int:
        return 6
```

**关键方法**：

- `_init_ui()` — 构建页面结构（header + tabs + search + scroll）
- `_rebuild_list()` — 筛选数据并批量渲染
- `_on_category_changed()` — 分类切换
- `_on_search_changed()` — 搜索输入

### 3. CommunityPage 重构示例

修改 `seeed_jetson_develop/modules/community/page.py`：

**重构前**：186 行的 `build_page()` 函数

**重构后**：

```python
from seeed_jetson_develop.gui.widgets.list_page_base import ListPageBase

class CommunityPage(ListPageBase):
    def load_data(self) -> list:
        # 加载 product_images.json
        data_dir = Path(__file__).parent.parent.parent / "data"
        with open(data_dir / "product_images.json", encoding="utf-8") as f:
            return json.load(f)

    def get_categories(self) -> list[str]:
        return ["全部"]  # 无分类

    def build_item_widget(self, item: dict) -> QWidget:
        # 构建产品卡片（复用原有逻辑）
        card = make_list_card()
        # ... 添加图片、标题、按钮
        return card

    def filter_item(self, item: dict) -> bool:
        kw = self.filter_state["search"].lower()
        if not kw:
            return True
        return kw in item.get("name", "").lower()

def build_page() -> QWidget:
    return CommunityPage()
```

**代码量**：从 186 行减少到约 60 行

---

## 实施步骤

### Step 1: 添加 UI 工厂函数到 theme.py

**文件**：`seeed_jetson_develop/gui/theme.py`

在文件末尾（约 466 行后）添加：

1. `make_tab_button(text, active=False)` — 标签按钮
2. `make_list_card()` — 列表卡片容器
3. `make_input_field(placeholder="", multiline=False)` — 输入框
4. `make_status_label(text, status="info")` — 状态标签

**预期改动**：+60 行

### Step 2: 创建 ListPageBase 基类

**文件**：`seeed_jetson_develop/gui/widgets/list_page_base.py`（新建）

需要先创建目录：`seeed_jetson_develop/gui/widgets/`

实现内容：
- `__init__` — 初始化状态和 UI
- `_init_ui()` — 构建页面结构
- `_rebuild_list()` — 批量渲染逻辑
- `_on_category_changed()` / `_on_search_changed()` — 事件处理
- 4 个抽象方法 + 3 个可选方法

**预期代码量**：约 200-250 行

### Step 3: 重构 community/page.py

**文件**：`seeed_jetson_develop/modules/community/page.py`

1. 导入 `ListPageBase`
2. 创建 `CommunityPage(ListPageBase)` 类
3. 实现 4 个抽象方法
4. 修改 `build_page()` 返回 `CommunityPage()` 实例

**预期改动**：从 186 行减少到约 60-80 行

---

## 验证策略

### 功能验证

**Step 1 验证**（theme.py 工厂函数）：

```python
# 测试脚本
from seeed_jetson_develop.gui.theme import make_tab_button, make_list_card, make_input_field, make_status_label

btn = make_tab_button("测试", active=True)
card = make_list_card()
input_field = make_input_field("请输入...")
status = make_status_label("成功", "success")

# 验证样式是否正确应用
assert btn.styleSheet() != ""
assert "rgba(122,179,23,0.15)" in btn.styleSheet()
```

**Step 2 验证**（ListPageBase 基类）：

创建最小测试子类验证基类功能：

```python
class TestPage(ListPageBase):
    def load_data(self):
        return [{"id": 1, "name": "测试"}]

    def get_categories(self):
        return ["全部"]

    def build_item_widget(self, item):
        return QLabel(item["name"])

    def filter_item(self, item):
        return True

# 实例化并验证
page = TestPage()
assert page.items_data == [{"id": 1, "name": "测试"}]
assert page.filter_state == {"category": "全部", "search": ""}
```

**Step 3 验证**（community/page.py 重构）：

1. 启动 GUI：`python run_v2.py`
2. 切换到 Community 页面
3. 验证功能：
   - 产品列表正常显示
   - 搜索框输入能筛选产品
   - 点击产品卡片能打开链接
   - 布局与重构前一致

---

## 后续迁移路径

### Phase 4: 重构 apps/page.py

**复杂度**：中等（783 行 → 预计 300-400 行）

**额外需求**：
- 需要处理线程（状态检查、安装）
- 需要集成事件总线（`bus.device_connected`）
- 需要对话框（`_InstallDialog`）

**策略**：
1. 继承 `ListPageBase`
2. 覆盖 `get_batch_size()` 返回 6
3. 实现 4 个抽象方法
4. 保留线程和对话框逻辑（暂不提取）

### Phase 5: 重构 skills/page.py

**复杂度**：高（934 行 → 预计 400-500 行）

**额外需求**：
- 变体加载（openclaw/claude/codex 三个来源）
- 分页加载（"加载更多"按钮）
- AI 助手集成
- SFTP 上传对话框

**策略**：
1. 继承 `ListPageBase`
2. 覆盖 `_rebuild_list()` 添加分页逻辑
3. 添加 `load_more()` 方法
4. 保留复杂的变体加载逻辑

### Phase 6: 评估 devices 和 flash 页面

**devices/page.py**（576 行）：
- 不是列表页面，是诊断页面
- 不适合 `ListPageBase`
- 建议单独提取 `DiagnosticsPageBase` 或保持现状

**flash/page.py**（1366 行）：
- 向导式页面，不是列表页面
- 不适合 `ListPageBase`
- 建议提取 `WizardPageBase` 或分步重构

---

## 风险评估与缓解

### 风险 1: 破坏现有功能

**风险等级**：中

**缓解措施**：

- Phase 1-2 只添加新代码，不修改现有代码
- Phase 3 选择最简单的页面（community）作为试点
- 保持 `build_page()` 函数签名不变，确保向后兼容
- 每个 Phase 完成后立即验证功能

### 风险 2: 基类设计不够灵活

**风险等级**：中

**缓解措施**：

- 提供足够的可选方法（`get_batch_size()`, `get_page_title()` 等）
- 允许子类覆盖内部方法（`_rebuild_list()`, `_init_ui()`）
- 先用 community 验证设计，发现问题及时调整
- apps/skills 迁移时可能需要扩展基类

### 风险 3: 性能下降

**风险等级**：低

**缓解措施**：

- 批量渲染逻辑保持不变（QTimer.singleShot 异步）
- 状态管理从闭包改为实例变量，性能影响可忽略
- 如有性能问题，可在基类中优化，所有子类受益

### 风险 4: 迁移成本高

**风险等级**：低

**缓解措施**：

- 渐进式迁移，不强制一次性完成
- community → apps → skills 逐步推进
- devices/flash 可暂不迁移，等待更合适的基类设计

---

## 预期收益

### 代码量减少

- community: 186 → 60-80 行（减少 60%）
- apps: 783 → 300-400 行（减少 50%）
- skills: 934 → 400-500 行（减少 50%）
- **总计**：约减少 1000+ 行重复代码

### 可维护性提升

- 状态管理清晰（实例变量 vs 闭包）
- 职责分离明确（基类 vs 子类）
- 样式统一（UI 工厂函数）
- 易于测试（可单独测试基类和子类）

### 扩展性增强

- 新增列表页面只需实现 4 个方法
- UI 样式修改只需改 theme.py
- 批量渲染逻辑统一优化

---

## 总结

本重构计划采用**渐进式、低风险**的策略：

1. **Phase 1**：补充 UI 工厂函数（纯新增，零风险）
2. **Phase 2**：创建基类（纯新增，零风险）
3. **Phase 3**：重构最简单页面验证设计（低风险，易回滚）
4. **Phase 4-5**：逐步迁移复杂页面（中风险，已验证设计）
5. **Phase 6**：评估其他页面（可选）

**关键成功因素**：

- 保持向后兼容
- 充分验证每个阶段
- 灵活调整基类设计
- 不强制完成所有迁移

**下一步行动**：开始实施 Phase 1，添加 UI 工厂函数到 theme.py。
