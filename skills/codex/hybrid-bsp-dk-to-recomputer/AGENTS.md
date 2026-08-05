---
name: hybrid-bsp-dk-to-recomputer
description: Hybrid BSP: Orin Nano DevKit to reComputer Classic/Super. Clones APP, regenerates QSPI with correct pinmux. JetPack 6.2.
---

# Hybrid BSP: Orin Nano DevKit → reComputer Classic/Super

Clone a complete DevKit development environment, swap in the target board's
QSPI firmware (pinmux + camera overlay), and flash the hybrid bundle onto
a reComputer Classic or Super.

```text
[Host] Extract L4T + apply_binaries + nvbuild
          │
          ▼
[DevKit APX] backup -c jetson-orin-nano-devkit-nvme
          │
          ├─► (optional) --use-backup-image → mfi_jetson-orin-nano-devkit-nvme
          │
          ├─► snapshot backup_images_dk_sku0005
          │         │
          │         ├─ APP-only (remove QSPI)
          │         └─► external APP
          │
          └─► [APX] target board conf → generate QSPI
                    │           │
                    │           ├─ Classic: recomputer-orin-j401 internal
                    │           └─ Super:   recomputer-orin-super-j401-nvme external
                    │
                    ▼
              assemble mfi_recomputer-orin-<target>
                    │
                    ▼
              [target APX] --flash-only
                    │
                    ▼
              check display/USB/NVMe/user environment
```

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
   > If SKU is not 0005: change `BOARDSKU`, pick the matching DTB per `p3767_super_overlay` in the target board conf, then regenerate QSPI. Do NOT reuse pre-built QSPI downloads.
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

