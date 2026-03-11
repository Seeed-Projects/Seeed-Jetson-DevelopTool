"""设备信息数据类"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeviceInfo:
    ip: str = ""
    hostname: str = ""
    model: str = ""          # e.g. "reComputer J4012"
    jetpack: str = ""        # e.g. "6.0"
    l4t: str = ""            # e.g. "36.3.0"
    connected: bool = False
    diagnostics: dict = field(default_factory=dict)
