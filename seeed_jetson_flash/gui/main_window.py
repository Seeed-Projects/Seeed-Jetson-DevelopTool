"""主窗口 (refactor pending)"""
import sys
import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QComboBox, QProgressBar,
    QTextEdit, QGroupBox, QTabWidget, QMessageBox,
    QCheckBox, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from .styles import MAIN_STYLE, SEEED_GREEN, SEEED_BLUE
from ..flash import JetsonFlasher


class FlashThread(QThread):
    """刷写线程"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, product, l4t_version, skip_verify=False):
        super().__init__()
        self.product = product
        self.l4t_version = l4t_version
        self.skip_verify = skip_verify
    
    def run(self):
        try:
            flasher = JetsonFlasher(self.product, self.l4t_version)
            
            self.progress.emit("正在下载固件...")
            if not flasher.download_firmware():
                self.finished.emit(False, "固件下载失败")
                return
            
            if not self.skip_verify:
                self.progress.emit("正在校验 SHA256...")
                if not flasher.verify_firmware():
                    self.finished.emit(False, "SHA256 校验失败")
                    return
            
            self.progress.emit("正在解压固件...")
            if not flasher.extract_firmware():
                self.finished.emit(False, "固件解压失败")
                return
            
            self.progress.emit("正在刷写固件...")
            if not flasher.flash_firmware():
                self.finished.emit(False, "固件刷写失败")
                return
            
            self.finished.emit(True, "刷写完成！")
        
        except Exception as e:
            self.finished.emit(False, f"错误: {str(e)}")


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.data_path = Path(__file__).parent.parent / "data"
        self.load_data()
        self.init_ui()
    
    def load_data(self):
        """加载数据"""
        with open(self.data_path / "l4t_data.json", 'r') as f:
            self.l4t_data = json.load(f)
        
        with open(self.data_path / "product_images.json", 'r') as f:
            self.product_images = json.load(f)
        
        with open(self.data_path / "recovery_guides.json", 'r', encoding='utf-8') as f:
            self.recovery_guides = json.load(f)
        
        self.products = {}
        for item in self.l4t_data:
            product = item['product']
            if product not in self.products:
                self.products[product] = []
            self.products[product].append(item['l4t'])
    
    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("Seeed Jetson Flash Tool")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(MAIN_STYLE)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        self.create_header(main_layout)
        
        tabs = QTabWidget()
        tabs.addTab(self.create_flash_tab(), "⚡ 刷写固件")
        tabs.addTab(self.create_recovery_tab(), "🔄 Recovery 模式")
        tabs.addTab(self.create_about_tab(), "ℹ️ 关于")
        main_layout.addWidget(tabs)
        
        self.statusBar().showMessage("就绪")

    
    def create_header(self, layout):
        """创建标题栏"""
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 {SEEED_BLUE},
                                            stop:1 {SEEED_GREEN});
                border-radius: 10px;
                padding: 20px;
            }}
        """)
        
        header_layout = QHBoxLayout(header)
        
        title = QLabel("🚀 Seeed Jetson Flash Tool")
        title.setStyleSheet("color: white; font-size: 28px; font-weight: bold;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        version = QLabel("v0.1.0")
        version.setStyleSheet("color: white; font-size: 14px;")
        header_layout.addWidget(version)
        
        layout.addWidget(header)
    
    def create_flash_tab(self):
        """创建刷写选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 设备选择组
        device_group = QGroupBox("📱 选择设备")
        device_layout = QVBoxLayout()
        
        product_layout = QHBoxLayout()
        product_layout.addWidget(QLabel("产品型号:"))
        self.product_combo = QComboBox()
        self.product_combo.addItems(sorted(self.products.keys()))
        self.product_combo.currentTextChanged.connect(self.on_product_changed)
        product_layout.addWidget(self.product_combo)
        product_layout.addStretch()
        device_layout.addLayout(product_layout)
        
        l4t_layout = QHBoxLayout()
        l4t_layout.addWidget(QLabel("L4T 版本:"))
        self.l4t_combo = QComboBox()
        l4t_layout.addWidget(self.l4t_combo)
        l4t_layout.addStretch()
        device_layout.addLayout(l4t_layout)
        
        self.product_info = QLabel()
        self.product_info.setWordWrap(True)
        self.product_info.setStyleSheet("background-color: #F5F5F5; border-radius: 6px; padding: 12px;")
        device_layout.addWidget(self.product_info)
        
        device_group.setLayout(device_layout)
        layout.addWidget(device_group)
        
        # 选项
        options_group = QGroupBox("⚙️ 选项")
        options_layout = QVBoxLayout()
        
        self.skip_verify_check = QCheckBox("跳过 SHA256 校验（不推荐）")
        options_layout.addWidget(self.skip_verify_check)
        
        self.download_only_check = QCheckBox("仅下载固件，不刷写")
        options_layout.addWidget(self.download_only_check)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # 进度
        progress_group = QGroupBox("📊 进度")
        progress_layout = QVBoxLayout()
        
        self.progress_label = QLabel("等待开始...")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # 日志
        log_group = QGroupBox("📝 日志")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.flash_button = QPushButton("⚡ 开始刷写")
        self.flash_button.setMinimumSize(150, 45)
        self.flash_button.clicked.connect(self.start_flash)
        button_layout.addWidget(self.flash_button)
        
        layout.addLayout(button_layout)
        
        self.on_product_changed(self.product_combo.currentText())
        
        return tab
    
    def create_recovery_tab(self):
        """创建 Recovery 教程选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("选择产品:"))
        self.recovery_product_combo = QComboBox()
        self.recovery_product_combo.addItems(sorted(self.products.keys()))
        self.recovery_product_combo.currentTextChanged.connect(self.show_recovery_guide)
        select_layout.addWidget(self.recovery_product_combo)
        select_layout.addStretch()
        layout.addLayout(select_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        self.recovery_content = QWidget()
        self.recovery_layout = QVBoxLayout(self.recovery_content)
        scroll.setWidget(self.recovery_content)
        
        layout.addWidget(scroll)
        
        self.show_recovery_guide(self.recovery_product_combo.currentText())
        
        return tab
    
    def create_about_tab(self):
        """创建关于选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignCenter)
        
        logo_label = QLabel("🌱")
        logo_label.setStyleSheet("font-size: 72px;")
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)
        
        title = QLabel("Seeed Jetson Flash Tool")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {SEEED_BLUE};")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        version = QLabel("版本 0.1.0")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)
        
        layout.addSpacing(20)
        
        desc = QLabel(
            "一个用于为 Seeed Studio Jetson 设备刷机的工具\n\n"
            "支持所有 Seeed Jetson 产品系列\n"
            "自动下载、校验和刷写固件"
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        layout.addSpacing(20)
        
        links_group = QGroupBox("🔗 相关链接")
        links_layout = QVBoxLayout()
        
        wiki_btn = QPushButton("📖 Wiki 文档")
        wiki_btn.clicked.connect(lambda: self.open_url("https://wiki.seeedstudio.com/"))
        links_layout.addWidget(wiki_btn)
        
        forum_btn = QPushButton("💬 论坛")
        forum_btn.clicked.connect(lambda: self.open_url("https://forum.seeedstudio.com/"))
        links_layout.addWidget(forum_btn)
        
        github_btn = QPushButton("🐙 GitHub")
        github_btn.clicked.connect(lambda: self.open_url("https://github.com/Seeed-Studio"))
        links_layout.addWidget(github_btn)
        
        links_group.setLayout(links_layout)
        layout.addWidget(links_group)
        
        layout.addStretch()
        
        copyright_label = QLabel("© 2026 Seeed Studio. All rights reserved.")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet("color: #999999; font-size: 12px;")
        layout.addWidget(copyright_label)
        
        return tab
    
    def on_product_changed(self, product):
        """产品改变时更新 L4T 版本"""
        self.l4t_combo.clear()
        if product in self.products:
            self.l4t_combo.addItems(self.products[product])
        
        if product in self.product_images:
            info = self.product_images[product]
            self.product_info.setText(f"📱 {info['name']}\n🔗 Wiki: {info['wiki']}")
    
    def show_recovery_guide(self, product):
        """显示 Recovery 教程"""
        while self.recovery_layout.count():
            child = self.recovery_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        guide_data = None
        for series_key, series_data in self.recovery_guides.items():
            if product in series_data['products']:
                guide_data = series_data
                break
        
        if not guide_data:
            self.recovery_layout.addWidget(QLabel("未找到该产品的 Recovery 教程"))
            return
        
        title = QLabel(f"🔄 {guide_data['name']} - Recovery 模式教程")
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {SEEED_BLUE};")
        self.recovery_layout.addWidget(title)
        
        req_group = QGroupBox("📋 所需设备")
        req_layout = QVBoxLayout()
        for req in guide_data['requirements']:
            req_layout.addWidget(QLabel(f"• {req}"))
        req_group.setLayout(req_layout)
        self.recovery_layout.addWidget(req_group)
        
        steps_group = QGroupBox("🔧 操作步骤")
        steps_layout = QVBoxLayout()
        for step in guide_data['steps']:
            step_label = QLabel(f"{step['step']}. {step['description']}")
            step_label.setWordWrap(True)
            step_label.setStyleSheet("padding: 5px;")
            steps_layout.addWidget(step_label)
        steps_group.setLayout(steps_layout)
        self.recovery_layout.addWidget(steps_group)
        
        verify_group = QGroupBox("✓ 验证方法")
        verify_layout = QVBoxLayout()
        verify_layout.addWidget(QLabel(f"在终端执行: {guide_data['verification']['command']}"))
        verify_layout.addWidget(QLabel("\n如果输出包含以下任一 ID，表示设备已进入 Recovery 模式："))
        
        for module, usb_id in guide_data['verification']['ids'].items():
            verify_layout.addWidget(QLabel(f"• {module}: {usb_id}"))
        
        verify_group.setLayout(verify_layout)
        self.recovery_layout.addWidget(verify_group)
        
        if 'images' in guide_data:
            images_group = QGroupBox("📷 参考图片")
            images_layout = QVBoxLayout()
            for img in guide_data['images']:
                images_layout.addWidget(QLabel(f"• {img['description']}"))
                url_label = QLabel(f"  <a href='{img['url']}'>{img['url']}</a>")
                url_label.setOpenExternalLinks(True)
                url_label.setWordWrap(True)
                images_layout.addWidget(url_label)
            images_group.setLayout(images_layout)
            self.recovery_layout.addWidget(images_group)
        
        self.recovery_layout.addStretch()
    
    def start_flash(self):
        """开始刷写"""
        product = self.product_combo.currentText()
        l4t = self.l4t_combo.currentText()
        
        if not product or not l4t:
            QMessageBox.warning(self, "警告", "请选择产品和 L4T 版本")
            return
        
        reply = QMessageBox.question(
            self, "确认刷写",
            f"确定要刷写 {product} (L4T {l4t}) 吗？\n\n"
            "请确保：\n1. 设备已进入 Recovery 模式\n2. USB 连接正常\n3. 有足够的磁盘空间",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        self.flash_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_text.clear()
        
        self.flash_thread = FlashThread(product, l4t, self.skip_verify_check.isChecked())
        self.flash_thread.progress.connect(self.on_flash_progress)
        self.flash_thread.finished.connect(self.on_flash_finished)
        self.flash_thread.start()
    
    def on_flash_progress(self, message):
        """刷写进度更新"""
        self.progress_label.setText(message)
        self.log_text.append(f"[INFO] {message}")
        self.statusBar().showMessage(message)
    
    def on_flash_finished(self, success, message):
        """刷写完成"""
        self.flash_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            self.progress_label.setText("✓ " + message)
            self.log_text.append(f"[SUCCESS] {message}")
            QMessageBox.information(self, "成功", message)
        else:
            self.progress_label.setText("✗ " + message)
            self.log_text.append(f"[ERROR] {message}")
            QMessageBox.critical(self, "错误", message)
        
        self.statusBar().showMessage("就绪")
    
    def open_url(self, url):
        """打开 URL"""
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))


def main():
    """主函数"""
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    app.setApplicationName("Seeed Jetson Flash")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


# 兼容旧入口：统一切换到现代版主窗口实现
try:
    from seeed_jetson_flash.gui.main_window_sdk import (
        FlashThread as _ModernFlashThread,
        MainWindow as _ModernMainWindow,
        main as _modern_main,
    )

    FlashThread = _ModernFlashThread
    MainWindow = _ModernMainWindow
    main = _modern_main
except Exception:
    # 如果现代版导入失败，回退到当前文件内实现
    pass


if __name__ == '__main__':
    main()
