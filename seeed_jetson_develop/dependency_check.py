"""Runtime dependency checks and automatic install helpers.

This module is intentionally kept free of heavy third-party imports so that it
can run before qtpy is loaded and fix the environment when needed.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


# System apt packages commonly required by qtpy's xcb platform plugin on
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
    "libgl1",
    "libegl1",
    "libdbus-1-3",
    "libfontconfig1",
    "libx11-xcb1",
    "libxcb-cursor0",
    "libxcb-glx0",
    "libxcb-render0",
    "libxcb-shm0",
    "libxcb-sync1",
    "libxkbcommon0",
    "xvfb",
]

# Ubuntu renamed libgl1-mesa-glx to libgl1. Keep the old name only as a
# fallback for releases that still publish it.
_LEGACY_GL_PACKAGE = "libgl1-mesa-glx"

# Fallback core Python packages required to run the GUI / CLI.  We prefer to
# read the real list from pyproject.toml when it is available.
_CORE_PYTHON_PACKAGES = [
    "qtpy",
    "PyQt6",
    "requests",
    "tqdm",
    "click",
    "rich",
    "paramiko",
    "pyserial",
    "pyte",
    "anthropic",
]

# pip distribution name -> importable module. Most names match, but PyQt6 and
# pyserial do not.
_IMPORT_NAMES = {
    "pyqt6": "PyQt6",
    "pyserial": "serial",
}


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
                        names = [re.split(r"[<>=!~;]", d)[0].strip() for d in deps]
                        return list(dict.fromkeys(name for name in names if name))
                except Exception:
                    pass
    return _CORE_PYTHON_PACKAGES


def _import_name(package: str) -> str:
    return _IMPORT_NAMES.get(package.lower(), package)


def _python_package_installed(name: str) -> bool:
    """Check whether a Python distribution package is installed by its pip name.

    importlib.metadata is the fast path, but it can miss packages that were
    installed into the user site-packages directory while this process is
    already running (or when the environment has user-site quirks).  We fall
    back to ``pip show`` and finally to importing the module itself.
    """
    # Fast path: importlib.metadata
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            version(name)
            return True
        except PackageNotFoundError:
            pass
    except ImportError:  # pragma: no cover
        try:
            from importlib_metadata import version, PackageNotFoundError  # type: ignore
            try:
                version(name)
                return True
            except PackageNotFoundError:
                pass
        except ImportError:
            pass

    # Robust path: ask pip, which knows about --user installs and editable
    # installs that importlib.metadata sometimes cannot see.
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip().startswith("Name:"):
            return True
    except Exception:
        pass

    # Fallback: try importing the module name as-is.
    try:
        __import__(_import_name(name))
        return True
    except ImportError:
        return False


def check_python_packages(packages: list[str] | None = None) -> list[str]:
    """Return the subset of *packages* that are not installed."""
    packages = packages or _get_project_python_requirements()
    return [p for p in packages if not _python_package_installed(p)]


def _is_frozen() -> bool:
    """Return True when running inside a PyInstaller / frozen executable."""
    return getattr(sys, "frozen", False) is True


def _pip_available() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def _ensure_pip() -> bool:
    """Make sure the current interpreter can run ``python -m pip``."""
    if _pip_available():
        return True
    if _is_frozen():
        return False

    print("[seeed-jetson-developer] 当前 Python 没有 pip，正在尝试安装...")
    try:
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
    except Exception:
        pass
    if _pip_available():
        return True

    if sys.platform == "linux" and _has_apt():
        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        candidates = [f"python{version}-pip", "python3-pip"]
        print(
            "[seeed-jetson-developer] 正在安装系统 pip: "
            + ", ".join(candidates)
        )
        if install_system_packages(candidates):
            return _pip_available()
    print("[seeed-jetson-developer] 找不到 pip，请检查 Python 环境。")
    return False


def _pip_install_command(
    packages: list[str],
    *,
    user: bool = False,
    break_system: bool = False,
) -> list[str]:
    cmd = [sys.executable, "-m", "pip", "install"]
    if user:
        cmd.append("--user")
    if break_system:
        cmd.append("--break-system-packages")
    cmd.extend(packages)
    return cmd


def _is_externally_managed_error(output: str) -> bool:
    text = output.lower()
    return "externally-managed-environment" in text or "externally managed" in text


def install_python_packages(packages: list[str]) -> bool:
    """Install the given Python packages with pip and return success.

    Ubuntu's system Python may refuse a plain pip install. Retry with
    ``--user`` and, when PEP 668 blocks that too, ``--break-system-packages``.
    """
    if not packages:
        return True
    if _is_frozen():
        print(
            "[seeed-jetson-developer] 检测到当前为打包后的可执行文件，"
            "无法自动安装 Python 包。"
        )
        return False
    if not _ensure_pip():
        return False
    print(f"[seeed-jetson-developer] 正在安装缺失的 Python 包: {', '.join(packages)}")

    attempts = [
        _pip_install_command(packages),
        _pip_install_command(packages, user=True),
        _pip_install_command(packages, break_system=True),
        _pip_install_command(packages, user=True, break_system=True),
    ]
    last_output = ""
    last_cmd = attempts[0]
    saw_managed = False
    for index, cmd in enumerate(attempts):
        if index and not saw_managed:
            break
        last_cmd = cmd
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            print("[seeed-jetson-developer] 找不到 pip，请检查 Python 环境。")
            return False
        last_output = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0:
            return True
        saw_managed = _is_externally_managed_error(last_output)
        if not saw_managed:
            break

    print(f"[seeed-jetson-developer] 安装失败，请手动执行:\n  {' '.join(last_cmd)}")
    if last_output.strip():
        print(last_output.strip()[-800:])
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


def _apt_package_known(name: str) -> bool:
    try:
        result = subprocess.run(
            ["apt-cache", "show", name],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def _required_system_packages() -> list[str]:
    packages = list(_DEBIAN_SYSTEM_PACKAGES)
    if not _apt_package_known("libgl1") and _apt_package_known(_LEGACY_GL_PACKAGE):
        packages = [
            _LEGACY_GL_PACKAGE if name == "libgl1" else name for name in packages
        ]
    return list(dict.fromkeys(packages))


def check_system_packages(packages: list[str] | None = None) -> list[str]:
    """Return missing system apt packages (Linux/Debian/Ubuntu only)."""
    if sys.platform != "linux" or not _has_apt():
        return []
    packages = list(dict.fromkeys(packages or _required_system_packages()))
    return [p for p in packages if not _apt_package_installed(p)]


def install_system_packages(packages: list[str]) -> bool:
    """Install the given apt packages with sudo and return success."""
    if not packages:
        return True
    packages = list(dict.fromkeys(packages))
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
    auto_install_system: bool | None = None,
) -> None:
    """Check and install dependencies before importing qtpy.

    On Linux the GUI also needs apt packages such as the Qt xcb libraries.
    Those are installed automatically because a fresh Ubuntu install otherwise
    exits before the window can open. Set ``SEEED_AUTO_INSTALL_SYSTEM=0`` to
    print the apt command instead.

    Raises SystemExit if required dependencies are missing and cannot be
    installed automatically.
    """
    if os.environ.get("SEEED_SKIP_DEPS_CHECK", "").lower() in {"1", "true", "yes"}:
        return

    env_system = os.environ.get("SEEED_AUTO_INSTALL_SYSTEM", "").strip().lower()
    if auto_install_system is None:
        if env_system in {"0", "false", "no", "off"}:
            auto_install_system = False
        elif env_system in {"1", "true", "yes", "on"}:
            auto_install_system = True
        else:
            auto_install_system = sys.platform == "linux"
    elif env_system in {"0", "false", "no", "off"}:
        auto_install_system = False
    elif env_system in {"1", "true", "yes", "on"}:
        auto_install_system = True

    if _is_frozen():
        auto_install_python = False

    missing_py = check_python_packages()
    if missing_py:
        if auto_install_python:
            if not install_python_packages(missing_py):
                sys.exit(1)
            import importlib
            importlib.invalidate_caches()
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
