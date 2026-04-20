---
name: jetpack-ota-update
description: Perform an image-based OTA update on Seeed Jetson devices to upgrade from JetPack 5.1.3 to JetPack 6.0. Requires Ubuntu 20.04 host PC and USB-C cable. Demonstrated on reComputer J3010.
---

# JetPack Image-Based OTA Update (5.1.3 → 6.0)

Upgrade Jetson Linux from JetPack 5.1.3 to JetPack 6.0 using NVIDIA's
image-based over-the-air update mechanism. Demonstrated on reComputer J3010.

Hardware: reComputer J4012/J4011/J3010/J3011, USB-C cable
Software: Ubuntu 20.04 host PC, internet connection

---

## Execution model

Run one phase at a time. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed

Board-specific variables must be set based on the Jetson module:

| Module | BOARDID | BOARDSKU | FAB | BOARDREV | CHIP_SKU |
|--------|---------|----------|-----|----------|----------|
| Orin Nano 4G | 3767 | 0004 | 300 | N.2 | 00:00:00:D6 |
| Orin Nano 8G | 3767 | 0003 | 300 | N.2 | 00:00:00:D6 |
| Orin NX 8G | 3767 | 0001 | 300 | M.3 | 00:00:00:D4 |
| Orin NX 16G | 3767 | 0000 | 300 | G.3 | 00:00:00:D3 |

---

## Phase 1 — download JP5.1.3 BSP (~10 min)

```bash
mkdir -p jp5 && cd jp5
wget https://developer.nvidia.com/downloads/embedded/l4t/r35_release_v5.0/release/jetson_linux_r35.5.0_aarch64.tbz2
wget https://developer.nvidia.com/downloads/embedded/l4t/r35_release_v5.0/release/tegra_linux_sample-root-filesystem_r35.5.0_aarch64.tbz2
```

`[OK]` when both files download successfully.

---

## Phase 2 — build JP5.1.3 system image (~15 min)

```bash
tar xf jetson_linux_r35.5.0_aarch64.tbz2
sudo tar xpf tegra_linux_sample-root-filesystem_r35.5.0_aarch64.tbz2 -C Linux_for_Tegra/rootfs/
cd Linux_for_Tegra
sudo ./apply_binaries.sh
```

Generate the system image (replace variables per the table above):
```bash
sudo BOARDID=<BOARDID> BOARDSKU=<BOARDSKU> FAB=<FAB> BOARDREV=<BOARDREV> CHIP_SKU=<CHIP_SKU> \
  ./tools/kernel_flash/l4t_initrd_flash.sh \
  --external-device nvme0n1p1 \
  -c tools/kernel_flash/flash_l4t_nvme.xml \
  -p "-c bootloader/t186ref/cfg/flash_t234_qspi.xml --no-systemimg" \
  --no-flash --massflash 5 --network usb0 \
  jetson-orin-nano-devkit external
```

`[OK]` when `mfi_jetson-orin-nano-devkit.tar.gz` is generated in `Linux_for_Tegra/`.

---

## Phase 3 — (optional) flash JP5.1.3 to device

If the device doesn't already have JP5.1.3:

```bash
sudo tar xpf mfi_jetson-orin-nano-devkit.tar.gz
cd mfi_jetson-orin-nano-devkit
sudo ./tools/kernel_flash/l4t_initrd_flash.sh --flash-only --massflash 1 --network usb0 --showlogs
```

`[OK]` when device boots JP5.1.3.

---

## Phase 4 — download JP6.0 BSP + OTA tools (~10 min)

```bash
cd <root_dir>
mkdir -p jp6 && cd jp6
wget https://developer.nvidia.com/downloads/embedded/l4t/r36_release_v3.0/release/jetson_linux_r36.3.0_aarch64.tbz2
wget https://developer.nvidia.com/downloads/embedded/l4t/r36_release_v3.0/release/tegra_linux_sample-root-filesystem_r36.3.0_aarch64.tbz2
wget https://developer.nvidia.com/downloads/embedded/l4t/r36_release_v3.0/release/ota_tools_R36.3.0_aarch64.tbz2
```

`[OK]` when all three files download successfully.

---

## Phase 5 — build JP6.0 system image (~15 min)

```bash
tar xf jetson_linux_r36.3.0_aarch64.tbz2
sudo tar xpf tegra_linux_sample-root-filesystem_r36.3.0_aarch64.tbz2 -C Linux_for_Tegra/rootfs
cd Linux_for_Tegra
sudo ./apply_binaries.sh
sudo BOARDID=<BOARDID> BOARDSKU=<BOARDSKU> FAB=<FAB> BOARDREV=<BOARDREV> CHIP_SKU=<CHIP_SKU> \
  ./tools/kernel_flash/l4t_initrd_flash.sh \
  --external-device nvme0n1p1 \
  -c tools/kernel_flash/flash_l4t_nvme.xml \
  -p "-c bootloader/generic/cfg/flash_t234_qspi.xml --no-systemimg" \
  --no-flash --massflash 5 --network usb0 \
  jetson-orin-nano-devkit external
```

`[OK]` when image generation completes.

---

## Phase 6 — generate OTA payload package (~10 min)

```bash
cd <root_dir>/jp6
tar xf ota_tools_R36.3.0_aarch64.tbz2
cd Linux_for_Tegra
sudo BASE_BSP=<root_dir>/jp5/Linux_for_Tegra \
  ./tools/ota_tools/version_upgrade/l4t_generate_ota_package.sh \
  --external-device nvme0n1 -S 80GiB jetson-orin-nano-devkit R35-5
```

`[OK]` when `ota_payload_package.tar.gz` appears in
`Linux_for_Tegra/bootloader/jetson-orin-nano-devkit/`.

---

## Phase 7 — apply OTA on device (~15 min)

Copy the OTA package to the Jetson device and run on the device:

```bash
scp <host_path>/jp6/Linux_for_Tegra/bootloader/jetson-orin-nano-devkit/ota_payload_package.tar.gz <user>@<jetson_ip>:~
```

On the Jetson device:
```bash
wget https://developer.nvidia.com/downloads/embedded/l4t/r36_release_v3.0/release/ota_tools_R36.3.0_aarch64.tbz2
sudo mkdir -p /ota
sudo mv ~/ota_payload_package.tar.gz /ota
tar xf ota_tools_R36.3.0_aarch64.tbz2
cd ~/Linux_for_Tegra/tools/ota_tools/version_upgrade
sudo ./nv_ota_start.sh /ota/ota_payload_package.tar.gz
```

After completion, reboot the device:
```bash
sudo reboot
```

`[OK]` when device boots into JetPack 6.0.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| BSP download fails | Check internet. Verify URLs are still valid at NVIDIA's download page. |
| `apply_binaries.sh` fails | Ensure rootfs was extracted with `sudo tar xpf`. Re-extract and retry. |
| Image generation fails | Verify BOARDID/BOARDSKU/FAB/BOARDREV/CHIP_SKU match your module. |
| OTA package generation fails | Ensure `BASE_BSP` path points to the JP5.1.3 `Linux_for_Tegra` directory. |
| `nv_ota_start.sh` fails on device | Check disk space (`df -h`). Ensure OTA package is in `/ota/`. |
| Device won't boot after OTA | Re-flash JP6.0 directly using standard flash method as fallback. |

---

## Reference files

- `references/source.body.md` — Original Seeed wiki with board-specific variable tables and screenshots
