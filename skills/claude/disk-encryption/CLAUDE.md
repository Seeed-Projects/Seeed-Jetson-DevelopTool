---
name: disk-encryption
description: Encrypt the root filesystem on Jetson devices during flashing using OPTEE-based encryption keys. Covers BSP source build, OPTEE key generation, encrypted image creation, and flashing with l4t_initrd_flash. Requires an Ubuntu 20.04/22.04 host PC and the target Jetson device (e.g. reComputer J401 with L4T 36.4.3).
---

# Disk Encryption for Jetson

Encrypts the Jetson root filesystem during the flashing process using OPTEE-generated keys. This is a destructive operation — the device must be re-flashed.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all output to the user.
- If output contains `[STOP]` → stop, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed.

**WARNING:** This process re-flashes the entire device. All existing data on the Jetson will be erased.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Host PC | Ubuntu 20.04 or 22.04 (x86_64) |
| Jetson device | e.g. reComputer J401 (Orin) in recovery mode |
| L4T version | 36.4.3 (adjust commands for other versions) |
| USB cable | Connecting host to Jetson recovery port |
| Storage | ~50GB free on host for BSP and build artifacts |

---

## Phase 1 — Prepare BSP workspace on host PC (~15 min)

Download and extract NVIDIA L4T BSP and root filesystem:

```bash
tar xf Jetson_Linux_r36.4.3_aarch64.tbz2
sudo tar xpf Tegra_Linux_Sample-Root-Filesystem_r36.4.3_aarch64.tbz2 -C Linux_for_Tegra/rootfs/
```

Sync kernel source:

```bash
cd Linux_for_Tegra/source/
./source_sync.sh -t jetson_36.4.3
cd ../..
```

Clone Seeed BSP overlay and apply:

```bash
sudo apt update && sudo apt install -y git-lfs
mkdir -p github/Linux_for_Tegra
git clone https://github.com/Seeed-Studio/Linux_for_Tegra.git -b r36.4.3 --depth=1 github/Linux_for_Tegra
cp -r github/Linux_for_Tegra/* Linux_for_Tegra/
cd Linux_for_Tegra
sudo ./apply_binaries.sh
```

`[OK]` when `apply_binaries.sh` completes. `[STOP]` if download or extraction fails.

---

## Phase 2 — Install build dependencies and compile kernel (~20–30 min)

```bash
sudo apt-get install -y build-essential flex bison libssl-dev sshpass \
    abootimg nfs-kernel-server libxml2-utils qemu-user-static
```

Set up cross-compiler (download the toolchain first):

```bash
mkdir -p l4t-gcc
tar xf aarch64--glibc--stable-2022.08-1.tar.bz2 -C ./l4t-gcc
export ARCH=arm64
export CROSS_COMPILE=$(pwd)/l4t-gcc/aarch64--glibc--stable-2022.08-1/bin/aarch64-buildroot-linux-gnu-
```

Build kernel and install:

```bash
cd source
./nvbuild.sh
./do_copy.sh
export INSTALL_MOD_PATH=$(pwd)/../rootfs/
./nvbuild.sh -i
cd ..
```

`[OK]` when kernel build and module install complete. `[STOP]` if compilation fails.

---

## Phase 3 — Generate OPTEE encryption keys (~3 min)

```bash
cd Linux_for_Tegra
sudo apt-get install -y python3-cryptography python3-cffi-backend libxml2-utils \
    python3-pycryptodome python3-crypto cryptsetup
pip install cryptography pycrypto
pip install --user --upgrade pycryptodome
```

Generate keys:

```bash
cd source/tegra/optee-src/nv-optee/optee/samples/hwkey-agent/host/tool/gen_ekb

openssl rand -hex 32 > sym_t234.key
openssl rand -hex 16 > sym2_t234.key
openssl rand -hex 16 > auth_t234.key
openssl rand -hex 32 > oem_k1.key

./example.sh
```

