# Seeed Jetson Develop Tool — UI 设计规范（design.md）

> 本文档是本项目 **UI/UX 的唯一权威规范**。所有界面相关代码（新页面、组件、对话框、主题改动）必须遵循本文档。
> 规范来源：`seeed_jetson_develop/gui/theme.py`（现代深色主题）、`gui/widgets/`（组件库）、`gui/ai_chat.py`（对话 UI）、`gui/i18n.py`（国际化机制）。
> 与代码冲突时，以**本项目文件为准**；需要新增设计 token 时，先修改本文档并同步修改 `theme.py`，禁止绕过。

---

## 1. 设计理念

本项目采用**深色科技风**上位机设计语言，核心理念（源自 `theme.py` 文档头）：

1. **用背景色层次代替边框** — 不同层级用不同深浅的背景区分，不依赖硬边框。
2. **用阴影代替硬边框** — 卡片、对话框用投影表达浮起，边框只做点缀高光。
3. **用留白代替分隔线** — 区块之间用间距分隔，不画分割线。
4. **深色科技风，符合上位机气质** — 全局深色背景 + Seeed 品牌绿高亮。

辅助原则：

- **克制**：动画是调味剂不是主菜（参考 Apple / Linear 设计哲学），每个动效必须有明确反馈意义。
- **渐进增强**：在既有组件之上叠加视觉/动效，不破坏功能。
- **性能优先**：动画只用 `QTimer` + `update()` 或 `QPropertyAnimation`，绝不阻塞主线程；`QTimer` 空闲即停。
- **一致性**：新代码不允许发明第二种风格，只允许复用现有 token 与工厂函数。

**主题基调一句话**：蓝灰深色渐变打底，Seeed 绿（`#8DC21F`）做唯一品牌高亮，所有浮起元素（卡片/对话框/按钮）用「顶部亮高光边 + 底部暗阴影边 + 投影」表达立体感，文字严格按主/次/辅助三档亮度分层。

---

## 2. 设计 Token

### 2.1 颜色系统（唯一来源：`gui/theme.py` 头部常量）

| Token | 值 | 用途 |
| --- | --- | --- |
| `C_BG_DEEP` | `#0A0F17` | 最深背景：自定义标题栏、侧边栏、AI 对话根容器 |
| `C_BG` | `#0F1620` | 主背景（QDialog 等） |
| `C_BG_LIGHT` | `#141D28` | 内容区背景 |
| `C_CARD` | `#192333` | 主卡片背景（AI 消息气泡、msgbox 卡片） |
| `C_CARD_HOVER` | `#1F2C3E` | 卡片悬停 |
| `C_CARD_LIGHT` | `#1E2B3C` | 次级卡片 / 输入框背景 / 日志面板 |
| `C_BORDER_SUBTLE` | `rgba(255,255,255,0.07)` | 卡片顶部高光边（立体感关键） |
| `C_BORDER_FOCUS` | `rgba(122,179,23,0.55)` | 输入框焦点边框 |
| `C_BORDER_CARD` | `rgba(255,255,255,0.05)` | 卡片外边框 |
| `C_GREEN` | `#8DC21F` | **Seeed 品牌绿**：主按钮、选中态、进度、成功 |
| `C_GREEN2` | `#7AB317` | 深绿（进度条渐变下沿） |
| `C_GREEN_DIM` | `#6BA30F` | 主按钮按压态 |
| `C_GREEN_GLOW` | `rgba(141,194,31,0.18)` | 绿色光晕（选中/聚焦） |
| `C_BLUE` | `#3D8EF0` | 信息 / 链接 |
| `C_ORANGE` | `#F5A623` | 警告（含工具调用气泡标题） |
| `C_RED` | `#E53E3E` | 错误 / 危险操作 |
| `C_TEXT` | `#F4F8FC` | 主文字（更白更清晰） |
| `C_TEXT2` | `#B8CCDC` | 次级文字 |
| `C_TEXT3` | `#8A9EAE` | 辅助文字 / 占位提示 |

**规则**：

