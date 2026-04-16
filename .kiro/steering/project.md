# Seeed Jetson Develop Tool — 项目规范

## 平台兼容性

**所有代码必须同时兼容 Linux 和 Windows。**

- 涉及平台差异时用 `sys.platform == "win32"` 或 `platform.system()` 判断
- 文件路径统一用 `pathlib.Path`，不用字符串拼接
- shell 命令只在 Linux 下执行，Windows 下走对应的 PowerShell / Win32 API 实现
- iptables / sysctl / systemctl 等 Linux 专属命令必须有 `if sys.platform != "win32":` 保护
- GUI 组件（PyQt5）的行为在两个平台可能有差异，需实测验证

## 项目结构

- `seeed_jetson_develop/modules/flash/` — 烧录功能
- `seeed_jetson_develop/modules/remote/` — 远程桌面、网络共享
- `seeed_jetson_develop/modules/devices/` — 设备管理
- `seeed_jetson_develop/data/l4t_data.json` — 固件数据
- `seeed_jetson_develop/data/product_images.json` — 产品图片和文档链接
- `seeed_jetson_develop/core/runner.py` — SSH/Serial 执行器
- `seeed_jetson_develop/gui/theme.py` — UI 主题和组件

## 技术栈

- Python 3.10+
- PyQt5（GUI）
- paramiko（SSH）
- requests（HTTP 下载）
