#!/usr/bin/env bash
# install_ultralytics.sh
# Full Ultralytics YOLO install on Jetson in strict order.
# Supports model families: yolov8 | yolo11 | yolo26
#
# Usage:
#   bash install_ultralytics.sh [--env ENV] [--wheel-dir DIR] \
#                               [--model-family FAMILY] [--phase PHASE]
#
# Phases (run in order):
#   env        — Step 1: create conda env (python=3.10), Step 2: family-specific setup, Step 3: cuSPARSELt
#   download   — Step 4: download torch/torchvision wheels (~900 MB, shows progress)
#   torch-pre  — Step 5: install torch wheels + CUDA NMS patch + verify CUDA
#   deps       — Step 6: onnxruntime-gpu, Step 7: numpy, Step 8: opencv,
#                Step 9: system TRT link, Step 10: ultralytics
#   torch-post — Step 11: reinstall torch wheels (mandatory), Step 12: final validation
#   all        — run all phases in order

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
ENV_NAME="ultralytics"
WHEEL_DIR="$HOME/wheels"
MODEL_FAMILY="yolo11"
MODEL_DIR="$HOME/ultralytics_data"
PHASE="all"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

TORCH_WHL="torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl"
TV_WHL="torchvision-0.23.0-cp310-cp310-linux_aarch64.whl"
ORT_SEARCH_DIRS=("$HOME/wheels" "$HOME/wheel")

# PyPI mirror — speeds up pip installs in China; set to "" to use default PyPI
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

# ── Args ──────────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)           ENV_NAME="$2";     shift 2 ;;
    --wheel-dir)     WHEEL_DIR="$2";    shift 2 ;;
    --model-family)  MODEL_FAMILY="$2"; shift 2 ;;
    --model-dir)     MODEL_DIR="$2";    shift 2 ;;
    --phase)         PHASE="$2";        shift 2 ;;
    *) echo "[error] Unknown arg: $1"; exit 1 ;;
  esac
done

# Validate model family
case "$MODEL_FAMILY" in
  yolov8|yolo11|yolo26) ;;
  *) echo "[error] Unknown --model-family: $MODEL_FAMILY. Valid: yolov8 | yolo11 | yolo26"; exit 1 ;;
esac

TORCH_WHL_PATH="$WHEEL_DIR/$TORCH_WHL"
TV_WHL_PATH="$WHEEL_DIR/$TV_WHL"

log()  { echo "[install] $*"; }
die()  { echo "[STOP]    $*" >&2; exit 1; }

log "ENV=$ENV_NAME  FAMILY=$MODEL_FAMILY  WHEEL_DIR=$WHEEL_DIR  PHASE=$PHASE"

# ── Conda auto-detect ─────────────────────────────────────────────────────────
CONDA_BIN=""
for _p in \
  "$(command -v conda 2>/dev/null)" \
  "$HOME/miniconda3/bin/conda" \
  "$HOME/anaconda3/bin/conda" \
  "$HOME/miniforge3/bin/conda" \
  "$HOME/mambaforge/bin/conda" \
  "/opt/conda/bin/conda" \
  "/usr/local/conda/bin/conda"; do
  if [[ -n "$_p" && -x "$_p" ]]; then
    CONDA_BIN="$_p"
    break
  fi
done
[[ -z "$CONDA_BIN" ]] && die "conda not found. Install Miniconda first:
  wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
  bash Miniconda3-latest-Linux-aarch64.sh"
log "conda found: $CONDA_BIN"

# ── Helper: CUDA NMS patch ────────────────────────────────────────────────────
patch_cuda_nms() {
  # Find where torchvision is ACTUALLY installed — use pip show (no import needed)
  local tv_site tv_dir
  tv_site=$(PYTHONNOUSERSITE=1 "$CONDA_BIN" run -n "$ENV_NAME" \
    pip show torchvision 2>/dev/null | awk '/^Location:/ {print $2}') || true
  tv_dir="$tv_site/torchvision"
  if [[ -z "$tv_site" || ! -d "$tv_dir" ]]; then
    log "WARN: could not locate torchvision install dir — skipping patch"
    return 0
  fi
  local local_so=""
  for _d in \
    "$HOME/vision/build/lib.linux-aarch64-3.10" \
    "$HOME/vision/build/lib.linux-aarch64-cpython-310"; do
    if [[ -f "$_d/torchvision/_C.so" ]]; then
      local_so="$_d"
      break
    fi
  done
  if [[ -n "$local_so" ]]; then
    log "Patching torchvision _C.so with CUDA-NMS build from $local_so"
    cp "$local_so/torchvision/_C.so"    "$tv_dir/_C.so"
    [[ -f "$local_so/torchvision/image.so" ]] && \
      cp "$local_so/torchvision/image.so" "$tv_dir/image.so"
  else
    log "Local CUDA-NMS torchvision not found at ~/vision/build/ — skipping patch"
    log "  torchvision NMS will fall back to CPU; TensorRT .engine inference still works."
  fi
}

