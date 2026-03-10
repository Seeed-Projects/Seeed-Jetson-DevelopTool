# Conflict Resolution Playbook — YOLOv26 on Jetson

Format: symptom → root cause → fix → verify

---

## F1: torch.cuda.is_available() → False

**Symptom**
```
CUDA available: False
```

**Root cause**
`pip install ultralytics[export]` pulled CPU-only torch from PyPI, overwriting the Jetson GPU wheel.

**Fix**
```bash
conda activate yolov26
pip install ~/wheels/torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl
pip install ~/wheels/torchvision-0.23.0-cp310-cp310-linux_aarch64.whl
pip install numpy==1.26.0
```

**Verify**
```bash
python3 -c "import torch; print(torch.cuda.is_available(), torch.__version__)"
# Expected: True  2.8.0a0+gitba56102
```

---

## F2: CUDA NMS not available in torchvision

**Symptom**
```
Could not run 'torchvision::nms' with arguments from the 'CUDA' backend
```

**Impact**
- **`.engine` (TensorRT) inference**: ✅ **Not affected** — TensorRT handles NMS internally inside the engine graph.
- **`.pt` (PyTorch) inference**: ⚠️ Falls back to CPU NMS — slower but functional.

**Root cause**
torchvision was built from source (e.g. `/opt/torchvision/`) without the CUDA NMS kernel,
or was overwritten by a PyPI build that lacks CUDA NMS compilation.

**Fix**
```bash
conda activate yolov26
pip install ~/wheels/torchvision-0.23.0-cp310-cp310-linux_aarch64.whl
```

**Verify**
```bash
python3 - <<'EOF'
import torch, torchvision
from torchvision.ops import nms
boxes  = torch.tensor([[0.0, 0.0, 1.0, 1.0], [0.1, 0.1, 1.1, 1.1]]).cuda()
scores = torch.tensor([0.9, 0.8]).cuda()
keep   = nms(boxes, scores, 0.5)
print("CUDA NMS OK:", keep)
EOF
```

---

## F3: numpy import conflict / AttributeError: _ARRAY_API

**Symptom**
```
AttributeError: _ARRAY_API not found
# or
ImportError: numpy.core.multiarray failed to import
```

**Root cause**
numpy 2.x was installed; opencv-python 4.10.0.84 requires numpy 1.x ABI.

**Fix**
```bash
pip install numpy==1.26.0
```

**Verify**
```bash
python3 -c "import numpy as np, cv2; print(np.__version__, cv2.__version__)"
# Expected: 1.26.x  4.10.0.84
```

---

## F4: OpenCV import conflict / double-import crash

**Symptom**
```
ImportError: /path/to/cv2.so: undefined symbol ...
# or cv2 version mismatch between conda and pip builds
```

**Root cause**
Both conda opencv and pip opencv-python are installed simultaneously.

**Fix**
```bash
conda remove -y opencv
pip install opencv-python==4.10.0.84
pip install numpy==1.26.0   # pip may have upgraded it
```

**Verify**
```bash
python3 -c "import cv2; print(cv2.__version__)"
# Expected: 4.10.0.84
```

---

## F5: Camera permission denied

**Symptom**
```
cv2.error: ... Can't open camera by index
# or /dev/video0: Permission denied
```

**Root cause A**: User not in `video` group.
**Root cause B**: udev rules not applied.

**Fix**
```bash
# Add to video group
sudo usermod -aG video $USER

# Create permanent udev rule (no re-login needed)
sudo tee /etc/udev/rules.d/99-usb-cameras.rules > /dev/null <<'EOF'
KERNEL=="video[0-9]*", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="046d", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="05a3", MODE="0666"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger
```

**Verify**
```bash
ls -l /dev/video*
# Expected: crw-rw-rw- (mode 0666)
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('opened:', cap.isOpened()); cap.release()"
```

---

## F6: TensorRT engine export failure

**Symptom**
```
yolo export ... fails with onnxruntime or TensorRT error
# or [TRT] engine build error
```

**Root cause**
onnxruntime-gpu not installed, or torch/torchvision overwritten by CPU wheel before export.

**Fix**
```bash
conda activate yolov26
pip install ~/wheels/torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl
pip install ~/wheels/torchvision-0.23.0-cp310-cp310-linux_aarch64.whl
pip install ~/wheels/onnxruntime_gpu-1.23.0-cp310-cp310-linux_aarch64.whl
```

Then re-export:
```bash
cd ~/ultralytics_data
yolo export model=yolo26n.pt format=engine device=0 half=True
```

**Verify**
```bash
python3 -c "import onnxruntime; print(onnxruntime.__version__)"
# Expected: 1.23.0
```

---

## F7: Low FPS / performance degradation

**Symptom**
```
Inference slower than expected; <10 FPS on Orin
```

**Root cause**
Jetson running in low-power mode, or using .pt models instead of .engine files.

**Fix**
```bash
# Set maximum performance mode
sudo nvpmodel -m 0
sudo jetson_clocks

# Verify TensorRT engines exist (not just .pt files)
ls ~/ultralytics_data/*.engine
# If missing, export them:
cd ~/ultralytics_data
yolo export model=yolo26n.pt      format=engine device=0 half=True
yolo export model=yolo26n-pose.pt format=engine device=0 half=True
yolo export model=yolo26n-seg.pt  format=engine device=0 half=True
```

**Verify**
```bash
tegrastats | head -5
# GPU should show high utilization during inference
```

**Expected performance on Orin (FP16 engines)**

| Model | Expected latency | Expected FPS |
|-------|-----------------|-------------|
| yolo26n (detect) | ~20-30 ms | >30 FPS |
| yolo26n-pose | ~25-35 ms | >25 FPS |
| yolo26n-seg | ~30-40 ms | >20 FPS |
