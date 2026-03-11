"""运行环境检测 — 判断是否在 Jetson 设备本地运行"""
import os
import platform


def is_jetson() -> bool:
    """
    检测当前是否运行在 NVIDIA Jetson 设备上。
    判断依据：Linux + aarch64 架构 + Tegra 特有文件。
    """
    if platform.system() != "Linux":
        return False
    if platform.machine() not in ("aarch64", "armv8l"):
        return False
    # Tegra release 标志文件
    if os.path.exists("/etc/nv_tegra_release"):
        return True
    # 设备树 model 文件
    model_file = "/proc/device-tree/model"
    if os.path.exists(model_file):
        try:
            with open(model_file, "rb") as f:
                model = f.read().decode("utf-8", errors="ignore").lower()
                return "jetson" in model or "tegra" in model
        except Exception:
            pass
    return False
