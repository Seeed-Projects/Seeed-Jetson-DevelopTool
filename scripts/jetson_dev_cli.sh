#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "jetson-develop CLI"
echo "1) Flash command preview"
echo "2) Create app workspace"
echo "3) Collect diagnostics"
read -rp "Select [1-3]: " CHOICE

case "$CHOICE" in
  1)
    read -rp "Board config: " BOARD
    read -rp "Target storage (internal/nvme0n1p1/...): " STORAGE
    "$ROOT/apps/flashing/flash_jetson.sh" "$BOARD" "$STORAGE"
    ;;
  2)
    read -rp "App name: " APP
    read -rp "Template (cv/genai/robotics/general): " TEMPLATE
    "$ROOT/apps/development/create_app_workspace.sh" "$APP" "$TEMPLATE"
    ;;
  3)
    "$ROOT/apps/diagnostics/collect_jetson_logs.sh"
    ;;
  *)
    echo "Invalid option"
    exit 1
    ;;
esac
