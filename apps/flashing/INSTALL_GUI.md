# GUI 安装和启动指南

## 快速安装

```bash
# 1. 进入项目目录
cd seeed-jetson-flash

# 2. 安装 PyQt5
pip install PyQt5

# 3. 重新安装项目（包含 GUI 依赖）
pip install -e .
```

## 启动 GUI

### 方法 1: 使用命令行工具

```bash
seeed-jetson-flash gui
```

### 方法 2: 直接运行 Python 模块

```bash
python -m seeed_jetson_flash.gui.main_window
```

### 方法 3: 使用测试脚本

```bash
python test_gui.py
```

## 验证安装

运行以下命令检查是否正确安装：

```bash
# 检查 CLI 是否可用
seeed-jetson-flash --help

# 应该看到 gui 命令
# Commands:
#   flash          刷写 Jetson 设备
#   gui            启动图形界面
#   list-products  列出所有支持的产品
#   recovery       显示进入 Recovery 模式的教程
```

## 故障排除

### 问题 1: 找不到 seeed-jetson-flash 命令

**解决方案**:
```bash
# 重新安装
pip uninstall seeed-jetson-flash
pip install -e .
```

### 问题 2: 提示 "无法启动 GUI，请安装 PyQt5"

**解决方案**:
```bash
pip install PyQt5
```

### 问题 3: Linux 下 GUI 无法显示

**解决方案**:
```bash
# 检查 DISPLAY 环境变量
echo $DISPLAY

# 如果为空，设置它
export DISPLAY=:0

# 或者使用 X11 转发（SSH）
ssh -X user@host
```

### 问题 4: 依赖冲突

**解决方案**:
```bash
# 创建新的虚拟环境
python -m venv venv-jetson
source venv-jetson/bin/activate  # Linux/Mac
# 或
venv-jetson\Scripts\activate  # Windows

# 安装
pip install PyQt5
pip install -e .
```

## 系统要求

- Python 3.6+
- PyQt5 5.15.0+
- Linux / macOS / Windows
- 显示器（GUI 模式）

## 下一步

启动 GUI 后：
1. 选择产品型号
2. 选择 L4T 版本
3. 查看 Recovery 教程
4. 开始刷写

详细使用说明请查看 [GUI_GUIDE.md](GUI_GUIDE.md)
