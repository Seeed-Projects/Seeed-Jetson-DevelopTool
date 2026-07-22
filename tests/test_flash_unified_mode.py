from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seeed_jetson_develop.flash import _native_flash_command, _uses_unified_flash
from seeed_jetson_develop.wsl_flash import WslFlashManager


def test_detects_thor_unified_flash_layout(tmp_path):
    workspace = tmp_path / "unified_flash" / "out" / "bsp_images" / "flash_workspace"
    workspace.mkdir(parents=True)

    assert _uses_unified_flash(tmp_path)


def test_does_not_treat_legacy_bootloader_layout_as_unified(tmp_path):
    (tmp_path / "bootloader").mkdir()

    assert not _uses_unified_flash(tmp_path)


def test_native_thor_command_enables_unified_flash():
    assert _native_flash_command(True)[:3] == ["sudo", "env", "UNIFIED_FLASH=1"]


def test_native_legacy_command_keeps_existing_flow():
    assert _native_flash_command(False)[0:2] == [
        "sudo",
        "./tools/kernel_flash/l4t_initrd_flash.sh",
    ]


def test_wsl_script_detects_and_enables_unified_flash(monkeypatch, tmp_path):
    archive = tmp_path / "firmware.tar.gz"
    archive.write_bytes(b"archive")
    manager = WslFlashManager(
        product="j601",
        l4t_version="38.4.0",
        firmware_info={
            "filename": archive.name,
            "foldername": "mfi_recomputer-thor-carrier-j6015",
        },
        download_dir=tmp_path,
    )
    manager.distro = "Ubuntu-20.04"
    manager._staged_archive = archive
    scripts = []

    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash._windows_path_to_wsl",
        lambda _path: "/mnt/c/firmware.tar.gz",
    )
    monkeypatch.setattr(manager, "_run_wsl_stream", scripts.append)

    manager._run_flash_in_wsl()

    assert len(scripts) == 1
    assert 'export UNIFIED_FLASH=1' in scripts[0]
    assert 'unified_flash/out/bsp_images/flash_workspace' in scripts[0]
