"""Flash background thread and progress estimation."""

from __future__ import annotations

import re

from PyQt5.QtCore import QThread, pyqtSignal

from seeed_jetson_develop.flash import JetsonFlasher
from seeed_jetson_develop.gui.i18n import get_language, t


class _FlashProgressEstimator:
    """Estimate flash progress from l4t_initrd_flash logs."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.progress = 0
        self._wait_count = 0
        self._current_index_target = None
        self._external_total_items = None
        self._external_last_item = -1
        self._external_started = False
        self._external_done = False
        self._emmc_started = False
        self._emmc_done = False
        self._qspi_started = False
        self._qspi_done = False
        self._qspi_expected = 0
        self._qspi_written = 0
        self._qspi_expected_seen = set()

    def _set_progress(self, value):
        value = max(0, min(100, int(value)))
        if value > self.progress:
            self.progress = value
            return value
        return None

    def _external_progress(self):
        if self._external_done:
            return 1.0
        if self._external_total_items and self._external_last_item >= 0:
            return max(0.08, min(0.96, (self._external_last_item + 1) / self._external_total_items))
        return 0.05 if self._external_started else 0.0

    def _emmc_progress(self):
        if self._emmc_done:
            return 1.0
        return 0.25 if self._emmc_started else 0.0

    def _qspi_progress(self):
        if self._qspi_done:
            return 1.0
        if self._qspi_expected > 0:
            ratio = self._qspi_written / self._qspi_expected
            return max(0.05 if self._qspi_started else 0.0, min(0.98, ratio))
        return 0.05 if self._qspi_started else 0.0

    def _recompute_flash_progress(self):
        fraction = (
            0.10 * self._emmc_progress()
            + 0.55 * self._external_progress()
            + 0.35 * self._qspi_progress()
        )
        return self._set_progress(50 + int(48 * min(1.0, fraction)))

    def update(self, line):
        text = (line or "").strip()
        if not text:
            return None

        if "Step 1: Build the flashing environment" in text:
            return self._set_progress(12)
        if "Finish creating flash environment" in text:
            return self._set_progress(20)
        if "Step 2: Boot the device with flash initrd image" in text:
            return self._set_progress(24)
        if "Entering RCM boot" in text:
            return self._set_progress(28)
        if "RCM-boot started" in text:
            return self._set_progress(38)
        if "Step 3: Start the flashing process" in text:
            return self._set_progress(42)
        if "Waiting for target to boot-up" in text or "Waiting for device to expose ssh" in text:
            self._wait_count += 1
            return self._set_progress(min(49, 42 + min(self._wait_count, 12) // 2))
        if "SSH ready" in text or "Run command: flash on " in text:
            return self._set_progress(50)

        if "/mnt/external/flash.idx" in text:
            self._current_index_target = "external"
            self._external_started = True
        elif "/mnt/internal/flash.idx" in text:
            self._current_index_target = "internal"

        match = re.search(r"max_index=(\d+)", text)
        if match and self._current_index_target == "external":
            self._external_total_items = max(1, int(match.group(1)) + 1)
            return self._recompute_flash_progress()

        if "Starting to flash the eMMC." in text:
            self._emmc_started = True
            return self._recompute_flash_progress()
        if "Successfully flashed the eMMC." in text:
            self._emmc_done = True
            return self._recompute_flash_progress()
        if "Starting to flash the external device." in text:
            self._external_started = True
            return self._recompute_flash_progress()
        if "Successfully flashed the external device." in text:
            self._external_done = True
            return self._recompute_flash_progress()
        if "Starting to flash the QSPI." in text:
            self._qspi_started = True
            return self._recompute_flash_progress()
        if "Successfully flashed the QSPI." in text:
            self._qspi_done = True
            return self._recompute_flash_progress()
        if "Flashing success" in text or "Flash is successful" in text:
            return self._set_progress(99)

        match = re.search(r"writing item=(\d+),", text)
        if match and self._current_index_target == "external":
            self._external_started = True
            self._external_last_item = max(self._external_last_item, int(match.group(1)))
            return self._recompute_flash_progress()

        match = re.search(r"Writing .+ \((\d+) bytes\) into\s+/dev/mtd0", text)
        if match:
            self._qspi_started = True
            if text not in self._qspi_expected_seen:
                self._qspi_expected_seen.add(text)
                self._qspi_expected += int(match.group(1))
            return self._recompute_flash_progress()

        match = re.search(r"Copied (\d+) bytes from .+ to address 0x[0-9a-fA-F]+ in flash", text)
        if match:
            self._qspi_started = True
            self._qspi_written += int(match.group(1))
            return self._recompute_flash_progress()

        return None


class FlashThread(QThread):
    progress_msg = pyqtSignal(str)
    progress_val = pyqtSignal(int)
    progress_log = pyqtSignal(str)
    download_progress = pyqtSignal(int, int)
    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        product,
        l4t,
        skip_verify=False,
        download_only=False,
        force_redownload=False,
        prepare_only=False,
        flash_only=False,
        download_dir=None,
        lang: str | None = None,
    ):
        super().__init__()
        self.product = product
        self.l4t = l4t
        self.skip_verify = skip_verify
        self.download_only = download_only
        self.force_redownload = force_redownload
        self.prepare_only = prepare_only
        self.flash_only = flash_only
        self.download_dir = download_dir
        self.lang = lang or get_language()
        self._cancel = False
        self._flash_progress = _FlashProgressEstimator()
        self._last_log_pct = -1   # 上次打印日志时的进度百分比

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = t(key, lang=self.lang, **kwargs)
        return default if text == key else text

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            self._flash_progress.reset()
            flasher = JetsonFlasher(
                self.product,
                self.l4t,
                progress_callback=self._on_dl,
                should_cancel=lambda: self._cancel,
                download_dir=self.download_dir,
            )
            self.progress_msg.emit(self._tr("flash.thread.initializing", "Initializing..."))
            self.progress_val.emit(2)

            if self.flash_only:
                self.progress_msg.emit(self._tr("flash.thread.flashing", "Flashing..."))
                self.progress_val.emit(10)
                if not flasher.flash_firmware():
                    self.finished.emit(False, self._tr("flash.thread.flash_failed", "Flash failed"))
                    return
                self.progress_val.emit(100)
                self.finished.emit(True, self._tr("flash.thread.flash_completed", "Flash completed!"))
                return

            if self.force_redownload or not flasher.firmware_cached():
                self.progress_msg.emit(self._tr("flash.thread.downloading", "Downloading firmware..."))
                self.progress_val.emit(5)
                if not flasher.download_firmware(force_redownload=self.force_redownload):
                    self.finished.emit(False, self._tr("flash.thread.download_failed", "Firmware download failed"))
                    return
            else:
                self.progress_msg.emit(self._tr("flash.thread.archive_exists", "Archive already exists, skipping download"))
                self.progress_val.emit(50)

            self.progress_val.emit(50)
            if not self.skip_verify:
                self.progress_msg.emit(self._tr("flash.thread.verifying", "Verifying SHA256..."))
                if not flasher.verify_firmware():
                    self.finished.emit(False, self._tr("flash.thread.verify_failed", "SHA256 verification failed"))
                    return
            self.progress_val.emit(60)

            if self.download_only:
                self.progress_val.emit(100)
                self.finished.emit(True, self._tr("flash.thread.download_only_done", "Firmware download completed (not flashed)"))
                return

            self.progress_msg.emit(self._tr("flash.thread.extracting", "Extracting firmware..."))
            if not flasher.extract_firmware():
                self.finished.emit(False, self._tr("flash.thread.extract_failed", "Firmware extraction failed"))
                return
            self.progress_val.emit(80)

            if self.prepare_only:
                self.progress_val.emit(100)
                self.finished.emit(
                    True,
                    self._tr(
                        "flash.thread.prepare_only_done",
                        "Download and extraction completed. You can continue to flashing.",
                    ),
                )
                return

            self.progress_msg.emit(self._tr("flash.thread.flashing", "Flashing..."))
            if not flasher.flash_firmware():
                self.finished.emit(False, self._tr("flash.thread.flash_failed", "Flash failed"))
                return
            self.progress_val.emit(100)
            self.finished.emit(True, self._tr("flash.thread.flash_completed", "Flash completed!"))
        except InterruptedError:
            self.finished.emit(False, self._tr("flash.thread.cancelled", "Cancelled by user"))
        except Exception as exc:
            self.finished.emit(False, str(exc))

    def _on_dl(self, stage, cur, total):
        if stage == "download":
            self.download_progress.emit(int(cur), int(total))
            if total:
                pct = int(cur / total * 100)
                self.progress_val.emit(int(5 + (cur / total) * 45))
                # 每变化 2% 才打印一次，避免刷屏
                if pct >= self._last_log_pct + 2 or pct == 100:
                    self._last_log_pct = pct
                    def _fmt(b):
                        if b >= 1024 ** 3: return f"{b / 1024 ** 3:.2f} GB"
                        if b >= 1024 ** 2: return f"{b / 1024 ** 2:.1f} MB"
                        return f"{b / 1024:.0f} KB"
                    remaining = total - cur
                    log_line = (
                        f"[下载] {_fmt(cur)} / {_fmt(total)} ({pct}%)"
                        f"  剩余 {_fmt(remaining)}"
                    )
                    self.progress_log.emit(log_line)
        elif stage == "verify":
            if total:
                self.progress_val.emit(int(50 + (cur / total) * 10))
        elif stage == "extract":
            if total:
                self.progress_val.emit(int(60 + (cur / total) * 20))
        elif stage == "log":
            line = str(cur)
            self.progress_log.emit(line)
            pct = self._flash_progress.update(line)
            if pct is not None:
                self.progress_val.emit(pct)
