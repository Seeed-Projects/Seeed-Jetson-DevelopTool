"""诊断项定义 — 快速诊断 / 外设检测 / 设备信息"""
import re
from dataclasses import dataclass
from typing import Callable
from seeed_jetson_develop.core.runner import Runner

# 匹配串口终端的 shell prompt，如 seeed@seeed-desktop:~$
_PROMPT_RE = re.compile(r'\w[\w-]*@[\w-]+:[^\n]*?[#$]\s*')

def _strip_prompts(out: str) -> str:
    """去除串口输出中的 shell prompt 行。"""
    return _PROMPT_RE.sub('', out).strip()


# ── reComputer 型号识别（解析 /etc/nv_tegra_release 中的 Seeed Image Name）──

_PART_MAP: dict[str, str] = {
    'recomputer': 'reComputer', 'reserver': 'reServer',
    'agx': 'AGX', 'nx': 'NX', 'xavier': 'Xavier',
    'mini': 'Mini', 'super': 'Super',
    'industrial': 'Industrial', 'robo': 'Robotics',
    'gmsl': 'GMSL', 'devkit': 'DevKit',
}

def _extract_image_prefix(image_name: str) -> str:
    """从镜像文件名中剥离版本/日期后缀，返回硬件标识前缀。

    mfi_recomputer-mini-agx-orin-32g-j501-6.2.1-36.4.-2026-02-11.tar.gz
    → mfi_recomputer-mini-agx-orin-32g-j501
    """
    name = re.sub(r'\.tar(\.gz)?$', '', image_name)
    parts = name.split('-')
    prefix_parts = []
    for part in parts:
        if re.match(r'^\d+\.\d+', part):   # 版本号如 6.2.1 / 36.4
            break
        if re.match(r'^\d{4}$', part):     # 年份如 2026
            break
        prefix_parts.append(part)
    return '-'.join(prefix_parts)

