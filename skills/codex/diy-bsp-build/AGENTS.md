---
name: diy-bsp-build
description: Create a custom flashable BSP (Board Support Package) by cloning a complete Jetson development environment. Covers working directory setup, environment cloning via l4t_backup_restore, BSP packaging, and flashing to target devices. Requires Ubuntu 22.04 host PC and USB-C cable.
---

# Creating a Custom BSP Package from Jetson Development Environment

---

## Execution model

Run one phase at a time. After each phase:
- Relay all command output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree below.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Source Jetson | Device with configured development environment |
| Host PC | Ubuntu 22.04 |
| Cable | USB Type-C data transmission cable |
| JetPack | 6.0 / 6.2 / 6.2.1 (guide uses 6.2 as example) |
| Disk space | Approximately 2× the storage used by the Jetson dev environment |

> The reComputer Classic series has insufficient cooling for MAXN super mode. Do not enable MAXN mode on reComputer Classic with JetPack 6.2.

---

## Phase 1 — Install host dependencies and prepare working directory (~10 min)

Download the working directory package for your JetPack version from the Seeed wiki, then install build dependencies on the host PC.

```bash
sudo apt-get update -y
sudo apt-get install -y \
  build-essential flex bison libssl-dev \
  sshpass abootimg nfs-kernel-server \
  libxml2-utils qemu-user-static
```

Extract the downloaded package and generate content:

```bash
sudo tar xpf xxx.tar.gz
# Example: sudo tar xpf L4T36-4-3_plus.tar

cd Linux_for_Tegra/
sudo ./apply_binaries.sh
cd ..
```

`[OK]` when `apply_binaries.sh` completes without errors. `[STOP]` if extraction or apply_binaries fails.

---

## Phase 2 — Set environment variables and compile source (~20–60 min)

Set up cross-compilation environment variables in the extracted directory:

```bash
export ARCH=arm64
export CROSS_COMPILE="$PWD/aarch64--glibc--stable-2022.08-1/bin/aarch64-buildroot-linux-gnu-"
export PATH="$PWD/aarch64--glibc--stable-2022.08-1/bin:$PATH"
export INSTALL_MOD_PATH="$PWD/Linux_for_Tegra/rootfs/"
```

Compile the source code:

```bash
cd Linux_for_Tegra/source
./nvbuild.sh
```

After compilation, copy and install:

```bash
./do_copy.sh
./nvbuild.sh -i
```

`[OK]` when `nvbuild.sh -i` completes. `[STOP]` if compilation errors occur.

---

## Phase 3 — Clone development environment from Jetson (~15–30 min)

Connect the source Jetson to the host PC via USB-C through the flashing port. Put the Jetson into Recovery mode (see https://wiki.seeedstudio.com/flash/jetpack_to_selected_product/).

Navigate to `Linux_for_Tegra/` and clone:

```bash
sudo ./tools/backup_restore/l4t_backup_restore.sh -e nvme0n1 -b -c <board-name>

# Example:
# sudo ./tools/backup_restore/l4t_backup_restore.sh -e nvme0n1 -b -c recomputer-orin-j401
```

Replace `<board-name>` with your device name. Valid names for L4T 36.4.3 include:
- `recomputer-industrial-orin-j201`
- `recomputer-orin-j401`
- `reserver-agx-orin-j501x`
- `recomputer-orin-j40mini`
- `recomputer-orin-robotics-j401`
- `recomputer-orin-super-j401`

Check `.conf` filenames in `Linux_for_Tegra/` root to find valid device names.

`[OK]` when backup completes. `[STOP]` if device not detected — check Recovery mode and USB cable.

---

## Phase 4 — Package BSP (~15–30 min)

The backup device must remain in Recovery mode. Package the cloned content:

```bash
sudo ./tools/kernel_flash/l4t_initrd_flash.sh --use-backup-image --no-flash --network usb0 --massflash 5 <board-name> internal

# Example:
# sudo ./tools/kernel_flash/l4t_initrd_flash.sh --use-backup-image --no-flash --network usb0 --massflash 5 recomputer-orin-j401 internal
```

Expected: files with `mfi_` prefix and a `mfi_xxxxx.tar.gz` package generated in `Linux_for_Tegra/`.

(Optional) For QSPI flash format BSP suitable for factory production:

```bash
sudo BOARDID=$BOARDID BOARDSKU=$BOARDSKU FAB=$FAB BOARDREV=$BOARDREV CHIP_SKU=$CHIP_SKU ./tools/kernel_flash/l4t_initrd_flash.sh \
--external-device nvme0n1p1 -c tools/kernel_flash/flash_l4t_t234_nvme.xml \
-p "-c bootloader/generic/cfg/flash_t234_qspi.xml --no-systemimg" --no-flash --massflash 5 --showlogs \
--network usb0 <board-name> internal
```

`[OK]` when `mfi_xxxxx.tar.gz` is generated. `[STOP]` if packaging fails.

---

## Phase 5 — Flash target device (~10–20 min)

Extract and flash the BSP to a new target Jetson (must be in Recovery mode):

```bash
sudo tar xpf mfi_xxxx.tar.gz
cd mfi_xxxx
sudo ./tools/kernel_flash/l4t_initrd_flash.sh --flash-only --massflash 1 --network usb0 --showlogs
```

`[OK]` when flashing completes and the target Jetson boots with the cloned environment.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `apply_binaries.sh` fails | Verify the tar.gz matches your JetPack version. Re-download if corrupted. |
| `nvbuild.sh` compilation error | Confirm cross-compiler path is correct. Check `CROSS_COMPILE` and `PATH` exports. |
| Device not detected in Recovery mode | Re-seat USB-C cable. Verify correct flashing port. Re-enter Recovery mode. |
| `l4t_backup_restore.sh` fails | Ensure sufficient disk space (2× Jetson storage). Confirm `<board-name>` matches a valid `.conf` file. |
| BSP packaging hangs or fails | Device must stay in Recovery mode throughout. Check USB connection stability. |
| Flash fails on target device | Confirm target is in Recovery mode. Verify `mfi_` package was extracted with `sudo tar xpf`. |
| Insufficient disk space | Free space or use a larger drive. BSP requires ~2× the source Jetson's used storage. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with download links, device name tables, and screenshots (reference only)