- 语义色仅允许 4 种状态映射：`ok=C_GREEN`、`warn=C_ORANGE`、`error=C_RED`、`info=C_BLUE`（见 `theme.STATUS_COLORS`）。
- 任何组件代码**不得**直接书写未在 `theme.py` 定义的十六进制色值；特殊状态色（禁用、危险渐变、半透明叠层）必须与 `theme.py` 中既有写法保持一致，并优先提取为常量。
- 深浅叠加规则：文字层级恒为 `C_TEXT → C_TEXT2 → C_TEXT3`（主 → 次 → 辅助），禁止反向。

### 2.2 字体与字号（`theme.py`：`UI_FONT_CANDIDATES` / `MONO_FONT_CANDIDATES` / `pt()`）

- **UI 字体候选链**（按序回退）：`Noto Sans CJK SC → Noto Sans SC → Source Han Sans SC → Microsoft YaHei UI → Microsoft YaHei → PingFang SC → Hiragino Sans GB → WenQuanYi Micro Hei → SimHei → Arial Unicode MS`。统一通过 `build_app_font()` 构建。
- **等宽字体候选链**：`Sarasa Mono SC → Sarasa Term SC → Noto Sans Mono CJK SC → Source Han Mono SC → WenQuanYi Zen Hei Mono → Cascadia Mono → Cascadia Code → JetBrains Mono → Consolas → DejaVu Sans Mono`。通过 `build_mono_font()` 构建；日志/命令输出一律追加 `monospace, 'Noto Color Emoji'` 样式链。
- **字号一律经 `pt(px)` 换算**：Windows 下缩放因子 `0.80` 防 DPI 二次放大；其他平台 `1.0`。任何地方禁用字面量 `px` 字号（`pt()` 除外）。
- **Emoji 必须彩色**：Linux 下全局字体追加 `Noto Color Emoji` 链（`build_app_font`）；含 emoji 的 QLabel 必须调用 `set_emoji_font_for_label()` 或 `make_label()`（内部自动处理）。禁止出现黑白 emoji 字形。

| 层级 | 字号（经 `pt()`）| 字重 | 典型场景 |
| --- | --- | --- | --- |
| 品牌标题 | 17 | 700 | 侧边栏 Logo 区 |
| 页面 Header 标题 | 18 | 700 | `PageBase` Header 标题 |
| 区块标题 | 15 | 700 | `make_section_header` 标题 |
| 卡片标题 | 14 | 700 | `CardTitle` |
| 正文 | 13 | 400–500 | 默认文本 |
| 次级 | 12 | 400–600 | 副标题、按钮（普通按钮 500 / 对话框按钮 600 字重）、状态 |
| 辅助 | 11 | 400 | 副标题说明、日志（等宽）、提示 |
| 小号 | 10 | 400–500 | 徽标、工具调用头部、注入提示 |

### 2.3 圆角、间距、尺寸、阴影

**圆角**

| 项 | 数值 |
| --- | --- |
| 卡片圆角 | 12px（`make_card` / `HoverCard` 默认） |
| 输入容器圆角 | 10px（`make_input_card`） |
| 按钮圆角 | 8px（工厂） / 10px（对话框按钮） |
| 输入框圆角 | 8px（`input_qss`/`QLineEdit`） / 10px（`QTextEdit`） |
| 日志面板圆角 | 8px（`make_log_view`） |
| 气泡圆角 | 10px（`_MsgBubble` / `_ToolCallBubble`） |
| 胶囊/徽标 | 999px |
| 滚动条 | 宽 8px、handle 圆角 4px、悬停变绿 |

**间距标尺**（全部经 `pt()`；比例层级固定，不允许自定义取值）

| 层级 | 数值 | 来源 / 用途 |
| --- | --- | --- |
| 页面外边距 | 28 水平 / 24 垂直 | `PageBase` 内容容器 padding |
| 页面主间距 | 20 | 页面主 layout 元素间距（块级） |
| 区块标题下边距 | 16 | `make_section_header` 底部留白 |
| 卡片/分组内距 | 20–24 | 对话框 body 内边距 24/22/20/18；`StepIndicator` 外距 24/20 |
| 组内元素间距 | 8–12 | `StepIndicator` 项 12、卡片/对话框元素间 10–16 |
| 文字组间距 | 4–6 | 标题+副标题 4（Header、section）、消息标题/正文/详情 6 |
| 控件内边距 | 8 × 14 | 输入框、下拉框、工具提示、日志面板 10 |
| 按钮水平内距 | 16 / 20 / 24 | 普通 / 危险 / 主按钮 |
| 微间距 | 2–4 | 徽标 2×8、代码片 4×8、滚动条 margin 2–4 |

