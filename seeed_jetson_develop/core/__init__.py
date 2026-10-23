from __future__ import annotations

from typing import Any

__all__ = ["DeviceInfo", "Runner", "bus"]


def __getattr__(name: str) -> Any:
    if name == "bus":
        from .events import bus

        return bus
    if name == "Runner":
        from .runner import Runner

        return Runner
    if name == "DeviceInfo":
        from .device import DeviceInfo

        return DeviceInfo
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
