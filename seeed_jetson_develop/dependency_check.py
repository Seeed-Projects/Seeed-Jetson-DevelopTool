"""Runtime dependency checks and optional auto-install helpers.

This module is intentionally kept free of heavy third-party imports so that it
can run before PyQt5 is loaded and fix the environment when needed.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


# System apt packages commonly required by PyQt5's xcb platform plugin on
# Debian/Ubuntu.  These are not installable via pip, so we detect them and
# either install automatically (with sudo) or print the exact apt command.
_DEBIAN_SYSTEM_PACKAGES = [
    "libxcb-xinerama0",
    "libxkbcommon-x11-0",
    "libxcb-icccm4",
    "libxcb-image0",
    "libxcb-keysyms1",
    "libxcb-randr0",
    "libxcb-render-util0",
    "libxcb-xfixes0",
    "libxcb-shape0",
    "libxcb-xkb1",
    "libgl1-mesa-glx",
]

# Fallback core Python packages required to run the GUI / CLI.  We prefer to
# read the real list from pyproject.toml when it is available.
_CORE_PYTHON_PACKAGES = [
    "PyQt5",
    "requests",
    "tqdm",
    "click",
    "rich",
    "paramiko",
    "pyserial",
    "pyte",
    "anthropic",
]


def _get_project_python_requirements() -> list[str]:
    """Read dependency names from pyproject.toml, fall back to a hardcoded list."""
    tomllib = None
    if sys.version_info >= (3, 11):
        import tomllib  # type: ignore
    else:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            tomllib = None

    candidates = [
        Path(__file__).resolve().parent.parent / "pyproject.toml",
        Path(__file__).with_name("pyproject.toml"),
    ]
    if tomllib:
        for candidate in candidates:
            if candidate.exists():
                try:
                    with candidate.open("rb") as f:
                        data = tomllib.load(f)
                    deps = data.get("project", {}).get("dependencies", [])
                    if deps:
                        # "requests>=2.25.0" -> "requests"
                        return [re.split(r"[<>=!~;]", d)[0].strip() for d in deps]
                except Exception:
                    pass
    return _CORE_PYTHON_PACKAGES


def _python_package_installed(name: str) -> bool:
    """Check whether a Python distribution package is installed by its pip name."""
    try:
        from importlib.metadata import version, PackageNotFoundError
    except ImportError:  # pragma: no cover
        try:
            from importlib_metadata import version, PackageNotFoundError  # type: ignore
        except ImportError:
            # Fallback: try importing the module name as-is.
            try:
                __import__(name)
                return True
            except ImportError:
                return False

    try:
        version(name)
        return True
    except PackageNotFoundError:
        return False


def check_python_packages(packages: list[str] | None = None) -> list[str]:
    """Return the subset of *packages* that are not installed."""
    packages = packages or _get_project_python_requirements()
    return [p for p in packages if not _python_package_installed(p)]


def _is_frozen() -> bool:
    """Return True when running inside a PyInstaller / frozen executable."""
    return getattr(sys, "frozen", False) is True


def install_python_packages(packages: list[str]) -> bool:
    """Install the given Python packages with pip and return success."""
    if not packages:
        return True
    if _is_frozen():
        print(
            "[seeed-jetson-developer] 检测到当前为打包后的可执行文件，"
            "无法自动安装 Python 包。"
        )
        return False
    print(f"[seeed-jetson-developer] 正在安装缺失的 Python 包: {', '.join(packages)}")
    cmd = [sys.executable, "-m", "pip", "install", *packages]
    try:
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError:
        print(f"[seeed-jetson-developer] 安装失败，请手动执行:\n  {' '.join(cmd)}")
        return False
    except FileNotFoundError:
        print("[seeed-jetson-developer] 找不到 pip，请检查 Python 环境。")
        return False


def _has_apt() -> bool:
    """Return True if apt-get is available (Debian/Ubuntu)."""
    try:
        return subprocess.run(
            ["which", "apt-get"],
            capture_output=True,
            check=False,
        ).returncode == 0
    except Exception:
        return False


def _apt_package_installed(name: str) -> bool:
    """Return True if the named apt package is installed."""
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", name],
            capture_output=True,
            text=True,
            check=False,
        )
        return "install ok installed" in result.stdout
    except Exception:
        return False


def check_system_packages(packages: list[str] | None = None) -> list[str]:
    """Return missing system apt packages (Linux/Debian/Ubuntu only)."""
    if sys.platform != "linux" or not _has_apt():
        return []
    packages = packages or _DEBIAN_SYSTEM_PACKAGES
    return [p for p in packages if not _apt_package_installed(p)]


def install_system_packages(packages: list[str]) -> bool:
    """Install the given apt packages with sudo and return success."""
    if not packages:
        return True
    print(f"[seeed-jetson-developer] 正在安装缺失的系统依赖: {', '.join(packages)}")
    cmd = ["sudo", "apt-get", "update"]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        print("[seeed-jetson-developer] apt-get update 失败，继续尝试安装...")
    except FileNotFoundError:
        pass

    cmd = ["sudo", "apt-get", "install", "-y", *packages]
    try:
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError:
        print(f"[seeed-jetson-developer] 安装失败，请手动执行:\n  {' '.join(cmd)}")
        return False
    except FileNotFoundError:
        print("[seeed-jetson-developer] 找不到 apt-get，请手动安装系统依赖。")
        return False


def ensure_dependencies(
    auto_install_python: bool = True,
    auto_install_system: bool = False,
) -> None:
    """Check and optionally install dependencies before importing PyQt5.

    System dependencies are *not* installed by default because that requires
    ``sudo`` and would surprise users who installed from pip.  Set
    ``auto_install_system=True`` or the environment variable
    ``SEEED_AUTO_INSTALL_SYSTEM=1`` to opt-in.

    Raises SystemExit if required dependencies are missing and cannot be
    installed automatically.
    """
    if os.environ.get("SEEED_SKIP_DEPS_CHECK", "").lower() in {"1", "true", "yes"}:
        return

    if os.environ.get("SEEED_AUTO_INSTALL_SYSTEM", "").lower() in {"1", "true", "yes"}:
        auto_install_system = True

    if _is_frozen():
        auto_install_python = False

    missing_py = check_python_packages()
    if missing_py:
        if auto_install_python:
            if not install_python_packages(missing_py):
                sys.exit(1)
            # Re-check to make sure installation actually succeeded.
            still_missing = check_python_packages(missing_py)
            if still_missing:
                print(
                    "[seeed-jetson-developer] 以下包仍未安装: "
                    f"{', '.join(still_missing)}"
                )
                sys.exit(1)
        else:
            print(
                "[seeed-jetson-developer] 缺少 Python 包: "
                f"{', '.join(missing_py)}"
            )
            print(
                f"请执行: {sys.executable} -m pip install {' '.join(missing_py)}"
            )
            sys.exit(1)

    missing_sys = check_system_packages()
    if missing_sys:
        if auto_install_system:
            if not install_system_packages(missing_sys):
                sys.exit(1)
            # Re-check after installation.
            still_missing = check_system_packages(missing_sys)
            if still_missing:
                print(
                    "[seeed-jetson-developer] 以下系统依赖仍缺失: "
                    f"{', '.join(still_missing)}"
                )
                sys.exit(1)
        else:
            print(
                "[seeed-jetson-developer] 缺少系统依赖: "
                f"{', '.join(missing_sys)}"
            )
            print(
                f"请执行: sudo apt-get install -y {' '.join(missing_sys)}"
            )
            sys.exit(1)