# ── Phase: env ────────────────────────────────────────────────────────────────
phase_env() {
  # Step 1: conda env (python=3.10 required for cp310 wheels)
  if "$CONDA_BIN" env list | grep -q "^${ENV_NAME} "; then
    EXISTING_PY=$("$CONDA_BIN" run -n "$ENV_NAME" python3 --version 2>/dev/null \
      | grep -oP '\d+\.\d+' | head -1)
    if [[ "$EXISTING_PY" == "3.10" ]]; then
      log "Step 1: conda env '$ENV_NAME' (Python 3.10) already exists — skip"
    else
      log "Step 1: conda env '$ENV_NAME' has Python $EXISTING_PY (need 3.10) — recreating"
      "$CONDA_BIN" env remove -y -n "$ENV_NAME"
      "$CONDA_BIN" create -y -n "$ENV_NAME" python=3.10
    fi
  else
    log "Step 1: creating conda env '$ENV_NAME' python=3.10"
    "$CONDA_BIN" create -y -n "$ENV_NAME" python=3.10
  fi

  # Step 2: family-specific setup
  log "Step 2: family-specific setup ($MODEL_FAMILY)"
  if [[ "$MODEL_FAMILY" == "yolo26" ]]; then
    local YOLO26_DIR="$HOME/yolov26_jetson"
    if [[ -d "$YOLO26_DIR" ]]; then
      log "Step 2: $YOLO26_DIR already exists — skip clone"
    else
      log "Step 2: cloning yolov26_jetson to $YOLO26_DIR"
      git clone https://github.com/bleaaach/yolov26_jetson.git "$YOLO26_DIR"
    fi
    # Copy models to shared model dir if needed
    if [[ -d "$YOLO26_DIR/ultralytics_data" && ! -f "$MODEL_DIR/yolo26n.pt" ]]; then
      log "Step 2: copying yolo26 model files to $MODEL_DIR"
      mkdir -p "$MODEL_DIR"
      cp "$YOLO26_DIR/ultralytics_data/"*.pt "$MODEL_DIR/" 2>/dev/null || true
      cp "$YOLO26_DIR/ultralytics_data/"*.engine "$MODEL_DIR/" 2>/dev/null || true
    fi
  fi

  # Step 2b: create shared model directory
  if [[ -d "$MODEL_DIR" ]]; then
    log "Step 2b: model dir $MODEL_DIR already exists — skip"
  else
    log "Step 2b: creating model dir $MODEL_DIR"
    mkdir -p "$MODEL_DIR"
  fi

  # Step 3: libcusparselt0 (required by torch 2.8 on JetPack 6.0)
  if dpkg -l libcusparselt0 2>/dev/null | grep -q '^ii'; then
    log "Step 3: libcusparselt0 already installed — skip"
  else
    log "Step 3: installing libcusparselt0"
    local LOCAL_DEB="$HOME/yolov26_jetson/libcusparselt0_0.6.2.3-1_arm64.deb"
    if [[ -f "$LOCAL_DEB" ]]; then
      sudo dpkg -i "$LOCAL_DEB" || sudo apt-get install -f -y
    else
      sudo apt-get update -qq && sudo apt-get install -y libcusparselt0
    fi
  fi

  log "Phase env done."
}

# ── Phase: download ────────────────────────────────────────────────────────────
phase_download() {
  if [[ -f "$TORCH_WHL_PATH" && -f "$TV_WHL_PATH" ]]; then
    log "Step 4: torch and torchvision wheels already in $WHEEL_DIR — skip download"
  else
    log "Step 4: downloading Jetson wheel files to $WHEEL_DIR (this takes 15-25 min)"
    PYTHONNOUSERSITE=1 "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet \
      ${PIP_MIRROR:+-i "$PIP_MIRROR"} requests
    "$CONDA_BIN" run -n "$ENV_NAME" python3 \
      "$SKILL_DIR/scripts/download_wheels.py" --dest "$WHEEL_DIR" \
      || die "wheel download failed — SharePoint URLs may have expired.
  Place wheels manually in $WHEEL_DIR and re-run this phase."
    [[ -f "$TORCH_WHL_PATH" ]] || die "torch wheel not found: $TORCH_WHL_PATH"
    [[ -f "$TV_WHL_PATH" ]]    || die "torchvision wheel not found: $TV_WHL_PATH"
  fi
  log "Phase download done."
}

