"""后台 SFTP 文件上传线程（PC → Jetson）。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from qtpy.QtCore import QThread, Signal

from seeed_jetson_develop.core.runner import SSHRunner


class FileTransferThread(QThread):
    """通过 SSH/SFTP 把本地文件上传到 Jetson 指定目录。"""

    log = Signal(str)
    progress = Signal(int)
    file_done = Signal(str, bool)
    done = Signal(bool, str)

    def __init__(
        self,
        runner: SSHRunner,
        local_paths: list[Path],
        remote_dir: str,
        on_log: Callable[[str], None] | None = None,
    ):
        super().__init__()
        self._runner = runner
        self._local_paths = [Path(p) for p in local_paths]
        self._remote_dir = (remote_dir or ".").strip()
        if on_log:
            self.log.connect(on_log)

    def _emit_log(self, message: str) -> None:
        self.log.emit(message)

    def _ensure_remote_dir(self, sftp, remote_dir: str) -> bool:
        """递归创建远端目录（类似 mkdir -p）。"""
        if remote_dir in ("", ".", "~/"):
            return True
        parts = remote_dir.strip("/").split("/")
        built = ""
        for part in parts:
            if not part:
                continue
            built = f"{built}/{part}" if built else part
            try:
                sftp.mkdir(built)
            except OSError:
                # 通常是因为目录已存在
                pass
        return True

    def run(self) -> None:
        total_files = len(self._local_paths)
        if total_files == 0:
            self.done.emit(False, "no files to upload")
            return

        client = None
        sftp = None
        try:
            client, sftp = self._runner.open_sftp()
            self._ensure_remote_dir(sftp, self._remote_dir)

            # Filter valid files and compute total size for byte-based progress.
            valid_paths: list[Path] = []
            file_sizes: list[int] = []
            for local_path in self._local_paths:
                if local_path.is_dir():
                    self._emit_log(f"[skip] directory not supported yet: {local_path.name}")
                    self.file_done.emit(str(local_path), False)
                    continue
                if not local_path.exists():
                    self._emit_log(f"[skip] file not found: {local_path}")
                    self.file_done.emit(str(local_path), False)
                    continue
                valid_paths.append(local_path)
                file_sizes.append(local_path.stat().st_size)

            total_size = sum(file_sizes)
            uploaded_size = 0
            processed_files = len(valid_paths)

            for idx, local_path in enumerate(valid_paths, start=1):
                file_size = file_sizes[idx - 1]
                remote_path = f"{self._remote_dir.rstrip('/')}/{local_path.name}"
                self._emit_log(f"[upload] {local_path.name} -> {remote_path}")

                def _progress(
                    sent: int,
                    size: int,
                    name: str = local_path.name,
                    base: int = uploaded_size,
                ):
                    if size > 0:
                        file_pct = int(sent / size * 100)
                        self._emit_log(f"[progress] {name}: {file_pct}%")
                    if total_size > 0:
                        overall_pct = int((base + sent) / total_size * 100)
                        self.progress.emit(overall_pct)

                sftp.put(str(local_path), remote_path, callback=_progress)
                uploaded_size += file_size
                self._emit_log(f"[ok] uploaded {local_path.name}")
                self.file_done.emit(str(local_path), True)
                if total_size > 0:
                    self.progress.emit(int(uploaded_size / total_size * 100))
                else:
                    self.progress.emit(int(idx / processed_files * 100))

            self.progress.emit(100)
            self.done.emit(True, "upload completed")
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
