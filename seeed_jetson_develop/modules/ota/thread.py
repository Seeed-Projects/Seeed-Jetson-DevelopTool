"""OTA execution thread — download payload + transfer + run OTA on Jetson."""
from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
import threading
import time
from pathlib import Path

import requests
from qtpy.QtCore import QThread, Signal

from seeed_jetson_develop.core.runner import SSHRunner

log = logging.getLogger("seeed.ota")
_CACHE_DIR = Path.home() / ".cache" / "seeed-jetson" / "ota"
_CHUNK_SIZE = 65536
_PARALLEL_DOWNLOAD_MIN_BYTES = 100 * 1024 * 1024  # use aria2c for files >100MB


def _human_size(size_bytes: int) -> str:
    if size_bytes >= 1 << 30:
        return f"{size_bytes / (1 << 30):.2f} GB"
    if size_bytes >= 1 << 20:
        return f"{size_bytes / (1 << 20):.2f} MB"
    if size_bytes >= 1 << 10:
        return f"{size_bytes / (1 << 10):.2f} KB"
    return f"{size_bytes} B"


def _ensure_sharepoint_download(url: str) -> str:
    """Ensure SharePoint 'download=1' query parameter is present."""
    try:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    except ImportError:
        return url
    parsed = urlparse(url)
    if "sharepoint.com" not in parsed.netloc.lower():
        return url
    qs = parse_qs(parsed.query)
    if "download" not in qs:
        qs["download"] = ["1"]
        new_query = urlencode(qs, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    return url


def _download_with_aria2c(
    url: str,
    dest: Path,
    total: int,
    on_progress,
    on_log,
    should_cancel,
) -> Path | None:
    """Try to download with aria2c (multi-connection) and return dest on success."""
    if not shutil.which("aria2c"):
        return None

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    on_log("[info] using aria2c for multi-connection download")

    cmd = [
        "aria2c",
        "--continue=true",
        "--max-connection-per-server=16",
        "--split=16",
        "--min-split-size=1M",
        "--file-allocation=none",
        "--summary-interval=0",
        "--console-log-level=warn",
        "--download-result=hide",
        "--dir", str(part.parent),
        "--out", part.name,
        url,
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    last_size = 0
    try:
        while proc.poll() is None:
            if should_cancel():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                raise InterruptedError("Cancelled by user")

            if part.exists():
                current = part.stat().st_size
                if current != last_size:
                    on_progress(current, total)
                    last_size = current
            time.sleep(0.5)

        proc.wait()
        if proc.returncode == 0 and part.exists():
            part.replace(dest)
            on_log(f"[ok] saved to {dest} ({_human_size(dest.stat().st_size)})")
            return dest
        else:
            out = proc.stdout.read() if proc.stdout else ""
            on_log(f"[warn] aria2c failed (rc={proc.returncode}): {out[:500]}")
            return None
    except InterruptedError:
        raise
    except Exception as e:
        on_log(f"[warn] aria2c error: {e}")
        return None


def _sha256_file(path: Path) -> str:
    """Return lower-case hex SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def _verify_sha256(path: Path, expected: str | None, on_log) -> bool:
    """Verify file sha256. Returns True if verified or skipped; raises on mismatch."""
    if not expected:
        on_log(f"[info] sha256 not configured, skipping sha256 verification for {path.name}")
        return True
    expected = expected.strip().lower()
    if not expected:
        return True
    on_log(f"[info] verifying sha256 for {path.name}...")
    actual = _sha256_file(path)
    if actual != expected:
        raise RuntimeError(
            f"sha256 mismatch for {path.name}: expected {expected}, got {actual}"
        )
    on_log(f"[ok] sha256 verified for {path.name}")
    return True


def _verify_cached_file(path: Path, url: str, expected_sha256: str | None, on_log) -> None:
    """Verify a cached file is complete.

    If sha256 is configured, use it. Otherwise verify the file size against the
    remote Content-Length so that incomplete downloads cannot be reused.
    """
    _verify_sha256(path, expected_sha256, on_log)
    if not expected_sha256 or not expected_sha256.strip():
        expected_total = _http_total_size(url, on_log)
        _verify_downloaded_size(path, expected_total, on_log)


def _http_total_size(url: str, on_log) -> int:
    """Return total Content-Length for url via HEAD, or 0 if unknown."""
    try:
        r = requests.head(url, allow_redirects=True, timeout=30)
        r.raise_for_status()
        return int(r.headers.get("content-length", 0))
    except Exception as e:
        on_log(f"[warn] failed to get file size via HEAD: {e}")
        return 0


def _download_file(
    url: str,
    dest: Path,
    on_progress,
    on_log,
    should_cancel,
    expected_sha256: str | None = None,
) -> Path:
    """Download url to dest with resume support and optional sha256 verification.

    If the download is cancelled or fails, the partial .part file is removed
    so that the next run cannot mistake an incomplete file for a complete one.
    """
    url = _ensure_sharepoint_download(url)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")

    # Determine expected total size early so we can validate after download.
    expected_total = _http_total_size(url, on_log)
    if expected_total > 0:
        on_log(f"[info] expected file size: {_human_size(expected_total)}")

    headers = {}
    start_offset = 0
    if part.exists():
        start_offset = part.stat().st_size
        if expected_total > 0 and start_offset >= expected_total:
            # Stale .part that is unexpectedly large; restart.
            on_log("[warn] stale partial file is larger than expected, restarting download")
            part.unlink(missing_ok=True)
            start_offset = 0
        else:
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

    response_total = int(r.headers.get("content-length", 0))
    if r.status_code == 206 and start_offset:
        total = response_total + start_offset
    elif r.status_code != 206 and start_offset:
        # Server doesn't support resume; restart
        part.unlink(missing_ok=True)
        start_offset = 0
        total = response_total
    else:
        total = response_total

    if expected_total == 0 and total > 0:
        expected_total = total

    # For large files, try aria2c first for multi-connection acceleration.
    if total > _PARALLEL_DOWNLOAD_MIN_BYTES:
        r.close()
        try:
            aria_dest = _download_with_aria2c(url, dest, total, on_progress, on_log, should_cancel)
            if aria_dest is not None:
                _verify_downloaded_size(aria_dest, expected_total, on_log)
                _verify_sha256(aria_dest, expected_sha256, on_log)
                return aria_dest
        except InterruptedError:
            part.unlink(missing_ok=True)
            raise
        on_log("[info] falling back to single-threaded download")
        # Re-open request for fallback
        r = requests.get(url, headers=headers, stream=True, timeout=30, allow_redirects=True)
        r.raise_for_status()

    mode = "ab" if r.status_code == 206 and start_offset else "wb"
    written = start_offset

    try:
        with open(part, mode) as f:
            for chunk in r.iter_content(chunk_size=_CHUNK_SIZE):
                if should_cancel():
                    raise InterruptedError("Cancelled by user")
                if chunk:
                    f.write(chunk)
                    written += len(chunk)
                    on_progress(written, total)
    except (InterruptedError, Exception):
        # Remove partial file so the next run does not treat it as complete.
        part.unlink(missing_ok=True)
        raise

    part.replace(dest)
    on_log(f"[ok] saved to {dest} ({_human_size(dest.stat().st_size)})")
    _verify_downloaded_size(dest, expected_total, on_log)
    _verify_sha256(dest, expected_sha256, on_log)
    return dest


def _verify_downloaded_size(path: Path, expected_total: int, on_log) -> None:
    """Verify downloaded file size when the expected total is known."""
    if expected_total <= 0:
        return
    actual = path.stat().st_size
    if actual != expected_total:
        raise RuntimeError(
            f"size mismatch for {path.name}: expected {_human_size(expected_total)}, "
            f"got {_human_size(actual)}"
        )
    on_log(f"[ok] size verified for {path.name} ({_human_size(actual)})")


class OTAThread(QThread):
    """Background thread that downloads payload, transfers to Jetson, and runs OTA."""

    log = Signal(str)
    progress = Signal(int)       # 0-100 overall
    download_progress = Signal("long long", "long long")  # current_bytes, total_bytes
    stage = Signal(str)          # "download" | "upload" | "prepare" | "execute"
    done = Signal(bool, str)     # success, message

    def __init__(
        self,
        runner: SSHRunner,
        ota_path: dict,
        payload_option: dict,
        backup_files: list[str],
        force_reupload: bool = False,
        skip_board_check: bool = False,
    ):
        super().__init__()
        self._runner = runner
        self._ota_path = ota_path
        self._payload_option = payload_option
        self._backup_files = backup_files
        self._force_reupload = force_reupload
        self._skip_board_check = skip_board_check
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
        if use_sudo:
            if not self._runner.sudo_password:
                raise RuntimeError(
                    "sudo password is not configured. Please go to the Remote page, "
                    "reconnect SSH, and enter the correct sudo password."
                )
            import shlex
            cmd = (
                "_S() { printf '%s\\n' \"$SEEED_SUDO_PASSWORD\" | command sudo -S -p '' \"$@\" 2>&1; return $?; }; "
                f"_S bash -c {shlex.quote(cmd)}"
            )
        rc, out = self._runner.run(cmd, timeout=timeout)
        return rc, out

    def _verify_sudo_password(self) -> None:
        """Verify that the configured sudo password works before starting OTA."""
        self._emit_log("[step] verifying sudo password...")
        rc, out = self._ssh_run("sudo -S -k true", timeout=15, use_sudo=True)
        if rc != 0:
            # Redact any accidental password echo from the output
            safe_out = out.replace(self._runner.sudo_password, "***") if self._runner.sudo_password else out
            raise RuntimeError(
                f"sudo password verification failed. Please go to the Remote page, "
                f"disconnect and reconnect SSH, and enter the correct sudo password.\n{safe_out}"
            )
        self._emit_log("[ok] sudo password verified")

    def _apply_board_compatibility_workarounds(self, ota_ws: str) -> None:
        """Apply carrier-board compatibility workarounds when skipping board checks.

        This is intended for advanced users who know that the OTA payload is
        compatible with their carrier board even though the board names differ.
        It creates symlinks for missing board-spec directories and patches the
        OTA helper function to skip the strict board-name check.
        """
        import tempfile

        script = r"""#!/usr/bin/env python3
import glob
import os
import re
import shutil
import sys

def log(msg):
    print(f'[board-compat] {msg}')

nv_boot_control = '/etc/nv_boot_control.conf'
if not os.path.exists(nv_boot_control):
    log('nv_boot_control.conf not found')
    sys.exit(1)

with open(nv_boot_control) as f:
    nv_content = f.read()

m = re.search(r'COMPATIBLE_SPEC\s+(\S+)', nv_content)
if not m:
    log('COMPATIBLE_SPEC not found')
    sys.exit(1)

compatible_spec = m.group(1)
parts = compatible_spec.split('-')
board_spec_name = '-'.join(parts[:4])
# Board name is the last non-empty field in COMPATIBLE_SPEC
board_name = [p for p in parts if p][-1]
log(f'COMPATIBLE_SPEC={compatible_spec}')
log(f'BOARD_SPEC_NAME={board_spec_name}')
log(f'BOARD_NAME={board_name}')

work_dir = '/ota_work'
for base in [f'{work_dir}/external_device', f'{work_dir}/internal_device']:
    if not os.path.isdir(base):
        continue
    for images_dir in glob.glob(f'{base}/images-*'):
        if not os.path.isdir(images_dir):
            continue
        expected = os.path.join(images_dir, board_spec_name)
        if os.path.lexists(expected):
            log(f'{expected} already exists')
            continue
        candidates = [
            d for d in os.listdir(images_dir)
            if os.path.isdir(os.path.join(images_dir, d))
        ]
        chosen = None
        for cand in candidates:
            if cand == board_spec_name:
                chosen = cand
                break
            # Accept a candidate that matches the prefix without the trailing
            # empty board revision field (e.g. 3767--0005- matches 3767--0005-1).
            prefix = board_spec_name.rstrip('-')
            if cand.startswith(prefix):
                chosen = cand
                break
        if chosen:
            src = os.path.join(images_dir, chosen)
            os.symlink(src, expected)
            log(f'Created symlink {expected} -> {src}')
        else:
            log(f'No board-spec candidate found in {images_dir}')

# Patch check_target_board to always pass.
func_file = '/home/seeed/ota_ws/Linux_for_Tegra/tools/ota_tools/version_upgrade/nv_ota_common.func'
if os.path.exists(func_file):
    shutil.copy(func_file, func_file + '.bak')
    with open(func_file) as f:
        text = f.read()
    old = '''if [ "${ota_target_board}" != "${sys_target_board}" ]; then
		ota_log "The board name in OTA package(${ota_target_board}) does not match current board(${sys_target_board})"
		return 1
	fi'''
    new = '''# Board check skipped by OTA tool for cross-compatible boards
	# if [ "${ota_target_board}" != "${sys_target_board}" ]; then
	# 	ota_log "The board name in OTA package(${ota_target_board}) does not match current board(${sys_target_board})"
	# 	return 1
	# fi'''
    if old in text:
        text = text.replace(old, new)
        with open(func_file, 'w') as f:
            f.write(text)
        log(f'Patched {func_file}')
    else:
        log('check_target_board already patched or pattern not found')
else:
    log(f'{func_file} not found')

# Keep /ota_work/board_name consistent with the device so that subsequent
# re-runs of nv_ota_start.sh do not need the patch to be re-applied.
board_name_file = f'{work_dir}/board_name'
if os.path.exists(board_name_file):
    with open(board_name_file, 'w') as f:
        f.write(board_name + '\n')
    log(f'Updated {board_name_file} to {board_name}')
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            local_script = Path(f.name)

        remote_script = f"/tmp/ota_board_compat_{self._runner.username}.py"
        self._emit_log(f"[info] uploading board-compatibility script -> {remote_script}")
        client, sftp = self._runner.open_sftp()
        try:
            sftp.put(str(local_script), remote_script)
        finally:
            sftp.close()
            client.close()
        local_script.unlink(missing_ok=True)

        self._emit_log("[step] running board-compatibility script on Jetson...")
        rc, out = self._ssh_run(f"python3 {remote_script}", timeout=60, use_sudo=True)
        self._emit_log(out)
        if rc != 0:
            raise RuntimeError(f"board compatibility workaround failed (rc={rc}): {out[:500]}")
        self._emit_log("[ok] board compatibility workaround applied")

    def _remote_file_size(self, remote_path: str) -> int | None:
        """Return remote file size in bytes, or None if it does not exist / is inaccessible."""
        client, sftp = self._runner.open_sftp()
        try:
            return sftp.stat(remote_path).st_size
        except FileNotFoundError:
            return None
        except Exception as e:
            log.debug("Failed to stat remote file %s: %s", remote_path, e)
            return None
        finally:
            sftp.close()
            client.close()

    def _sftp_put(self, local_path: Path, remote_path: str, stage_name: str = "upload"):
        if self._should_cancel():
            raise InterruptedError("Cancelled")

        local_size = local_path.stat().st_size

        if not self._force_reupload:
            remote_size = self._remote_file_size(remote_path)
            if remote_size is not None and remote_size == local_size:
                self._emit_log(
                    f"[info] {local_path.name} already exists on device "
                    f"({_human_size(remote_size)}), skipping upload"
                )
                return

        self._emit_log(f"[info] uploading {local_path.name} -> {remote_path}")
        total_size = local_size

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
        payload_sha256 = payload.get("sha256", "")
        if local_payload.exists():
            try:
                _verify_cached_file(local_payload, url, payload_sha256, self._emit_log)
                self._emit_log(f"[info] using cached payload: {local_payload}")
            except RuntimeError as e:
                self._emit_log(f"[warn] {e}")
                self._emit_log("[info] removing invalid cached payload and re-downloading...")
                local_payload.unlink(missing_ok=True)
        if not local_payload.exists():
            self._emit_log("[step] downloading OTA payload...")
            local_payload = _download_file(
                url, local_payload,
                self._on_download_progress,
                self._emit_log,
                self._should_cancel,
                expected_sha256=payload_sha256,
            )

        self._emit_progress(25)

        # ── 2. Download OTA tools to PC cache ──
        tools_url = ota_path.get("ota_tools_url", "")
        tools_fn = ota_path.get("ota_tools_filename", "ota_tools.tbz2")
        tools_sha256 = ota_path.get("ota_tools_sha256", "")
        local_tools = _CACHE_DIR / tools_fn
        if local_tools.exists():
            try:
                _verify_cached_file(local_tools, tools_url, tools_sha256, self._emit_log)
                self._emit_log(f"[info] using cached OTA tools: {local_tools}")
            except RuntimeError as e:
                self._emit_log(f"[warn] {e}")
                self._emit_log("[info] removing invalid cached tools and re-downloading...")
                local_tools.unlink(missing_ok=True)
        if not local_tools.exists():
            self._emit_log(f"[step] downloading OTA tools to PC cache ({tools_fn})...")
            local_tools = _download_file(
                tools_url, local_tools,
                self._on_tools_download_progress,
                self._emit_log,
                self._should_cancel,
                expected_sha256=tools_sha256,
            )
        self._emit_progress(35)

        # ── 3. Prepare Jetson workspace ──
        self._emit_log("[step] preparing Jetson workspace...")
        ws = f"/home/{self._runner.username}/ota_ws"
        rc, out = self._ssh_run(f"mkdir -p {ws}", timeout=10)
        if rc != 0:
            raise RuntimeError(f"failed to create workspace: {out}")

        # Verify sudo password before any destructive / long-running steps
        self._verify_sudo_password()

        # Install deps
        self._emit_log("[step] installing dependencies...")
        rc, out = self._ssh_run(
            "apt-get update && apt-get install -y efibootmgr nvme-cli",
            timeout=120,
            use_sudo=True,
        )
        if rc != 0:
            lower = out.lower()
            if "sorry" in lower or "incorrect password" in lower or "no password" in lower:
                raise RuntimeError(
                    "dependency installation failed because the sudo password is incorrect. "
                    "Please go to the Remote page, reconnect SSH, and enter the correct sudo password."
                )
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

        # ── 7. Optional board-compatibility workaround ──
        if self._skip_board_check:
            self._emit_log("[step] applying board compatibility workaround...")
            self._apply_board_compatibility_workarounds(ws)

        # ── 8. Start OTA ──
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
            error_indicators = [
                "error", "fail", "no such file", "permission denied",
                "not found", "cannot", "unable", "invalid",
            ]
            has_error = any(p in lower for p in error_indicators)
            has_ota_sign = "reboot" in lower or "ota" in lower or "upgrade" in lower
            if has_ota_sign and not has_error:
                self._emit_log(f"[info] nv_ota_start.sh returned rc={rc} (likely due to reboot)")
            else:
                raise RuntimeError(f"nv_ota_start.sh failed (rc={rc}): {out[:500]}")

        self._emit_progress(90)
        self._emit_log("[ok] OTA script executed. Device will reboot automatically.")
        self._emit_progress(100)
        self.done.emit(True, "OTA started successfully. The device will reboot.")
