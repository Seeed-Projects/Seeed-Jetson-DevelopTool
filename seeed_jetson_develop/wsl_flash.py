"""Windows WSL2 flashing support for Seeed Jetson massflash packages."""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests


DEFAULT_WSL_DISTRO = os.environ.get("SEEED_WSL_DISTRO", "Ubuntu-20.04")
KERNEL_URL = os.environ.get(
    "SEEED_WSL_KERNEL_URL",
    "https://seeedstudio88-my.sharepoint.com/:u:/g/personal/"
    "youjiang_yu_seeedstudio88_onmicrosoft_com/"
    "IQBAoWWTQQsBSYpacMvUN9LYAUi6X_jPQmzYrGWtZtb5ilc?e=ZjNaJr",
)
KERNEL_SHA256 = os.environ.get(
    "SEEED_WSL_KERNEL_SHA256",
    "f249022feab9372d448d236a4401e087d0f150dd6b3367b571f0b9a703bd2d38",
)
FLASH_PACKAGES = (
    "qemu-user-static",
    "sshpass",
    "abootimg",
    "nfs-kernel-server",
    "libxml2-utils",
    "binutils",
    "usbutils",
)
NVIDIA_APX_IDS = {"7023", "7223", "7323", "7423", "7523", "7623"}
NVIDIA_INITRD_USB_IDS = {"7035"}
WINDOWS_SHELL_HW_DETECTION_SERVICE = "ShellHWDetection"


class WslFlashError(RuntimeError):
    """Raised when the Windows/WSL flashing helper cannot continue."""


@dataclass
class UsbDevice:
    busid: str
    hardware_id: str
    description: str
    state: str
    raw: str


def _default_wsl_distro_for_l4t(l4t_version: str) -> str:
    if os.environ.get("SEEED_WSL_DISTRO"):
        return DEFAULT_WSL_DISTRO
    try:
        major = int(str(l4t_version).split(".", 1)[0])
    except Exception:
        return DEFAULT_WSL_DISTRO
    if major <= 32:
        return "Ubuntu-18.04"
    if major <= 36:
        return "Ubuntu-20.04"
    return DEFAULT_WSL_DISTRO


def _preferred_wsl_distros_for_l4t(l4t_version: str) -> list[str]:
    if os.environ.get("SEEED_WSL_DISTRO"):
        return [DEFAULT_WSL_DISTRO]
    try:
        major = int(str(l4t_version).split(".", 1)[0])
    except Exception:
        return [DEFAULT_WSL_DISTRO]
    if major <= 32:
        return ["Ubuntu-18.04"]
    if major <= 36:
        return ["Ubuntu-22.04", "Ubuntu-20.04"]
    return [DEFAULT_WSL_DISTRO]


def _decode_output(data: bytes) -> str:
    if not data:
        return ""
    if b"\x00" in data:
        try:
            return data.decode("utf-8", errors="replace").replace("\x00", "")
        except Exception:
            pass
        try:
            return data.decode("utf-16le", errors="replace").replace("\x00", "")
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


def _hidden_startupinfo():
    if os.name != "nt":
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


def _hidden_subprocess_kwargs() -> dict:
    if os.name != "nt":
        return {}
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": _hidden_startupinfo(),
    }


def _run_capture(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    proc.stdout = _decode_output(proc.stdout).encode("utf-8", errors="replace")
    return proc


def _completed_text(proc: subprocess.CompletedProcess) -> str:
    out = proc.stdout or b""
    if isinstance(out, bytes):
        return out.decode("utf-8", errors="replace")
    return str(out)


def _usbipd_state_attached(state: str) -> bool:
    return state.strip().lower().startswith("attached")


def _usbipd_state_shared(state: str) -> bool:
    lower = state.strip().lower()
    return _usbipd_state_attached(state) or lower == "shared" or lower.startswith("shared ")


def _usbipd_state_needs_bind(state: str) -> bool:
    return "not shared" in state.strip().lower()


def _looks_like_nfs_mount_failure(text: str) -> bool:
    lower = (text or "").lower()
    return (
        "either the device cannot mount the nfs server on the host" in lower
        or "error: nfs mount failure during flashing" in lower
        or ("flash failure" in lower and "nfs server" in lower)
        or "check your network setting (vpn, firewall" in lower
    )


def _ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _run_elevated(program: str, args: list[str], timeout: int | None = None) -> int:
    arg_string = subprocess.list2cmdline(args)
    script = (
        "$p = Start-Process -FilePath "
        + _ps_single_quote(program)
        + " -ArgumentList "
        + _ps_single_quote(arg_string)
        + " -Verb RunAs -Wait -PassThru; exit $p.ExitCode"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        timeout=timeout,
    )
    return result.returncode


def _with_download_flag(url: str) -> str:
    lower = url.lower()
    if ("sharepoint.com" not in lower and "sharepoint.cn" not in lower) or "download=" in lower:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}download=1"


def _usbipd_exe() -> str | None:
    found = shutil.which("usbipd")
    if found:
        return found
    default = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "usbipd-win" / "usbipd.exe"
    if default.exists():
        return str(default)
    return None


def _log_usbipd(message: str, log: Callable[[str], None] | None = None):
    if log:
        log(message)


def ensure_usbipd_ready(log: Callable[[str], None] | None = None) -> str:
    """Ensure usbipd-win is installed and return the executable path."""

    usbipd = _usbipd_exe()
    if not usbipd:
        _log_usbipd("[usbipd] usbipd.exe not found on PATH or Program Files.", log)
        _log_usbipd("[usbipd] Attempting to install via winget...", log)
        _log_usbipd("[usbipd] A Windows UAC prompt will appear; click 'Yes' to continue.", log)
        winget = shutil.which("winget") or "winget"
        code = _run_elevated(
            winget,
            [
                "install",
                "--interactive",
                "--exact",
                "--id",
                "dorssel.usbipd-win",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            timeout=None,
        )
        _log_usbipd(f"[usbipd] winget install returned code: {code}", log)
        if code != 0:
            raise WslFlashError(f"Failed to install usbipd-win with winget (exit {code}).")
        usbipd = _usbipd_exe()
        if not usbipd:
            raise WslFlashError("usbipd-win was installed, but usbipd.exe is not visible yet. Restart the app.")
        _log_usbipd("[usbipd] usbipd-win installed successfully.", log)
    else:
        _log_usbipd(f"[usbipd] Found: {usbipd}", log)

    version = _run_capture([usbipd, "--version"], timeout=20)
    text = _completed_text(version).strip()
    _log_usbipd(f"[usbipd] Version: {text or '(unknown)'}", log)

    match = re.search(r"(\d+)\.(\d+)", text)
    if match and int(match.group(1)) < 4:
        _log_usbipd(f"[usbipd] Current version {match.group(1)}.{match.group(2)} < 4. Upgrading...", log)
        _run_elevated("winget", ["upgrade", "--exact", "--id", "dorssel.usbipd-win"], timeout=None)
        _log_usbipd("[usbipd] Upgrade complete.", log)
    return usbipd


def _wsl_exe() -> str | None:
    return shutil.which("wsl") or str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wsl.exe")


def _usbpcap_status() -> str | None:
    """Return a short warning if the USBPcap filter driver is present/active."""
    running = False
    upper_filter = False
    try:
        result = _run_capture(["sc.exe", "query", "USBPcap"], timeout=10)
        text = _completed_text(result)
        running = "RUNNING" in text.upper()
    except Exception:
        pass
    try:
        result = _run_capture(
            [
                "reg",
                "query",
                r"HKLM\SYSTEM\CurrentControlSet\Control\Class\{36fc9e60-c465-11cf-8056-444553540000}",
                "/v",
                "UpperFilters",
            ],
            timeout=10,
        )
        upper_filter = "USBPcap" in _completed_text(result)
    except Exception:
        pass
    if running and upper_filter:
        return "USBPcap filter driver is running and installed as a USB UpperFilters driver."
    if running:
        return "USBPcap filter driver is running."
    if upper_filter:
        return "USBPcap is installed as a USB UpperFilters driver."
    return None


def _sc_exe() -> str:
    found = shutil.which("sc.exe")
    if found:
        return found
    return str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "sc.exe")


def _parse_sc_state(text: str) -> str | None:
    match = re.search(r"\bSTATE\s*:\s*\d+\s+(\S+)", text or "", re.IGNORECASE)
    if not match:
        return None
    return match.group(1).upper()


def _windows_service_state(service_name: str) -> str | None:
    if os.name != "nt":
        return None
    try:
        result = _run_capture([_sc_exe(), "query", service_name], timeout=10)
    except Exception:
        return None
    return _parse_sc_state(_completed_text(result))


def _run_elevated_service_control(action: str, service_name: str) -> int:
    return _run_elevated(_sc_exe(), [action, service_name], timeout=120)


def _parse_wsl_unc_path(path: Path) -> tuple[str, str] | None:
    r"""Convert \\wsl$\<distro>\path to (distro, /internal/path)."""
    raw = str(path)
    prefix = "\\\\wsl$\\"
    if not raw.lower().startswith(prefix):
        return None
    rest = raw[len(prefix):]
    parts = rest.split("\\", 1)
    if len(parts) != 2:
        return None
    distro, rel = parts
    return distro, "/" + rel.replace("\\", "/")