Copy generated files to BSP directories:

```bash
cp eks_t234.img /path/to/Linux_for_Tegra/bootloader/
sudo cp sym2_t234.key /path/to/Linux_for_Tegra/
```

`[OK]` when `eks_t234.img` and `sym2_t234.key` are generated and copied. `[STOP]` if key generation fails.

---

## Phase 4 — Generate encrypted flash image (~10–20 min)

Replace `recomputer-orin-j401` with your device name (check `.conf` files in `Linux_for_Tegra/`):

```bash
cd /path/to/Linux_for_Tegra

sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --network usb0 \
  --no-flash \
  --showlogs \
  -p "-c bootloader/generic/cfg/flash_t234_qspi.xml" \
  recomputer-orin-j401 \
  internal
```

Copy the encrypted header:

```bash
sudo cp bootloader/eks_t234_sigheader.img.encrypt ./tools/kernel_flash/images/internal/
```

Available device names for L4T 36.4.3:
- `recomputer-orin-j401`
- `recomputer-industrial-orin-j201` (also for j40/j30 series)
- `reserver-agx-orin-j501x`
- `recomputer-orin-j40mini`
- `recomputer-orin-robotics-j401`
- `recomputer-orin-super-j401`

`[OK]` when image generation completes. `[STOP]` if flash tool errors.

---

## Phase 5 — Flash encrypted filesystem to Jetson (~15–30 min)

Put the Jetson device into recovery mode, then:

```bash
sudo ROOTFS_ENC=1 \
./tools/kernel_flash/l4t_initrd_flash.sh \
  --external-device nvme0n1p1 \
  -i ./sym2_t234.key \
  -c tools/kernel_flash/flash_l4t_t234_nvme_rootfs_enc.xml \
  -S 80GiB \
  -p "-c bootloader/generic/cfg/flash_t234_qspi.xml" \
  --showlogs \
  --network usb0 \
  recomputer-orin-j401 internal
```

`[OK]` when flashing completes successfully. `[STOP]` if USB connection drops or flash fails.

---

## Phase 6 — Retrieve decryption password (~2 min)

```bash
cp source/tegra/optee-src/nv-optee/optee/samples/hwkey-agent/host/tool/gen_ekb/sym2_t234.key \
   source/tegra/optee-src/nv-optee/optee/samples/luks-srv/host/tool/gen_luks_passphrase/

cd source/tegra/optee-src/nv-optee/optee/samples/luks-srv/host/tool/gen_luks_passphrase

python3 gen_luks_passphrase.py -k sym2_t234.key -c "<UUID>" -u -e "<BR_CID>"
```

Find `UUID` and `BR_CID` values in the flash log files under `Linux_for_Tegra/initrdlog/` (match by timestamp).

**Record the decryption password immediately** — it displays briefly in the terminal.

`[OK]` when the password is displayed and recorded.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `source_sync.sh` fails | Check internet. Retry. Ensure git-lfs is installed. |
| Kernel build fails | Verify cross-compiler path. Check `ARCH=arm64` is set. Install missing deps. |
| `example.sh` (OPTEE) fails | Ensure openssl is installed. Check all `.key` files were generated. |
| Image generation fails | Verify device name matches a `.conf` file. Check `-p` path is correct for your L4T version. |
| USB connection drops during flash | Use a short, high-quality USB cable. Retry. Check Jetson is in recovery mode: `lsusb \| grep NVIDIA`. |
| Flash fails with permission error | Run with `sudo`. Ensure all paths are absolute. |
| `gen_luks_passphrase.py` fails | Verify `sym2_t234.key` is in the correct directory. Check UUID/BR_CID values from logs. |
| Cannot find UUID/BR_CID | Check `Linux_for_Tegra/initrdlog/` for the log file matching your flash timestamp. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with screenshots, JetPack version mapping, and detailed OPTEE key generation steps (reference only)
