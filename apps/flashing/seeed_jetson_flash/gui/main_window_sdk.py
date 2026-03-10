"""SDK-style main window with bilingual support."""
import hashlib
import html
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl, QEvent, QPoint
from PyQt5.QtGui import QDesktopServices, QColor, QPixmap
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
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
import requests


I18N = {
    "zh": {
        "brand_subtitle": "Jetson 设备刷写管理器",
        "flow_hint": "建议流程\n1. 选择设备\n2. 检查 Recovery\n3. 开始刷写",
        "nav_flash": "刷写中心",
        "nav_recovery": "Recovery 指南",
        "nav_about": "关于工具",
        "top_flash_title": "刷写中心",
        "top_flash_subtitle": "选择产品和 L4T 版本，然后执行下载或刷写",
        "top_recovery_title": "Recovery 指南",
        "top_recovery_subtitle": "按设备型号查看进入 Recovery 模式的详细步骤",
        "top_about_title": "关于工具",
        "top_about_subtitle": "查看工具功能和相关文档入口",
        "lang_label": "语言",
        "status_ready": "就绪",
        "status_busy": "执行中",
        "status_done": "完成",
        "status_error": "失败",
        "card_target_title": "目标设备",
        "card_target_subtitle": "按目标型号选择可用固件版本。",
        "label_product": "产品型号",
        "label_l4t": "L4T 版本",
        "info_waiting": "等待选择产品",
        "card_options_title": "执行选项",
        "card_options_subtitle": "默认会下载、校验、解压并刷写。",
        "skip_verify": "跳过 SHA256 校验",
        "download_only": "仅下载固件，不执行刷写",
        "mode_flash": "当前模式: 下载 + 刷写",
        "mode_download": "当前模式: 仅下载（不会执行刷写）",
        "card_task_title": "任务执行",
        "card_task_subtitle": "建议先在 Recovery 页面确认设备已被识别。",
        "task_idle": "尚未开始",
        "btn_run": "开始执行",
        "btn_cancel": "取消任务",
        "btn_open_recovery": "打开 Recovery 指南",
        "card_log_title": "执行日志",
        "card_log_subtitle": "显示当前会话的关键状态。",
        "card_recovery_title": "Recovery 指南",
        "card_recovery_subtitle": "根据产品型号查看进入 Recovery 模式的步骤。",
        "card_recovery_detail_title": "详细步骤",
        "no_guide": "未找到该产品的 Recovery 教程",
        "block_requirements": "所需设备",
        "block_steps": "操作步骤",
        "block_verify": "验证方法",
        "block_images": "参考图片",
        "block_video": "视频教程",
        "image_load_failed": "图片加载失败",
        "card_about_title": "关于 Seeed Jetson Flash",
        "card_about_subtitle": "用于 Seeed Jetson 系列设备的下载、校验和刷写工具。",
        "about_text": "支持功能:\n• 设备型号与 L4T 版本匹配\n• 固件自动下载与 SHA256 校验\n• Recovery 指南与常见故障排查\n• 图形化操作与日志反馈",
        "card_links_title": "相关链接",
        "btn_wiki": "Seeed Wiki",
        "btn_forum": "Seeed Forum",
        "btn_github": "Seeed GitHub",
        "warn_data_title": "数据加载警告",
        "warn_data_empty": "未加载到有效产品数据，请检查 data/l4t_data.json",
        "warn_select": "请选择产品和 L4T 版本",
        "hint_running": "任务正在执行，请等待当前流程结束",
        "confirm_title": "确认执行",
        "confirm_tpl": "目标: {product}\n版本: {l4t}\n模式: {mode}\n校验: {verify}\n\n确认继续吗？",
        "mode_download_short": "仅下载",
        "mode_flash_short": "下载 + 刷写",
        "verify_skip_short": "跳过校验",
        "verify_do_short": "执行校验",
        "task_started": "任务已启动",
        "log_start": "开始执行: {product} / L4T {l4t}",
        "log_mode": "模式: {mode}, 校验: {verify}",
        "msg_done_title": "完成",
        "msg_error_title": "错误",
        "msg_info_title": "提示",
        "progress_init": "初始化任务...",
        "progress_download": "正在下载固件...",
        "progress_verify": "正在校验 SHA256...",
        "progress_extract": "正在解压固件...",
        "progress_flash": "正在刷写固件...",
        "result_download_done": "固件下载完成（未执行刷写）",
        "result_download_fail": "固件下载失败",
        "result_verify_fail": "SHA256 校验失败",
        "result_extract_fail": "固件解压失败",
        "result_flash_fail": "固件刷写失败",
        "result_flash_done": "刷写完成",
        "result_cancelled": "任务已取消",
        "result_done_prefix": "完成: {message}",
        "result_error_prefix": "失败: {message}",
        "task_cancelling": "正在取消任务...",
        "log_loaded": "已加载 {count} 个产品型号",
        "statusbar_ready": "就绪",
        "statusbar_running": "任务执行中",
        "product_info_tpl": "名称: {name}\n最新 L4T: {latest}\n可选版本数: {count}\nWiki: {wiki}",
        "product_info_html_tpl": "名称: {name}<br>最新 L4T: {latest}<br>可选版本数: {count}<br>Wiki: {wiki_link}",
    },
    "en": {
        "brand_subtitle": "Jetson Device Flash Manager",
        "flow_hint": "Recommended flow\n1. Select device\n2. Check Recovery\n3. Start task",
        "nav_flash": "Flash Center",
        "nav_recovery": "Recovery Guide",
        "nav_about": "About",
        "top_flash_title": "Flash Center",
        "top_flash_subtitle": "Select product and L4T version, then run download or flash",
        "top_recovery_title": "Recovery Guide",
        "top_recovery_subtitle": "View Recovery steps by product model",
        "top_about_title": "About",
        "top_about_subtitle": "Tool overview and related links",
        "lang_label": "Language",
        "status_ready": "Ready",
        "status_busy": "Running",
        "status_done": "Done",
        "status_error": "Failed",
        "card_target_title": "Target Device",
        "card_target_subtitle": "Select a product model and available L4T versions.",
        "label_product": "Product",
        "label_l4t": "L4T Version",
        "info_waiting": "Waiting for product selection",
        "card_options_title": "Execution Options",
        "card_options_subtitle": "Default flow includes download, verify, extract, and flash.",
        "skip_verify": "Skip SHA256 verification",
        "download_only": "Download firmware only (no flashing)",
        "mode_flash": "Mode: Download + Flash",
        "mode_download": "Mode: Download only (no flashing)",
        "card_task_title": "Task Execution",
        "card_task_subtitle": "Check device status in Recovery page before flashing.",
        "task_idle": "Not started",
        "btn_run": "Run",
        "btn_cancel": "Cancel",
        "btn_open_recovery": "Open Recovery Guide",
        "card_log_title": "Execution Log",
        "card_log_subtitle": "Shows key events in current session.",
        "card_recovery_title": "Recovery Guide",
        "card_recovery_subtitle": "Select a model to view Recovery instructions.",
        "card_recovery_detail_title": "Details",
        "no_guide": "No Recovery guide found for this product",
        "block_requirements": "Requirements",
        "block_steps": "Steps",
        "block_verify": "Verification",
        "block_images": "Reference Images",
        "block_video": "Video Tutorial",
        "image_load_failed": "Image preview failed.",
        "card_about_title": "About Seeed Jetson Flash",
        "card_about_subtitle": "Tool for downloading, verifying, and flashing Seeed Jetson devices.",
        "about_text": "Capabilities:\n• Product / L4T matching\n• Auto download and SHA256 verification\n• Recovery guides and troubleshooting\n• GUI workflow and runtime logs",
        "card_links_title": "Links",
        "btn_wiki": "Seeed Wiki",
        "btn_forum": "Seeed Forum",
        "btn_github": "Seeed GitHub",
        "warn_data_title": "Data Warning",
        "warn_data_empty": "No valid product data loaded. Check data/l4t_data.json",
        "warn_select": "Please select product and L4T version",
        "hint_running": "A task is running. Please wait for it to finish",
        "confirm_title": "Confirm",
        "confirm_tpl": "Target: {product}\nVersion: {l4t}\nMode: {mode}\nVerify: {verify}\n\nContinue?",
        "mode_download_short": "Download only",
        "mode_flash_short": "Download + Flash",
        "verify_skip_short": "Skip verify",
        "verify_do_short": "Verify enabled",
        "task_started": "Task started",
        "log_start": "Starting: {product} / L4T {l4t}",
        "log_mode": "Mode: {mode}, Verify: {verify}",
        "msg_done_title": "Done",
        "msg_error_title": "Error",
        "msg_info_title": "Info",
        "progress_init": "Initializing...",
        "progress_download": "Downloading firmware...",
        "progress_verify": "Verifying SHA256...",
        "progress_extract": "Extracting firmware...",
        "progress_flash": "Flashing firmware...",
        "result_download_done": "Firmware downloaded (flash skipped)",
        "result_download_fail": "Firmware download failed",
        "result_verify_fail": "SHA256 verification failed",
        "result_extract_fail": "Firmware extraction failed",
        "result_flash_fail": "Firmware flash failed",
        "result_flash_done": "Firmware flash completed",
        "result_cancelled": "Task cancelled",
        "result_done_prefix": "Done: {message}",
        "result_error_prefix": "Failed: {message}",
        "task_cancelling": "Cancelling task...",
        "log_loaded": "Loaded {count} product models",
        "statusbar_ready": "Ready",
        "statusbar_running": "Task running",
        "product_info_tpl": "Name: {name}\nLatest L4T: {latest}\nAvailable versions: {count}\nWiki: {wiki}",
        "product_info_html_tpl": "Name: {name}<br>Latest L4T: {latest}<br>Available versions: {count}<br>Wiki: {wiki_link}",
    },
}