def _windows_path_to_wsl(path: Path) -> str:
    parsed = _parse_wsl_unc_path(path)
    if parsed is not None:
        return parsed[1]
    path = path.resolve()
    drive = path.drive.rstrip(":").lower()
    if not drive:
        raise WslFlashError(f"Cannot map Windows path to WSL: {path}")
    rest = [part for part in path.parts[1:]]
    return "/mnt/" + drive + "/" + "/".join(part.replace("\\", "/") for part in rest)


def _wsl_internal_to_windows(wsl_path: str, distro: str) -> Path:
    r"""Convert a WSL-internal path like /root/foo to \\wsl$\<distro>\root\foo."""
    posix = wsl_path.lstrip("/")
    return Path(f"\\\\wsl$\\{distro}") / posix.replace("/", "\\")


def get_wsl_download_dir(distro: str | None = None) -> Path | None:
    """Return the WSL-internal firmware directory as a Windows UNC path.

    Uses the default WSL user's home directory so Windows has read/write access.
    Returns None if WSL is not available or the path cannot be determined.
    """
    try:
        resolved_distro = distro or _default_wsl_distro_for_l4t("")
        wsl = _wsl_exe()
        if not wsl:
            return None
        # Get the default user's home directory inside WSL
        result = subprocess.run(
            [wsl, "-d", resolved_distro, "--", "bash", "-c", "echo $HOME"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode != 0:
            return None
        wsl_home = result.stdout.strip()
        if not wsl_home or wsl_home.startswith("/mnt/"):
            # HOME points to a Windows path — fall back to /home/<user>
            user = subprocess.run(
                [wsl, "-d", resolved_distro, "--", "whoami"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            ).stdout.strip()
            wsl_home = f"/home/{user}"
        wsl_dir = wsl_home + "/seeed-jetson-firmware"
        # Create the directory inside WSL
        subprocess.run(
            [wsl, "-d", resolved_distro, "--", "mkdir", "-p", wsl_dir],
            capture_output=True, timeout=10
        )
        unc = _wsl_internal_to_windows(wsl_dir, resolved_distro)
        if unc.exists():
            return unc
        return None
    except Exception:
        return None


def list_usb_devices(
    auto_install: bool = False,
    log: Callable[[str], None] | None = None,
) -> list[UsbDevice]:
    usbipd = ensure_usbipd_ready(log=log) if auto_install else _usbipd_exe()
    if not usbipd:
        raise WslFlashError("usbipd-win is not installed or not on PATH")
    result = _run_capture([usbipd, "list"], timeout=20)
    text = _completed_text(result)
    devices: list[UsbDevice] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith(("connected", "persisted", "busid", "guid")):
            continue
        match = re.match(r"^(\S+)\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\s+(.+?)\s{2,}(.+)$", line)
        if not match:
            continue
        devices.append(
            UsbDevice(
                busid=match.group(1),
                hardware_id=match.group(2).lower(),
                description=match.group(3).strip(),
                state=match.group(4).strip(),
                raw=raw,
            )
        )
    return devices


def find_nvidia_apx_device(
    auto_install: bool = False,
    log: Callable[[str], None] | None = None,
) -> UsbDevice | None:
    for device in list_usb_devices(auto_install=auto_install, log=log):
        vid, pid = device.hardware_id.split(":", 1)
        desc = device.description.lower()
        if vid == "0955" and (pid in NVIDIA_APX_IDS or "apx" in desc):
            return device
    return None


def find_nvidia_flash_usb_device(
    auto_install: bool = False,
    log: Callable[[str], None] | None = None,
) -> UsbDevice | None:
    for device in list_usb_devices(auto_install=auto_install, log=log):
        vid, pid = device.hardware_id.split(":", 1)
        desc = device.description.lower()
        if vid != "0955":
            continue
        if (
            pid in NVIDIA_APX_IDS
            or pid in NVIDIA_INITRD_USB_IDS
            or "apx" in desc
            or "nvidia" in desc
        ):
            return device
    return None


def _kernel_config_enabled(text: str, name: str) -> bool:
    return re.search(rf"^{re.escape(name)}=(?:y|m)$", text, re.MULTILINE) is not None


class WslFlashManager:
    """Prepare WSL, keep APX attached, and run the Linux flash script."""

    def __init__(
        self,
        product: str,
        l4t_version: str,
        firmware_info: dict,
        download_dir: Path,
        progress_callback: Callable[[str, object, object], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
        distro: str | None = None,
        verify_archive_sha256: bool = False,
    ):
        self.product = product
        self.l4t_version = l4t_version
        self.firmware_info = firmware_info
        self.download_dir = Path(download_dir)
        self.progress_callback = progress_callback
        self.should_cancel = should_cancel
        self.verify_archive_sha256 = verify_archive_sha256
        self.distro = distro or _default_wsl_distro_for_l4t(l4t_version)
        self._preferred_distros = [self.distro] if distro else _preferred_wsl_distros_for_l4t(l4t_version)
        self._attach_stop = threading.Event()
        self._attach_process: subprocess.Popen | None = None
        self._attach_thread: threading.Thread | None = None
        self._attach_pulse_thread: threading.Thread | None = None
        self._dynamic_attach_thread: threading.Thread | None = None
        self._attach_lock = threading.Lock()
        self._attached_busid: str | None = None
        self._seen_busids: set[str] = set()
        self._bound_busids: set[str] = set()
        self._attach_confirmed = threading.Event()
        self._attach_state_stop = threading.Event()
        self._attach_state_thread: threading.Thread | None = None
        self._last_host_attach_state: str | None = None
        self._last_wsl_ready_error: str | None = None
        self._restore_shell_hw_detection = False

    def _prefer_archive_distro(self):
        archive = self.download_dir / self.firmware_info["filename"]
        parsed = _parse_wsl_unc_path(archive)
        if parsed is None:
            return
        source_distro, _ = parsed
        candidates = [d.lower() for d in self._preferred_distros]
        if source_distro.lower() in candidates and source_distro != self.distro:
            self._log(
                f"Firmware archive already lives in WSL distro {source_distro}; "
                f"using it instead of {self.distro}."
            )
            self.distro = source_distro
        self._preferred_distros = [self.distro] + [
            d for d in self._preferred_distros if d.lower() != self.distro.lower()
        ]

    def flash(self) -> bool:
        self._log("=" * 60)
        self._log("Windows WSL2 Flash Workflow Starting")
        self._log("=" * 60)
        self._log("[STEP 1/7] WSL distro setup")
        self._log("[STEP 2/7] usbipd-win setup")
        self._log("[STEP 3/7] WSL kernel USB/IP check")
        self._log("[STEP 4/7] Find & bind recovery device")
        self._log("[STEP 5/7] USB passthrough stabilization")
        self._log("[STEP 6/7] Execute flash script in WSL")
        self._log("[STEP 7/7] Cleanup")
        self._log("=" * 60)
        try:
            self._check_cancel()
            self._prefer_archive_distro()
            self._ensure_wsl()
            self._ensure_usbipd()
            self._ensure_kernel_if_needed()
            # Stage archive before USB attach to avoid WSL network reset during copy
            self._pre_stage_archive()
            device = self._find_or_attach_recovery()
            self._remember_attached_busid(device.busid)
            self._suspend_shell_hardware_detection()
            self._start_auto_attach(device.busid)
            self._start_attach_state_monitor(device.busid)
            self._wait_for_usbipd_attach_stable(device.busid, timeout=120)
            self._run_flash_in_wsl()
            self._log("=" * 60)
            self._log("[STEP 7/7] Cleanup and finalization...")
            self._log("WSL flash workflow completed successfully. ✓")
            self._log("=" * 60)
            return True
        finally:
            self._stop_attach_state_monitor()
            self._stop_auto_attach()
            self._restore_shell_hardware_detection_if_needed()

    def _log(self, line: str):
        try:
            print(line)
        except UnicodeEncodeError:
            encoding = sys.stdout.encoding or "utf-8"
            safe = line.encode(encoding, errors="replace").decode(encoding, errors="replace")
            print(safe)
        if self.progress_callback:
            try:
                self.progress_callback("log", line, 0)
            except Exception:
                pass

    def _check_cancel(self):
        if self.should_cancel and self.should_cancel():
            raise InterruptedError("cancel requested")

    def _ensure_wsl(self):
        wsl = _wsl_exe()
        if not wsl or not Path(wsl).exists():
            raise WslFlashError("wsl.exe was not found. Please update Windows and enable WSL.")

        self._log("[STEP 1/7] Checking WSL installation...")
        # Query WSL version info for diagnostics
        result_ver = _run_capture([wsl, "--status"], timeout=15)
        ver_text = _completed_text(result_ver).strip()
        if ver_text:
            for line in ver_text.splitlines():
                if line.strip():
                    self._log(f"[WSL status] {line.strip()}")
        else:
            self._log("[WSL status] Could not retrieve WSL version info.")

        self._log(f"[WSL] Setting default WSL version to 2...")
        subprocess.run(
            [wsl, "--set-default-version", "2"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **_hidden_subprocess_kwargs(),
        )
        distros = self._wsl_distros()
        self._log(f"[WSL] Installed distros: {sorted(distros) if distros else '(none)'}")

        candidate_order = [self.distro] + [
            d for d in self._preferred_distros if d.lower() != self.distro.lower()
        ]
        self._log(f"[WSL] Preferred distro order: {candidate_order}")

        for candidate in candidate_order:
            if candidate in distros:
                self.distro = candidate
                self._log(f"[WSL] Selected existing distro: {self.distro}")
                break
        if self.distro not in distros:
            self._log(f"[WSL] Installing WSL distro '{self.distro}'. Approve the Windows UAC prompt if it appears.")
            self._log("[WSL] If the installer hangs waiting for reboot, restart Windows and try again.")
            code = _run_elevated(wsl, ["--install", "-d", self.distro], timeout=None)
            self._log(f"[WSL] WSL installer returned code: {code}")
            distros = self._wait_for_distro_registration(timeout=120)
            self._log(f"[WSL] Distros after install attempt: {sorted(distros) if distros else '(none)'}")
            if self.distro not in distros:
                raise WslFlashError(
                    f"Failed to install {self.distro} (exit {code}). "
                    "If Windows asks for a restart, restart and run the tool again."
                )
            if code != 0:
                self._log(
                    f"WSL installer exited with code {code}, but {self.distro} "
                    "was registered successfully; continuing."
                )

        self._log(f"[WSL] Waiting for {self.distro} to become ready (timeout=180s)...")
        ready = self._wait_for_wsl_ready(timeout=180)
        if not ready:
            detail = self._last_wsl_ready_error or f"{self.distro} is installed but not responding."
            raise WslFlashError(
                f"{detail} "
                f"If Ubuntu first-time setup has not completed, open {self.distro} once "
                "from the Start menu and finish setup. "
                f"If the distro is stuck, run `wsl --terminate {self.distro}` or "
                "`wsl --shutdown`, then retry."
            )
        self._log(f"[STEP 1/7] WSL distro ready: {self.distro} ✓")

    def _wsl_distros(self) -> set[str]:
        result = _run_capture([_wsl_exe(), "-l", "-q"], timeout=30)
        names = {
            line.replace("\x00", "").strip().lstrip("*").strip()
            for line in _completed_text(result).splitlines()
        }
        return {name for name in names if name}

    def _wait_for_distro_registration(self, timeout: int) -> set[str]:
        deadline = time.time() + timeout
        latest = set()
        while time.time() < deadline:
            latest = self._wsl_distros()
            if self.distro in latest:
                return latest
            time.sleep(2)
        return latest

    def _restart_unresponsive_wsl_distro(self) -> bool:
        wsl = _wsl_exe()
        if not wsl:
            return False
        self._log(f"[WSL] {self.distro} is not responding. Restarting this distro and retrying...")
        try:
            result = subprocess.run(
                [wsl, "--terminate", self.distro],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=20,
                **_hidden_subprocess_kwargs(),
            )
        except subprocess.TimeoutExpired:
            self._log(f"[WSL] Timed out while terminating {self.distro}.")
            return False
        except Exception as e:
            self._log(f"[WSL] Failed to terminate {self.distro}: {e}")
            return False

        output = _decode_output(result.stdout or b"").strip()
        if result.returncode != 0:
            if output:
                self._log(f"[WSL] terminate output: {output.splitlines()[-1]}")
            return False
        time.sleep(3)
        return True

    def _wait_for_wsl_ready(self, timeout: int) -> bool:
        deadline = time.time() + timeout
        attempt = 0
        restarted = False
        self._last_wsl_ready_error = None
        while time.time() < deadline:
            attempt += 1
            remaining = max(15, int(deadline - time.time()))
            probe_timeout = min(60, remaining)
            try:
                ready = self._run_wsl(["sh", "-c", "echo SEEED_WSL_READY"], timeout=probe_timeout)
            except subprocess.TimeoutExpired:
                self._last_wsl_ready_error = (
                    f"{self.distro} did not respond to WSL commands within {probe_timeout}s."
                )
                self._log(
                    f"[WSL] Ready probe timed out after {probe_timeout}s "
                    f"(attempt {attempt})."
                )
                if not restarted and self._restart_unresponsive_wsl_distro():
                    restarted = True
                    continue
                time.sleep(3)
                continue
            except Exception as e:
                self._last_wsl_ready_error = f"WSL ready probe failed: {e}"
                self._log(f"[WSL] Ready probe failed: {e}")
                time.sleep(3)
                continue

            output = _completed_text(ready).strip()
            if ready.returncode == 0 and "SEEED_WSL_READY" in output:
                self._last_wsl_ready_error = None
                return True
            if output:
                self._last_wsl_ready_error = (
                    f"{self.distro} returned exit code {ready.returncode} while starting."
                )
                self._log(f"[WSL] Ready probe output: {output.splitlines()[-1]}")
            time.sleep(3)
        return False

    def _run_wsl(self, args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
        return _run_capture([_wsl_exe(), "-d", self.distro, "-u", "root", "--", *args], timeout=timeout or 60)

    def _log_diagnostic_output(self, title: str, output: str, returncode: int | None = None, max_lines: int = 24):
        header = f"[STEP 6/7] {title}"
        if returncode is not None:
            header += f" (exit={returncode})"
        self._log(header)
        lines = [line.rstrip() for line in (output or "").splitlines() if line.strip()]
        if not lines:
            self._log("[STEP 6/7]   (no output)")
            return
        for line in lines[:max_lines]:
            self._log(f"[STEP 6/7]   {line}")
        if len(lines) > max_lines:
            self._log(f"[STEP 6/7]   ... {len(lines) - max_lines} more line(s) omitted")

    def _run_wsl_diag(self, title: str, command: str, timeout: int = 20):
        try:
            result = self._run_wsl(["bash", "-lc", command], timeout=timeout)
            self._log_diagnostic_output(title, _completed_text(result), result.returncode)
        except Exception as e:
            self._log(f"[STEP 6/7] {title} failed: {e}")

    def _run_host_diag(self, title: str, args: list[str], timeout: int = 15):
        try:
            result = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                **_hidden_subprocess_kwargs(),
            )
            self._log_diagnostic_output(title, result.stdout or "", result.returncode)
        except Exception as e:
            self._log(f"[STEP 6/7] {title} failed: {e}")

    def _collect_nfs_failure_diagnostics(self, tail_text: str):
        self._log("[STEP 6/7] ROOT CAUSE: NFS mount failure during flashing.")
        self._log("[STEP 6/7] The device booted into initrd flash mode, but could not mount the host NFS share.")
        self._log("[STEP 6/7] Running automatic diagnostics based on Seeed's NFS troubleshooting checklist...")
        self._log("[STEP 6/7] Note: WSL is less stable than a native Ubuntu host for NFS-based flashing.")

        match = re.search(r"Debug log saved to (\S+)", tail_text)
        if match:
            debug_log = match.group(1).rstrip(".")
            self._run_wsl_diag(
                f"NVIDIA debug log tail: {debug_log}",
                f"tail -n 80 {shlex.quote(debug_log)} 2>/dev/null || "
                f"sed -n '1,80p' {shlex.quote(debug_log)} 2>/dev/null || "
                f"echo 'debug log not found: {debug_log}'",
                timeout=20,
            )

        self._run_wsl_diag(
            "WSL NFS services",
            "service rpcbind start >/dev/null 2>&1 || true; "
            "service nfs-kernel-server start >/dev/null 2>&1 || true; "
            "service rpcbind status 2>&1 || true; echo '---'; "
            "service nfs-kernel-server status 2>&1 || true",
            timeout=20,
        )
        self._run_wsl_diag(
            "WSL exported NFS shares",
            "exportfs -v 2>&1 || echo 'exportfs unavailable'",
            timeout=15,
        )
        self._run_wsl_diag(
            "WSL rpcbind/NFS listening ports",
            "ss -ltnup 2>&1 | grep -E ':(111|2049)\\b' || echo 'rpcbind/NFS ports are not listening'",
            timeout=15,
        )
        self._run_wsl_diag(
            "WSL usb0 network interface",
            "ip addr show usb0 2>&1 || echo 'usb0 interface is missing'",
            timeout=15,
        )
        self._run_wsl_diag(
            "WSL disk space",
            "df -h / /tmp 2>&1 || true",
            timeout=15,
        )
        self._run_wsl_diag(
            "WSL firewall status",
            "command -v ufw >/dev/null 2>&1 && ufw status 2>&1 || echo 'ufw not installed'",
            timeout=15,
        )
        self._run_host_diag(
            "Windows firewall profiles",
            ["netsh", "advfirewall", "show", "allprofiles", "state"],
            timeout=15,
        )
        self._run_host_diag(
            "Windows active VPN-like adapters",
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and "
                    "($_.Name -match 'VPN|TAP|TUN|WireGuard|AnyConnect|Fortinet|OpenVPN|ZeroTier|Tailscale' -or "
                    "$_.InterfaceDescription -match 'VPN|TAP|TUN|WireGuard|AnyConnect|Fortinet|OpenVPN|ZeroTier|Tailscale') } | "
                    "Select-Object -ExpandProperty Name"
                ),
            ],
            timeout=15,
        )
        self._log("[STEP 6/7] Manual follow-up if this still fails:")
        self._log("[STEP 6/7]   1. Temporarily disable VPN / firewall rules that may block NFS over usb0.")
        self._log("[STEP 6/7]   2. Ensure the target SSD is formatted as ext4 if flashing to external storage.")
        self._log("[STEP 6/7]   3. Verify there is enough host disk space for the initrd flash workspace.")
        self._log("[STEP 6/7]   4. If repeated in WSL, retry on a native Ubuntu host.")

    def _ensure_usbipd(self):
        self._log("[STEP 2/7] Checking usbipd-win installation...")
        ensure_usbipd_ready(log=self._log)

        # List all devices for diagnostics
        try:
            dev_list = list_usb_devices()
            self._log(f"[usbipd] Current device count: {len(dev_list)}")
            for d in dev_list:
                self._log(f"[usbipd]   {d.busid} {d.hardware_id} {d.description} [{d.state}]")
        except Exception as e:
            self._log(f"[usbipd] Could not enumerate devices: {e}")

        usbpcap = _usbpcap_status()
        if usbpcap:
            self._log(f"[WARN] {usbpcap}")
            self._log("[WARN] USBPcap may interfere with usbipd. Consider uninstalling USBPcap if flashing fails.")
        self._log("[STEP 2/7] usbipd-win ready ✓")

    def _ensure_kernel_if_needed(self):
        if os.environ.get("SEEED_WSL_SKIP_KERNEL") == "1":
            self._log("[STEP 3/7] Skipping WSL kernel USBIP check (SEEED_WSL_SKIP_KERNEL=1).")
            return
        self._log("[STEP 3/7] Checking WSL kernel USB/RNDIS support...")
        check = self._run_wsl(
            [
                "bash",
                "-lc",
                "zcat /proc/config.gz 2>/dev/null || true",
            ],
            timeout=30,
        )
        text = _completed_text(check)
        usbip_ok = _kernel_config_enabled(text, "CONFIG_USBIP_VHCI_HCD")
        rndis_ok = _kernel_config_enabled(text, "CONFIG_USB_NET_RNDIS_HOST")
        self._log(f"[WSL kernel] CONFIG_USBIP_VHCI_HCD={usbip_ok}, CONFIG_USB_NET_RNDIS_HOST={rndis_ok}")
        if usbip_ok and rndis_ok:
            self._log("[STEP 3/7] WSL kernel already has USBIP and RNDIS support. ✓")
            return

        self._log("[WSL kernel] Missing kernel features. Attempting to download custom Seeed bzImage...")
        kernel_path = Path.home() / "Seeed" / "WSL_Kernel" / "bzImage"
        if not kernel_path.exists() or not self._sha256_matches(kernel_path, KERNEL_SHA256):
            self._log(f"[WSL kernel] Downloading custom kernel to {kernel_path}...")
            self._download_kernel(kernel_path)
        else:
            self._log(f"[WSL kernel] Using cached custom kernel at {kernel_path}.")
        self._configure_wsl_kernel(kernel_path)
        self._log("[WSL kernel] WSL kernel configured. Restarting WSL (wsl --shutdown)...")
        subprocess.run(
            [_wsl_exe(), "--shutdown"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **_hidden_subprocess_kwargs(),
        )
        time.sleep(2)
        self._log("[STEP 3/7] Custom WSL kernel configured and WSL restarted. ✓")
        self._log("[NOTE] Custom kernel requires WSL restart. Flashing can now proceed.")

    def _suspend_shell_hardware_detection(self):
        if os.name != "nt" or os.environ.get("SEEED_WSL_KEEP_SHELL_HW_DETECTION") == "1":
            return
        service = WINDOWS_SHELL_HW_DETECTION_SERVICE
        state = _windows_service_state(service)
        if state is None:
            self._log("[Windows shell] Could not read Shell Hardware Detection state; skipping popup suppression.")
            return
        if state != "RUNNING":
            self._log(f"[Windows shell] Shell Hardware Detection is {state}; leaving it unchanged.")
            return

        self._log("[Windows shell] Temporarily stopping Shell Hardware Detection to suppress AutoPlay disk popups...")
        self._log("[Windows shell] A Windows UAC prompt may appear; click 'Yes' to continue.")
        code = _run_elevated_service_control("stop", service)
        if code != 0:
            self._log(f"[Windows shell] Could not stop Shell Hardware Detection (exit {code}); continuing.")
            return

        deadline = time.time() + 20
        while time.time() < deadline:
            current = _windows_service_state(service)
            if current == "STOPPED":
                self._restore_shell_hw_detection = True
                self._log("[Windows shell] Shell Hardware Detection stopped for this flash session.")
                return
            time.sleep(1)

        self._log("[Windows shell] Shell Hardware Detection stop did not settle in time; continuing.")

    def _restore_shell_hardware_detection_if_needed(self):
        if not self._restore_shell_hw_detection:
            return
        service = WINDOWS_SHELL_HW_DETECTION_SERVICE
        self._log("[Windows shell] Restoring Shell Hardware Detection...")
        code = _run_elevated_service_control("start", service)
        if code == 0:
            self._restore_shell_hw_detection = False
            self._log("[Windows shell] Shell Hardware Detection restored.")
        else:
            self._log(
                f"[Windows shell] WARNING: failed to restore Shell Hardware Detection (exit {code}). "
                "Run 'sc start ShellHWDetection' as Administrator to restore it manually."
            )

    def _sha256_matches(self, path: Path, expected: str) -> bool:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest().lower() == expected.lower()

    def _download_kernel(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".download")
        self._log(f"Downloading Seeed WSL kernel to {path}...")
        try:
            response = requests.get(
                _with_download_flag(KERNEL_URL),
                stream=True,
                timeout=(15, 900),
                allow_redirects=True,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status == 403:
                raise WslFlashError(
                    "The configured WSL kernel link is not publicly downloadable (HTTP 403). "
                    "Set SEEED_WSL_KERNEL_URL to a working public share link or provide a direct bzImage URL."
                ) from exc
            raise
        first = True
        with open(tmp, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                self._check_cancel()
                if not chunk:
                    continue
                if first and chunk.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                    raise WslFlashError("The WSL kernel download returned an HTML page instead of bzImage.")
                first = False
                f.write(chunk)
        if not self._sha256_matches(tmp, KERNEL_SHA256):
            tmp.unlink(missing_ok=True)
            raise WslFlashError("Downloaded WSL kernel SHA256 does not match the Seeed wiki value.")
        tmp.replace(path)

    def _configure_wsl_kernel(self, kernel_path: Path):
        config = Path.home() / ".wslconfig"
        old = config.read_text(encoding="utf-8") if config.exists() else ""
        backup = config.with_suffix(f".wslconfig.bak.{int(time.time())}")
        if config.exists():
            shutil.copy2(config, backup)
            self._log(f"Backed up existing .wslconfig to {backup}")

        kernel_value = str(kernel_path).replace("\\", "\\\\")
        kernel_line = f"kernel={kernel_value}"
        lines = old.splitlines()
        out: list[str] = []
        in_wsl2 = False
        wrote_kernel = False
        saw_wsl2 = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if in_wsl2 and not wrote_kernel:
                    out.append(kernel_line)
                    wrote_kernel = True
                in_wsl2 = stripped.lower() == "[wsl2]"
                saw_wsl2 = saw_wsl2 or in_wsl2
                out.append(line)
                continue
            if in_wsl2 and stripped.lower().startswith("kernel="):
                if not wrote_kernel:
                    out.append(kernel_line)
                    wrote_kernel = True
                continue
            out.append(line)
        if not saw_wsl2:
            if out and out[-1].strip():
                out.append("")
            out.extend(["[wsl2]", kernel_line])
        elif in_wsl2 and not wrote_kernel:
            out.append(kernel_line)
        config.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")

    def _find_or_attach_recovery(self) -> UsbDevice:
        self._log("[STEP 4/7] Looking for NVIDIA APX recovery device in usbipd (timeout=120s)...")
        self._log("[STEP 4/7] Ensure the Jetson is in Recovery mode:")
        self._log("  1. Disconnect power")
        self._log("  2. Connect USB-C cable (DATA cable, NOT charge-only)")
        self._log("  3. Hold RECOVERY button")
        self._log("  4. Press and release RESET button")
        self._log("  5. Release RECOVERY button 2-3 seconds later")
        self._log("  6. Check Windows Device Manager for 'NVIDIA APX' device")
        self._log("")

        deadline = time.time() + 120
        last_error = None
        attempt = 0
        while time.time() < deadline:
            self._check_cancel()
            attempt += 1
            elapsed = int(time.time() - (deadline - 120))
            remaining = int(deadline - time.time())

            # Log all visible USB devices each poll for diagnostics
            try:
                all_devs = list_usb_devices()
                nvidia_devs = [d for d in all_devs if "0955" in d.hardware_id]
                if nvidia_devs:
                    for d in nvidia_devs:
                        self._log(f"[usbipd scan #{attempt}] [{remaining}s left] Found NVIDIA device: {d.raw.strip()} [{d.state}]")
                elif attempt % 5 == 1:  # Throttle to every 5 attempts (~15s)
                    self._log(f"[usbipd scan #{attempt}] [{remaining}s left] No NVIDIA device found. Current devices: {len(all_devs)}")
            except Exception as scan_e:
                if attempt % 5 == 1:
                    self._log(f"[usbipd scan #{attempt}] [{remaining}s left] Device enumeration error: {scan_e}")

            try:
                device = find_nvidia_apx_device()
                if device:
                    self._log(f"[STEP 4/7] Found APX device after {attempt} scan(s): {device.raw.strip()}")
                    self._log(f"[STEP 4/7] BusID={device.busid}, State={device.state}, HWID={device.hardware_id}")
                    self._bind_device(device.busid)
                    self._log("[STEP 4/7] Recovery device found and bound ✓")
                    return device
            except WslFlashError as exc:
                last_error = exc
                break
            self._log(f"[STEP 4/7] Waiting... ({remaining}s remaining until timeout)")
            time.sleep(3)

        # Final attempt: also log all devices before failing
        try:
            final_devs = list_usb_devices()
            self._log("[STEP 4/7] === Final device list before failure ===")
            for d in final_devs:
                self._log(f"[STEP 4/7]   {d.busid} {d.hardware_id} {d.description} [{d.state}]")
            if not any("0955" in d.hardware_id for d in final_devs):
                self._log("[STEP 4/7] ROOT CAUSE: No NVIDIA USB device found at all.")
                self._log("[STEP 4/7] Check: (1) Is Jetson in Recovery mode? (2) USB data cable? (3) Try a different USB port.")
        except Exception as e:
            self._log(f"[STEP 4/7] Could not enumerate final devices: {e}")

        if last_error:
            raise last_error
        raise WslFlashError(
            "No NVIDIA APX recovery device found. Put the Jetson into Recovery mode and retry.\n"
            "  - Use a USB DATA cable (not charge-only)\n"
            "  - Hold RECOVERY button while pressing RESET\n"
            "  - Check Device Manager for 'NVIDIA APX' or '0955' device"
        )

    def _bind_device(self, busid: str, state_hint: str | None = None):
        current_state = (state_hint if state_hint is not None else self._get_host_attach_state(busid)).strip()
        with self._attach_lock:
            if _usbipd_state_needs_bind(current_state):
                self._bound_busids.discard(busid)
            elif busid in self._bound_busids and _usbipd_state_shared(current_state):
                self._log(f"[usbipd] BusID {busid} already shared on host ({current_state}); skipping bind.")
                return
        if _usbipd_state_shared(current_state):
            with self._attach_lock:
                self._bound_busids.add(busid)
            self._log(f"[usbipd] BusID {busid} already shared on host ({current_state}); skipping bind.")
            return
        if _usbipd_state_needs_bind(current_state):
            self._log(f"[usbipd] BusID {busid} host state is '{current_state}'. Rebinding for WSL passthrough...")
        usbipd = _usbipd_exe()
        self._log(f"[usbipd] Binding BusID {busid} for WSL USB passthrough (requires admin)...")
        result = subprocess.run(
            [usbipd, "bind", "--busid", busid, "--force"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        text = result.stdout or ""
        lowered = text.lower()
        self._log(f"[usbipd] bind result: code={result.returncode}, stdout={text.strip()!r}")
        if result.returncode == 0 or "already shared" in lowered or "is already shared" in lowered:
            with self._attach_lock:
                self._bound_busids.add(busid)
            self._log(f"[usbipd] BusID {busid} bound successfully ✓")
            return
        self._log("[usbipd] Non-admin bind failed. Requesting UAC elevation...")
        self._log("[usbipd] A Windows UAC prompt will appear; click 'Yes' to grant admin rights.")
        code = _run_elevated(usbipd, ["bind", "--busid", busid, "--force"], timeout=None)
        self._log(f"[usbipd] Elevated bind returned code: {code}")
        if code != 0:
            raise WslFlashError(f"usbipd bind failed for {busid} (exit {code}).")
        with self._attach_lock:
            self._bound_busids.add(busid)
        self._log(f"[usbipd] BusID {busid} bound with elevation ✓")

    def _attach_busid_to_wsl(
        self,
        busid: str,
        state_hint: str | None = None,
        timeout: int = 15,
    ) -> subprocess.CompletedProcess:
        usbipd = _usbipd_exe()
        if not usbipd:
            raise WslFlashError("usbipd-win is not installed or not on PATH")
        current_state = (state_hint if state_hint is not None else self._get_host_attach_state(busid)).strip()
        if _usbipd_state_needs_bind(current_state):
            self._bind_device(busid, state_hint=current_state)

        command = [usbipd, "attach", "--wsl", "--busid", busid]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        lowered = (result.stdout or "").lower()
        if "device is not shared" in lowered:
            self._log(f"[usbipd] BusID {busid} lost share state during attach; rebinding and retrying once.")
            self._bind_device(busid, state_hint="Not shared")
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        return result

    def _remember_attached_busid(self, busid: str):
        with self._attach_lock:
            self._attached_busid = busid
            self._seen_busids.add(busid)

    def _current_attached_busid(self) -> str | None:
        with self._attach_lock:
            return self._attached_busid

    def _known_busids(self) -> list[str]:
        with self._attach_lock:
            return sorted(self._seen_busids)

    def _start_auto_attach(self, busid: str):
        if self._attach_thread and self._attach_thread.is_alive():
            return
        self._attach_stop.clear()
        self._attach_confirmed.clear()
        self._attach_thread = threading.Thread(target=self._auto_attach_worker, args=(busid,), daemon=True)
        self._attach_thread.start()
        self._attach_pulse_thread = threading.Thread(target=self._attach_pulse_worker, args=(busid,), daemon=True)
        self._attach_pulse_thread.start()
        self._dynamic_attach_thread = threading.Thread(target=self._dynamic_attach_worker, daemon=True)
        self._dynamic_attach_thread.start()

    def _auto_attach_worker(self, busid: str):
        usbipd = _usbipd_exe()
        command = [usbipd, "attach", "--wsl", "--busid", busid, "--auto-attach"]
        while not self._attach_stop.is_set():
            self._log(f"Starting usbipd auto-attach loop for bus {busid}.")
            try:
                self._attach_process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
                assert self._attach_process.stdout is not None
                for line in self._attach_process.stdout:
                    if line.strip():
                        self._log(f"[usbipd] {line.rstrip()}")
                        if "is now attached" in line.lower():
                            self._remember_attached_busid(busid)
                            self._attach_confirmed.set()
                    if self._attach_stop.is_set():
                        break
                code = self._attach_process.wait(timeout=5)
                if self._attach_stop.is_set():
                    return
                self._log(f"usbipd auto-attach exited with {code}; restarting in 3 seconds.")
            except Exception as exc:
                if self._attach_stop.is_set():
                    return
                self._log(f"usbipd auto-attach failed: {exc}; retrying in 3 seconds.")
            time.sleep(3)

    def _attach_pulse_worker(self, busid: str):
        usbipd = _usbipd_exe()
        if not usbipd:
            return
        command = [usbipd, "attach", "--wsl", "--busid", busid]
        last_log = ""
        self._log(f"Starting secondary usbipd attach pulse for bus {busid}.")
        while not self._attach_stop.is_set():
            try:
                state = self._get_host_attach_state(busid)
                if _usbipd_state_attached(state):
                    self._remember_attached_busid(busid)
                    self._attach_confirmed.set()
                    summary = f"{busid}:attached"
                    if summary != last_log:
                        self._log(f"[usbipd-pulse] bus {busid} already attached; pulse is standing by.")
                        last_log = summary
                    for _ in range(20):
                        if self._attach_stop.is_set():
                            return
                        time.sleep(0.1)
                    continue

                result = self._attach_busid_to_wsl(busid, state_hint=state, timeout=15)
                text = (result.stdout or "").strip()
                lowered = text.lower()
                if result.returncode == 0 or "already attached" in lowered or "is now attached" in lowered:
                    self._remember_attached_busid(busid)
                    self._attach_confirmed.set()
                summary = f"{result.returncode}: {text.splitlines()[-1] if text else ''}".strip()
                if text and summary != last_log and (
                    result.returncode == 0
                    or "already attached" not in lowered
                ):
                    self._log(f"[usbipd-pulse] {text}")
                    last_log = summary
            except subprocess.TimeoutExpired:
                if last_log != "timeout":
                    self._log(f"[usbipd-pulse] attach command timed out for bus {busid}; retrying.")
                    last_log = "timeout"
            except Exception as exc:
                if self._attach_stop.is_set():
                    return
                summary = str(exc)
                if summary != last_log:
                    self._log(f"[usbipd-pulse] attach failed: {exc}; retrying.")
                    last_log = summary
            for _ in range(20):
                if self._attach_stop.is_set():
                    return
                time.sleep(0.1)

    def _dynamic_attach_worker(self):
        usbipd = _usbipd_exe()
        if not usbipd:
            return
        last_log = ""
        self._log("Starting dynamic NVIDIA USB attach watcher.")
        while not self._attach_stop.is_set():
            try:
                device = find_nvidia_flash_usb_device()
                if device is None:
                    summary = "no-nvidia-usb"
                    if summary != last_log:
                        self._log("[usbipd-dynamic] Waiting for NVIDIA USB re-enumeration.")
                        last_log = summary
                else:
                    busid = device.busid
                    self._remember_attached_busid(busid)
                    state = device.state.lower()
                    if _usbipd_state_attached(state):
                        self._attach_confirmed.set()
                        summary = f"{busid}:attached"
                        if summary != last_log:
                            self._log(f"[usbipd-dynamic] {device.raw.strip()}")
                            self._log(f"[usbipd-dynamic] bus {busid} already attached; watcher is standing by.")
                            last_log = summary
                        for _ in range(10):
                            if self._attach_stop.is_set():
                                return
                            time.sleep(0.1)
                        continue

                    result = self._attach_busid_to_wsl(busid, state_hint=device.state, timeout=10)
                    text = (result.stdout or "").strip()
                    lowered = text.lower()
                    if result.returncode == 0 or "already attached" in lowered or "is now attached" in lowered:
                        self._remember_attached_busid(busid)
                        self._attach_confirmed.set()
                    summary = f"{busid}:{result.returncode}:{text.splitlines()[-1] if text else device.state}"
                    if summary != last_log and (
                        result.returncode == 0
                        or "already attached" not in lowered
                    ):
                        self._log(f"[usbipd-dynamic] {device.raw.strip()}")
                        if text:
                            self._log(f"[usbipd-dynamic] {text}")
                        last_log = summary
            except subprocess.TimeoutExpired:
                if last_log != "dynamic-timeout":
                    self._log("[usbipd-dynamic] attach command timed out; retrying.")
                    last_log = "dynamic-timeout"
            except Exception as exc:
                if self._attach_stop.is_set():
                    return
                summary = str(exc)
                if summary != last_log:
                    self._log(f"[usbipd-dynamic] attach watcher failed: {exc}; retrying.")
                    last_log = summary
            for _ in range(10):
                if self._attach_stop.is_set():
                    return
                time.sleep(0.1)

    def _get_host_attach_state(self, busid: str) -> str:
        for device in list_usb_devices():
            if device.busid == busid:
                return device.state
        return "Missing"

    def _start_attach_state_monitor(self, busid: str):
        if self._attach_state_thread and self._attach_state_thread.is_alive():
            return
        self._attach_state_stop.clear()
        self._last_host_attach_state = None

        def _worker():
            while not self._attach_state_stop.is_set():
                try:
                    current_busid = self._current_attached_busid() or busid
                    state = self._get_host_attach_state(current_busid)
                    state_key = f"{current_busid}:{state}"
                    if state_key != self._last_host_attach_state:
                        self._last_host_attach_state = state_key
                        self._log(f"[usbipd] Host BUSID {current_busid} state: {state}")
                        if "attached" not in state.lower():
                            self._attach_confirmed.clear()
                    if "attached" in state.lower():
                        self._attach_confirmed.set()
                except Exception as exc:
                    self._log(f"[usbipd] Host state check failed: {exc}")
                time.sleep(1)

        self._attach_state_thread = threading.Thread(target=_worker, daemon=True)
        self._attach_state_thread.start()

    def _stop_attach_state_monitor(self):
        self._attach_state_stop.set()
        if self._attach_state_thread and self._attach_state_thread.is_alive():
            self._attach_state_thread.join(timeout=3)

    def _stop_auto_attach(self):
        self._attach_stop.set()
        proc = self._attach_process
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        if self._attach_thread and self._attach_thread.is_alive():
            self._attach_thread.join(timeout=5)
        if self._attach_pulse_thread and self._attach_pulse_thread.is_alive():
            self._attach_pulse_thread.join(timeout=5)
        if self._dynamic_attach_thread and self._dynamic_attach_thread.is_alive():
            self._dynamic_attach_thread.join(timeout=5)
        known_busids = self._known_busids()
        if known_busids:
            self._log(
                "[usbipd] Leaving APX attached for retry/debug: "
                + ", ".join(known_busids)
            )

    def _wait_for_wsl_apx(self, timeout: int):
        self._log("Waiting for APX device to appear inside WSL...")
        deadline = time.time() + timeout
        probe = r"""python3 - <<'PY'
from pathlib import Path
found = False
for path in Path('/sys/bus/usb/devices').glob('*'):
    vendor = path / 'idVendor'
    product = path / 'idProduct'
    if not vendor.exists() or not product.exists():
        continue
    try:
        vid = vendor.read_text().strip().lower()
        pid = product.read_text().strip().lower()
    except Exception:
        continue
    if vid == '0955':
        print(f'{path.name} 0955:{pid}')
        found = True
if not found:
    raise SystemExit(1)
PY"""
        while time.time() < deadline:
            self._check_cancel()
            result = self._run_wsl(["bash", "-lc", probe], timeout=20)
            text = _completed_text(result).strip()
            if result.returncode == 0 and text:
                device_lines = [line.strip() for line in text.splitlines() if re.search(r"\b0955:[0-9a-f]{4}\b", line, re.I)]
                self._log(f"WSL sees recovery device: {device_lines[-1] if device_lines else text}")
                return
            time.sleep(2)
        raise WslFlashError("APX device did not appear inside WSL. Check usbipd, cable, and Recovery mode.")

    def _wait_for_usbipd_attach_stable(self, busid: str, timeout: int):
        self._log("[STEP 5/7] Waiting for USB passthrough to stabilize (require 3 consecutive confirmations)...")
        self._log("[STEP 5/7] This step requires 3 conditions to ALL be true simultaneously:")
        self._log("  (A) usbipd attach event was fired (_attach_confirmed event set)")
        self._log("  (B) Windows 'usbipd list' shows BUSID state=attached")
        self._log("  (C) WSL 'lsusb | grep 0955' sees the NVIDIA APX device")
        self._log("[STEP 5/7] All 3 conditions must hold stable for 3 consecutive checks (~6s).")
        self._log("[STEP 5/7] If this step times out, the APX device is not stably visible inside WSL.")
        self._log("")

        deadline = time.time() + timeout
        stable_hits = 0
        attempt = 0
        while time.time() < deadline:
            self._check_cancel()
            attempt += 1
            remaining = int(deadline - time.time())
            current_busid = self._current_attached_busid() or busid

            # Check (A): _attach_confirmed event
            attach_confirmed = self._attach_confirmed.is_set()

            # Check (B): Windows host state
            host_state = self._get_host_attach_state(current_busid)
            host_attached = "attached" in host_state.lower()
            host_state_detail = f"{current_busid} [{host_state}]"

            # Check (C): WSL lsusb
            wsl_visible = False
            wsl_output = ""
            try:
                result = self._run_wsl(
                    ["bash", "-lc", "lsusb | grep -i '0955:' || echo SEEED_APX_NOT_FOUND"],
                    timeout=20,
                )
                wsl_output = _completed_text(result).strip()
                wsl_visible = result.returncode == 0 and "SEEED_APX_NOT_FOUND" not in wsl_output and bool(wsl_output)
            except Exception as e:
                wsl_output = f"error: {e}"
                wsl_visible = False

            # Determine all 3 conditions
            all_ok = attach_confirmed and host_attached and wsl_visible

            # Build detailed status line
            status_parts = []
            status_parts.append(f"#{attempt} [{remaining}s left]")
            status_parts.append(f"A={'Y' if attach_confirmed else 'N'}")
            status_parts.append(f"B={'Y' if host_attached else 'N'}({host_state})")
            status_parts.append(f"C={'Y' if wsl_visible else 'N'}({wsl_output.splitlines()[-1] if wsl_output else 'N/A'})")
            status_parts.append(f"STABLE_HITS={stable_hits}/3")
            status_parts.append("** ALL OK **" if all_ok else "")

            if all_ok:
                stable_hits += 1
                self._log(f"[usbipd stable?] {' '.join(status_parts)}")
            else:
                if stable_hits > 0:
                    self._log(f"[usbipd stable?] RESET hits to 0 — one condition dropped. {' '.join(status_parts)}")
                stable_hits = 0
                # Only log every ~10s to avoid spam
                if attempt % 5 == 1:
                    self._log(f"[usbipd stable?] {' '.join(status_parts)}")
                    if not host_attached:
                        self._log(f"[usbipd] (B) NOT attached — Windows usbipd did not attach the device.")
                    if not wsl_visible:
                        self._log(f"[usbipd] (C) NOT visible in WSL — USB passthrough is broken.")
                        self._log(f"[usbipd]   Check: WSL kernel USBIP support, USB cable quality, avoid USB hubs.")
                    if not attach_confirmed:
                        self._log(f"[usbipd] (A) NOT confirmed — attach event not received by the tool.")

            if stable_hits >= 3:
                self._log(f"[STEP 5/7] USB passthrough stable after {attempt} checks. ✓ ✓ ✓")
                return

            time.sleep(2)

        # Failed: log final diagnostic
        self._log("[STEP 5/7] === USB PASSTHROUGH TIMEOUT — ROOT CAUSE ANALYSIS ===")
        self._log("[STEP 5/7] Stable hits achieved: {}/3 (needed 3)".format(stable_hits))
        current_busid = self._current_attached_busid() or busid
        host_state = self._get_host_attach_state(current_busid)
        self._log(f"[STEP 5/7] Final Windows host state for {current_busid}: {host_state!r}")
        if "attached" not in host_state.lower():
            self._log("[STEP 5/7] DIAGNOSIS: Windows 'usbipd list' does NOT show 'attached' state.")
            self._log("[STEP 5/7]   → This usually means the USB cable dropped or the device disconnected.")
        try:
            result = self._run_wsl(["bash", "-lc", "lsusb | grep -i '0955:' || echo NOT_FOUND"], timeout=10)
            wsl_out = _completed_text(result).strip()
            self._log(f"[STEP 5/7] Final WSL lsusb output: {wsl_out!r}")
            if "NOT_FOUND" in wsl_out or not wsl_out:
                self._log("[STEP 5/7] DIAGNOSIS: APX device is NOT visible inside WSL.")
                self._log("[STEP 5/7]   → The usbipd-win driver is not forwarding USB to WSL.")
                self._log("[STEP 5/7]   → Check WSL kernel CONFIG_USBIP_VHCI_HCD, USB cable, and avoid USB hubs.")
        except Exception as e:
            self._log(f"[STEP 5/7] Could not check WSL lsusb: {e}")
        self._log("[STEP 5/7] Try: (1) Use a shorter/higher-quality USB cable, (2) Direct USB port (no hub),")
        self._log("[STEP 5/7]        (3) Re-enter Recovery mode, (4) Restart usbipd-win service.")
        raise WslFlashError(
            "usbipd attach did not stabilize. "
            "The APX device is not stably visible inside WSL. "
            "Check: (1) USB cable quality — use a DATA cable, not charge-only; "
            "(2) Avoid USB hubs; (3) Re-enter Recovery mode; "
            "(4) Ensure WSL kernel has CONFIG_USBIP_VHCI_HCD. "
            "See full diagnosis above in the log."
        )

    def _pre_stage_archive(self):
        """Stage firmware archive to Windows temp before USB attach, so WSL network reset doesn't interrupt the copy."""
        archive = self.download_dir / self.firmware_info["filename"]
        if not archive.exists():
            return
        self._staged_archive = self._stage_archive_for_current_distro(archive)

    def _run_flash_in_wsl(self):
        self._log("[STEP 6/7] Starting WSL flash script (this takes 10-30 minutes)...")
        archive = self.download_dir / self.firmware_info["filename"]
        if not archive.exists():
            raise WslFlashError(f"Firmware archive not found: {archive}. Download/Extract BSP first.")
        archive = getattr(self, "_staged_archive", None) or self._stage_archive_for_current_distro(archive)

        product_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.product).strip("_") or "jetson"
        version_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.l4t_version).strip("_") or "l4t"
        workspace = f"/root/seeed-jetson-firmware/{product_slug}-{version_slug}"
        self._log(f"[WSL flash] Workspace: {workspace}")
        self._log(f"[WSL flash] Archive: {archive} ({archive.stat().st_size // 1024 // 1024} MB)")

        # Check if the archive is already inside WSL
        archive_str = str(archive.resolve())
        archive_in_wsl = archive_str.lower().startswith(f"\\\\wsl$\\{self.distro.lower()}\\")
        if archive_in_wsl:
            wsl_relative = archive_str[len(f"\\\\wsl$\\{self.distro}\\"):]
            archive_wsl = "/" + wsl_relative.replace("\\", "/")
            self._log(f"[WSL flash] Archive is in WSL filesystem: {archive_wsl}")
        else:
            archive_wsl = _windows_path_to_wsl(archive)
            self._log(f"[WSL flash] Archive is on Windows, mapped to WSL path: {archive_wsl}")

        foldername = self.firmware_info.get("foldername", "")
        expected_sha256 = (
            str(self.firmware_info.get("sha256") or "").strip().lower()
            if self.verify_archive_sha256
            else ""
        )
        # Use empty unquoted string for shell so that [ -n "$VAR" ] correctly returns false.
        # shlex.quote("") produces "''" which makes [ -n "''" ] return true (bug).
        expected_sha256_shell = expected_sha256 if expected_sha256 else '""'
        marker_value = f"{self.product}|{self.l4t_version}|{expected_sha256 or archive.name}"
        packages = " ".join(FLASH_PACKAGES)

        # When the archive is already in the workspace, $SRC == $ARCHIVE — skip cp.
        archive_already_in_workspace = archive_in_wsl and archive_wsl.startswith(workspace + "/")

        copy_block = (
            [
                '# archive is already in WSL workspace, no copy needed',
                'echo "[WSL] Firmware archive already in WSL workspace, skipping copy."',
            ]
            if archive_already_in_workspace
            else [
                'ARCHIVE_OK=0',
                'if [ -f "$ARCHIVE" ]; then',
                '  ARCHIVE_SIZE="$(stat -c%s "$ARCHIVE" 2>/dev/null || echo 0)"',
                '  SRC_SIZE="$(stat -c%s "$SRC")"',
                '  if [ "$ARCHIVE_SIZE" = "$SRC_SIZE" ]; then',
                '    if [ -n "$EXPECTED_SHA256" ] && command -v sha256sum >/dev/null 2>&1; then',
                '      ARCHIVE_SHA="$(sha256sum "$ARCHIVE" | awk \'{print tolower($1)}\')"',
                '      if [ "$ARCHIVE_SHA" = "$EXPECTED_SHA256" ]; then',
                '        ARCHIVE_OK=1',
                '      else',
                '        echo "[WSL] Existing firmware archive SHA256 mismatch; recopying."',
                '      fi',
                '    else',
                '      ARCHIVE_OK=1',
                '    fi',
                '  fi',
                'fi',
                'if [ "$ARCHIVE_OK" != "1" ]; then',
                '  echo "[WSL] Copying firmware archive into WSL storage..."',
                '  cp "$SRC" "$ARCHIVE"',
                '  chmod -x "$ARCHIVE" || true',
                'else',
                '  echo "[WSL] Existing firmware archive is complete, skipping copy."',
                "fi",
            ]
        )

        script = "\n".join(
            [
                "set -euo pipefail",
                "export DEBIAN_FRONTEND=noninteractive",
                f"WORK={shlex.quote(workspace)}",
                f"SRC={shlex.quote(archive_wsl)}",
                f"ARCHIVE_NAME={shlex.quote(archive.name)}",
                'ARCHIVE="$WORK/$ARCHIVE_NAME"' if not archive_already_in_workspace else f'ARCHIVE={shlex.quote(archive_wsl)}',
                'EXTRACT="$WORK/extracted"',
                f"FOLDERNAME={shlex.quote(foldername)}",
                f"EXPECTED_SHA256={expected_sha256_shell}",
                f"MARKER_EXPECTED={shlex.quote(marker_value)}",
                'echo "[WSL] Workspace: $WORK"',
                'mkdir -p "$WORK" "$EXTRACT"',
                *copy_block,
                'if [ "$(cat "$EXTRACT/.seeed_flash_marker" 2>/dev/null || true)" != "$MARKER_EXPECTED" ]; then',
                '  echo "[WSL] Extracting firmware archive with Linux permissions..."',
                '  rm -rf "$EXTRACT"',
                '  mkdir -p "$EXTRACT"',
                "  tar xpf \"$ARCHIVE\" -C \"$EXTRACT\" --checkpoint=500 --checkpoint-action='echo=[WSL] Extract checkpoint'",
                '  echo "$MARKER_EXPECTED" > "$EXTRACT/.seeed_flash_marker"',
                "fi",
                'if [ -n "$FOLDERNAME" ] && [ -d "$EXTRACT/$FOLDERNAME" ]; then',
                '  L4T_DIR="$EXTRACT/$FOLDERNAME"',
                "else",
                '  L4T_DIR="$(find "$EXTRACT" -mindepth 1 -maxdepth 1 -type d | head -n 1)"',
                "fi",
                'if [ -z "${L4T_DIR:-}" ] || [ ! -d "$L4T_DIR" ]; then',
                '  echo "[WSL] Could not locate extracted Linux_for_Tegra directory." >&2',
                "  exit 42",
                "fi",
                'echo "[WSL] Linux_for_Tegra directory: $L4T_DIR"',
                'if [ ! -f "$L4T_DIR/tools/kernel_flash/l4t_initrd_flash.sh" ]; then',
                '  echo "[WSL] Missing l4t_initrd_flash.sh in $L4T_DIR" >&2',
                "  exit 43",
                "fi",
                'chmod +x "$L4T_DIR/tools/kernel_flash/l4t_initrd_flash.sh" || true',
                'PATCHED_FLASH_SCRIPT="$L4T_DIR/tools/kernel_flash/l4t_initrd_flash.wsl.sh"',
                'cp "$L4T_DIR/tools/kernel_flash/l4t_initrd_flash.sh" "$PATCHED_FLASH_SCRIPT"',
                'python3 - "$PATCHED_FLASH_SCRIPT" <<\'PY\'',
                "from pathlib import Path",
                "import sys",
                "",
                "path = Path(sys.argv[1])",
                'text = path.read_text(encoding="utf-8")',
                "needle = 'autosuspend_value=\"$(cat /sys/module/usbcore/parameters/autosuspend)\"\\nset +e\\necho -1 > /sys/module/usbcore/parameters/autosuspend\\nset -e\\n'",
                "replacement = \"\"\"if [ -f /sys/module/usbcore/parameters/autosuspend ]; then",
                "\\tautosuspend_value=\\\"$(cat /sys/module/usbcore/parameters/autosuspend)\\\"",
                "\\tset +e",
                "\\techo -1 > /sys/module/usbcore/parameters/autosuspend",
                "\\tset -e",
                "else",
                "\\tautosuspend_value=\\\"\\\"",
                "fi",
                "\"\"\"",
                "if needle in text:",
                "    text = text.replace(needle, replacement, 1)",
                "cleanup_needle = '\\tset +e\\n\\techo \"${autosuspend_value}\" > /sys/module/usbcore/parameters/autosuspend\\n\\tset -e\\n'",
                "cleanup_replacement = \"\"\"\\tif [ -n \\\"${autosuspend_value}\\\" ] && [ -f /sys/module/usbcore/parameters/autosuspend ]; then",
                "\\t\\tset +e",
                "\\t\\techo \\\"${autosuspend_value}\\\" > /sys/module/usbcore/parameters/autosuspend",
                "\\t\\tset -e",
                "\\tfi",
                "\"\"\"",
                "if cleanup_needle in text:",
                "    text = text.replace(cleanup_needle, cleanup_replacement, 1)",
                'with path.open("w", encoding="utf-8", newline="\\n") as f:',
                "    f.write(text)",
                "PY",
                'chmod +x "$PATCHED_FLASH_SCRIPT"',
                'echo "[WSL] Installing flash prerequisites..."',
                f"PACKAGES=\"{packages}\"",
                'MISSING=""',
                'for pkg in $PACKAGES; do',
                '  if ! dpkg-query -W -f=\'${Status}\' "$pkg" 2>/dev/null | grep -q "install ok installed"; then',
                '    MISSING="$MISSING $pkg"',
                "  fi",
                "done",
                'if [ -n "$MISSING" ]; then',
                '  echo "[WSL] Missing packages:$MISSING"',
                "  apt-get update",
                '  apt-get install -y $MISSING',
                "else",
                '  echo "[WSL] Flash prerequisites already installed."',
                "fi",
                "service rpcbind start >/dev/null 2>&1 || true",
                "service nfs-kernel-server start >/dev/null 2>&1 || true",
                'echo "[WSL] Verifying APX device before flash..."',
                'lsusb | grep -i \'0955:\' || (echo "[WSL] APX device not visible in WSL." >&2; exit 44)',
                'echo "[WSL] Checking network interfaces (usb0 should appear after APX boot)..."',
                'echo "[WSL] Current network interfaces:"',
                'ip link show 2>/dev/null || ls /sys/class/net/ 2>/dev/null || echo "  (no network info)"',
                'echo "[WSL] Checking for USB gadget (RNDIS) driver:"',
                'ls /sys/bus/usb/drivers/rndis_host/ 2>/dev/null || echo "  (rndis_host driver dir not found)"',
                'ls /sys/bus/usb/drivers/usb0/ 2>/dev/null || echo "  (usb0 driver dir not found)"',
                'cd "$L4T_DIR"',
                'echo "[WSL] Flash command: ./tools/kernel_flash/l4t_initrd_flash.sh --flash-only --massflash 1 --network usb0 --showlogs"',
                'echo "[WSL] Starting l4t_initrd_flash.sh..."',
                "./tools/kernel_flash/l4t_initrd_flash.sh --flash-only --massflash 1 --network usb0 --showlogs",
            ]
        ) + "\n"
        self._log("[STEP 6/7] Executing WSL flash script (may take 10-30 minutes)...")
        self._log("[STEP 6/7] Progress will appear below as NVIDIA's flash tool runs.")
        self._run_wsl_stream(script)
        self._log("[STEP 6/7] WSL flash script completed without error.")

    def _stage_archive_for_current_distro(self, archive: Path) -> Path:
        parsed = _parse_wsl_unc_path(archive)
        if parsed is None:
            return archive

        source_distro, _ = parsed
        if source_distro.lower() == self.distro.lower():
            return archive

        target_dir = Path(tempfile.gettempdir()) / "seeed-wsl-archive-stage"
        staged = target_dir / archive.name
        source_size = archive.stat().st_size
        if staged.exists():
            try:
                if staged.stat().st_size == source_size:
                    self._log(
                        f"[WSL] Reusing staged archive for {self.distro}: {staged}"
                    )
                    return staged
            except OSError:
                pass

        self._log(
            f"[WSL] Staging firmware archive from {source_distro} to Windows temp for {self.distro}..."
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        for attempt in range(5):
            try:
                shutil.copy2(archive, staged)
                break
            except OSError as e:
                if attempt >= 4:
                    raise
                self._log(f"[WSL] Archive copy failed ({e}), retrying in 5s ({attempt+1}/5)...")
                time.sleep(5)
        return staged

    def _run_wsl_stream(self, script: str):
        script = script.replace("\r\n", "\n").replace("\r", "\n")
        temp_script = None
        process = None
        output_tail: list[str] = []
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False, encoding="utf-8", newline="\n") as f:
                f.write(script)
                temp_script = Path(f.name)
            wsl_cmd = [
                _wsl_exe(),
                "-d",
                self.distro,
                "-u",
                "root",
                "--",
                "bash",
                _windows_path_to_wsl(temp_script),
            ]
            self._log(f"[WSL exec] Running script via: {' '.join(wsl_cmd[:4])} ... bash {_windows_path_to_wsl(temp_script)}")
            process = subprocess.Popen(
                wsl_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                clean = line.rstrip()
                output_tail.append(clean)
                output_tail = output_tail[-120:]
                if clean.strip():
                    self._log(clean)
                self._check_cancel()
            code = process.wait()
            if code != 0:
                tail_text = "\n".join(output_tail)
                lowered = tail_text.lower()
                self._log(f"[STEP 6/7] WSL flash script exited with code {code}.")
                if _looks_like_nfs_mount_failure(tail_text):
                    self._collect_nfs_failure_diagnostics(tail_text)
                    raise WslFlashError(
                        "NFS mount failure during flashing. "
                        "The device reached initrd flash mode but could not mount the host NFS share. "
                        "Automatic diagnostics for NFS services, usb0, disk space, firewall, and VPN adapters "
                        "have been added to the log above."
                    )
                if (
                    "might be timeout in usb write" in lowered
                    or ("tegrarcm_v2" in lowered and "return value 3" in lowered)
                ):
                    current_busid = self._current_attached_busid() or "unknown"
                    usbpcap = _usbpcap_status()
                    self._log(f"[STEP 6/7] ROOT CAUSE: tegrarcm USB write timeout for BUSID {current_busid}.")
                    self._log("[STEP 6/7] This means APX boot data could NOT be sent through WSL usbipd.")
                    if usbpcap:
                        self._log(f"[STEP 6/7] NOTE: USBPcap is active and may be interfering.")
                    self._log("[STEP 6/7] Troubleshooting: (1) Try a shorter USB cable, (2) Direct port not hub,")
                    self._log("[STEP 6/7]            (3) Re-enter Recovery mode, (4) Check WSL kernel USBIP support.")
                    raise WslFlashError(
                        f"tegrarcm USB write timeout. APX boot data could not be sent through WSL usbipd "
                        f"(last BUSID={current_busid}). "
                        f"{usbpcap and ('Note: USBPcap may be interfering.' + chr(10)) or ''}"
                        "Try: shorter USB cable, direct port (no hub), re-enter Recovery mode. "
                        "Extraction is cached; only this step needs retry."
                    )

                # Detect boot-up timeout: NVIDIA flash tool sends APX boot data, then waits for the
                # device to enumerate as a USB gadget on the usb0 network interface.
                if "waiting for target to boot-up" in lowered or "boot-up" in lowered:
                    self._log("[STEP 6/7] ROOT CAUSE: Boot-up timeout.")
                    self._log("[STEP 6/7] The APX boot data WAS sent successfully (USB write OK).")
                    self._log("[STEP 6/7] But the device did not enumerate as a USB network gadget.")
                    self._log("[STEP 6/7] This is a network/RNDIS enumeration issue, not a USBIP passthrough issue.")
                    self._log("[STEP 6/7] Diagnostic steps:")
                    self._log("[STEP 6/7]   1. Check: ls /sys/class/net/usb0  (inside WSL)")
                    self._log("[STEP 6/7]   2. Check: ip link show usb0  (inside WSL)")
                    self._log("[STEP 6/7]   3. If usb0 exists but no IP: WSL kernel RNDIS driver issue")
                    self._log("[STEP 6/7]   4. If usb0 does NOT exist: CONFIG_USB_NET_RNDIS_HOST missing from WSL kernel")
                    self._log("[STEP 6/7]   5. Check: WSL .wslconfig has kernel= pointing to custom bzImage")
                    self._log("[STEP 6/7]   6. If using custom kernel, verify it has CONFIG_USB_NET_RNDIS_HOST=y")
                    raise WslFlashError(
                        "Boot-up timeout. APX boot data was sent but the device did not enumerate "
                        "as a USB network gadget (usb0). "
                        "This means WSL kernel lacks CONFIG_USB_NET_RNDIS_HOST support. "
                        "Run: SEEED_WSL_SKIP_KERNEL=0 to force custom bzImage download, "
                        "or manually verify your WSL kernel has CONFIG_USB_NET_RNDIS_HOST=y. "
                        "Check ls /sys/class/net/usb0 and ip link show usb0 inside WSL for details."
                    )
                last_line = next((line for line in reversed(output_tail) if line.strip()), "")
                detail = f" Last log line: {last_line}" if last_line else ""
                raise WslFlashError(f"WSL flash script exited with {code}.{detail}")
        except InterruptedError:
            if process is not None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
            raise
        finally:
            if temp_script:
                temp_script.unlink(missing_ok=True)