**固定尺寸**

| 项 | 数值 |
| --- | --- |
| 页面 Header 高度 | 64px（`PageBase`，背景 `C_BG_DEEP`） |
| 主按钮高度 | 42px；`small=True` 36px |
| 主导航项 | 最小高 18px + 内边距 10×12 |
| 标签页（Tab） | 最小高 36px，水平内距 18 |
| StepIndicator 圆 | 36px；箭头 28×36 |
| 复选框 / 单选指示器 | 18 × 18 |
| 日志区最小高 | 180px（`make_log_view` 默认） |
| 对话框宽度 | 460–600px（`ThemedMessageBox`） |
| 滚动条 handle 最小尺寸 | 垂直 48px 高 / 水平 48px 宽 |
| 窗口最小值 | 1120 × 720 |
| 图标圆（msgbox） | 40px |

**阴影**

| 项 | 数值 |
| --- | --- |
| 卡片阴影 | blur 28, offset (0, 6), alpha 80；hover → blur 42, offset (0, 10), alpha 100 |
| 常规阴影 | blur 20, offset (0, 4), alpha 60（`apply_shadow`） |
| 绿色光晕 | blur 15, offset (0, 0), alpha 80（`apply_glow`，选中态） |
| 对话框主卡片阴影 | blur 32, offset (0, 10), alpha 120 |

**阴影红线**：`QGraphicsDropShadowEffect` 搭配 `QTimer` 高频重绘在 Windows 下会触发 painter 冲突崩溃 —— `HoverCard` 的 hover 阴影切换**必须直接赋值、不做动画过渡**（保持现有实现），新组件如需阴影动效改用 `QPropertyAnimation`。

### 2.4 动效时长规范

| 类型 | 时长/频率 |
| --- | --- |
| 微交互（按钮缩放/涟漪） | 150ms 内；涟漪 `QTimer` 16ms/tick |
| 过渡（页面切换、下划线） | 200–300ms |
| 通知（Toast） | 250ms 淡入（OutCubic），默认 3000ms 后自动淡出 |
| 列表交错入场 | 每项间隔 40ms |
| 呼吸/扫描/流光动画 | `QTimer` 16ms/tick，空闲即 `stop()` |

---

## 3. 布局结构

### 3.1 应用窗口

- **无边框窗口**（`FramelessWindowHint`）+ 自定义可拖动标题栏（`WindowChrome`），深蓝渐变标题栏底色。
- 窗口最小尺寸：`1120 × 720`（Windows 平台常量 `_PlatformConfig`）。
- 全局结构：左侧 `Sidebar`（深色渐变 `#1C2733→#121922`，左侧 3px Seeed 绿边 `#8DC21F`，品牌 Logo + 标题 + 导航按钮）+ 右侧 `TopBar` + `QStackedWidget` 页面堆叠。

### 3.2 侧边栏导航

- 导航按钮：透明底、左对齐、圆角 9px、字重 600、内边距 10px 12px。
- 状态：`hover` → `#2A3347`；`active` → 渐变 `#394B66→#2E3E56` + 边框 `#425572` + 白字。
- 导航项可带 emoji 图标前缀（如 ⚡ 🖥 📦 🤖 💻 💬），emoji 必须走彩色字体链。

### 3.3 页面骨架（`widgets/page_base.py` — `PageBase`）

**所有页面必须继承 `PageBase`**，统一结构：

1. **Header**：固定高 64px、背景 `C_BG_DEEP`、水平内边距 28px；标题 18px / 700 / `C_TEXT`，副标题 12px / `C_TEXT3`，右侧操作区（`add_header_widget()`，右对齐）。
2. **内容滚动区**：`QScrollArea`（透明背景，横向滚动关闭），内容容器背景 `C_BG`、边距 28/24/28/24、间距 20。
3. 区块标题一律使用 `make_section_header(title, subtitle)`（无分割线，纯文字层次，下边距 16px）。

