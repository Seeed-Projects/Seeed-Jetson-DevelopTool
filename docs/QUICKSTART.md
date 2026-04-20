# 快速开始

## 安装

```bash
# 1. 克隆或进入项目目录
cd seeed-jetson-flash

# 2. 安装依赖（包括 GUI）
pip install PyQt5

# 3. 安装项目
pip install -e .
```

## 验证安装

```bash
# 运行验证脚本
python verify_install.py

# 或者检查命令是否可用
seeed-jetson-flash --help
```

## 使用

### 方式 1: 图形界面（推荐）

```bash
seeed-jetson-flash gui
```

### 方式 2: 命令行

```bash
# 查看支持的产品
seeed-jetson-flash list-products

# 查看 Recovery 教程
seeed-jetson-flash recovery -p j4012mini

# 刷写固件
seeed-jetson-flash flash -p j4012mini -l 36.3.0
```

## 故障排除

### GUI 无法启动

1. **检查 PyQt5**:
   ```bash
   python -c "import PyQt5; print('PyQt5 OK')"
   ```

2. **重新安装**:
   ```bash
   pip uninstall seeed-jetson-flash
   pip install -e .
   ```

3. **直接运行**:
   ```bash
   python -m seeed_jetson_develop.gui.main_window
   ```

4. **使用启动脚本**:
   ```bash
   bash RUN_GUI.sh
   ```

### 找不到命令

```bash
# 确保安装在正确的环境
which python
which pip

# 重新安装
pip install -e .

# 检查安装位置
pip show seeed-jetson-flash
```

## 下一步

- 查看 [GUI_GUIDE.md](GUI_GUIDE.md) 了解 GUI 详细使用
- 查看 [USAGE.md](USAGE.md) 了解命令行详细使用
- 查看 [RESOURCES.md](RESOURCES.md) 了解资源说明
