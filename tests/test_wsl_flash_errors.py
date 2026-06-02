from __future__ import annotations

from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seeed_jetson_develop.wsl_flash import (
    _decode_output,
    _looks_like_nfs_mount_failure,
    WslFlashError,
    WslFlashManager,
    _wsl_status_summary,
    ensure_usbipd_ready,
)


def test_detects_nfs_mount_failure_message():
    text = """
Flash failure
Either the device cannot mount the NFS server on the host or a flash command has failed.
Check your network setting (VPN, firewall,...) to make sure the device can mount NFS server.
Debug log saved to /tmp/tmp.VkmeOeTpMp.
Cleaning up...
"""
    assert _looks_like_nfs_mount_failure(text)


def test_does_not_confuse_boot_timeout_with_nfs_failure():
    text = """
Waiting for target to boot-up...
Waiting for target to boot-up...
"""
    assert not _looks_like_nfs_mount_failure(text)


def test_decode_output_prefers_utf16le_for_wsl_output():
    text = "默认版本: 2\r\n默认分发版: Ubuntu-20.04\r\n"
    assert _decode_output(text.encode("utf-16le")) == text


def test_decode_output_keeps_ascii_wsl_distro_names_from_utf16le():
    text = "Ubuntu-20.04\r\nUbuntu-22.04\r\n"
    assert _decode_output(text.encode("utf-16le")) == text


def test_usbipd_timeout_recovers_after_service_restart(monkeypatch):
    calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_usbipd_exe():
        return r"C:\Program Files\usbipd-win\usbipd.exe"

    def fake_run_capture(args, timeout=60):
        calls.append(("run", tuple(args)))
        if args[-1] == "--version" and sum(1 for kind, cmd in calls if kind == "run" and cmd[-1] == "--version") == 1:
            raise subprocess.TimeoutExpired(args, timeout)
        return subprocess.CompletedProcess(args, 0, stdout=b"5.0.0")

    def fake_run_elevated(program, args, timeout=None):
        calls.append(("elevated", (program, *args)))
        return 0

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._usbipd_exe", fake_usbipd_exe)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_capture", fake_run_capture)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated", fake_run_elevated)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._usbipd_service_status", lambda: "RUNNING")
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._usbpcap_status", lambda: None)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash.time.sleep", lambda _: None)

    assert ensure_usbipd_ready() == r"C:\Program Files\usbipd-win\usbipd.exe"
    assert ("elevated", ("sc.exe", "stop", "usbipd")) in calls
    assert ("elevated", ("sc.exe", "start", "usbipd")) in calls


def test_usbipd_timeout_raises_when_recovery_fails(monkeypatch):
    def fake_usbipd_exe():
        return r"C:\Program Files\usbipd-win\usbipd.exe"

    def fake_run_capture(args, timeout=60):
        if args[-1] == "--version":
            raise subprocess.TimeoutExpired(args, timeout)
        return subprocess.CompletedProcess(args, 0, stdout=b"")

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._usbipd_exe", fake_usbipd_exe)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_capture", fake_run_capture)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated", lambda *args, **kwargs: 1)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._usbipd_service_status", lambda: "STOPPED")
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._usbpcap_status", lambda: None)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash.time.sleep", lambda _: None)

    try:
        ensure_usbipd_ready()
        assert False, "expected WslFlashError"
    except WslFlashError as exc:
        assert "could not restart the usbipd service automatically" in str(exc)


