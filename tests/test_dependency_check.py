"""Startup dependency bootstrap without touching apt or pip."""
from __future__ import annotations

import builtins
import subprocess
import sys

import pytest

from seeed_jetson_develop import dependency_check as deps


def test_requirements_keep_pyqt6_once() -> None:
    names = deps._get_project_python_requirements()
    assert "PyQt6" in names
    assert "qtpy" in names
    assert names.count("PyQt6") == 1


def test_python_package_check_imports_pyqt6(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        deps.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", ""),
    )

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "importlib.metadata" or name == "importlib_metadata":
            raise ImportError(name)
        if name == "PyQt6":
            return object()
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert deps._python_package_installed("PyQt6") is True


def test_pip_retries_break_system_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_run(cmd, capture_output=True, text=True, check=False):
        calls.append(cmd)
        if cmd[-2:] == ["pip", "--version"]:
            return subprocess.CompletedProcess(cmd, 0, "pip 24", "")
        if "--break-system-packages" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "ok", "")
        return subprocess.CompletedProcess(
            cmd,
            1,
            "",
            "error: externally-managed-environment",
        )

    monkeypatch.setattr(deps.subprocess, "run", fake_run)
    monkeypatch.setattr(deps, "_is_frozen", lambda: False)
    assert deps.install_python_packages(["PyQt6"]) is True
    assert any("--break-system-packages" in cmd for cmd in calls)
    assert calls[1][:4] == [sys.executable, "-m", "pip", "install"]


def test_linux_installs_system_packages_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def fake_check_system(packages=None):
        calls["n"] += 1
        return ["libxcb-cursor0"] if calls["n"] == 1 else []

    monkeypatch.setattr(deps, "check_python_packages", lambda packages=None: [])
    monkeypatch.setattr(deps, "check_system_packages", fake_check_system)
    installed = []
    monkeypatch.setattr(deps, "install_system_packages", lambda packages: installed.append(packages) or True)
    monkeypatch.setattr(deps, "_is_frozen", lambda: False)
    monkeypatch.setattr(deps.sys, "platform", "linux")
    monkeypatch.delenv("SEEED_AUTO_INSTALL_SYSTEM", raising=False)
    monkeypatch.delenv("SEEED_SKIP_DEPS_CHECK", raising=False)

    deps.ensure_dependencies()
    assert installed == [["libxcb-cursor0"]]


def test_system_auto_install_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(deps, "check_python_packages", lambda packages=None: [])
    monkeypatch.setattr(deps, "check_system_packages", lambda packages=None: ["xvfb"])
    monkeypatch.setenv("SEEED_AUTO_INSTALL_SYSTEM", "0")
    monkeypatch.delenv("SEEED_SKIP_DEPS_CHECK", raising=False)

    with pytest.raises(SystemExit):
        deps.ensure_dependencies()
    assert "sudo apt-get install -y xvfb" in capsys.readouterr().out


def test_legacy_gl_package_replaces_missing_libgl1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        deps,
        "_apt_package_known",
        lambda name: name == deps._LEGACY_GL_PACKAGE,
    )
    packages = deps._required_system_packages()
    assert "libgl1" not in packages
    assert deps._LEGACY_GL_PACKAGE in packages
