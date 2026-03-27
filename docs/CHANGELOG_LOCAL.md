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

---

## 各功能模块完成度审计（2026-03-26 实测）

以下基于代码实际检查，更正原始评估中的偏差。

---

### 1. 烧录功能（85%） ✅ 评估基本准确

**已实现：**
- `flash.py`（401 行）：完整的固件下载（多 URL 回退、断点续传）、SHA256 校验、tar 解压、sudo 鉴权、可取消刷写流程
- `l4t_data.json`：94 条固件记录，覆盖 **32 个产品型号**、多个 L4T 版本
- `recovery_guides.json` + `recovery_guides.py`：**5 个系列**的 Recovery 教程
- `main_window_v2.py` 中 `_build_flash_page()`：完整的步骤向导 UI（4 步 wizard、设备选择、Recovery 指南、刷写进度）

**缺口（与原描述一致）：**
- `modules/flash/page.py` 仍是 TODO 占位（`"⚡ 烧录模块 — 开发中，逻辑见 main_window_v2._build_flash_page()"`），UI 逻辑未迁移到模块化结构
- `flash_started` / `flash_completed` 事件已在 `events.py` 定义，但全局无任何 `.emit()` 调用，事件回调与其他模块的联动未接通

**规划不变：**
- 迁移 `_build_flash_page()` → `modules/flash/page.py`
- 接通 `bus.flash_completed` → 设备检测自动触发

---

### 2. 设备监控功能（90%） ⬆️ 原评估 70% 偏低

**已实现（远超原描述）：**
- `modules/devices/page.py`（574 行）：**完整 UI**，非 TODO。包含设备信息卡片（2×2 grid：型号/L4T/内存/IP）、快速诊断卡片、外设状态卡片、PyTorch 安装对话框
- `diagnostics.py`（220 行）：6 项快速诊断（网络、GPU/Torch、Docker、jtop、USB 摄像头、启动盘）+ 6 项外设检测（WiFi、5G、蓝牙、NVMe、摄像头、HDMI）
- 设备信息采集：型号（自动解析 Seeed Image Name）、L4T 版本、内存/存储使用、IP、温度
- `_DiagThread` 异步线程执行诊断，逐项回报结果
- 局域网扫描 **已在 `modules/remote/connector.py` 实现**（ThreadPoolExecutor 64 workers，2-4 秒扫完 /24 子网）
- `device_connected` / `device_disconnected` 事件已定义并在 `runner.py` 中触发
- 页面监听 `bus.device_connected`，SSH 连接后自动触发诊断

**剩余缺口：**
- 设备连接状态持久化（上次连接的设备记忆）未实现
- 诊断历史记录/趋势未实现

---

### 3. 开发调试 / 远程开发功能（90%） ⬆️ 原评估 65% 严重偏低

**已实现（远超原描述）：**
- `modules/remote/page.py`（1215 行）：**完整 UI**，4 大卡片区域 —— Claude API 配置、设备连接（IP/用户名/密码/扫描）、Jetson 初始化（串口）、6 个开发工具
- `connector.py`（94 行）：`check_ssh()` + `scan_local_network()` 均已完整实现，含自动子网检测、多线程扫描、重试机制、进度回调
- `core/runner.py`（285 行）：三种执行器（Local / SSHRunner / SerialRunner）全部实现，SSHRunner 含 keepalive(30)、sudo 密码注入
- `native_terminal.py`（172 行）：VT100 终端模拟器（基于 pyte），支持 ANSI 颜色、键盘输入
- **VS Code Remote SSH**：配置引导对话框
- **VS Code Server (Web)**：多镜像降级下载（3 个 mirror）、文件完整性校验（>52MB）、600s 超时、自动启动
- **Jupyter Lab**：安装 + 启动，实时日志
- **Remote Desktop**：x11vnc + noVNC（`desktop_remote.py` 170 行 + `desktop_dialog.py` 330 行）
- **AI Agent 安装**：Claude Code / Codex / OpenClaw CLI 安装器（`agent_install_dialog.py` 301 行）
- **网络共享**：Linux NAT + Windows ICS（`net_share.py` 247 行）
- **Jetson 初始化**：串口管理（`jetson_init.py` 1214 行），跨平台串口检测

**剩余缺口：**
- SSH 断线自动重连机制未实现（当前每次 run() 创建新连接）
- 连接配置持久化（保存上次连接）未完善

---

### 4. 应用市场功能（80%） ⬆️ 原评估 40% 严重偏低

