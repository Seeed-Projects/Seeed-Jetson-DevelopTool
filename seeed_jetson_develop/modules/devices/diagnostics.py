"""Diagnostics definitions for quick checks, peripheral checks, and device info."""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Callable
from seeed_jetson_develop.core.runner import Runner

# Match shell prompts from serial terminal output, e.g. seeed@seeed-desktop:~$
_PROMPT_RE = re.compile(r'\w[\w-]*@[\w-]+:[^\n]*?[#$]\s*')

def _strip_prompts(out: str) -> str:
    """Remove shell prompt fragments from serial command output."""
    return _PROMPT_RE.sub('', out).strip()


# reComputer model detection (parse Seeed Image Name from /etc/nv_tegra_release).

_PART_MAP: dict[str, str] = {
    'recomputer': 'reComputer', 'reserver': 'reServer',
    'agx': 'AGX', 'nx': 'NX', 'xavier': 'Xavier',
    'mini': 'Mini', 'super': 'Super',
    'industrial': 'Industrial', 'robo': 'Robotics',
    'gmsl': 'GMSL', 'devkit': 'DevKit',
}

def _extract_image_prefix(image_name: str) -> str:
    """Strip version/date suffix from image filename and return hardware prefix.

    mfi_recomputer-mini-agx-orin-32g-j501-6.2.1-36.4.-2026-02-11.tar.gz
    → mfi_recomputer-mini-agx-orin-32g-j501
    """
    name = re.sub(r'\.tar(\.gz)?$', '', image_name)
    parts = name.split('-')
    prefix_parts = []
    for part in parts:
        if re.match(r'^\d+\.\d+', part):   # version marker like 6.2.1 / 36.4
            break
        if re.match(r'^\d{4}$', part):     # year marker like 2026
            break
        prefix_parts.append(part)
    return '-'.join(prefix_parts)

def _format_product_name(prefix: str) -> str:
    """Format hardware prefix into readable product name.

    mfi_recomputer-mini-agx-orin-32g-j501 → reComputer J501 Mini AGX Orin 32G
    mfi_reserver-agx-orin-64g-j501        → reServer J501 AGX Orin 64G
    mfi_reserver-agx-orin-64g-j501-gmsl   → reServer J501 AGX Orin 64G GMSL
    """
    p = re.sub(r'^mfi_', '', prefix)
    parts = p.split('-')
    series = ''
    carrier = ''
    rest: list[str] = []
    for part in parts:
        lp = part.lower()
        if lp in ('recomputer', 'reserver'):
            series = _PART_MAP[lp]
        elif re.match(r'^j\d+[a-z]?$', lp):       # carrier board ID: j401 j501 j201 j30 j40
            carrier = part.upper()
        elif re.match(r'^\d+[gq]$', lp):           # memory size: 32g 16g 64g 16q
            rest.append(part.upper())
        else:
            rest.append(_PART_MAP.get(lp, part.capitalize()))
    out = [series]
    if carrier:
        out.append(carrier)
    out.extend(rest)
    return ' '.join(out)

def _identify_recomputer_model(nv_tegra_content: str) -> str | None:
    """Identify specific reComputer model from /etc/nv_tegra_release content."""
    m = re.search(r'Seeed Image Name\s+(\S+)', nv_tegra_content)
    if not m:
        return None
    image_name = m.group(1)
    prefix = _extract_image_prefix(image_name)
    if not prefix or not re.search(r're(computer|server)', prefix, re.I):
        return None
    return _format_product_name(prefix)


@dataclass
class DiagItem:
    id: str
    icon: str
    name: str
    cmd: str
    parse: Callable[[int, str], tuple[str, str]]  # -> (status_text, color_key)


# color_key: "ok" | "warn" | "error" | "info"

def _net(rc, out):
    return ("Normal", "ok") if rc == 0 else ("Unreachable", "error")

def _torch(rc, out):
    # _TORCH_PROBE_CMD prints a line like "CUDA @ <python>" or "CPU @ <python>" on success,
    # or "MISSING" on failure. Scan all output lines (not just the first) because over a
    # serial console the long for-loop command is line-wrapped and its echoed fragments
    # appear before the real output.
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("CUDA @"): return ("CUDA Available", "ok")
        if s.startswith("CPU @"):  return ("CPU Only", "warn")
    return ("Not Installed", "error")

def _docker(rc, out):
    return ("Running", "ok") if rc == 0 else ("Not Running", "error")
def _jtop(rc, out):
    return ("Installed", "ok") if rc == 0 and out.strip() else ("Not Installed", "warn")

def _camera(rc, out):
    devices = []
    seen = set()
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.fullmatch(r"/dev/video\d+", line) and line not in seen:
            seen.add(line)
            devices.append(line)
    if rc == 0 and devices:
        return (f"Found {len(devices)}", "ok")
    return ("Not Detected", "warn")

