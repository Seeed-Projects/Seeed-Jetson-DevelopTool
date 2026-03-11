# Dependency Mapping Rules — Ultralytics YOLO on Jetson

These rules define the **required install order** and **version constraints**.
The install script (`install_ultralytics.sh`) enforces all of them automatically.

---

## Rule 1 — torch must be installed BEFORE and AFTER `pip install ultralytics[export]`

`pip install ultralytics[export]` pulls CPU-only `torch` from PyPI as a dependency.
This silently overwrites the Jetson GPU wheel.

**Required sequence (phases torch-pre → deps → torch-post):**
1. `pip install torch-2.8.0a0...whl` (phase torch-pre)
2. `pip install torchvision-0.23.0...whl` (phase torch-pre)
3. `pip install ultralytics[export]` (phase deps — overwrites torch)
4. `pip install torch-2.8.0a0...whl` again (phase torch-post — restore GPU wheel)
5. `pip install torchvision-0.23.0...whl` again (phase torch-post)

---

## Rule 2 — torchvision CUDA NMS patch must be applied after every torchvision install

The SharePoint `torchvision-0.23.0-cp310-cp310-linux_aarch64.whl` was compiled
**without the CUDA NMS kernel** (`torchvision._C`). Every time the wheel is installed
or reinstalled it overwrites `_C.so` with a stub version.

**Required after every torchvision wheel install:**
```bash
cp ~/vision/build/lib.linux-aarch64-3.10/torchvision/_C.so \
   $CONDA_ENV_SITE/torchvision/_C.so
```

Source: `~/vision/build/lib.linux-aarch64-3.10/torchvision/_C.so`
(compiled from source with `-DCMAKE_CUDA_ARCHITECTURES=87`).

Why needed even for `.engine` files: ultralytics applies a confidence-filter NMS
pass (`ultralytics/utils/ops.py`) using `torchvision.ops.nms` with GPU tensors
**after** every TensorRT forward pass.

---

## Rule 3 — numpy must be pinned to 1.26.x

| Version | Status |
|---------|--------|
| numpy 1.x (1.26.0) | ✅ Required |
| numpy 2.x | ❌ Breaks opencv-python 4.10 (ABI mismatch: `_ARRAY_API not found`) |

`pip install ultralytics[export]` may pull numpy 2.x. Pin explicitly:
```bash
pip install numpy==1.26.0
```

---

## Rule 4 — opencv must be installed via pip, NOT conda

`conda install opencv` silently upgrades Python as a dependency resolution side effect
(observed: 3.10 → 3.14). The torch/torchvision wheels are `cp310` only — a Python
upgrade breaks the entire environment irreversibly.

**Required:**
```bash
pip install opencv-python==4.10.0.84
```

**Never:**
```bash
conda install opencv  # DO NOT USE
```

---

## Rule 5 — onnxruntime-gpu must be sourced from local wheel, not GitHub

The GitHub Releases URL for `onnxruntime_gpu-*.whl` (aarch64, JetPack 6) returns
HTTP 403 via `pip install` due to asset size redirect restrictions.

**Required:** Place the `.whl` file manually in `~/wheels/` before running phase deps.
The script searches:
1. `~/wheels/onnxruntime_gpu-*.whl`
2. `~/wheel/onnxruntime_gpu-*.whl`

If not found, phase deps logs a warning and skips onnxruntime (inference still works
via TensorRT backend; onnxruntime is only needed for ONNX format inference).

---

## Rule 6 — system TensorRT must be linked into the conda env via .pth

System TensorRT 10.3.0 is installed at:
```
/usr/lib/python3.10/dist-packages/tensorrt*
/usr/lib/python3.10/dist-packages/tensorrt_libs/
```

`pip install ultralytics[export]` installs PyPI `tensorrt` (targets CUDA 13, ~2.5 GB)
which is incompatible with Jetson TensorRT 10.3.0 and wastes disk space.

**Required:** Write a `.pth` file into the conda env site-packages **before**
`pip install ultralytics[export]`:
```bash
echo "/usr/lib/python3.10/dist-packages" \
  > $CONDA_ENV_SITE/system_tensorrt.pth
```

This makes `import tensorrt` resolve to system TRT and prevents ultralytics from
triggering the PyPI install.

---

## Rule 7 — `conda install` must not be used for any package in this env

Any `conda install` command can trigger Python version upgrades as part of
dependency resolution. All packages must be installed via `pip` or direct
wheel installation.

**Exceptions:**
- `conda create -n ENV python=3.10` (env creation only)
- `conda env remove` (env deletion only)

---

## Rule 8 — All pip installs must use PYTHONNOUSERSITE=1

Jetson systems often have packages pre-installed in `~/.local/lib/python3.10/site-packages`
(user site-packages). When `conda run -n ENV pip install` runs, pip can see these packages
and either skip installation (treating them as "already satisfied") or install back to
`~/.local` instead of the conda env.

**Required:** prefix every `pip install` inside the install script with `PYTHONNOUSERSITE=1`:
```bash
PYTHONNOUSERSITE=1 conda run -n ENV pip install <package>
```

**Also required for torchvision:** use `--no-deps` to prevent pip from pulling torch from PyPI
as a dependency (which would overwrite the Jetson GPU wheel):
```bash
PYTHONNOUSERSITE=1 conda run -n ENV pip install --no-deps torchvision-*.whl
```

---

## Rule 9 — Use a PyPI mirror for faster installs (optional but recommended in China)

Default PyPI can be slow. Set `PIP_MIRROR` at the top of the install script:
```bash
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
```

Then pass it to all PyPI installs:
```bash
PYTHONNOUSERSITE=1 conda run -n ENV pip install ${PIP_MIRROR:+-i "$PIP_MIRROR"} <package>
```

Local wheel installs (`~/wheels/*.whl`) do NOT need the mirror flag.

---

## Rule 10 — TensorRT engines are device-specific, always export on target

TRT engines are compiled for the specific GPU architecture (SM 8.7 for Orin).
An engine exported on one Jetson Orin will work on another Orin but **not** on
a non-Orin GPU or a different CUDA / TRT version.

**Required:**
```bash
# Always run on the target Jetson, never cross-compile
yolo export model=<model>.pt format=engine device=0 half=True
```

---

## Install order summary

```
Phase env       conda create python=3.10
                libcusparselt0 (apt/deb)
                [yolo26 only] git clone yolov26_jetson

Phase download  download_wheels.py → ~/wheels/torch-*.whl + torchvision-*.whl

Phase torch-pre PYTHONNOUSERSITE=1 pip install torch wheel          ← Rule 8
                PYTHONNOUSERSITE=1 pip install --no-deps torchvision wheel  ← Rule 8
                patch_cuda_nms()    ← Rule 2
                verify CUDA

Phase deps      PYTHONNOUSERSITE=1 pip install onnxruntime (local wheel)  ← Rule 5, 8
                PYTHONNOUSERSITE=1 pip install numpy==1.26.0               ← Rule 3, 8
                PYTHONNOUSERSITE=1 pip install opencv-python==4.10.0.84    ← Rule 4, 8
                write system_tensorrt.pth                                  ← Rule 6
                PYTHONNOUSERSITE=1 pip install ultralytics[export]         ← Rule 1, 8, 9

Phase torch-post PYTHONNOUSERSITE=1 pip install torch wheel (restore)     ← Rule 1, 8
                 PYTHONNOUSERSITE=1 pip install --no-deps torchvision wheel ← Rule 8
                 PYTHONNOUSERSITE=1 pip install numpy==1.26.0
                 patch_cuda_nms()                                          ← Rule 2
                 validate all checks
```
