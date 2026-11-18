from __future__ import annotations

from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seeed_jetson_develop import dependency_check
from seeed_jetson_develop import flash as flash_mod

_EN_LOCALE = json.loads(
    (Path(__file__).resolve().parents[1]
     / "seeed_jetson_develop/locales/en/flash.json").read_text(encoding="utf-8")
)


def _fmt(key, **kwargs):
    """Render messages from the real English locale (also validates keys exist)."""
    return _EN_LOCALE.get(key, key).format(**kwargs)


def _force_linux(monkeypatch):
    monkeypatch.setattr(flash_mod, "_is_linux_host", lambda: True)


def test_deps_ok_when_nothing_missing(monkeypatch):
    _force_linux(monkeypatch)
    monkeypatch.setattr(dependency_check, "_has_apt", lambda: True)
    monkeypatch.setattr(dependency_check, "check_system_packages", lambda packages=None: [])
    assert flash_mod.ensure_linux_flash_host_deps() is True


def test_missing_deps_are_installed_automatically(monkeypatch):
    _force_linux(monkeypatch)
    monkeypatch.setattr(dependency_check, "_has_apt", lambda: True)

    state = {"installed": False}

    def fake_check(packages=None):
        if state["installed"]:
            return []
        return ["sshpass"]

    def fake_install(packages):
        assert "sshpass" in packages
        state["installed"] = True
        return True

    monkeypatch.setattr(dependency_check, "check_system_packages", fake_check)
    monkeypatch.setattr(dependency_check, "install_system_packages", fake_install)

    lines: list[str] = []
    assert flash_mod.ensure_linux_flash_host_deps(log=lines.append, fmt=_fmt) is True
    assert any("sshpass" in line for line in lines)


def test_install_failure_blocks_flash_with_manual_hint(monkeypatch):
    _force_linux(monkeypatch)
    monkeypatch.setattr(dependency_check, "_has_apt", lambda: True)
    monkeypatch.setattr(
        dependency_check, "check_system_packages", lambda packages=None: ["sshpass"]
    )
    monkeypatch.setattr(dependency_check, "install_system_packages", lambda packages: False)

    lines: list[str] = []
    assert flash_mod.ensure_linux_flash_host_deps(log=lines.append, fmt=_fmt) is False
    assert any("apt-get install" in line and "sshpass" in line for line in lines)


def test_non_apt_host_warns_but_continues(monkeypatch):
    _force_linux(monkeypatch)
    monkeypatch.setattr(dependency_check, "_has_apt", lambda: False)
    monkeypatch.setattr(flash_mod.shutil, "which", lambda name: None)

    lines: list[str] = []
    assert flash_mod.ensure_linux_flash_host_deps(log=lines.append, fmt=_fmt) is True
    assert any("sshpass" in line for line in lines)


def test_non_linux_host_is_noop(monkeypatch):
    monkeypatch.setattr(flash_mod, "_is_linux_host", lambda: False)
    assert flash_mod.ensure_linux_flash_host_deps() is True
