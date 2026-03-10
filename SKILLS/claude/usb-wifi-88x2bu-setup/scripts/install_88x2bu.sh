#!/usr/bin/env bash
# install_88x2bu.sh
# Install and enable RTL88x2bu USB Wi-Fi (e.g. 0bda:b812)
#
# Usage examples:
#   bash install_88x2bu.sh --phase preflight --usb-id 0bda:b812
#   bash install_88x2bu.sh --phase all --usb-id 0bda:b812 --sudo-mode prompt

set -euo pipefail

USB_ID="0bda:b812"
REPO_URL="https://github.com/morrownr/88x2bu-20210702.git"
WORKDIR="$HOME/drivers"
REPO_DIR="$WORKDIR/88x2bu-20210702"
MODULE_NAME="88x2bu"
PHASE="all"
SUDO_MODE="noninteractive"   # noninteractive | prompt
AUTO_FIX_JETSON_LINKS="yes"  # yes | no
IFNAME=""
CONNECT_SSID=""
CONNECT_PASSWORD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --phase) PHASE="$2"; shift 2 ;;
    --usb-id) USB_ID="$2"; shift 2 ;;
    --repo-url) REPO_URL="$2"; shift 2 ;;
    --workdir) WORKDIR="$2"; REPO_DIR="$2/88x2bu-20210702"; shift 2 ;;
    --repo-dir) REPO_DIR="$2"; shift 2 ;;
    --module-name) MODULE_NAME="$2"; shift 2 ;;
    --sudo-mode) SUDO_MODE="$2"; shift 2 ;;
    --auto-fix-jetson-links) AUTO_FIX_JETSON_LINKS="$2"; shift 2 ;;
    --ifname) IFNAME="$2"; shift 2 ;;
    --ssid) CONNECT_SSID="$2"; shift 2 ;;
    --password) CONNECT_PASSWORD="$2"; shift 2 ;;
    *) echo "[STOP]    unknown arg: $1" >&2; exit 1 ;;
  esac
done

KVER="$(uname -r)"
ARCH="$(uname -m)"

