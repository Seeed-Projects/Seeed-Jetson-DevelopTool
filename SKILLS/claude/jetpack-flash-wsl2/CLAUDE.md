---
name: jetpack-flash-wsl2
description: Flash JetPack on Jetson from Windows using WSL2 + usbipd-win. Covers custom WSL kernel setup, USB passthrough, and Seeed BSP massflash. Not officially supported — use native Ubuntu if issues persist.
---

# Flash JetPack with WSL2

> Stability warning: This is not an officially supported flashing path. Seeed documents it as a workaround. If you hit repeated USB or flash failures, switch to a native Ubuntu 20.04/22.04 machine.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all command output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree below.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Minimum |
|-------------|---------|
| Windows | 10 build 1903+ or Windows 11 |
| WSL2 | installed and enabled |
| usbipd-win | v4.x+ |
| JetPack / WSL distro | JP4.x → Ubuntu 18.04 · JP5.x → 18.04 or 20.04 · JP6.x → 20.04 or 22.04 |

---

## Phase 1 — Check system (PowerShell)

Verify Windows build, WSL version, and usbipd-win. Install the target Ubuntu distro if missing.

```powershell
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v CurrentBuild
wsl -v
usbipd --version
wsl --install -d Ubuntu-22.04
```

Expected: build ≥ 19041, WSL 2.x, usbipd 4.x. `[OK]` when all three pass.

---

## Phase 2 — Set up custom WSL2 kernel (PowerShell + WSL)

The stock WSL2 kernel lacks USB RNDIS support required for flashing. A pre-built kernel is needed.

1. Download the pre-built kernel from the Seeed OneDrive link (see `references/source.body.md`).
   SHA256: `f249022feab9372d448d236a4401e087d0f150dd6b3367b571f0b9a703bd2d38`
2. Place it at `D:\WSL_Kernel\bzImage` (or any path without spaces).
3. Edit `%USERPROFILE%\.wslconfig` — add or update the `[wsl2]` section:
   ```ini
   [wsl2]
   kernel=D:\\WSL_Kernel\\bzImage
   ```
4. Restart WSL and verify:

```powershell
wsl --shutdown
```

```bash
# In WSL after restart:
uname -a
zcat /proc/config.gz | grep RNDIS
```

Expected: `uname -a` shows the custom kernel tag; `grep RNDIS` returns `CONFIG_USB_NET_RNDIS_HOST=y`. `[OK]` when both pass.

---

## Phase 3 — Enter force recovery mode on Jetson

Physical steps — no commands. Do these in order:

1. Power off the Jetson device completely.
2. Short the FEC and GND pins with a jumper.
3. Connect the USB-C cable from the Jetson to the Windows host.
4. Connect power to the Jetson; wait 2–3 seconds, then remove the jumper.

The device is now in APX (force recovery) mode. Proceed immediately to Phase 4.

---

## Phase 4 — Attach USB device to WSL (PowerShell as Administrator)

```powershell
usbipd list
# Locate the "NVIDIA APX" entry and note its bus ID, e.g. 1-1
usbipd bind -b 1-1 -f
usbipd attach -b 1-1 --wsl --auto-attach
```

Verify in WSL:

```bash
lsusb
# Expected line: Bus 001 Device 00x: ID 0955:7045 NVIDIA Corp. APX
```

`[OK]` when `lsusb` shows the NVIDIA APX device. `[STOP]` if it does not appear — see failure decision tree.

---

## Phase 5 — Flash (WSL terminal)

Replace `<user>` and `<xxxx>` with your actual values.

```bash
# Install flash prerequisites
sudo apt install -y qemu-user-static sshpass abootimg nfs-kernel-server libxml2-utils binutils

# Move image from Windows Downloads into WSL home
mv /mnt/c/Users/<user>/Downloads/mfi_recomputer-<xxxx>.tar.gz ~

# Remove accidental execute bit, then verify checksum
chmod -x ~/mfi_recomputer-<xxxx>.tar.gz
sha256sum ~/mfi_recomputer-<xxxx>.tar.gz

# Extract
tar -xzf ~/mfi_recomputer-<xxxx>.tar.gz
cd mfi_recomputer-<xxxx>

# Flash via Seeed BSP massflash
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --flash-only --massflash 1 --network usb0 --showlogs
```

Expected: flash log ends with `Flash success`. `[OK]` when the device reboots into JetPack. `[STOP]` on any error — see failure decision tree.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| APX device not visible in `usbipd list` | Confirm device is in force recovery mode (redo Phase 3). Try a different USB port. Disable Windows Firewall temporarily. |
| `usbipd attach` succeeds but `lsusb` in WSL shows nothing | Confirm usbipd-win is v4.x+. Rerun `usbipd attach`. Check that the correct WSL distro is targeted. |
| RNDIS not in kernel config | Custom kernel not loaded. Verify `.wslconfig` path has double backslashes. Run `wsl --shutdown` and retry. |
| Flash times out or stalls | Cable quality issue — use a cable ≤1.5 m. Ensure 5 V / 4 A power supply. Consider switching to native Ubuntu. |
| `Permission denied` on `/dev/bus/usb` | Run `sudo chmod 666 /dev/bus/usb/001/*` in WSL, then retry flash. |
| `usbipd bind` fails | Run PowerShell as Administrator. |
| SHA256 mismatch on image | Re-download the BSP image. Do not flash a corrupt image. |
| Repeated unexplained failures | This method is not officially supported. Switch to a native Ubuntu 20.04/22.04 host. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with screenshots, kernel download link, and additional context (reference only)
