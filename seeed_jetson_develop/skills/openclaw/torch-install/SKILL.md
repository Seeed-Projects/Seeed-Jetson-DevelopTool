---
name: torch-install
description: Install NVIDIA-optimized PyTorch with CUDA support on reComputer Jetson devices, covering JetPack 5.1.3 and JetPack 6.2 workflows, cuSPARSELt setup, verification, and managing multiple PyTorch versions with Miniconda.
---

# Install PyTorch for reComputer Jetson

## Execution model

Run one phase at a time. After each phase, verify the expected result before continuing.
- If a phase succeeds → print `[OK]` and move to the next phase.
- If a phase fails → print `[STOP]`, consult the failure decision tree, and ask the user before retrying.

## Phase 1 — Verify prerequisites

```bash
cat /etc/nv_tegra_release
dpkg -l | grep nvidia-jetpack
python3 --version
ping -c 2 developer.download.nvidia.com
```

Expected: JetPack version identified; Python version noted; internet reachable.

## Phase 2A — Install PyTorch on JetPack 5.1.3

```bash
sudo apt-get -y update
sudo apt-get install -y python3-pip libopenblas-dev

wget https://developer.download.nvidia.com/compute/redist/jp/v512/pytorch/torch-2.1.0a0+41361538.nv23.06-cp38-cp38-linux_aarch64.whl
pip install torch-2.1.0a0+41361538.nv23.06-cp38-cp38-linux_aarch64.whl
```

Verify:

```python
import torch
print(torch.cuda.is_available())  # Should print True
print(torch.__version__)
```

Expected: `True` and torch version displayed.

## Phase 2B — Install PyTorch on JetPack 6.2

```bash
sudo apt-get -y update
sudo apt-get install -y python3-pip libopenblas-dev
```

Install cuSPARSELt (required for PyTorch 24.06+):

```bash
wget https://developer.download.nvidia.com/compute/cusparselt/0.7.1/local_installers/cusparselt-local-tegra-repo-ubuntu2204-0.7.1_1.0-1_arm64.deb
sudo dpkg -i cusparselt-local-tegra-repo-ubuntu2204-0.7.1_1.0-1_arm64.deb
sudo cp /var/cusparselt-local-tegra-repo-ubuntu2204-0.7.1/cusparselt-*-keyring.gpg /usr/share/keyrings/
sudo apt-get update
sudo apt-get -y install libcusparselt0 libcusparselt-dev
```

Install PyTorch:

```bash
wget https://developer.download.nvidia.cn/compute/redist/jp/v61/pytorch/torch-2.5.0a0+872d972e41.nv24.08.17622132-cp310-cp310-linux_aarch64.whl
pip install torch-2.5.0a0+872d972e41.nv24.08.17622132-cp310-cp310-linux_aarch64.whl
```

Verify:

```python
import torch
print(torch.cuda.is_available())  # Should print True
```

Expected: `True`

## Phase 2C — Install PyTorch for other JetPack versions

```bash
sudo apt-get -y update
sudo apt-get install -y python3-pip libopenblas-dev
```

Browse [NVIDIA PyTorch wheels](https://developer.download.nvidia.cn/compute/redist/jp/) and download the wheel matching your JetPack and Python version:

```bash
wget <wheel_url>
pip install <wheel_filename>.whl
```

Verify:

```python
import torch
print(torch.cuda.is_available())
```

## Phase 3 — Multiple PyTorch versions with Conda (optional)

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
bash Miniconda3-latest-Linux-aarch64.sh
```

Follow prompts: agree to terms, use default path, enter "yes" to add to .bashrc.

```bash
source ~/.bashrc
conda --version
conda config --set auto_activate_base false
```

Create environment and install a specific PyTorch version:

```bash
conda create -n torch_2.0 python=3.8
conda activate torch_2.0
# Then download and install the appropriate wheel as in Phase 2
```

## Failure decision tree

| Symptom | Likely cause | Suggested fix |
|---|---|---|
| `torch.cuda.is_available()` returns `False` | Wrong wheel for JetPack version | Verify JetPack version and download matching wheel |
| `pip install` fails with version conflict | Python version mismatch | Check `python3 --version` matches wheel (cp38/cp310) |
| `libopenblas` not found | Missing dependency | `sudo apt-get install libopenblas-dev` |
| cuSPARSELt install fails (JP6) | Wrong Ubuntu version or arch | Verify Ubuntu 22.04 aarch64 on JetPack 6 |
| `wget` download fails | Network issue or URL changed | Check connectivity; browse NVIDIA redist page for updated URL |
| Conda not found after install | .bashrc not sourced | Run `source ~/.bashrc` or open new terminal |

## Reference files

- `references/source.body.md` — Full original wiki content (reference only)
