#!/bin/bash
# 快速启动 GUI 的脚本

echo "=== Seeed Jetson Flash GUI 启动脚本 ==="
echo ""

# 检查 PyQt5
echo "检查 PyQt5..."
python -c "import PyQt5" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "✗ PyQt5 未安装"
    echo "正在安装 PyQt5..."
    pip install PyQt5
else
    echo "✓ PyQt5 已安装"
fi

echo ""
echo "启动 GUI..."
echo ""

# 启动 GUI
seeed-jetson-flash gui

# 如果上面失败，尝试直接运行
if [ $? -ne 0 ]; then
    echo ""
    echo "尝试直接运行..."
    python -m seeed_jetson_flash.gui.main_window
fi
