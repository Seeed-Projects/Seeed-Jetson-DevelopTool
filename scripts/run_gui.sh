#!/bin/bash
# 快速启动 GUI 的脚本

echo "=== Seeed Jetson Developer Tool GUI 启动脚本 ==="
echo ""

# 检查 qtpy / PyQt6
echo "检查 GUI 依赖..."
python -c "import qtpy, PyQt6" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "✗ qtpy / PyQt6 未安装"
    echo "正在安装 GUI 依赖..."
    pip install qtpy PyQt6
else
    echo "✓ qtpy / PyQt6 已安装"
fi

echo ""
echo "启动 GUI..."
echo ""

# 启动 GUI
python run_v2.py

# 如果上面失败，尝试直接运行模块
if [ $? -ne 0 ]; then
    echo ""
    echo "尝试直接运行..."
    python -m seeed_jetson_develop.gui.main_window_v2
fi