def test_attempt_wsl_first_run_recovery_succeeds_after_shutdown(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    manager.distro = "Ubuntu-20.04"
    calls: list[tuple[str, ...]] = []
    attempts = {"warmup": 0}

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._wsl_exe", lambda: r"C:\Windows\System32\wsl.exe")
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash.time.sleep", lambda _: None)

    def fake_run_wsl_host(args, timeout=60):
        calls.append(tuple(args))
        if args == ["--shutdown"]:
            return subprocess.CompletedProcess(args, 0, stdout=b"")
        attempts["warmup"] += 1
        if attempts["warmup"] == 1:
            raise subprocess.TimeoutExpired(args, timeout)
        return subprocess.CompletedProcess(args, 0, stdout=b"")

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_wsl_host", fake_run_wsl_host)

    assert manager._attempt_wsl_first_run_recovery() is True
    assert ("--shutdown",) in calls


def test_attempt_wsl_first_run_recovery_returns_false_when_all_retries_fail(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    manager.distro = "Ubuntu-20.04"

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._wsl_exe", lambda: r"C:\Windows\System32\wsl.exe")
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash.time.sleep", lambda _: None)

    def fake_run_wsl_host(args, timeout=60):
        if args == ["--shutdown"]:
            return subprocess.CompletedProcess(args, 0, stdout=b"")
        return subprocess.CompletedProcess(args, 1, stdout=b"setup pending")

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_wsl_host", fake_run_wsl_host)

    assert manager._attempt_wsl_first_run_recovery() is False


def test_wsl_status_summary_decodes_utf16_outputs(monkeypatch):
    def fake_run_capture(args, timeout=60):
        if "--status" in args:
            text = "Default Distribution: Ubuntu-20.04\r\nDefault Version: 2\r\n"
        else:
            text = "  NAME            STATE   VERSION\r\n* Ubuntu-20.04    Stopped 2\r\n"
        return subprocess.CompletedProcess(args, 0, stdout=text.encode("utf-16le"))

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._wsl_exe", lambda: r"C:\Windows\System32\wsl.exe")
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_capture", fake_run_capture)

    summary = _wsl_status_summary()
    assert any("status: Default Distribution: Ubuntu-20.04" in line for line in summary)
    assert any("distros: * Ubuntu-20.04    Stopped 2" in line for line in summary)


def test_read_wsl_release_version_uses_posix_compatible_os_release_source(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    calls: list[list[str]] = []

    def fake_run_wsl_host(args, timeout=60):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=b"22.04")

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_wsl_host", fake_run_wsl_host)

    assert manager._read_wsl_release_version("Ubuntu") == "22.04"
    assert calls
    assert calls[0][-1] == ". /etc/os-release 2>/dev/null && printf '%s' \"$VERSION_ID\""


def test_wait_for_wsl_ready_recovers_after_restart(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    attempts = {"count": 0}

    def fake_run_wsl(args, timeout=None):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise subprocess.TimeoutExpired(args, timeout or 60)
        return subprocess.CompletedProcess(args, 0, stdout=b"SEEED_WSL_READY\n")

    monkeypatch.setattr(manager, "_run_wsl", fake_run_wsl)
    monkeypatch.setattr(manager, "_restart_unresponsive_wsl_distro", lambda: True)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash.time.sleep", lambda _: None)

    assert manager._wait_for_wsl_ready(timeout=30) is True
    assert attempts["count"] == 2


def test_ensure_wsl_retries_after_first_run_recovery(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    wait_calls: list[int] = []

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._wsl_exe", lambda: r"C:\Windows\System32\wsl.exe")
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash.subprocess.run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=b""))
    monkeypatch.setattr(manager, "_wsl_distros", lambda: {"Ubuntu-20.04"})
    monkeypatch.setattr(manager, "_attempt_wsl_first_run_recovery", lambda: True)

    def fake_wait(timeout):
        wait_calls.append(timeout)
        return len(wait_calls) == 2

    monkeypatch.setattr(manager, "_wait_for_wsl_ready", fake_wait)

    manager._ensure_wsl()
    assert wait_calls == [180, 90]


def test_ensure_wsl_reuses_generic_ubuntu_when_version_matches(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._wsl_exe", lambda: r"C:\Windows\System32\wsl.exe")
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash._run_capture",
        lambda args, timeout=60: subprocess.CompletedProcess(args, 0, stdout=b""),
    )
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=b""),
    )
    monkeypatch.setattr(manager, "_wsl_distros", lambda: {"Ubuntu"})
    monkeypatch.setattr(manager, "_read_wsl_release_version", lambda distro: "22.04")
    monkeypatch.setattr(manager, "_wait_for_wsl_ready", lambda timeout: True)

    manager._ensure_wsl()

    assert manager.distro == "Ubuntu"


def test_preferred_wsl_distros_for_l4t_35_accepts_20_and_18():
    from seeed_jetson_develop.wsl_flash import _preferred_wsl_distros_for_l4t

    assert _preferred_wsl_distros_for_l4t("35.3") == ["Ubuntu-20.04", "Ubuntu-18.04"]


def test_match_existing_distro_for_l4t_35_reuses_generic_ubuntu_20(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="35.3",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )

    monkeypatch.setattr(manager, "_read_wsl_release_version", lambda distro: "20.04")

    assert manager._match_existing_distro({"Ubuntu"}) == "Ubuntu"


