"""
GUI 模块
"""
# 延迟导入，避免在导入时就加载 PyQt5
__all__ = ['MainWindow', 'main']

def __getattr__(name):
    if name == 'MainWindow':
        from .main_window import MainWindow
        return MainWindow
    elif name == 'main':
        from .main_window import main
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
