# LeRobot Environment Setup — Jetson / SO-ARM (JetPack 6.0+)

Validated: Orin AGX / Orin NX, JetPack 6.0+, CUDA 12.x, Python 3.10

**Before executing any step**, run the analysis script and read `steps` in the output JSON.
Each step below lists its skip condition — only run steps marked `"status": "run"`.

---

## §1 Create environment

**Skip condition**: `steps.miniconda = skip` AND `steps.conda_env = skip` AND `steps.git_clone = skip`

```bash
# §1a — skip if steps.miniconda = skip
if ! command -v conda &>/dev/null; then
  wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
  chmod +x Miniconda3-latest-Linux-aarch64.sh
  ./Miniconda3-latest-Linux-aarch64.sh
  source ~/.bashrc
fi

# §1b — skip if steps.conda_env = skip
if ! conda env list | grep -q '^lerobot '; then
  conda create -y -n lerobot python=3.10
fi
conda activate lerobot

# §1c — skip if steps.git_clone = skip (lerobot already installed)
if ! conda run -n lerobot python3 -c "import lerobot" 2>/dev/null; then
  git clone https://github.com/Seeed-Projects/lerobot.git ~/lerobot
fi
```

---

## §2 Download and install torch / torchvision FIRST

**Skip condition**: `steps.download_wheels = skip` AND `steps.install_torch_pre = skip`

> **Why first**: `pip install -e .` (§3) overwrites GPU torch with a CPU PyPI wheel.
> **Why a script**: SharePoint 302 sets a `FedAuth` cookie; must use `requests.Session()`.

```bash
# §2a — skip if steps.download_wheels = skip
if [[ ! -f ~/wheels/torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl ]] || \
   [[ ! -f ~/wheels/torchvision-0.23.0-cp310-cp310-linux_aarch64.whl ]]; then
  pip install requests
  python3 scripts/download_wheels.py --dest ~/wheels
fi

# §2b — skip if steps.install_torch_pre = skip
# (torch already correct version + CUDA, lerobot already installed)
pip install ~/wheels/torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl
pip install ~/wheels/torchvision-0.23.0-cp310-cp310-linux_aarch64.whl
```

---

## §3 Install dependencies + LeRobot (editable)

**Skip condition**: `steps.install_opencv = skip` AND `steps.install_ffmpeg = skip`
AND `steps.pin_numpy = skip` AND `steps.install_lerobot = skip`

```bash
# §3a opencv — skip if steps.install_opencv = skip
if ! conda run -n lerobot python3 -c "import cv2; assert cv2.__version__=='4.10.0.84'" 2>/dev/null; then
  conda install -y -c conda-forge "opencv>=4.10.0.84"
  conda remove -y opencv
  pip3 install opencv-python==4.10.0.84
fi

# §3b ffmpeg — skip if steps.install_ffmpeg = skip
if ! conda run -n lerobot ffmpeg -version &>/dev/null; then
  conda install -y -c conda-forge ffmpeg
  # If libsvtav1 error: conda install -y ffmpeg=7.1.1 -c conda-forge
fi

# §3c numpy — skip if steps.pin_numpy = skip
if ! conda run -n lerobot python3 -c "import numpy as np; assert np.__version__.startswith('1.26')" 2>/dev/null; then
  conda uninstall -y numpy 2>/dev/null || true
  pip3 install numpy==1.26.0
fi

# §3d lerobot — skip if steps.install_lerobot = skip
if ! conda run -n lerobot python3 -c "import lerobot" 2>/dev/null; then
  cd ~/lerobot && pip install -e ".[feetech]"
fi
```

---

## §4 Reinstall torch stack after editable install

**Skip condition**: `steps.reinstall_torch_post = skip`
(Only skippable if lerobot was already installed AND torch CUDA was already True before this session.)

```bash
# Wheels already in ~/wheels from §2 — reinstall to undo editable install overwrite
pip install ~/wheels/torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl
pip install ~/wheels/torchvision-0.23.0-cp310-cp310-linux_aarch64.whl
pip3 install numpy==1.26.0
```

---

## §5 Validation

**Always run** — confirms the full stack is correct regardless of which steps were skipped.

```bash
conda activate lerobot
python3 - <<'EOF'
import torch, torchvision, cv2, numpy as np
print("CUDA available:", torch.cuda.is_available())
print("torch:", torch.__version__)
print("torchvision:", torchvision.__version__)
print("OpenCV:", cv2.__version__)
print("numpy:", np.__version__)
EOF
```

Expected:
- `CUDA available: True`
- `torch: 2.8.0a0+gitba56102`
- `torchvision: 0.23.0`
- `OpenCV: 4.10.0.84`
- `numpy: 1.26.x`

---

## §6 Serial port setup (SO-ARM)

**Skip condition**: `steps.serial = skip`
(user in dialout, brltty absent, udev rule `/etc/udev/rules.d/99-serial-ports.rules` present)

```bash
# Remove brltty if present
if dpkg -l brltty 2>/dev/null | grep -q '^ii'; then
  sudo apt remove brltty
fi

# Add to dialout if missing
if ! id -nG | grep -qw dialout; then
  sudo usermod -aG dialout $USER
fi

# Add udev rule if missing
if [[ ! -f /etc/udev/rules.d/99-serial-ports.rules ]]; then
  sudo tee /etc/udev/rules.d/99-serial-ports.rules > /dev/null <<'EOF'
KERNEL=="ttyUSB[0-9]*", MODE="0666"
KERNEL=="ttyACM[0-9]*", MODE="0666"
EOF
  sudo udevadm control --reload-rules
  sudo udevadm trigger
fi
```

---

## §7 Optional packages

### Fashionstar dual-arm only

```bash
pip install lerobot_teleoperator_bimanual_leader
pip install lerobot_robot_bimanual_follower
pip install --upgrade tifffile
```

### cuDSS 0.7.1

```bash
wget https://developer.download.nvidia.com/compute/cudss/0.7.1/local_installers/cudss-local-tegra-repo-ubuntu2204-0.7.1_0.7.1-1_arm64.deb
sudo dpkg -i cudss-local-tegra-repo-ubuntu2204-0.7.1_0.7.1-1_arm64.deb
sudo cp /var/cudss-local-tegra-repo-ubuntu2204-0.7.1/cudss-*-keyring.gpg /usr/share/keyrings/
sudo apt-get update
sudo apt-get -y install cudss
```
