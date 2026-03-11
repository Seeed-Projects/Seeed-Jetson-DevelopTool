# Seeed Jetson Flash 使用指南

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

## 基本用法

### 1. 查看支持的产品列表

```bash
seeed-jetson-flash list-products
```

输出示例：
```
支持的产品列表：

  j3010mini
    L4T 版本: 36.4.3, 36.3.0, 35.5.0

  j3010s
    L4T 版本: 36.4.3

  j4012mini
    L4T 版本: 36.3.0, 35.5.0
  ...
```

### 2. 查看进入 Recovery 模式的教程

在刷机前，需要让设备进入 Recovery 模式：

```bash
seeed-jetson-flash recovery -p j4012mini
```

这会显示详细的步骤说明、所需设备、验证方法和参考图片。

### 3. 刷写固件

```bash
seeed-jetson-flash flash -p j4012mini -l 36.3.0
```

参数说明：
- `-p, --product`: 产品型号（必需）
- `-l, --l4t`: L4T 版本（必需）
- `--download-only`: 仅下载固件，不刷写
- `--skip-verify`: 跳过 SHA256 校验

### 4. 仅下载固件

如果只想下载固件而不立即刷写：

```bash
seeed-jetson-flash flash -p j4012mini -l 36.3.0 --download-only
```

## 完整刷机流程

### 步骤 1: 准备环境

确保你的 Ubuntu 主机已安装必要的依赖：

```bash
sudo apt-get update && \
sudo apt-get install -y abootimg \
                        binfmt-support \
                        binutils \
                        cpp \
                        device-tree-compiler \
                        dosfstools \
                        lbzip2 \
                        libxml2-utils \
                        nfs-kernel-server \
                        python3-yaml \
                        qemu-user-static \
                        sshpass \
                        udev \
                        uuid-runtime \
                        whois \
                        openssl \
                        cpio \
                        rsync \
                        zstd
```

对于 Ubuntu 20.04 及以上：
```bash
sudo apt-get install -y lz4
```

对于 Ubuntu 18.04 及以下：
```bash
sudo apt-get install -y liblz4-tool
```

### 步骤 2: 查看 Recovery 模式教程

```bash
seeed-jetson-flash recovery -p j4012mini
```

按照显示的步骤让设备进入 Recovery 模式。

### 步骤 3: 验证设备已进入 Recovery 模式

在终端执行：
```bash
lsusb
```

查看输出中是否包含 NVIDIA 设备 ID（例如 `0955:7323`）。

### 步骤 4: 刷写固件

```bash
seeed-jetson-flash flash -p j4012mini -l 36.3.0
```

刷写过程包括：
1. 下载固件（如果尚未下载）
2. 校验 SHA256
3. 解压固件
4. 刷写到设备

整个过程可能需要 2-10 分钟。

### 步骤 5: 首次启动配置

刷写完成后：
1. 将 Jetson 连接到显示器（HDMI 或 Type-C）
2. 完成系统初始化配置
3. （可选）安装 NVIDIA JetPack SDK

## 支持的产品系列

### reComputer Super 系列
- J4012s (Orin NX 16GB)
- J4011s (Orin NX 8GB)
- J3011s (Orin Nano 8GB)
- J3010s (Orin Nano 4GB)

### reComputer Mini 系列
- J4012mini (Orin NX 16GB)
- J4011mini (Orin NX 8GB)
- J3011mini (Orin Nano 8GB)
- J3010mini (Orin Nano 4GB)

### reComputer Robotics 系列
- J4012robotics (Orin NX 16GB)
- J4011robotics (Orin NX 8GB)
- J3011robotics (Orin Nano 8GB)
- J3010robotics (Orin Nano 4GB)

### reComputer Classic 系列
- J4012classic (Orin NX 16GB)
- J4011classic (Orin NX 8GB)
- J3011classic (Orin Nano 8GB)
- J3010classic (Orin Nano 4GB)

### reComputer Industrial 系列
- J4012industrial (Orin NX 16GB)
- J4011industrial (Orin NX 8GB)
- J3011industrial (Orin Nano 8GB)
- J3010industrial (Orin Nano 4GB)
- J2012industrial (Xavier NX 16GB)
- J2011industrial (Xavier NX 8GB)

## 数据文件说明

项目包含以下数据文件，从官方文档提取：

### 1. l4t_data.json
包含所有产品的固件下载链接、文件名、SHA256 校验值等信息。

### 2. recovery_guides.json
包含各系列产品进入 Recovery 模式的详细教程，包括：
- 所需设备列表
- 操作步骤
- 验证方法
- 参考图片链接
- 视频教程链接（如有）

### 3. product_images.json
包含各产品的图片链接和 Wiki 文档链接。

## 故障排除

### 设备未被检测到

如果 `lsusb` 未显示 NVIDIA 设备：
1. 重新插拔 USB 数据线
2. 更换 USB 接口（优先使用 USB 2.0）
3. 确认设备已正确进入 Recovery 模式
4. 检查 USB 线是否支持数据传输

### SHA256 校验失败

如果 SHA256 校验失败：
1. 删除已下载的固件文件
2. 重新下载
3. 检查网络连接是否稳定

### 刷写失败

如果刷写过程失败：
1. 确认设备在 Recovery 模式
2. 检查 USB 连接是否稳定
3. 确认主机有足够的磁盘空间
4. 查看错误日志获取详细信息

## 参考资源

- [Seeed Studio Wiki - Jetson Flash](https://wiki.seeedstudio.com/flash/jetpack_to_selected_product)
- [NVIDIA Jetson Linux](https://developer.nvidia.com/embedded/jetson-linux)
- [Seeed Studio 论坛](https://forum.seeedstudio.com/)

## 技术支持

如有问题，请访问：
- 论坛: https://forum.seeedstudio.com/
- 邮箱: support@seeedstudio.com
- Discord: https://discord.gg/eWkprNDMU7
