"""刷写后台线程"""
from PyQt5.QtCore import QThread, pyqtSignal
from seeed_jetson_develop.flash import JetsonFlasher


class FlashThread(QThread):
    progress_msg = pyqtSignal(str)
    progress_val = pyqtSignal(int)
    finished     = pyqtSignal(bool, str)

    def __init__(self, product, l4t, skip_verify=False, download_only=False,
                 force_redownload=False, prepare_only=False):
        """
        prepare_only=True : 只做下载+解压，不刷写（"下载/解压 BSP" 按钮用）
        force_redownload   : 忽略已有压缩包，强制重下
        """
        super().__init__()
        self.product          = product
        self.l4t              = l4t
        self.skip_verify      = skip_verify
        self.download_only    = download_only
        self.force_redownload = force_redownload
        self.prepare_only     = prepare_only
        self._cancel          = False

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

            # ── 下载阶段（有包则跳过，除非 force_redownload）──
            if self.force_redownload or not flasher.firmware_cached():
                self.progress_msg.emit("下载固件中..."); self.progress_val.emit(5)
                if not flasher.download_firmware(force_redownload=self.force_redownload):
                    self.finished.emit(False, "固件下载失败"); return
            else:
                self.progress_msg.emit("压缩包已存在，跳过下载"); self.progress_val.emit(50)

            self.progress_val.emit(50)

            # ── 校验阶段 ──
            if not self.skip_verify:
                self.progress_msg.emit("校验 SHA256...")
                if not flasher.verify_firmware():
                    self.finished.emit(False, "SHA256 校验失败"); return

            self.progress_val.emit(60)

            if self.download_only:
                self.progress_val.emit(100)
                self.finished.emit(True, "固件下载完成（未刷写）"); return

            # ── 解压阶段 ──
            self.progress_msg.emit("解压固件...")
            if not flasher.extract_firmware():
                self.finished.emit(False, "固件解压失败"); return
            self.progress_val.emit(80)

            if self.prepare_only:
                self.progress_val.emit(100)
                self.finished.emit(True, "下载并解压完成，可进入下一步刷写"); return

            # ── 刷写阶段 ──
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
