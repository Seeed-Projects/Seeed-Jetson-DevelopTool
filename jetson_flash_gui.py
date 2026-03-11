#!/usr/bin/env python3
"""
Seeed Jetson Flash GUI - 独立版本
直接运行: python jetson_flash_gui.py
"""
import sys
import json
import os
from pathlib import Path

# PyQt5 导入
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QProgressBar, QTextEdit,
    QGroupBox, QTabWidget, QMessageBox, QCheckBox, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl

# Seeed 品牌色
SEEED_GREEN = "#8DC21F"
SEEED_BLUE = "#003A4A"

STYLE = """
QMainWindow { background-color: #FFFFFF; }
QPushButton {
    background-color: #8DC21F;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton:hover { background-color: #74B281; }
QComboBox {
    background-color: white;
    border: 2px solid #8DC21F;
    border-radius: 6px;
    padding: 8px 12px;
}
QProgressBar {
    border: 2px solid #8DC21F;
    border-radius: 6px;
    text-align: center;
    height: 30px;
}
QProgressBar::chunk {
    background-color: #8DC21F;
    border-radius: 4px;
}
QGroupBox {
    border: 2px solid #8DC21F;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
}
"""

# 数据路径
DATA_DIR = Path(__file__).parent / "seeed_jetson_flash" / "data"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.load_data()
        self.init_ui()

    def load_data(self):
        with open(DATA_DIR / "l4t_data.json", 'r') as f:
            self.l4t_data = json.load(f)
        with open(DATA_DIR / "product_images.json", 'r') as f:
            self.product_images = json.load(f)
        with open(DATA_DIR / "recovery_guides.json", 'r', encoding='utf-8') as f:
            self.recovery_guides = json.load(f)
        
        self.products = {}
        for item in self.l4t_data:
            p = item['product']
            if p not in self.products:
                self.products[p] = []
            self.products[p].append(item['l4t'])

    def init_ui(self):
        self.setWindowTitle("Seeed Jetson Flash Tool")
        self.setMinimumSize(900, 650)
        self.setStyleSheet(STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {SEEED_BLUE}, stop:1 {SEEED_GREEN});
                border-radius: 10px;
            }}
        """)
        header_layout = QHBoxLayout(header)
        title = QLabel("🚀 Seeed Jetson Flash Tool")
        title.setStyleSheet("color: white; font-size: 26px; font-weight: bold; padding: 15px;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        ver = QLabel("v0.1.0")
        ver.setStyleSheet("color: white; font-size: 14px; padding: 15px;")
        header_layout.addWidget(ver)
        layout.addWidget(header)

        # 选项卡
        tabs = QTabWidget()
        tabs.addTab(self.create_flash_tab(), "⚡ 刷写固件")
        tabs.addTab(self.create_recovery_tab(), "🔄 Recovery 模式")
        tabs.addTab(self.create_about_tab(), "ℹ️ 关于")
        layout.addWidget(tabs)

        self.statusBar().showMessage("就绪")

    def create_flash_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 设备选择
        grp = QGroupBox("📱 选择设备")
        grp_layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("产品型号:"))
        self.product_combo = QComboBox()
        self.product_combo.addItems(sorted(self.products.keys()))
        self.product_combo.currentTextChanged.connect(self.on_product_changed)
        row1.addWidget(self.product_combo)
        row1.addStretch()
        grp_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("L4T 版本:"))
        self.l4t_combo = QComboBox()
        row2.addWidget(self.l4t_combo)
        row2.addStretch()
        grp_layout.addLayout(row2)

        self.info_label = QLabel()
        self.info_label.setStyleSheet("background: #F5F5F5; padding: 10px; border-radius: 6px;")
        self.info_label.setWordWrap(True)
        grp_layout.addWidget(self.info_label)

        grp.setLayout(grp_layout)
        layout.addWidget(grp)

        # 进度
        prog_grp = QGroupBox("📊 进度")
        prog_layout = QVBoxLayout()
        self.progress_label = QLabel("等待开始...")
        prog_layout.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        prog_layout.addWidget(self.progress_bar)
        prog_grp.setLayout(prog_layout)
        layout.addWidget(prog_grp)

        # 日志
        log_grp = QGroupBox("📝 日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        log_layout.addWidget(self.log_text)
        log_grp.setLayout(log_layout)
        layout.addWidget(log_grp)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.flash_btn = QPushButton("⚡ 开始刷写")
        self.flash_btn.setMinimumSize(140, 40)
        self.flash_btn.clicked.connect(self.start_flash)
        btn_layout.addWidget(self.flash_btn)
        layout.addLayout(btn_layout)

        self.on_product_changed(self.product_combo.currentText())
        return tab

    def create_recovery_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        row = QHBoxLayout()
        row.addWidget(QLabel("选择产品:"))
        self.rec_combo = QComboBox()
        self.rec_combo.addItems(sorted(self.products.keys()))
        self.rec_combo.currentTextChanged.connect(self.show_recovery)
        row.addWidget(self.rec_combo)
        row.addStretch()
        layout.addLayout(row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        self.rec_content = QWidget()
        self.rec_layout = QVBoxLayout(self.rec_content)
        scroll.setWidget(self.rec_content)
        layout.addWidget(scroll)

        self.show_recovery(self.rec_combo.currentText())
        return tab

    def create_about_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignCenter)

        logo = QLabel("🌱")
        logo.setStyleSheet("font-size: 64px;")
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        title = QLabel("Seeed Jetson Flash Tool")
        title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {SEEED_BLUE};")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        ver = QLabel("版本 0.1.0")
        ver.setAlignment(Qt.AlignCenter)
        layout.addWidget(ver)

        layout.addSpacing(15)

        desc = QLabel("为 Seeed Studio Jetson 设备刷机的工具\n支持所有 Seeed Jetson 产品系列")
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(15)

        links = QGroupBox("🔗 链接")
        links_layout = QVBoxLayout()
        for name, url in [
            ("📖 Wiki", "https://wiki.seeedstudio.com/"),
            ("💬 论坛", "https://forum.seeedstudio.com/"),
            ("🐙 GitHub", "https://github.com/Seeed-Studio")
        ]:
            btn = QPushButton(name)
            btn.clicked.connect(lambda _, u=url: QDesktopServices.openUrl(QUrl(u)))
            links_layout.addWidget(btn)
        links.setLayout(links_layout)
        layout.addWidget(links)

        layout.addStretch()

        copy = QLabel("© 2026 Seeed Studio")
        copy.setStyleSheet("color: #999; font-size: 11px;")
        copy.setAlignment(Qt.AlignCenter)
        layout.addWidget(copy)

        return tab

    def on_product_changed(self, product):
        self.l4t_combo.clear()
        if product in self.products:
            self.l4t_combo.addItems(self.products[product])
        if product in self.product_images:
            info = self.product_images[product]
            self.info_label.setText(f"📱 {info['name']}\n🔗 {info['wiki']}")

    def show_recovery(self, product):
        while self.rec_layout.count():
            child = self.rec_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        guide = None
        for k, v in self.recovery_guides.items():
            if product in v['products']:
                guide = v
                break

        if not guide:
            self.rec_layout.addWidget(QLabel("未找到教程"))
            return

        title = QLabel(f"🔄 {guide['name']} - Recovery 模式")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {SEEED_BLUE};")
        self.rec_layout.addWidget(title)

        req = QGroupBox("📋 所需设备")
        req_l = QVBoxLayout()
        for r in guide['requirements']:
            req_l.addWidget(QLabel(f"• {r}"))
        req.setLayout(req_l)
        self.rec_layout.addWidget(req)

        steps = QGroupBox("🔧 步骤")
        steps_l = QVBoxLayout()
        for s in guide['steps']:
            lbl = QLabel(f"{s['step']}. {s['description']}")
            lbl.setWordWrap(True)
            steps_l.addWidget(lbl)
        steps.setLayout(steps_l)
        self.rec_layout.addWidget(steps)

        verify = QGroupBox("✓ 验证")
        verify_l = QVBoxLayout()
        verify_l.addWidget(QLabel(f"执行: {guide['verification']['command']}"))
        for m, uid in guide['verification']['ids'].items():
            verify_l.addWidget(QLabel(f"• {m}: {uid}"))
        verify.setLayout(verify_l)
        self.rec_layout.addWidget(verify)

        self.rec_layout.addStretch()

    def start_flash(self):
        product = self.product_combo.currentText()
        l4t = self.l4t_combo.currentText()
        if not product or not l4t:
            QMessageBox.warning(self, "警告", "请选择产品和版本")
            return

        reply = QMessageBox.question(
            self, "确认",
            f"刷写 {product} (L4T {l4t})?\n\n确保设备已进入 Recovery 模式",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        self.log_text.append(f"[INFO] 开始刷写 {product} L4T {l4t}")
        self.log_text.append("[INFO] 功能开发中...")
        QMessageBox.information(self, "提示", "刷写功能开发中，请使用命令行:\nseeed-jetson-flash flash -p " + product + " -l " + l4t)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Seeed Jetson Flash")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
