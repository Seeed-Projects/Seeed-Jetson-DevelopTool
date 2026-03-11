# 资源提取说明

本项目从 Seeed Studio 官方文档中提取了以下资源，用于构建 Jetson 刷机工具。

## 提取的资源

### 1. 固件数据 (L4TData.json)

**来源**: `src/data/jetson/L4TData.json`

**内容**:
- 产品型号 (product)
- L4T 版本 (l4t)
- 下载链接 (mainlink, mirrorlink)
- 文件名 (filename)
- 文件夹名 (foldername)
- SHA256 校验值 (sha256)

**示例**:
```json
{
    "product": "j4012mini",
    "l4t": "36.3.0",
    "mainlink": "https://seeedstudio88-my.sharepoint.com/...",
    "filename": "mfi_recomputer-mini-orin-nx-16g-j40-6.0-36.3.0.tar.gz",
    "foldername": "mfi_recomputer-mini-orin",
    "sha256": "C579FF60F6F140E43C592F784EA541791DD8F7DDA49924F36EFBB63196FC1C35"
}
```

### 2. Recovery 模式教程

**来源**: `docs/Edge/NVIDIA_Jetson/Flash_Jetpack.mdx` 和 `src/components/jetson/FlashCodeBlock.jsx`

**提取内容**:

#### reComputer Mini 系列
- **所需设备**: Ubuntu 主机、USB Micro-B 数据线
- **步骤**:
  1. 连接 USB Micro-B 线到 USB2.0 DEVICE 口
  2. 用针按住 RECOVERY 孔内的按钮
  3. 接通电源
  4. 松开 RECOVERY 按钮
- **验证**: `lsusb` 查看 USB ID
- **参考图片**:
  - https://files.seeedstudio.com/wiki/reComputer-Jetson/mini/reComputer_mini_rec.png
  - https://files.seeedstudio.com/wiki/reComputer-J4012/3.png
- **视频教程**: https://www.youtube.com/embed/HEIXFkizP5Y

#### reComputer Robotics 系列
- **所需设备**: Ubuntu 主机、USB Type-C 数据线
- **步骤**:
  1. 将拨码开关切至 RESET 档位
  2. 连接电源线
  3. 用 USB Type-C 线连接主机
  4. 执行 lsusb 验证
- **参考图片**:
  - https://files.seeedstudio.com/wiki/reComputer-Jetson/robotics_j401/flash1.jpg
  - https://files.seeedstudio.com/wiki/reComputer-Jetson/robotics_j401/lsusb_f.png

#### reComputer Super 系列
- **所需设备**: Ubuntu 主机、USB Type-C 数据线
- **步骤**: 与 Robotics 系列相同
- **参考图片**:
  - https://files.seeedstudio.com/wiki/reComputer-Jetson/super/flash1.jpg

#### reComputer Classic 系列
- **所需设备**: Ubuntu 主机、USB Type-C 数据线、跳线
- **步骤**:
  1. 用跳线短接 FC REC 与 GND 引脚
  2. 连接电源
  3. 用 USB Type-C 线连接主机
- **参考图片**:
  - https://files.seeedstudio.com/wiki/reComputer-J4012/2.png

#### reComputer Industrial 系列
- **所需设备**: Ubuntu 主机、USB Type-C 数据线、2针端子电源连接器
- **步骤**:
  1. 用 USB Type-C 线连接 DEVICE 口
  2. 用针按住 REC 孔内的按钮
  3. 连接 2针端子电源
  4. 松开 REC 按钮
- **参考图片**:
  - https://files.seeedstudio.com/wiki/reComputer-Industrial/2.png

### 3. 产品图片

**来源**: `docs/Edge/NVIDIA_Jetson/Flash_Jetpack.mdx` 中的 `productOptions` 数组

**提取的图片链接**:

| 产品系列 | 图片链接 |
|---------|---------|
| reComputer Super | https://media-cdn.seeedstudio.com/media/catalog/product/.../2-114110311-recomputer-super-j3010_1.jpg |
| reComputer Mini | https://files.seeedstudio.com/wiki/reComputer-Jetson/mini/1-reComputer-Mini-bundle.jpg |
| reComputer Robotics | https://media-cdn.seeedstudio.com/media/catalog/product/.../1-114110310-recomputer-robotics_2.jpg |
| reComputer Classic | https://media-cdn.seeedstudio.com/media/catalog/product/.../recomputer_classic_optional_accessories_nvidia_jetson_orin_powered_edge_ai_box.jpeg |
| reComputer Industrial | https://media-cdn.seeedstudio.com/media/catalog/product/.../1--recomputer-industrial-bundle.jpg |
| reServer Industrial | https://media-cdn.seeedstudio.com/media/catalog/product/.../1-114110247-reserver-industrial-j4012-first.jpg |