def test_match_existing_distro_for_l4t_35_rejects_generic_ubuntu_22(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="35.3",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )

    monkeypatch.setattr(manager, "_read_wsl_release_version", lambda distro: "22.04")

    assert manager._match_existing_distro({"Ubuntu"}) is None


def test_match_existing_distro_accepts_generic_ubuntu_when_any_preferred_version_matches(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )

    monkeypatch.setattr(manager, "_read_wsl_release_version", lambda distro: "22.04")

    assert manager._match_existing_distro({"Ubuntu"}) == "Ubuntu"


def test_ensure_wsl_does_not_reuse_generic_ubuntu_when_version_mismatches(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    calls: list[tuple[str, tuple[str, ...]]] = []

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._wsl_exe", lambda: r"C:\Windows\System32\wsl.exe")
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash._run_capture",
        lambda args, timeout=60: subprocess.CompletedProcess(args, 0, stdout=b""),
    )
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=b""),
    )
    monkeypatch.setattr(manager, "_wsl_distros", lambda: {"Ubuntu"})
    monkeypatch.setattr(manager, "_read_wsl_release_version", lambda distro: "24.04")
    monkeypatch.setattr(manager, "_wait_for_distro_registration", lambda timeout: {"Ubuntu-20.04"})
    monkeypatch.setattr(manager, "_wait_for_wsl_ready", lambda timeout: True)

    def fake_run_elevated(program, args, timeout=None):
        calls.append((program, tuple(args)))
        return 0

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated", fake_run_elevated)
    monkeypatch.setattr(manager, "_install_wsl_distro_web_download", lambda wsl: False)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_file", lambda wsl: False)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_rootfs", lambda wsl: False)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_appx", lambda: False)

    manager._ensure_wsl()

    assert manager.distro == "Ubuntu-20.04"
    assert ("C:\\Windows\\System32\\wsl.exe", ("--install", "-d", "Ubuntu-20.04")) in calls


def test_wsl_status_summary_reports_timeouts(monkeypatch):
    def fake_run_capture(args, timeout=60):
        raise subprocess.TimeoutExpired(args, timeout)

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._wsl_exe", lambda: r"C:\Windows\System32\wsl.exe")
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_capture", fake_run_capture)

    summary = _wsl_status_summary()
    assert "status: timeout after 15s" in summary
    assert "distros: timeout after 20s" in summary


def test_ensure_wsl_raises_with_install_diag_when_registration_never_appears(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    logs: list[str] = []

    monkeypatch.setattr(manager, "_log", logs.append)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._wsl_exe", lambda: r"C:\Windows\System32\wsl.exe")
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash._run_capture",
        lambda args, timeout=60: subprocess.CompletedProcess(args, 0, stdout=b""),
    )
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=b""),
    )
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated", lambda *args, **kwargs: 4294967295)
    monkeypatch.setattr(manager, "_wsl_distros", lambda: set())
    monkeypatch.setattr(manager, "_wait_for_distro_registration", lambda timeout: set())
    monkeypatch.setattr(manager, "_install_wsl_distro_web_download", lambda wsl: False)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_file", lambda wsl: False)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_rootfs", lambda wsl: False)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_appx", lambda: False)
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash._wsl_status_summary",
        lambda wsl=None: ["status: timeout after 15s", "distros: timeout after 20s"],
    )

    try:
        manager._ensure_wsl()
        assert False, "expected WslFlashError"
    except WslFlashError as exc:
        assert "Failed to install Ubuntu-20.04 (exit 4294967295)." in str(exc)

    assert any("Installer returned 4294967295 (-1)." in line for line in logs)
    assert any("[WSL diag] status: timeout after 15s" == line for line in logs)


def test_usbipd_timeout_reports_policy_block_when_restart_denied(monkeypatch):
    def fake_usbipd_exe():
        return r"C:\Program Files\usbipd-win\usbipd.exe"

    def fake_run_capture(args, timeout=60):
        if args[-1] == "--version":
            raise subprocess.TimeoutExpired(args, timeout)
        return subprocess.CompletedProcess(args, 0, stdout=b"")

    elevated_calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_run_elevated(program, args, timeout=None):
        elevated_calls.append((program, tuple(args)))
        return 5

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._usbipd_exe", fake_usbipd_exe)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_capture", fake_run_capture)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated", fake_run_elevated)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._usbipd_service_status", lambda: "ACCESS DENIED")
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._usbpcap_status", lambda: None)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash.time.sleep", lambda _: None)

    try:
        ensure_usbipd_ready()
        assert False, "expected WslFlashError"
    except WslFlashError as exc:
        assert "Administrator policy or endpoint security may be blocking service control." in str(exc)

    assert ("sc.exe", ("stop", "usbipd")) in elevated_calls