class FlashThread(QThread):
    """Background thread for flashing workflow."""

    progress = pyqtSignal(str)
    progress_value = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, product, l4t_version, tr, skip_verify=False, download_only=False):
        super().__init__()
        self.product = product
        self.l4t_version = l4t_version
        self.tr = tr
        self.skip_verify = skip_verify
        self.download_only = download_only
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    def _is_cancelled(self):
        return self._cancel_requested

    def _on_core_progress(self, stage, current, total):
        """Map downloader progress to rough global progress percentage."""
        if stage == "download":
            if total and total > 0:
                ratio = max(0.0, min(1.0, float(current) / float(total)))
                self.progress_value.emit(int(6 + ratio * 40))
            else:
                self.progress_value.emit(10)

    def run(self):
        try:
            flasher = JetsonFlasher(
                self.product,
                self.l4t_version,
                progress_callback=self._on_core_progress,
                should_cancel=self._is_cancelled,
            )

            self.progress.emit(self.tr("progress_init"))
            self.progress_value.emit(2)
            if self._is_cancelled():
                raise InterruptedError()
            self.progress.emit(self.tr("progress_download"))
            if not flasher.download_firmware():
                self.finished.emit(False, self.tr("result_download_fail"))
                return

            self.progress_value.emit(46)
            if self._is_cancelled():
                raise InterruptedError()
            if not self.skip_verify:
                self.progress.emit(self.tr("progress_verify"))
                self.progress_value.emit(55)
                if not flasher.verify_firmware():
                    self.finished.emit(False, self.tr("result_verify_fail"))
                    return
                self.progress_value.emit(64)
                if self._is_cancelled():
                    raise InterruptedError()

            if self.download_only:
                self.progress_value.emit(100)
                self.finished.emit(True, self.tr("result_download_done"))
                return

            self.progress.emit(self.tr("progress_extract"))
            self.progress_value.emit(74)
            if self._is_cancelled():
                raise InterruptedError()
            if not flasher.extract_firmware():
                self.finished.emit(False, self.tr("result_extract_fail"))
                return

            self.progress.emit(self.tr("progress_flash"))
            self.progress_value.emit(86)
            if self._is_cancelled():
                raise InterruptedError()
            if not flasher.flash_firmware():
                self.finished.emit(False, self.tr("result_flash_fail"))
                return

            self.progress_value.emit(100)
            self.finished.emit(True, self.tr("result_flash_done"))
        except InterruptedError:
            self.finished.emit(False, self.tr("result_cancelled"))
        except Exception as exc:  # pragma: no cover
            self.finished.emit(False, f"Error: {exc}")


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.data_path = Path(__file__).parent.parent / "data"
        self.project_root = Path(__file__).resolve().parents[2]
        self.recovery_image_dir = Path.home() / ".cache" / "seeed-jetson-flash" / "recovery_images"
        self.lang = "zh"

        self.l4t_data = []
        self.product_images = {}
        self.recovery_guides = {}
        self.products = {}
        self.data_error = None
        self.flash_thread = None
        self._dragging = False
        self._drag_pos = QPoint()

        self.status_key = "status_ready"
        self.status_style = "info"
        self.nav_buttons = []
        self.retranslate_pairs = []
        self.image_cache = {}
        self.recovery_local_images = {}

        self.load_data()
        self.prime_recovery_images()
        self.init_ui()
        self.populate_products()

        if self.data_error:
            self.append_log(self.data_error, "ERROR")
            QMessageBox.warning(self, self.tr("warn_data_title"), self.data_error)

    def tr(self, key, **kwargs):
        text = I18N[self.lang].get(key, key)
        if kwargs:
            return text.format(**kwargs)
        return text

    def set_translatable(self, widget, key):
        self.retranslate_pairs.append((widget, key))
        widget.setText(self.tr(key))

    @staticmethod
    def add_elevation(widget, blur=20, y_offset=3, alpha=70):
        """Add a subtle drop shadow to improve depth."""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur)
        shadow.setOffset(0, y_offset)
        shadow.setColor(QColor(16, 27, 43, alpha))
        widget.setGraphicsEffect(shadow)

    def load_data(self):
        errors = []

        try:
            with open(self.data_path / "l4t_data.json", "r", encoding="utf-8") as file:
                self.l4t_data = json.load(file)
        except Exception as exc:
            errors.append(f"l4t_data.json: {exc}")

        try:
            with open(self.data_path / "product_images.json", "r", encoding="utf-8") as file:
                self.product_images = json.load(file)
        except Exception as exc:
            errors.append(f"product_images.json: {exc}")

        try:
            with open(self.data_path / "recovery_guides.json", "r", encoding="utf-8") as file:
                self.recovery_guides = json.load(file)
        except Exception as exc:
            errors.append(f"recovery_guides.json: {exc}")

        if errors:
            self.data_error = "\n".join(errors)

    @staticmethod
    def _pick_image_extension(url):
        """Get a usable image extension from URL path."""
        suffix = Path(urlparse(url).path).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            return suffix
        return ".png"

    def _local_image_path_for_url(self, url):
        """Build stable local path for recovery image URL."""
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        ext = self._pick_image_extension(url)
        return self.recovery_image_dir / f"{digest}{ext}"

    @staticmethod
    def _pixmap_from_response_bytes(data):
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            return pixmap
        return None

    def _download_and_store_recovery_image(self, url, local_path):
        """Download recovery image and save to local cache if valid."""
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            data = resp.content
            pixmap = self._pixmap_from_response_bytes(data)
            if not pixmap:
                return None
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(data)
            return pixmap
        except Exception:
            return None

    def prime_recovery_images(self):
        """Download all recovery images to local cache for local-first loading."""
        try:
            self.recovery_image_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.recovery_image_dir = Path("/tmp/seeed-jetson-flash/recovery_images")
            try:
                self.recovery_image_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                return

        urls = []
        for series_data in self.recovery_guides.values():
            for image_item in series_data.get("images", []):
                url = image_item.get("url", "").strip()
                if url:
                    urls.append(url)

        for url in sorted(set(urls)):
            local_path = self._local_image_path_for_url(url)
            self.recovery_local_images[url] = local_path
            if local_path.exists() and local_path.stat().st_size > 0:
                continue
            self._download_and_store_recovery_image(url, local_path)

    def init_ui(self):
        self.setWindowTitle("Seeed Jetson Flash Tool")
        self.setMinimumSize(1160, 740)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet(MAIN_STYLE)

        root = QWidget()
        root.setObjectName("RootContainer")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(0)

        outer_frame = QFrame()
        outer_frame.setObjectName("WindowFrame")
        outer_layout = QVBoxLayout(outer_frame)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.chrome_bar = self.create_window_chrome()
        outer_layout.addWidget(self.chrome_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(18, 12, 18, 18)
        body_layout.setSpacing(16)

        body_layout.addWidget(self.create_sidebar())

        right_panel = QFrame()
        right_panel.setObjectName("MainWorkspace")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)
        body_layout.addWidget(right_panel, 1)

        right_layout.addWidget(self.create_topbar())

        self.stack = QStackedWidget()
        self.stack.setObjectName("MainStack")
        self.stack.addWidget(self.create_flash_page())
        self.stack.addWidget(self.create_recovery_page())
        self.stack.addWidget(self.create_about_page())
        right_layout.addWidget(self.stack, 1)
        self.add_elevation(self.stack, blur=18, y_offset=2, alpha=36)

        outer_layout.addWidget(body, 1)
        root_layout.addWidget(outer_frame, 1)

        self.set_nav_index(0)
        self.statusBar().showMessage(self.tr("statusbar_ready"))

    def create_window_chrome(self):
        """Create custom outer title bar with window controls."""
        bar = QFrame()
        bar.setObjectName("WindowChrome")
        bar.installEventFilter(self)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(8)

        self.chrome_title = QLabel("Seeed Jetson Flash Tool")
        self.chrome_title.setObjectName("WindowChromeTitle")
        self.chrome_title.installEventFilter(self)
        layout.addWidget(self.chrome_title)
        layout.addStretch()

        self.min_btn = QPushButton("-")
        self.min_btn.setObjectName("WindowChromeBtn")
        self.min_btn.setCursor(Qt.PointingHandCursor)
        self.min_btn.setFixedSize(28, 22)
        self.min_btn.clicked.connect(self.showMinimized)
        layout.addWidget(self.min_btn)

        self.max_btn = QPushButton("□")
        self.max_btn.setObjectName("WindowChromeBtn")
        self.max_btn.setCursor(Qt.PointingHandCursor)
        self.max_btn.setFixedSize(28, 22)
        self.max_btn.clicked.connect(self.toggle_max_restore)
        layout.addWidget(self.max_btn)

        self.close_btn = QPushButton("x")
        self.close_btn.setObjectName("WindowChromeCloseBtn")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setFixedSize(28, 22)
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)

        return bar

    def toggle_max_restore(self):
        """Toggle between maximized and normal window state."""
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText("□")
        else:
            self.showMaximized()
            self.max_btn.setText("❐")

    def eventFilter(self, source, event):
        """Enable window dragging from custom title bar."""
        if source in (getattr(self, "chrome_bar", None), getattr(self, "chrome_title", None)):
            if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self.toggle_max_restore()
                return True
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._dragging = True
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                return True
            if event.type() == QEvent.MouseMove and self._dragging and event.buttons() & Qt.LeftButton:
                if self.isMaximized():
                    return True
                self.move(event.globalPos() - self._drag_pos)
                return True
            if event.type() == QEvent.MouseButtonRelease:
                self._dragging = False
                return True
        return super().eventFilter(source, event)

    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(236)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(10)

        self.logo_label = QLabel()
        self.logo_label.setObjectName("BrandLogo")
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setMinimumHeight(58)
        logo_path = self.project_root / "seeed-logo-blend.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                scaled = pix.scaled(178, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.logo_label.setPixmap(scaled)
        layout.addWidget(self.logo_label)

        title = QLabel("Seeed Flash")
        title.setObjectName("BrandTitle")
        layout.addWidget(title)

        subtitle = QLabel()
        subtitle.setObjectName("BrandSubtitle")
        self.set_translatable(subtitle, "brand_subtitle")
        layout.addWidget(subtitle)

        gap = QFrame()
        gap.setFixedHeight(12)
        gap.setStyleSheet("background: transparent;")
        layout.addWidget(gap)

        nav_keys = ["nav_flash", "nav_recovery", "nav_about"]
        for idx, key in enumerate(nav_keys):
            btn = QPushButton()
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("nav", True)
            btn.setProperty("active", False)
            self.set_translatable(btn, key)
            btn.clicked.connect(lambda _, i=idx: self.set_nav_index(i))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)

        layout.addStretch()

        flow = QLabel()
        flow.setObjectName("BrandSubtitle")
        flow.setStyleSheet("padding: 6px 2px;")
        self.set_translatable(flow, "flow_hint")
        layout.addWidget(flow)

        ver = QLabel("v0.1.0")
        ver.setObjectName("BrandSubtitle")
        layout.addWidget(ver)
        self.add_elevation(sidebar, blur=26, y_offset=4, alpha=85)
        return sidebar

    def create_topbar(self):
        topbar = QFrame()
        topbar.setObjectName("TopBar")

        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(14, 12, 14, 12)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        self.top_title = QLabel()
        self.top_title.setObjectName("TopTitle")
        title_layout.addWidget(self.top_title)

        self.top_subtitle = QLabel()
        self.top_subtitle.setObjectName("TopSubtitle")
        title_layout.addWidget(self.top_subtitle)
        layout.addLayout(title_layout)
        layout.addStretch()

        lang_label = QLabel()
        lang_label.setObjectName("TopBarHint")
        self.set_translatable(lang_label, "lang_label")
        layout.addWidget(lang_label)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["中文", "English"])
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)
        layout.addWidget(self.language_combo)

        self.status_chip = QLabel()
        self.status_chip.setObjectName("StatusChip")
        layout.addWidget(self.status_chip)
        self.set_status("status_ready", "info")

        self.add_elevation(topbar, blur=20, y_offset=3, alpha=55)
        return topbar

    def create_card(self, title_key, subtitle_key=None):
        card = QFrame()
        card.setObjectName("Card")

        wrapper = QVBoxLayout(card)
        wrapper.setContentsMargins(14, 12, 14, 12)
        wrapper.setSpacing(9)

        title = QLabel()
        title.setObjectName("CardTitle")
        self.set_translatable(title, title_key)
        wrapper.addWidget(title)

        if subtitle_key:
            subtitle = QLabel()
            subtitle.setObjectName("CardSubtitle")
            subtitle.setWordWrap(True)
            self.set_translatable(subtitle, subtitle_key)
            wrapper.addWidget(subtitle)

        content_layout = QVBoxLayout()
        content_layout.setSpacing(8)
        wrapper.addLayout(content_layout)
        self.add_elevation(card, blur=16, y_offset=2, alpha=45)
        return card, content_layout

    def create_flash_page(self):
        page = QWidget()
        page.setObjectName("ContentPage")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("SectionScroll")
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("SectionContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(11)

        device_card, device = self.create_card("card_target_title", "card_target_subtitle")
        device_card.setProperty("priority", "high")
        row_p = QHBoxLayout()
        self.product_label = QLabel()
        self.set_translatable(self.product_label, "label_product")
        self.product_label.setFixedWidth(92)
        self.product_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_p.addWidget(self.product_label)
        self.product_combo = QComboBox()
        self.product_combo.currentTextChanged.connect(self.on_product_changed)
        row_p.addWidget(self.product_combo)
        device.addLayout(row_p)

        row_l = QHBoxLayout()
        self.l4t_label = QLabel()
        self.set_translatable(self.l4t_label, "label_l4t")
        self.l4t_label.setFixedWidth(92)
        self.l4t_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_l.addWidget(self.l4t_label)
        self.l4t_combo = QComboBox()
        row_l.addWidget(self.l4t_combo)
        device.addLayout(row_l)

        self.product_info = QLabel()
        self.product_info.setObjectName("InfoPanel")
        self.product_info.setWordWrap(True)
        self.product_info.setTextFormat(Qt.RichText)
        self.product_info.setOpenExternalLinks(True)
        self.product_info.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.set_translatable(self.product_info, "info_waiting")
        device.addWidget(self.product_info)
        layout.addWidget(device_card)

        opt_card, opt = self.create_card("card_options_title", "card_options_subtitle")
        self.skip_verify_check = QCheckBox()
        self.set_translatable(self.skip_verify_check, "skip_verify")
        opt.addWidget(self.skip_verify_check)

        self.download_only_check = QCheckBox()
        self.set_translatable(self.download_only_check, "download_only")
        self.download_only_check.stateChanged.connect(self.on_download_mode_changed)
        opt.addWidget(self.download_only_check)

        self.mode_hint = QLabel()
        self.mode_hint.setObjectName("LabelHint")
        self.set_translatable(self.mode_hint, "mode_flash")
        opt.addWidget(self.mode_hint)

        task_card, task = self.create_card("card_task_title", "card_task_subtitle")
        self.progress_label = QLabel()
        self.set_translatable(self.progress_label, "task_idle")
        task.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        task.addWidget(self.progress_bar)

        row_btn = QHBoxLayout()
        self.run_btn = QPushButton()
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.set_translatable(self.run_btn, "btn_run")
        self.run_btn.clicked.connect(self.start_flash)
        row_btn.addWidget(self.run_btn)

        self.cancel_btn = QPushButton()
        self.cancel_btn.setObjectName("SecondaryButton")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.set_translatable(self.cancel_btn, "btn_cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_flash)
        row_btn.addWidget(self.cancel_btn)

        self.open_recovery_btn = QPushButton()
        self.open_recovery_btn.setObjectName("SecondaryButton")
        self.open_recovery_btn.setCursor(Qt.PointingHandCursor)
        self.set_translatable(self.open_recovery_btn, "btn_open_recovery")
        self.open_recovery_btn.clicked.connect(lambda: self.set_nav_index(1))
        row_btn.addWidget(self.open_recovery_btn)
        task.addLayout(row_btn)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(11)
        mid_row.addWidget(opt_card, 1)
        mid_row.addWidget(task_card, 1)
        layout.addLayout(mid_row)

        log_card, log = self.create_card("card_log_title", "card_log_subtitle")
        log_card.setProperty("priority", "high")
        self.log_text = QTextEdit()
        self.log_text.setObjectName("LogPanel")
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(108)
        self.log_text.setMaximumHeight(150)
        self.log_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.log_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        log.addWidget(self.log_text)
        layout.addWidget(log_card)

        layout.addStretch()
        scroll.setWidget(content)
        page_layout.addWidget(scroll)
        return page

    def create_recovery_page(self):
        page = QWidget()
        page.setObjectName("ContentPage")
        layout = QVBoxLayout(page)
        layout.setSpacing(11)

        top_card, top = self.create_card("card_recovery_title", "card_recovery_subtitle")
        top_card.setProperty("priority", "high")
        row = QHBoxLayout()
        self.recovery_product_label = QLabel()
        self.set_translatable(self.recovery_product_label, "label_product")
        self.recovery_product_label.setFixedWidth(92)
        self.recovery_product_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self.recovery_product_label)
        self.recovery_product_combo = QComboBox()
        self.recovery_product_combo.currentTextChanged.connect(
            lambda text: self.show_recovery_guide(text, load_images=True)
        )
        row.addWidget(self.recovery_product_combo)
        top.addLayout(row)
        layout.addWidget(top_card)

        detail_card, detail = self.create_card("card_recovery_detail_title")
        detail_card.setProperty("priority", "high")
        scroll = QScrollArea()
        scroll.setObjectName("SectionScroll")
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.recovery_content = QWidget()
        self.recovery_content.setObjectName("RecoveryContent")
        self.recovery_layout = QVBoxLayout(self.recovery_content)
        self.recovery_layout.setContentsMargins(4, 4, 4, 4)
        self.recovery_layout.setSpacing(9)
        scroll.setWidget(self.recovery_content)

        detail.addWidget(scroll)
        layout.addWidget(detail_card, 1)
        return page

    def create_about_page(self):
        page = QWidget()
        page.setObjectName("ContentPage")
        layout = QVBoxLayout(page)
        layout.setSpacing(11)

        about_card, about = self.create_card("card_about_title", "card_about_subtitle")
        self.about_text = QLabel()
        self.about_text.setWordWrap(True)
        self.set_translatable(self.about_text, "about_text")
        about.addWidget(self.about_text)
        layout.addWidget(about_card)

        links_card, links = self.create_card("card_links_title")
        self.wiki_btn = QPushButton()
        self.wiki_btn.setObjectName("SecondaryButton")
        self.wiki_btn.setCursor(Qt.PointingHandCursor)
        self.set_translatable(self.wiki_btn, "btn_wiki")
        self.wiki_btn.clicked.connect(lambda: self.open_url("https://wiki.seeedstudio.com/"))
        links.addWidget(self.wiki_btn)

        self.forum_btn = QPushButton()
        self.forum_btn.setObjectName("SecondaryButton")
        self.forum_btn.setCursor(Qt.PointingHandCursor)
        self.set_translatable(self.forum_btn, "btn_forum")
        self.forum_btn.clicked.connect(lambda: self.open_url("https://forum.seeedstudio.com/"))
        links.addWidget(self.forum_btn)

        self.github_btn = QPushButton()
        self.github_btn.setObjectName("SecondaryButton")
        self.github_btn.setCursor(Qt.PointingHandCursor)
        self.set_translatable(self.github_btn, "btn_github")
        self.github_btn.clicked.connect(lambda: self.open_url("https://github.com/Seeed-Studio"))
        links.addWidget(self.github_btn)

        layout.addWidget(links_card)
        layout.addStretch()
        return page

    def set_status(self, text_key, status_style):
        self.status_key = text_key
        self.status_style = status_style
        self.status_chip.setText(self.tr(text_key))
        self.status_chip.setProperty("status", status_style)
        self.status_chip.style().unpolish(self.status_chip)
        self.status_chip.style().polish(self.status_chip)
        self.status_chip.update()

    def set_nav_index(self, index):
        self.stack.setCurrentIndex(index)
        for idx, btn in enumerate(self.nav_buttons):
            btn.setProperty("active", idx == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

        page_map = {
            0: ("top_flash_title", "top_flash_subtitle"),
            1: ("top_recovery_title", "top_recovery_subtitle"),
            2: ("top_about_title", "top_about_subtitle"),
        }
        title_key, sub_key = page_map.get(index, ("top_flash_title", "top_flash_subtitle"))
        self.top_title.setText(self.tr(title_key))
        self.top_subtitle.setText(self.tr(sub_key))
        if index == 1 and self.recovery_product_combo.currentText():
            self.show_recovery_guide(self.recovery_product_combo.currentText(), load_images=True)

    def on_language_changed(self, index):
        self.lang = "zh" if index == 0 else "en"
        for widget, key in self.retranslate_pairs:
            widget.setText(self.tr(key))

        self.on_download_mode_changed()
        self.set_nav_index(self.stack.currentIndex())
        self.set_status(self.status_key, self.status_style)
        self.statusBar().showMessage(self.tr("statusbar_ready"))

        if self.product_combo.currentText():
            self.on_product_changed(self.product_combo.currentText())
        if self.recovery_product_combo.currentText():
            self.show_recovery_guide(
                self.recovery_product_combo.currentText(),
                load_images=(self.stack.currentIndex() == 1),
            )

    def populate_products(self):
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

        products = sorted(self.products.keys())
        self.product_combo.clear()
        self.recovery_product_combo.clear()
        self.product_combo.addItems(products)
        self.recovery_product_combo.addItems(products)
        self.run_btn.setEnabled(bool(products))

        if not products:
            self.product_info.setText(self.tr("warn_data_empty"))
            self.progress_label.setText(self.tr("status_error"))
            self.set_status("status_error", "error")
            return

        self.on_product_changed(self.product_combo.currentText())
        self.show_recovery_guide(self.recovery_product_combo.currentText(), load_images=False)
        self.append_log(self.tr("log_loaded", count=len(products)))

    def on_product_changed(self, product):
        self.l4t_combo.clear()
        versions = self.products.get(product, [])
        self.l4t_combo.addItems(versions)

        info = self.product_images.get(product, {})
        name = html.escape(info.get("name", product or "N/A"))
        latest = html.escape(versions[0] if versions else "N/A")
        wiki = info.get("wiki", "").strip()
        if wiki:
            wiki_escaped = html.escape(wiki, quote=True)
            wiki_link = f"<a href='{wiki_escaped}'>{wiki_escaped}</a>"
        else:
            wiki_link = "N/A"

        self.product_info.setText(
            self.tr(
                "product_info_html_tpl",
                name=name,
                latest=latest,
                count=len(versions),
                wiki_link=wiki_link,
            )
        )

    def on_download_mode_changed(self):
        self.mode_hint.setText(self.tr("mode_download" if self.download_only_check.isChecked() else "mode_flash"))

    @staticmethod
    def clear_layout(layout):
        while layout.count():
            child = layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def load_recovery_image(self, url):
        """Load and cache recovery image preview from local cache first."""
        if not url:
            return None
        if url in self.image_cache:
            return self.image_cache[url]

        local_path = self.recovery_local_images.get(url)
        if not local_path:
            local_path = self._local_image_path_for_url(url)
            self.recovery_local_images[url] = local_path

        pixmap = None
        if local_path.exists() and local_path.stat().st_size > 0:
            test = QPixmap(str(local_path))
            if not test.isNull():
                pixmap = test

        if not pixmap:
            pixmap = self._download_and_store_recovery_image(url, local_path)

        self.image_cache[url] = pixmap
        return pixmap

    def show_recovery_guide(self, product, load_images=True):
        self.clear_layout(self.recovery_layout)

        guide_data = None
        for series_data in self.recovery_guides.values():
            if product in series_data.get("products", []):
                guide_data = series_data
                break

        if not guide_data:
            no_data = QLabel(self.tr("no_guide"))
            no_data.setObjectName("LabelHint")
            self.recovery_layout.addWidget(no_data)
            self.recovery_layout.addStretch()
            return

        title = QLabel(f"{guide_data.get('name', 'Recovery')}")
        title.setObjectName("CardTitle")
        self.recovery_layout.addWidget(title)

        req = "\n".join(f"• {item}" for item in guide_data.get("requirements", []))
        req_block = QLabel(f"{self.tr('block_requirements')}\n{req}")
        req_block.setObjectName("InfoPanel")
        req_block.setWordWrap(True)
        self.recovery_layout.addWidget(req_block)

        steps = []
        for item in guide_data.get("steps", []):
            steps.append(f"{item.get('step', '?')}. {item.get('description', '')}")
        step_block = QLabel(f"{self.tr('block_steps')}\n" + "\n".join(steps))
        step_block.setObjectName("InfoPanel")
        step_block.setWordWrap(True)
        self.recovery_layout.addWidget(step_block)

        verification = guide_data.get("verification", {})
        verify_lines = [f"Command: {verification.get('command', '')}"]
        for module, usb_id in verification.get("ids", {}).items():
            verify_lines.append(f"• {module}: {usb_id}")
        verify_block = QLabel(f"{self.tr('block_verify')}\n" + "\n".join(verify_lines))
        verify_block.setObjectName("InfoPanel")
        verify_block.setWordWrap(True)
        self.recovery_layout.addWidget(verify_block)

        images = guide_data.get("images", [])
        if images and load_images:
            block_title = QLabel(self.tr("block_images"))
            block_title.setObjectName("CardTitle")
            self.recovery_layout.addWidget(block_title)
            for item in images:
                desc = item.get("description", "")
                url = item.get("url", "")

                desc_label = QLabel(f"• {desc}")
                desc_label.setObjectName("LabelHint")
                desc_label.setWordWrap(True)
                self.recovery_layout.addWidget(desc_label)

                pix = self.load_recovery_image(url)
                if pix:
                    preview = QLabel()
                    preview.setObjectName("InfoPanel")
                    preview.setAlignment(Qt.AlignCenter)
                    preview.setPixmap(pix.scaledToWidth(700, Qt.SmoothTransformation))
                    preview.setMinimumHeight(150)
                    self.recovery_layout.addWidget(preview)
                else:
                    fail = QLabel(self.tr("image_load_failed"))
                    fail.setObjectName("LabelHint")
                    self.recovery_layout.addWidget(fail)

        video = guide_data.get("video")
        if video:
            video_block = QLabel(f"{self.tr('block_video')}\n<a href='{video}'>{video}</a>")
            video_block.setObjectName("InfoPanel")
            video_block.setWordWrap(True)
            video_block.setOpenExternalLinks(True)
            self.recovery_layout.addWidget(video_block)

        self.recovery_layout.addStretch()

    def append_log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] [{level}] {message}")

    def start_flash(self):
        if self.flash_thread and self.flash_thread.isRunning():
            QMessageBox.information(self, self.tr("msg_info_title"), self.tr("hint_running"))
            return

        product = self.product_combo.currentText()
        l4t = self.l4t_combo.currentText()
        if not product or not l4t:
            QMessageBox.warning(self, self.tr("msg_error_title"), self.tr("warn_select"))
            return

        mode = self.tr("mode_download_short" if self.download_only_check.isChecked() else "mode_flash_short")
        verify = self.tr("verify_skip_short" if self.skip_verify_check.isChecked() else "verify_do_short")
        confirm = self.tr("confirm_tpl", product=product, l4t=l4t, mode=mode, verify=verify)

        reply = QMessageBox.question(
            self,
            self.tr("confirm_title"),
            confirm,
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(1)
        self.progress_label.setText(self.tr("task_started"))
        self.log_text.clear()
        self.append_log(self.tr("log_start", product=product, l4t=l4t))
        self.append_log(self.tr("log_mode", mode=mode, verify=verify))

        self.set_status("status_busy", "busy")
        self.statusBar().showMessage(self.tr("statusbar_running"))

        self.flash_thread = FlashThread(
            product,
            l4t,
            tr=self.tr,
            skip_verify=self.skip_verify_check.isChecked(),
            download_only=self.download_only_check.isChecked(),
        )
        self.flash_thread.progress.connect(self.on_flash_progress)
        self.flash_thread.progress_value.connect(self.on_flash_progress_value)
        self.flash_thread.finished.connect(self.on_flash_finished)
        self.flash_thread.start()

    def cancel_flash(self):
        if not self.flash_thread or not self.flash_thread.isRunning():
            return
        self.flash_thread.request_cancel()
        self.cancel_btn.setEnabled(False)
        self.progress_label.setText(self.tr("task_cancelling"))
        self.append_log(self.tr("task_cancelling"), "INFO")

    def on_flash_progress(self, message):
        self.progress_label.setText(message)
        self.append_log(message)
        self.statusBar().showMessage(message)

    def on_flash_progress_value(self, value):
        value = max(0, min(100, int(value)))
        if value > self.progress_bar.value():
            self.progress_bar.setValue(value)

    def on_flash_finished(self, success, message):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if success else max(self.progress_bar.value(), 95))

        if success:
            self.set_status("status_done", "success")
            self.progress_label.setText(self.tr("result_done_prefix", message=message))
            self.append_log(message, "SUCCESS")
            QMessageBox.information(self, self.tr("msg_done_title"), message)
        else:
            if message == self.tr("result_cancelled"):
                self.set_status("status_ready", "info")
                self.progress_label.setText(message)
                self.append_log(message, "INFO")
                QMessageBox.information(self, self.tr("msg_info_title"), message)
            else:
                self.set_status("status_error", "error")
                self.progress_label.setText(self.tr("result_error_prefix", message=message))
                self.append_log(message, "ERROR")
                QMessageBox.critical(self, self.tr("msg_error_title"), message)

        self.statusBar().showMessage(self.tr("statusbar_ready"))
        self.flash_thread = None

    @staticmethod
    def open_url(url):
        QDesktopServices.openUrl(QUrl(url))


def main():
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Seeed Jetson Flash")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
