"""Core module exports.

Imports are intentionally lazy so non-GUI helpers such as config/i18n can be
tested without requiring PyQt5 to be installed in the current environment.
"""

__all__ = ["bus", "Runner", "DeviceInfo"]


def __getattr__(name):
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
