"""后台 SFTP 文件上传线程（PC → Jetson），支持文件和文件夹递归上传。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from qtpy.QtCore import QThread, Signal

from seeed_jetson_develop.core.runner import SSHRunner


@dataclass
class _TransferItem:
    local_path: Path
    remote_path: str
    size: int


class FileTransferThread(QThread):
    """通过 SSH/SFTP 把本地文件或文件夹上传到 Jetson 指定目录。"""

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

    def _collect_items(self) -> list[_TransferItem]:
        """将本地路径展开为待上传文件列表，保持目录结构。"""
        items: list[_TransferItem] = []
        remote_base = self._remote_dir.rstrip("/")

        for local_path in self._local_paths:
            if not local_path.exists():
                self._emit_log(f"[skip] not found: {local_path}")
                self.file_done.emit(str(local_path), False)
                continue

            if local_path.is_file():
                remote_path = f"{remote_base}/{local_path.name}"
                items.append(_TransferItem(local_path, remote_path, local_path.stat().st_size))
            elif local_path.is_dir():
                # 保持文件夹结构：remote_dir / folder_name / ...
                base_remote = f"{remote_base}/{local_path.name}"
                for child in local_path.rglob("*"):
                    if child.is_file():
                        relative = child.relative_to(local_path)
                        remote_path = f"{base_remote}/{relative.as_posix()}"
                        items.append(_TransferItem(child, remote_path, child.stat().st_size))
            else:
                self._emit_log(f"[skip] unsupported path type: {local_path}")
                self.file_done.emit(str(local_path), False)

        return items

    def run(self) -> None:
        if not self._local_paths:
            self.done.emit(False, "no files to upload")
            return

        client = None
        sftp = None
        try:
            client, sftp = self._runner.open_sftp()
            self._ensure_remote_dir(sftp, self._remote_dir)

            items = self._collect_items()
            if not items:
                self.done.emit(False, "no valid files to upload")
                return

            total_size = sum(item.size for item in items)
            uploaded_size = 0

            for item in items:
                self._ensure_remote_dir(sftp, str(Path(item.remote_path).parent))
                self._emit_log(f"[upload] {item.local_path} -> {item.remote_path}")

                def _progress(
                    sent: int,
                    size: int,
                    name: str = item.local_path.name,
                    base: int = uploaded_size,
                ):
                    if size > 0:
                        file_pct = int(sent / size * 100)
                        self._emit_log(f"[progress] {name}: {file_pct}%")
                    if total_size > 0:
                        overall_pct = int((base + sent) / total_size * 100)
                        self.progress.emit(overall_pct)

                sftp.put(str(item.local_path), item.remote_path, callback=_progress)
                uploaded_size += item.size
                self._emit_log(f"[ok] uploaded {item.local_path.name}")
                self.file_done.emit(str(item.local_path), True)
                if total_size > 0:
                    self.progress.emit(int(uploaded_size / total_size * 100))

            self.progress.emit(100)
            self.done.emit(True, f"upload completed ({len(items)} items)")
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
