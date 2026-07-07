# Seeed Jetson Develop Tool

Seeed Jetson Develop Tool 是面向 Seeed Jetson 开发者的桌面客户端。它把 Jetson 开发过程中最常用的步骤集中到一个 GUI 中：固件烧录、首次开机初始化、设备诊断、远程开发、应用部署、Skills 自动化、OTA 升级和社区资源入口。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey.svg)]()
[![PyPI Downloads](https://static.pepy.tech/badge/seeed-jetson-developer)](https://pepy.tech/project/seeed-jetson-developer)
[![PyPI Downloads / month](https://static.pepy.tech/badge/seeed-jetson-developer/month)](https://pepy.tech/project/seeed-jetson-developer)

[English](https://github.com/Seeed-Projects/Seeed-Jetson-DevelopTool/blob/main/README.md)

### PyPI 下载趋势

![PyPI Downloads Trend](https://raw.githubusercontent.com/Seeed-Projects/Seeed-Jetson-DevelopTool/main/assets/downloads-chart.svg)

![UI 预览](https://raw.githubusercontent.com/Seeed-Projects/Seeed-Jetson-DevelopTool/main/assets/Reference-UI.png)

## 这个客户端能做什么

| 模块 | 用途 |
| --- | --- |
| 烧录中心 | 选择 Seeed Jetson 型号和 L4T 版本，下载 BSP，校验 SHA256，解压固件，检测 Recovery 模式并执行烧录。 |
| 远程连接 | 通过 SSH 连接 Jetson，扫描局域网主机，打开终端，完成首次开机串口初始化，并把 PC 网络共享给 Jetson。 |
| 设备管理 | 采集 Jetson 系统信息，运行诊断，检查外设，并按 JetPack/L4T 安装匹配的 PyTorch 环境。 |
| 应用市场 | 安装和运行 Jetson 应用与示例，例如 Jupyter Lab、Node-RED、jtop、YOLO/GMSL、Depth Anything、LLM、RAG、音频和机器人示例。 |
| Skills 中心 | 浏览并安装 OpenClaw、Claude、Codex 格式的 Jetson 技能，用于部署、排障、AI、CV、机器人、网络和系统调优。 |
| OTA 升级 | 按向导执行已支持的 JetPack/L4T OTA 升级路径。 |
| 社区资源 | 打开 Seeed Wiki、论坛、GitHub、视频资源、NVIDIA NGC、Hugging Face 和产品购买链接。 |

当前命令行入口用于启动 GUI。产品选择、烧录、OTA、应用安装和 Skills 工作流都在桌面客户端中完成。

## 系统要求

- Python 3.8 或更新版本。
- 运行 PyQt6 GUI（通过 qtpy）需要图形桌面环境。
- 固件烧录推荐使用 Ubuntu 20.04 / 22.04 / 24.04 主机。
- Windows 可运行 GUI，并提供 WSL2 + usbipd 辅助烧录流程；如果要做稳定量产或频繁烧录，仍建议使用原生 Ubuntu。
- 远程开发、应用安装、Skills 安装、网络诊断和 OTA 需要 Jetson 已开启 SSH。
- 下载 BSP、应用依赖、OTA 包、Skills 依赖或刷新 BSP 元数据时需要联网。

Python 依赖在 `pyproject.toml` 中声明，主要包括 qtpy + PyQt6、paramiko、requests、pyserial、pyte、rich、tqdm、click 和 anthropic。

## 安装和启动

安装发布包：

```bash
pip install seeed-jetson-developer
seeed-jetson-developer
```

从源码安装：

```bash
git clone https://github.com/Seeed-Projects/Seeed-Jetson-DevelopTool.git
cd Seeed-Jetson-DevelopTool
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
seeed-jetson-developer
```

在仓库中直接运行：

```bash
python3 run_v2.py
```

需要在终端输出调试日志时：

```bash
python3 run_v2.py --debug-console
```

## 推荐使用流程

1. 打开 **烧录中心**，选择目标产品和 L4T 版本。
2. 下载并解压 BSP。已有固件压缩包会优先复用本地缓存。
3. 根据页面中的 Recovery 指南让设备进入 Recovery 模式，然后点击 **检测设备**。
4. 开始烧录。Linux 下执行 NVIDIA initrd massflash 流程；Windows 下走 WSL2 + usbipd 辅助流程。
5. 烧录完成后，如有需要，在 **远程连接** 页面使用 **Jetson 初始化** 通过串口完成首次开机设置。
6. 通过 SSH 连接 Jetson，然后继续使用设备管理、应用市场、Skills、远程桌面、Jupyter、VS Code Server 或 OTA。

## 主要功能

### 固件烧录

- 根据内置 BSP 元数据匹配产品型号和 L4T 版本。
- 启动时可从 Seeed Wiki 仓库刷新 BSP 元数据；离线时使用内置或本地缓存数据。
- 支持固件断点续传、可用时多线程分片下载、SHA256 校验和自动解压。
- 检测 NVIDIA APX Recovery USB ID。
- 内置不同产品系列的 Recovery 指南，包括所需线缆、操作步骤、USB ID 和参考图片。
- 支持清理本地压缩包缓存和解压工作目录。
- Windows 下提供 WSL2、usbipd-win、USB attach、WSL 解压和烧录辅助。

固件缓存目录：

```text
~/jetson_firmware
```

### 远程开发

- SSH 连接，支持用户名、密码、sudo 密码和密钥认证。
- 局域网 SSH 主机扫描。
- 内置终端入口。
- VS Code Remote SSH 使用引导。
- 一键部署 code-server，在浏览器中使用 VS Code。
- 在 Jetson 上安装并启动 Jupyter Lab。
- 部署 VNC/noVNC 远程桌面，支持无显示器场景下的 Xvfb fallback。
- PC 网络共享，自动配置网关、DNS 和代理。
- 串口首次开机初始化和串口网络配置。
- 安装 Claude Code CLI、Codex CLI 和 OpenClaw。

### 设备管理

- 采集设备型号、L4T/JetPack、Kernel、磁盘、内存和网络等信息。
- 检查网络、PyTorch/CUDA、Docker、jtop、摄像头和磁盘状态。
- 检查常见外设，例如 USB Wi-Fi、5G 模块、蓝牙、NVMe、视频设备和 HDMI。
- 根据检测到的 JetPack/L4T 与 Python 环境生成兼容的 PyTorch 安装命令。

### 应用市场

应用市场会加载内置应用和从 Jetson Examples 生成的应用条目，可在 Jetson 本机执行，也可通过当前 SSH 连接远程安装和运行。

覆盖方向包括：

- 开发工具：jtop、Jupyter Lab、Node-RED、浏览器工具。
- 计算机视觉：YOLO、DeepStream 类工作流、GMSL 示例、Depth Anything。
- LLM 与生成式 AI：本地模型示例、RAG/向量数据库、Llama、Qwen、LLaVA 类示例。
- 音频与语音示例。
- Robotics 和 ROS 示例。

### Skills 中心

客户端内置多种格式的技能库：

- OpenClaw skills：`skills/openclaw/`
- Claude skills：`skills/claude/`
- Codex skills：`skills/codex/`

Skills 会按主题聚合展示，并可通过 SFTP 安装到已连接的 Jetson。覆盖烧录、JetPack 环境、PyTorch、Docker、摄像头、VNC、OTA、USB Wi-Fi、LLM、CV 示例、机器人工作流和系统排障等场景。

### OTA 升级

OTA 页面提供四步向导：

1. 选择支持 OTA 的产品。
2. 通过 SSH 连接设备并检测当前 JetPack/L4T。
3. 匹配可用 OTA 路径并下载 payload。
4. 传输文件、执行预检查、运行 OTA 并处理重启。

当前内置 OTA 路径主要覆盖部分 J401、J301、reServer、Industrial 和 Orin Nano Dev Kit 设备从 JetPack 5.1.3 / L4T 35.5.0 升级到 JetPack 6.2 / L4T 36.4.3。实际可用路径以客户端页面展示为准。

## 支持硬件

内置 BSP 元数据当前覆盖 30+ 个产品条目，主要包括：

- reComputer Super、Mini、Robotics、Classic、Industrial
- reServer Industrial
- reComputer / reServer J501 AGX Orin 载板变体
- NVIDIA Jetson Orin Nano Developer Kit Super
- Xavier NX J201 Industrial 变体

可用 L4T 版本来自 `seeed_jetson_develop/data/l4t_data.json`，并可在运行时从 Seeed Wiki 数据源刷新。因此准确的型号和版本组合以客户端界面为准。

## 运行时文件

| 路径 | 用途 |
| --- | --- |
| `~/.cache/seeed-jetson/app.log` | GUI 启动和运行日志。 |
| `~/jetson_firmware` | 已下载和已解压的 BSP 固件包。 |
| `~/.cache/seeed-jetson-develop/data` | 刷新后的 BSP 元数据缓存。 |
| `~/.cache/seeed-jetson/ota` | OTA payload 和工具缓存。 |

## 常见问题

### Linux 下 GUI 无法启动

先确认当前会话有可用的图形显示：

```bash
echo $DISPLAY
```

如果是无头环境或 X11 连接受限，可安装 Xvfb：

```bash
sudo apt install xvfb
```

详细错误会写入 `~/.cache/seeed-jetson/app.log`。

### 检测不到 Recovery 设备

- 使用支持数据传输的 USB 线。
- 按所选产品页面中的 Recovery 指南让 Jetson 进入 Recovery 模式。
- Linux 下使用 `lsusb` 检查是否存在 NVIDIA 设备，例如 `0955:7323`、`0955:7423`、`0955:7523`、`0955:7623` 或 `0955:7023`。
- Windows 下确认 WSL2 和 usbipd-win 可用，并允许 USB attach 权限提示。

### 远程工具不可用

Jupyter、VS Code Server、远程桌面、应用市场远程安装、Skills 安装和 OTA 都依赖 SSH。请先在 **远程连接** 页面输入 Jetson IP、用户名和密码并连接成功。

### 应用或 Skill 安装失败

多数安装命令会在 Jetson 上执行。请确认 Jetson 可以联网、DNS 正常、磁盘空间充足。必要时可在 **远程连接** 页面使用 **PC 网络共享**。

## 开发

源码开发运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python3 run_v2.py
```

运行测试：

```bash
pytest
```

项目结构：

```text
seeed_jetson_develop/
  gui/                 Qt 主窗口、主题、i18n 和通用组件（通过 qtpy + PyQt6）
  modules/flash/       烧录页面和烧录线程
  modules/remote/      SSH、串口初始化、VNC/noVNC、网络共享
  modules/devices/     设备诊断和 PyTorch 安装支持
  modules/apps/        应用市场注册表和安装器
  modules/skills/      Skill 扫描、聚合和安装
  modules/ota/         OTA 向导和执行线程
  data/                BSP、产品图片和 Recovery 元数据
  skills/              内置 OpenClaw、Claude、Codex 技能库
```

## 链接

- Seeed Wiki: https://wiki.seeedstudio.com/
- Seeed Forum: https://forum.seeedstudio.com/
- Seeed GitHub: https://github.com/Seeed-Studio
- NVIDIA NGC: https://catalog.ngc.nvidia.com/
- Hugging Face: https://huggingface.co/

## License

MIT
