---
name: backup-restore
description: Backup and restore a reComputer Jetson system image using the L4T backup/restore script. Requires Ubuntu host, USB-C cable, and the matching JetPack BSP package.
---

# Backup and Restore reComputer Jetson System Image

> Hardware required: Ubuntu host PC, USB-C cable, reComputer J3011 (JetPack 5.1.3). The backup and restore operations use the same script with different flags — complete Phases 1–4 for both operations.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all command output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree below.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Host OS | Ubuntu 20.04 or 22.04 (native, not VM) |
| Cable | USB-C data cable ≤1.5 m |
| BSP package | `Jetson_Linux_R35.5.0_aarch64.tbz2` (JetPack 5.1.3) |
| Flashing package | `mfi_recomputer-orin` (Seeed massflash image) |
| Disk space | ≥64 GB free on host for backup image |

---

## Phase 1 — Enter force recovery mode (physical steps, no commands)

Do these steps in order:

1. Power off the reComputer J3011 completely.
2. Locate the **REC** (recovery) button and **GND** pin on the carrier board.
3. Hold the REC button (or short REC to GND with a jumper).
4. While holding REC, connect the USB-C cable from the Jetson to the Ubuntu host.
5. Apply power to the Jetson; wait 2–3 seconds, then release REC / remove the jumper.

Verify on the host:

```bash
lsusb | grep -i nvidia
# Expected: Bus 00x Device 00x: ID 0955:7045 NVIDIA Corp. APX
```

`[OK]` when the NVIDIA APX device appears. `[STOP]` if it does not — see failure decision tree.

---

## Phase 2 — Download and extract BSP

Download `Jetson_Linux_R35.5.0_aarch64.tbz2` from the NVIDIA L4T archive, then extract:

```bash
tar -xvzf Jetson_Linux_R35.5.0_aarch64.tbz2
# Produces: Linux_for_Tegra/
```

`[OK]` when extraction completes without errors and `Linux_for_Tegra/` directory exists.

---

## Phase 3 — Merge BSP into flashing package

Copy BSP files into the Seeed massflash package without overwriting existing files:

```bash
sudo cp -rn Linux_for_Tegra/* mfi_recomputer-orin/
```

`[OK]` when the command completes with no errors.

---

## Phase 4 — Confirm board name

Find the correct board config name before running backup or restore:

```bash
cd mfi_recomputer-orin
ls | grep "\.conf"
# Note the board name, e.g. recomputer-orin-j3011.conf → board name is recomputer-orin-j3011
```

`[OK]` when you have identified the `.conf` filename to use as the `-b` argument.

---

## Phase 5a — Run backup

```bash
# Run from inside mfi_recomputer-orin/
sudo ./tools/backup_restore/l4t_backup_restore.sh -e nvme0n1 -b recomputer-orin
```

Replace `recomputer-orin` with the board name identified in Phase 4 (without `.conf`).

Expected: script prints progress and ends with a success message. The backup image is written to the `backup/` subdirectory.

`[OK]` when the script exits cleanly. `[STOP]` on any error — see failure decision tree.

---

## Phase 5b — Run restore (optional, only if restoring)

Ensure the device is in force recovery mode (redo Phase 1), then:

```bash
# Run from inside mfi_recomputer-orin/
sudo ./tools/backup_restore/l4t_backup_restore.sh -e nvme0n1 -r recomputer-orin
```

Replace `recomputer-orin` with the same board name used during backup.

`[OK]` when the script exits cleanly and the device reboots. `[STOP]` on any error — see failure decision tree.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `lsusb` shows no NVIDIA APX device | Device not in recovery mode. Redo Phase 1. Try a different USB port. Confirm cable is data-rated (not charge-only). |
| Recovery mode entered but device disappears mid-operation | Insufficient power or bad cable. Use the official power adapter and a cable ≤1.5 m. |
| `l4t_backup_restore.sh: No such file or directory` | BSP merge incomplete. Rerun Phase 3 and confirm `tools/backup_restore/` exists inside `mfi_recomputer-orin/`. |
| Script fails with "board not found" or config error | Wrong board name passed to `-b`. Redo Phase 4 and use the exact filename stem from `ls *.conf`. |
| Backup script stalls or times out | USB instability. Flash from bare-metal Ubuntu (not a VM). Reconnect USB and retry from Phase 1. |
| Restore completes but device won't boot | Backup image may be corrupt or from a mismatched board. Verify the backup was taken from the same device and board config. |

---

## Reference files

- `references/source.body.md` — full Seeed Wiki tutorial with screenshots and additional context (reference only)