### 3.4 列表页骨架（`widgets/list_page_base.py` — `ListPageBase`）

列表/筛选类页面（Apps、Skills 等）继承 `ListPageBase`：

- 顶部筛选标签：`make_tab_button()`（动画下划线 Tab，选中 = `C_GREEN` 文字 + 底部绿色下划线展开，无背景块）。
- 搜索框：`make_input_field()`（单行 `FocusRippleLineEdit`）。
- 列表项渲染采用分批挂载（`QTimer`）避免卡顿。

### 3.5 向导流程（`theme.py` — `StepIndicator`）

多步操作（Flash、OTA）使用 `StepIndicator(["Step1", "Step2", …])`：

- 36px 圆形编号 + 标签 + `›` 箭头，水平排布。
- 三态：`active` = 绿色实心圆（`C_GREEN` 底、`#071200` 数字）；`done` = 绿色描边半透明圆；`pending` = `rgba(255,255,255,0.10)` 描边灰字。
- `set_current(idx)` 切换状态（0-based）。

---

## 4. 组件规范

所有组件**必须**通过 `gui/theme.py` 与 `gui/widgets/` 提供工厂函数创建；禁止在各页面重复定义同款组件。

### 4.1 按钮（`make_button` / `RippleButton`）

| 类型 | 参数 | 样式 |
| --- | --- | --- |
| 主按钮 | `make_button(text, primary=True)` | 绿色渐变 `#A0D428→#7AB317` + 顶部高光 `rgba(180,240,60,0.45)` + 深色文字 `#0A1800` + 字重 700；hover `#B0E030→#8DC21F`；pressed `#6BA30F→#7AB317`；disabled 底色 `#1A2535` 灰字 |
| 普通按钮 | 默认 | `rgba(255,255,255,0.04)` 底 + `rgba(255,255,255,0.08)` 边框 + 顶部 `0.12` 高光 + `C_TEXT2` 字重 500；hover 提亮至 `0.09`/`0.15`、字色 `C_TEXT` |
| 危险按钮 | `make_button(..., danger=True)` | 红渐变 `rgba(229,62,62,0.22)→rgba(180,30,30,0.18)` + 红边框 + 红字 `#FF8080`；hover 加深 |
| 小号 | `small=True` | 高 36px、字号 11 |

- 全部按钮带 **Material 涟漪点击反馈 + 按压 padding 微缩放**（`RippleButton` 内置，禁用态除外）。
- 指针一律 `PointingHandCursor`。

### 4.2 卡片（`make_card` / `make_input_card` / `HoverCard`）

- `make_card(radius=12, with_shadow=True)`：渐变 `#1E2D40→C_CARD` 底 + 悬浮阴影，hover 阴影加深（直接切换，不做动画）。
- `make_input_card(radius=10)`：内凹感输入容器（顶边暗、底边亮）。
- 用途区分：展示/条目用 `make_card`，表单包容器用 `make_input_card`。

### 4.3 输入控件

- 单行输入：`make_input_field()` / `FocusRippleLineEdit`（焦点绿色涟漪）；多行：`QTextEdit` + `input_qss()`。
- 焦点态统一：边框变 `C_BORDER_FOCUS`、顶边染绿；selection 背景 `rgba(141,194,31,0.25)`。
- `QLineEdit` 底色 `#0D1520`、悬停 `#0F1825`：确保深色主题下清晰可辨。
- 下拉框 `QComboBox` 深色渐变 + 自定义箭头（禁默认箭头）；Linux popup 限高问题用 `DropdownButton` 替代。
- 复选框/单选：18px 指示器、圆角 5px/9px、选中绿色渐变 `#A0D428→#7AB317`。

### 4.4 标签页与筛选（`AnimatedTabButton` / `make_tab_button`）

- 选中态：仅文字变色 `C_GREEN` + 底部绿色下划线从中间向两侧展开（`QTimer` 驱动，步进 0.18/16ms）。
- 禁止用背景块表达选中。

### 4.5 进度条（`ShinyProgressBar`）

- 圆角胶囊、绿色渐变 chunk + 流动光泽高光；`set_color()` 支持蓝/橙/绿按阶段换色（下载/上传/执行）。
- 普通低速场景可用全局 `QProgressBar` 样式（默认绿色渐进渐变）。