### 4. 文字教程

**来源**: `src/components/jetson/FlashCodeBlock.jsx` 中的多语言内容

**提取的文字内容**:
- SHA256 校验说明
- 所需设备列表
- Recovery 模式进入步骤
- 设备检测方法
- USB ID 对照表
- 故障排除建议
- 刷写流程说明

### 5. 相关链接

**Wiki 文档链接**:
- reComputer Super: https://wiki.seeedstudio.com/recomputer_jetson_super_hardware_interfaces_usage/
- reComputer Mini: https://wiki.seeedstudio.com/recomputer_jetson_mini_hardware_interfaces_usage/
- reComputer Robotics: https://wiki.seeedstudio.com/recomputer_jetson_robotics_j401_getting_started/
- reComputer Classic: https://wiki.seeedstudio.com/J401_carrierboard_Hardware_Interfaces_Usage/
- reComputer Industrial: https://wiki.seeedstudio.com/reComputer_Industrial_J40_J30_Hardware_Interfaces_Usage/
- reServer Industrial: https://wiki.seeedstudio.com/reserver_industrial_hardware_interface_usage/

**其他资源**:
- Seeed Jetson 初学者教程: https://github.com/Seeed-Projects/reComputer-Jetson-for-Beginners
- Jetson 示例代码: https://github.com/Seeed-Projects/jetson-examples
- Seeed L4T 源码: https://github.com/Seeed-Studio/Linux_for_Tegra

## USB Device ID 对照表

| 模块 | USB ID | 说明 |
|------|--------|------|
| Orin NX 16GB | 0955:7323 | NVidia Corp |
| Orin NX 8GB | 0955:7423 | NVidia Corp |
| Orin Nano 8GB | 0955:7523 | NVidia Corp |
| Orin Nano 4GB | 0955:7623 | NVidia Corp |
| Xavier NX | 0955:7e19 | NVidia Corp |
| AGX Orin 32GB | 0955:7023 | NVidia Corp |
| AGX Orin 64GB | 0955:7023 | NVidia Corp |

## 主机环境要求

| JetPack 版本 | L4T 版本 | Ubuntu 版本 (主机) |
|-------------|---------|-------------------|
| 6.2 | 36.4.3 | 20.04 / 22.04 |
| 6.1 | 36.4.0 | 20.04 / 22.04 |
| 6.0 | 36.3.0 | 20.04 / 22.04 |
| 5.1.3 | 35.5.0 | 18.04 / 20.04 |
| 5.1.1 | 35.3.1 | 18.04 / 20.04 |

## 依赖包列表

从文档中提取的必需依赖包：

```bash
abootimg
binfmt-support
binutils
cpp
device-tree-compiler
dosfstools
lbzip2
libxml2-utils
nfs-kernel-server
python3-yaml
qemu-user-static
sshpass
udev
uuid-runtime
whois
openssl
cpio
rsync
zstd
lz4 (Ubuntu 20.04+) 或 liblz4-tool (Ubuntu 18.04-)
```

## 提取方法

资源提取使用以下方法：

1. **JSON 数据**: 直接从 `src/data/jetson/L4TData.json` 读取
2. **React 组件**: 从 `src/components/jetson/FlashCodeBlock.jsx` 提取多语言文本和步骤
3. **MDX 文档**: 从 `docs/Edge/NVIDIA_Jetson/Flash_Jetpack.mdx` 提取产品信息和图片链接
4. **图片链接**: 通过正则表达式搜索 `.mdx` 文件中的图片 URL
5. **文字内容**: 从 React 组件的 `content` 对象中提取中文、英文、日文、西班牙文内容

## 版权说明

所有资源均来自 Seeed Studio 官方文档，版权归 Seeed Studio 所有。本工具仅用于方便用户刷写 Jetson 设备，不得用于商业用途。
