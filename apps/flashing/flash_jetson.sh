#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <board_config> <target_storage> [--execute]"
  echo "Example: $0 jetson-orin-nano-devkit internal"
  exit 1
fi

BOARD_CONFIG="$1"
TARGET_STORAGE="$2"
EXECUTE="${3:-}"
L4T_DIR="${L4T_DIR:-$HOME/nvidia/nvidia_sdk/Linux_for_Tegra}"

if [[ ! -d "$L4T_DIR" ]]; then
  echo "[ERROR] Linux_for_Tegra not found: $L4T_DIR"
  echo "Set L4T_DIR env var before running this script."
  exit 2
fi

FLASH_CMD="sudo ./tools/kernel_flash/l4t_initrd_flash.sh --external-device ${TARGET_STORAGE} -c tools/kernel_flash/flash_l4t_external.xml --showlogs --network usb0 ${BOARD_CONFIG} internal"

echo "[INFO] L4T_DIR      : $L4T_DIR"
echo "[INFO] BOARD_CONFIG : $BOARD_CONFIG"
echo "[INFO] STORAGE      : $TARGET_STORAGE"
echo "[INFO] Ensure device is in recovery mode before flashing."
echo

echo "[PREVIEW] Command to run:"
echo "cd $L4T_DIR && $FLASH_CMD"

if [[ "$EXECUTE" == "--execute" ]]; then
  echo "[RUN] Executing flash command..."
  cd "$L4T_DIR"
  eval "$FLASH_CMD"
else
  echo "[SAFE] Preview mode. Add --execute to run."
fi
