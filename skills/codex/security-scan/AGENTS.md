---
name: security-scan
description: Deploy a knife detection model on Triton Inference Server using reComputer J1010 for X-ray security scanning, with Raspberry Pi clients sending images for inference and displaying detection results.
---

# Security X-ray Scan Knife Detection

## Execution model

Run one phase at a time. After each phase, verify the expected result before continuing.
- If a phase succeeds → print `[OK]` and move to the next phase.
- If a phase fails → print `[STOP]`, consult the failure decision tree, and ask the user before retrying.

## Phase 1 — Verify prerequisites

Hardware required:
- 1-2x Raspberry Pi 4B
- reComputer J1010 (or J1020, J2011, J2012, AGX Xavier)
- HDMI display, mouse, keyboard
- All devices on the same network

```bash
# On Raspberry Pi: check Python version (need 3.9.2)
python3 --version
# On reComputer: check JetPack
cat /etc/nv_tegra_release
```

Expected: Python 3.9.2 on RPi; JetPack 4.6.1 on reComputer.

## Phase 2 — Set up Raspberry Pi environment

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade

# Install dependencies
sudo apt-get install python3-pip libjpeg-dev libopenblas-dev libopenmpi-dev libomp-dev

# Install setuptools and Cython
sudo -H pip3 install setuptools==58.3.0
sudo -H pip3 install Cython

# Install gdown for Google Drive downloads
sudo -H pip3 install gdown

# Install PyTorch 1.11.0 (Buster OS, aarch64)
gdown https://drive.google.com/uc?id=1gAxP9q94pMeHQ1XOvLHqjEcmgyxjlY_R
sudo -H pip3 install torch-1.11.0a0+gitbc2c6ed-cp39-cp39-linux_aarch64.whl
rm torch-1.11.0a0+gitbc2c6ed-cp39-cp39-linux_aarch64.whl
```

Verify PyTorch:

```python
import torch as tr
print(tr.__version__)
```

Install remaining dependencies:

```bash
# Tritonclient
pip3 install tritonclient[all]

# TorchVision 0.12.0
gdown https://drive.google.com/uc?id=1oDsJEHoVNEXe53S9f1zEzx9UZCFWbExh
sudo -H pip3 install torchvision-0.12.0a0+9b5a3fe-cp39-cp39-linux_aarch64.whl
rm torchvision-0.12.0a0+9b5a3fe-cp39-cp39-linux_aarch64.whl

# OpenCV
pip3 install opencv-python
```

Expected: All packages install without errors.

## Phase 3 — Set up reComputer J1010 (Triton Server)

Ensure JetPack 4.6.1 is installed on the reComputer.

```bash
# Create model repository and download ONNX model
mkdir -p ~/server/docs/examples/model_repository/opi/1
# Download model.onnx from: https://drive.google.com/file/d/1RcHK_gthCXHsJLeDOUQ6c3r0RlAUgRfV/view
# Place model.onnx into ~/server/docs/examples/model_repository/opi/1/

# (Optional) Clone general Triton server examples
git clone https://github.com/triton-inference-server/server
cd ~/server/docs/examples
sh fetch_models.sh
```

Install Triton Inference Server:

```bash
# Download tritonserver2.19.0-jetpack4.6.1.tgz from:
# https://github.com/triton-inference-server/server/releases/download/v2.19.0/tritonserver2.19.0-jetpack4.6.1.tgz

mkdir ~/TritonServer && tar -xzvf tritonserver2.19.0-jetpack4.6.1.tgz -C ~/TritonServer
cd ~/TritonServer/bin
./tritonserver --model-repository=/home/seeed/server/docs/examples/model_repository \
  --backend-directory=/home/seeed/TritonServer/backends \
  --strict-model-config=false \
  --min-supported-compute-capability=5.3
```

Expected: Triton server starts and shows models loaded successfully.

## Phase 4 — Clone project and prepare data (on Raspberry Pi)

```bash
git clone https://github.com/LemonCANDY42/Seeed_SMG_AIOT.git
cd Seeed_SMG_AIOT/
git clone https://github.com/LemonCANDY42/OPIXray.git

# Create weights directory and download DOAM.pth
cd OPIXray/DOAM
mkdir weights
# Download DOAM.pth from: https://files.seeedstudio.com/wiki/SecurityCheck/DOAM.pth.zip
# Extract and place DOAM.pth into weights/

# Create Dataset directory
# Download X-ray dataset from: https://drive.google.com/file/d/12moaa-ylpVu0KmUCZj_XXeA5TxZuCQ3o/view
# Extract into a Dataset folder
```

Expected: Project cloned; weights and dataset in place.

## Phase 5 — Run inference

```bash
cd ~/Seeed_SMG_AIOT
python3 OPIXray_grpc_image_client.py -u <RECOMPUTER_IP>:8001 -m opi Dataset
```

Replace `<RECOMPUTER_IP>` with the reComputer's IP address.

Expected: Inference results displayed showing knife detection in X-ray images.

## Failure decision tree

| Symptom | Likely cause | Suggested fix |
|---|---|---|
| `libb64.so.0d` error on Triton launch | Missing library | `sudo apt-get install libb64-0d` |
| `libre2.so.2` error on Triton launch | Missing library | `sudo apt-get install libre2-dev` |
| "failed to load all models" on Triton | Model config issue | Add `--exit-on-error=false` flag; check model.onnx placement |
| PyTorch install fails on RPi | Wrong Python version or OS | Confirm Python 3.9.2 and Raspbian Buster 64-bit |
| gRPC connection refused | Triton not running or wrong IP | Verify Triton is running; check IP and port 8001 |
| No detection results | Wrong dataset path or model weights | Verify Dataset folder path and DOAM.pth in weights/ |

## Reference files

- `references/source.body.md` — Full original wiki content (reference only)
