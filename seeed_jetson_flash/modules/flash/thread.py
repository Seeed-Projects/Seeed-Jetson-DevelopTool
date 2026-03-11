"""刷写后台线程"""
from PyQt5.QtCore import QThread, pyqtSignal
from seeed_jetson_flash.flash import JetsonFlasher


class FlashThread(QThread):
    progress_msg = pyqtSignal(str)
    progress_val = pyqtSignal(int)
    finished     = pyqtSignal(bool, str)

    def __init__(self, product, l4t, skip_verify=False, download_only=False):
        super().__init__()
        self.product       = product
        self.l4t           = l4t
        self.skip_verify   = skip_verify
        self.download_only = download_only
        self._cancel       = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            flasher = JetsonFlasher(
                self.product, self.l4t,
                progress_callback=self._on_dl,
                should_cancel=lambda: self._cancel,
            )
            self.progress_msg.emit("初始化..."); self.progress_val.emit(2)
            self.progress_msg.emit("下载固件中..."); self.progress_val.emit(5)
            if not flasher.download_firmware():
                self.finished.emit(False, "固件下载失败"); return
            self.progress_val.emit(50)
            if not self.skip_verify:
                self.progress_msg.emit("校验 SHA256...")
                if not flasher.verify_firmware():
                    self.finished.emit(False, "SHA256 校验失败"); return
            self.progress_val.emit(65)
            if self.download_only:
                self.progress_val.emit(100)
                self.finished.emit(True, "固件下载完成（未刷写）"); return
            self.progress_msg.emit("解压固件...")
            if not flasher.extract_firmware():
                self.finished.emit(False, "固件解压失败"); return
            self.progress_val.emit(80)
            self.progress_msg.emit("刷写中...")
            if not flasher.flash_firmware():
                self.finished.emit(False, "刷写失败"); return
            self.progress_val.emit(100)
            self.finished.emit(True, "刷写完成！")
        except Exception as e:
            self.finished.emit(False, str(e))

    def _on_dl(self, stage, cur, total):
        if stage == "download" and total:
            self.progress_val.emit(int(5 + (cur / total) * 45))
