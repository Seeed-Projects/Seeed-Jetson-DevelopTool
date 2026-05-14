"""Shared torch install profiles for Jetson devices."""
from __future__ import annotations

from dataclasses import dataclass
import shlex


@dataclass(frozen=True)
class TorchProfile:
    id: str
    label: str
    l4t_prefixes: tuple[str, ...]
    python_version: str
    torch_version: str
    torchvision_version: str
    torch_url: str
    torchvision_url: str = ""
    needs_cusparselt: bool = False
    recommended: bool = False


@dataclass(frozen=True)
class TorchTarget:
    id: str
    label: str
    kind: str
    python_version: str
    python_cmd: str
    conda_bin: str = ""
    env_name: str = ""
    installed_torch: str = ""
    installed_torchvision: str = ""
    cuda_available: str = ""


TORCH_PROFILES: tuple[TorchProfile, ...] = (
    TorchProfile(
        id="jp5-2.1",
        label="JetPack 5.x - PyTorch 2.1 / TorchVision 0.16",
        l4t_prefixes=("35.",),
        python_version="3.8",
        torch_version="2.1.0a0+41361538.nv23.06",
        torchvision_version="0.16.2",
        torch_url=(
            "https://developer.download.nvidia.com/compute/redist/jp/v512/pytorch/"
            "torch-2.1.0a0+41361538.nv23.06-cp38-cp38-linux_aarch64.whl"
        ),
    ),
    TorchProfile(
        id="jp5-2.2",
        label="JetPack 5.x - PyTorch 2.2 / TorchVision 0.17 (Seeed wheel)",
        l4t_prefixes=("35.",),
        python_version="3.8",
        torch_version="2.2.x (Seeed wheel)",
        torchvision_version="0.17.2",
        torch_url=(
            "https://seeedstudio88-my.sharepoint.com/:u:/g/personal/"
            "youjiang_yu_seeedstudio88_onmicrosoft_com/"
            "EVSylp0HuEFKigdpEzDlkVoBgmcjcT5StPS2xkzfp8RQVg?e=duoRdR&download=1"
        ),
    ),
    TorchProfile(
        id="jp6-2.5",
        label="JetPack 6.x - PyTorch 2.5 / TorchVision 0.20",
        l4t_prefixes=("36.",),
        python_version="3.10",
        torch_version="2.5.0a0+872d972e41.nv24.08.17622132",
        torchvision_version="0.20.0a0+afc54f7",
        torch_url=(
            "https://developer.download.nvidia.cn/compute/redist/jp/v61/pytorch/"
            "torch-2.5.0a0+872d972e41.nv24.08.17622132-cp310-cp310-linux_aarch64.whl"
        ),
        torchvision_url=(
            "https://github.com/ultralytics/assets/releases/download/v0.0.0/"
            "torchvision-0.20.0a0+afc54f7-cp310-cp310-linux_aarch64.whl"
        ),
        needs_cusparselt=True,
        recommended=True,
    ),
    TorchProfile(
        id="jp6-2.7",
        label="JetPack 6.x - PyTorch 2.7 / TorchVision 0.22 (Seeed wheel)",
        l4t_prefixes=("36.",),
        python_version="3.10",
        torch_version="2.7.x (Seeed wheel)",
        torchvision_version="0.22.0",
        torch_url=(
            "https://seeedstudio88-my.sharepoint.com/:u:/g/personal/"
            "youjiang_yu_seeedstudio88_onmicrosoft_com/"
            "EW2ke8EPcVhGsM2mjCMQOWEBQHRtPMGgAkHOR6hGD-zLjA?e=wPiBzH&download=1"
        ),
        needs_cusparselt=True,
    ),
)


def select_profiles_for_l4t(l4t_release: str) -> list[TorchProfile]:
    release = (l4t_release or "").strip().lstrip("R")
    if release.startswith("35."):
        return [p for p in TORCH_PROFILES if p.id.startswith("jp5-")]
    if release.startswith("36."):
        return [p for p in TORCH_PROFILES if p.id.startswith("jp6-")]
    return list(TORCH_PROFILES)


def compatible_targets_for_profile(
    targets: list[TorchTarget],
    profile: TorchProfile,
    conda_bin: str = "",
) -> list[TorchTarget]:
    matched = [t for t in targets if t.python_version == profile.python_version]
    if matched:
        return matched
    if conda_bin:
        env_name = f"torch-jp-{profile.python_version.replace('.', '')}"
        matched.append(
            TorchTarget(
                id=f"new-conda:{env_name}",
                label=f"Create conda env {env_name} (Python {profile.python_version})",
                kind="new-conda",
                python_version=profile.python_version,
                python_cmd="python3",
                conda_bin=conda_bin,
                env_name=env_name,
            )
        )
    return matched


def build_install_commands(profile: TorchProfile, target: TorchTarget) -> list[str]:
    cmds = [
        "sudo apt-get -y update",
        "sudo apt-get install -y python3-pip libopenblas-dev libjpeg-dev zlib1g-dev git",
    ]

    if target.kind == "new-conda":
        conda_bin = shlex.quote(target.conda_bin)
        env_name = shlex.quote(target.env_name)
        cmds.append(f"{conda_bin} create -y -n {env_name} python={target.python_version}")
        exec_prefix = f"{conda_bin} run -n {env_name} "
    elif target.kind == "conda":
        conda_bin = shlex.quote(target.conda_bin)
        env_name = shlex.quote(target.env_name)
        exec_prefix = f"{conda_bin} run -n {env_name} "
    else:
        exec_prefix = ""

    python_cmd = shlex.quote(target.python_cmd)
    pip_cmd = f"{exec_prefix}{python_cmd} -m pip"

    if profile.needs_cusparselt:
        cmds.extend(
            [
                "wget -q https://developer.download.nvidia.com/compute/cusparselt/0.7.1/local_installers/"
                "cusparselt-local-tegra-repo-ubuntu2204-0.7.1_1.0-1_arm64.deb -O /tmp/cusparselt.deb",
                "sudo dpkg -i /tmp/cusparselt.deb",
                "sudo cp /var/cusparselt-local-tegra-repo-ubuntu2204-0.7.1/cusparselt-*-keyring.gpg /usr/share/keyrings/",
                "sudo apt-get update -qq",
                "sudo apt-get -y install libcusparselt0 libcusparselt-dev",
            ]
        )

    cmds.extend(
        [
            f"{pip_cmd} install --upgrade pip setuptools wheel",
            f"{pip_cmd} install --no-cache-dir numpy==1.26.1",
            f"{pip_cmd} install --no-cache-dir {profile.torch_url}",
        ]
    )
    if profile.torchvision_url:
        cmds.append(f"{pip_cmd} install --no-cache-dir {profile.torchvision_url}")
    else:
        cmds.append(f"{pip_cmd} install --no-cache-dir --no-deps torchvision=={profile.torchvision_version}")
    cmds.append(
        f"{exec_prefix}{python_cmd} -c \"import torch, torchvision; "
        "print('CUDA:', torch.cuda.is_available()); "
        "print('Torch:', torch.__version__); "
        "print('TorchVision:', torchvision.__version__)\""
    )
    return cmds
