# AGENTS.md — 项目规则

本文件是 AI 编码代理（Codex / Claude / 同类工具）在本仓库工作时的**操作守则**。先读它，再动手。

## 项目一句话

Seeed Jetson Develop Tool：PyQt6（qtpy）桌面客户端，面向 Seeed Jetson 开发者的上位机 —— 烧录、设备诊断、远程开发、应用市场、Skills、OTA、社区。深色科技风 UI。

## 规则优先级

1. 用户明确指令（本次会话中最高）
2. 本文档（AGENTS.md）
3. `design.md`（UI 设计规范，唯一权威）
4. `CONTEXT.md`（架构背景）
5. 既有代码里的既有模式（新代码遵循，不是照抄所有历史代码）

**任何 UI 改动前必须先读 `design.md`，并严格遵守。UI 规范冲突时以 `design.md` 为准。**

## UI 改动铁律（违反即返工）

- 颜色 / 字体 / 圆角 / 阴影 token 只允许来自 `gui/theme.py` 常量；**禁止**在页面代码写字面量色值。
- 组件一律用工厂函数：`make_button / make_label / make_card / make_input_card / make_section_header / make_log_view / make_input_field / make_tab_button / ShinyProgressBar / StepIndicator / StatusBadge / EmptyStateWidget / ToastNotification`。
- **禁止原生 `QMessageBox`**；用 `theme.show_info_message / show_warning_message / show_error_message / ask_question_message`。
- 字号必须经 `pt()`（Windows DPI 缩放）；font-family 走 `build_app_font()` / `build_mono_font()`，不硬编码。
- Emoji 必须彩色：含 emoji 的 QLabel 用 `make_label()` 或 `set_emoji_font_for_label()`。
- 新页面继承 `widgets/page_base.PageBase`；筛选列表页继承 `widgets/list_page_base.ListPageBase`。禁止脱离设计系统自建页面骨架。
- 操作反馈：Toast 通知 + StatusBadge；禁止用"日志追加一行"代替操作反馈。
- 空状态用 `EmptyStateWidget`，禁止裸 "No data"。
- 耗时操作必须 `QThread` + 信号回主线程，禁止阻塞 UI。
- `QGraphicsDropShadowEffect` 不与高频 `QTimer` 重绘叠加（Windows 崩溃史）；阴影对象销毁时 `clear_shadow()`。

## 国际化铁律

- 文案唯一入口：`seeed_jetson_develop.gui.i18n.t(key, **kwargs)`。
- **禁止使用 `gui/runtime_i18n.py`（已废弃）**及其 `ZH_EN_EXACT` 字典方式。
- 新文案必须同时写入 `locales/en/<module>.json` 与 `locales/zh-CN/<module>.json`。
- Key 命名：`<module>.<区域>.<名称>` 小写点分式，如 `ai_chat.btn.send`、`skills.search.placeholder`。
- 占位符用 `{name}`（`str.format`）；支持 `t("…", lang=…)` 与运行时 `retranslate_ui()` 切换。

## 代码地图

```
run_v2.py                        # 启动入口（python3 run_v2.py [--debug-console]）
seeed_jetson_develop/
  gui/
    theme.py                     # ★ 设计 token + 组件工厂（唯一权威）
    styles.py                    # 旧版浅色 QSS（历史兼容，新代码勿扩展）
    ai_chat.py                   # AI 对话面板
    i18n.py                      # ★ 现代 key 式国际化
    runtime_i18n.py              # 已废弃，禁止使用
    main_window_v2.py            # 主窗口组装
    widgets/                     # ★ 组件库：page_base / list_page_base / empty_state /
                                 #   toast_notification / loading_spinner / breathing_* /
                                 #   animated_* / ripple_button / focus_ripple_edit / ...
  modules/<flash|devices|apps|skills|remote|ota|community>/
    page.py                      # 各功能页（迁移目标：全部基于 PageBase）
    thread.py / *.py             # 后台线程与业务逻辑
  locales/en|zh-CN/*.json        # 双语文案
  data/                          # BSP / 产品图 / Recovery 元数据
  core/                          # events(事件总线) / runner / config ...
design.md                        # ★ UI 设计规范（改动 UI 先读它）
AGENTS.md                        # 本文件
CONTEXT.md                       # 架构演进背景
```

## 协作方式

- 大改（跨模块、迁移、重构）：先读 `design.md` + 相关 `modules/*/page.py` + `CONTEXT.md`，再动手；用 TODO 列表跟踪。
- 只读调查：优先用 `scout` 思路——先定位，再改；不要整文件通读无关键文件。
- 改共享文件（`theme.py`、`i18n.py`、`page_base.py`）：先说明改动意图，避免与并行任务冲突。

## 验收（每次 UI/逻辑改动必做）

1. **运行验证**：`python3 run_v2.py --debug-console`（或针对性冒烟脚本），确认改动面实际生效，无样式断裂/异常日志。
2. **测试**：有测试框架就跑 `pytest`；新建逻辑（状态机 / 过滤 / locale key 完整性）按需补单测。UI 视觉效果以实际运行为准，不写"为了有测试"的测试。
3. **清理**：删除调试打印、临时代码；同步 `CHANGELOG.md`（如有对应小节）。
4. **自检**：对照 `design.md` 第 8 节验收清单逐项过。

## 明确禁止

- 绕过 `design.md` 新造第二种 UI 风格 / 新色值。
- 用 `sed`/手写正则跨文件改代码（符号级改动用 LSP rename、结构级用 AST）。
- 删除或改名 `theme.py` 中仍被引用的 token 而不更新全部调用点（改前跑全套引用检查）。
- 把阻塞 UI 的耗时逻辑放主线程。
- 在不读 `design.md` 的情况下提交任何视觉相关改动。