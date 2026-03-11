# Seeed Jetson Develop Tool — 上下文文档

## 项目背景

本项目原名 `seeed-jetson-flash`，最初只有烧录（刷机）功能。
根据 PRD 文档（`jetson_Develop_prd.docx`，V0.9），需要大幅扩展为完整的 **Jetson 开发工作台**。

PRD 核心定位：
> 设备管理是入口，Skills 是效率引擎，容器是交付载体，远程开发是长期留存抓手。

---

## 代码结构

```
seeed_jetson_flash/
│
├── core/                        # 共享基础层，所有模块依赖，不依赖任何模块
│   ├── __init__.py              # 导出 bus / Runner / DeviceInfo
│   ├── events.py                # ★ 全局事件总线（模块间通信唯一通道）
│   ├── runner.py                # 命令执行引擎（本地，可扩展 SSH）
│   ├── device.py                # DeviceInfo 数据类
│   └── config.py                # 全局配置持久化（~/.config/seeed-jetson-tool/）
│
├── modules/                     # 6 大功能模块，各自独立，互不直接 import
│   ├── flash/                   # ⚡ 烧录
│   │   ├── __init__.py          # 导出 build_page
│   │   ├── thread.py            # FlashThread（后台刷写线程）
│   │   ├── page.py              # 烧录页 UI（TODO: 从 main_window_v2 迁移）
│   │   └── data/                # 存放 l4t_data.json / product_images.json 副本
│   │
│   ├── devices/                 # 🖥 设备管理
│   │   ├── __init__.py          # 导出 build_page
│   │   ├── diagnostics.py       # ★ 诊断项定义（DIAG_ITEMS）+ run_all()
│   │   ├── page.py              # 设备管理页 UI（TODO: 从 main_window_v2 迁移）
│   │   └── data/                # 存放 recovery_guides.json 副本
│   │
│   ├── apps/                    # 📦 应用市场
│   │   ├── __init__.py          # 导出 build_page
│   │   ├── registry.py          # ★ 应用注册表，load_apps() / get_app()
│   │   ├── page.py              # 应用市场页 UI（TODO: 从 main_window_v2 迁移）
│   │   └── data/
│   │       └── apps.json        # 应用元数据（id/name/category/skill_id/status）
│   │
│   ├── skills/                  # 🤖 Skills
│   │   ├── __init__.py          # 导出 build_page / load_skills / run_skill
│   │   ├── engine.py            # ★ Skill 数据类 + load_skills() + run_skill()
│   │   ├── page.py              # Skills 页 UI（TODO: 从 main_window_v2 迁移）
│   │   └── data/
│   │       └── skills.json      # Skill 定义（id/commands/params/verified）
│   │
│   ├── remote/                  # 💻 远程开发
│   │   ├── __init__.py          # 导出 build_page
│   │   ├── connector.py         # ★ check_ssh() / scan_local_network()
│   │   └── page.py              # 远程开发页 UI（TODO: 从 main_window_v2 迁移）
│   │
│   └── community/               # 💬 社区
│       ├── __init__.py          # 导出 build_page
│       └── page.py              # 社区页 UI（TODO: 从 main_window_v2 迁移）
│
├── gui/                         # 主窗口壳，只负责组装各模块 page
│   ├── main_window_v2.py        # ★ 当前主力 UI（过渡期，含完整 UI 实现）
│   ├── main_window_sdk.py       # 旧版双语烧录 UI（保留兼容）
│   ├── main_window.py           # 最初版本（已废弃）
│   └── styles.py                # 旧版样式常量
│
├── data/                        # 原始数据（向后兼容旧入口）
│   ├── l4t_data.json
│   ├── product_images.json
│   └── recovery_guides.json
│
├── flash.py                     # JetsonFlasher 核心刷写逻辑（被 modules/flash 依赖）
├── recovery.py                  # Recovery 辅助逻辑
└── cli.py                       # CLI 入口
```

**根目录**

```
run_v2.py       # ★ 新版 UI 启动入口（python3 run_v2.py）
run_gui.py      # 旧版启动入口
prd_images/     # 从 PRD docx 提取的参考截图
  image1.png    # 图1：烧录流程界面
  image2.png    # 图2：设备管理首页
  image3.png    # 图3：应用空间
  image4.png    # 图4：示例应用市场
```

---

## 架构设计原则

### 模块间通信：事件总线

模块之间**不直接 import**，全部通过 `core/events.py` 的全局单例 `bus` 通信：

