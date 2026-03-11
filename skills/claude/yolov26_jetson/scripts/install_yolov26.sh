#!/usr/bin/env bash
# install_yolov26.sh
# Full YOLOv26 install on Jetson in strict order.
#
# Usage:
#   bash install_yolov26.sh [--env ENV] [--wheel-dir DIR] [--phase PHASE]
#
# Phases (run in order):
#   env        — Step 1: create conda env (python=3.10), Step 2: clone repo, Step 3: cuSPARSELt
#   download   — Step 4: download torch/torchvision wheels (~900 MB, shows progress)
#   torch-pre  — Step 5: install torch wheels + verify CUDA (hard stop if False)
#   deps       — Step 6: onnxruntime-gpu, Step 7: numpy, Step 8: opencv, Step 9: ultralytics
#   torch-post — Step 10: reinstall torch wheels (mandatory), Step 11: final validation
#   all        — run all phases in order

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
ENV_NAME="yolov26"
WHEEL_DIR="$HOME/wheels"
YOLO_DIR="$HOME/yolov26_jetson"
MODEL_DIR="$HOME/ultralytics_data"
PHASE="all"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

TORCH_WHL="torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl"
TV_WHL="torchvision-0.23.0-cp310-cp310-linux_aarch64.whl"
# onnxruntime-gpu: searched in common wheel locations, not downloaded automatically
ORT_SEARCH_DIRS=("$HOME/wheels" "$HOME/wheel")

# ── Args ──────────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)        ENV_NAME="$2";   shift 2 ;;
    --wheel-dir)  WHEEL_DIR="$2";  shift 2 ;;
    --yolo-dir)   YOLO_DIR="$2";   shift 2 ;;
    --phase)      PHASE="$2";      shift 2 ;;
    *) echo "[error] Unknown arg: $1"; exit 1 ;;
  esac
done

TORCH_WHL_PATH="$WHEEL_DIR/$TORCH_WHL"
TV_WHL_PATH="$WHEEL_DIR/$TV_WHL"

log()  { echo "[install] $*"; }
die()  { echo "[STOP]    $*" >&2; exit 1; }

log "ENV=$ENV_NAME  WHEEL_DIR=$WHEEL_DIR  PHASE=$PHASE"

# ── Conda auto-detect ─────────────────────────────────────────────────────────
# Agent exec sessions do not source ~/.bashrc, so conda may not be in PATH.
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

if [[ -z "$CONDA_BIN" ]]; then
  die "conda not found in PATH or standard locations (~miniconda3, ~/anaconda3, etc.).
  Install Miniconda first:
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
    bash Miniconda3-latest-Linux-aarch64.sh
  Then rerun this script."
fi
log "conda found: $CONDA_BIN"

# ── Phase: env ────────────────────────────────────────────────────────────────
phase_env() {
  # Step 1: conda env (must be python=3.10 for cp310 wheels)
  if "$CONDA_BIN" env list | grep -q "^${ENV_NAME} "; then
    EXISTING_PY=$("$CONDA_BIN" run -n "$ENV_NAME" python3 --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1)
    if [[ "$EXISTING_PY" == "3.10" ]]; then
      log "Step 1: conda env '$ENV_NAME' already exists with Python 3.10 — skip create"
    else
      log "Step 1: conda env '$ENV_NAME' exists but has Python $EXISTING_PY (need 3.10) — removing and recreating"
      "$CONDA_BIN" env remove -y -n "$ENV_NAME"
      "$CONDA_BIN" create -y -n "$ENV_NAME" python=3.10
    fi
  else
    log "Step 1: creating conda env '$ENV_NAME' python=3.10"
    "$CONDA_BIN" create -y -n "$ENV_NAME" python=3.10
  fi

  # Step 2: clone yolov26_jetson
  if [[ -d "$YOLO_DIR" ]]; then
    log "Step 2: $YOLO_DIR already exists — skip clone"
  else
    log "Step 2: cloning yolov26_jetson to $YOLO_DIR"
    git clone https://github.com/bleaaach/yolov26_jetson.git "$YOLO_DIR"
  fi

  # Step 3: create model directory
  if [[ -d "$MODEL_DIR" ]]; then
    log "Step 3: $MODEL_DIR already exists — skip"
  else
    log "Step 3: creating model directory $MODEL_DIR"
    mkdir -p "$MODEL_DIR"
  fi

  # Step 4: install libcusparselt0 (required by torch 2.8 on JetPack 6.0)
  if dpkg -l libcusparselt0 2>/dev/null | grep -q '^ii'; then
    log "Step 4: libcusparselt0 already installed — skip"
  else
    log "Step 4: installing libcusparselt0"
    # Prefer local deb from repo, fall back to apt
    LOCAL_DEB="$YOLO_DIR/libcusparselt0_0.6.2.3-1_arm64.deb"
    if [[ -f "$LOCAL_DEB" ]]; then
      sudo dpkg -i "$LOCAL_DEB" || sudo apt-get install -f -y
    else
      sudo apt-get update -qq
      sudo apt-get install -y libcusparselt0
    fi
  fi

  log "Phase env done."
}

