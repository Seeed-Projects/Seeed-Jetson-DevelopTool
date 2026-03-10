"""Modern main window for Seeed Jetson Flash GUI."""
import json
import sys
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .styles import MAIN_STYLE
from ..flash import JetsonFlasher


class FlashThread(QThread):
    """Background thread for flashing workflow."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, product, l4t_version, skip_verify=False, download_only=False):
        super().__init__()
        self.product = product
        self.l4t_version = l4t_version
        self.skip_verify = skip_verify
        self.download_only = download_only

    def run(self):
        try:
            flasher = JetsonFlasher(self.product, self.l4t_version)

            self.progress.emit("初始化任务...")
            self.progress.emit("正在下载固件...")
            if not flasher.download_firmware():
                self.finished.emit(False, "固件下载失败")
                return

            if not self.skip_verify:
                self.progress.emit("正在校验 SHA256...")
                if not flasher.verify_firmware():
                    self.finished.emit(False, "SHA256 校验失败")
                    return

            if self.download_only:
                self.finished.emit(True, "固件下载完成（未执行刷写）")
                return

            self.progress.emit("正在解压固件...")
            if not flasher.extract_firmware():
                self.finished.emit(False, "固件解压失败")
                return

            self.progress.emit("正在刷写固件...")
            if not flasher.flash_firmware():
                self.finished.emit(False, "固件刷写失败")
                return

            self.finished.emit(True, "刷写完成")
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.finished.emit(False, f"错误: {exc}")


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.data_path = Path(__file__).parent.parent / "data"

        self.l4t_data = []
        self.product_images = {}
        self.recovery_guides = {}
        self.products = {}
        self.data_error = None

        self.flash_thread = None
        self.nav_buttons = []

        self.load_data()
        self.init_ui()
        self.populate_products()

        if self.data_error:
            self.append_log(self.data_error, "ERROR")
            QMessageBox.warning(self, "数据加载警告", self.data_error)

    def load_data(self):
        """Load JSON data used by the UI."""
        errors = []

        try:
            with open(self.data_path / "l4t_data.json", "r", encoding="utf-8") as file:
                self.l4t_data = json.load(file)
        except Exception as exc:
            errors.append(f"l4t_data.json 加载失败: {exc}")

        try:
            with open(self.data_path / "product_images.json", "r", encoding="utf-8") as file:
                self.product_images = json.load(file)
        except Exception as exc:
            errors.append(f"product_images.json 加载失败: {exc}")

        try:
            with open(self.data_path / "recovery_guides.json", "r", encoding="utf-8") as file:
                self.recovery_guides = json.load(file)
        except Exception as exc:
            errors.append(f"recovery_guides.json 加载失败: {exc}")

        if errors:
            self.data_error = "\n".join(errors)

    def init_ui(self):
        """Build main layout and pages."""
        self.setWindowTitle("Seeed Jetson Flash Tool")
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(MAIN_STYLE)

        root = QWidget()
        root.setObjectName("RootContainer")
        self.setCentralWidget(root)

        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(18)

        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(14)
        main_layout.addLayout(right_layout, 1)

        topbar = self.create_topbar()
        right_layout.addWidget(topbar)

        self.stack = QStackedWidget()
        self.flash_page = self.create_flash_page()
        self.recovery_page = self.create_recovery_page()
        self.about_page = self.create_about_page()

        self.stack.addWidget(self.flash_page)
        self.stack.addWidget(self.recovery_page)
        self.stack.addWidget(self.about_page)
        right_layout.addWidget(self.stack, 1)

        self.set_nav_index(0)
        self.statusBar().showMessage("就绪")

    def create_sidebar(self):
        """Create left navigation pane."""
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(10)

        brand_title = QLabel("Seeed Flash")
        brand_title.setObjectName("BrandTitle")
        layout.addWidget(brand_title)

        brand_subtitle = QLabel("Jetson Device Manager")
        brand_subtitle.setObjectName("BrandSubtitle")
        layout.addWidget(brand_subtitle)

        spacer = QFrame()
        spacer.setFixedHeight(14)
        spacer.setStyleSheet("background: transparent;")
        layout.addWidget(spacer)

        nav_items = [
            "刷写中心",
            "Recovery 指南",
            "关于工具",
        ]
        for index, text in enumerate(nav_items):
            button = QPushButton(text)
            button.setCursor(Qt.PointingHandCursor)
            button.setProperty("nav", True)
            button.setProperty("active", False)
            button.clicked.connect(lambda _, i=index: self.set_nav_index(i))
            layout.addWidget(button)
            self.nav_buttons.append(button)

        layout.addStretch()

        hint_label = QLabel("建议流程\n1. 选择设备\n2. 检查 Recovery\n3. 开始刷写")
        hint_label.setObjectName("BrandSubtitle")
        hint_label.setStyleSheet("padding: 8px 4px;")
        layout.addWidget(hint_label)

        footer = QLabel("v0.1.0")
        footer.setObjectName("BrandSubtitle")
        layout.addWidget(footer)

        return sidebar

    def create_topbar(self):
        """Create top title/status bar."""
        topbar = QFrame()
        topbar.setObjectName("TopBar")

        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(16, 14, 16, 14)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        self.top_title = QLabel("刷写中心")
        self.top_title.setObjectName("TopTitle")
        title_layout.addWidget(self.top_title)

        self.top_subtitle = QLabel("选择产品和 L4T 版本，然后执行下载或刷写")
        self.top_subtitle.setObjectName("TopSubtitle")
        title_layout.addWidget(self.top_subtitle)

        layout.addLayout(title_layout)
        layout.addStretch()

        self.status_chip = QLabel("就绪")
        self.status_chip.setObjectName("StatusChip")
        layout.addWidget(self.status_chip)

        self.set_status("就绪", "info")
        return topbar

    def create_card(self, title, subtitle=None):
        """Create a reusable card container."""
        card = QFrame()
        card.setObjectName("Card")

        wrapper = QVBoxLayout(card)
        wrapper.setContentsMargins(16, 14, 16, 14)
        wrapper.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        wrapper.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("CardSubtitle")
            subtitle_label.setWordWrap(True)
            wrapper.addWidget(subtitle_label)

        content_layout = QVBoxLayout()
        content_layout.setSpacing(9)
        wrapper.addLayout(content_layout)

        return card, content_layout

    def create_flash_page(self):
        """Create flashing page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setSpacing(12)

        upper_layout = QHBoxLayout()
        upper_layout.setSpacing(12)

        left_column = QVBoxLayout()
        left_column.setSpacing(12)

        device_card, device_layout = self.create_card(
            "目标设备",
            "按目标型号选择可用固件版本。",
        )

        row_product = QHBoxLayout()
        row_product.addWidget(QLabel("产品型号"))
        self.product_combo = QComboBox()
        self.product_combo.currentTextChanged.connect(self.on_product_changed)
        row_product.addWidget(self.product_combo)
        device_layout.addLayout(row_product)

        row_l4t = QHBoxLayout()
        row_l4t.addWidget(QLabel("L4T 版本"))
        self.l4t_combo = QComboBox()
        row_l4t.addWidget(self.l4t_combo)
        device_layout.addLayout(row_l4t)

        self.product_info = QLabel("等待选择产品")
        self.product_info.setObjectName("InfoPanel")
        self.product_info.setWordWrap(True)
        device_layout.addWidget(self.product_info)

        left_column.addWidget(device_card)

        option_card, option_layout = self.create_card(
            "执行选项",
            "默认会下载、校验、解压并刷写。",
        )
        self.skip_verify_check = QCheckBox("跳过 SHA256 校验")
        option_layout.addWidget(self.skip_verify_check)

        self.download_only_check = QCheckBox("仅下载固件，不执行刷写")
        self.download_only_check.stateChanged.connect(self.on_download_mode_changed)
        option_layout.addWidget(self.download_only_check)

        self.mode_hint_label = QLabel("当前模式: 下载 + 刷写")
        self.mode_hint_label.setObjectName("LabelHint")
        option_layout.addWidget(self.mode_hint_label)

        left_column.addWidget(option_card)

        upper_layout.addLayout(left_column, 3)

        right_column = QVBoxLayout()
        right_column.setSpacing(12)

        task_card, task_layout = self.create_card(
            "任务执行",
            "建议先在 Recovery 页面确认设备已被识别。",
        )

        self.progress_label = QLabel("尚未开始")
        task_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        task_layout.addWidget(self.progress_bar)

        button_row = QHBoxLayout()

        self.flash_button = QPushButton("开始执行")
        self.flash_button.setObjectName("PrimaryButton")
        self.flash_button.setCursor(Qt.PointingHandCursor)
        self.flash_button.clicked.connect(self.start_flash)
        button_row.addWidget(self.flash_button)

        self.recovery_shortcut_btn = QPushButton("打开 Recovery 指南")
        self.recovery_shortcut_btn.setObjectName("SecondaryButton")
        self.recovery_shortcut_btn.setCursor(Qt.PointingHandCursor)
        self.recovery_shortcut_btn.clicked.connect(lambda: self.set_nav_index(1))
        button_row.addWidget(self.recovery_shortcut_btn)

        task_layout.addLayout(button_row)

        right_column.addWidget(task_card)
        right_column.addStretch()

        upper_layout.addLayout(right_column, 2)
        page_layout.addLayout(upper_layout)

        log_card, log_layout = self.create_card("执行日志", "显示当前会话的关键状态。")
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(180)
        log_layout.addWidget(self.log_text)
        page_layout.addWidget(log_card)

        return page

    def create_recovery_page(self):
        """Create recovery guide page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        select_card, select_layout = self.create_card(
            "Recovery 指南",
            "根据产品型号查看进入 Recovery 模式的步骤。",
        )

        row = QHBoxLayout()
        row.addWidget(QLabel("产品型号"))
        self.recovery_product_combo = QComboBox()
        self.recovery_product_combo.currentTextChanged.connect(self.show_recovery_guide)
        row.addWidget(self.recovery_product_combo)
        select_layout.addLayout(row)

        layout.addWidget(select_card)

        content_card, content_layout = self.create_card("详细步骤")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.recovery_content = QWidget()
        self.recovery_layout = QVBoxLayout(self.recovery_content)
        self.recovery_layout.setContentsMargins(4, 4, 4, 4)
        self.recovery_layout.setSpacing(10)

        scroll.setWidget(self.recovery_content)
        content_layout.addWidget(scroll)
        layout.addWidget(content_card, 1)

        return page

    def create_about_page(self):
        """Create about page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        about_card, about_layout = self.create_card(
            "关于 Seeed Jetson Flash",
            "用于 Seeed Jetson 系列设备的下载、校验和刷写工具。",
        )
        about_text = QLabel(
            "支持功能:\n"
            "• 设备型号与 L4T 版本匹配\n"
            "• 固件自动下载与 SHA256 校验\n"
            "• Recovery 指南与常见故障排查\n"
            "• 图形化操作与日志反馈"
        )
        about_text.setWordWrap(True)
        about_layout.addWidget(about_text)
        layout.addWidget(about_card)

        links_card, links_layout = self.create_card("相关链接")

        wiki_btn = QPushButton("Seeed Wiki")
        wiki_btn.setObjectName("SecondaryButton")
        wiki_btn.setCursor(Qt.PointingHandCursor)
        wiki_btn.clicked.connect(lambda: self.open_url("https://wiki.seeedstudio.com/"))
        links_layout.addWidget(wiki_btn)

        forum_btn = QPushButton("Seeed Forum")
        forum_btn.setObjectName("SecondaryButton")
        forum_btn.setCursor(Qt.PointingHandCursor)
        forum_btn.clicked.connect(lambda: self.open_url("https://forum.seeedstudio.com/"))
        links_layout.addWidget(forum_btn)

        github_btn = QPushButton("Seeed GitHub")
        github_btn.setObjectName("SecondaryButton")
        github_btn.setCursor(Qt.PointingHandCursor)
        github_btn.clicked.connect(lambda: self.open_url("https://github.com/Seeed-Studio"))
        links_layout.addWidget(github_btn)

        layout.addWidget(links_card)
        layout.addStretch()

        return page

    def set_status(self, text, status):
        """Update status chip style and text."""
        self.status_chip.setText(text)
        self.status_chip.setProperty("status", status)
        self.status_chip.style().unpolish(self.status_chip)
        self.status_chip.style().polish(self.status_chip)
        self.status_chip.update()

    def set_nav_index(self, index):
        """Switch page and highlight active nav item."""
        self.stack.setCurrentIndex(index)

        for idx, button in enumerate(self.nav_buttons):
            button.setProperty("active", idx == index)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

        titles = {
            0: ("刷写中心", "选择产品和 L4T 版本，然后执行下载或刷写"),
            1: ("Recovery 指南", "按设备型号查看进入 Recovery 模式的详细步骤"),
            2: ("关于工具", "查看工具功能和相关文档入口"),
        }
        title, subtitle = titles.get(index, ("Seeed Flash", ""))
        self.top_title.setText(title)
        self.top_subtitle.setText(subtitle)

    def populate_products(self):
        """Populate product-related UI controls."""
        self.products = {}

        for item in self.l4t_data:
            product = item.get("product")
            l4t = item.get("l4t")
            if not product or not l4t:
                continue
            self.products.setdefault(product, [])
            if l4t not in self.products[product]:
                self.products[product].append(l4t)

        for versions in self.products.values():
            versions.sort(reverse=True)

        product_list = sorted(self.products.keys())

        self.product_combo.blockSignals(True)
        self.recovery_product_combo.blockSignals(True)

        self.product_combo.clear()
        self.recovery_product_combo.clear()

        self.product_combo.addItems(product_list)
        self.recovery_product_combo.addItems(product_list)

        self.product_combo.blockSignals(False)
        self.recovery_product_combo.blockSignals(False)

        has_data = bool(product_list)
        self.flash_button.setEnabled(has_data)

        if has_data:
            self.on_product_changed(self.product_combo.currentText())
            self.show_recovery_guide(self.recovery_product_combo.currentText())
            self.append_log(f"已加载 {len(product_list)} 个产品型号", "INFO")
        else:
            self.product_info.setText("未加载到有效产品数据，请检查 data/l4t_data.json")
            self.progress_label.setText("数据不可用")
            self.set_status("数据错误", "error")

    def on_product_changed(self, product):
        """Update L4T versions and product info when product changes."""
        self.l4t_combo.clear()
        versions = self.products.get(product, [])
        self.l4t_combo.addItems(versions)

        info = self.product_images.get(product, {})
        name = info.get("name", product or "未知产品")
        wiki = info.get("wiki", "无")
        latest = versions[0] if versions else "无"

        self.product_info.setText(
            f"名称: {name}\n"
            f"最新 L4T: {latest}\n"
            f"可选版本数: {len(versions)}\n"
            f"Wiki: {wiki}"
        )

    def on_download_mode_changed(self):
        """Update mode hint text when download-only option changes."""
        if self.download_only_check.isChecked():
            self.mode_hint_label.setText("当前模式: 仅下载（不会执行刷写）")
        else:
            self.mode_hint_label.setText("当前模式: 下载 + 刷写")

    def clear_layout(self, layout):
        """Remove all child widgets from a layout."""
        while layout.count():
            child = layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def show_recovery_guide(self, product):
        """Render recovery guide for selected product."""
        self.clear_layout(self.recovery_layout)

        guide_data = None
        for series_data in self.recovery_guides.values():
            if product in series_data.get("products", []):
                guide_data = series_data
                break

        if not guide_data:
            empty_label = QLabel("未找到该产品的 Recovery 教程")
            empty_label.setObjectName("LabelHint")
            self.recovery_layout.addWidget(empty_label)
            self.recovery_layout.addStretch()
            return

        title = QLabel(f"{guide_data.get('name', 'Recovery')} - 操作说明")
        title.setObjectName("CardTitle")
        self.recovery_layout.addWidget(title)

        requirements = "\n".join(f"• {item}" for item in guide_data.get("requirements", []))
        req_block = QLabel(f"所需设备\n{requirements}")
        req_block.setObjectName("InfoPanel")
        req_block.setWordWrap(True)
        self.recovery_layout.addWidget(req_block)

        steps_lines = []
        for step in guide_data.get("steps", []):
            steps_lines.append(f"{step.get('step', '?')}. {step.get('description', '')}")
        step_block = QLabel("操作步骤\n" + "\n".join(steps_lines))
        step_block.setObjectName("InfoPanel")
        step_block.setWordWrap(True)
        self.recovery_layout.addWidget(step_block)

        verification = guide_data.get("verification", {})
        verify_lines = [f"命令: {verification.get('command', '')}"]
        for module, usb_id in verification.get("ids", {}).items():
            verify_lines.append(f"• {module}: {usb_id}")
        verify_block = QLabel("验证方法\n" + "\n".join(verify_lines))
        verify_block.setObjectName("InfoPanel")
        verify_block.setWordWrap(True)
        self.recovery_layout.addWidget(verify_block)

        image_list = guide_data.get("images", [])
        if image_list:
            links = []
            for image in image_list:
                desc = image.get("description", "")
                url = image.get("url", "")
                links.append(f"• {desc}\n  <a href='{url}'>{url}</a>")
            image_block = QLabel("参考图片\n" + "\n".join(links))
            image_block.setObjectName("InfoPanel")
            image_block.setWordWrap(True)
            image_block.setOpenExternalLinks(True)
            self.recovery_layout.addWidget(image_block)

        video_url = guide_data.get("video")
        if video_url:
            video_label = QLabel(f"视频教程\n<a href='{video_url}'>{video_url}</a>")
            video_label.setObjectName("InfoPanel")
            video_label.setOpenExternalLinks(True)
            video_label.setWordWrap(True)
            self.recovery_layout.addWidget(video_label)

        self.recovery_layout.addStretch()

    def append_log(self, message, level="INFO"):
        """Append one line to log area."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] [{level}] {message}")

    def start_flash(self):
        """Start flashing workflow."""
        if self.flash_thread and self.flash_thread.isRunning():
            QMessageBox.information(self, "提示", "任务正在执行，请等待当前流程结束")
            return

        product = self.product_combo.currentText()
        l4t = self.l4t_combo.currentText()

        if not product or not l4t:
            QMessageBox.warning(self, "警告", "请选择产品和 L4T 版本")
            return

        mode_desc = "仅下载" if self.download_only_check.isChecked() else "下载 + 刷写"
        verify_desc = "跳过校验" if self.skip_verify_check.isChecked() else "执行校验"

        reply = QMessageBox.question(
            self,
            "确认执行",
            f"目标: {product}\n版本: {l4t}\n模式: {mode_desc}\n校验: {verify_desc}\n\n确认继续吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.flash_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.progress_label.setText("任务已启动")

        self.log_text.clear()
        self.append_log(f"开始执行: {product} / L4T {l4t}")
        self.append_log(f"模式: {mode_desc}, 校验: {verify_desc}")

        self.set_status("执行中", "busy")
        self.statusBar().showMessage("任务执行中")

        self.flash_thread = FlashThread(
            product,
            l4t,
            skip_verify=self.skip_verify_check.isChecked(),
            download_only=self.download_only_check.isChecked(),
        )
        self.flash_thread.progress.connect(self.on_flash_progress)
        self.flash_thread.finished.connect(self.on_flash_finished)
        self.flash_thread.start()

    def on_flash_progress(self, message):
        """Handle progress signal from worker thread."""
        self.progress_label.setText(message)
        self.append_log(message)
        self.statusBar().showMessage(message)

    def on_flash_finished(self, success, message):
        """Handle worker completion."""
        self.flash_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        if success:
            self.set_status("完成", "success")
            self.progress_label.setText(f"完成: {message}")
            self.append_log(message, "SUCCESS")
            QMessageBox.information(self, "完成", message)
        else:
            self.set_status("失败", "error")
            self.progress_label.setText(f"失败: {message}")
            self.append_log(message, "ERROR")
            QMessageBox.critical(self, "错误", message)

        self.statusBar().showMessage("就绪")
        self.flash_thread = None

    def open_url(self, url):
        """Open URL in default browser."""
        QDesktopServices.openUrl(QUrl(url))


def main():
    """Application entry point."""
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Seeed Jetson Flash")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
