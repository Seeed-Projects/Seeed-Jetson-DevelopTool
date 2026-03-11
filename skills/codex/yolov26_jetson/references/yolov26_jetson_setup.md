# YOLOv26 Jetson Setup — Dual USB Camera System (JetPack 6.0+)

Validated: Orin AGX / Orin NX, JetPack 6.0+, CUDA 12.x, Python 3.10

---

## §1 Prerequisites

### Hardware
- **reComputer J4012** (Orin NX 16GB) or **Jetson AGX Orin**
- **2× USB cameras** (Logitech C920 or similar UVC-compliant)
- USB 3.0 hub recommended for dual-camera bandwidth

### Software
- JetPack 6.0+ (L4T 36.x)
- Miniconda (Python 3.10 environment)
- Git

**Check JetPack version:**
```bash
cat /etc/nv_tegra_release
# Expected: R36.x.x (JetPack 6.x)
```

**Install Miniconda if missing:**
```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
bash Miniconda3-latest-Linux-aarch64.sh
source ~/.bashrc
```

---

## §2 Environment setup (Phase 1)

```bash
bash ~/.agents/skills/yolov26_jetson_fixed/scripts/install_yolov26.sh \
  --env yolov26 --phase env
```

This phase:
- Creates `yolov26` conda env with Python 3.10
- Clones `https://github.com/bleaaach/yolov26_jetson.git` → `~/yolov26_jetson/`
- Creates `~/ultralytics_data/` model directory
- Installs `libcusparselt0` (from bundled deb or apt)

---

## §3 Download wheels (Phase 2)

```bash
bash ~/.agents/skills/yolov26_jetson_fixed/scripts/install_yolov26.sh \
  --env yolov26 --phase download
```

Downloads to `~/wheels/`:
| File | Size | Source |
|------|------|--------|
| `torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl` | ~700 MB | Seeed SharePoint |
| `torchvision-0.23.0-cp310-cp310-linux_aarch64.whl` | ~15 MB | Seeed SharePoint |
| `onnxruntime_gpu-1.23.0-cp310-cp310-linux_aarch64.whl` | ~60 MB | GitHub Releases |

> **Network note**: SharePoint downloads set a FedAuth cookie on first redirect.
> The script handles this automatically via `requests.Session()`.

**Manual fallback** — if download fails, place files directly:
```bash
mkdir -p ~/wheels
# Copy wheel files to ~/wheels/ then re-run phase 2 to verify
```

---

## §4 Install torch + verify CUDA (Phase 3)

```bash
bash ~/.agents/skills/yolov26_jetson_fixed/scripts/install_yolov26.sh \
  --env yolov26 --phase torch-pre
```

Installs torch + torchvision wheels, then hard-stops if CUDA is not available.
If this phase fails with `torch.cuda.is_available() = False`, the wheel is corrupt:

```bash
rm ~/wheels/torch-*.whl ~/wheels/torchvision-*.whl
# Re-run phase 2 and 3
```

---

## §5 Install dependencies (Phase 4)

```bash
bash ~/.agents/skills/yolov26_jetson_fixed/scripts/install_yolov26.sh \
  --env yolov26 --phase deps
```

Installs in order:
1. `onnxruntime-gpu 1.23.0` — required for TensorRT engine export
2. `numpy==1.26.0` — pinned for OpenCV ABI compatibility
3. `opencv-python==4.10.0.84` — via conda then pip (see `dependency_mapping_rules.md` Rule 5)
4. `ultralytics[export]` — YOLOv26 framework (may overwrite torch — Phase 5 fixes this)

---

## §6 Reinstall torch + validate (Phase 5)

```bash
bash ~/.agents/skills/yolov26_jetson_fixed/scripts/install_yolov26.sh \
  --env yolov26 --phase torch-post
```

**Why reinstall?** `ultralytics[export]` pulls CPU-only torch from PyPI.
This phase restores the Jetson GPU wheels, then runs full validation:

```
  ✓ CUDA available: True  (expected True)
  ✓ torch version: 2.8.0a0+gitba56102  (expected 2.8.0a0+gitba56102)
  ✓ torchvision version: 0.23.0  (expected 0.23.0)
  ✓ numpy version: True  (expected True)
  ✓ opencv version: 4.10.0.84  (expected 4.10.0.84)
  ✓ onnxruntime version: 1.23.0  (expected 1.23.0)
  ✓ ultralytics present: True  (expected True)
  ✓ CUDA NMS: works

[OK] All checks passed
```

If any check shows ✗, consult `conflict_resolution_playbook.md`.

---

## §7 Camera permissions

```bash
# Add user to video group
if ! id -nG | grep -qw video; then sudo usermod -aG video $USER; fi

# Create udev rules (take effect immediately, no re-login needed)
if [[ ! -f /etc/udev/rules.d/99-usb-cameras.rules ]]; then
  sudo tee /etc/udev/rules.d/99-usb-cameras.rules > /dev/null <<'EOF'
KERNEL=="video[0-9]*", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="046d", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="05a3", MODE="0666"
EOF
  sudo udevadm control --reload-rules && sudo udevadm trigger
fi
```

**Verify cameras are detected:**
```bash
ls /dev/video*
# Should show /dev/video0, /dev/video1 (or higher indices)
v4l2-ctl --list-devices
```

---

## §8 Export TensorRT engines

Engines are device-specific and must be built on the target Jetson.
Place `.pt` model files in `~/ultralytics_data/` first.

```bash
conda activate yolov26
cd ~/ultralytics_data

# Export all three models (FP16, takes ~3-5 min each)
yolo export model=yolo26n.pt      format=engine device=0 half=True
yolo export model=yolo26n-pose.pt format=engine device=0 half=True
yolo export model=yolo26n-seg.pt  format=engine device=0 half=True
```

**Expected output files:**
```
~/ultralytics_data/
├── yolo26n.pt            ← source model (keep)
├── yolo26n.engine        ← TensorRT engine (FP16)
├── yolo26n-pose.pt
├── yolo26n-pose.engine
├── yolo26n-seg.pt
└── yolo26n-seg.engine
```

---

## §9 Run the dual camera system

```bash
conda activate yolov26
cd ~/yolov26_jetson

# Optional: enable maximum performance
sudo nvpmodel -m 0
sudo jetson_clocks

# Launch
bash run_dual_camera_local.sh
```

**System layout:**
- Camera 0: Object detection (every frame) + Pose estimation (every 2 frames)
- Camera 1: Object detection (every frame) + Segmentation (every 5 frames)
- Display: OpenCV window
- Inference: FP16 TensorRT engines

**Expected performance on Orin NX 16GB:**

| Task | Latency | FPS |
|------|---------|-----|
| Detection (engine) | ~20-30 ms | >30 |
| Pose (engine) | ~25-35 ms | >25 |
| Segmentation (engine) | ~30-40 ms | >20 |

---

## §10 Performance monitoring

```bash
# Real-time Jetson stats (GPU/CPU/memory)
tegrastats

# Check thermal state
cat /sys/devices/virtual/thermal/thermal_zone*/temp | awk '{print $1/1000 "°C"}'

# Check power mode
sudo nvpmodel -q
```