# ── Phase: torch-pre ──────────────────────────────────────────────────────────
phase_torch_pre() {
  [[ -f "$TORCH_WHL_PATH" ]] || die "torch wheel missing — run phase 'download' first"
  [[ -f "$TV_WHL_PATH" ]]    || die "torchvision wheel missing — run phase 'download' first"

  log "Step 5: installing torch/torchvision GPU wheels"
  PYTHONNOUSERSITE=1 "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "$TORCH_WHL_PATH"
  PYTHONNOUSERSITE=1 "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet --no-deps "$TV_WHL_PATH"

  log "Step 5: verifying CUDA..."
  CUDA_OK=$("$CONDA_BIN" run -n "$ENV_NAME" \
    python3 -c "import torch; print(torch.cuda.is_available())" 2>/dev/null || echo "False")
  [[ "$CUDA_OK" == "True" ]] || die "torch.cuda.is_available() = False.
  Wheel may be corrupt. Fix: rm $WHEEL_DIR/*.whl then re-run phases 'download' and 'torch-pre'."
  log "Step 5: CUDA OK ✓"

  log "Step 5b: patching torchvision with CUDA-NMS build"
  patch_cuda_nms

  log "Phase torch-pre done."
}

# ── Phase: deps ───────────────────────────────────────────────────────────────
phase_deps() {
  # Step 6: onnxruntime-gpu (>= 1.22)
  if "$CONDA_BIN" run -n "$ENV_NAME" python3 -c \
      "import onnxruntime as o; v=tuple(int(x) for x in o.__version__.split('.')[:2]); assert v>=(1,22)" \
      2>/dev/null; then
    ORT_VER=$("$CONDA_BIN" run -n "$ENV_NAME" \
      python3 -c "import onnxruntime; print(onnxruntime.__version__)" 2>/dev/null || echo "?")
    log "Step 6: onnxruntime-gpu $ORT_VER already installed (>= 1.22) — skip"
  else
    ORT_WHL_FOUND=""
    for _dir in "${ORT_SEARCH_DIRS[@]}"; do
      _whl=$(ls "$_dir"/onnxruntime_gpu-*.whl 2>/dev/null | sort -V | tail -1) || true
      [[ -n "$_whl" ]] && { ORT_WHL_FOUND="$_whl"; break; }
    done
    if [[ -n "$ORT_WHL_FOUND" ]]; then
      log "Step 6: installing onnxruntime-gpu from $ORT_WHL_FOUND"
      PYTHONNOUSERSITE=1 "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "$ORT_WHL_FOUND"
    else
      log "Step 6: onnxruntime-gpu wheel not found — skipping (TensorRT inference still works)"
      log "  To enable ONNX inference: place onnxruntime_gpu-*.whl in $WHEEL_DIR and re-run phase deps"
    fi
  fi

  # Step 7: numpy
  if "$CONDA_BIN" run -n "$ENV_NAME" python3 -c \
      "import numpy as np; assert np.__version__.startswith('1.26')" 2>/dev/null; then
    log "Step 7: numpy 1.26.x already installed — skip"
  else
    log "Step 7: pinning numpy to 1.26.0"
    "$CONDA_BIN" run -n "$ENV_NAME" conda uninstall -y numpy 2>/dev/null || true
    PYTHONNOUSERSITE=1 "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet \
      ${PIP_MIRROR:+-i "$PIP_MIRROR"} numpy==1.26.0
  fi

  # Step 8: opencv (pip only — conda install can upgrade Python)
  if "$CONDA_BIN" run -n "$ENV_NAME" python3 -c \
      "import cv2; assert cv2.__version__ >= '4.10.0'" 2>/dev/null; then
    CV_VER=$("$CONDA_BIN" run -n "$ENV_NAME" \
      python3 -c "import cv2; print(cv2.__version__)" 2>/dev/null || echo "?")
    log "Step 8: opencv $CV_VER already installed (>= 4.10.0) — skip"
  else
    log "Step 8: installing opencv-python 4.10.0.84 (pip only)"
    PYTHONNOUSERSITE=1 "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet \
      ${PIP_MIRROR:+-i "$PIP_MIRROR"} opencv-python==4.10.0.84
  fi

  # Step 9: link system TensorRT into conda env
  CONDA_SITE=$("$CONDA_BIN" run -n "$ENV_NAME" python3 -c \
    'import site; print(site.getsitepackages()[0])' 2>/dev/null)
  PTH_FILE="$CONDA_SITE/jetpack-system.pth"
  SYSTEM_DIST="/usr/lib/python3.10/dist-packages"
  if [[ -f "$PTH_FILE" ]] && grep -q "$SYSTEM_DIST" "$PTH_FILE" 2>/dev/null; then
    log "Step 9: system TensorRT path already linked — skip"
  elif [[ -d "$SYSTEM_DIST/tensorrt" ]]; then
    log "Step 9: linking system TensorRT ($SYSTEM_DIST) into conda env"
    echo "$SYSTEM_DIST" > "$PTH_FILE"
  else
    log "Step 9: system TensorRT not found — skipping link"
    log "  If engine inference fails, verify JetPack TensorRT installation."
  fi

  # Step 10: ultralytics (may overwrite torch — torch-post fixes this)
  if "$CONDA_BIN" run -n "$ENV_NAME" python3 -c "import ultralytics" 2>/dev/null; then
    log "Step 10: ultralytics already installed — skip"
  else
    log "Step 10: installing ultralytics[export] (may take a few minutes)"
    PYTHONNOUSERSITE=1 "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet \
      ${PIP_MIRROR:+-i "$PIP_MIRROR"} "ultralytics[export]"
  fi

  log "Phase deps done."
}

# ── Phase: torch-post ─────────────────────────────────────────────────────────
phase_torch_post() {
  [[ -f "$TORCH_WHL_PATH" ]] || die "torch wheel missing: $TORCH_WHL_PATH"
  [[ -f "$TV_WHL_PATH" ]]    || die "torchvision wheel missing: $TV_WHL_PATH"

  log "Step 11: reinstalling torch/torchvision wheels (post-deps — mandatory)"
  PYTHONNOUSERSITE=1 "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "$TORCH_WHL_PATH"
  PYTHONNOUSERSITE=1 "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet --no-deps "$TV_WHL_PATH"
  PYTHONNOUSERSITE=1 "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet \
    ${PIP_MIRROR:+-i "$PIP_MIRROR"} numpy==1.26.0

  log "Step 11b: re-applying CUDA-NMS patch (post wheel reinstall)"
  patch_cuda_nms

  log "Step 12: final validation"
  _VALIDATE_PY=$(mktemp /tmp/ultralytics_validate_XXXXXX.py)
  cat > "$_VALIDATE_PY" <<PYEOF
import sys
import torch, torchvision, cv2, numpy as np, onnxruntime, ultralytics

ort_ver = tuple(int(x) for x in onnxruntime.__version__.split(".")[:2])

checks = {
    "CUDA available":      (torch.cuda.is_available(),         True),
    "torch version":       (torch.__version__,                 "2.8.0a0+gitba56102"),
    "torchvision version": (torchvision.__version__,           "0.23.0"),
    "numpy version":       (np.__version__.startswith("1.26"), True),
    "opencv >= 4.10.0":    (cv2.__version__ >= "4.10.0",       True),
    "onnxruntime >= 1.22": (ort_ver >= (1, 22),                True),
    "ultralytics present": (bool(ultralytics.__version__),     True),
}

ok = True
for name, (got, want) in checks.items():
    status = "\u2713" if got == want else "\u2717"
    print(f"  {status} {name}: {got}  (expected {want})")
    if got != want:
        ok = False

try:
    from torchvision.ops import nms
    boxes  = torch.tensor([[0.0, 0.0, 1.0, 1.0],
                            [0.1, 0.1, 1.1, 1.1]]).cuda()
    scores = torch.tensor([0.9, 0.8]).cuda()
    nms(boxes, scores, 0.5)
    print("  \u2713 CUDA NMS: works")
except Exception as e:
    print(f"  \u2717 CUDA NMS: {e}")
    print("    Fix: re-run phase torch-pre to patch torchvision _C.so")
    ok = False

# Model family note
family = "$MODEL_FAMILY"
print(f"\n  Model family: {family}")
if family == "yolov8":
    print("  Next: yolo export model=yolov8n.pt format=engine device=0 half=True")
elif family == "yolo11":
    print("  Next: yolo export model=yolo11n.pt format=engine device=0 half=True")
elif family == "yolo26":
    print("  Next: yolo export model=yolo26n.pt format=engine device=0 half=True")

if not ok:
    print("\n[FAIL] Some checks failed — see references/conflict_resolution_playbook.md")
    sys.exit(1)
print("\n[OK] All checks passed")
PYEOF
  "$CONDA_BIN" run -n "$ENV_NAME" python3 "$_VALIDATE_PY"
  _EXIT=$?
  rm -f "$_VALIDATE_PY"
  [[ $_EXIT -eq 0 ]] || die "Validation failed — see output above"

  log "Phase torch-post done."
  log "Activate with: conda activate $ENV_NAME"
  log "Model dir: $MODEL_DIR"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
case "$PHASE" in
  env)        phase_env ;;
  download)   phase_download ;;
  torch-pre)  phase_torch_pre ;;
  deps)       phase_deps ;;
  torch-post) phase_torch_post ;;
  all)
    phase_env
    phase_download
    phase_torch_pre
    phase_deps
    phase_torch_post
    ;;
  *)
    die "Unknown phase: $PHASE. Valid: env | download | torch-pre | deps | torch-post | all"
    ;;
esac
