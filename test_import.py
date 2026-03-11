#!/usr/bin/env python3
"""测试导入"""
import sys
import traceback

try:
    print("Testing import...")
    from seeed_jetson_flash.gui.main_window import MainWindow
    print("✓ MainWindow imported successfully")
    print(f"MainWindow class: {MainWindow}")
except Exception as e:
    print(f"✗ Import failed: {e}")
    traceback.print_exc()