> **NOTE:** The [DIY BSP wiki](https://wiki.seeedstudio.com/make_diy_bsp_for_jetson/) uses `recomputer-orin-j401` because it assumes **source and target are both Seeed boards**. When the source is an NVIDIA DevKit, backup must first use `jetson-orin-nano-devkit-nvme`, then follow this Hybrid guide to adapt to the target board.

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
# Adjust the filename to match your downloaded L4T package
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

# Idempotency: skip if snapshot already exists
if [ -f ~/backup_images_dk_sku0005/nvpartitionmap.txt ]; then
  echo "[install] Backup snapshot already exists — skip backup"
  echo "[install] To re-run, remove ~/backup_images_dk_sku0005 first"
else
  sudo ./tools/backup_restore/l4t_backup_restore.sh \
    -e nvme0n1 -b -c jetson-orin-nano-devkit-nvme
fi
```

> **WARNING:** When the source is a DevKit, do NOT use the target board-name for the first backup — `board_spec` and subsequent baselines will be wrong.

### 2.4 Validate backup

```bash
ls -lah tools/backup_restore/images/
head -5 tools/backup_restore/images/nvpartitionmap.txt
```

Expected:
- `board_spec` contains `jetson-orin-nano-devkit-nvme`
  - Example format: `3767-300-0005-V.2-1-1-jetson-orin-nano-devkit-nvme-`
- `nvme0n1p1.tar.zst` (or converted large APP) is GB-scale
- `QSPI0.img` exists (this is the **DevKit** QSPI — cannot be reused for target board)

### 2.5 Snapshot (recommended)

```bash
# Idempotency: skip if snapshot already exists (Phase 2.3 also checks this)
if [ -d ~/backup_images_dk_sku0005 ] && [ -f ~/backup_images_dk_sku0005/nvpartitionmap.txt ]; then
  echo "[install] Snapshot already exists — skip copy"
else
  sudo cp -a tools/backup_restore/images/. ~/backup_images_dk_sku0005/
fi
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

Key conf contents (for verification):

```bash
# Classic (recomputer-orin-j401.conf):
PINMUX_CONFIG="tegra234-mb1-bct-pinmux-p3767-hdmi-a03.dtsi"
PMC_CONFIG="tegra234-mb1-bct-padvoltage-p3767-hdmi-a03.dtsi"
OVERLAY_DTB_FILE+=",tegra234-dcb-p3767-0000-hdmi.dtbo,tegra234-p3767-camera-p3768-imx219-dual-seeed.dtbo"
DCE_OVERLAY_DTB_FILE="tegra234-dcb-p3767-0000-hdmi.dtbo"

# Super (recomputer-orin-super-j401.conf):
PINMUX_CONFIG="recomputer-super-orin-j401-pinmux-p3767-hdmi-a03.dtsi"
PMC_CONFIG="recomputer-super-orin-j401-padvoltage-p3767-hdmi-a03.dtsi"
OVERLAY_DTB_FILE+=",tegra234-dcb-p3767-0000-hdmi.dtbo,tegra234-p3767-camera-p3768-imx219-quad-seeed.dtbo"
DCE_OVERLAY_DTB_FILE="tegra234-dcb-p3767-0000-hdmi.dtbo"
```

> **WARNING:** For SKU 0005, the main DTB filename is still NVIDIA's `tegra234-p3768-0000+p3767-0005-nv-super.dtb`. Do NOT force-switch to `tegra234-p3768-0000+p3767-0000-recomputer.dtb` — that path is for Orin NX 16GB, not Orin Nano 8GB.

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

After downloading, place the pre-built QSPI into the workspace `internal/` and create the mfi directory skeleton. Note: this manual skeleton only copies `internal/`, `external/` placeholders, and the conf file — it does NOT include bootloader/flash scripts that `l4t_initrd_flash.sh` would normally generate. If Phase 6 flash fails with missing files, re-run Option B instead.

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

> **WARNING:** If Phase 6 `--flash-only` fails with "No such file" or missing bootloader errors, the manual skeleton is incomplete. In that case, run Option B (full `l4t_initrd_flash.sh --no-flash`) which generates the complete mfi structure including flash scripts and bootloader files.

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
sudo rm -rf ~/j401_qspi_internal_save
sudo cp -a tools/kernel_flash/images/internal/. ~/j401_qspi_internal_save/
# Super:
sudo rm -rf ~/super_j401_qspi_internal_save
sudo cp -a tools/kernel_flash/images/internal/. ~/super_j401_qspi_internal_save/
```

`[OK]` when `internal/` contains split QSPI files (not a single DevKit `QSPI0.img`). `[STOP]` if logs show DevKit pinmux instead of target pinmux.

---

## Phase 5 — Assemble Hybrid mfi bundle (~5–10 min)

### 5.1 Prepare APP-only (remove DevKit QSPI)

> **NOTE:** The `images_app_only` directory below is for audit/reference. The `else` branch's `l4t_initrd_flash.sh --use-backup-image` uses the default `tools/backup_restore/images/` path, but the generated `external/` only contains the APP partition (not QSPI), so QSPI0.img in the backup does not contaminate the output.

```bash
cd Linux_for_Tegra
# Idempotency: remove stale images_app_only to prevent stale-file merge
if [ -d tools/backup_restore/images_app_only ]; then
  echo "[install] images_app_only already exists — removing stale copy"
  sudo rm -rf tools/backup_restore/images_app_only
fi
sudo cp -a ~/backup_images_dk_sku0005/. \
  tools/backup_restore/images_app_only/
sudo rm -f tools/backup_restore/images_app_only/QSPI0.img
sudo sed -i '/qspi/Id' tools/backup_restore/images_app_only/nvpartitionmap.txt
```

Convert APP-only to initrd flash `external/` images. The approach depends on whether Phase 3 was run:

```bash
cd Linux_for_Tegra

# If Phase 3 was run, reuse its external/ directly (faster):
if [ -d mfi_jetson-orin-nano-devkit-nvme/tools/kernel_flash/images/external ] && \
   [ -f mfi_jetson-orin-nano-devkit-nvme/tools/kernel_flash/images/external/nvme0n1p1_bak.img ]; then
  echo "[install] Reusing external/ from Phase 3"
  sudo cp -a mfi_jetson-orin-nano-devkit-nvme/tools/kernel_flash/images/external/. \
    tools/kernel_flash/images/external/

# Otherwise, generate external/ from the APP-only backup:
else
  echo "[install] Phase 3 skipped — generating external/ from backup"
  sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
    --use-backup-image --no-flash --network usb0 --massflash 5 \
    jetson-orin-nano-devkit-nvme internal
fi
```

> The `--use-backup-image` flag triggers `convert_backup_image_to_initrd_flash` internally, which converts the backup APP into the `external/` image format. The generated `tools/kernel_flash/images/external/` will contain `nvme0n1p1_bak.img` (GB-scale APP).
>
> **WARNING:** This overwrites `tools/kernel_flash/images/external/` which may contain the target board's standard external layout from Phase 4 Option B. Phase 5.2 checks the mfi directory directly to avoid using the overwritten workspace `external/`.

### 5.2 Assemble the target mfi directory

**For reComputer Classic:**

> **WARNING:** Same GPT size caveat as Super — if the DevKit source disk is larger than the Classic target disk, blindly copying the entire DevKit `external/` will cause "GPT is larger than device storage" at `partprobe`. Use the workspace-generated standard `external/` layout, not the DevKit mfi's.

The mfi directory was created by Phase 4 Option B (or the skeleton from Option A). Now place the external APP:

```bash
cd Linux_for_Tegra
# Check if mfi external/ already has standard layout from Phase 4 Option B:
if [ -f mfi_recomputer-orin-j401/tools/kernel_flash/images/external/flash.xml ] || \
   [ -f mfi_recomputer-orin-j401/tools/kernel_flash/images/external/gpt_*.img ]; then
  echo "[install] mfi external/ already has Classic standard layout from Phase 4 — skip copy"
else
  echo "[install] mfi external/ empty (Phase 4 Option A) — copying from workspace"
  sudo cp -a tools/kernel_flash/images/external/. \
    mfi_recomputer-orin-j401/tools/kernel_flash/images/external/
fi
```

Final directory structure:

| Path | Content |
|------|---------|
| `mfi_recomputer-orin-j401/recomputer-orin-j401.conf` | Exists |
| `.../tools/kernel_flash/images/internal/` | J401 new QSPI (no DevKit single `QSPI0.img`; `flash.idx` is multi-line split) |
| `.../tools/kernel_flash/images/external/nvme0n1p1_bak.img` | GB-scale APP |

Validation:

```bash
test -f mfi_recomputer-orin-j401/recomputer-orin-j401.conf
test -f mfi_recomputer-orin-j401/tools/kernel_flash/images/external/nvme0n1p1_bak.img
test ! -f mfi_recomputer-orin-j401/tools/kernel_flash/images/internal/QSPI0.img
test -f mfi_recomputer-orin-j401/tools/kernel_flash/images/internal/flash.idx
```

Optional archive:

```bash
cd Linux_for_Tegra
sudo tar czf mfi_recomputer-orin-j401.tar.gz mfi_recomputer-orin-j401
```

**For reComputer Super:**

> **DANGER:** Do NOT blindly copy the entire DevKit mfi `external/`. If the DevKit source disk is 256GB but the Super target disk is 128GB, the source GPT will cause "GPT is larger than device storage" at `partprobe`.
>
> **Reference (from Seeed Wiki test build):** Validated target drive was `128035676160` bytes (~128GB). Standard `flash_l4t_t234_nvme.xml` external layout is `102400000000` bytes (~102GB). Only the APP payload was replaced.

> **PRE-PACKAGING CHECK:** Before assembling, verify the three Super consistency conditions in [Tech Note A](#tech-note-a--super-ensure-first-boot-needs-no-on-site-repair) (PARTUUID match, ESP UUID match, lan743x blacklist). Failure to check these will cause first-boot failures that require on-site repair.

Use the standard external layout generated by the Super/current workspace, then only replace the APP content:

```bash
cd Linux_for_Tegra
# Check if mfi external/ already has standard layout from Phase 4 Option B:
if [ -f mfi_recomputer-orin-super-j401/tools/kernel_flash/images/external/flash.xml ] || \
   [ -f mfi_recomputer-orin-super-j401/tools/kernel_flash/images/external/gpt_*.img ]; then
  echo "[install] mfi external/ already has Super standard layout from Phase 4 — skip copy"
else
  echo "[install] mfi external/ empty (Phase 4 Option A) — copying from workspace"
  echo "[install] WARNING: If tools/kernel_flash/images/external/ was overwritten by Phase 5.1,"
  echo "[install]   it contains DevKit GPT — may cause 'GPT larger than device' error"
  sudo cp -a tools/kernel_flash/images/external/. \
    mfi_recomputer-orin-super-j401/tools/kernel_flash/images/external/
fi

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
test -f mfi_recomputer-orin-super-j401/tools/kernel_flash/images/internal/flash.idx
```

All four must pass:
- `internal/` is the newly generated Super QSPI
- `external/` GPT is smaller than the target physical disk
- `APP_ext` points to the DevKit's `nvme0n1p1_bak.img`
- `flash.idx` exists (multi-line QSPI split index)

> Reference values (from Seeed Wiki test build, JetPack 6.2 / L4T 36.4.3):
> - Final Super bundle size: ~12.8 GB (`12,822,619,478` bytes)
> - SHA-256: `fb1d502d9e869d67226eaf71bbe2462fab4e2f1dacf8a6a7fa59057c66a2e845`
> - These are reference-only; your build may differ if source disk size or APP content differs.

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
# NOTE: dmesg requires sudo — without it, you may get "Operation not permitted"

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

   > **NOTE:** Interface names like `enP8p1s0` and `wlP1p1s0` are kernel/PCIe-bus dependent and may vary across board revisions or kernel versions. Use `ip -br link` to list actual names — look for the Ethernet and Wi-Fi interfaces by type, not by exact name.

   - Classic: verify dual camera config (`imx219-dual-seeed`)
   - Super: verify quad camera config (`imx219-quad-seeed`)

> **Super validated results (from Seeed Wiki test build):**
> - System reached Ubuntu login screen with `display-manager` active
> - HDMI, USB keyboard/mouse, Bluetooth, and Wi-Fi all worked
> - Cloned DevKit APP and CUDA 12.6 were retained
> - Quad-camera overlay and four IMX219/I2C configuration nodes were present

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

If the Hybrid BSP fails to boot or peripherals are broken, fall back to the official target board BSP and migrate only the user data.

**Before starting, ask the user for:**
- `TARGET_USER` — target board username (default: `seeed`)
- `TARGET_IP` — target board IP address (e.g. `192.168.7.26`)

### 8.1 Flash official target board BSP

Download the official reComputer Classic/Super BSP from Seeed wiki and flash it using the standard JetPack flashing flow (not this Hybrid BSP).

### 8.2 Extract /home from DevKit backup

> **WARNING:** Do NOT use `l4t_backup_restore.sh -r` — the `-r` (restore) flag will attempt to **flash the backup image to a connected device**, not just mount it. Use manual loop-mount or tar extraction instead.

> **NOTE:** The backup may exist as either `nvme0n1p1*.img` (raw image, if Phase 3/5.1 conversion was run) or `nvme0n1p1*.tar.zst` (compressed tarball, the original backup format). The script below handles both.

```bash
# On the host, from the Phase 2 backup:
cd Linux_for_Tegra
sudo mkdir -p /mnt/external

# Try .img first (from Phase 3/5.1 conversion):
if ls tools/backup_restore/images/nvme0n1p1*.img >/dev/null 2>&1; then
  echo "[install] Found .img — loop-mounting"
  sudo mount -o loop,ro tools/backup_restore/images/nvme0n1p1*.img /mnt/external/
  ls /mnt/external/home/
  sudo tar czf ~/devkit_home_backup.tar.gz -C /mnt/external/home .
  sudo umount /mnt/external

# Fallback: extract /home directly from .tar.zst (original backup format):
elif ls tools/backup_restore/images/nvme0n1p1*.tar.zst >/dev/null 2>&1; then
  echo "[install] Found .tar.zst — extracting /home directly"
  sudo tar --zstd -xf tools/backup_restore/images/nvme0n1p1*.tar.zst \
    -C /mnt/external/ home/
  sudo tar czf ~/devkit_home_backup.tar.gz -C /mnt/external/home .

# Also check snapshot directory:
elif ls ~/backup_images_dk_sku0005/nvme0n1p1*.img >/dev/null 2>&1; then
  echo "[install] Found .img in snapshot — loop-mounting"
  sudo mount -o loop,ro ~/backup_images_dk_sku0005/nvme0n1p1*.img /mnt/external/
  ls /mnt/external/home/
  sudo tar czf ~/devkit_home_backup.tar.gz -C /mnt/external/home .
  sudo umount /mnt/external

elif ls ~/backup_images_dk_sku0005/nvme0n1p1*.tar.zst >/dev/null 2>&1; then
  echo "[install] Found .tar.zst in snapshot — extracting /home directly"
  sudo tar --zstd -xf ~/backup_images_dk_sku0005/nvme0n1p1*.tar.zst \
    -C /mnt/external/ home/
  sudo tar czf ~/devkit_home_backup.tar.gz -C /mnt/external/home .

else
  echo "[STOP] No backup APP found. Check tools/backup_restore/images/ and ~/backup_images_dk_sku0005/"
  exit 1
fi

# Cleanup:
sudo rm -rf /mnt/external
```

### 8.3 Restore /home on target board

```bash
# Transfer the archive to the target board:
scp ~/devkit_home_backup.tar.gz ${TARGET_USER}@${TARGET_IP}:/tmp/

# Run restore commands remotely via SSH (do NOT ssh then run locally):
ssh ${TARGET_USER}@${TARGET_IP} << EOF
cd /
sudo tar xpf /tmp/devkit_home_backup.tar.gz
sudo chown -R ${TARGET_USER}:${TARGET_USER} /home/${TARGET_USER}
EOF
```

> This preserves the DevKit's user data, installed packages (in /home), and configurations, but uses the official target board's QSPI/kernel/dtb — ensuring hardware compatibility. System-level software outside `/home` (e.g. `/usr`, `/etc`, Docker, systemd services) needs separate reinstallation on the target board.
>
> **Pros:** cleanest board firmware. **Cons:** not a full `/` disk clone.

`[OK]` when the target board boots with official BSP and user data is restored.

---

## Key Paths Quick Reference

| Path | Content | Phase |
|------|---------|-------|
| `~/backup_images_dk_sku0005/` | DevKit backup snapshot (APP + QSPI) | 2.5 |
| `tools/backup_restore/images/` | Active backup working directory | 2.3 |
| `tools/backup_restore/images_app_only/` | APP-only backup (QSPI removed) | 5.1 |
| `tools/kernel_flash/images/internal/` | Target board QSPI shards | 4 |
| `tools/kernel_flash/images/external/` | DevKit APP (converted) — may be overwritten by 5.1 | 3/5.1 |
| `mfi_jetson-orin-nano-devkit-nvme/` | DevKit same-board mfi (optional) | 3 |
| `mfi_recomputer-orin-j401/` | Classic hybrid mfi (target QSPI + DevKit APP) | 5.2 |
| `mfi_recomputer-orin-super-j401/` | Super hybrid mfi (target QSPI + DevKit APP) | 5.2 |
| `mfi_recomputer-orin-*.tar.gz` | Final flashable archive | 6 |

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `lsusb` does not show `0955:7523 APX` | Re-enter recovery mode. Re-seat USB-C cable. Try different port. |
| `apply_binaries.sh` fails | Verify the tar.gz matches your JetPack version. Re-download if corrupted. |
| `nvbuild.sh` compilation error | Confirm `CROSS_COMPILE` and `PATH` are correct. Check all build deps installed. |
| Backup used wrong board-name | Restart Phase 2 with `jetson-orin-nano-devkit-nvme`. Do NOT use target board-name for first backup. |
| `QSPI0.img` still in `internal/` after Phase 4 | QSPI was not regenerated. Ensure you did NOT use `--use-backup-image` in Phase 4. |
| `[STOP] No APP image found` (Phase 5.1) | Run Phase 5.1 conversion or Phase 3 first. The `external/nvme0n1p1_bak.img` must exist before assembly. |
| Phase 6 `--flash-only` fails with missing files | Manual skeleton (Option A) is incomplete. Re-run Option B (`l4t_initrd_flash.sh --no-flash`) to generate complete mfi structure. |
| Logs show DevKit pinmux (DP) instead of HDMI | Target conf was not applied. Check `BOARDID`/`BOARDSKU`/`FAB`/`BOARDREV` match the backup. |
| Super: boot hangs at `Busy Spin` | You used `internal` as rootdev. Re-run Phase 4 with `external` as rootdev. |
| GPT larger than device storage | Do not copy DevKit's entire `external/`. Use standard external layout from mfi directory (Phase 4 Option B), only replace APP content. If Option A was used, run Option B to generate standard external first. |
| `/mnt/external/...: Permission denied` | NFS permission issue. See Tech Note B below. |
| `[STOP] No backup APP found` (Phase 8) | Check both `tools/backup_restore/images/` and `~/backup_images_dk_sku0005/` for `nvme0n1p1*.img` or `nvme0n1p1*.tar.zst` |
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
# Mount the backup APP and create the blacklist inside it
# APP_ROOT is the mount point of the backup APP (e.g. /mnt/external)
sudo mkdir -p /mnt/external/etc/modprobe.d
sudo tee /mnt/external/etc/modprobe.d/blacklist-lan743x-super-hybrid.conf >/dev/null <<'EOF'
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

- `references/source.body.md` — full original Seeed wiki content with screenshots and download links
