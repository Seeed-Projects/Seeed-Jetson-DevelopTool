---
name: hybrid-bsp-dk-to-recomputer
description: Make Hybrid BSP from Orin Nano DevKit to reComputer Classic/Super. Clones DevKit APP, regenerates target QSPI with correct HDMI pinmux and camera overlay, assembles cross-board mfi bundle. Requires Ubuntu 22.04 host, JetPack 6.2/L4T 36.4.3, USB-C cable.
---

# Hybrid BSP: Orin Nano DevKit → reComputer Classic/Super

Clone a complete DevKit development environment, swap in the target board's
QSPI firmware (pinmux + camera overlay), and flash the hybrid bundle onto
a reComputer Classic or Super.

Source: https://wiki.seeedstudio.com/cn/make_diy_bsp_from_orin_nano_devkit_to_recomputer_classic_and_super/

---

## Execution model

Run one phase at a time. After each phase:
- Relay all command output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed.

**Before starting, ask the user:**

1. Target board?
   - `recomputer-orin-j401` (reComputer Classic J4011/J4012)
   - `recomputer-orin-super-j401` (reComputer Super)
2. Module SKU? (guide verified on `0005` = Orin Nano 8GB)
3. L4T version? (guide verified on `36.4.3`)

Set variables based on user choice:

| Variable | Classic | Super |
|----------|---------|-------|
| `TARGET_BOARD` | `recomputer-orin-j401` | `recomputer-orin-super-j401` |
| `TARGET_CONF` | `recomputer-orin-j401.conf` | `recomputer-orin-super-j401.conf` |
| `PINMUX` | `tegra234-mb1-bct-pinmux-p3767-hdmi-a03.dtsi` | `recomputer-super-orin-j401-pinmux-p3767-hdmi-a03.dtsi` |
| `CAMERA_OVERLAY` | `tegra234-p3767-camera-p3768-imx219-dual-seeed.dtbo` | `tegra234-p3767-camera-p3768-imx219-quad-seeed.dtbo` |
| `QSPI_DOWNLOAD_URL` | `https://files.seeedstudio.com/wiki/reComputer-Jetson/FAQ/dk-to-classic/j401_qspi_internal_save.tar.gz` | `https://files.seeedstudio.com/wiki/reComputer-Jetson/FAQ/dk-to-super/super_j401_qspi_internal_save.tar.gz` |

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Source device | NVIDIA Jetson Orin Nano **Developer Kit** (SKU 0005, NVMe boot) |
| Target device | Seeed reComputer Classic J4011/J4012 or reComputer Super (module SKU 0005 recommended) |
| Host PC | Ubuntu 22.04 x86_64 |
| Cable | USB Type-C data cable (flashing port) |
| JetPack | 6.2 / L4T 36.4.3 (guide verified) |
| Disk space | ≥ 100GB free (backup + dual mfi + snapshots) |

> **DANGER:** reComputer Classic series has insufficient cooling for MAXN super mode. Do NOT enable MAXN mode on reComputer Classic with JetPack 6.2.

> **DANGER:** Do NOT flash the DevKit's `mfi_jetson-orin-nano-devkit-nvme` directly to the target board. Do NOT swap a single `.dtb` and call it adapted. Do NOT flash Classic's hybrid bundle to Super or vice versa — pinmux and camera overlays differ.

---

## Board reference