def test_usbipd_install_waits_for_executable_visibility(monkeypatch):
    state = {"calls": 0}

    def fake_usbipd_exe():
        state["calls"] += 1
        if state["calls"] < 3:
            return None
        return r"C:\Program Files\usbipd-win\usbipd.exe"

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._usbipd_exe", fake_usbipd_exe)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash.shutil.which", lambda name: "winget" if name == "winget" else None)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated", lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash._run_capture",
        lambda args, timeout=60: subprocess.CompletedProcess(args, 0, stdout=b"5.0.0"),
    )
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash.time.sleep", lambda _: None)

    assert ensure_usbipd_ready() == r"C:\Program Files\usbipd-win\usbipd.exe"
    assert state["calls"] >= 3


def test_ensure_wsl_surfaces_virtualization_prereq_hint(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    logs: list[str] = []

    monkeypatch.setattr(manager, "_log", logs.append)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._wsl_exe", lambda: r"C:\Windows\System32\wsl.exe")
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash._run_capture",
        lambda args, timeout=60: subprocess.CompletedProcess(args, 0, stdout=b""),
    )
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=b""),
    )
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated", lambda *args, **kwargs: 4294967295)
    monkeypatch.setattr(manager, "_wsl_distros", lambda: set())
    monkeypatch.setattr(manager, "_wait_for_distro_registration", lambda timeout: set())
    monkeypatch.setattr(manager, "_install_wsl_distro_web_download", lambda wsl: False)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_file", lambda wsl: False)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_rootfs", lambda wsl: False)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_appx", lambda: False)
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash._wsl_status_summary",
        lambda wsl=None: ["status: timeout after 15s", "distros: timeout after 20s"],
    )
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash._wsl_install_failure_hint",
        lambda: "WSL2 prerequisites look incomplete: enable the Windows 'Virtual Machine Platform' feature; turn on CPU virtualization in BIOS/UEFI.",
    )

    try:
        manager._ensure_wsl()
        assert False, "expected WslFlashError"
    except WslFlashError as exc:
        assert "Virtual Machine Platform" in str(exc)
        assert "BIOS/UEFI" in str(exc)

    assert any("WSL2 prerequisites look incomplete" in line for line in logs)


def test_ensure_wsl_updates_legacy_wsl_cli_help_output(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    calls: list[tuple[str, tuple[str, ...]]] = []
    state = {"modern": False}

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._wsl_exe", lambda: r"C:\Windows\System32\wsl.exe")

    def fake_run_capture(args, timeout=60):
        if args[-2:] == ["-l", "-q"]:
            if not state["modern"]:
                text = "用法：wsl.exe [参数]\n    --install <选项>\n    --list, -l [选项]\n"
                return subprocess.CompletedProcess(args, 0, stdout=text.encode("utf-8"))
            return subprocess.CompletedProcess(args, 0, stdout=b"Ubuntu-20.04\n")
        if "-d" in args:
            return subprocess.CompletedProcess(args, 0, stdout=b"SEEED_WSL_READY\n")
        return subprocess.CompletedProcess(args, 0, stdout=b"")

    def fake_run_elevated(program, args, timeout=None):
        calls.append((program, tuple(args)))
        if "--web-download" in args and "--no-distribution" in args:
            state["modern"] = True
        return 0

    def fake_run_elevated_capture(program, args, timeout=None):
        code = fake_run_elevated(program, args, timeout=timeout)
        return subprocess.CompletedProcess(args, code, stdout=b"")

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_capture", fake_run_capture)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated", fake_run_elevated)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated_capture", fake_run_elevated_capture)
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash.subprocess.run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=b"Usage: wsl.exe [Argument]\n" if not state["modern"] else b""),
    )

    manager._ensure_wsl()
    assert ("C:\\Windows\\System32\\wsl.exe", ("--install", "--web-download", "--no-distribution")) in calls


