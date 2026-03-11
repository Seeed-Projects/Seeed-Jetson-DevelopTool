---
name: bsp-source-build
description: Build Seeed's custom BSP source code for Jetson devices — obtain NVIDIA L4T, overlay Seeed patches, compile kernel, and flash. Requires Ubuntu 20.04/22.04 host PC.
---

# Build Seeed Jetson BSP from Source

Obtain the BSP source code for Seeed's Jetson products, overlay Seeed's
customizations from GitHub, compile the kernel, and flash onto the device.

Hardware: Seeed Jetson device (reComputer/reServer), USB cable for flashing
Software: Ubuntu 20.04 or 22.04 host PC (native)

Source: https://github.com/Seeed-Studio/Linux_for_Tegra

---

## Execution model

Run one phase at a time. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed

Replace `<L4T_VERSION>` with the target version (e.g. `36.4.3`) throughout.

---

## Phase 1 — install build dependencies (~2 min)

```bash
sudo apt-get update
sudo apt-get install -y build-essential flex bison libssl-dev \
  sshpass abootimg nfs-kernel-server libxml2-utils qemu-user-static git-lfs
```

`[OK]` when all packages install without errors.

---

## Phase 2 — download & extract NVIDIA BSP + rootfs (~10 min)

Download from https://developer.nvidia.com/embedded/linux-tegra-archive:
- L4T Driver Package (BSP): `Jetson_Linux_r<L4T_VERSION>_aarch64.tbz2`
- Sample Root Filesystem: `Tegra_Linux_Sample-Root-Filesystem_r<L4T_VERSION>_aarch64.tbz2`

```bash
tar xf Jetson_Linux_r<L4T_VERSION>_aarch64.tbz2
sudo tar xpf Tegra_Linux_Sample-Root-Filesystem_r<L4T_VERSION>_aarch64.tbz2 \
  -C Linux_for_Tegra/rootfs/
```

`[OK]` when `Linux_for_Tegra/rootfs/` is populated.

---

## Phase 3 — sync NVIDIA source & overlay Seeed patches (~15 min)

```bash
cd Linux_for_Tegra/source/
./source_sync.sh -t jetson_<L4T_VERSION>
cd ../..
```

Clone Seeed's BSP overlay:
```bash
mkdir -p github/Linux_for_Tegra
git clone https://github.com/Seeed-Studio/Linux_for_Tegra.git \
  -b r<L4T_VERSION> --depth=1 github/Linux_for_Tegra
```

Overlay Seeed files:
```bash
cp -r github/Linux_for_Tegra/* Linux_for_Tegra/
```

Apply binaries:
```bash
cd Linux_for_Tegra
sudo ./apply_binaries.sh
```

`[OK]` when `apply_binaries.sh` completes.

---

## Phase 4 — setup cross-compilation toolchain (~2 min)

Download the toolchain `aarch64--glibc--stable-2022.08-1.tar.bz2` and extract:

```bash
mkdir -p l4t-gcc
tar xf aarch64--glibc--stable-2022.08-1.tar.bz2 -C ./l4t-gcc
export ARCH=arm64
export CROSS_COMPILE=$(pwd)/l4t-gcc/aarch64--glibc--stable-2022.08-1/bin/aarch64-buildroot-linux-gnu-
```

`[OK]` when `$CROSS_COMPILE` points to a valid binary.

---

## Phase 5 — build kernel (~10–30 min)

```bash
cd Linux_for_Tegra/source
./nvbuild.sh
```

`[OK]` when build completes without errors.

---

## Phase 6 — install kernel & modules (~2 min)

```bash
./do_copy.sh
export INSTALL_MOD_PATH=$(pwd)/../rootfs/
./nvbuild.sh -i
```

`[OK]` when modules are installed to rootfs.

---

## Phase 7 — flash device (~15–30 min)

Put the Jetson device into recovery mode:
1. Power off
2. Hold REC button, connect USB to host
3. Release REC after 2 seconds

Verify:
```bash
lsusb | grep -i nvidia
```

Flash (JetPack 6 example):
```bash
cd ..
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --external-device nvme0n1p1 \
  -c tools/kernel_flash/flash_l4t_t234_nvme.xml \
  -p "-c bootloader/generic/cfg/flash_t234_qspi.xml" \
  --showlogs --network usb0 <DEVICE_NAME> internal
```

Replace `<DEVICE_NAME>` with your board's config name. Available names for L4T 36.4.3:
- `recomputer-orin-j401`
- `recomputer-industrial-orin-j201` (also for j40/j30 series)
- `reserver-agx-orin-j501x`
- `reserver-agx-orin-j501x-gmsl`
- `reserver-industrial-orin-j401`
- `recomputer-orin-j40mini`
- `recomputer-orin-robotics-j401`
- `recomputer-orin-super-j401`

For JetPack 5, change the `-p` parameter to:
`-p "-c bootloader/t186ref/cfg/flash_t234_qspi.xml"`

`[OK]` when flash completes and device boots.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `source_sync.sh` fails | Check internet. Verify tag `jetson_<L4T_VERSION>` exists. |
| Seeed GitHub branch not found | Check available branches at https://github.com/Seeed-Studio/Linux_for_Tegra |
| `apply_binaries.sh` fails | Verify rootfs was extracted correctly. Re-extract and retry. |
| `nvbuild.sh` compile error | Check `CROSS_COMPILE` path. Ensure all build deps are installed. |
| `lsusb` doesn't show NVIDIA device | Re-enter recovery mode. Try a different USB cable/port. |
| Flash fails with device name error | Check `.conf` files in `Linux_for_Tegra/` root for valid device names. |
| Flash fails mid-way | Retry. Ensure USB cable is ≤1.5m and stable. |

---

## Reference files

- `references/source.body.md` — Original Seeed wiki with version-specific details and screenshots
