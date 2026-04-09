# 本次本地改动汇总

本文档记录当前未提交的全部本地改动（相对于上次 commit），共 18 个源文件，+2073 / -1065 行。

---

## 1. CLAUDE.md — 项目指引文档更新

- 新增 **AI 助手** 章节：记录浮动面板实现、模型调用、SSH 状态同步机制、安全拦截规则、外部注入接口
- 新增 **YOLOv26 Dual GMSL 应用** 章节：明确 apps.json 与 wiki GMSL 版的版本对齐关系，区分 GMSL 版与 USB 版的脚本/模型命名差异
- 补充 CLI 模式用法、事件总线完整信号列表、SerialRunner 说明

---

## 2. gui/ai_chat.py — AI 助手浮动面板 (+424 行)

这是改动量最大的文件，主要变更：

### 新增功能
- `FloatingAIAssistant` 浮动球 + 面板容器，球可拖拽、吸附窗口边缘
- `_AiToolThread` 支持 Claude tool_use 循环，可在 Jetson 上执行 SSH 命令
- `_ToolCallBubble` 工具调用气泡，显示命令 + 执行结果
- `inject_context()` / `inject_topic()` / `inject_error()` 外部注入接口
- `build_ai_system_prompt()` 动态构建 system prompt（包含 Skills 和 Apps 列表）

### Bug 修复
- **面板自适应窗口大小**：`_update_positions()` 中动态计算 `pw/ph = min(固定值, 可用空间)`，最小 280×300，避免小窗口溢出
- **SSH badge 状态同步**：`_fire_ai()` 每次请求前从全局 `get_runner()` 重新同步 runner，修复"已连接但显示无设备"的问题
- **发送按钮截断**：`setFixedWidth` 改为 `setMinimumWidth`，按钮根据文字自动撑开

---

## 3. gui/main_window_v2.py — 主窗口 (+79 行)

- 集成 `FloatingAIAssistant`，挂载到主窗口
- 社区页帖子点击时调用 `inject_topic()` 注入 AI 助手

---

## 4. gui/runtime_i18n.py — 运行时国际化 (+63 行)

- 新增/扩展翻译条目

---

## 5. modules/apps/ — 应用市场

### apps/data/apps.json (+173/-变更)
- 新增 `yolov26-dual-gmsl` 应用条目（14 步安装命令、check_cmd、run_cmd、clean_cmd）
- 各应用补充 `uninstall_cmds` 字段
- jetson-examples 类应用统一加 `export PATH=$HOME/.local/bin:$PATH` 前缀

### apps/page.py (+652 行，重构)
- 应用卡片 UI 重构，支持安装/卸载/运行/清理全流程
- 安装进度条 + 分步执行
- 错误时调用 `inject_error()` 自动弹出 AI 助手分析

### apps/registry.py (-174 行，精简)
- 移除硬编码的默认应用列表，统一从 `apps.json` + `jetson_examples.json` 加载

---

## 6. modules/devices/ — 设备管理

### devices/diagnostics.py (+96 行)
- 扩展体检项：新增 CUDA、TensorRT、Docker、磁盘空间等检测命令
- 检测结果结构化输出

### devices/page.py (+50 行)
- 体检结果 UI 展示优化

---

## 7. modules/remote/ — 远程连接

### remote/page.py (+56 行)
- code-server 多镜像降级下载逻辑

### remote/connector.py (+16 行)
- 局域网扫描优化

### remote/net_share_dialog.py (+31 行)
- 网络共享对话框改进

### remote/jetson_init.py (+3 行)
- 初始化流程小调整

### remote/agent_install_dialog.py / desktop_dialog.py
- 微调（各 2 行）

---

## 8. modules/skills/ — Skills 中心

### skills/engine.py (+124 行)
- `run_skill()` 支持 `max_retries` 重试机制
- 内置 Skills 加载逻辑增强

### skills/page.py (+1084 行，大幅重构)
- Skills 卡片 UI 重新设计（左侧彩色边框表示状态）
- 支持运行、重试、查看日志
- 与 AI 助手联动（`inject_context`）

---

## 9. core/runner.py — 命令执行引擎 (+50 行)

- 新增 `SerialRunner`（串口执行）
- SSHRunner 增加 `set_keepalive(30)` 防空闲断连
- runner 切换时发送 `device_connected` / `device_disconnected` 事件
