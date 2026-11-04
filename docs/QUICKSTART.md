# 快速开始

## 安装

一键安装发布版：

```bash
pip install seeed-jetson-developer
seeed-jetson-developer
```

从源码安装运行：

```bash
git clone https://github.com/Seeed-Projects/Seeed-Jetson-DevelopTool.git
cd Seeed-Jetson-DevelopTool
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
seeed-jetson-developer
```

或直接运行仓库脚本：

```bash
python3 run_v2.py
```

需要终端输出调试日志时：

```bash
python3 run_v2.py --debug-console
```

## 验证安装

```bash
pip show seeed-jetson-developer
```

## 使用

启动后通过左侧导航使用各功能页：

- **烧录中心**：选择 Seeed Jetson 型号与 L4T 版本，下载 BSP、校验 SHA256、进入 Recovery 模式并烧录固件（Linux 原生 / Windows WSL2 + usbipd）。
- **远程连接**：SSH 连接 Jetson、局域网扫描、内置终端、首次开机串口初始化、网络共享。
- **设备管理**：采集系统信息、运行诊断、按 JetPack/L4T 安装匹配的 PyTorch 环境。
- **应用市场**：一键安装运行 YOLO、LLM、RAG、机器人等 Jetson 应用与示例。
- **Skills 中心**：安装 OpenClaw / Claude / Codex 格式的 Jetson 技能（SFTP 到已连接设备）。
- **OTA / 备份恢复 / 社区资源**：进阶功能说明见仓库根目录 `README.md`。

## 常见问题

### GUI 无法启动

- 确认有图形桌面会话：`echo $DISPLAY`；无头环境可安装 Xvfb：`sudo apt install xvfb`。
- 详细错误写入 `~/.cache/seeed-jetson/app.log`。

### 找不到 seeed-jetson-developer 命令

- 确认包安装在当前 Python 环境：`pip show seeed-jetson-developer`。
- 或改用 `python3 run_v2.py` 直接启动。

## 下一步

- 完整功能说明：[README.md](../README.md)
- 运行测试：`pytest`