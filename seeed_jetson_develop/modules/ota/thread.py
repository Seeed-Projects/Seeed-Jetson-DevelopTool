"""OTA execution thread — download payload + transfer + run OTA on Jetson."""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from seeed_jetson_develop.core.runner import SSHRunner

log = logging.getLogger("seeed.ota")
_CACHE_DIR = Path.home() / ".cache" / "seeed-jetson" / "ota"
_CHUNK_SIZE = 65536


def _human_size(size_bytes: int) -> str:
    if size_bytes >= 1 << 30:
        return f"{size_bytes / (1 << 30):.2f} GB"
    if size_bytes >= 1 << 20:
        return f"{size_bytes / (1 << 20):.2f} MB"
    if size_bytes >= 1 << 10:
        return f"{size_bytes / (1 << 10):.2f} KB"
    return f"{size_bytes} B"


def _download_file(url: str, dest: Path, on_progress, on_log, should_cancel) -> Path:
    """Download url to dest with resume support. Returns final Path."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    headers = {}
    start_offset = 0
    if part.exists():
        start_offset = part.stat().st_size
        headers["Range"] = f"bytes={start_offset}-"
        on_log(f"[info] resuming from {start_offset} bytes")

    on_log(f"[info] downloading from {url[:80]}...")
    r = requests.get(url, headers=headers, stream=True, timeout=30, allow_redirects=True)
    r.raise_for_status()

    ct = r.headers.get("content-type", "").lower()
    if "text/html" in ct:
        # Likely a login / redirect page instead of the binary payload
        snippet = r.content[:512].decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"Server returned HTML instead of file (content-type={ct}). "
            f"Please check the URL or append '?download=1'. Snippet: {snippet[:200]}"
        )

    total = int(r.headers.get("content-length", 0))
    if r.status_code == 206 and start_offset:
        total += start_offset
    elif r.status_code != 206 and start_offset:
        # Server doesn't support resume; restart
        part.unlink(missing_ok=True)
        start_offset = 0

    mode = "ab" if r.status_code == 206 and start_offset else "wb"
    written = start_offset

    with open(part, mode) as f:
        for chunk in r.iter_content(chunk_size=_CHUNK_SIZE):
            if should_cancel():
                raise InterruptedError("Cancelled by user")
            if chunk:
                f.write(chunk)
                written += len(chunk)
                on_progress(written, total)

    part.replace(dest)
    on_log(f"[ok] saved to {dest} ({_human_size(dest.stat().st_size)})")
    return dest


class OTAThread(QThread):
    """Background thread that downloads payload, transfers to Jetson, and runs OTA."""

    log = pyqtSignal(str)
    progress = pyqtSignal(int)       # 0-100 overall
    download_progress = pyqtSignal(int, int)  # current_bytes, total_bytes
    stage = pyqtSignal(str)          # "download" | "upload" | "prepare" | "execute"
    done = pyqtSignal(bool, str)     # success, message

    def __init__(
        self,
        runner: SSHRunner,
        ota_path: dict,
        payload_option: dict,
        backup_files: list[str],
    ):
        super().__init__()
        self._runner = runner
        self._ota_path = ota_path
        self._payload_option = payload_option
        self._backup_files = backup_files
        self._cancel = False
        self._cancel_lock = threading.Lock()

    def cancel(self):
        with self._cancel_lock:
            self._cancel = True

    def _should_cancel(self) -> bool:
        with self._cancel_lock:
            return self._cancel

    def _emit_log(self, msg: str):
        self.log.emit(msg)

    def _emit_progress(self, pct: int):
        self.progress.emit(max(0, min(100, pct)))

    def _on_download_progress(self, current: int, total: int):
        self.download_progress.emit(current, total)
        if total > 0:
            pct = int(current / total * 25)  # payload download = 0-25%
            self._emit_progress(pct)
            # log every ~5% or every 50 MB to avoid flooding
            step = max(1, total // 20)
            if current % step < 65536 or current == total:
                self._emit_log(
                    f"[download payload] {_human_size(current)} / {_human_size(total)} "
                    f"({current/total*100:.1f}%)"
                )

    def _on_tools_download_progress(self, current: int, total: int):
        self.download_progress.emit(current, total)
        if total > 0:
            pct = int(current / total * 10) + 25  # tools download = 25-35%
            self._emit_progress(pct)
            step = max(1, total // 10)
            if current % step < 65536 or current == total:
                self._emit_log(
                    f"[download tools] {_human_size(current)} / {_human_size(total)} "
                    f"({current/total*100:.1f}%)"
                )

    def _ssh_run(self, cmd: str, timeout: int = 60, use_sudo: bool = False) -> tuple[int, str]:
        if self._should_cancel():
            raise InterruptedError("Cancelled")
        if use_sudo and self._runner.sudo_password:
            import shlex
            cmd = (
                "_S() { printf '%s\\n' \"$SEEED_SUDO_PASSWORD\" | command sudo -S -p '' \"$@\" 2>&1; return $?; }; "
                f"_S bash -c {shlex.quote(cmd)}"
            )
        rc, out = self._runner.run(cmd, timeout=timeout)
        return rc, out

    def _sftp_put(self, local_path: Path, remote_path: str, stage_name: str = "upload"):
        if self._should_cancel():
            raise InterruptedError("Cancelled")
        self._emit_log(f"[info] uploading {local_path.name} -> {remote_path}")
        total_size = local_path.stat().st_size

        def _on_progress(sent: int, total: int):
            if self._should_cancel():
                raise InterruptedError("Cancelled")
            pct = int(sent / total * 20) + 35  # upload = 35-55%
            self._emit_progress(pct)
            step = max(1, total // 10)
            if sent % step < 65536 or sent == total:
                self._emit_log(
                    f"[upload] {_human_size(sent)} / {_human_size(total)} "
                    f"({sent/total*100:.1f}%)"
                )

        client, sftp = self._runner.open_sftp()
        try:
            sftp.put(str(local_path), remote_path, callback=_on_progress)
        finally:
            sftp.close()
            client.close()
        self._emit_log(f"[ok] upload complete")

    def run(self):
        try:
            self._run_ota()
        except InterruptedError:
            self._emit_log("[cancelled] OTA cancelled by user")
            self.done.emit(False, "Cancelled")
        except Exception as e:
            log.exception("OTA failed")
            self._emit_log(f"[failed] {type(e).__name__}: {e}")
            self.done.emit(False, str(e))

    def _run_ota(self):
        payload = self._payload_option
        ota_path = self._ota_path
        url = payload.get("url", "")
        filename = payload.get("filename", "ota_payload.tar.gz")
        local_payload = _CACHE_DIR / filename

        # ── 1. Download payload to PC cache ──
        self.stage.emit("download")
        if not local_payload.exists():
            self._emit_log("[step] downloading OTA payload...")
            local_payload = _download_file(
                url, local_payload,
                self._on_download_progress,
                self._emit_log,
                self._should_cancel,
            )
        else:
            self._emit_log(f"[info] using cached payload: {local_payload}")

        self._emit_progress(25)

        # ── 2. Download OTA tools to PC cache ──
        tools_url = ota_path.get("ota_tools_url", "")
        tools_fn = ota_path.get("ota_tools_filename", "ota_tools.tbz2")
        local_tools = _CACHE_DIR / tools_fn
        if not local_tools.exists():
            self._emit_log(f"[step] downloading OTA tools to PC cache ({tools_fn})...")
            local_tools = _download_file(
                tools_url, local_tools,
                self._on_tools_download_progress,
                self._emit_log,
                self._should_cancel,
            )
        else:
            self._emit_log(f"[info] using cached OTA tools: {local_tools}")
        self._emit_progress(35)

        # ── 3. Prepare Jetson workspace ──
        self._emit_log("[step] preparing Jetson workspace...")
        ws = "$HOME/ota_ws"
        rc, out = self._ssh_run(f"mkdir -p {ws}", timeout=10)
        if rc != 0:
            raise RuntimeError(f"failed to create workspace: {out}")

        # Install deps
        self._emit_log("[step] installing dependencies...")
        rc, out = self._ssh_run(
            "apt-get update && apt-get install -y efibootmgr nvme-cli",
            timeout=120,
            use_sudo=True,
        )
        if rc != 0:
            self._emit_log(f"[warn] dependency install may have issues: {out}")
        self._emit_progress(40)

        # ── 4. Upload payload + OTA tools via SFTP ──
        remote_payload = f"/home/{self._runner.username}/ota_ws/{filename}"
        remote_tools = f"/home/{self._runner.username}/ota_ws/{tools_fn}"
        self.stage.emit("upload")
        self._sftp_put(local_tools, remote_tools)
        self._sftp_put(local_payload, remote_payload)

        # Extract OTA tools on Jetson
        self._emit_log("[step] extracting OTA tools on Jetson...")
        rc, out = self._ssh_run(
            f"cd {ws} && tar xf {tools_fn}",
            timeout=120,
        )
        if rc != 0:
            raise RuntimeError(f"failed to extract OTA tools: {out}")
        self._emit_progress(55)

        # ── 5. Backup list ──
        if self._backup_files:
            self._emit_log("[step] writing backup file list...")
            backup_path = f"/home/{self._runner.username}/ota_ws/ota_backup_files_list.txt"
            content = "\n".join(self._backup_files)
            rc, out = self._ssh_run(
                f"cat > {backup_path} << 'EOF'\n{content}\nEOF",
                timeout=10,
            )
            if rc != 0:
                self._emit_log(f"[warn] failed to write backup list: {out}")
            else:
                # copy to version_upgrade dir
                self._ssh_run(
                    f"cp {backup_path} {ws}/Linux_for_Tegra/tools/ota_tools/version_upgrade/",
                    timeout=10,
                )
        self._emit_progress(60)

        # ── 6. Preserve data ──
        self.stage.emit("prepare")
        self._emit_log("[step] preserving data...")
        rc, out = self._ssh_run(
            f"cd {ws}/Linux_for_Tegra/tools/ota_tools/version_upgrade && bash ./nv_ota_preserve_data.sh",
            timeout=60,
        )
        if rc != 0:
            self._emit_log(f"[warn] preserve data script returned rc={rc}: {out}")
        self._emit_progress(65)

        # ── 7. Start OTA ──
        self.stage.emit("execute")
        self._emit_log("[step] starting OTA...")
        self._emit_progress(65)
        rc, out = self._ssh_run(
            f"cd {ws}/Linux_for_Tegra/tools/ota_tools/version_upgrade && "
            f"./nv_ota_start.sh {ws}/{filename}",
            timeout=900,
            use_sudo=True,
        )
        self._emit_log(out)
        # nv_ota_start.sh triggers a reboot; SSH may drop before a clean exit.
        if rc != 0:
            lower = out.lower()
            if "reboot" in lower or "ota" in lower or "upgrade" in lower:
                self._emit_log(f"[info] nv_ota_start.sh returned rc={rc} (likely due to reboot)")
            else:
                raise RuntimeError(f"nv_ota_start.sh failed (rc={rc})")

        self._emit_progress(90)
        self._emit_log("[ok] OTA script executed. Device will reboot automatically.")
        self._emit_progress(100)
        self.done.emit(True, "OTA started successfully. The device will reboot.")