### 4.6 状态徽标（`StatusBadge`）

- 纯文字颜色表达状态：`ok=C_GREEN` / `warn=C_ORANGE` / `error=C_RED` / `info=C_BLUE` / `default=C_TEXT2`，字号 12。
- `set_status(status, text)` 更新；状态词严格限定上述 5 键。

### 4.7 日志区（`make_log_view`）

- 所有日志面板统一使用：`C_CARD_LIGHT` 底、无边框、圆角 8、内边距 10、等宽字体、`C_GREEN` 文字、最小高 180。

### 4.8 对话框（`ThemedMessageBox` 及工厂）

- **禁止直接使用原生 `QMessageBox`**。统一走 `theme.py` 工厂：`show_info_message / show_warning_message / show_error_message / ask_question_message`。
- 视觉：无边框半透明窗口 + 居中卡片（`C_CARD` 底、圆角 12、阴影 blur 32）；40px 圆形图标（配色：info 蓝 / warning 橙 / error 红 / question 绿 + 对应 `rgba` 底）；标题 `C_TEXT` 700、正文 `C_TEXT2`、详情 `C_TEXT3`；底部按钮行（默认按钮绿色、危险按钮红色、常规透明）。宽度 460–600px。

### 4.9 Toast 通知（`widgets/toast_notification.py`）

- 操作结果反馈统一用 Toast：从右上角滑入，success（绿）/ error（红）/ warning（橙）/ info（蓝），自动约 3s 淡出。**禁止用"日志追加一行"代替操作反馈。**

### 4.10 空状态（`widgets/empty_state_widget.py` — `EmptyStateWidget`）

- 列表无数据时显示 QPainter 几何风插图（box / search / wifi 等）+ 标题 + 引导文案；禁止裸 `"No data"` 文本。
- 插图画布带缓慢飘动动画，空闲即停。

### 4.11 AI 对话（`gui/ai_chat.py`）

- 用户气泡：`rgba(122,179,23,0.12)` 底 + `C_TEXT` 字；AI 气泡：`C_CARD` 底 + `C_TEXT2` 字；均圆角 10。
- 工具调用气泡 `_ToolCallBubble`：橙色标题行（`C_ORANGE`）、等宽输出块 `rgba(0,0,0,0.25)`、代码片段浅色芯片 `rgba(255,255,255,0.06)`、链接 `C_BLUE`。
- 对话根容器 `C_BG_DEEP`。
- 格式化文本支持 Markdown 风：`**粗体**`、代码块。

### 4.12 其他内置组件（`widgets/`）

`breathing_logo` / `breathing_dot` / `breathing_button`（品牌呼吸感）、`flash_animation` / `scan_line_overlay` / `content_bg_anim`（扫描/流光背景）、`loading_spinner`、`glow_separator`、`animated_checkbox`、`animated_stacked_widget`（页面切换淡入淡出）、`onboarding_guide`（引导）。选用时直接复用，禁止重写。

---

## 5. 状态与交互反馈

| 状态 | 表现（必须与现有实现一致） |
| --- | --- |
| 悬停 | 卡片阴影加深；按钮渐变/底色提亮；输入框边框 `rgba(255,255,255,0.30)` |
| 聚焦 | 输入框边框 `C_BORDER_FOCUS` + 顶边染绿 + selection 绿底 |
| 按压 | 按钮渐变压暗 + padding 微扩展（涟漪） |
| 禁用 | 灰化（按钮 `#1A2535` 底 `#4A5B6A` 字；输入框 `#111820` 底 `C_TEXT3` 字） |
| 进行中 | `ShinyProgressBar` 流光 / `loading_spinner` / 骨架或占位（禁纯 "Loading..." 空白） |
| 成功/失败/警告 | Toast + `StatusBadge` 状态色 |
| 长任务 | 后台线程（`QThread`）+ 信号回传进度，禁阻塞主线程 |

---

## 6. 国际化与语言

