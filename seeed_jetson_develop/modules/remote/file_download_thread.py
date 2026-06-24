"""后台 SFTP 文件下载线程（Jetson → PC）。"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from qtpy.QtCore import QThread, Signal

from seeed_jetson_develop.core.runner import SSHRunner


class FileDownloadThread(QThread):
    """通过 SSH/SFTP 把 Jetson 上的文件下载到 PC 指定目录。"""

    log = Signal(str)
    progress = Signal(int)
    file_done = Signal(str, bool)
    done = Signal(bool, str)

    def __init__(
        self,
        runner: SSHRunner,
        remote_paths: list[str],
        local_dir: Path,
        on_log: Callable[[str], None] | None = None,
    ):
        super().__init__()
        self._runner = runner
        self._remote_paths = list(remote_paths)
        self._local_dir = Path(local_dir)
        if on_log:
            self.log.connect(on_log)

    def _emit_log(self, message: str) -> None:
        self.log.emit(message)

    def run(self) -> None:
        total_files = len(self._remote_paths)
        if total_files == 0:
            self.done.emit(False, "no files to download")
            return

        client = None
        sftp = None
        try:
            client, sftp = self._runner.open_sftp()
            self._local_dir.mkdir(parents=True, exist_ok=True)

            for idx, remote_path in enumerate(self._remote_paths, start=1):
                name = Path(remote_path).name
                try:
                    sftp.stat(remote_path)
                except FileNotFoundError:
                    self._emit_log(f"[skip] remote file not found: {remote_path}")
                    self.file_done.emit(remote_path, False)
                    continue

                local_path = self._local_dir / name
                self._emit_log(f"[download] {remote_path} -> {local_path}")

                def _progress(sent: int, size: int, n=name):
                    if size > 0:
                        pct = int(sent / size * 100)
                        self._emit_log(f"[progress] {n}: {pct}%")

                sftp.get(remote_path, str(local_path), callback=_progress)
                self._emit_log(f"[ok] downloaded {name}")
                self.file_done.emit(remote_path, True)
                self.progress.emit(int(idx / total_files * 100))

            self.progress.emit(100)
            self.done.emit(True, "download completed")
        except Exception as e:
            self._emit_log(f"[failed] {type(e).__name__}: {e}")
            self.done.emit(False, str(e))
        finally:
            if sftp is not None:
                try:
                    sftp.close()
                except Exception:
                    pass
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
