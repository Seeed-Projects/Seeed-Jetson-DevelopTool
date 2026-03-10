# Seeed Jetson Flash

一个用于为多款 Seeed Studio Jetson 设备刷机的 Python 命令行工具。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)

## 特性

- 🚀 **简单易用**: 一条命令完成固件下载、校验和刷写
- 📦 **自动化**: 自动下载固件、解压、校验 SHA256
- 📖 **详细教程**: 内置各系列产品进入 Recovery 模式的详细教程
- 🎨 **美观输出**: 使用 Rich 库提供彩色、格式化的终端输出
- 🔒 **安全可靠**: SHA256 校验确保固件完整性
- 🌐 **多产品支持**: 支持 Seeed Studio 全系列 Jetson 产品

## 安装

### 从 PyPI 安装（推荐）

```bash
pip install seeed-jetson-flash
```

### 从源码安装

```bash
git clone https://github.com/Seeed-Studio/seeed-jetson-flash.git
cd seeed-jetson-flash
pip install -e .
```

## 快速开始

### 命令行模式

### 1. 查看支持的产品

```bash
seeed-jetson-flash list-products
```

### 2. 查看 Recovery 模式教程

```bash
seeed-jetson-flash recovery -p j4012mini
```

### 3. 刷写固件

```bash
seeed-jetson-flash flash -p j4012mini -l 36.3.0
```

### 图形界面模式

启动 GUI（需要安装 PyQt5）：

```bash
# 安装 PyQt5
pip install PyQt5

# 启动 GUI
seeed-jetson-flash gui
```

GUI 特性：
- 🎨 Seeed Studio 品牌风格设计
- 📱 直观的产品选择界面
- 📊 实时进度显示
- 📝 详细的操作日志
- 🔄 内置 Recovery 模式教程
- 🔗 快速访问相关链接

详细 GUI 使用说明请查看 [GUI_GUIDE.md](GUI_GUIDE.md)

## 支持的设备

### reComputer Super 系列
- J4012s (Orin NX 16GB) - L4T 36.4.3
- J4011s (Orin NX 8GB) - L4T 36.4.3
- J3011s (Orin Nano 8GB) - L4T 36.4.3
- J3010s (Orin Nano 4GB) - L4T 36.4.3

### reComputer Mini 系列
- J4012mini (Orin NX 16GB) - L4T 36.3.0, 35.5.0
- J4011mini (Orin NX 8GB) - L4T 36.3.0, 35.5.0
- J3011mini (Orin Nano 8GB) - L4T 36.4.3, 36.3.0, 35.5.0
- J3010mini (Orin Nano 4GB) - L4T 36.4.3, 36.3.0, 35.5.0

### reComputer Robotics 系列
- J4012robotics (Orin NX 16GB) - L4T 36.4.3
- J4011robotics (Orin NX 8GB) - L4T 36.4.3
- J3011robotics (Orin Nano 8GB) - L4T 36.4.3
- J3010robotics (Orin Nano 4GB) - L4T 36.4.3

### reComputer Classic 系列
- J4012classic (Orin NX 16GB) - L4T 36.4.3, 36.4.0, 36.3.0, 35.5.0
- J4011classic (Orin NX 8GB) - L4T 36.4.3, 36.4.0, 36.3.0, 35.5.0
- J3011classic (Orin Nano 8GB) - L4T 36.4.3, 36.4.0, 36.3.0, 35.5.0
- J3010classic (Orin Nano 4GB) - L4T 36.4.3, 36.4.0, 36.3.0, 35.5.0

### reComputer Industrial 系列
- J4012industrial (Orin NX 16GB)
- J4011industrial (Orin NX 8GB)
- J3011industrial (Orin Nano 8GB)
- J3010industrial (Orin Nano 4GB)
- J2012industrial (Xavier NX 16GB)
- J2011industrial (Xavier NX 8GB)

### reServer Industrial 系列
- J4012reserver, J4011reserver, J3011reserver, J3010reserver

### J501 系列
- J501 Carrier Board (AGX Orin 64GB/32GB)
- J501 Mini (AGX Orin 64GB/32GB)
- J501 Robotics (AGX Orin 64GB/32GB)

## 文档

- 📖 [README.md](README.md) - 项目介绍
- 🚀 [QUICKSTART.md](QUICKSTART.md) - 快速开始指南
- 📱 [GUI_GUIDE.md](GUI_GUIDE.md) - GUI 使用指南
- 💻 [USAGE.md](USAGE.md) - 命令行使用指南
- 📦 [INSTALL_GUI.md](INSTALL_GUI.md) - GUI 安装说明
- 📚 [RESOURCES.md](RESOURCES.md) - 资源提取说明
- 📝 [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - 项目总结

## 使用说明

详细使用说明请查看 [USAGE.md](USAGE.md)

## 资源说明

本项目从 Seeed Studio 官方文档中提取了以下资源：
- 固件下载链接和 SHA256 校验值
- Recovery 模式进入教程（含图片和视频）
- 产品图片和 Wiki 链接
- 多语言支持（中文、英文、日文、西班牙文）

详细资源说明请查看 [RESOURCES.md](RESOURCES.md)

## 项目结构

```
seeed-jetson-flash/
├── seeed_jetson_flash/
│   ├── __init__.py          # 包初始化
│   ├── cli.py               # 命令行接口
│   ├── flash.py             # 固件刷写模块
│   ├── recovery.py          # Recovery 教程模块
│   └── data/                # 数据文件
│       ├── l4t_data.json           # 固件信息
│       ├── recovery_guides.json    # Recovery 教程
│       └── product_images.json     # 产品图片
├── setup.py                 # 安装配置
├── requirements.txt         # 依赖包
├── README.md               # 项目说明
├── USAGE.md                # 使用指南
├── RESOURCES.md            # 资源说明
├── LICENSE                 # 许可证
└── MANIFEST.in             # 打包配置
```

## 依赖

- Python 3.6+
- requests
- tqdm
- click
- rich

## 开发

```bash
# 克隆仓库
git clone https://github.com/Seeed-Studio/seeed-jetson-flash.git
cd seeed-jetson-flash

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 以开发模式安装
pip install -e .
```

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 技术支持

- 📖 Wiki: https://wiki.seeedstudio.com/
- 💬 论坛: https://forum.seeedstudio.com/
- 📧 邮箱: support@seeedstudio.com
- 💬 Discord: https://discord.gg/eWkprNDMU7

## 相关资源

- [Seeed Jetson 初学者教程](https://github.com/Seeed-Projects/reComputer-Jetson-for-Beginners)
- [Jetson 示例代码](https://github.com/Seeed-Projects/jetson-examples)
- [Seeed L4T 源码](https://github.com/Seeed-Studio/Linux_for_Tegra)
- [NVIDIA Jetson Linux](https://developer.nvidia.com/embedded/jetson-linux)
