# Ultralytics YOLO on Jetson — Detailed Setup Notes

Platform: NVIDIA Jetson Orin / JetPack 6.0+ / CUDA 12.x / TensorRT 10.3.0

---

## §1 Prerequisites

### Hardware
- Jetson Orin (Nano / NX / AGX) — SM 8.7
- JetPack 6.0, 6.1, or 6.2 (L4T 36.x)
- Minimum 8 GB storage free for wheels + model files

### Software already installed on JetPack 6.x
| Package | Location | Version |
|---------|----------|---------|
| CUDA | `/usr/local/cuda` | 12.x |
| TensorRT | `/usr/lib/python3.10/dist-packages/tensorrt*` | 10.3.0 |
| Python 3.10 | system | 3.10.x |
| libcusparselt0 | apt | 0.6.2.3 (or install manually) |

### Required before starting
1. **Miniconda / Miniforge** installed at one of:
   - `~/miniconda3`, `~/anaconda3`, `~/miniforge3`, `~/mambaforge`, `/opt/conda`
2. **Wheel files** (download or place manually in `~/wheels/`):
   - `torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl`
   - `torchvision-0.23.0-cp310-cp310-linux_aarch64.whl`
3. **CUDA-NMS torchvision build** at `~/vision/build/lib.linux-aarch64-3.10/torchvision/_C.so`
   (pre-compiled on the Jetson from PyTorch vision source with CUDA 12)
4. **[Optional] onnxruntime-gpu wheel** in `~/wheels/` for ONNX inference support
5. **[YOLOv26 only]** Git and internet access (script clones `https://github.com/bleaaach/yolov26_jetson.git`)

---

## §2 Environment Setup (Phase env)

Creates a conda environment with Python 3.10 locked:

```bash
conda create -n ultralytics python=3.10 -y
```

**Python version lock is critical.** All wheel files are `cp310` — if the env
ever upgrades to a different Python version (e.g. via `conda install`), the wheels
will refuse to install. The script detects this and auto-recreates the env.

**libcusparselt0** is required by torch 2.8 for sparse operations:
```bash
# Check if installed
dpkg -l | grep libcusparselt

# If not: install from .deb in ~/wheels/ or via apt
sudo apt install libcusparselt0=0.6.2.3
```

**YOLOv26 only:** The script clones the repo and copies `.pt` model files:
```bash
git clone https://github.com/bleaaach/yolov26_jetson.git ~/yolov26_jetson
cp ~/yolov26_jetson/ultralytics_data/*.pt ~/ultralytics_data/
```

---

## §3 Wheel Download (Phase download)

Downloads from Seeed Studio SharePoint using a requests session
(SharePoint requires FedAuth cookie handling, plain `wget` fails):

```python
# download_wheels.py uses requests.Session() + stream=True
# Shows download progress in percent
```

SharePoint URLs expire periodically. If downloads fail with 403:
1. Ask Seeed Studio to re-share the wheel files
2. Or place `*.whl` files manually in `~/wheels/`

Only torch + torchvision are downloaded. onnxruntime-gpu must be placed manually
(GitHub Releases returns 403 for large assets).

---

## §4 PyTorch Install + CUDA Verify (Phase torch-pre)

```bash
pip install ~/wheels/torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl
pip install ~/wheels/torchvision-0.23.0-cp310-cp310-linux_aarch64.whl
```

Verification:
```python
import torch
assert torch.cuda.is_available()          # must be True
assert "2.8.0a0+gitba56102" in torch.__version__
```

If `torch.cuda.is_available()` returns False:
- The GPU wheel failed to install
- Check: `pip show torch | grep Location` — if in a system path, something went wrong
- Fix: delete `~/wheels/*.whl`, re-run phase download + torch-pre

**CUDA NMS patch** is applied immediately after torchvision install:
```bash
cp ~/vision/build/lib.linux-aarch64-3.10/torchvision/_C.so \
   $CONDA_ENV_SITE/torchvision/_C.so
```

---

## §5 Dependencies + Ultralytics Install (Phase deps)

Install order matters (see `dependency_mapping_rules.md`):

1. **onnxruntime-gpu** — search `~/wheels/` and `~/wheel/` for local wheel
2. **numpy 1.26.0** — pin before ultralytics pulls numpy 2.x
3. **opencv-python 4.10.0.84** — pip only, never conda
4. **system TRT .pth link** — prevents ultralytics from installing PyPI tensorrt

```bash
echo "/usr/lib/python3.10/dist-packages" > \
  $CONDA_ENV_SITE/system_tensorrt.pth
```

5. **ultralytics[export]** — installs last, will overwrite torch with CPU version

```bash
pip install ultralytics[export]
```

This is expected and handled in phase torch-post.

---

## §6 Restore torch + Validate (Phase torch-post)

Restores the GPU wheel after ultralytics overwrites it:

```bash
pip install ~/wheels/torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl
pip install ~/wheels/torchvision-0.23.0-cp310-cp310-linux_aarch64.whl
pip install numpy==1.26.0
```

