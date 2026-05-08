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


def _run_capture(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    proc.stdout = _decode_output(proc.stdout).encode("utf-8", errors="replace")
    return proc


def _completed_text(proc: subprocess.CompletedProcess) -> str:
    out = proc.stdout or b""
    if isinstance(out, bytes):
        return out.decode("utf-8", errors="replace")
    return str(out)


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


def list_usb_devices() -> list[UsbDevice]:
    usbipd = _usbipd_exe()
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


def find_nvidia_apx_device() -> UsbDevice | None:
    for device in list_usb_devices():
        vid, pid = device.hardware_id.split(":", 1)
        desc = device.description.lower()
        if vid == "0955" and (pid in NVIDIA_APX_IDS or "apx" in desc):
            return device
    return None


def find_nvidia_flash_usb_device() -> UsbDevice | None:
    for device in list_usb_devices():
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
        self._log("Windows host detected; switching to WSL2 flash workflow.")
        self._log("WSL flashing is a convenience path. Use native Ubuntu if USB timeouts persist.")
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
            self._start_auto_attach(device.busid)
            self._start_attach_state_monitor(device.busid)
            self._wait_for_usbipd_attach_stable(device.busid, timeout=120)
            self._run_flash_in_wsl()
            self._log("WSL flash workflow completed.")
            return True
        finally:
            self._stop_attach_state_monitor()
            self._stop_auto_attach()

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

        self._log("Checking WSL installation...")
        subprocess.run([wsl, "--set-default-version", "2"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        distros = self._wsl_distros()
        candidate_order = [self.distro] + [
            d for d in self._preferred_distros if d.lower() != self.distro.lower()
        ]
        for candidate in candidate_order:
            if candidate in distros:
                self.distro = candidate
                break
        if self.distro not in distros:
            self._log(f"Installing WSL distro {self.distro}. Approve the Windows UAC prompt if it appears.")
            code = _run_elevated(wsl, ["--install", "-d", self.distro], timeout=None)
            distros = self._wait_for_distro_registration(timeout=120)
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

        ready = self._wait_for_wsl_ready(timeout=90)
        if not ready:
            raise WslFlashError(
                f"{self.distro} is installed but not initialized. "
                "Open it once from the Start menu, finish first-time setup, then retry."
            )
        self._log(f"WSL distro ready: {self.distro}")

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

    def _wait_for_wsl_ready(self, timeout: int) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            ready = self._run_wsl(["bash", "-lc", "echo SEEED_WSL_READY"], timeout=30)
            if ready.returncode == 0 and "SEEED_WSL_READY" in _completed_text(ready):
                return True
            time.sleep(3)
        return False

    def _run_wsl(self, args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
        return _run_capture([_wsl_exe(), "-d", self.distro, "-u", "root", "--", *args], timeout=timeout or 60)

    def _ensure_usbipd(self):
        usbipd = _usbipd_exe()
        if not usbipd:
            self._log("Installing usbipd-win. Approve the Windows UAC prompt if it appears.")
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
            if code != 0:
                raise WslFlashError(f"Failed to install usbipd-win with winget (exit {code}).")
            usbipd = _usbipd_exe()
            if not usbipd:
                raise WslFlashError("usbipd-win was installed, but usbipd.exe is not visible yet. Restart the app.")

        version = _run_capture([usbipd, "--version"], timeout=20)
        text = _completed_text(version).strip()
        self._log(f"usbipd-win detected: {text or usbipd}")
        usbpcap = _usbpcap_status()
        if usbpcap:
            self._log(
                f"[WARN] {usbpcap} usbipd-win reports USBPcap as incompatible. "
                "This is a host USB filter warning, not a firmware archive error."
            )
        match = re.search(r"(\d+)\.(\d+)", text)
        if match and int(match.group(1)) < 4:
            self._log("usbipd-win is older than 4.x; upgrading through winget.")
            _run_elevated("winget", ["upgrade", "--exact", "--id", "dorssel.usbipd-win"], timeout=None)

    def _ensure_kernel_if_needed(self):
        if os.environ.get("SEEED_WSL_SKIP_KERNEL") == "1":
            self._log("Skipping WSL custom kernel check because SEEED_WSL_SKIP_KERNEL=1.")
            return
        self._log("Checking WSL kernel USB/RNDIS support...")
        check = self._run_wsl(
            [
                "bash",
                "-lc",
                "zcat /proc/config.gz 2>/dev/null || true",
            ],
            timeout=30,
        )
        text = _completed_text(check)
        if (
            _kernel_config_enabled(text, "CONFIG_USBIP_VHCI_HCD")
            and _kernel_config_enabled(text, "CONFIG_USB_NET_RNDIS_HOST")
        ):
            self._log("WSL kernel already exposes USB/IP and RNDIS support.")
            return

        kernel_path = Path.home() / "Seeed" / "WSL_Kernel" / "bzImage"
        if not kernel_path.exists() or not self._sha256_matches(kernel_path, KERNEL_SHA256):
            self._download_kernel(kernel_path)
        self._configure_wsl_kernel(kernel_path)
        subprocess.run([_wsl_exe(), "--shutdown"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        time.sleep(2)
        self._log("Custom WSL kernel configured.")

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
        self._log("Looking for NVIDIA APX recovery device in usbipd...")
        deadline = time.time() + 120
        last_error = None
        while time.time() < deadline:
            self._check_cancel()
            try:
                device = find_nvidia_apx_device()
                if device:
                    self._log(f"Found recovery device: {device.raw.strip()}")
                    self._bind_device(device.busid)
                    return device
            except WslFlashError as exc:
                last_error = exc
                break
            self._log("No NVIDIA APX device yet; waiting for Recovery mode...")
            time.sleep(3)
        if last_error:
            raise last_error
        raise WslFlashError("No NVIDIA APX recovery device found. Put the Jetson into Recovery mode and retry.")

    def _bind_device(self, busid: str):
        with self._attach_lock:
            if busid in self._bound_busids:
                return
        usbipd = _usbipd_exe()
        self._log(f"Binding NVIDIA USB device {busid} for WSL USB passthrough...")
        result = subprocess.run(
            [usbipd, "bind", "--busid", busid, "--force"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        text = result.stdout or ""
        lowered = text.lower()
        if result.returncode == 0 or "already shared" in lowered or "is already shared" in lowered:
            with self._attach_lock:
                self._bound_busids.add(busid)
            return
        self._log("usbipd bind requires administrator permission. Requesting UAC elevation...")
        code = _run_elevated(usbipd, ["bind", "--busid", busid, "--force"], timeout=None)
        if code != 0:
            raise WslFlashError(f"usbipd bind failed for {busid} (exit {code}).")
        with self._attach_lock:
            self._bound_busids.add(busid)

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
                if "attached" in state.lower():
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

                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=15,
                )
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
                    if "attached" in state:
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

                    if "attached" not in state and "shared" not in state:
                        self._bind_device(busid)

                    result = subprocess.run(
                        [usbipd, "attach", "--wsl", "--busid", busid],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=10,
                    )
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
        self._log("Waiting for usbipd attach confirmation before flashing...")
        deadline = time.time() + timeout
        stable_hits = 0
        while time.time() < deadline:
            self._check_cancel()
            current_busid = self._current_attached_busid() or busid
            host_state = self._get_host_attach_state(current_busid)
            host_attached = "attached" in host_state.lower()
            wsl_visible = False
            try:
                result = self._run_wsl(
                    ["bash", "-lc", "lsusb | grep -i '0955:' || true"],
                    timeout=20,
                )
                text = _completed_text(result).strip()
                wsl_visible = result.returncode == 0 and bool(text)
            except Exception:
                wsl_visible = False
            if self._attach_confirmed.is_set() and host_attached and wsl_visible:
                stable_hits += 1
            else:
                stable_hits = 0
            if stable_hits >= 3:
                self._log(f"usbipd attach is stable for bus {current_busid}.")
                return
            time.sleep(2)
        raise WslFlashError(
            "usbipd attach did not stabilize before flashing. "
            "Check cable quality, Recovery mode, and USB passthrough."
        )

    def _pre_stage_archive(self):
        """Stage firmware archive to Windows temp before USB attach, so WSL network reset doesn't interrupt the copy."""
        archive = self.download_dir / self.firmware_info["filename"]
        if not archive.exists():
            return
        self._staged_archive = self._stage_archive_for_current_distro(archive)

    def _run_flash_in_wsl(self):
        archive = self.download_dir / self.firmware_info["filename"]
        if not archive.exists():
            raise WslFlashError(f"Firmware archive not found: {archive}. Download/Extract BSP first.")
        archive = getattr(self, "_staged_archive", None) or self._stage_archive_for_current_distro(archive)

        product_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.product).strip("_") or "jetson"
        version_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.l4t_version).strip("_") or "l4t"
        workspace = f"/root/seeed-jetson-firmware/{product_slug}-{version_slug}"

        # Check if the archive is already inside WSL (downloaded directly to WSL filesystem).
        # \\wsl$\<distro>\root\... maps to /root/... inside WSL.
        archive_str = str(archive.resolve())
        archive_in_wsl = archive_str.lower().startswith(f"\\\\wsl$\\{self.distro.lower()}\\")
        if archive_in_wsl:
            # Convert \\wsl$\<distro>\root\foo -> /root/foo
            wsl_relative = archive_str[len(f"\\\\wsl$\\{self.distro}\\"):]
            archive_wsl = "/" + wsl_relative.replace("\\", "/")
        else:
            archive_wsl = _windows_path_to_wsl(archive)

        foldername = self.firmware_info.get("foldername", "")
        expected_sha256 = (
            str(self.firmware_info.get("sha256") or "").strip().lower()
            if self.verify_archive_sha256
            else ""
        )
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
                f"EXPECTED_SHA256={shlex.quote(expected_sha256)}",
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
                'cd "$L4T_DIR"',
                'echo "[WSL] Flash command: ./tools/kernel_flash/l4t_initrd_flash.wsl.sh --flash-only --massflash 1 --network usb0 --showlogs"',
                'echo "[WSL] Starting l4t_initrd_flash.sh..."',
                "./tools/kernel_flash/l4t_initrd_flash.wsl.sh --flash-only --massflash 1 --network usb0 --showlogs",
            ]
        ) + "\n"
        self._run_wsl_stream(script)

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
            command = [
                _wsl_exe(),
                "-d",
                self.distro,
                "-u",
                "root",
                "--",
                "bash",
                _windows_path_to_wsl(temp_script),
            ]
            process = subprocess.Popen(
                command,
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
                if (
                    "might be timeout in usb write" in lowered
                    or ("tegrarcm_v2" in lowered and "return value 3" in lowered)
                ):
                    current_busid = self._current_attached_busid() or "unknown"
                    usbpcap = _usbpcap_status()
                    detail = (
                        " USBPcap is active on this Windows host and usbipd reports it as incompatible; "
                        "treat that as one host-side variable to test, alongside cable/port/Recovery-mode state."
                        if usbpcap
                        else " Check cable/port quality, avoid hubs, re-enter Recovery mode, then retry."
                    )
                    raise WslFlashError(
                        "Detected tegrarcm USB write timeout while sending APX boot data. "
                        "This is below the archive/extraction layer and means the APX USB write did not complete through WSL usbipd. "
                        "The tool is running fixed auto-attach plus dynamic APX attach; "
                        f"last tracked BUSID is {current_busid}."
                        f"{detail} Extraction is already cached."
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
