#!/usr/bin/env bash
# install_pinocchio.sh
# Install Pinocchio (stack-of-tasks/pinocchio) into a conda env, venv, or system Python.
#
# Usage:
#   bash install_pinocchio.sh [--env ENV] [--method METHOD] [--prefix PREFIX] [--phase PHASE]
#
# --env:    conda env name | "system" | "venv:/path/to/venv"  (default: pinocchio)
# --method: conda | pip | source                               (default: conda)
# --prefix: cmake install prefix for source builds             (default: ~/.local)
# --phase:  detect | deps | build | validate | all             (default: all)

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
ENV_NAME="pinocchio"
METHOD="conda"
PREFIX="$HOME/.local"
PHASE="all"
SRC_DIR="$HOME/pinocchio_src"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ── Arg parse ─────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)    ENV_NAME="$2"; shift 2 ;;
    --method) METHOD="$2";   shift 2 ;;
    --prefix) PREFIX="$2";   shift 2 ;;
    --phase)  PHASE="$2";    shift 2 ;;
    --src-dir) SRC_DIR="$2"; shift 2 ;;
    *) echo "[error] Unknown argument: $1"; exit 1 ;;
  esac
done

log()  { echo "[install] $*"; }
die()  { echo "[STOP]    $*" >&2; exit 1; }
ok()   { echo "[OK]      $*"; }

log "ENV=$ENV_NAME  METHOD=$METHOD  PHASE=$PHASE"

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

CONDA_BASE=""
if [[ -n "$CONDA_BIN" ]]; then
  CONDA_BASE="$("$CONDA_BIN" info --base 2>/dev/null || true)"
fi

# ── Helper: resolve Python executable for the target env ─────────────────────
resolve_python() {
  case "$ENV_NAME" in
    system)
      PYTHON_BIN="$(command -v python3 2>/dev/null || command -v python 2>/dev/null)"
      [[ -z "$PYTHON_BIN" ]] && die "python3 not found on system PATH"
      ;;
    venv:*)
      VENV_PATH="${ENV_NAME#venv:}"
      PYTHON_BIN="$VENV_PATH/bin/python"
      [[ -x "$PYTHON_BIN" ]] || die "venv not found at $VENV_PATH — create it first with: python3 -m venv $VENV_PATH"
      ;;
    *)
      # conda env
      [[ -z "$CONDA_BIN" ]] && die "conda not found — install Miniconda/Mamba first, or use --env system or --env venv:<path>"
      PYTHON_BIN="$CONDA_BASE/envs/$ENV_NAME/bin/python"
      ;;
  esac
  log "Python: $PYTHON_BIN"
}

