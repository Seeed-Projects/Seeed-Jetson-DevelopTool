---
name: jetpack5-ssd-boot-fix
description: Fix JetPack 5 boot failures from NVMe SSDs on Seeed Jetson devices. Two options — full SSD wipe via external enclosure, or re-flash with --erase-all flag. JetPack 6 is not affected.
---

# Fix JetPack 5 SSD Boot Failure

JetPack 5 may fail to boot from certain NVMe SSDs even after a successful flash.
This is caused by filesystem incompatibility or incomplete wiping during flash.
JetPack 6 is not affected by this issue.

Hardware: Seeed Jetson device, NVMe SSD, SSD enclosure (for Option A), USB cable
Software: JetPack 5.x, Ubuntu host PC

---

## Execution model

Run one phase at a time. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed

Two repair options are available. Ask the user which they prefer before starting.

---

## Phase 1 — confirm the issue (~1 min)

Symptom: JetPack 5 was flashed successfully to SSD, but device fails to boot
with filesystem errors on screen.

```bash
# On the Jetson (if accessible via serial/recovery), check:
cat /etc/nv_tegra_release
```

`[OK]` when user confirms JetPack 5 boot failure from SSD.
`[STOP]` if running JetPack 6 (this issue does not apply).

---

## Option A — Wipe SSD externally

### Phase 2A — connect SSD to host PC (~1 min)

1. Remove the NVMe SSD from the Jetson device
2. Connect it to a host PC using an NVMe-to-USB enclosure
3. Identify the device name:

```bash
lsblk
```

Verify it's the Jetson SSD by checking for Jetson device tree files:
```bash
ls /media/$USER/*/boot/
# Should show Jetson-specific device tree files (*.dtb)
```

`[OK]` when SSD is identified (e.g. `/dev/sda`).
`[STOP]` if SSD not detected — check enclosure and cable.

### Phase 3A — wipe the SSD (~5–15 min)

> ⚠️ DANGER: This destroys all data. Back up first. Double-check the device name.

Replace `/dev/sdX` with the actual device. Adjust `count` for larger SSDs
(count=800 with bs=100M = 80 GB wiped):

```bash
sudo wipefs -a /dev/sdX
sudo dd if=/dev/zero of=/dev/sdX bs=100M count=800
```

`[OK]` when dd completes without errors.

### Phase 4A — re-flash JetPack 5 (~15–30 min)

1. Reinstall the SSD into the Jetson
2. Put device into recovery mode
3. Flash JetPack 5 following the standard Seeed flash guide:
   https://wiki.seeedstudio.com/flash/jetpack_to_selected_product/

`[OK]` when device boots successfully from SSD.

---

## Option B — Re-flash with --erase-all

### Phase 2B — prepare BSP source project

Follow the Seeed BSP source build guide to prepare the flashing environment:
https://wiki.seeedstudio.com/how_to_build_the_source_code_project_for_seeed_jetson_bsp

### Phase 3B — flash with full erase (~15–30 min)

Add `--erase-all` to the flash command to completely wipe the SSD during flash:

```bash
sudo ./tools/kernel_flash/l4t_initrd_flash.sh --erase-all \
  --external-device nvme0n1p1 \
  -c tools/kernel_flash/flash_l4t_nvme.xml \
  -p "-c bootloader/t186ref/cfg/flash_t234_qspi.xml --no-systemimg" \
  --network usb0 <DEVICE_NAME> external
```

Replace `<DEVICE_NAME>` with the appropriate board config name.

`[OK]` when flash completes and device boots.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| SSD not detected via enclosure | Try different USB port/cable. Check enclosure compatibility with NVMe. |
| `dd` reports I/O error | SSD may be hardware-faulty. Try a different SSD. |
| Boot still fails after wipe + re-flash | Wipe more of the SSD (increase `count`). Or try Option B with `--erase-all`. |
| `--erase-all` flash fails | Ensure device is in recovery mode. Check USB cable. Retry. |
| Issue persists after both options | Consider upgrading to JetPack 6, which is not affected. |

---

## Reference files

- `references/source.body.md` — Original Seeed wiki with screenshots and detailed context
