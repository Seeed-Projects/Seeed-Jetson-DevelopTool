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

            # Pre-stat files so we can report byte-based overall progress.
            valid_paths: list[str] = []
            file_sizes: list[int] = []
            for remote_path in self._remote_paths:
                try:
                    stat = sftp.stat(remote_path)
                    valid_paths.append(remote_path)
                    file_sizes.append(stat.st_size)
                except FileNotFoundError:
                    self._emit_log(f"[skip] remote file not found: {remote_path}")
                    self.file_done.emit(remote_path, False)

            total_size = sum(file_sizes)
            downloaded_size = 0
            processed_files = len(valid_paths)

            for idx, remote_path in enumerate(valid_paths, start=1):
                name = Path(remote_path).name
                file_size = file_sizes[idx - 1]
                local_path = self._local_dir / name
                self._emit_log(f"[download] {remote_path} -> {local_path}")

                def _progress(
                    sent: int,
                    size: int,
                    n: str = name,
                    base: int = downloaded_size,
                    fsize: int = file_size,
                ):
                    if size > 0:
                        file_pct = int(sent / size * 100)
                        self._emit_log(f"[progress] {n}: {file_pct}%")
                    if total_size > 0:
                        overall_pct = int((base + sent) / total_size * 100)
                        self.progress.emit(overall_pct)

                sftp.get(remote_path, str(local_path), callback=_progress)
                downloaded_size += file_size
                self._emit_log(f"[ok] downloaded {name}")
                self.file_done.emit(remote_path, True)
                if total_size > 0:
                    self.progress.emit(int(downloaded_size / total_size * 100))
                else:
                    self.progress.emit(int(idx / processed_files * 100))

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