# ── Helper: run pip in target env ─────────────────────────────────────────────
run_pip() {
  "$PYTHON_BIN" -m pip "$@"
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE: detect
# ══════════════════════════════════════════════════════════════════════════════
phase_detect() {
  log "=== Phase 1: detect ==="

  # Architecture
  ARCH="$(uname -m)"
  log "Architecture: $ARCH"
  OS_ID="$(. /etc/os-release 2>/dev/null && echo "$ID $VERSION_ID" || uname -s)"
  log "OS: $OS_ID"

  # conda
  if [[ -n "$CONDA_BIN" ]]; then
    CONDA_VER="$("$CONDA_BIN" --version 2>&1)"
    log "Conda: $CONDA_VER (base: $CONDA_BASE)"
  else
    log "Conda: not found"
  fi

  # cmake / git
  CMAKE_VER="$(cmake --version 2>/dev/null | head -1 || echo 'not found')"
  log "CMake: $CMAKE_VER"
  GIT_VER="$(git --version 2>/dev/null || echo 'not found')"
  log "Git: $GIT_VER"

  # Resolve python and check existing install
  resolve_python

  PY_VER="$("$PYTHON_BIN" --version 2>&1)"
  log "Python: $PY_VER"

  if "$PYTHON_BIN" -c "import pinocchio" 2>/dev/null; then
    PIN_VER="$("$PYTHON_BIN" -c "import pinocchio; print(pinocchio.__version__)" 2>/dev/null || echo 'unknown')"
    die "conda env $ENV_NAME already has pinocchio==$PIN_VER — run validate to confirm it works"
  else
    log "pinocchio: not yet installed in target env"
  fi

  # ARM64 warning for conda method
  if [[ "$ARCH" == "aarch64" && "$METHOD" == "conda" ]]; then
    log "WARNING: aarch64 detected. conda-forge pinocchio may not have pre-built arm64 binaries."
    log "         If phase build fails, re-run with --method source"
  fi

  ok "detect complete"
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE: deps
# ══════════════════════════════════════════════════════════════════════════════
phase_deps() {
  log "=== Phase 2: deps ==="

  if [[ "$METHOD" == "conda" ]]; then
    log "conda method: system deps not required — skipping"
    ok "deps skipped (conda handles its own deps)"
    return
  fi

  if [[ "$METHOD" == "pip" ]]; then
    log "pip method: no system build deps needed — skipping"
    ok "deps skipped (pip wheels are pre-compiled)"
    return
  fi

  # source method — install build deps via apt
  log "Checking apt package manager..."
  command -v apt-get >/dev/null 2>&1 || die "apt-get not found — this script only handles apt-based systems for source builds"

  log "Updating apt cache..."
  sudo apt-get update -qq

  PKGS=(
    cmake
    build-essential
    git
    libeigen3-dev
    libboost-all-dev
    liburdfdom-dev
    liburdfdom-headers-dev
    libconsole-bridge-dev
    python3-dev
    python3-pip
  )

  MISSING=()
  for pkg in "${PKGS[@]}"; do
    if ! dpkg -s "$pkg" &>/dev/null; then
      MISSING+=("$pkg")
    fi
  done

  if [[ ${#MISSING[@]} -eq 0 ]]; then
    log "All apt deps already installed — skipping"
  else
    log "Installing: ${MISSING[*]}"
    sudo apt-get install -y "${MISSING[@]}"
  fi

  # eigenpy — try robotpkg, else build from source
  if python3 -c "import eigenpy" 2>/dev/null; then
    log "eigenpy: already installed"
  else
    log "Installing eigenpy via pip..."
    python3 -m pip install eigenpy || {
      log "pip install eigenpy failed — trying conda-forge standalone..."
      die "eigenpy not available via pip and conda is absent. See references/build_troubleshooting.md B2"
    }
  fi

  ok "deps complete"
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE: build
# ══════════════════════════════════════════════════════════════════════════════
phase_build() {
  log "=== Phase 3: build (method=$METHOD) ==="

  resolve_python

  case "$METHOD" in

    # ── conda ────────────────────────────────────────────────────────────────
    conda)
      [[ -z "$CONDA_BIN" ]] && die "conda not found"

      if [[ "$ENV_NAME" == "system" || "$ENV_NAME" == venv:* ]]; then
        die "conda method requires a conda env name, not 'system' or 'venv:...'"
      fi

      # Create env if missing
      if ! "$CONDA_BIN" env list 2>/dev/null | grep -qE "^$ENV_NAME\s"; then
        log "Creating conda env '$ENV_NAME' with python=3.10..."
        "$CONDA_BIN" create -n "$ENV_NAME" python=3.10 -y
        log "Env created"
      else
        log "Conda env '$ENV_NAME' already exists — reusing"
      fi

      log "Installing pinocchio via conda-forge (this may take 1-3 min)..."
      "$CONDA_BIN" install -n "$ENV_NAME" -c conda-forge pinocchio -y
      log "conda install complete"
      ;;

    # ── pip ──────────────────────────────────────────────────────────────────
    pip)
      ARCH="$(uname -m)"
      OS="$(uname -s)"
      if [[ "$OS" == "Windows"* ]]; then
        die "pip install pinocchio is not supported on Windows — use conda or source"
      fi
      if [[ "$ARCH" == "aarch64" ]]; then
        log "WARNING: aarch64 — pip wheels may not be available. Will attempt; if fails, use --method source"
      fi

      # Create venv if venv: prefix and venv doesn't exist
      if [[ "$ENV_NAME" == venv:* ]]; then
        VENV_PATH="${ENV_NAME#venv:}"
        if [[ ! -d "$VENV_PATH" ]]; then
          log "Creating venv at $VENV_PATH..."
          python3 -m venv "$VENV_PATH"
        fi
      fi

      log "Installing 'pin' package (pinocchio Python wheel) via pip..."
      run_pip install --upgrade pip
      run_pip install pin || die "pip install failed — unsupported platform. Retry with --method source"
      log "pip install complete"
      ;;

    # ── source ───────────────────────────────────────────────────────────────
    source)
      log "Source build into prefix=$PREFIX"
      mkdir -p "$PREFIX"

      # Clone
      if [[ -d "$SRC_DIR/.git" ]]; then
        log "Source repo already cloned at $SRC_DIR — pulling latest..."
        git -C "$SRC_DIR" pull --ff-only || log "git pull skipped (local changes present)"
      else
        log "Cloning pinocchio (with submodules)..."
        git clone --recursive https://github.com/stack-of-tasks/pinocchio.git "$SRC_DIR" \
          || die "git clone failed — check network or disk space"
        log "Clone complete"
      fi

      # Configure
      BUILD_DIR="$SRC_DIR/build"
      mkdir -p "$BUILD_DIR"
      log "Running cmake configure..."
      cmake -S "$SRC_DIR" -B "$BUILD_DIR" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DBUILD_PYTHON_INTERFACE=ON \
        -DBUILD_WITH_COLLISION_SUPPORT=OFF \
        -DBUILD_TESTING=OFF \
        || die "cmake configure failed — check references/build_troubleshooting.md B3"

      # Build
      NPROC="$(nproc 2>/dev/null || echo 2)"
      # Cap at 4 to avoid OOM on low-RAM devices
      [[ "$NPROC" -gt 4 ]] && NPROC=4
      log "Building with -j$NPROC (this takes 10–30 min on first build)..."
      cmake --build "$BUILD_DIR" --parallel "$NPROC" \
        || die "make failed — check references/build_troubleshooting.md B4"

      # Install
      log "Installing to $PREFIX..."
      cmake --install "$BUILD_DIR"
      log "Source build and install complete"
      ;;

    *)
      die "Unknown method '$METHOD'. Choose: conda | pip | source"
      ;;
  esac

  ok "build complete"
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE: validate
# ══════════════════════════════════════════════════════════════════════════════
phase_validate() {
  log "=== Phase 4: validate ==="

  resolve_python

  # For source builds, PYTHONPATH must include the install prefix
  if [[ "$METHOD" == "source" ]]; then
    PY_VER_SHORT="$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"
    PYPATH_ENTRY="$PREFIX/lib/python${PY_VER_SHORT}/site-packages"
    export PYTHONPATH="$PYPATH_ENTRY${PYTHONPATH:+:$PYTHONPATH}"
    export LD_LIBRARY_PATH="$PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    log "PYTHONPATH set to include $PYPATH_ENTRY"
  fi

  log "Importing pinocchio..."
  "$PYTHON_BIN" -c "import pinocchio" \
    || die "import pinocchio failed — see references/build_troubleshooting.md B5"

  PIN_VER="$("$PYTHON_BIN" -c "import pinocchio; print(pinocchio.__version__)")"
  log "pinocchio version: $PIN_VER"

  log "Running sanity check (build model, run FK)..."
  "$PYTHON_BIN" - <<'PYEOF'
import pinocchio as pin
import numpy as np

model = pin.buildSampleModelHumanoidRandom()
data  = model.createData()
q     = pin.randomConfiguration(model)
pin.forwardKinematics(model, data, q)
print(f"[install] FK OK — model has {model.njoints} joints, nq={model.nq}")
PYEOF
  [[ $? -eq 0 ]] || die "sanity check failed — see references/build_troubleshooting.md B5"

  # Print activation instructions
  log ""
  log "=== Activation instructions ==="
  case "$ENV_NAME" in
    system)
      if [[ "$METHOD" == "source" ]]; then
        PY_VER_SHORT="$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"
        log "Add to ~/.bashrc:"
        log "  export PYTHONPATH=$PREFIX/lib/python${PY_VER_SHORT}/site-packages:\$PYTHONPATH"
        log "  export LD_LIBRARY_PATH=$PREFIX/lib:\$LD_LIBRARY_PATH"
      fi
      ;;
    venv:*)
      VENV_PATH="${ENV_NAME#venv:}"
      log "Activate with:  source $VENV_PATH/bin/activate"
      if [[ "$METHOD" == "source" ]]; then
        PY_VER_SHORT="$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"
        log "Also set:  export PYTHONPATH=$PREFIX/lib/python${PY_VER_SHORT}/site-packages:\$PYTHONPATH"
      fi
      ;;
    *)
      log "Activate with:  conda activate $ENV_NAME"
      ;;
  esac

  ok "validate complete — pinocchio $PIN_VER is ready"
}

# ══════════════════════════════════════════════════════════════════════════════
# Dispatch
# ══════════════════════════════════════════════════════════════════════════════
case "$PHASE" in
  detect)   phase_detect ;;
  deps)     phase_deps   ;;
  build)    phase_build  ;;
  validate) phase_validate ;;
  all)
    phase_detect
    phase_deps
    phase_build
    phase_validate
    ;;
  *)
    die "Unknown phase '$PHASE'. Choose: detect | deps | build | validate | all"
    ;;
esac
