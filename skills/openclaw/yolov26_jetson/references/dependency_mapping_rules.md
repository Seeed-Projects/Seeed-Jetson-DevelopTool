# Dependency Mapping Rules — YOLOv26 on Jetson

Mandatory rules derived from validated install. Violating any of these will break CUDA or cause import conflicts.

---

## Rule 1: torch source — Jetson wheel, not PyPI

```
torch source = Seeed SharePoint wheel (cp310, linux_aarch64)
  torch:       2.8.0a0+gitba56102
  torchvision: 0.23.0

NEVER use:
  pip install torch              ← CPU-only PyPI wheel
  pip install torch --index-url https://pypi.jetson-ai-lab.dev/...  ← different build
```

---

## Rule 2: torchvision source — Jetson wheel with CUDA NMS

```
torchvision source = Seeed SharePoint wheel (cp310, linux_aarch64)
  torchvision: 0.23.0  (compiled with CUDA NMS support)

NEVER use:
  pip install torchvision        ← PyPI build lacks CUDA NMS
  conda install torchvision      ← wrong build for Jetson

Why CUDA NMS matters:
  YOLOv26 TensorRT engines dispatch post-processing to torchvision::nms.
  If the CUDA backend is missing, inference falls back to CPU and raises:
  "Could not run 'torchvision::nms' with arguments from the 'CUDA' backend"
```

---

## Rule 3: mandatory install order (torch wrap-around)

```
ORDER:
  1.  conda create -n yolov26 python=3.10
  2.  git clone yolov26_jetson repo
  3.  apt/dpkg install libcusparselt0
  4.  pip install torch wheel           (Jetson GPU wheel)
  5.  pip install torchvision wheel     (Jetson wheel with CUDA NMS)
  6.  VERIFY: torch.cuda.is_available() == True  ← hard stop if False
  7.  pip install onnxruntime-gpu wheel
  8.  pip install numpy==1.26.0
  9.  conda install opencv → conda remove opencv → pip install opencv-python==4.10.0.84
  10. pip install ultralytics[export]   ← OVERWRITES torch with CPU wheel
  11. pip install torch wheel           ← MANDATORY REINSTALL
  12. pip install torchvision wheel     ← MANDATORY REINSTALL
  13. pip install numpy==1.26.0         ← MANDATORY REINSTALL
  14. VERIFY: CUDA + NMS CUDA + all versions
```

Steps 11–13 are not optional. `ultralytics[export]` silently downgrades torch.

---

## Rule 4: numpy version lock

```
Pin: numpy==1.26.0

Reason:
  opencv-python 4.10.0.84 compiled against numpy 1.x ABI
  numpy 2.x breaks cv2 import with AttributeError: _ARRAY_API

NEVER let pip resolve numpy freely — always reinstall after ultralytics install.
```

---

## Rule 5: OpenCV install sequence

```
Step A: conda install -y -c conda-forge "opencv>=4.10.0.84"
  (pulls in system codec libraries and libGL as conda deps)
Step B: conda remove -y opencv
  (removes the conda-managed Python binding to avoid double-import)
Step C: pip install opencv-python==4.10.0.84
  (installs pinned version using the system libs from Step A)

DO NOT skip Step A — the conda install is needed to pull libGL, libgthread, etc.
DO NOT skip Step B — leaving the conda binding causes a symbol conflict at import.
```

---

## Rule 6: onnxruntime source — GPU wheel, not CPU

```
Source: GitHub Releases (ultralytics/assets)
  onnxruntime_gpu-1.23.0-cp310-cp310-linux_aarch64.whl

NEVER use:
  pip install onnxruntime          ← CPU-only build
  pip install onnxruntime-gpu      ← resolves PyPI ARM64 build (may lack CUDA EP)

Why:
  yolo export format=engine requires onnxruntime with CUDA Execution Provider.
  The CPU build causes TensorRT export to silently skip CUDA graph optimization.
```

---

## Rule 7: libcusparselt0 system library

```
Required by: torch 2.8.0a0 on JetPack 6.0 (CUDA 12.2)
Version: 0.6.2.3

Install sources (in priority order):
  1. ~/yolov26_jetson/libcusparselt0_0.6.2.3-1_arm64.deb  (bundled in repo)
  2. sudo apt-get install libcusparselt0

Must be installed BEFORE torch wheel install — torch import will fail otherwise.
```

---

## Rule 8: TensorRT engine portability

```
TensorRT engines are device-specific:
  - Built for Orin (sm_87) — will NOT run on Xavier (sm_72) or Nano (sm_53)
  - Built with JetPack 6.0 TensorRT — may warn on JetPack 6.1+

Always export engines on the TARGET device:
  yolo export model=yolo26n.pt format=engine device=0 half=True

Source .pt models are portable — keep them as the master copy.
```
