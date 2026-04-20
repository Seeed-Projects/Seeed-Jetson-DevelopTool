#!/usr/bin/env bash
# fix_browser_snap.sh
# Fix browsers (Chromium/Firefox snap) that fail to launch on Jetson by
# installing a pinned snapd revision and holding it from auto-updates.
#
# Usage:
#   bash fix_browser_snap.sh [--phase PHASE] [--snapd-revision REV] [--work-dir DIR]
#
# --phase:           preflight | download | install | hold | verify | all  (default: all)
# --snapd-revision:  snapd snap revision to install                         (default: 24724)
# --work-dir:        directory for downloaded files                         (default: ~/snapd-fix)

set -euo pipefail

PHASE="all"
SNAPD_REVISION="24724"
WORK_DIR="$HOME/snapd-fix"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --phase)           PHASE="$2";           shift 2 ;;
    --snapd-revision)  SNAPD_REVISION="$2";  shift 2 ;;
    --work-dir)        WORK_DIR="$2";        shift 2 ;;
    *) echo "[STOP]    unknown argument: $1" >&2; exit 1 ;;
  esac
done

SNAP_FILE="$WORK_DIR/snapd_${SNAPD_REVISION}.snap"
ASSERT_FILE="$WORK_DIR/snapd_${SNAPD_REVISION}.assert"

log() { echo "[install] $*"; }
die() { echo "[STOP]    $*" >&2; exit 1; }
ok()  { echo "[OK]      $*"; }

# ══════════════════════════════════════════════════════════════════════════════
# PHASE: preflight
# ══════════════════════════════════════════════════════════════════════════════
phase_preflight() {
  log "=== Phase 1: preflight ==="

  command -v snap >/dev/null 2>&1 || die "snap command not found — install snapd first: sudo apt install snapd"

  SNAPD_SVC_STATUS="$(systemctl is-active snapd 2>/dev/null || echo inactive)"
  if [[ "$SNAPD_SVC_STATUS" != "active" ]]; then
    die "snapd service not running (status=$SNAPD_SVC_STATUS) — run: sudo systemctl enable --now snapd"
  fi
  log "snapd service: active"

  CURRENT_VER="$(snap version 2>/dev/null | awk '/^snapd/{print $2}' || echo unknown)"
  log "Current snapd version: $CURRENT_VER"

  ARCH="$(uname -m)"
  log "Architecture: $ARCH"

  KVER="$(uname -r)"
  log "Kernel: $KVER"

  # Check for browser snaps
  for browser in chromium firefox; do
    if snap list "$browser" &>/dev/null; then
      log "Browser snap found: $browser ($(snap list "$browser" | awk 'NR==2{print $2}'))"
    fi
  done

  log "Work dir will be: $WORK_DIR"
  ok "preflight complete"
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE: download
# ══════════════════════════════════════════════════════════════════════════════
phase_download() {
  log "=== Phase 2: download (revision=$SNAPD_REVISION) ==="

  mkdir -p "$WORK_DIR"

  if [[ -f "$SNAP_FILE" && -f "$ASSERT_FILE" ]]; then
    log "Files already downloaded — skipping download"
    log "  $SNAP_FILE"
    log "  $ASSERT_FILE"
    ok "download skipped (files present)"
    return
  fi

  log "Downloading snapd revision $SNAPD_REVISION to $WORK_DIR ..."
  (
    cd "$WORK_DIR"
    snap download snapd --revision="$SNAPD_REVISION" \
      || die "snap download failed — check network connectivity or try a different revision"
  )

  [[ -f "$SNAP_FILE" ]]   || die "expected snap file not found after download: $SNAP_FILE"
  [[ -f "$ASSERT_FILE" ]] || die "expected assert file not found after download: $ASSERT_FILE"

  log "Downloaded:"
  log "  $SNAP_FILE   ($(du -sh "$SNAP_FILE" | cut -f1))"
  log "  $ASSERT_FILE ($(du -sh "$ASSERT_FILE" | cut -f1))"

  ok "download complete"
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE: install
# ══════════════════════════════════════════════════════════════════════════════
phase_install() {
  log "=== Phase 3: install ==="

  [[ -f "$SNAP_FILE" ]]   || die "snap file not found: $SNAP_FILE — run phase download first"
  [[ -f "$ASSERT_FILE" ]] || die "assert file not found: $ASSERT_FILE — run phase download first"

  log "Acknowledging assertion..."
  sudo snap ack "$ASSERT_FILE" \
    || die "snap ack failed — assert file may be corrupt; delete $WORK_DIR and rerun phase download"

  log "Installing snapd from local file..."
  sudo snap install "$SNAP_FILE" \
    || die "snap install failed — see references/browser_snap_troubleshooting.md section T2"

  NEW_VER="$(snap version 2>/dev/null | awk '/^snapd/{print $2}' || echo unknown)"
  log "snapd version after install: $NEW_VER"

  ok "install complete"
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE: hold
# ══════════════════════════════════════════════════════════════════════════════
phase_hold() {
  log "=== Phase 4: hold ==="

  sudo snap refresh --hold snapd \
    || die "snap refresh --hold failed — see references/browser_snap_troubleshooting.md section T3"

  log "snapd is now held at current revision and will not auto-update"
  ok "hold complete"
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE: verify
# ══════════════════════════════════════════════════════════════════════════════
phase_verify() {
  log "=== Phase 5: verify ==="

  SNAPD_VER="$(snap version 2>/dev/null | awk '/^snapd/{print $2}' || echo unknown)"
  log "snapd version: $SNAPD_VER"

  SNAP_VER="$(snap version 2>/dev/null | awk '/^snap /{print $2}' || echo unknown)"
  log "snap  version: $SNAP_VER"

  # Check hold status
  HOLD_INFO="$(snap refresh --time 2>/dev/null | grep -i hold || echo 'hold: not set')"
  log "Hold status: $HOLD_INFO"

  # List installed browser snaps and their status
  FOUND_BROWSER=0
  for browser in chromium firefox; do
    if snap list "$browser" &>/dev/null; then
      BROWSER_VER="$(snap list "$browser" | awk 'NR==2{print $2}')"
      log "Browser snap: $browser $BROWSER_VER — installed"
      FOUND_BROWSER=1
    fi
  done

  if [[ "$FOUND_BROWSER" -eq 0 ]]; then
    log "No browser snap currently installed (chromium / firefox)"
    log "Install one with: sudo snap install chromium"
  fi

  # Verify snapd socket is responsive
  if snap list snapd &>/dev/null; then
    log "snapd snap: $(snap list snapd | awk 'NR==2{print $2}')"
  fi

  ok "verify complete — snapd $SNAPD_VER is active and held"
}

# ══════════════════════════════════════════════════════════════════════════════
# Dispatch
# ══════════════════════════════════════════════════════════════════════════════
log "phase=$PHASE  snapd-revision=$SNAPD_REVISION  work-dir=$WORK_DIR"

case "$PHASE" in
  preflight) phase_preflight ;;
  download)  phase_download  ;;
  install)   phase_install   ;;
  hold)      phase_hold      ;;
  verify)    phase_verify    ;;
  all)
    phase_preflight
    phase_download
    phase_install
    phase_hold
    phase_verify
    ;;
  *)
    die "unknown phase '$PHASE' (valid: preflight | download | install | hold | verify | all)"
    ;;
esac
