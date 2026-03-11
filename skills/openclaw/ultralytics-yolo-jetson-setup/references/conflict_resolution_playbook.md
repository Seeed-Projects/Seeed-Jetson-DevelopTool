# Conflict Resolution Playbook — Ultralytics YOLO on Jetson

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
conda activate <ENV>
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

## F2: CUDA NMS error during inference

**Symptom**
```
Could not run 'torchvision::nms' with arguments from the 'CUDA' backend
```

**Root cause**
The torchvision wheel from SharePoint is compiled without the CUDA NMS kernel.
ultralytics calls `torchvision.ops.nms` with GPU tensors for post-processing —
even for TensorRT `.engine` files, because ultralytics applies a confidence
filtering pass after the TRT forward pass.

**Fix**
Re-run phase torch-pre to re-apply the CUDA NMS patch:
```bash
bash ~/.agents/skills/ultralytics-jetson-setup/scripts/install_ultralytics.sh \
  --env <ENV> --phase torch-pre
```

Or manually:
```bash
TV_SITE=$(conda run -n <ENV> python3 -c 'import site; print(site.getsitepackages()[0])')
cp ~/vision/build/lib.linux-aarch64-3.10/torchvision/_C.so \
   $TV_SITE/torchvision/_C.so
```

**Verify**
```bash
conda run -n <ENV> python3 -c "
import torch
from torchvision.ops import nms
b = torch.tensor([[0.,0.,1.,1.],[0.1,0.1,1.1,1.1]]).cuda()
s = torch.tensor([0.9,0.8]).cuda()
print('CUDA NMS OK:', nms(b,s,0.5).tolist())
"
```

---

## F3: numpy import conflict / AttributeError: _ARRAY_API

**Symptom**
```
AttributeError: _ARRAY_API not found
ImportError: numpy.core.multiarray failed to import
```

**Root cause**
numpy 2.x installed; opencv-python 4.10.0.84 requires numpy 1.x ABI.

**Fix**
```bash
pip install numpy==1.26.0
```

**Verify**
```bash
python3 -c "import numpy as np, cv2; print(np.__version__, cv2.__version__)"
# Expected: 1.26.x  4.10.0
```

---

## F4: OpenCV import conflict

**Symptom**
```
ImportError: /path/to/cv2.so: undefined symbol ...
```

**Root cause**
conda opencv and pip opencv-python both installed simultaneously.

**Fix**
```bash
conda remove -y opencv
pip install opencv-python==4.10.0.84
pip install numpy==1.26.0
```

**Verify**
```bash
python3 -c "import cv2; print(cv2.__version__)"
# Expected: 4.10.0
```

---

## F5: Camera permission denied

**Symptom**
```
cv2.error: Can't open camera by index
/dev/video0: Permission denied
```

**Fix**
```bash
sudo usermod -aG video $USER
sudo tee /etc/udev/rules.d/99-usb-cameras.rules > /dev/null <<'EOF'
KERNEL=="video[0-9]*", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="046d", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="05a3", MODE="0666"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger
```

**Verify**
```bash
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('opened:', cap.isOpened()); cap.release()"
```

---

## F6: TensorRT engine export failure

**Symptom**
```
yolo export ... fails with onnxruntime or TensorRT error
```

**Root cause**
onnxruntime-gpu not installed, or torch overwritten by CPU wheel before export.

**Fix**
```bash
# Reinstall GPU wheels first
pip install ~/wheels/torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl
pip install ~/wheels/torchvision-0.23.0-cp310-cp310-linux_aarch64.whl
# Re-export
cd ~/ultralytics_data
yolo export model=<model>.pt format=engine device=0 half=True
```

---

## F7: Python upgraded silently (3.10 → 3.14) during install

**Symptom**
```
torch-2.8.0...cp310...whl is not a supported wheel on this platform
# Python shows 3.14.x instead of 3.10
```

**Root cause**
`conda install opencv` in an existing env can upgrade Python as a side effect.
This skill uses pip-only opencv install to avoid this.
If it still happens (e.g., an older version of the skill was run), the env must be recreated.

**Fix**
```bash
conda env remove -n <ENV>
# Re-run from phase env
bash ~/.agents/skills/ultralytics-jetson-setup/scripts/install_ultralytics.sh \
  --env <ENV> --phase all
```

**Verify**
```bash
conda run -n <ENV> python3 --version
# Expected: Python 3.10.x
```