def _video_device_enum_cmd(*, usb_only: bool) -> str:
    usb_flag = "True" if usb_only else "False"
    return rf"""python3 - <<'PY'
import glob
import os
import struct
import sys

try:
    import fcntl
except Exception:
    sys.exit(1)

USB_ONLY = {usb_flag}
VIDIOC_QUERYCAP = 0x80685600
V4L2_CAP_VIDEO_CAPTURE = 0x00000001
V4L2_CAP_VIDEO_CAPTURE_MPLANE = 0x00001000
V4L2_CAP_DEVICE_CAPS = 0x80000000

def c_string(buf, start, end):
    return bytes(buf[start:end]).split(b'\0', 1)[0].decode(errors='ignore')

def query_caps(dev):
    with open(dev, 'rb', buffering=0) as f:
        buf = bytearray(104)
        fcntl.ioctl(f.fileno(), VIDIOC_QUERYCAP, buf, True)
    driver = c_string(buf, 0, 16)
    card = c_string(buf, 16, 48)
    bus_info = c_string(buf, 48, 80)
    capabilities = struct.unpack_from('I', buf, 84)[0]
    device_caps = struct.unpack_from('I', buf, 88)[0]
    caps = device_caps if (capabilities & V4L2_CAP_DEVICE_CAPS) else capabilities
    return driver, card, bus_info, caps

def is_capture_device(caps):
    return bool(caps & (V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_VIDEO_CAPTURE_MPLANE))

def sysfs_dir_for_dev(dev):
    return os.path.realpath(f"/sys/class/video4linux/{{os.path.basename(dev)}}")

def find_usb_root(path):
    cur = os.path.realpath(path)
    while cur and cur != "/" and cur != os.path.dirname(cur):
        if os.path.exists(os.path.join(cur, "idVendor")) and os.path.exists(os.path.join(cur, "idProduct")):
            return cur
        cur = os.path.dirname(cur)
    return ""

def is_usb_camera(dev, driver, bus_info):
    if driver == "uvcvideo" or bus_info.lower().startswith("usb-"):
        return True
    dev_path = os.path.join(sysfs_dir_for_dev(dev), "device")
    return bool(find_usb_root(dev_path))

def device_key(dev, driver, card, bus_info):
    usb_root = find_usb_root(os.path.join(sysfs_dir_for_dev(dev), "device"))
    if usb_root:
        return ("usb", usb_root)
    return ("capture", driver, card, bus_info or dev)

seen = set()
selected = []
for dev in sorted(glob.glob("/dev/video*")):
    try:
        driver, card, bus_info, caps = query_caps(dev)
    except OSError:
        continue
    if not is_capture_device(caps):
        continue
    if USB_ONLY and not is_usb_camera(dev, driver, bus_info):
        continue
    key = device_key(dev, driver, card, bus_info)
    if key in seen:
        continue
    seen.add(key)
    selected.append(dev)

for dev in selected:
    print(dev)
PY"""

def _disk(rc, out):
    if rc != 0 or not out.strip():
        return ("Check Failed", "error")
    line = out.strip().splitlines()[0]
    return (line[:40], "info")


# Scan likely python interpreters (system + miniforge/miniconda/anaconda/mambaforge envs + /opt/conda)
# and return on the first one that successfully imports torch. This is required because the
# bundled install dialog installs torch into a fresh conda env (e.g. ~/miniforge3/envs/torch-jp-310),
# not into /usr/bin/python3.
_PY_CANDIDATES_GLOB = (
    "/usr/bin/python3 /usr/local/bin/python3 "
    "$HOME/miniforge3/bin/python $HOME/miniforge3/envs/*/bin/python "
    "$HOME/miniconda3/bin/python $HOME/miniconda3/envs/*/bin/python "
    "$HOME/anaconda3/bin/python $HOME/anaconda3/envs/*/bin/python "
    "$HOME/mambaforge/bin/python $HOME/mambaforge/envs/*/bin/python "
    "/opt/conda/bin/python /opt/conda/envs/*/bin/python"
)


def python_module_check_cmd(probe_py: str) -> str:
    """Build a shell command that runs `probe_py` against each candidate python on the device.

    `probe_py` must be a single python expression that prints status on success and raises on failure.
    Returns the first interpreter's output (rc=0) or echoes MISSING (rc=1) when no interpreter passes.
    """
    quoted = shlex.quote(probe_py)
    return (
        f"for py in {_PY_CANDIDATES_GLOB}; do "
        '[ -x "$py" ] || continue; '
        f'out=$("$py" -c {quoted} 2>/dev/null) || continue; '
        'printf "%s @ %s\\n" "$out" "$py"; exit 0; '
        "done; echo MISSING; exit 1"
    )


_TORCH_PROBE_CMD = python_module_check_cmd(
    'import torch; print("CUDA" if torch.cuda.is_available() else "CPU")'
)