log()  { echo "[install] $*"; }
die()  { echo "[STOP]    $*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

run_root() {
  if [[ "$EUID" -eq 0 ]]; then
    "$@"
    return
  fi

  if [[ "$SUDO_MODE" == "noninteractive" ]]; then
    sudo -n "$@" || die "sudo is required but passwordless sudo is not available. Re-run with --sudo-mode prompt in an interactive terminal."
  elif [[ "$SUDO_MODE" == "prompt" ]]; then
    sudo "$@"
  else
    die "invalid --sudo-mode '$SUDO_MODE' (use noninteractive or prompt)"
  fi
}

module_interfaces() {
  local n mod
  for n in /sys/class/net/*; do
    [[ -e "$n" ]] || continue
    mod="$(basename "$(readlink -f "$n/device/driver/module" 2>/dev/null || true)")"
    if [[ "$mod" == "$MODULE_NAME" ]]; then
      basename "$n"
    fi
  done
}

find_kernel_source_tree() {
  local p

  if [[ -d "/lib/modules/$KVER/build" && -f "/lib/modules/$KVER/build/Makefile" ]]; then
    echo "/lib/modules/$KVER/build"
    return
  fi

  p="/usr/src/linux-headers-${KVER}-ubuntu22.04_aarch64/3rdparty/canonical/linux-jammy/kernel-source"
  if [[ -d "$p" && -f "$p/Makefile" ]]; then
    echo "$p"
    return
  fi

  p="$(find /usr/src -maxdepth 6 -type f -name Makefile -path '*/kernel-source/Makefile' 2>/dev/null | head -n 1 || true)"
  if [[ -n "$p" ]]; then
    dirname "$p"
    return
  fi

  p="/usr/src/linux-headers-$KVER"
  if [[ -d "$p" && -f "$p/Makefile" ]]; then
    echo "$p"
    return
  fi

  echo ""
}

fix_jetson_module_links_if_needed() {
  local ksrc="$1"
  local build_link="/lib/modules/$KVER/build"
  local source_link="/lib/modules/$KVER/source"

  if [[ "$AUTO_FIX_JETSON_LINKS" != "yes" ]]; then
    return
  fi

  if [[ "$KVER" == *tegra* ]]; then
    if [[ -e "$build_link" && ! -L "$build_link" ]]; then
      log "Jetson build path is a real directory/file; removing it: $build_link"
      run_root rm -rf "$build_link"
    fi

    if [[ "$(readlink -f "$build_link" 2>/dev/null || true)" != "$ksrc" ]]; then
      log "Jetson detected; linking $build_link -> $ksrc"
      run_root ln -sfn "$ksrc" "$build_link"
    fi

    if [[ "$(readlink -f "$source_link" 2>/dev/null || true)" != "$ksrc" ]]; then
      log "Jetson detected; linking $source_link -> $ksrc"
      run_root ln -sfn "$ksrc" "$source_link"
    fi
  fi
}

phase_preflight() {
  require_cmd uname
  require_cmd lsusb
  require_cmd git
  require_cmd make

  log "Kernel: $KVER"
  log "Arch:   $ARCH"
  log "USB ID: $USB_ID"

  if lsusb | grep -qi "$USB_ID"; then
    log "USB adapter detected: $USB_ID"
  else
    die "usb device $USB_ID not detected via lsusb"
  fi

  log "[OK] preflight passed"
}

phase_deps() {
  log "Installing build dependencies"
  run_root apt-get update
  run_root apt-get install -y dkms build-essential bc git libelf-dev rfkill iw

  if [[ "$KVER" == *tegra* ]]; then
    log "Jetson kernel detected; ensuring nvidia-l4t-kernel-headers is installed"
    run_root apt-get install -y nvidia-l4t-kernel-headers
  else
    log "Ensuring linux headers for running kernel are installed"
    run_root apt-get install -y "linux-headers-$KVER"
  fi

  log "[OK] deps phase complete"
}

phase_repo() {
  mkdir -p "$WORKDIR"
  if [[ -d "$REPO_DIR/.git" ]]; then
    log "Updating existing repo at $REPO_DIR"
    git -C "$REPO_DIR" pull --ff-only
  else
    log "Cloning repo: $REPO_URL"
    git clone "$REPO_URL" "$REPO_DIR"
  fi

  if [[ -f "$REPO_DIR/supported-device-IDs" ]]; then
    if grep -qi "$USB_ID" "$REPO_DIR/supported-device-IDs"; then
      log "Repo support list includes USB ID $USB_ID"
    else
      log "Warning: USB ID $USB_ID not found in supported-device-IDs; build may still work"
    fi
  fi

  log "[OK] repo phase complete"
}

phase_build() {
  [[ -d "$REPO_DIR" ]] || die "repo dir missing: $REPO_DIR (run phase repo first)"
  local ksrc
  ksrc="$(find_kernel_source_tree)"
  [[ -n "$ksrc" ]] || die "unable to locate a usable kernel source tree for $KVER"

  log "Kernel source: $ksrc"
  fix_jetson_module_links_if_needed "$ksrc"

  log "Building $MODULE_NAME for kernel $KVER"
  (
    cd "$REPO_DIR"
    make clean >/tmp/${MODULE_NAME}-clean.log 2>&1 || true
    make -j"$(nproc)" KVER="$KVER" KSRC="$ksrc" >/tmp/${MODULE_NAME}-build.log 2>&1 || {
      tail -n 120 "/tmp/${MODULE_NAME}-build.log"
      die "build failed; see /tmp/${MODULE_NAME}-build.log"
    }
    [[ -f "${MODULE_NAME}.ko" ]] || die "build finished but ${MODULE_NAME}.ko not found"
  )

  log "[OK] build phase complete"
}

phase_install() {
  [[ -f "$REPO_DIR/${MODULE_NAME}.ko" ]] || die "missing $REPO_DIR/${MODULE_NAME}.ko (run phase build first)"
  log "Installing module into /lib/modules/$KVER"

  if run_root make -C "$REPO_DIR" install; then
    :
  else
    log "make install failed; falling back to direct copy"
    run_root install -D -m 644 "$REPO_DIR/${MODULE_NAME}.ko" "/lib/modules/$KVER/updates/dkms/${MODULE_NAME}.ko"
    run_root depmod -a "$KVER"
  fi

  log "[OK] install phase complete"
}

phase_enable() {
  require_cmd ip
  log "Loading module: $MODULE_NAME"
  run_root modprobe "$MODULE_NAME" || die "modprobe $MODULE_NAME failed"

  local picked_if=""
  if [[ -n "$IFNAME" ]]; then
    picked_if="$IFNAME"
  else
    picked_if="$(module_interfaces | head -n 1 || true)"
  fi

  if [[ -z "$picked_if" ]]; then
    echo "[FAIL]    $MODULE_NAME module loaded but no interface found."
    echo "[FAIL]    Replug adapter and run phase enable again."
    exit 1
  fi

  log "Bringing interface up: $picked_if"
  run_root ip link set "$picked_if" up

  if [[ -n "$CONNECT_SSID" ]]; then
    require_cmd nmcli
    if [[ -z "$CONNECT_PASSWORD" ]]; then
      die "--ssid was provided but --password is empty"
    fi
    log "Connecting $picked_if to SSID: $CONNECT_SSID"
    run_root nmcli dev wifi connect "$CONNECT_SSID" password "$CONNECT_PASSWORD" ifname "$picked_if"
  fi

  log "[OK] enable phase complete (interface=$picked_if)"
}

phase_verify() {
  require_cmd lsmod
  require_cmd modinfo

  if lsmod | grep -q "^${MODULE_NAME}\b"; then
    log "Module loaded: $MODULE_NAME"
  else
    die "module not loaded: $MODULE_NAME"
  fi

  log "Module metadata:"
  modinfo "$MODULE_NAME" | sed -n '1,20p'

  local ifs
  ifs="$(module_interfaces || true)"
  if [[ -n "$ifs" ]]; then
    log "Interfaces using $MODULE_NAME:"
    echo "$ifs"
  else
    echo "[FAIL]    No interface currently bound to module $MODULE_NAME."
    exit 1
  fi

  if command -v nmcli >/dev/null 2>&1; then
    log "nmcli device status:"
    nmcli -f DEVICE,TYPE,STATE,CONNECTION device status || true
  fi

  log "[OK] verify phase complete"
}

log "phase=$PHASE usb-id=$USB_ID module=$MODULE_NAME repo=$REPO_URL"

case "$PHASE" in
  preflight) phase_preflight ;;
  deps)      phase_deps ;;
  repo)      phase_repo ;;
  build)     phase_build ;;
  install)   phase_install ;;
  enable)    phase_enable ;;
  verify)    phase_verify ;;
  all)
    phase_preflight
    phase_deps
    phase_repo
    phase_build
    phase_install
    phase_enable
    phase_verify
    ;;
  *)
    die "unknown phase '$PHASE' (valid: preflight|deps|repo|build|install|enable|verify|all)"
    ;;
esac