- **唯一入口**：`seeed_jetson_develop.gui.i18n.t(key, **kwargs)`（基于 key 的 locale JSON；`{param}` 占位符用 `str.format`）。
- **`gui/runtime_i18n.py` 已废弃**（仅服务旧版 V2 widget），新页面/新改动**禁止**使用其中任何内容（包括 `ZH_EN_EXACT` 字典方式）。
- locale 文件：`seeed_jetson_develop/locales/<lang>/<module>.json`，现支持 `en` 与 `zh-CN`。
- **Key 命名规范**：`<module>.<区域>.<名称>`，小写点分式。例：`ai_chat.btn.send`、`ai_chat.key_saved`、`skills.search.placeholder`、`flash.step.detect`。
- 新增文案必须**同时**写入 `en` 与 `zh-CN` 对应模块文件；`t()` 找不到 key 时回退显示 key 本身 —— 因此 key 必须可读（不要用无意义 hash）。
- 运行时语言切换：页面通过 `I18nBinding` 注册 + `retranslate_ui(lang)` 刷新。
- 系统语言未匹配时归一化到 `DEFAULT_LANGUAGE`（见 `core/config.py`）。
- UI 文案语言风格：中文简洁、英文自然；界面 emoji 允许（如 ✅ 🔍 ▶ 📦），必须走彩色字体链。

---

## 7. 代码规范（强制）

1. **主题单点**：所有颜色/字体/圆角/阴影 token 只存在于 `theme.py`（及兼容的 `styles.py` 常量头）。页面代码引用变量，禁止字面量色值。
2. **工厂优先**：按钮 `make_button`、标签 `make_label`、卡片 `make_card/make_input_card`、区块标题 `make_section_header`、日志 `make_log_view`、输入 `make_input_field`、标签页 `make_tab_button`、进度 `ShinyProgressBar`、步骤 `StepIndicator`、状态 `StatusBadge`、对话框 `show_*_message`、空状态 `EmptyStateWidget`、Toast `ToastNotification`。
   - 特性风格导入别名（与现有页面一致）：`from ..theme import pt as _pt, make_label as _lbl, make_card as _card`。
3. **禁止内联样式**：新页面禁止大段 `setStyleSheet("...")` 写死样式；必须走工厂或引用 token。确有例外（仅限局部布局微调）时，使用的色值必须来自 theme 常量，并注释原因。
4. **对话框**：禁止 `QMessageBox` 原生弹窗；禁止浅色/系统默认标题栏混入（历史 Bug：Apps 安装对话框曾用浅灰标题栏，违反深色主题）。
5. **线程**：耗时操作进 `QThread`；UI 更新通过信号回主线程。
6. **阴影**：`QGraphicsDropShadowEffect` 不与高频 `QTimer` 重绘叠加（Windows 崩溃风险）；阴影对象记录引用并在销毁时 `clear_shadow()`。
7. **新增 token 流程**：先在 `design.md` 本文件补 Token → 在 `theme.py` 定义常量 → 组件引用。三处缺一不可。
8. **自动化测试**：UI 逻辑可测部分（状态机、过滤、i18n key 完整性）写 pytest；视觉部分通过实际运行验证（见 AGENTS.md 验收）。
9. **回归红线**：默认字体 `Noto Sans CJK SC` 链、emoji 彩色链、深色主题底色、Seeed 绿 `#8DC21F`、1120×720 最小窗口，任何改动不得破坏。

---

## 8. 验收清单（提交 UI 改动前逐项自检）

- [ ] 全部颜色来自 theme token，无字面量色值；
- [ ] 组件均由工厂函数创建，未重复发明组件；
- [ ] 字号均经 `pt()`，Windows 不会偏大；
- [ ] emoji 彩色可显示；
- [ ] 无原生 `QMessageBox` / 浅色弹窗；
- [ ] 焦点态、悬停态、禁用态齐全且有区分；
- [ ] 新文案已同时加入 `en` 与 `zh-CN` locale，key 遵循 `<module>.<area>.<name>`；
- [ ] 耗时操作在后台线程，UI 不卡顿；
- [ ] 阴影不与高频重绘叠加；
- [ ] 空状态、进行中、成功/失败均有视觉反馈（Toast/骨架/StatusBadge）；
- [ ] 实际启动运行验证（`python3 run_v2.py --debug-console`），页面无样式断裂。

---

*本规范随 `gui/theme.py` 演进；改动设计语言必须先更新本文档，再改代码。*