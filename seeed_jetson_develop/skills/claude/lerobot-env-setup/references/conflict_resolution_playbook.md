# Conflict Resolution Playbook — LeRobot on Jetson

Format: symptom → root cause → fix → verify

---

## F1: torch.cuda.is_available() → False

**Symptom**
```
CUDA available: False
```

**Root cause**
`pip install -e .` pulled CPU-only torch from PyPI, overwriting the Jetson wheel.

**Fix**
```bash
conda activate lerobot
pip install torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl
pip install torchvision-0.23.0-cp310-cp310-linux_aarch64.whl
```

**Verify**
```bash
python3 -c "import torch; print(torch.cuda.is_available(), torch.__version__)"
# Expected: True  2.8.0a0+gitba56102
```

---

## F2: numpy import conflict / AttributeError: _ARRAY_API

**Symptom**
```
AttributeError: _ARRAY_API not found
# or
ImportError: numpy.core.multiarray failed to import
```

**Root cause**
numpy 2.x installed; opencv-python 4.10.0.84 requires numpy 1.x ABI.

**Fix**
```bash
pip3 install numpy==1.26.0
```

**Verify**
```bash
python3 -c "import numpy as np, cv2; print(np.__version__, cv2.__version__)"
# Expected: 1.26.x  4.10.0.84
```

---

## F3: OpenCV import conflict / double-import crash

**Symptom**
```
ImportError: /path/to/cv2.so: undefined symbol ...
# or cv2 version mismatch between conda and pip builds
```

**Root cause**
Both conda opencv and pip opencv-python installed simultaneously.

**Fix**
```bash
conda remove -y opencv
pip3 install opencv-python==4.10.0.84
pip3 install numpy==1.26.0   # reinstall — pip may upgrade it
```

**Verify**
```bash
python3 -c "import cv2; print(cv2.__version__)"
# Expected: 4.10.0.84
```

---

## F4: ffmpeg libsvtav1 error

**Symptom**
```
ffmpeg: error while loading shared libraries: libsvtav1.so.x
# or ffmpeg codec initialization failure
```

**Root cause**
Default conda-forge ffmpeg version links against libsvtav1 not present in the Jetson environment.

**Fix**
```bash
conda install -y ffmpeg=7.1.1 -c conda-forge
```

**Verify**
```bash
ffmpeg -version | head -1
# Expected: ffmpeg version 7.1.1-...
```

---

## F5: rerun.scalar missing / AttributeError on rerun

**Symptom**
```
AttributeError: module 'rerun' has no attribute 'scalar'
```

**Root cause**
Wrong version of `rerun-sdk` installed by lerobot editable install.

**Fix**
```bash
pip install rerun-sdk==0.19.1
```

**Verify**
```bash
python3 -c "import rerun; print(rerun.__version__)"
# Expected: 0.19.1
```

---

## F6: libtiff error (Fashionstar dual-arm)

**Symptom**
```
ImportError: libtiff.so.x: cannot open shared object file
# or tifffile import failure
```

**Root cause**
tifffile version incompatibility on Fashionstar dual-arm setup.

**Fix**
```bash
pip install --upgrade tifffile
```

**Verify**
```bash
python3 -c "import tifffile; print(tifffile.__version__)"
```

---

## F7: Permission denied on /dev/ttyUSB* or /dev/ttyACM*

**Symptom**
```
serial.serialutil.SerialException: [Errno 13] Permission denied: '/dev/ttyUSB0'
# or device not found
```

**Root cause A**: `brltty` service claims ttyUSB devices on boot.
**Root cause B**: User not in `dialout` group.

**Fix**
```bash
# Remove brltty (root cause A)
sudo apt remove brltty

# Add to group (root cause B)
sudo usermod -aG dialout $USER

# Permanent udev rule — takes effect immediately, no re-login
sudo tee /etc/udev/rules.d/99-serial-ports.rules > /dev/null <<'EOF'
KERNEL=="ttyUSB[0-9]*", MODE="0666"
KERNEL=="ttyACM[0-9]*", MODE="0666"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
```

**Verify**
```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
# Expected: crw-rw-rw- (mode 0666) or crw-rw---- group=dialout
python3 -c "import serial; s = serial.Serial('/dev/ttyUSB0', 1000000); s.close(); print('ok')"
```
