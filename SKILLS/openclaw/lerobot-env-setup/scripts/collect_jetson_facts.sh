#!/usr/bin/env bash
# collect_jetson_facts.sh
# Collect Jetson runtime facts relevant to lerobot-env-setup.
# Usage: bash collect_jetson_facts.sh --local --output /tmp/jetson-facts.json

set -euo pipefail

OUTPUT="/tmp/jetson-facts.json"
WHEEL_DIR="$HOME/wheels"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)        shift ;;
    --output)       OUTPUT="$2"; shift 2 ;;
    --wheel-dir)    WHEEL_DIR="$2"; shift 2 ;;
    *)              echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# ── Board ─────────────────────────────────────────────────────────────────────
board=""
if [[ -f /proc/device-tree/model ]]; then
  board="$(tr -d '\0' < /proc/device-tree/model)"
fi

# ── JetPack ───────────────────────────────────────────────────────────────────
jetpack=""
if command -v dpkg &>/dev/null; then
  jetpack="$(dpkg -l nvidia-jetpack 2>/dev/null | awk '/^ii/{print $3}' || true)"
fi

# ── L4T ───────────────────────────────────────────────────────────────────────
l4t=""
if [[ -f /etc/nv_tegra_release ]]; then
  l4t="$(head -1 /etc/nv_tegra_release)"
fi

# ── CUDA ──────────────────────────────────────────────────────────────────────
cuda=""
if command -v nvcc &>/dev/null; then
  cuda="$(nvcc --version 2>/dev/null | grep -oP 'release \K[\d.]+')"
elif [[ -f /usr/local/cuda/version.txt ]]; then
  cuda="$(grep -oP '[\d.]+' /usr/local/cuda/version.txt | head -1)"
fi

# ── Python (system) ───────────────────────────────────────────────────────────
python_ver="$(python3 --version 2>/dev/null | grep -oP '[\d.]+')"

# ── Conda: installed? which binary? ──────────────────────────────────────────
# Search common locations so this works even when conda is not in PATH
conda_installed="false"
conda_bin=""
for _p in \
  "$(command -v conda 2>/dev/null)" \
  "$HOME/miniconda3/bin/conda" \
  "$HOME/anaconda3/bin/conda" \
  "$HOME/miniforge3/bin/conda" \
  "$HOME/mambaforge/bin/conda" \
  "/opt/conda/bin/conda" \
  "/usr/local/conda/bin/conda"; do
  if [[ -n "$_p" && -x "$_p" ]]; then
    conda_installed="true"
    conda_bin="$_p"
    break
  fi
done

# ── Conda envs ────────────────────────────────────────────────────────────────
conda_envs="[]"
if [[ "$conda_installed" == "true" ]]; then
  conda_envs="$("$conda_bin" env list --json 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps([e.split('/')[-1] for e in d.get('envs',[])]))" \
    2>/dev/null || echo '[]')"
fi

# ── lerobot env: package installed? ──────────────────────────────────────────
lerobot_installed="false"
if [[ "$conda_installed" == "true" ]] && echo "$conda_envs" | python3 -c "import json,sys; sys.exit(0 if 'lerobot' in json.load(sys.stdin) else 1)" 2>/dev/null; then
  if "$conda_bin" run -n lerobot python3 -c "import lerobot" 2>/dev/null; then
    lerobot_installed="true"
  fi
fi

# ── torch in lerobot env ──────────────────────────────────────────────────────
torch_ver=""
torch_cuda="unknown"
if [[ "$lerobot_installed" == "true" ]]; then
  torch_ver="$("$conda_bin" run -n lerobot python3 -c "import torch; print(torch.__version__)" 2>/dev/null || true)"
  torch_cuda="$("$conda_bin" run -n lerobot python3 -c "import torch; print(torch.cuda.is_available())" 2>/dev/null || true)"
fi

# ── numpy in lerobot env ──────────────────────────────────────────────────────
numpy_ver=""
if [[ "$lerobot_installed" == "true" ]]; then
  numpy_ver="$("$conda_bin" run -n lerobot python3 -c "import numpy; print(numpy.__version__)" 2>/dev/null || true)"
fi

# ── opencv in lerobot env ─────────────────────────────────────────────────────
opencv_ver=""
if [[ "$lerobot_installed" == "true" ]]; then
  opencv_ver="$("$conda_bin" run -n lerobot python3 -c "import cv2; print(cv2.__version__)" 2>/dev/null || true)"
fi

# ── ffmpeg in lerobot env ─────────────────────────────────────────────────────
ffmpeg_ver=""
if [[ "$conda_installed" == "true" ]] && echo "$conda_envs" | python3 -c "import json,sys; sys.exit(0 if 'lerobot' in json.load(sys.stdin) else 1)" 2>/dev/null; then
  ffmpeg_ver="$("$conda_bin" run -n lerobot ffmpeg -version 2>/dev/null | grep -oP 'ffmpeg version \K[\S]+' || true)"
fi

# ── wheel files present ───────────────────────────────────────────────────────
torch_whl="false"
torchvision_whl="false"
if [[ -f "$WHEEL_DIR/torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl" ]]; then
  torch_whl="true"
fi
if [[ -f "$WHEEL_DIR/torchvision-0.23.0-cp310-cp310-linux_aarch64.whl" ]]; then
  torchvision_whl="true"
fi

# ── serial group ──────────────────────────────────────────────────────────────
serial_group="missing"
if id -nG 2>/dev/null | grep -qw dialout; then
  serial_group="ok"
fi

# ── brltty installed ──────────────────────────────────────────────────────────
brltty_installed="false"
if dpkg -l brltty 2>/dev/null | grep -q '^ii'; then
  brltty_installed="true"
fi

# ── udev rule present ─────────────────────────────────────────────────────────
udev_rule="false"
if [[ -f /etc/udev/rules.d/99-serial-ports.rules ]]; then
  udev_rule="true"
fi

# ── Output JSON ───────────────────────────────────────────────────────────────
python3 - <<EOF
import json
data = {
    "board":              "$board",
    "jetpack":            "$jetpack",
    "l4t":                "$l4t",
    "cuda":               "$cuda",
    "python":             "$python_ver",
    "conda_installed":    $conda_installed,
    "conda_bin":          "$conda_bin",
    "conda_envs":         $conda_envs,
    "lerobot_installed":  $lerobot_installed,
    "wheel_files": {
        "torch":          $torch_whl,
        "torchvision":    $torchvision_whl,
        "wheel_dir":      "$WHEEL_DIR",
    },
    "lerobot_env": {
        "torch_version":  "$torch_ver",
        "torch_cuda":     "$torch_cuda",
        "numpy_version":  "$numpy_ver",
        "opencv_version": "$opencv_ver",
        "ffmpeg_version": "$ffmpeg_ver",
    },
    "serial_group":       "$serial_group",
    "brltty_installed":   $brltty_installed,
    "udev_rule":          $udev_rule,
}
with open("$OUTPUT", "w") as f:
    json.dump(data, f, indent=2)
print(f"[facts] Written to $OUTPUT")
EOF