def _format_product_name(prefix: str) -> str:
    """将硬件前缀格式化为可读型号名。

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
        elif re.match(r'^j\d+[a-z]?$', lp):       # 载板号：j401 j501 j201 j30 j40
            carrier = part.upper()
        elif re.match(r'^\d+[gq]$', lp):            # 内存容量：32g 16g 64g 16q
            rest.append(part.upper())
        else:
            rest.append(_PART_MAP.get(lp, part.capitalize()))
    out = [series]
    if carrier:
        out.append(carrier)
    out.extend(rest)
    return ' '.join(out)

def _identify_recomputer_model(nv_tegra_content: str) -> str | None:
    """从 /etc/nv_tegra_release 内容识别具体 reComputer 型号。"""
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
    return ("正常", "ok") if rc == 0 else ("无法连接", "error")

def _torch(rc, out):
    if rc == 0 and "True" in out:  return ("CUDA 可用", "ok")
    if rc == 0:                    return ("CPU 模式", "warn")
    return ("未安装", "error")

def _docker(rc, out):
    return ("运行中", "ok") if rc == 0 else ("未运行", "error")
def _jtop(rc, out):
    return ("已安装", "ok") if rc == 0 and out.strip() else ("未安装", "warn")

def _camera(rc, out):
    devices = [l for l in out.splitlines() if l.strip()]
    if rc == 0 and devices:
        return (f"已检测到 {len(devices)} 个", "ok")
    return ("未检测到", "warn")

def _disk(rc, out):
    if rc != 0 or not out.strip():
        return ("检测失败", "error")
    line = out.strip().splitlines()[0]
    return (line[:40], "info")


# ── 快速诊断项 ──────────────────────────────────────────────────────────────
DIAG_ITEMS: list[DiagItem] = [
    DiagItem("network", "🌐", "网络连接",
             "ping -c 1 -W 2 8.8.8.8", _net),
    DiagItem("torch",   "⚡", "GPU / Torch",
             "python3 -c 'import torch; print(torch.cuda.is_available())'", _torch),
    DiagItem("docker",  "🐳", "Docker 服务",
             "docker ps -q", _docker),
    DiagItem("jtop",    "📊", "jtop 监控",
             "pip3 show jtop 2>/dev/null | grep -i name || python3 -m jtop --version 2>/dev/null || which jtop 2>/dev/null", _jtop),
    DiagItem("camera",  "📷", "USB 摄像头",
             "ls /dev/video* 2>/dev/null", _camera),
    DiagItem("disk",    "💾", "启动磁盘",
             "lsblk -d -o NAME,SIZE,TYPE | grep disk | head -2", _disk),
]


# ── 外设检测项 ──────────────────────────────────────────────────────────────
def _periph_found(rc, out):
    return ("已检测到", "ok") if rc == 0 and out.strip() else ("未检测到", "warn")

def _bt(rc, out):
    if rc == 0 and out.strip():
        return ("已检测到", "ok")
    return ("未检测到", "warn")

def _hdmi(rc, out):
    if rc == 0 and "connected" in out.lower():
        return ("已连接", "ok")
    return ("未连接", "warn")

def _nvme(rc, out):
    if rc == 0 and out.strip():
        # 只统计 disk 类型，过滤掉分区（nvme0n1p1 等）
        lines = [l for l in out.splitlines() if "nvme" in l.lower() and "disk" in l.lower()]
        return (f"已检测到 {len(lines)} 个", "ok") if lines else ("未检测到", "warn")
    return ("未检测到", "warn")

PERIPH_ITEMS: list[DiagItem] = [
    DiagItem("usb_wifi",  "📡", "USB-WiFi",
             "iwconfig 2>/dev/null | grep -v 'no wireless'| grep ESSID", _periph_found),
    DiagItem("5g",        "📶", "5G 模组",
             "lsusb 2>/dev/null | grep -iE 'quectel|sierra|huawei|modem|EC[0-9]|RM[0-9]'", _periph_found),
    DiagItem("bluetooth", "🔵", "蓝牙",
             "hciconfig 2>/dev/null | grep 'BD Address'", _bt),
    DiagItem("nvme",      "💾", "NVMe SSD",
             "lsblk -d -o NAME,TYPE 2>/dev/null | grep nvme", _nvme),
    DiagItem("cam_dev",   "📷", "摄像头",
             "ls /dev/video* 2>/dev/null", _camera),
    DiagItem("hdmi",      "🖥",  "HDMI 显示",
             "cat /sys/class/drm/card0*/status 2>/dev/null | head -1", _hdmi),
]


# ── 设备基本信息 ────────────────────────────────────────────────────────────
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
    "ip":      "hostname -I 2>/dev/null | awk '{print $1}'",
    "temp":    "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.1f°C\", $1/1000}'",
}


def run_all(runner: Runner, on_result: Callable[[str, str, str], None]):
    """逐项执行快速诊断，每项完成后回调 on_result(item_id, status_text, color_key)。"""
    for item in DIAG_ITEMS:
        rc, out = runner.run(item.cmd, timeout=10)
        status, color = item.parse(rc, _strip_prompts(out))
        on_result(item.id, status, color)


def run_periph(runner: Runner, on_result: Callable[[str, str, str], None]):
    """逐项执行外设检测，回调同 run_all。"""
    for item in PERIPH_ITEMS:
        rc, out = runner.run(item.cmd, timeout=8)
        status, color = item.parse(rc, _strip_prompts(out))
        on_result(item.id, status, color)


def collect_info(runner: Runner) -> dict[str, str]:
    """采集设备基本信息，返回 key→value 字典。"""
    result = {}
    for key, cmd in INFO_CMDS.items():
        rc, out = runner.run(cmd, timeout=5)
        val = _strip_prompts(out)
        result[key] = val if rc == 0 and val else "—"

    # 尝试从 /etc/nv_tegra_release 的 Seeed Image Name 识别具体型号
    rc, out = runner.run("cat /etc/nv_tegra_release 2>/dev/null", timeout=5)
    if rc == 0:
        seeed_model = _identify_recomputer_model(_strip_prompts(out))
        if seeed_model:
            result['model'] = seeed_model

    return result
