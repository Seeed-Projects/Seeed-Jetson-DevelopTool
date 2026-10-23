"""Small, deterministic task routes; resolve only named skills, never scan a tree."""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from .cli_tools import local_skills_dirs

PRESETS = ("ssh", "network", "camera", "arm_read", "arm", "radar", "free")
ICONS = {"ssh": "💻", "network": "🌐", "camera": "📷", "arm_read": "📊",
         "arm": "🦾", "radar": "📡", "free": "🧭"}
SKILL_ROUTES = {
    "ssh": ("developtool-device",),
    "network": ("developtool-device", "jetson-pc-wired-share"),
    "camera": ("developtool-device",),
    "arm_read": ("developtool-device", "soarm-control", "rebot-arm-grasp"),
    "arm": ("developtool-device", "soarm-control", "rebot-arm-grasp", "lerobot-env-setup"),
    "radar": ("developtool-device",),
    "free": ("developtool-device",),
}


def match_task(text: str) -> str:
    text = text.casefold()
    if any(word in text for word in ("机械臂", "robot arm", "soarm", "so-arm", "rebot", "抓取", "joint")):
        moving = ("控制", "移动", "抓取", "搬", "move", "pick", "grasp", "control")
        return "arm" if any(word in text for word in moving) else "arm_read"
    for task, words in (
        ("network", ("网络共享", "共享网络", "共享上网", "internet shar", "network shar", "nat", "wired-share")),
        ("camera", ("摄像头", "相机", "camera", "video", "csi", "rtsp")),
        ("radar", ("雷达", "传感器", "radar", "lidar", "imu", "sensor")),
        ("ssh", ("ssh", "连接设备", "连接jetson", "connect to")),
    ):
        if any(word in text for word in words):
            return task
    return "free"


def resolve_skills(agent: str, task: str) -> list[Path]:
    """An installed skill takes precedence over its bundled copy."""
    package_root = Path(__file__).resolve().parents[2] / "skills"
    roots = (*local_skills_dirs(agent), package_root / agent, package_root / "openclaw")
    found = []
    for slug in SKILL_ROUTES.get(task, SKILL_ROUTES["free"]):
        for root in roots:
            marker = next((root / slug / name for name in ("SKILL.md", "CLAUDE.md", "AGENTS.md")
                           if (root / slug / name).is_file()), None)
            if marker is not None:
                found.append(marker)
                break
    return found


def shell_command(parts: list[str]) -> str:
    return subprocess.list2cmdline(parts) if os.name == "nt" else shlex.join(parts)