def test_ensure_wsl_falls_back_to_offline_distro_install(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    calls: list[tuple[str, tuple[str, ...]]] = []
    registration_calls = {"count": 0}

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._wsl_exe", lambda: r"C:\Windows\System32\wsl.exe")
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash._run_capture",
        lambda args, timeout=60: subprocess.CompletedProcess(args, 0, stdout=b""),
    )
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=b""),
    )

    def fake_wait(timeout):
        registration_calls["count"] += 1
        return {"Ubuntu-20.04"} if registration_calls["count"] >= 2 else set()

    def fake_run_elevated(program, args, timeout=None):
        calls.append((program, tuple(args)))
        return 1 if "--web-download" in args else 0

    def fake_run_elevated_capture(program, args, timeout=None):
        code = fake_run_elevated(program, args, timeout=timeout)
        return subprocess.CompletedProcess(args, code, stdout=b"")

    monkeypatch.setattr(manager, "_wsl_distros", lambda: set())
    monkeypatch.setattr(manager, "_wait_for_distro_registration", fake_wait)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_file", lambda wsl: True)
    monkeypatch.setattr(manager, "_wait_for_wsl_ready", lambda timeout: True)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated", fake_run_elevated)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated_capture", fake_run_elevated_capture)

    manager._ensure_wsl()
    assert ("C:\\Windows\\System32\\wsl.exe", ("--install", "-d", "Ubuntu-20.04")) in calls
    assert ("C:\\Windows\\System32\\wsl.exe", ("--install", "--web-download", "-d", "Ubuntu-20.04")) in calls


def test_web_download_help_output_falls_back_to_offline_distro(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    logs: list[str] = []
    monkeypatch.setattr(manager, "_log", logs.append)

    help_text = "用法：wsl.exe [参数]\n    --install <选项>\n"

    def fake_run_elevated_capture(program, args, timeout=None):
        return subprocess.CompletedProcess(args, 0, stdout=help_text.encode("utf-8"))

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated_capture", fake_run_elevated_capture)

    assert manager._install_wsl_distro_web_download(r"C:\Windows\System32\wsl.exe") is False
    assert any("does not support --web-download" in line for line in logs)


def test_ensure_wsl_tries_rootfs_and_appx_fallbacks(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    calls: list[str] = []
    wait_calls = {"count": 0}

    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._wsl_exe", lambda: r"C:\Windows\System32\wsl.exe")
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash._run_capture",
        lambda args, timeout=60: subprocess.CompletedProcess(args, 0, stdout=b""),
    )
    monkeypatch.setattr(
        "seeed_jetson_develop.wsl_flash.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=b""),
    )
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated", lambda *args, **kwargs: 1)
    monkeypatch.setattr("seeed_jetson_develop.wsl_flash._run_elevated_capture", lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, stdout=b""))
    monkeypatch.setattr(manager, "_wsl_distros", lambda: set())
    monkeypatch.setattr(manager, "_install_wsl_distro_web_download", lambda wsl: calls.append("web") or False)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_file", lambda wsl: calls.append("from-file") or False)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_rootfs", lambda wsl: calls.append("rootfs") or False)
    monkeypatch.setattr(manager, "_install_wsl_distro_from_appx", lambda: calls.append("appx") or True)
    monkeypatch.setattr(manager, "_wait_for_wsl_ready", lambda timeout: True)

    def fake_wait(timeout):
        wait_calls["count"] += 1
        return {"Ubuntu-20.04"} if wait_calls["count"] >= 2 else set()

    monkeypatch.setattr(manager, "_wait_for_distro_registration", fake_wait)

    manager._ensure_wsl()
    assert calls == ["web", "from-file", "rootfs", "appx"]


def test_flash_emits_failure_diagnostics_before_reraising(monkeypatch, tmp_path):
    manager = WslFlashManager(
        product="p",
        l4t_version="36.0",
        firmware_info={"filename": "fw.tbz2"},
        download_dir=tmp_path,
    )
    called: list[str] = []

    monkeypatch.setattr(manager, "_check_cancel", lambda: None)
    monkeypatch.setattr(manager, "_prefer_archive_distro", lambda: None)
    monkeypatch.setattr(manager, "_ensure_wsl", lambda: (_ for _ in ()).throw(WslFlashError("boom")))
    monkeypatch.setattr(manager, "_emit_failure_diagnostics", called.append)
    monkeypatch.setattr(manager, "_stop_attach_state_monitor", lambda: called.append("stop-monitor"))
    monkeypatch.setattr(manager, "_stop_auto_attach", lambda: called.append("stop-attach"))

    try:
        manager.flash()
        assert False, "expected WslFlashError"
    except WslFlashError as exc:
        assert str(exc) == "boom"

    assert called[0] == "boom"
    assert "stop-monitor" in called
    assert "stop-attach" in called
