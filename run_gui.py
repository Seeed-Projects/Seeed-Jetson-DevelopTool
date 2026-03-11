#!/usr/bin/env python3
"""
独立的 GUI 启动脚本
直接运行: python run_gui.py
"""
import sys
import os

# 添加项目路径
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# 清除缓存
for key in list(sys.modules.keys()):
    if 'seeed_jetson_flash' in key:
        del sys.modules[key]

def main():
    try:
        from PyQt5.QtWidgets import QApplication
        
        # 直接导入模块内容，不通过包
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "main_window", 
            os.path.join(project_dir, "seeed_jetson_flash", "gui", "main_window.py")
        )
        main_window = importlib.util.module_from_spec(spec)
        
        # 先加载 styles
        styles_spec = importlib.util.spec_from_file_location(
            "styles",
            os.path.join(project_dir, "seeed_jetson_flash", "gui", "styles.py")
        )
        styles = importlib.util.module_from_spec(styles_spec)
        sys.modules['seeed_jetson_flash.gui.styles'] = styles
        styles_spec.loader.exec_module(styles)
        
        # 加载 flash 模块
        flash_spec = importlib.util.spec_from_file_location(
            "flash",
            os.path.join(project_dir, "seeed_jetson_flash", "flash.py")
        )
        flash = importlib.util.module_from_spec(flash_spec)
        sys.modules['seeed_jetson_flash.flash'] = flash
        flash_spec.loader.exec_module(flash)
        
        spec.loader.exec_module(main_window)
        
        app = QApplication(sys.argv)
        app.setApplicationName("Seeed Jetson Flash")
        
        window = main_window.MainWindow()
        window.show()
        
        sys.exit(app.exec_())
        
    except Exception as e:
        import traceback
        print(f"错误: {e}")
        traceback.print_exc()
        print("\n请安装 PyQt5:")
        print("  pip install PyQt5")
        sys.exit(1)

if __name__ == '__main__':
    main()
