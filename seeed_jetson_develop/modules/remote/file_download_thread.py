"""后台 SFTP 文件下载线程（Jetson → PC），支持文件和文件夹递归下载。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from qtpy.QtCore import QThread, Signal

from seeed_jetson_develop.core.runner import SSHRunner


@dataclass
class _DownloadItem:
    remote_path: str
    local_path: Path
    size: int


class FileDownloadThread(QThread):
    """通过 SSH/SFTP 把 Jetson 上的文件或文件夹下载到 PC 指定目录。"""

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

    def _collect_remote_items(
        self,
        sftp,
        remote_path: str,
        local_base: Path,
    ) -> list[_DownloadItem]:
        """递归收集远程文件，保持目录结构。"""
        items: list[_DownloadItem] = []
        try:
            stat = sftp.stat(remote_path)
        except FileNotFoundError:
            self._emit_log(f"[skip] remote not found: {remote_path}")
            self.file_done.emit(remote_path, False)
            return items

        if not (stat.st_mode & 0o40000):
            # Regular file
            local_path = local_base / Path(remote_path).name
            items.append(_DownloadItem(remote_path, local_path, stat.st_size))
            return items

        # Directory: recreate structure under local_base / dir_name
        dir_name = Path(remote_path).name
        local_dir = local_base / dir_name
        try:
            for entry in sftp.listdir_attr(remote_path):
                if entry.filename.startswith("."):
                    continue
                child_remote = f"{remote_path.rstrip('/')}/{entry.filename}"
                items.extend(self._collect_remote_items(sftp, child_remote, local_dir))
        except Exception as e:
            self._emit_log(f"[skip] cannot list {remote_path}: {e}")
            self.file_done.emit(remote_path, False)

        return items

    def run(self) -> None:
        if not self._remote_paths:
            self.done.emit(False, "no files to download")
            return

        client = None
        sftp = None
        try:
            client, sftp = self._runner.open_sftp()
            self._local_dir.mkdir(parents=True, exist_ok=True)

            items: list[_DownloadItem] = []
            for remote_path in self._remote_paths:
                items.extend(self._collect_remote_items(sftp, remote_path, self._local_dir))

            if not items:
                self.done.emit(False, "no valid files to download")
                return

            total_size = sum(item.size for item in items)
            downloaded_size = 0

            for item in items:
                item.local_path.parent.mkdir(parents=True, exist_ok=True)
                self._emit_log(f"[download] {item.remote_path} -> {item.local_path}")

                def _progress(
                    sent: int,
                    size: int,
                    name: str = item.local_path.name,
                    base: int = downloaded_size,
                ):
                    if size > 0:
                        file_pct = int(sent / size * 100)
                        self._emit_log(f"[progress] {name}: {file_pct}%")
                    if total_size > 0:
                        overall_pct = int((base + sent) / total_size * 100)
                        self.progress.emit(overall_pct)

                sftp.get(item.remote_path, str(item.local_path), callback=_progress)
                downloaded_size += item.size
                self._emit_log(f"[ok] downloaded {item.local_path.name}")
                self.file_done.emit(item.remote_path, True)
                if total_size > 0:
                    self.progress.emit(int(downloaded_size / total_size * 100))

            self.progress.emit(100)
            self.done.emit(True, f"download completed ({len(items)} items)")
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