Re-applies CUDA NMS patch (torchvision reinstall overwrites `_C.so`):
```bash
cp ~/vision/build/lib.linux-aarch64-3.10/torchvision/_C.so \
   $CONDA_ENV_SITE/torchvision/_C.so
```

Full validation script checks (all must pass ✓):
| Check | Expected |
|-------|----------|
| torch.cuda.is_available() | True |
| torch.__version__ | 2.8.0a0+gitba56102 |
| CUDA NMS | runs without error |
| numpy.__version__ | 1.26.x |
| cv2.__version__ | >= 4.10.0 |
| tensorrt version | 10.3.0.x |
| ultralytics version | installed |

---

## §7 Camera Setup

Jetson USB cameras (/dev/video*) require group membership and udev rules:

```bash
# Add current user to video group
sudo usermod -aG video $USER

# Create udev rules (applies without reboot)
sudo tee /etc/udev/rules.d/99-usb-cameras.rules > /dev/null <<'EOF'
KERNEL=="video[0-9]*", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="046d", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="05a3", MODE="0666"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Test:
```python
import cv2
cap = cv2.VideoCapture(0)
print('opened:', cap.isOpened())
cap.release()
```

Note: `sudo usermod -aG video` requires **logout + login** to take effect for
interactive sessions, but udev rules apply immediately for device-level access.

---

## §8 Model Download and TensorRT Export

### YOLOv8

```bash
conda activate ultralytics
mkdir -p ~/ultralytics_data && cd ~/ultralytics_data

# Auto-download .pt models (first use triggers download from ultralytics CDN)
python3 -c "
from ultralytics import YOLO
YOLO('yolov8n.pt')
YOLO('yolov8n-pose.pt')
YOLO('yolov8n-seg.pt')
"

# Export TensorRT engines (~3–5 min each)
yolo export model=yolov8n.pt      format=engine device=0 half=True
yolo export model=yolov8n-pose.pt format=engine device=0 half=True
yolo export model=yolov8n-seg.pt  format=engine device=0 half=True
```

### YOLOv11

```bash
conda activate ultralytics
mkdir -p ~/ultralytics_data && cd ~/ultralytics_data

python3 -c "
from ultralytics import YOLO
YOLO('yolo11n.pt')
YOLO('yolo11n-pose.pt')
YOLO('yolo11n-seg.pt')
"

yolo export model=yolo11n.pt      format=engine device=0 half=True
yolo export model=yolo11n-pose.pt format=engine device=0 half=True
yolo export model=yolo11n-seg.pt  format=engine device=0 half=True
```

### YOLOv26

```bash
conda activate ultralytics
# Models already in ~/ultralytics_data/ (copied from cloned repo in phase env)
cd ~/ultralytics_data

yolo export model=yolo26n.pt      format=engine device=0 half=True
yolo export model=yolo26n-pose.pt format=engine device=0 half=True
yolo export model=yolo26n-seg.pt  format=engine device=0 half=True
```

### Export flags explained
| Flag | Value | Reason |
|------|-------|--------|
| `format=engine` | TensorRT `.engine` | GPU-optimized inference |
| `device=0` | CUDA:0 | Always GPU, never CPU |
| `half=True` | FP16 | 2x speed on Jetson Orin vs FP32 |
| `end2end` | (not set) | Default; NMS in Python post-process |

---

## §9 Running Inference

```bash
conda activate ultralytics

# Image inference
python3 -c "
from ultralytics import YOLO
model = YOLO('/home/seeed/ultralytics_data/yolo11n.engine')
results = model('path/to/image.jpg', device=0)
results[0].show()
"

# Webcam inference
python3 -c "
from ultralytics import YOLO
model = YOLO('/home/seeed/ultralytics_data/yolo11n.engine')
results = model(source=0, stream=True, device=0)
for r in results:
    r.show()
"
```

---

## §10 Performance Tuning

### Max Jetson clocks
```bash
sudo nvpmodel -m 0        # Max power mode (15W/25W depending on module)
sudo jetson_clocks        # Lock all clocks at max frequency
```

### Check GPU utilization
```bash
tegrastats                          # Jetson-native stats
watch -n1 tegrastats                # Live view
```

### Benchmark
```bash
conda activate ultralytics
python3 -c "
from ultralytics import YOLO
model = YOLO('/home/seeed/ultralytics_data/yolo11n.engine')
model.benchmark(imgsz=640, device=0, half=True)
"
```

### Expected inference speed (Jetson Orin NX 16GB, FP16)
| Model | Format | FPS (approx) |
|-------|--------|-------------|
| yolo11n | PyTorch | ~30 |
| yolo11n | TensorRT FP16 | ~120 |
| yolov8n | TensorRT FP16 | ~130 |

---

## §11 Uninstall / Clean Up

```bash
# Remove environment
conda env remove -n ultralytics

# Remove downloaded model files
rm -rf ~/ultralytics_data/

# Remove wheels (keep if planning to reinstall)
rm ~/wheels/torch-*.whl ~/wheels/torchvision-*.whl

# Remove udev rules
sudo rm /etc/udev/rules.d/99-usb-cameras.rules
sudo udevadm control --reload-rules
```

YOLOv26 repo:
```bash
rm -rf ~/yolov26_jetson
```