```python
from seeed_jetson_flash.core import bus

# 发出事件（任意模块）
bus.skill_run_requested.emit("usb_wifi")

# 监听事件（任意模块）
bus.skill_completed.connect(my_callback)
```

`bus` 上定义的信号：

| 信号 | 发出方 | 监听方 |
|------|--------|--------|
| `device_connected(dict)` | devices | flash / skills |
| `flash_completed(bool, str)` | flash | devices（触发体检）|
| `skill_run_requested(str)` | apps / devices | skills |
| `skill_completed(str, bool, str)` | skills | apps / devices |
| `app_install_requested(str)` | apps | skills |
| `navigate_to(int)` | 任意 | gui 主窗口 |

### 每个模块对外只暴露一个函数

```python
# 主窗口组装示例
from seeed_jetson_flash.modules.flash import build_page as flash_page
from seeed_jetson_flash.modules.devices import build_page as devices_page

stack.addWidget(flash_page(products, product_images))
stack.addWidget(devices_page())
```

### 并发开发分工

| 人员 | 负责目录 | 依赖 |
|------|---------|------|
| 开发 A | `modules/flash/` | 只依赖 `core/` + `flash.py` |
| 开发 B | `modules/devices/` + `modules/skills/` | 依赖 `core/runner` |
| 开发 C | `modules/apps/` + `modules/remote/` | 依赖 `core/device` |
| 开发 D | `gui/` 主窗口组装 + `core/` 基础层 | 无外部依赖 |

---

## main_window_v2.py 说明（过渡期）

当前 `gui/main_window_v2.py` 包含所有 6 个页面的完整 UI 实现，作为**视觉参考和过渡实现**。
各模块开发者的任务是把对应的 `_build_xxx_page()` 方法迁移到各自的 `modules/xxx/page.py`。

### 技术栈
- PyQt5，无边框窗口（`FramelessWindowHint`），自定义标题栏可拖动
- 深色主题，Seeed 绿（`#8DC21F`）+ 深蓝配色
- 6 页 `QStackedWidget` + 左侧 `SidebarButton` 导航

### 6 个页面迁移状态

| 页面 | main_window_v2 方法 | 目标文件 | 状态 |
|------|---------------------|---------|------|
| ⚡ 烧录 | `_build_flash_page` | `modules/flash/page.py` | 🔲 待迁移 |
| 🖥 设备管理 | `_build_devices_page` | `modules/devices/page.py` | 🔲 待迁移 |
| 📦 应用市场 | `_build_apps_page` | `modules/apps/page.py` | 🔲 待迁移 |
| 🤖 Skills | `_build_skills_page` | `modules/skills/page.py` | 🔲 待迁移 |
| 💻 远程开发 | `_build_remote_page` | `modules/remote/page.py` | 🔲 待迁移 |
| 💬 社区 | `_build_community_page` | `modules/community/page.py` | 🔲 待迁移 |

---

## PRD 要求的功能优先级

### P0（首版必做）
- [x] 烧录功能（已有，已集成到新 UI）
- [ ] 设备体检（网络/GPU Torch/Docker/jtop/摄像头）— 逻辑待实现
- [ ] Skills 执行引擎（参数化执行、状态回传、失败重试）
- [ ] 应用市场（卡片绑定 Demo + Skill + 容器 + 文档）
- [ ] 首批 4 个已验证 Skill 上线：
  - LeRobot 开发环境配置
  - USB-WiFi 驱动适配
  - Qwen Demo 适配
  - 浏览器无法打开修复

### P1（后续版本）
- [ ] 远程开发（VS Code Remote SSH / code-server / Jupyter）
- [ ] 社区内容回流（问题修复结果沉淀）
- [ ] 容器部署（vLLM / Ollama / ROS）

---

## 下一步任务建议

1. **设备体检逻辑**：在 `_build_devices_page` 中接入真实 SSH/本地命令执行，更新诊断项状态
2. **Skills 执行引擎**：设计 Skill 数据结构（JSON），实现参数化执行 + 日志回传
3. **应用市场数据化**：将硬编码的应用列表迁移到 `data/apps.json`
4. **Recovery 指南集成**：在社区页的 Recovery 入口接入 `recovery_guides.json` 数据
5. **样式细化**：对照 `prd_images/` 中的参考截图调整布局细节

---

## 运行方式

```bash
# 新版 UI（推荐）
python3 run_v2.py

# 旧版 UI
python3 run_gui.py
```

## 依赖

```
PyQt5
requests
python-docx  # 仅用于读取 PRD，运行时不需要
```
