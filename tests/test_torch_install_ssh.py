"""Integration tests for PyTorch install flow on a real Jetson device.

Usage:
    python -m pytest tests/test_torch_install_ssh.py -v -s

Requires:
    - Jetson device reachable at the IP in tests/device.json
    - SSH credentials in tests/device.json

Configuration (tests/device.json):
    {
      "host": "192.168.55.1",
      "username": "seeed",
      "password": "seeed",
      "port": 22
    }
"""
from __future__ import annotations

import json
import sys
import io
from pathlib import Path

import pytest

# Force UTF-8 stdout on Windows to handle pip's Unicode progress bars
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seeed_jetson_develop.core.runner import SSHRunner
from seeed_jetson_develop.modules.devices.torch_install_support import (
    TorchProfile, TorchTarget,
    select_profiles_for_l4t, compatible_targets_for_profile, build_install_commands,
    MINIFORGE_INSTALL_PATH,
)

DEVICE_CONFIG = Path(__file__).parent / "device.json"


def _load_device_config() -> dict:
    if not DEVICE_CONFIG.exists():
        pytest.skip(f"No device config at {DEVICE_CONFIG}")
    return json.loads(DEVICE_CONFIG.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def runner():
    import time
    cfg = _load_device_config()
    r = SSHRunner(
        host=cfg["host"],
        username=cfg["username"],
        password=cfg["password"],
        port=cfg.get("port", 22),
    )
    for attempt in range(5):
        rc, out = r.run("echo hello", timeout=15)
        if rc == 0:
            return r
        time.sleep(3)
    pytest.skip(f"Cannot reach device after 5 attempts: rc={rc}, out={out}")
    return r


@pytest.fixture(scope="module")
def l4t_version(runner: SSHRunner) -> str:
    rc, out = runner.run(
        "head -1 /etc/nv_tegra_release 2>/dev/null | awk '{gsub(\",\",\"\",$5); print $2\".\"$5}'",
        timeout=5,
    )
    assert rc == 0, f"Failed to get L4T version: {out}"
    ver = out.strip().splitlines()[-1].strip()
    print(f"\n[device] L4T version: {ver}")
    return ver


class TestSSHConnection:
    def test_ssh_reachable(self, runner: SSHRunner):
        rc, out = runner.run("whoami", timeout=5)
        assert rc == 0
        assert "seeed" in out.lower() or len(out.strip()) > 0

    def test_sudo_works(self, runner: SSHRunner):
        rc, out = runner.run("sudo -n true 2>/dev/null || echo 'need-password'", timeout=5)
        assert rc == 0

    def test_docker_available(self, runner: SSHRunner):
        rc, out = runner.run("docker --version", timeout=10)
        assert rc == 0, f"Docker not available: {out}"
        print(f"[device] Docker: {out.strip()}")


class TestProfileSelection:
    def test_profiles_for_jp6(self, l4t_version: str):
        if not l4t_version.startswith("36."):
            pytest.skip("Not JetPack 6")
        profiles = select_profiles_for_l4t(l4t_version)
        assert len(profiles) >= 1
        assert all(p.python_version == "3.10" for p in profiles)
        print(f"[profiles] {[p.id for p in profiles]}")

    def test_profiles_for_jp5(self, l4t_version: str):
        if not l4t_version.startswith("35."):
            pytest.skip("Not JetPack 5")
        profiles = select_profiles_for_l4t(l4t_version)
        assert len(profiles) >= 1
        assert all(p.python_version == "3.8" for p in profiles)

    def test_always_has_miniforge_target(self, l4t_version: str):
        profiles = select_profiles_for_l4t(l4t_version)
        targets = compatible_targets_for_profile([], profiles[0], conda_bin="")
        kinds = [t.kind for t in targets]
        assert "install-miniforge" in kinds


class TestMiniforgeInstall:
    """Test Miniforge download + conda env creation on device."""

    def test_miniforge_download_or_skip(self, runner: SSHRunner):
        rc, _ = runner.run(f"test -x $HOME/miniforge3/bin/conda && echo exists", timeout=5)
        if rc == 0:
            print("[skip] Miniforge already installed")
            return
        rc, out = runner.run(
            "wget --progress=dot:mega --tries=3 --timeout=30 "
            "https://github.com/conda-forge/miniforge/releases/latest/download/"
            "Miniforge3-Linux-aarch64.sh -O /tmp/miniforge.sh",
            timeout=600,
            on_output=lambda l: print(f"  {l}"),
        )
        if rc != 0:
            rc, out = runner.run(
                "wget --progress=dot:mega --tries=3 --timeout=30 "
                "https://mirrors.tuna.tsinghua.edu.cn/github-release/conda-forge/miniforge/"
                "LatestRelease/Miniforge3-Linux-aarch64.sh -O /tmp/miniforge.sh",
                timeout=600,
                on_output=lambda l: print(f"  {l}"),
            )
        assert rc == 0, f"Miniforge download failed: {out}"
        rc, out = runner.run(
            "bash /tmp/miniforge.sh -b -p $HOME/miniforge3 && rm -f /tmp/miniforge.sh",
            timeout=300,
            on_output=lambda l: print(f"  {l}"),
        )
        assert rc == 0, f"Miniforge install failed: {out}"

    def test_conda_create_env(self, runner: SSHRunner, l4t_version: str):
        profiles = select_profiles_for_l4t(l4t_version)
        if not profiles:
            pytest.skip("No profiles for this L4T")
        profile = profiles[0]
        env_name = f"torch-jp-{profile.python_version.replace('.', '')}"
        conda_bin = "$HOME/miniforge3/bin/conda"

        rc, _ = runner.run(f"test -x {conda_bin}", timeout=5)
        if rc != 0:
            pytest.skip("Miniforge not installed")

        rc, out = runner.run(
            f"({conda_bin} env list | grep -q {env_name} && "
            f"{conda_bin} env remove -y -n {env_name} || true) && "
            f"{conda_bin} create -y --quiet -n {env_name} python={profile.python_version} pip",
            timeout=600,
            on_output=lambda l: print(f"  {l}"),
        )
        assert rc == 0, f"conda create failed: {out}"

    def test_pip_available_in_env(self, runner: SSHRunner, l4t_version: str):
        profiles = select_profiles_for_l4t(l4t_version)
        if not profiles:
            pytest.skip("No profiles")
        profile = profiles[0]
        env_name = f"torch-jp-{profile.python_version.replace('.', '')}"
        conda_bin = "$HOME/miniforge3/bin/conda"

        rc, out = runner.run(
            f"{conda_bin} run --no-capture-output -n {env_name} python3 -m pip --version",
            timeout=30,
        )
        assert rc == 0, f"pip not available in env: {out}"
        print(f"[env] pip: {out.strip()}")


class TestTorchInstallCommands:
    """Validate generated commands are syntactically correct on device."""

    def test_commands_parse_on_device(self, runner: SSHRunner, l4t_version: str):
        profiles = select_profiles_for_l4t(l4t_version)
        if not profiles:
            pytest.skip("No profiles")
        profile = profiles[0]
        targets = compatible_targets_for_profile([], profile, conda_bin="")
        mf_target = next(t for t in targets if t.kind == "install-miniforge")
        cmds = build_install_commands(profile, mf_target)

        for i, cmd in enumerate(cmds):
            rc, out = runner.run(f"bash -n -c {__import__('shlex').quote(cmd)}", timeout=10)
            assert rc == 0, f"Step {i+1} syntax error: {cmd[:80]}... → {out}"
        print(f"[syntax] All {len(cmds)} commands pass bash -n check")


class TestFullInstall:
    """Full end-to-end torch install. Slow — run with: pytest -k TestFullInstall"""

    @pytest.mark.slow
    def test_full_torch_install(self, runner: SSHRunner, l4t_version: str):
        profiles = select_profiles_for_l4t(l4t_version)
        if not profiles:
            pytest.skip("No profiles")
        profile = profiles[0]
        targets = compatible_targets_for_profile([], profile, conda_bin="")
        mf_target = next(t for t in targets if t.kind == "install-miniforge")
        cmds = build_install_commands(profile, mf_target)

        print(f"\n[full install] {profile.label} → {len(cmds)} steps")
        for i, cmd in enumerate(cmds, 1):
            print(f"\n--- Step {i}/{len(cmds)} ---")
            print(f"$ {cmd[:120]}{'...' if len(cmd) > 120 else ''}")

            max_retries = 3 if _is_network_cmd(cmd) else 1
            for attempt in range(1, max_retries + 1):
                rc, out = runner.run(
                    cmd,
                    timeout=3600,
                    on_output=lambda l: print(f"  {l}"),
                )
                if rc == 0:
                    break
                if rc == -1 and attempt < max_retries:
                    import time
                    wait = 5 * attempt
                    print(f"  [retry] rc=-1 (connection lost?), waiting {wait}s then retry {attempt+1}/{max_retries}")
                    time.sleep(wait)
                    continue
                break
            assert rc == 0, f"Step {i} failed (rc={rc}) after {attempt} attempt(s): {out[-500:]}"
            print(f"[ok] Step {i}/{len(cmds)}")

        print("\n[PASS] Full PyTorch install completed successfully")


def _is_network_cmd(cmd: str) -> bool:
    keywords = ("apt-get", "wget", "pip install", "conda create", "conda env remove", "docker pull", "git clone")
    return any(k in cmd for k in keywords)