# Quick diagnostics.
DIAG_ITEMS: list[DiagItem] = [
    DiagItem("network", "🌐", "Network Connectivity",
             "ping -c 1 -W 2 8.8.8.8", _net),
    DiagItem("torch",   "⚡", "GPU / Torch",
             _TORCH_PROBE_CMD, _torch),
    DiagItem("docker",  "🐳", "Docker Service",
             "docker ps -q", _docker),
    DiagItem("jtop",    "📊", "jtop Monitor",
             "pip3 show jtop 2>/dev/null | grep -i name || python3 -m jtop --version 2>/dev/null || which jtop 2>/dev/null", _jtop),
    DiagItem("camera",  "📷", "USB Camera",
             _video_device_enum_cmd(usb_only=True), _camera),
    DiagItem("disk",    "💾", "Boot Disk",
             "lsblk -d -o NAME,SIZE,TYPE | grep disk | head -2", _disk),
]


# Peripheral checks.
def _periph_found(rc, out):
    return ("Detected", "ok") if rc == 0 and out.strip() else ("Not Detected", "warn")

def _bt(rc, out):
    if rc == 0 and out.strip():
        return ("Detected", "ok")
    return ("Not Detected", "warn")

def _hdmi(rc, out):
    if rc == 0 and "connected" in out.lower():
        return ("Connected", "ok")
    return ("Disconnected", "warn")

def _nvme(rc, out):
    if rc == 0 and out.strip():
        # Count only disk type lines, exclude partitions (e.g. nvme0n1p1).
        lines = [l for l in out.splitlines() if "nvme" in l.lower() and "disk" in l.lower()]
        return (f"Found {len(lines)}", "ok") if lines else ("Not Detected", "warn")
    return ("Not Detected", "warn")

PERIPH_ITEMS: list[DiagItem] = [
    DiagItem("usb_wifi",  "📡", "USB-WiFi",
             "iwconfig 2>/dev/null | grep -v 'no wireless'| grep ESSID", _periph_found),
    DiagItem("5g",        "📶", "5G Module",
             "lsusb 2>/dev/null | grep -iE 'quectel|sierra|huawei|modem|EC[0-9]|RM[0-9]'", _periph_found),
    DiagItem("bluetooth", "🔵", "Bluetooth",
             "hciconfig 2>/dev/null | grep 'BD Address'", _bt),
    DiagItem("nvme",      "💾", "NVMe SSD",
             "lsblk -d -o NAME,TYPE 2>/dev/null | grep nvme", _nvme),
    DiagItem("cam_dev",   "📷", "Camera",
             _video_device_enum_cmd(usb_only=False), _camera),
    DiagItem("hdmi",      "🖥",  "HDMI Display",
             "cat /sys/class/drm/card0*/status 2>/dev/null | head -1", _hdmi),
]


# Device base info.
INFO_CMDS: dict[str, str] = {
    "model": (
        r"""python3 -c "import pathlib;"""
        r"""p=['/proc/device-tree/model','/sys/firmware/devicetree/base/model'];"""
        r"""m=next((pathlib.Path(x).read_bytes().rstrip(b'\x00').decode(errors='replace').strip() for x in p if pathlib.Path(x).exists()),'Unknown');"""
        r"""print(m)" 2>/dev/null || cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || echo Unknown"""
    ),
    "l4t":     "head -1 /etc/nv_tegra_release 2>/dev/null | awk '{gsub(\",\",\"\",$5); print $2\".\"$5}'",
    "memory":  "free -h | awk 'NR==2{print $3\"/\"$2}'",
    "storage": "df -h / | awk 'NR==2{print $3\"/\"$2\" (\"$5\" used)\"}'",
    "ip":      "ip -4 -br addr show 2>/dev/null | awk '$1!=\"lo\" && $3~/^192\\./ {printf \"%s %s\\n\", $1, $3}' | sed 's|/[0-9]*||g'",
    "temp":    "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.1f°C\", $1/1000}'",
}


def run_all(runner: Runner, on_result: Callable[[str, str, str], None]):
    """Run all quick diagnostics and callback on_result(item_id, status_text, color_key)."""
    for item in DIAG_ITEMS:
        # torch probe scans multiple conda envs; allow a longer timeout than the rest
        timeout = 30 if item.id == "torch" else 10
        rc, out = runner.run(item.cmd, timeout=timeout)
        status, color = item.parse(rc, _strip_prompts(out))
        on_result(item.id, status, color)


def run_periph(runner: Runner, on_result: Callable[[str, str, str], None]):
    """Run all peripheral checks; callback signature is the same as run_all."""
    for item in PERIPH_ITEMS:
        rc, out = runner.run(item.cmd, timeout=8)
        status, color = item.parse(rc, _strip_prompts(out))
        on_result(item.id, status, color)


def collect_info(runner: Runner) -> dict[str, str]:
    """Collect device information and return key-to-value mapping."""
    result = {}
    for key, cmd in INFO_CMDS.items():
        rc, out = runner.run(cmd, timeout=5)
        val = _strip_prompts(out)
        result[key] = val if rc == 0 and val else "—"

    # Try identifying exact model from Seeed Image Name in /etc/nv_tegra_release.
    rc, out = runner.run("cat /etc/nv_tegra_release 2>/dev/null", timeout=5)
    if rc == 0:
        seeed_model = _identify_recomputer_model(_strip_prompts(out))
        if seeed_model:
            result['model'] = seeed_model

    return result
