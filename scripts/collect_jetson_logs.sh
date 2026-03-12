#!/usr/bin/env bash
set -euo pipefail

OUT_ROOT="${1:-$(pwd)/logs}"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="$OUT_ROOT/jetson_diag_${TS}"
mkdir -p "$OUT_DIR"

echo "[INFO] Writing diagnostics to: $OUT_DIR"

uname -a > "$OUT_DIR/uname.txt" 2>&1 || true
cat /etc/os-release > "$OUT_DIR/os-release.txt" 2>&1 || true
lsusb > "$OUT_DIR/lsusb.txt" 2>&1 || true
lspci > "$OUT_DIR/lspci.txt" 2>&1 || true
ip a > "$OUT_DIR/ip_addr.txt" 2>&1 || true
df -h > "$OUT_DIR/df.txt" 2>&1 || true
free -h > "$OUT_DIR/free.txt" 2>&1 || true
dmesg > "$OUT_DIR/dmesg.txt" 2>&1 || true
journalctl -b > "$OUT_DIR/journalctl_boot.txt" 2>&1 || true

if command -v tegrastats >/dev/null 2>&1; then
  timeout 3 tegrastats > "$OUT_DIR/tegrastats.txt" 2>&1 || true
fi

ARCHIVE="${OUT_DIR}.tar.gz"
tar -czf "$ARCHIVE" -C "$OUT_ROOT" "$(basename "$OUT_DIR")"

echo "[OK] Archive: $ARCHIVE"
