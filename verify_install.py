#!/usr/bin/env python3
"""
验证安装脚本
"""
import sys

def check_module(module_name, import_statement):
    """检查模块是否可以导入"""
    try:
        exec(import_statement)
        print(f"✓ {module_name}")
        return True
    except Exception as e:
        print(f"✗ {module_name}: {e}")
        return False

print("=== Seeed Jetson Flash 安装验证 ===\n")

print("检查核心模块:")
check_module("seeed_jetson_flash", "import seeed_jetson_flash")
check_module("cli", "from seeed_jetson_flash import cli")
check_module("flash", "from seeed_jetson_flash import flash")
check_module("recovery", "from seeed_jetson_flash import recovery")

print("\n检查数据文件:")
check_module("l4t_data.json", "import json; from pathlib import Path; json.load(open(Path('seeed_jetson_flash/data/l4t_data.json')))")
check_module("product_images.json", "import json; from pathlib import Path; json.load(open(Path('seeed_jetson_flash/data/product_images.json')))")
check_module("recovery_guides.json", "import json; from pathlib import Path; json.load(open(Path('seeed_jetson_flash/data/recovery_guides.json')))")

print("\n检查 GUI 模块:")
gui_ok = check_module("PyQt5", "import PyQt5")
if gui_ok:
    check_module("gui.styles", "from seeed_jetson_flash.gui import styles")
    check_module("gui.main_window", "from seeed_jetson_flash.gui import main_window")
    check_module("MainWindow", "from seeed_jetson_flash.gui.main_window import MainWindow")
    check_module("main function", "from seeed_jetson_flash.gui.main_window import main")
else:
    print("  (跳过 GUI 检查，PyQt5 未安装)")

print("\n=== 验证完成 ===")
