#!/usr/bin/env bash
# install_lerobot.sh
# Full LeRobot install on Jetson in strict order.
#
# Usage:
#   bash install_lerobot.sh [--env ENV] [--wheel-dir DIR] [--robot-type TYPE] [--phase PHASE]
#
# Phases (run in order):
#   env        — Step 1: create conda env (python=3.10), Step 2: clone lerobot
#   download   — Step 3: download torch/torchvision wheels (~254 MB, shows progress)
#   torch-pre  — Step 4: install torch wheels + verify CUDA (hard stop if False)
#   deps       — Step 5: opencv / ffmpeg / numpy, Step 6: pip install -e lerobot
#   torch-post — Step 7: reinstall torch wheels (mandatory), Step 8: final validation
#   all        — run all phases in order (default)

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
ENV_NAME="lerobot"
WHEEL_DIR="$HOME/wheels"
ROBOT_TYPE="so-arm"
LEROBOT_DIR="$HOME/lerobot"
PHASE="all"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

TORCH_WHL="torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl"
TV_WHL="torchvision-0.23.0-cp310-cp310-linux_aarch64.whl"

# ── Args ──────────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)         ENV_NAME="$2";    shift 2 ;;
    --wheel-dir)   WHEEL_DIR="$2";   shift 2 ;;
    --robot-type)  ROBOT_TYPE="$2";  shift 2 ;;
    --lerobot-dir) LEROBOT_DIR="$2"; shift 2 ;;
    --phase)       PHASE="$2";       shift 2 ;;
    *) echo "[error] Unknown arg: $1"; exit 1 ;;
  esac
done

TORCH_WHL_PATH="$WHEEL_DIR/$TORCH_WHL"
TV_WHL_PATH="$WHEEL_DIR/$TV_WHL"

log()  { echo "[install] $*"; }
die()  { echo "[STOP]    $*" >&2; exit 1; }

log "ENV=$ENV_NAME  WHEEL_DIR=$WHEEL_DIR  ROBOT_TYPE=$ROBOT_TYPE  PHASE=$PHASE"

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

  # Step 2: clone lerobot
  if "$CONDA_BIN" run -n "$ENV_NAME" python3 -c "import lerobot" 2>/dev/null; then
    log "Step 2: lerobot already installed in '$ENV_NAME' — skip clone"
  elif [[ -d "$LEROBOT_DIR" ]]; then
    log "Step 2: $LEROBOT_DIR exists — skip clone"
  else
    log "Step 2: cloning Seeed-Projects/lerobot to $LEROBOT_DIR"
    git clone https://github.com/Seeed-Projects/lerobot.git "$LEROBOT_DIR"
  fi

  log "Phase env done."
}

# ── Phase: download ────────────────────────────────────────────────────────────
phase_download() {
  if [[ -f "$TORCH_WHL_PATH" && -f "$TV_WHL_PATH" ]]; then
    log "Step 3: wheel files already in $WHEEL_DIR — skip download"
  else
    log "Step 3: downloading Jetson wheel files to $WHEEL_DIR (this takes 10-20 min)"
    "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet requests
    "$CONDA_BIN" run -n "$ENV_NAME" python3 "$SKILL_DIR/scripts/download_wheels.py" --dest "$WHEEL_DIR"
    [[ -f "$TORCH_WHL_PATH" ]] || die "torch wheel not found after download: $TORCH_WHL_PATH"
    [[ -f "$TV_WHL_PATH" ]]    || die "torchvision wheel not found after download: $TV_WHL_PATH"
  fi

  log "Phase download done."
}