# ── Phase: download ────────────────────────────────────────────────────────────
phase_download() {
  if [[ -f "$TORCH_WHL_PATH" && -f "$TV_WHL_PATH" ]]; then
    log "Step 5: torch and torchvision wheels already in $WHEEL_DIR — skip download"
  else
    log "Step 5: downloading Jetson wheel files to $WHEEL_DIR (this takes 15-25 min)"
    "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet requests
    "$CONDA_BIN" run -n "$ENV_NAME" python3 "$SKILL_DIR/scripts/download_wheels.py" --dest "$WHEEL_DIR" \
      || die "wheel download failed — SharePoint URLs may have expired. Place wheels manually in $WHEEL_DIR"
    [[ -f "$TORCH_WHL_PATH" ]] || die "torch wheel not found after download: $TORCH_WHL_PATH"
    [[ -f "$TV_WHL_PATH" ]]    || die "torchvision wheel not found after download: $TV_WHL_PATH"
  fi

  log "Phase download done."
}

# ── Phase: torch-pre ──────────────────────────────────────────────────────────
phase_torch_pre() {
  [[ -f "$TORCH_WHL_PATH" ]] || die "torch wheel missing: $TORCH_WHL_PATH — run phase 'download' first"
  [[ -f "$TV_WHL_PATH" ]]    || die "torchvision wheel missing: $TV_WHL_PATH — run phase 'download' first"

  log "Step 6: installing torch/torchvision GPU wheels (pre-deps)"
  "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "$TORCH_WHL_PATH"
  "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "$TV_WHL_PATH"

  log "Step 6: verifying CUDA..."
  CUDA_OK=$("$CONDA_BIN" run -n "$ENV_NAME" python3 -c "import torch; print(torch.cuda.is_available())" 2>/dev/null || echo "False")
  if [[ "$CUDA_OK" != "True" ]]; then
    die "torch.cuda.is_available() = $CUDA_OK after wheel install.
  Wheel file may be corrupt or wrong architecture.
  Fix: rm $WHEEL_DIR/*.whl  then re-run phases 'download' and 'torch-pre'."
  fi
  log "Step 6: CUDA OK ✓"

  # Step 6b: patch torchvision _C.so with local CUDA-NMS-enabled build.
  # The SharePoint torchvision wheel is compiled without CUDA NMS kernel,
  # which causes "torchvision::nms CUDA backend" errors during inference.
  # The locally compiled torchvision at ~/vision/build/ has CUDA NMS.
  TV_SITE=$("$CONDA_BIN" run -n "$ENV_NAME" python3 -c \
    'import site; print(site.getsitepackages()[0])' 2>/dev/null)
  LOCAL_SO_DIR=""
  for _d in \
    "$HOME/vision/build/lib.linux-aarch64-3.10" \
    "$HOME/vision/build/lib.linux-aarch64-cpython-310"; do
    if [[ -f "$_d/torchvision/_C.so" ]]; then
      LOCAL_SO_DIR="$_d"
      break
    fi
  done

  if [[ -n "$LOCAL_SO_DIR" ]]; then
    log "Step 6b: patching torchvision with CUDA-NMS build from $LOCAL_SO_DIR"
    cp "$LOCAL_SO_DIR/torchvision/_C.so"    "$TV_SITE/torchvision/_C.so"
    [[ -f "$LOCAL_SO_DIR/torchvision/image.so" ]] && \
      cp "$LOCAL_SO_DIR/torchvision/image.so" "$TV_SITE/torchvision/image.so"
  else
    log "Step 6b: local CUDA-NMS torchvision not found at ~/vision/build/ — skipping patch"
    log "         torchvision::nms will fall back to CPU; TensorRT .engine inference still works."
  fi

  log "Phase torch-pre done."
}

# ── Phase: deps ───────────────────────────────────────────────────────────────
phase_deps() {
  # Step 7: onnxruntime-gpu (>= 1.22 required for TensorRT export)
  if "$CONDA_BIN" run -n "$ENV_NAME" python3 -c \
      "import onnxruntime as ort; v=tuple(int(x) for x in ort.__version__.split('.')[:2]); assert v>=(1,22)" 2>/dev/null; then
    ORT_VER=$("$CONDA_BIN" run -n "$ENV_NAME" python3 -c "import onnxruntime; print(onnxruntime.__version__)" 2>/dev/null || echo "?")
    log "Step 7: onnxruntime-gpu $ORT_VER already installed (>= 1.22) — skip"
  else
    # Search common wheel locations for any onnxruntime-gpu >= 1.22 wheel
    ORT_WHL_FOUND=""
    for _dir in "${ORT_SEARCH_DIRS[@]}"; do
      _whl=$(ls "$_dir"/onnxruntime_gpu-*.whl 2>/dev/null | sort -V | tail -1)
      if [[ -n "$_whl" ]]; then
        ORT_WHL_FOUND="$_whl"
        break
      fi
    done
    if [[ -n "$ORT_WHL_FOUND" ]]; then
      log "Step 7: installing onnxruntime-gpu from $ORT_WHL_FOUND"
      "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "$ORT_WHL_FOUND"
    else
      die "onnxruntime-gpu not found (>= 1.22 required).
  Place a wheel file in $WHEEL_DIR, e.g.:
    onnxruntime_gpu-1.23.0-cp310-cp310-linux_aarch64.whl
  Available from: https://github.com/ultralytics/assets/releases/"
    fi
  fi

  # Step 8: numpy
  if "$CONDA_BIN" run -n "$ENV_NAME" python3 -c "import numpy as np; assert np.__version__.startswith('1.26')" 2>/dev/null; then
    log "Step 8: numpy 1.26.x already installed — skip"
  else
    log "Step 8: pinning numpy to 1.26.0"
    "$CONDA_BIN" run -n "$ENV_NAME" conda uninstall -y numpy 2>/dev/null || true
    "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet numpy==1.26.0
  fi

  # Step 9a: opencv
  # NOTE: We install opencv-python directly via pip (not via conda-forge).
  # conda install opencv on an existing env can silently upgrade Python (e.g. 3.10→3.14),
  # which breaks cp310 wheel compatibility. Jetson JetPack 6 already ships all
  # required system libs (libGL, libgthread, etc.), so pip-only is sufficient.
  # cv2.__version__ returns the underlying OpenCV version (e.g. "4.10.0"),
  # NOT the pip package revision suffix (e.g. "4.10.0.84").
  if "$CONDA_BIN" run -n "$ENV_NAME" python3 -c "import cv2; assert cv2.__version__ >= '4.10.0'" 2>/dev/null; then
    log "Step 9a: opencv $(conda run -n "$ENV_NAME" python3 -c 'import cv2; print(cv2.__version__)' 2>/dev/null) already installed (>= 4.10.0) — skip"
  else
    log "Step 9a: installing opencv-python 4.10.0.84 (pip only)"
    "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet opencv-python==4.10.0.84
  fi

  # Step 9b: expose system TensorRT to the conda env via a .pth file.
  # Jetson ships TensorRT 10.x in /usr/lib/python3.10/dist-packages/.
  # Without this, ultralytics auto-installs a PyPI tensorrt (CUDA 13 build)
  # that is incompatible with Jetson and causes a crash when loading .engine files.
  CONDA_SITE="$("$CONDA_BIN" run -n "$ENV_NAME" python3 -c \
    'import site; print(site.getsitepackages()[0])' 2>/dev/null)"
  PTH_FILE="$CONDA_SITE/jetpack-system.pth"
  SYSTEM_DIST="/usr/lib/python3.10/dist-packages"
  if [[ -f "$PTH_FILE" ]] && grep -q "$SYSTEM_DIST" "$PTH_FILE" 2>/dev/null; then
    log "Step 9b: system TensorRT path already linked — skip"
  elif [[ -d "$SYSTEM_DIST/tensorrt" ]]; then
    log "Step 9b: linking system TensorRT ($SYSTEM_DIST) into conda env"
    echo "$SYSTEM_DIST" > "$PTH_FILE"
  else
    log "Step 9b: /usr/lib/python3.10/dist-packages/tensorrt not found — skipping TRT link"
    log "         If engine inference fails, check JetPack TensorRT installation."
  fi

  # Step 9c: ultralytics (may overwrite torch with CPU wheel — torch-post fixes this)
  if "$CONDA_BIN" run -n "$ENV_NAME" python3 -c "import ultralytics" 2>/dev/null; then
    log "Step 9c: ultralytics already installed — skip"
  else
    log "Step 9c: installing ultralytics[export] (may take a few minutes)"
    "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "ultralytics[export]"
  fi

  log "Phase deps done."
}

# ── Phase: torch-post ─────────────────────────────────────────────────────────
phase_torch_post() {
  [[ -f "$TORCH_WHL_PATH" ]] || die "torch wheel missing: $TORCH_WHL_PATH"
  [[ -f "$TV_WHL_PATH" ]]    || die "torchvision wheel missing: $TV_WHL_PATH"

  log "Step 10: reinstalling torch/torchvision wheels (post-deps — mandatory)"
  # ultralytics[export] may have pulled CPU-only torch from PyPI; reinstall GPU wheels
  "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "$TORCH_WHL_PATH"
  "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "$TV_WHL_PATH"
  "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet numpy==1.26.0

  # Step 10b: re-apply CUDA NMS patch (pip reinstall above may overwrite _C.so)
  TV_SITE=$("$CONDA_BIN" run -n "$ENV_NAME" python3 -c \
    'import site; print(site.getsitepackages()[0])' 2>/dev/null)
  LOCAL_SO_DIR=""
  for _d in \
    "$HOME/vision/build/lib.linux-aarch64-3.10" \
    "$HOME/vision/build/lib.linux-aarch64-cpython-310"; do
    if [[ -f "$_d/torchvision/_C.so" ]]; then
      LOCAL_SO_DIR="$_d"
      break
    fi
  done
  if [[ -n "$LOCAL_SO_DIR" ]]; then
    log "Step 10b: re-applying CUDA-NMS patch (post wheel reinstall)"
    cp "$LOCAL_SO_DIR/torchvision/_C.so"    "$TV_SITE/torchvision/_C.so"
    [[ -f "$LOCAL_SO_DIR/torchvision/image.so" ]] && \
      cp "$LOCAL_SO_DIR/torchvision/image.so" "$TV_SITE/torchvision/image.so"
  fi

  log "Step 11: final validation"
  # Write validation script to a temp file to avoid heredoc+conda-run stdin issues
  _VALIDATE_PY=$(mktemp /tmp/yolov26_validate_XXXXXX.py)
  cat > "$_VALIDATE_PY" <<'PYEOF'
import sys
import torch, torchvision, cv2, numpy as np, onnxruntime, ultralytics

ort_ver = tuple(int(x) for x in onnxruntime.__version__.split(".")[:2])

checks = {
    "CUDA available":      (torch.cuda.is_available(),               True),
    "torch version":       (torch.__version__,                       "2.8.0a0+gitba56102"),
    "torchvision version": (torchvision.__version__,                 "0.23.0"),
    "numpy version":       (np.__version__.startswith("1.26"),       True),
    # cv2.__version__ is the underlying OpenCV version (e.g. "4.10.0"),
    # not the pip package suffix (e.g. "4.10.0.84")
    "opencv >= 4.10.0":    (cv2.__version__ >= "4.10.0",             True),
    "onnxruntime >= 1.22": (ort_ver >= (1, 22),                      True),
    "ultralytics present": (bool(ultralytics.__version__),           True),
}

ok = True
for name, (got, want) in checks.items():
    status = "\u2713" if got == want else "\u2717"
    print(f"  {status} {name}: {got}  (expected {want})")
    if got != want:
        ok = False

# CUDA NMS test — required for TensorRT .engine inference.
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

if not ok:
    print("\n[FAIL] Some checks failed — see references/conflict_resolution_playbook.md")
    sys.exit(1)
print("\n[OK] All checks passed")
PYEOF
  "$CONDA_BIN" run -n "$ENV_NAME" python3 "$_VALIDATE_PY"
  _VALIDATE_EXIT=$?
  rm -f "$_VALIDATE_PY"
  [[ $_VALIDATE_EXIT -eq 0 ]] || die "Validation failed — see output above"

  log "Phase torch-post done."
  log "Activate with: conda activate $ENV_NAME"
  log "Next: export TensorRT engines, then run bash ~/yolov26_jetson/run_dual_camera_local.sh"
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