| Item | DevKit | reComputer Classic | reComputer Super |
|------|--------|-------------------|-----------------|
| board-name | `jetson-orin-nano-devkit-nvme` | `recomputer-orin-j401` | `recomputer-orin-super-j401` |
| Config file | `p3768-0000-p3767-0000-a0-nvme.conf` | `recomputer-orin-j401.conf` | `recomputer-orin-super-j401.conf` |
| Pinmux | NVIDIA DevKit (DP) | Classic HDMI | Super HDMI |
| Camera overlay | NVIDIA dynamic | Seeed dual IMX219 | Seeed quad IMX219 |
| SKU0005 main DTB | `tegra234-p3768-0000+p3767-0005-nv-super.dtb` | same (still NVIDIA's `*-0005-nv-super.dtb`) | same |
| Final mfi | DevKit-only | Classic-only | Super-only |

---

## Phase 1 — Prepare Linux_for_Tegra workspace (~10 min)

Download the Seeed L4T working package for your JetPack version (e.g. `L4T_36.4.3_plus.tar.gz`) from the Seeed wiki. Install host dependencies:

```bash
sudo apt-get update -y
sudo apt-get install -y \
  build-essential flex bison libssl-dev \
  sshpass abootimg nfs-kernel-server \
  libxml2-utils qemu-user-static
```

Extract and prepare:

```bash
sudo tar xpf L4T_36.4.3_plus.tar.gz
cd Linux_for_Tegra/
sudo ./apply_binaries.sh
cd ..
```

Set cross-compilation environment:

```bash
export ARCH=arm64
export CROSS_COMPILE="$PWD/aarch64--glibc--stable-2022.08-1/bin/aarch64-buildroot-linux-gnu-"
export PATH="$PWD/aarch64--glibc--stable-2022.08-1/bin:$PATH"
export INSTALL_MOD_PATH="$PWD/Linux_for_Tegra/rootfs/"
```

Build kernel and install modules:

```bash
cd Linux_for_Tegra/source
./nvbuild.sh
./do_copy.sh
./nvbuild.sh -i
```

Validation:

```bash
# Classic:
test -f Linux_for_Tegra/recomputer-orin-j401.conf
test -f Linux_for_Tegra/jetson-orin-nano-devkit-nvme.conf
ls Linux_for_Tegra/kernel/dtb/tegra234-j401-*-recomputer.dtb
ls Linux_for_Tegra/kernel/dtb/tegra234-dcb-p3767-0000-hdmi.dtbo

# Super:
test -f Linux_for_Tegra/recomputer-orin-super-j401.conf
test -f Linux_for_Tegra/jetson-orin-nano-devkit-nvme.conf
test -f Linux_for_Tegra/kernel/dtb/tegra234-dcb-p3767-0000-hdmi.dtbo
test -f Linux_for_Tegra/kernel/dtb/tegra234-p3767-camera-p3768-imx219-quad-seeed.dtbo
```

`[OK]` when all `test -f` pass. `[STOP]` if `apply_binaries.sh` or `nvbuild.sh` fails.

---

## Phase 2 — Backup DevKit complete environment (~15–30 min)

### 2.1 Enter recovery mode

Connect the DevKit flashing port to the host via USB-C. Put the DevKit into recovery mode. Verify:

```bash
lsusb | grep 0955:7523   # must show NVIDIA Corp. APX
```

> During backup the device may briefly show `0955:7035` (Linux for Tegra / initrd) — this is normal.

### 2.2 Start NFS and stop udisks2

```bash
sudo systemctl stop udisks2.service
sudo service nfs-kernel-server start
```

### 2.3 Backup

```bash
cd Linux_for_Tegra
sudo ./tools/backup_restore/l4t_backup_restore.sh \
  -e nvme0n1 -b -c jetson-orin-nano-devkit-nvme
```

> **WARNING:** When the source is a DevKit, do NOT use the target board-name for the first backup — `board_spec` and subsequent baselines will be wrong.

### 2.4 Validate backup

```bash
ls -lah tools/backup_restore/images/
head -5 tools/backup_restore/images/nvpartitionmap.txt
```

Expected:
- `board_spec` contains `jetson-orin-nano-devkit-nvme`
- `nvme0n1p1.tar.zst` (or converted large APP) is GB-scale
- `QSPI0.img` exists (this is the **DevKit** QSPI — cannot be reused for target board)

### 2.5 Snapshot (recommended)

```bash
sudo cp -a tools/backup_restore/images ~/backup_images_dk_sku0005
```

`[OK]` when backup images are GB-scale and `board_spec` is correct. `[STOP]` if device not detected — check recovery mode and USB cable.

---

## Phase 3 — DevKit same-board DIY BSP (optional, ~15–30 min)

> This phase is ONLY needed if you want to re-flash the DevKit itself. Skip to Phase 4 if your goal is the hybrid target board bundle.
>
> However, if you run this phase, the `tools/kernel_flash/images/external/` directory it produces can be reused in Phase 5 as the APP data source.

Put the DevKit back into APX recovery mode (`lsusb` → `0955:7523`):

```bash
cd Linux_for_Tegra
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --use-backup-image --no-flash --network usb0 --massflash 5 \
  jetson-orin-nano-devkit-nvme internal
```

Expected output: `mfi_jetson-orin-nano-devkit-nvme/` and `mfi_jetson-orin-nano-devkit-nvme.tar.gz`.

> **DANGER:** This package is for re-flashing the DevKit ONLY. Do NOT flash it to the target board. Its QSPI cannot be reused for the hybrid bundle.

`[OK]` when `mfi_jetson-orin-nano-devkit-nvme.tar.gz` is generated. Skip to Phase 4 if not needed.

---

## Phase 4 — Generate target board QSPI (~10–20 min)

### Critical: QSPI trap

`--use-backup-image` via `convert_backup_image_to_initrd_flash` places:
- NVMe/APP → `tools/kernel_flash/images/external/`
- **Source** `QSPI0.img` → `tools/kernel_flash/images/internal/`

Therefore:
- Changing only a `.dtb` in `mfi/.../rootfs` is **ineffective** (the real flash uses bak/QSPI)
- Using `--use-backup-image` with a target board-name still flashes the **DevKit QSPI** (DP pinmux) — HDMI/USB may be broken
- `--flash-only` does **not** recompute the image from conf

The target board's real differences are in the conf's **HDMI pinmux + DCB/camera overlay**.

### Option A: Quick path (download pre-built QSPI)

If target is reComputer Classic/Super, module SKU 0005, L4T 36.4.3 — download the pre-built QSPI internal:

```bash
# Classic:
wget -O j401_qspi_internal_save.tar.gz \
  https://files.seeedstudio.com/wiki/reComputer-Jetson/FAQ/dk-to-classic/j401_qspi_internal_save.tar.gz

# Super:
wget -O super_j401_qspi_internal_save.tar.gz \
  https://files.seeedstudio.com/wiki/reComputer-Jetson/FAQ/dk-to-super/super_j401_qspi_internal_save.tar.gz

mkdir -p Linux_for_Tegra/tools/kernel_flash/images/internal
# Classic:
tar xpf j401_qspi_internal_save.tar.gz \
  -C Linux_for_Tegra/tools/kernel_flash/images/internal/
# Super:
tar xpf super_j401_qspi_internal_save.tar.gz \
  -C Linux_for_Tegra/tools/kernel_flash/images/internal/
```

> If any of these conditions do not hold (different SKU, different L4T), you MUST use Option B.

After downloading, you still need to create the mfi directory skeleton (Option B does this automatically via `l4t_initrd_flash.sh`):

```bash
cd Linux_for_Tegra
# Classic:
mkdir -p mfi_recomputer-orin-j401/tools/kernel_flash/images/internal
mkdir -p mfi_recomputer-orin-j401/tools/kernel_flash/images/external
cp -a tools/kernel_flash/images/internal/. \
  mfi_recomputer-orin-j401/tools/kernel_flash/images/internal/
cp -a recomputer-orin-j401.conf \
  mfi_recomputer-orin-j401/recomputer-orin-j401.conf

# Super:
mkdir -p mfi_recomputer-orin-super-j401/tools/kernel_flash/images/internal
mkdir -p mfi_recomputer-orin-super-j401/tools/kernel_flash/images/external
cp -a tools/kernel_flash/images/internal/. \
  mfi_recomputer-orin-super-j401/tools/kernel_flash/images/internal/
cp -a recomputer-orin-super-j401.conf \
  mfi_recomputer-orin-super-j401/recomputer-orin-super-j401.conf
```

Skip to Phase 5.

### Option B: Generate QSPI from scratch

Device must be in APX. Module parameters must match the backup (e.g. 3767 / 0005 / 300 / V.2).

**For reComputer Classic:**

```bash
cd Linux_for_Tegra
sudo BOARDID=3767 BOARDSKU=0005 FAB=300 BOARDREV=V.2 CHIP_SKU=00:00:00:D5 \
  ./tools/kernel_flash/l4t_initrd_flash.sh \
  --external-device nvme0n1p1 \
  -c tools/kernel_flash/flash_l4t_t234_nvme.xml \
  -p "-c bootloader/generic/cfg/flash_t234_qspi.xml --no-systemimg" \
  --no-flash --massflash 5 --showlogs --network usb0 \
  recomputer-orin-j401 internal
```

**For reComputer Super** (requires an NVMe alias conf first):

```bash
cd Linux_for_Tegra
cat > recomputer-orin-super-j401-nvme.conf <<'EOF'
source "${LDK_DIR}/recomputer-orin-super-j401.conf";
EOF

sudo BOARDID=3767 BOARDSKU=0005 FAB=300 BOARDREV=V.2 \
  CHIP_SKU=00:00:00:D5 \
  ./tools/kernel_flash/l4t_initrd_flash.sh \
  --external-device nvme0n1p1 \
  -c tools/kernel_flash/flash_l4t_t234_nvme.xml \
  -p "-c bootloader/generic/cfg/flash_t234_qspi.xml --no-systemimg" \
  --no-flash --massflash 5 --showlogs --network usb0 \
  recomputer-orin-super-j401-nvme external
```

> **DANGER:** For Super, do NOT use `internal` as the final rootdev. This causes MB2 to configure secondary storage as `SDCARD instance: 0`, and without an SD card the boot hangs at `Busy Spin`.

Verify logs contain the correct pinmux:
- Classic: `tegra234-mb1-bct-pinmux-p3767-hdmi-a03`
- Super: `recomputer-super-orin-j401-pinmux-p3767-hdmi-a03` and `tegra234-p3767-camera-p3768-imx219-quad-seeed.dtbo`

Save the new QSPI internal:

```bash
# Classic:
sudo cp -a tools/kernel_flash/images/internal ~/j401_qspi_internal_save
# Super:
sudo cp -a tools/kernel_flash/images/internal ~/super_j401_qspi_internal_save
```

`[OK]` when `internal/` contains split QSPI files (not a single DevKit `QSPI0.img`). `[STOP]` if logs show DevKit pinmux instead of target pinmux.

---

## Phase 5 — Assemble Hybrid mfi bundle (~5–10 min)

### 5.1 Prepare APP-only (remove DevKit QSPI)

```bash
cd Linux_for_Tegra
sudo cp -a ~/backup_images_dk_sku0005 \
  tools/backup_restore/images_app_only
sudo rm -f tools/backup_restore/images_app_only/QSPI0.img
sudo sed -i '/qspi/Id' tools/backup_restore/images_app_only/nvpartitionmap.txt
```

Convert APP-only to initrd flash `external/` images:

```bash
# Method 1: Re-run backup tool with --use-backup-image to generate external images
# This converts the APP-only backup into initrd flash external/ format
cd Linux_for_Tegra
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --use-backup-image --no-flash --network usb0 --massflash 5 \
  jetson-orin-nano-devkit-nvme internal
# Then copy the generated external/ to the workspace:
# cp -a tools/kernel_flash/images/external/. tools/kernel_flash/images/external_bak/

# Method 2: If Phase 3 was run, reuse its external/ directly (faster)
# cp -a mfi_jetson-orin-nano-devkit-nvme/tools/kernel_flash/images/external/. \
#   tools/kernel_flash/images/external/
```

> The `--use-backup-image` flag triggers `convert_backup_image_to_initrd_flash` internally, which converts the backup APP into the `external/` image format. If Method 1 fails, use Method 2 or manually run `l4t_initrd_flash.sh --use-backup-image` with the DevKit board-name.

### 5.2 Assemble the target mfi directory

**For reComputer Classic:**

The mfi directory was created by Phase 4 Option B (or the skeleton from Option A). Now place the external APP:

```bash
cd Linux_for_Tegra
# Copy the converted external APP into the mfi directory
sudo cp -a tools/kernel_flash/images/external/. \
  mfi_recomputer-orin-j401/tools/kernel_flash/images/external/
```

Final directory structure:

| Path | Content |
|------|---------|
| `mfi_recomputer-orin-j401/recomputer-orin-j401.conf` | Exists |
| `.../tools/kernel_flash/images/internal/` | J401 new QSPI (no DevKit single `QSPI0.img`; `flash.idx` is multi-line split) |
| `.../tools/kernel_flash/images/external/nvme0n1p1_bak.img` | GB-scale APP |

Optional archive:

```bash
cd Linux_for_Tegra
sudo tar czf mfi_recomputer-orin-j401.tar.gz mfi_recomputer-orin-j401
```

**For reComputer Super:**

> **DANGER:** Do NOT blindly copy the entire DevKit mfi `external/`. If the DevKit source disk is 256GB but the Super target disk is 128GB, the source GPT will cause "GPT is larger than device storage" at `partprobe`.

Use the standard external layout generated by the Super/current workspace, then only replace the APP content:

```bash
cd Linux_for_Tegra
# Use standard external generated by Super workspace:
sudo cp -a tools/kernel_flash/images/external/. \
  mfi_recomputer-orin-super-j401/tools/kernel_flash/images/external/

# Only reuse DevKit APP content:
# Source path depends on whether Phase 3 was run:
#   - Phase 3 run: mfi_jetson-orin-nano-devkit-nvme/tools/kernel_flash/images/external/
#   - Phase 3 skipped: tools/kernel_flash/images/external/ (from Phase 5.1 conversion)
APP_SRC=""
if [ -f mfi_jetson-orin-nano-devkit-nvme/tools/kernel_flash/images/external/nvme0n1p1_bak.img ]; then
  APP_SRC="mfi_jetson-orin-nano-devkit-nvme/tools/kernel_flash/images/external"
elif [ -f tools/kernel_flash/images/external/nvme0n1p1_bak.img ]; then
  APP_SRC="tools/kernel_flash/images/external"
else
  echo "[STOP] No APP image found. Run Phase 5.1 conversion or Phase 3 first."
  exit 1
fi
sudo cp -a "$APP_SRC/nvme0n1p1_bak.img"* \
  mfi_recomputer-orin-super-j401/tools/kernel_flash/images/external/

sudo tee \
  mfi_recomputer-orin-super-j401/tools/kernel_flash/images/external/flash.cfg \
  >/dev/null <<'EOF'
APP_ext=nvme0n1p1_bak.img
external_device=nvme0n1p1
EOF
```

Validation:

```bash
test -f mfi_recomputer-orin-super-j401/recomputer-orin-super-j401.conf
test -f mfi_recomputer-orin-super-j401/tools/kernel_flash/images/external/nvme0n1p1_bak.img
test ! -f mfi_recomputer-orin-super-j401/tools/kernel_flash/images/internal/QSPI0.img
```

All three must pass:
- `internal/` is the newly generated Super QSPI
- `external/` GPT is smaller than the target physical disk
- `APP_ext` points to the DevKit's `nvme0n1p1_bak.img`

Optional archive:

```bash
cd Linux_for_Tegra
sudo tar czf mfi_recomputer-orin-super-j401.tar.gz \
  mfi_recomputer-orin-super-j401
sudo gzip -t mfi_recomputer-orin-super-j401.tar.gz
sha256sum mfi_recomputer-orin-super-j401.tar.gz \
  > mfi_recomputer-orin-super-j401.tar.gz.sha256
```

`[OK]` when all `test -f` validations pass. `[STOP]` if `QSPI0.img` still exists in `internal/` — QSPI was not regenerated.

---

## Phase 6 — Flash to target device (~10–20 min)

### 6.1 Target device enters APX

```bash
lsusb | grep 0955:7523   # NVIDIA Corp. APX
```

### 6.2 Flash

If the mfi directory is already extracted, do NOT re-extract:

```bash
# Classic:
cd Linux_for_Tegra/mfi_recomputer-orin-j401
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --flash-only --massflash 1 --network usb0 --showlogs

# Super:
cd Linux_for_Tegra/mfi_recomputer-orin-super-j401
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --flash-only --massflash 1 --network usb0 --showlogs
```

If only the `.tar.gz` is available on another machine:

```bash
# Classic:
sudo tar xpf mfi_recomputer-orin-j401.tar.gz
cd mfi_recomputer-orin-j401
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --flash-only --massflash 1 --network usb0 --showlogs

# Super:
sudo tar xpf mfi_recomputer-orin-super-j401.tar.gz
cd mfi_recomputer-orin-super-j401
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --flash-only --massflash 1 --network usb0 --showlogs
```

> If `/mnt/external/...: Permission denied` appears during recovery or APP flash, this is an NFS permission issue — see failure decision tree.

`[OK]` when flashing completes and the target Jetson boots. `[STOP]` if flash fails mid-way.

---

## Phase 7 — Post-flash validation (~2 min)

### Normal log phenomena (harmless)

| Log message | Meaning |
|-------------|---------|
| `p3768-0000-p3767-0000-a0.conf: No such file or directory` | Common under `--flash-only`; image is pre-generated, continue |
| `rpcbind already running` | Ignore |
| `blockdev: cannot open /dev/mmcblk0boot0` | Orin Nano has no such partition, harmless |
| RCM-boot + `SSH ready` | Normal entry into flash mode |
| DTB `...-0005-nv-super.dtb` | SKU0005 correct |
| `internal` multi-line + `Starting to flash to qspi` | Flashing target QSPI |
| `tar ... zstd ... nvme0n1p1_bak.img` | Restoring APP (longest step, may take tens of minutes) |
| `Successfully flash the qspi` | QSPI flash complete |
| `Successfully flash the external device` | External device flash complete |
| `Flashing success` / `Flash is successful` | Flash successful |

> **WARNING:** Do NOT power off or unplug before the success message appears.

### Boot verification

After flashing, release recovery button/jumper, power cycle. If `lsusb` still shows `0955:7523 APX`, the device is still in recovery — not booted yet.

```bash
cat /proc/device-tree/model
ls /boot/kernel_tegra234*.dtb
ls /boot/*.dtbo | grep -E 'hdmi|imx219' || true

# Peripheral functionality (more important than model/dtb filenames)
xrandr 2>/dev/null | head -20
lsusb | head
ip -br link
ls /boot/*.dtbo 2>/dev/null | head -40
sudo dmesg | grep -iE 'dtb|overlay|hdmi|tegra234' | tail -30

# Verify DevKit user environment survived (CUDA example)
nvcc --version
```

### How to interpret results (SKU 0005)

1. **`/proc/device-tree/model` still shows DevKit — NORMAL for SKU 0005**

   Example: `NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super`

   Reason: target conf for SKU 0005 uses NVIDIA's `tegra234-p3768-0000+p3767-0005-nv-super.dtb`, NOT `tegra234-j401-*-recomputer.dtb`. Do NOT judge "flashed wrong DevKit package" based on this line alone.

2. **`/boot` DTB filenames** — reference only

   Actual boot DTB is determined by UEFI/QSPI side, `/boot` listing is just reference.

3. **`grep hdmi|imx219` empty — does NOT mean failure**

   Seeed HDMI/camera config is applied via the target board's newly generated QSPI/UEFI overlay path, not necessarily visible in `/boot/*.dtbo`.

4. **Judge by "does it actually work"**

   | Check | Normal example |
   |-------|---------------|
   | USB | Hub, mouse, Bluetooth, USB NIC enumerated (`lsusb` shows multiple devices) |
   | Ethernet | Classic: `enP8p1s0` UP; Super: see Tech Note C |
   | Wi-Fi | `wlP1p1s0` UP |
   | Display | Desktop usable; or `xrandr` has output |
   | User env | Original DevKit users, software, data present |
   | CUDA | `nvcc --version` works (e.g. 12.6) — confirms APP clone complete |

   - Classic: verify dual camera config (`imx219-dual-seeed`)
   - Super: verify quad camera config (`imx219-quad-seeed`)

### When to modify extlinux.conf

Only if HDMI/USB/boot is abnormal, try adding to `/boot/extlinux/extlinux.conf` under `LABEL primary`:

```text
FDT /boot/kernel_tegra234-p3768-0000+p3767-0005-nv-super.dtb
```

> If `/boot` doesn't have this file, try `...-0005-nv.dtb`, or copy from BSP's `kernel/dtb/` first.

```bash
sudo reboot
```

If still abnormal, proceed to Phase 8 fallback.

`[OK]` when the target device boots with working display, USB, network, and cloned user environment.

---

## Phase 8 — Fallback: official BSP + /home migration

If the Hybrid BSP fails to boot or peripherals are broken, fall back to the official target board BSP and migrate only the user data:

### 8.1 Flash official target board BSP

Download the official reComputer Classic/Super BSP from Seeed wiki and flash it using the standard JetPack flashing flow (not this Hybrid BSP).

### 8.2 Extract /home from DevKit backup

```bash
# On the host, from the Phase 2 backup:
cd Linux_for_Tegra
sudo ./tools/backup_restore/l4t_backup_restore.sh \
  -e nvme0n1 -r -c jetson-orin-nano-devkit-nvme \
  --mount-only
# This mounts the backup APP at /mnt/external/
sudo tar czf ~/devkit_home_backup.tar.gz \
  -C /mnt/external/home .
```

### 8.3 Restore /home on target board

```bash
# On the target board (booted with official BSP, via SSH or terminal):
sudo mkdir -p /home_restore
# Transfer devkit_home_backup.tar.gz to the target board
scp ~/devkit_home_backup.tar.gz <target_user>@<target_ip>:/tmp/

# On the target board:
cd /
sudo tar xpf /tmp/devkit_home_backup.tar.gz
sudo chown -R <target_user>:<target_user> /home/<target_user>
```

> This preserves the DevKit's user data, installed packages (in /home), and configurations, but uses the official target board's QSPI/kernel/dtb — ensuring hardware compatibility.

`[OK]` when the target board boots with official BSP and user data is restored.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `lsusb` does not show `0955:7523 APX` | Re-enter recovery mode. Re-seat USB-C cable. Try different port. |
| `apply_binaries.sh` fails | Verify the tar.gz matches your JetPack version. Re-download if corrupted. |
| `nvbuild.sh` compilation error | Confirm `CROSS_COMPILE` and `PATH` are correct. Check all build deps installed. |
| Backup used wrong board-name | Restart Phase 2 with `jetson-orin-nano-devkit-nvme`. Do NOT use target board-name for first backup. |
| `QSPI0.img` still in `internal/` after Phase 4 | QSPI was not regenerated. Ensure you did NOT use `--use-backup-image` in Phase 4. |
| Logs show DevKit pinmux (DP) instead of HDMI | Target conf was not applied. Check `BOARDID`/`BOARDSKU`/`FAB`/`BOARDREV` match the backup. |
| Super: boot hangs at `Busy Spin` | You used `internal` as rootdev. Re-run Phase 4 with `external` as rootdev. |
| GPT larger than device storage | Do not copy DevKit's entire `external/`. Use standard external layout, only replace APP content. |
| `/mnt/external/...: Permission denied` | NFS permission issue. See Tech Note B below. |
| Flash fails mid-way | Ensure USB cable ≤1.5m and stable. Retry. Device must stay in APX throughout. |
| `blockdev: cannot open /dev/mmcblk0boot0` | Normal on Orin Nano — no action needed. |
| Insufficient disk space | Free space or use larger drive. Need ≥100GB (backup + dual mfi + snapshots). |
| Super: `lan743x` kernel Oops | Pre-place blacklist in APP. See Tech Note A item 3. |
| Super: wired Ethernet not working | Expected — `lan743x` is blacklisted by default. See Tech Note C. |

---

## Tech Note A — Super: ensure first boot needs no on-site repair

Before packaging the Super mfi, verify three consistency conditions:

1. **PARTUUID match**: `boot.img`'s `root=PARTUUID=...` must match the APP partition's unique GUID in the external GPT.
2. **ESP UUID match**: DevKit APP's `/etc/fstab` `/boot/efi` UUID must match the new `esp.img`'s FAT UUID.
3. **lan743x blacklist**: If the cloned DevKit kernel triggers `lan743x` Oops on Super's LAN7430, pre-place in APP:

```bash
# Inside the APP/rootfs, create:
sudo mkdir -p <app_root>/etc/modprobe.d
sudo tee <app_root>/etc/modprobe.d/blacklist-lan743x-super-hybrid.conf >/dev/null <<'EOF'
blacklist lan743x
install lan743x /bin/false
EOF
```

> If conditions 1 or 2 are not met, the device will fail to mount root or enter maintenance mode. Do NOT use `sgdisk` to change PARTUUID in initrd as a permanent fix — regenerate GPT and `boot.img` as a pair, and pre-fix the APP in the archive.

## Tech Note B — NFS Permission denied

If `/mnt/external/...: Permission denied` appears during recovery or APP flash, check that every parent directory in the mfi path allows NFS client traversal.

For example, if the user home directory is `750`, temporarily change to `751` during flashing, then restore:

```bash
sudo chmod 751 /home/$USER
# Re-enter APX and flash
sudo chmod 750 /home/$USER
```

> `751` only adds directory traversal permission, does not allow listing. Never use `777`.

## Tech Note C — Super lan743x wired Ethernet limitation

The cloned DevKit RT kernel triggers `lan743x` Oops on Super's LAN7430. The Hybrid BSP disables `lan743x` by default (see Tech Note A item 3), so onboard wired Ethernet is temporarily unavailable. Wi-Fi is unaffected.

This is a source APP/kernel driver compatibility limitation, not a Super QSPI or pinmux failure. Before production use of wired Ethernet, port/upgrade the compatible driver and complete stress testing.

---

## Reference files

- `references/source.md` — full original Seeed wiki content with screenshots and download links
