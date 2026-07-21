"""
固件刷写模块
"""
from __future__ import annotations

import json
import os
import subprocess
import hashlib
import time
import platform
import shutil
import stat
import tarfile
from pathlib import Path
from typing import Callable
import requests
from tqdm import tqdm

from seeed_jetson_develop.data_update import get_data_file


def _is_windows_host() -> bool:
    return platform.system() == "Windows"


def _is_linux_host() -> bool:
    return platform.system() == "Linux"


def _hidden_startupinfo():
    if not _is_windows_host():
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


def _hidden_subprocess_kwargs() -> dict:
    if not _is_windows_host():
        return {}
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": _hidden_startupinfo(),
    }


def sudo_authenticate(password: str) -> bool:
    """用给定密码刷新 sudo 凭证。返回 True 表示密码正确且 sudo 已授权。"""
    if not _is_linux_host():
        return True
    try:
        # 用 sudo -S bash -c true 验证密码，比 sudo -S -v 更可靠
        # 某些 Linux 系统上 sudo -S -v 会忽略 -S 或把提示写到 /dev/tty
        proc = subprocess.Popen(
            ["sudo", "-S", "bash", "-c", "true"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        out, _ = proc.communicate(input=password + "\n", timeout=10)
        return proc.returncode == 0
    except Exception:
        return False


def sudo_check_cached() -> bool:
    """检查 sudo 凭证是否仍在缓存期内（无需密码）。"""
    if not _is_linux_host():
        return True
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def find_recovery_device_line(log: Callable[[str], None] | None = None) -> str | None:
    """Return a host-specific recovery-device description line."""
    if _is_windows_host():
        from seeed_jetson_develop.wsl_flash import find_nvidia_apx_device

        device = find_nvidia_apx_device(auto_install=True, log=log)
        if device:
            return device.raw.strip()
        print("[flash] find_recovery_device_line: no NVIDIA APX device found on Windows.")
        print("[flash] Ensure Jetson is in Recovery mode and a DATA USB cable is connected.")
        return None

    nvidia_apx_ids = {"7023", "7223", "7323", "7423", "7523", "7623", "7e19", "7026"}
    result = subprocess.run(
        ["lsusb"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
    )
    for line in result.stdout.splitlines():
        line_lower = line.lower()
        if "0955:" not in line_lower and "nvidia" not in line_lower:
            continue
        parts = line.split("ID ")
        if len(parts) <= 1:
            continue
        pid = parts[1].split()[0].split(":")[-1].lower()
        if pid in nvidia_apx_ids:
            return line.strip()
    return None


# PID -> 模组名称映射（与 recovery_guides.py 中的 usb_ids 保持一致）
_PID_TO_MODULE = {
    "7023": "AGX Orin 64GB",
    "7223": "AGX Orin 32GB",
    "7323": "Orin NX 16GB",
    "7423": "Orin NX 8GB",
    "7523": "Orin Nano 8GB",
    "7623": "Orin Nano 4GB",
    "7e19": "Xavier NX",
    "7026": "AGX Thor T5000",
}


def get_recovery_module_info(log: Callable[[str], None] | None = None) -> dict | None:
    """Return recovery device info including module name from USB PID.

    Returns dict with keys: line, pid, module_name; or None if not found.
    """
    if _is_windows_host():
        from seeed_jetson_develop.wsl_flash import find_nvidia_apx_device, NVIDIA_APX_IDS

        device = find_nvidia_apx_device(auto_install=True, log=log)
        if not device:
            return None
        vid, pid = device.hardware_id.split(":", 1)
        pid = pid.lower()
        if vid == "0955" and pid in NVIDIA_APX_IDS:
            return {
                "line": device.raw.strip(),
                "pid": pid,
                "module_name": _PID_TO_MODULE.get(pid, "Unknown NVIDIA APX"),
            }
        # Fallback: try matching by raw string if hardware_id parse failed
        raw_lower = device.raw.lower()
        for known_pid, name in _PID_TO_MODULE.items():
            if known_pid in raw_lower:
                return {
                    "line": device.raw.strip(),
                    "pid": known_pid,
                    "module_name": name,
                }
        return {
            "line": device.raw.strip(),
            "pid": pid,
            "module_name": "Unknown NVIDIA APX",
        }

    nvidia_apx_ids = {"7023", "7223", "7323", "7423", "7523", "7623", "7e19", "7026"}
    result = subprocess.run(
        ["lsusb"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
    )
    for line in result.stdout.splitlines():
        line_lower = line.lower()
        if "0955:" not in line_lower and "nvidia" not in line_lower:
            continue
        parts = line.split("ID ")
        if len(parts) <= 1:
            continue
        vid_pid = parts[1].split()[0].lower()
        pid = vid_pid.split(":")[-1]
        if pid in nvidia_apx_ids:
            return {
                "line": line.strip(),
                "pid": pid,
                "module_name": _PID_TO_MODULE.get(pid, "Unknown NVIDIA APX"),
            }
    return None


class JetsonFlasher:
    def __init__(self, product, l4t_version, progress_callback=None, should_cancel=None,
                 download_dir: Path | None = None, log_formatter=None, skip_verify: bool = False,
                 probe_wsl_cache: bool = False):
        self.product = product
        self.l4t_version = l4t_version
        self.progress_callback = progress_callback
        self.should_cancel = should_cancel
        self.skip_verify = skip_verify
        self.data_path = get_data_file("l4t_data.json")
        self._fmt = log_formatter or (lambda key, **kw: key)
        self.firmware_info = self._load_firmware_info()
        if download_dir:
            self.download_dir = Path(download_dir)
        elif _is_windows_host():
            windows_dir = Path.home() / "jetson_firmware"
            filename = self.firmware_info["filename"]
            wsl_dir = None
            if probe_wsl_cache:
                try:
                    from seeed_jetson_develop.wsl_flash import get_wsl_download_dir
                    wsl_dir = get_wsl_download_dir()
                except Exception:
                    wsl_dir = None
            if (windows_dir / filename).exists():
                self.download_dir = windows_dir
            elif wsl_dir and (wsl_dir / filename).exists():
                self.download_dir = wsl_dir
            else:
                self.download_dir = windows_dir
        else:
            self.download_dir = Path.home() / "jetson_firmware"
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_firmware_info(self):
        """加载固件信息"""
        with open(self.data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            if item['product'] == self.product and item['l4t'] == self.l4t_version:
                return item
        
        raise ValueError(self._fmt("flash.flasher.firmware_not_found", product=self.product, l4t=self.l4t_version))

    @staticmethod
    def _with_download_flag(url):
        """为 SharePoint 分享链接追加 download=1 参数。"""
        if not url:
            return None
        lower = url.lower()
        if ("sharepoint.com" not in lower and "sharepoint.cn" not in lower) or "download=" in lower:
            return url
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}download=1"

    @staticmethod
    def _looks_like_html(content_type, first_chunk):
        content_type = (content_type or "").lower()
        first = (first_chunk or b"").lstrip().lower()
        if "text/html" in content_type or "application/xhtml" in content_type:
            return True
        return first.startswith(b"<!doctype html") or first.startswith(b"<html")

    def _candidate_urls(self):
        """生成可尝试的下载地址（主链路 + 镜像 + download=1 变体）。"""
        urls = []
        for raw in [self.firmware_info.get("mainlink"), self.firmware_info.get("mirrorlink")]:
            if not raw:
                continue
            for url in [raw, self._with_download_flag(raw)]:
                if url and url not in urls:
                    urls.append(url)
        return urls

    def _emit_progress(self, stage, current, total):
        """向外部回调进度信息。"""
        if not self.progress_callback:
            return
        try:
            self.progress_callback(stage, current, total)
        except Exception:
            # GUI 回调失败不应中断下载流程
            pass

    def _check_cancel(self):
        if self.should_cancel and self.should_cancel():
            raise InterruptedError("cancel requested")

    def _run_cancelable_process(self, args, cwd=None):
        """运行可取消的子进程，实时输出每行日志。"""
        self._check_cancel()
        process = subprocess.Popen(
            args, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', bufsize=1
        )
        try:
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    print(line)
                    self._emit_log(line)
                self._check_cancel()
            process.wait()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, args)
        except InterruptedError:
            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                process.kill()
            raise

    def _emit_log(self, line: str):
        """向外部回调发送日志行。"""
        if self.progress_callback:
            try:
                self.progress_callback("log", line, 0)
            except Exception:
                pass

    @staticmethod
    def _clean_process_output(text: str) -> str:
        return (text or "").replace("\x00", "").strip()

    def _extract_archive_portable(self, filepath: Path, extract_dir: Path):
        """Extract archive. On Windows, delegates to WSL tar to avoid Python tarfile
        recursion limits on large .tar.gz files and to preserve Linux file attributes."""
        if _is_windows_host():
            self._extract_via_wsl(filepath, extract_dir)
        else:
            self._extract_via_tarfile(filepath, extract_dir)

    def _extract_via_wsl(self, filepath: Path, extract_dir: Path):
        """Use WSL tar to extract the archive, reporting progress via file count."""
        from seeed_jetson_develop.wsl_flash import (
            WslFlashManager,
            WslFlashError,
            _windows_path_to_wsl,
            _wsl_exe,
        )

        wsl = _wsl_exe()
        if not wsl or not Path(wsl).exists():
            raise WslFlashError("wsl.exe was not found. Please update Windows and enable WSL.")

        manager = WslFlashManager(
            self.product,
            self.l4t_version,
            self.firmware_info,
            self.download_dir,
            progress_callback=self.progress_callback,
            should_cancel=self.should_cancel,
            verify_archive_sha256=not self.skip_verify,
        )
        manager._prefer_archive_distro()
        manager._ensure_wsl()
        distro = manager.distro

        # Convert paths to WSL-internal paths
        archive_str = str(filepath.resolve())
        if archive_str.lower().startswith(f"\\\\wsl$\\{distro.lower()}\\"):
            rel = archive_str[len(f"\\\\wsl$\\{distro}\\"):]
            archive_wsl = "/" + rel.replace("\\", "/")
        else:
            archive_wsl = _windows_path_to_wsl(filepath)

        extract_str = str(extract_dir.resolve())
        if extract_str.lower().startswith(f"\\\\wsl$\\{distro.lower()}\\"):
            rel = extract_str[len(f"\\\\wsl$\\{distro}\\"):]
            extract_wsl = "/" + rel.replace("\\", "/")
        else:
            extract_wsl = _windows_path_to_wsl(extract_dir)

        import shlex as _shlex
        archive_q = _shlex.quote(archive_wsl)
        extract_q = _shlex.quote(extract_wsl)

        # Emit an indeterminate start so the UI shows something immediately
        self._emit_progress("extract", 0, 0)

        script = (
            "set -o pipefail; "
            f"mkdir -p {extract_q}; "
            f"test -f {archive_q} || "
            f"(echo '[WSL] Archive not found: {archive_wsl}' >&2; exit 41); "
            f"tar xpf {archive_q} -C {extract_q} --checkpoint=500 "
            "--checkpoint-action=echo=#CKPT"
        )

        # Run tar extraction with checkpoints every 500 records for progress ticks.
        # We don't pre-scan (tar tf) because that would decompress the whole archive twice.
        process = subprocess.Popen(
            [wsl, "-d", distro, "-u", "root", "--",
             "bash", "-lc", script],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            **_hidden_subprocess_kwargs(),
        )
        checkpoints = 0
        output_tail: list[str] = []
        try:
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    output_tail.append(line)
                    if len(output_tail) > 40:
                        output_tail.pop(0)
                self._check_cancel()
                normalized = self._clean_process_output(line)
                if normalized == "#CKPT" or normalized.endswith(": #CKPT"):
                    checkpoints += 1
                    # emit (checkpoints, 0) — thread.py treats total==0 as indeterminate
                    # but still increments the counter so the log updates
                    self._emit_progress("extract", checkpoints, 0)
                elif normalized:
                    self._emit_log(normalized)
            process.wait()
        except InterruptedError:
            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                process.kill()
            raise

        if process.returncode != 0:
            detail = self._clean_process_output("\n".join(output_tail))
            lowered = detail.lower()
            if "wsl_e_distro_not_found" in lowered:
                raise WslFlashError(
                    f"WSL distro {distro} is not installed or registered. "
                    "Restart Windows if WSL was just installed, then run Download / Extract again."
                )
            if (
                "unexpected eof" in lowered
                or "unexpected end of file" in lowered
                or "not in gzip format" in lowered
                or "this does not look like a tar archive" in lowered
            ):
                raise WslFlashError(
                    "Firmware archive looks incomplete or corrupted. "
                    "Please use Force re-download, then extract again."
                )
            message = f"WSL tar failed in {distro} (exit {process.returncode})."
            if detail:
                message += f"\nLast WSL output:\n{detail}"
            raise WslFlashError(message)

    def _extract_via_tarfile(self, filepath: Path, extract_dir: Path):
        """Extract using Python tarfile (Linux/native path only)."""
        import sys
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old_limit, 5000))
        try:
            with tarfile.open(filepath, "r:*") as tar:
                members = tar.getmembers()
                total_bytes = sum(m.size for m in members if m.isfile())
                extracted_bytes = 0
                total_members = max(1, len(members))

                for idx, member in enumerate(members, start=1):
                    self._check_cancel()
                    # path traversal guard
                    base = str(extract_dir.resolve())
                    target = str((extract_dir / member.name).resolve())
                    if target != base and not target.startswith(base + os.sep):
                        raise ValueError(self._fmt("flash.flasher.unsafe_path", path=member.name))
                    tar.extract(member, path=extract_dir, set_attrs=True)
                    if member.isfile():
                        extracted_bytes += max(0, member.size)
                    if total_bytes > 0:
                        self._emit_progress("extract", extracted_bytes, total_bytes)
                    else:
                        self._emit_progress("extract", idx, total_members)
        finally:
            sys.setrecursionlimit(old_limit)

    def _download_from_url(self, url, filepath, filename):
        """从指定 URL 下载到目标文件，支持多线程分片并行下载和断点续传。"""
        self._check_cancel()

        # ── 1. HEAD 请求探测服务器能力 ──────────────────────────────────────
        try:
            head = requests.head(url, timeout=(10, 30), allow_redirects=True)
            total_size = int(head.headers.get("content-length", 0))
            accept_ranges = head.headers.get("accept-ranges", "").lower() == "bytes"
        except Exception:
            total_size = 0
            accept_ranges = False

        # 服务器支持 Range 且文件足够大时启用多线程分片下载
        MIN_MULTIPART_SIZE = 32 * 1024 * 1024   # 32 MB 以上才分片
        NUM_PARTS = 8                             # 并发分片数
        use_multipart = accept_ranges and total_size >= MIN_MULTIPART_SIZE

        if use_multipart:
            print(self._fmt("flash.flasher.multipart_enabled", parts=NUM_PARTS, size_mb=total_size // 1024 // 1024))
            self._download_multipart(url, filepath, filename, total_size, NUM_PARTS)
        else:
            print(self._fmt("flash.flasher.singlethread"))
            self._download_single(url, filepath, filename)

    def _download_single(self, url, filepath, filename):
        """单线程下载，支持断点续传。"""
        tmp_path = filepath.with_suffix(filepath.suffix + ".part")
        resume_pos = tmp_path.stat().st_size if tmp_path.exists() else 0

        headers = {}
        if resume_pos > 0:
            headers["Range"] = f"bytes={resume_pos}-"
            print(self._fmt("flash.flasher.resume", pos=resume_pos))

        response = requests.get(url, stream=True, timeout=(15, 600),
                                allow_redirects=True, headers=headers)

        if resume_pos > 0 and response.status_code == 200:
            print(self._fmt("flash.flasher.no_resume"))
            resume_pos = 0
            tmp_path.unlink(missing_ok=True)

        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        if total_size and resume_pos and response.status_code == 206:
            total_size += resume_pos

        content_type = response.headers.get("content-type", "")
        chunks = response.iter_content(chunk_size=1024 * 1024)  # 1 MB chunks

        first_chunk = b""
        for chunk in chunks:
            if chunk:
                first_chunk = chunk
                break

        if not first_chunk:
            raise ValueError(self._fmt("flash.flasher.empty_download"))
        if resume_pos == 0 and self._looks_like_html(content_type, first_chunk):
            raise ValueError(self._fmt("flash.flasher.html_response"))

        written = resume_pos + len(first_chunk)
        open_mode = "ab" if resume_pos > 0 else "wb"

        with open(tmp_path, open_mode) as f:
            self._check_cancel()
            f.write(first_chunk)
            self._emit_progress("download", written, total_size)
            for chunk in chunks:
                if chunk:
                    self._check_cancel()
                    f.write(chunk)
                    written += len(chunk)
                    self._emit_progress("download", written, total_size)

        if written < 1024 * 1024:
            raise ValueError(self._fmt("flash.flasher.file_too_small", size=written))

        tmp_path.replace(filepath)

    def _download_multipart(self, url, filepath, filename, total_size, num_parts):
        """多线程分片并行下载，所有分片完成后合并。"""
        import threading

        part_size = total_size // num_parts
        parts = []
        for i in range(num_parts):
            start = i * part_size
            end = (start + part_size - 1) if i < num_parts - 1 else (total_size - 1)
            part_file = filepath.with_suffix(filepath.suffix + f".part{i}")
            parts.append((i, start, end, part_file))

        # 用一个共享计数器累计全局已下载字节数，初始值为各分片断点续传的已有大小
        total_written_bytes = sum(
            part_file.stat().st_size if part_file.exists() else 0
            for _, _, _, part_file in parts
        )
        counter_lock = threading.Lock()
        part_errors = [None] * num_parts

        def download_part(idx, start, end, part_file):
            nonlocal total_written_bytes
            resume = part_file.stat().st_size if part_file.exists() else 0
            byte_start = start + resume
            if resume > 0 and byte_start > end:
                # 该分片已完整下载
                return

            headers = {"Range": f"bytes={byte_start}-{end}"}
            max_retries = 3
            # 记录本次尝试开始前该分片贡献的字节数（用于重试时修正计数器）
            committed = resume

            for attempt in range(max_retries):
                try:
                    self._check_cancel()
                    resp = requests.get(url, stream=True, timeout=(15, 600),
                                        allow_redirects=True, headers=headers)
                    resp.raise_for_status()

                    with open(part_file, "ab" if committed > 0 else "wb") as f:
                        for chunk in resp.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                self._check_cancel()
                                f.write(chunk)
                                with counter_lock:
                                    total_written_bytes += len(chunk)
                                    snap = total_written_bytes
                                self._emit_progress("download", snap, total_size)
                                committed += len(chunk)
                    return  # 成功
                except InterruptedError:
                    raise
                except Exception as e:
                    if attempt == max_retries - 1:
                        part_errors[idx] = e
                    else:
                        # 重试前：把本次尝试写入但未成功的字节从计数器中减掉
                        actual_on_disk = part_file.stat().st_size if part_file.exists() else 0
                        with counter_lock:
                            total_written_bytes -= (committed - actual_on_disk)
                        committed = actual_on_disk
                        # 重新计算断点续传起点
                        resume = actual_on_disk
                        byte_start = start + resume
                        headers = {"Range": f"bytes={byte_start}-{end}"}
                        time.sleep(2 ** attempt)

        threads = []
        for idx, start, end, part_file in parts:
            t = threading.Thread(target=download_part, args=(idx, start, end, part_file), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self._check_cancel()

        # 检查是否有分片失败
        failed = [(i, e) for i, e in enumerate(part_errors) if e is not None]
        if failed:
            raise Exception(self._fmt("flash.flasher.part_failed", detail=', '.join(f'part{i}: {e}' for i, e in failed)))

        # merge parts
        print(self._fmt("flash.flasher.merge_parts"))
        tmp_path = filepath.with_suffix(filepath.suffix + ".part")
        with open(tmp_path, "wb") as out:
            for idx, start, end, part_file in parts:
                with open(part_file, "rb") as pf:
                    shutil.copyfileobj(pf, out, length=4 * 1024 * 1024)
                part_file.unlink(missing_ok=True)

        actual_size = tmp_path.stat().st_size
        if actual_size < 1024 * 1024:
            raise ValueError(self._fmt("flash.flasher.merge_too_small", size=actual_size))

        tmp_path.replace(filepath)
        print(self._fmt("flash.flasher.download_complete_size", size_mb=actual_size // 1024 // 1024))
    
    def firmware_cached(self) -> bool:
        """检查固件压缩包是否已缓存（文件存在且大小正常）。"""
        filepath = self.download_dir / self.firmware_info['filename']
        return filepath.exists() and filepath.stat().st_size > 1024 * 1024

    def _unc_to_wsl_path(self, unc: Path) -> tuple[str, str] | None:
        r"""Convert \\wsl$\<distro>\... to (distro, /internal/path). Returns None if not a WSL UNC path."""
        # Do not call Path.resolve() for \\wsl$ paths. Windows tries to access
        # the target first, which fails for root-owned Linux directories before
        # we can delegate the operation to WSL as root.
        s = str(unc)
        lower = s.lower()
        prefix = "\\\\wsl$\\"
        if not lower.startswith(prefix):
            s = str(unc.resolve())
            lower = s.lower()
            if not lower.startswith(prefix):
                return None
        rest = s[len(prefix):]
        parts = rest.split("\\", 1)
        if len(parts) < 2:
            return None
        distro, rel = parts
        return distro, "/" + rel.replace("\\", "/")

    def _wsl_read_marker(self, marker_unc: Path) -> str | None:
        """Read a marker file inside WSL via wsl cat. Returns stripped content or None."""
        parsed = self._unc_to_wsl_path(marker_unc)
        if parsed is None:
            try:
                return marker_unc.read_text().strip()
            except Exception:
                return None
        distro, wsl_path = parsed
        from seeed_jetson_develop.wsl_flash import _wsl_exe
        import shlex
        try:
            result = subprocess.run(
                [_wsl_exe(), "-d", distro, "-u", "root", "--",
                 "bash", "-c", f"cat {shlex.quote(wsl_path)} 2>/dev/null"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                **_hidden_subprocess_kwargs(),
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def _wsl_write_marker(self, marker_unc: Path, content: str):
        """Write a marker file inside WSL via wsl bash. Silently ignores errors."""
        parsed = self._unc_to_wsl_path(marker_unc)
        if parsed is None:
            try:
                marker_unc.write_text(content)
            except Exception:
                pass
            return
        distro, wsl_path = parsed
        from seeed_jetson_develop.wsl_flash import _wsl_exe
        import shlex
        try:
            subprocess.run(
                [_wsl_exe(), "-d", distro, "-u", "root", "--",
                 "bash", "-c", f"echo -n {shlex.quote(content)} > {shlex.quote(wsl_path)}"],
                capture_output=True, timeout=10, **_hidden_subprocess_kwargs(),
            )
        except Exception:
            pass

    def _wsl_rmtree(self, path: Path):
        """Delete a directory tree inside WSL via wsl rm -rf (handles root-owned files)."""
        parsed = self._unc_to_wsl_path(path)
        if parsed is None:
            self._rmtree_privileged(path)
            return
        distro, wsl_path = parsed
        from seeed_jetson_develop.wsl_flash import _wsl_exe
        import shlex
        result = subprocess.run(
            [_wsl_exe(), "-d", distro, "-u", "root", "--",
             "bash", "-c", f"rm -rf {shlex.quote(wsl_path)}"],
            capture_output=True, timeout=120, **_hidden_subprocess_kwargs(),
        )
        if result.returncode != 0:
            raise PermissionError(f"wsl rm -rf failed (exit {result.returncode})")

    def firmware_extracted(self) -> bool:
        """检查当前产品+版本的固件是否已解压且内容匹配。
        通过标记文件确认解压内容属于当前 product+l4t，避免共用 foldername 时用错固件。
        """
        extract_dir = self.download_dir / "extracted"
        if not extract_dir.exists():
            return False
        actual = self._detect_extracted_dir(extract_dir)
        if actual is None:
            return False
        marker = actual / ".seeed_flash_marker"
        content = self._wsl_read_marker(marker)
        if content is not None:
            return content == f"{self.product}|{self.l4t_version}"
        # 无 marker 文件视为未完成解压
        return False

    def clear_cache(self, clear_archive=True, clear_extracted=True):
        """清除本地缓存。返回已删除路径列表。
        解压目录内含 rootfs（root 权限文件），优先用 sudo rm -rf 删除。
        """
        import shutil
        removed = []
        if clear_archive:
            filepath = self.download_dir / self.firmware_info['filename']
            if filepath.exists():
                filepath.unlink()
                removed.append(str(filepath))
            part = filepath.with_suffix(filepath.suffix + ".part")
            if part.exists():
                part.unlink()
                removed.append(str(part))
        if clear_extracted:
            extract_dir = self.download_dir / "extracted"
            foldername = self.firmware_info.get('foldername', '')
            if foldername and extract_dir.exists():
                # 只删精确匹配当前产品 foldername 的目录，绝不误删其他产品的目录
                actual = extract_dir / foldername
                if actual.exists():
                    self._wsl_rmtree(actual)
                    removed.append(str(actual))
        return removed

    @staticmethod
    def _rmtree_privileged(path: Path):
        """删除目录，自动处理 rootfs 等需要 root 权限的子目录。
        先尝试普通删除，失败则用 sudo rm -rf。
        """
        def _retry_remove(func, target, _exc):
            try:
                os.chmod(target, stat.S_IWRITE)
            except Exception:
                pass
            func(target)

        try:
            shutil.rmtree(path, onerror=_retry_remove)
        except PermissionError:
            if not _is_linux_host():
                raise
            print(self._fmt("flash.flasher.rmtree_sudo", path=path))
            result = subprocess.run(
                ["sudo", "rm", "-rf", str(path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                raise PermissionError(
                    self._fmt("flash.flasher.rmtree_sudo_fail", code=result.returncode, error=result.stderr.strip())
                )

    def download_firmware(self, force_redownload: bool = False):
        """下载固件。force_redownload=True 时忽略缓存强制重新下载。"""
        filename = self.firmware_info['filename']
        filepath = self.download_dir / filename

        if not force_redownload and filepath.exists():
            size = filepath.stat().st_size
            if size > 1024 * 1024:
                print(self._fmt("flash.flasher.firmware_exists", path=filepath))
                return True
            print(self._fmt("flash.flasher.file_too_small_redownload", size=size, path=filepath))
            filepath.unlink()

        if force_redownload and filepath.exists():
            print(self._fmt("flash.flasher.force_redownload", path=filepath))
            filepath.unlink()
            part_path = filepath.with_suffix(filepath.suffix + ".part")
            if part_path.exists():
                part_path.unlink()
            # 清理多线程分片文件
            for part_file in self.download_dir.glob(filepath.name + ".part[0-9]*"):
                part_file.unlink(missing_ok=True)
        
        print(self._fmt("flash.flasher.downloading", filename=filename))
        urls = self._candidate_urls()

        last_error = None
        for idx, url in enumerate(urls, start=1):
            print(self._fmt("flash.flasher.download_url", idx=idx, total=len(urls), url=url))
            self._emit_progress("download", 0, 0)
            try:
                self._download_from_url(url, filepath, filename)
                return True
            except InterruptedError:
                raise
            except Exception as e:
                last_error = e
                print(self._fmt("flash.flasher.url_failed", error=e))

        print(self._fmt("flash.flasher.download_failed", error=last_error))
        return False
    
    def verify_firmware(self):
        """校验固件 SHA256"""
        self._check_cancel()
        filename = self.firmware_info['filename']
        filepath = self.download_dir / filename
        expected_sha256 = self.firmware_info['sha256'].lower()
        total_size = filepath.stat().st_size if filepath.exists() else 0
        
        print(self._fmt("flash.flasher.verifying", filename=filename))

        sha256_hash = hashlib.sha256()
        processed = 0
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                self._check_cancel()
                sha256_hash.update(byte_block)
                processed += len(byte_block)
                if total_size > 0:
                    self._emit_progress("verify", processed, total_size)

        actual_sha256 = sha256_hash.hexdigest().lower()

        if actual_sha256 == expected_sha256:
            print(self._fmt("flash.flasher.verify_ok"))
            return True
        else:
            print(self._fmt("flash.flasher.verify_fail"))
            print(self._fmt("flash.flasher.verify_expected", hash=expected_sha256))
            print(self._fmt("flash.flasher.verify_actual", hash=actual_sha256))
            return False
    
    def _detect_extracted_dir(self, extract_dir: Path) -> Path | None:
        """探测解压后的实际顶层目录，优先精确匹配 foldername，否则取唯一子目录。"""
        foldername = self.firmware_info.get('foldername', '')
        # 优先：精确匹配（foldername 就是解压后的目录名）
        if foldername:
            candidate = extract_dir / foldername
            if candidate.is_dir():
                return candidate
        # 兜底：唯一子目录（用于 foldername 为空或目录名有细微差异的情况）
        try:
            subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
        except Exception:
            return None
        if len(subdirs) == 1:
            return subdirs[0]
        return None

    def extract_firmware(self):
        self._check_cancel()
        filename = self.firmware_info['filename']
        filepath = self.download_dir / filename
        extract_dir = self.download_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)

        # 已解压且内容匹配当前 product+l4t，直接跳过
        if self.firmware_extracted():
            existing = self._detect_extracted_dir(extract_dir)
            self._extracted_dir = existing
            print(self._fmt("flash.flasher.already_extracted", path=existing))
            return True

        foldername = self.firmware_info.get('foldername', '')
        if foldername:
            target = extract_dir / foldername
            if target.exists():
                print(self._fmt("flash.flasher.old_dir_cleanup", path=target))
                self._rmtree_privileged(target)

        print(self._fmt("flash.flasher.extracting", filename=filename))

        try:
            if not (filename.endswith('.tar.gz') or filename.endswith('.tar')):
                print(self._fmt("flash.flasher.unsupported_format", filename=filename))
                return False

            self._extract_archive_portable(filepath, extract_dir)

            actual_dir = self._detect_extracted_dir(extract_dir)
            if actual_dir:
                self._extracted_dir = actual_dir
                marker = actual_dir / ".seeed_flash_marker"
                self._wsl_write_marker(marker, f"{self.product}|{self.l4t_version}")
                print(self._fmt("flash.flasher.extract_done", path=actual_dir))
            else:
                print(self._fmt("flash.flasher.extract_done_unknown_dir", path=extract_dir))
                self._extracted_dir = None
            return True
        
        except InterruptedError:
            raise
        except Exception as e:
            print(self._fmt("flash.flasher.extract_failed", error=e))
            return False
    
    def flash_firmware(self):
        """刷写固件（需已解压，设备已进入 Recovery 模式）。"""
        self._check_cancel()
        if _is_windows_host():
            print("[Windows] Detected Windows host — using WSL2 flash path")
            print("[Windows] This path uses WSL2 + usbipd-win to passthrough USB to Linux.")
            print("[Windows] A PowerShell UAC prompt may appear for: WSL install, usbipd-win install, USB bind.")
            try:
                from seeed_jetson_develop.wsl_flash import WslFlashManager

                manager = WslFlashManager(
                    self.product,
                    self.l4t_version,
                    self.firmware_info,
                    self.download_dir,
                    progress_callback=self.progress_callback,
                    should_cancel=self.should_cancel,
                    verify_archive_sha256=not self.skip_verify,
                )
                return manager.flash()
            except InterruptedError:
                raise
            except Exception as exc:
                msg = f"WSL2 flash failed: {exc}"
                print(msg)
                self._emit_log(msg)
                return False

        print("[Linux] Detected Linux host — using native flash path")
        print("[Linux] Running NVIDIA l4t_initrd_flash.sh directly with sudo.")
        extract_dir = self.download_dir / "extracted"

        actual_dir = getattr(self, '_extracted_dir', None)
        if actual_dir is None:
            actual_dir = self._detect_extracted_dir(extract_dir)
        if actual_dir is None:
            print(self._fmt("flash.flasher.no_extracted_dir", path=extract_dir))
            return False

        flash_script = actual_dir / "tools" / "kernel_flash" / "l4t_initrd_flash.sh"
        if not flash_script.exists():
            print(self._fmt("flash.flasher.no_flash_script", path=flash_script))
            return False

        print(f"[Linux] Working directory: {actual_dir}")
        print(f"[Linux] Flash script: {flash_script}")
        print("[Linux] === Starting native Linux flash (sudo required) ===")
        print("[Linux] This step requires sudo password and takes 10-30 minutes.")
        print("[Linux] Ensure the Jetson is in Recovery mode before proceeding.")

        try:
            args = ["sudo", "./tools/kernel_flash/l4t_initrd_flash.sh",
                    "--flash-only", "--massflash", "1",
                    "--network", "usb0", "--showlogs"]
            print(f"[Linux] Running: sudo ./tools/kernel_flash/l4t_initrd_flash.sh --flash-only --massflash 1 --network usb0 --showlogs")
            self._run_cancelable_process(args, cwd=str(actual_dir))
            print("[Linux] === Flash completed successfully. ===")
            return True
        except InterruptedError:
            raise
        except subprocess.CalledProcessError as e:
            print(f"[Linux] Flash failed with exit code: {e.returncode}")
            return False
