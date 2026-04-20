# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 运行与开发

```bash
# 启动 GUI（主入口）
python run_v2.py

# 安装依赖
pip install -r requirements.txt

# 语法检查
python -m py_compile seeed_jetson_develop/gui/main_window_v2.py

# 快速验证窗口能否创建（无需显示器）
python -c "
import sys, os
os.environ['NO_AT_BRIDGE']='1'; os.environ['QT_ACCESSIBILITY']='0'
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
app = QApplication(sys.argv)
from seeed_jetson_develop.gui.main_window_v2 import MainWindowV2
w = MainWindowV2(); print('OK')
"

# CLI 模式
python -m seeed_jetson_develop.cli flash -p j4012mini -l 36.3.0
python -m seeed_jetson_develop.cli list-products
```

## 架构

### 分层结构

```text
core/          ← 基础层，无任何业务依赖
modules/       ← 6 个功能模块，互不直接 import
gui/           ← 主窗口壳，只负责组装各模块 page
```

### 模块间通信：事件总线（唯一合法跨模块通道）

```python
from seeed_jetson_develop.core import bus
bus.skill_run_requested.emit("usb_wifi")   # 发出
bus.skill_completed.connect(my_callback)   # 监听
```

信号定义在 `core/events.py`：`device_connected`, `device_disconnected`, `diagnostics_done`, `flash_started`, `flash_completed`, `skill_run_requested`, `skill_completed`, `app_install_requested`, `app_installed`, `navigate_to`。

### 每个模块对外只暴露 `build_page()`

```python
from seeed_jetson_develop.modules.apps import build_page as apps_page
stack.addWidget(apps_page())
```

### 命令执行引擎

- `core/runner.py` — `Runner`（本地）/ `SSHRunner`（paramiko 远程）/ `SerialRunner`（串口）
- `get_runner()` 返回全局活跃 runner，`set_runner()` 切换
- 模块内执行命令统一用 `get_runner().run(cmd)`，不直接调用 subprocess
- SSHRunner 已配置 `set_keepalive(30)` 防止空闲断连

### 主题系统

`gui/theme.py` 是唯一样式来源，所有模块页面从此 import：

```python
from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_CARD, C_CARD_LIGHT,
    C_GREEN, C_BLUE, C_ORANGE, C_RED,
    C_TEXT, C_TEXT2, C_TEXT3,
    pt as _pt, make_label as _lbl, make_button as _btn,
    make_card as _card, make_input_card as _input_card,
    apply_shadow as _shadow,
)
```

设计原则：无边框，用背景色层次区分深度，阴影代替硬边框。颜色：`C_BG=#0D1822`，`C_GREEN=#8DC21F`。

## 关键约定

- **`pt()` 别名**：theme 导入时必须用 `pt as _pt`，页面内统一用 `_pt()`，不能裸调用 `pt()`
- **Windows 开发**：`core.fileMode = false` 已配置，`.sh` 文件权限变化不会出现在 git diff
- **Skills 数据**：`modules/skills/data/skills.json`，通过 `engine.load_skills()` 加载
- **Apps 数据**：`modules/apps/data/apps.json`，通过 `registry.load_apps()` 加载；jetson-examples 类应用统一用 `bash -c 'export PATH=$HOME/.local/bin:$PATH && reComputer run <name>'`，避免 SSH PATH 缺失 `~/.local/bin`
- **配置持久化**：`core/config.py`，存储路径 `~/.config/seeed-jetson-tool/`
- **日志**：运行时写入 `~/.cache/seeed-jetson/app.log`

## 当前迁移状态

`gui/main_window_v2.py` 仍直接实现了烧录页（`_build_flash_page`）和社区页（`_build_community_page`），其余 4 个页面已迁移到各自 `modules/xxx/page.py`。

### 页面加载策略

- Flash、Devices、Remote、Community：启动时立即构建
- **Apps (index=2)、Skills (index=3)：延迟加载** — 在 `_set_page()` 中，首次切换到该页面时用 `build_page()` 替换占位 placeholder widget

## AI 助手

- **实现**：`gui/ai_chat.py` — `AIChatPanel`（聊天面板）+ `FloatingAIAssistant`（浮动球 + 面板容器）
- **浮动面板**：悬浮在主窗口上方，球可拖拽吸附边缘，面板动态适应窗口大小（最小 280×300）
- **模型**：调用 `claude-haiku-4-5-20251001`，支持 `run_ssh_command` tool_use 在设备上执行命令
- **SSH 状态同步**：`show_panel()` 和 `_fire_ai()` 均从全局 `get_runner()` 同步 runner，badge 显示 "SSH ✓" 或 "无设备"
- **安全**：`_DANGEROUS_PATTERNS` 拦截 `rm -rf /`、`dd`、`mkfs` 等破坏性命令
- **外部调用**：`inject_context()`（Skills 注入）、`inject_topic()`（社区话题）、`inject_error()`（错误日志分析）

## YOLOv26 Dual GMSL 应用（apps.json）

Wiki 参考：https://wiki.seeedstudio.com/ai_roboticsyolov26_dual_camera_system/

apps.json 中 `yolov26-dual-gmsl` 条目已与 wiki GMSL 版对齐：
- **torch**: `2.5.0a0+872d972e41.nv24.08`（ultralytics assets wheel）
- **torchvision**: `0.20.0a0+afc54f7`
- **模型名**: `yolov26n.pt` / `yolov26n-pose.pt` / `yolov26n-seg.pt`（有 v）
- **运行脚本**: `run_dual_gmsl_local.sh`（GMSL 版专用）
- **安装方式**: `pip install --user`（无 conda），14 步顺序安装
- **注意**：skills 目录里的 `run_dual_camera_local.sh` 和 `yolo26n`（无 v）是 **USB 摄像头版本**，两套脚本不要混用

## 已完成的 P0 功能

- 局域网扫描：`modules/remote/connector.py`，ThreadPoolExecutor(64)，自动检测子网
- Skills 重试：`modules/skills/engine.py`，`run_skill(max_retries=N)`
- 设备体检：`modules/devices/diagnostics.py` + `page.py`，真实命令已接入
- 应用市场卸载：`page.py` + `apps.json` 每条加 `uninstall_cmds`
- 应用状态检测：未连接时重置为 available，连接后自动触发检测
- code-server 多镜像降级下载：`modules/remote/page.py`
- SSH keepalive：`core/runner.py`
- Jupyter check_cmd：`python3 -m jupyter --version` 规避 SSH PATH 问题
