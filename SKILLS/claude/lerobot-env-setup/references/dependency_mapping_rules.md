# Dependency Mapping Rules — LeRobot on Jetson

Mandatory rules derived from validated install. Violating any of these will break CUDA or cause import conflicts.

---

## Rule 1: torch source — Jetson wheel, not PyPI

```
torch source = Seeed SharePoint wheel (cp310, linux_aarch64)
  torch: 2.8.0a0+gitba56102
  torchvision: 0.23.0

NEVER use:
  pip install torch           ← CPU-only PyPI wheel
  pip install torch --index-url https://pypi.jetson-ai-lab.dev/...  ← different build
```

---

## Rule 2: mandatory install order (torch wrap-around)

```
ORDER:
  1. pip install torch wheel
  2. pip install torchvision wheel
  3. conda install opencv → conda remove opencv → pip install opencv-python==4.10.0.84
  4. conda install ffmpeg
  5. conda uninstall numpy → pip install numpy==1.26.0
  6. pip install -e ".[feetech]"        ← OVERWRITES torch with CPU wheel
  7. pip install torch wheel            ← MANDATORY REINSTALL
  8. pip install torchvision wheel      ← MANDATORY REINSTALL
  9. pip install numpy==1.26.0          ← MANDATORY REINSTALL
```

Steps 7–9 are not optional. The editable install at step 6 silently downgrades torch.

---

## Rule 3: numpy version lock

```
Pin: numpy==1.26.0

Reason:
  opencv-python 4.10.0.84 compiled against numpy 1.x ABI
  numpy 2.x breaks cv2 import with AttributeError: _ARRAY_API

NEVER let pip resolve numpy freely — always pin after editable install.
```

---

## Rule 4: OpenCV install sequence

```
Step A: conda install -y -c conda-forge "opencv>=4.10.0.84"
  (pulls in system codec libraries as conda deps)
Step B: conda remove -y opencv
  (removes the conda-managed Python binding)
Step C: pip3 install opencv-python==4.10.0.84
  (installs pinned version using the system libs from Step A)

DO NOT skip Step A — the conda install is needed to pull libGL, libgthread, etc.
DO NOT skip Step B — leaving the conda binding causes a double-import conflict.
```

---

## Rule 5: ffmpeg source

```
Source: conda-forge (NOT system apt, NOT pip)

Reason: conda-forge ffmpeg links against conda env libs, avoiding NVMM conflicts.

Default: conda install -y -c conda-forge ffmpeg
Fallback (libsvtav1 error): conda install -y ffmpeg=7.1.1 -c conda-forge
```

---

## Rule 6: lerobot repository

```
Repo: https://github.com/Seeed-Projects/lerobot.git
NOT:  https://github.com/huggingface/lerobot.git

Extras:
  SO-ARM / FashionStar:  pip install -e ".[feetech]"
  Fashionstar dual-arm add-on:
    pip install lerobot_teleoperator_bimanual_leader
    pip install lerobot_robot_bimanual_follower
```

---

## Rule 7: serial port

```
Remove conflicting service first:
  sudo apt remove brltty

Group membership (for interactive use):
  sudo usermod -aG dialout $USER

Permanent udev rule (recommended, no re-login needed):
  KERNEL=="ttyUSB[0-9]*", MODE="0666"
  KERNEL=="ttyACM[0-9]*", MODE="0666"
```