**已实现（远超原描述）：**
- `modules/apps/page.py`（782 行）：**完整 UI**，非骨架。包含应用卡片（图标/名称/描述/分类标签/状态徽章/操作按钮）、安装对话框（命令预览 + 实时日志 + 开始/停止）
- `apps.json`：**4 个内置应用**（jtop、Jupyter、Node-RED、YOLOv26-GMSL）含完整的 install/run/check/uninstall/clean 命令
- `jetson_examples.json`：**21 个 jetson-examples 应用**（Audio/Vision/LLM/RAG 方向），通过 `registry.py` 自动合并加载
- **总计 25 个应用**
- `registry.py`（85 行）：智能合并加载，自动注入 reComputer bootstrap PATH
- **分类筛选**：动态提取分类 + "已安装" 特殊筛选，绿色高亮选中态
- **搜索**：实时搜索（名称/描述/ID，大小写不敏感）
- **状态检测**：三态系统（installed / checking / available），`_StatusCheckThread` 后台执行 `check_cmd`
- **安装/卸载/运行/清理**：全流程实现，含 L4T 版本兼容性检查、确认对话框、错误时自动注入 AI 助手
- **懒加载渲染**：每批 6 张卡片，防止 UI 卡顿

**剩余缺口：**
- 应用数量仍偏少（25 个，目标 40+），AI 推理、ROS 方向需要补充
- 应用更新检测（可更新状态）未实现
- 应用详情页 / 截图展示未实现

---

### 5. 环境一键配置功能（55%） ⬇️ 原评估 60% 略高

**已实现：**
- Skills 执行引擎（`engine.py` 525 行）覆盖了高频环境配置：PyTorch、Docker、jtop、Swap、性能模式等
- 32 个内置 Skill 分 5 类：驱动修复(6)、应用部署(11)、网络远程(5)、系统优化(5)、其他(5)
- `diagnostics.py` 提供基础的环境检测能力

**缺口（与原描述一致）：**
- **Preset（环境预设）概念完全未实现**：无法将多个 Skill 组合为"AI 开发环境"等套餐
- Preset 执行的顺序编排和依赖管理未实现
- 配置状态检测（已配置 / 未配置 / 版本不匹配）仅有基础诊断，无系统性的"环境健康度"评分
- UI 上无"推荐配置"引导流程

**规划不变。**

---

### 6. Skills 适配（55%） ⬆️ 原评估 15% 严重偏低

**已实现（远超原描述）：**
- `modules/skills/page.py`（933 行）：**完整 UI**，含搜索、分类筛选、分页（首批 20 + "加载全部"）、SkillGroup 聚合（同一 Skill 的 OpenClaw/Claude/Codex 多变体）
- `engine.py`（525 行）：32 内置 Skill + OpenClaw SKILL.md 解析（frontmatter + bash 代码块提取）+ `run_skill()` 含重试机制
- **外部 Skills**：283 个（OpenClaw 97 + Claude 96 + Codex 96），总计 **315 个 Skills**
- **AI Chat 联动已部分实现**：`inject_context()` 注入 Skill 预览、`inject_error()` 注入执行错误日志供 AI 分析
- Skills UI 的"问 AI"按钮调用 `assistant.inject_context()`，安装失败调用 `assistant.inject_error()`
- `skill_run_requested` / `skill_completed` 事件已在 `events.py` 定义

**剩余缺口：**
- `skill_run_requested` / `skill_completed` 事件已定义但**全局无 emit 调用**，事件链路未接通
- Skills 标准化 JSON Schema（供 AI Agent 通过 API 调用）未定义
- `ai_chat.py` → `bus.skill_run_requested` → 执行引擎的完整链路未接通
- OpenClaw manifest、依赖声明等完整规范支持未实现
- Skills 验证框架仅有 `verified` 布尔标志，无自动化验证流程
- Preset / 编排层未实现（与环境配置模块交叉）

---

### 完成度汇总

| 模块 | 原评估 | 实测 | 偏差原因 |
|------|--------|------|---------|
| 烧录 | 85% | **85%** | 准确，UI 未迁移 + 事件未接通 |
| 设备监控 | 70% | **90%** | page.py 已完整实现，局域网扫描已有 |
| 开发调试 | 65% | **90%** | page.py 1215 行完整，6 个开发工具全实现 |
| 应用市场 | 40% | **80%** | 25 个应用 + 完整 UI + 安装/卸载/筛选/搜索 |
| 环境配置 | 60% | **55%** | Preset 概念完全未实现，执行引擎有但编排层没有 |
| Skills适配 | 15% | **55%** | 315 个 Skills + 完整 UI + 部分 AI 联动，但事件链路未接通 |