# ── Phase: torch-pre ──────────────────────────────────────────────────────────
phase_torch_pre() {
  [[ -f "$TORCH_WHL_PATH" ]] || die "torch wheel missing: $TORCH_WHL_PATH — run phase 'download' first"
  [[ -f "$TV_WHL_PATH" ]]    || die "torchvision wheel missing: $TV_WHL_PATH — run phase 'download' first"

  log "Step 4: installing torch/torchvision GPU wheels (pre-editable)"
  "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "$TORCH_WHL_PATH"
  "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "$TV_WHL_PATH"

  log "Step 4: verifying CUDA..."
  CUDA_OK=$("$CONDA_BIN" run -n "$ENV_NAME" python3 -c "import torch; print(torch.cuda.is_available())" 2>/dev/null || echo "False")
  if [[ "$CUDA_OK" != "True" ]]; then
    die "torch.cuda.is_available() = $CUDA_OK after wheel install.
  Wheel file may be corrupt or wrong architecture.
  Fix: rm $WHEEL_DIR/*.whl  then re-run phases 'download' and 'torch-pre'."
  fi
  log "Step 4: CUDA OK ✓"

  log "Phase torch-pre done."
}

# ── Phase: deps ───────────────────────────────────────────────────────────────
phase_deps() {
  # Step 5a: opencv
  if "$CONDA_BIN" run -n "$ENV_NAME" python3 -c "import cv2; assert cv2.__version__=='4.10.0.84'" 2>/dev/null; then
    log "Step 5a: opencv 4.10.0.84 already installed — skip"
  else
    log "Step 5a: installing opencv-python 4.10.0.84"
    "$CONDA_BIN" run -n "$ENV_NAME" conda install -y -c conda-forge "opencv>=4.10.0.84" || true
    "$CONDA_BIN" run -n "$ENV_NAME" conda remove -y opencv 2>/dev/null || true
    "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet opencv-python==4.10.0.84
  fi

  # Step 5b: ffmpeg
  if "$CONDA_BIN" run -n "$ENV_NAME" ffmpeg -version &>/dev/null; then
    log "Step 5b: ffmpeg already installed — skip"
  else
    log "Step 5b: installing ffmpeg via conda-forge"
    "$CONDA_BIN" run -n "$ENV_NAME" conda install -y -c conda-forge ffmpeg || \
    "$CONDA_BIN" run -n "$ENV_NAME" conda install -y -c conda-forge ffmpeg=7.1.1
  fi

  # Step 5c: numpy
  if "$CONDA_BIN" run -n "$ENV_NAME" python3 -c "import numpy as np; assert np.__version__.startswith('1.26')" 2>/dev/null; then
    log "Step 5c: numpy 1.26.x already installed — skip"
  else
    log "Step 5c: pinning numpy to 1.26.0"
    "$CONDA_BIN" run -n "$ENV_NAME" conda uninstall -y numpy 2>/dev/null || true
    "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet numpy==1.26.0
  fi

  # Step 6: lerobot editable install
  if "$CONDA_BIN" run -n "$ENV_NAME" python3 -c "import lerobot" 2>/dev/null; then
    log "Step 6: lerobot already installed — skip editable install"
  else
    log "Step 6: pip install -e lerobot [feetech]"
    "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet -e "$LEROBOT_DIR/.[feetech]"
  fi

  log "Phase deps done."
}

# ── Phase: torch-post ─────────────────────────────────────────────────────────
phase_torch_post() {
  [[ -f "$TORCH_WHL_PATH" ]] || die "torch wheel missing: $TORCH_WHL_PATH"
  [[ -f "$TV_WHL_PATH" ]]    || die "torchvision wheel missing: $TV_WHL_PATH"

  log "Step 7: reinstalling torch/torchvision wheels (post-editable — mandatory)"
  "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "$TORCH_WHL_PATH"
  "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet "$TV_WHL_PATH"
  "$CONDA_BIN" run -n "$ENV_NAME" pip install --quiet numpy==1.26.0

  log "Step 8: final validation"
  "$CONDA_BIN" run -n "$ENV_NAME" python3 - <<'EOF'
import sys
import torch, torchvision, cv2, numpy as np

results = {
    "CUDA available":   (torch.cuda.is_available(),       True),
    "torch version":    (torch.__version__,               "2.8.0a0+gitba56102"),
    "torchvision":      (torchvision.__version__,         "0.23.0"),
    "OpenCV":           (cv2.__version__,                 "4.10.0.84"),
    "numpy":            (np.__version__.startswith("1.26"), True),
}

ok = True
for name, (got, want) in results.items():
    status = "✓" if got == want else "✗"
    print(f"  {status} {name}: {got}  (expected {want})")
    if got != want:
        ok = False

if not ok:
    print("\n[FAIL] Some checks failed — see conflict_resolution_playbook.md")
    sys.exit(1)
print("\n[OK] All checks passed")
EOF

  log "Phase torch-post done."
  log "Activate with: conda activate $ENV_NAME"
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
