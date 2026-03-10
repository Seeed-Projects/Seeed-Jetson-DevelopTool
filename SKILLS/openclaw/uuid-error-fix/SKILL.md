---
name: uuid-error-fix
description: Resolve UUID-related boot errors on Jetson devices that cause the system to enter recovery terminal (bash-5.1#). Covers clearing OTA flags, replacing corrupted /boot/initrd, and a fresh installation fallback method.
---

# Resolve the Issue of UUID Error

## Execution model

Run one phase at a time. After each phase, verify the expected result before continuing.
- If a phase succeeds → print `[OK]` and move to the next phase.
- If a phase fails → print `[STOP]`, consult the failure decision tree, and ask the user before retrying.

## Symptoms

- System fails to mount user partition with UUID error during boot
- System enters Recovery mode and drops into `bash-5.1#` shell
- Normal startup is prevented despite no kernel modifications

## Method 1: Clear OTA Flags and Replace initrd

### Phase 1 — Mount EFI variables in recovery terminal

In the `bash-5.1#` recovery shell:

```bash
mount -t efivarfs efivarfs /sys/firmware/efi/efivars
```

Expected: No errors; EFI variables filesystem mounted.

### Phase 2 — Clear OTA flag variables

Remove the L4T default boot mode flag:

```bash
chattr -i /sys/firmware/efi/efivars/L4TDefaultBootMode-781e084c-a330-417c-b678-38e696380cb9
rm /sys/firmware/efi/efivars/L4TDefaultBootMode-781e084c-a330-417c-b678-38e696380cb9
```

Remove partition A status flag:

```bash
chattr -i /sys/firmware/efi/efivars/RootfsStatusSlotA-781e084c-a330-417c-b678-38e696380cb9
rm /sys/firmware/efi/efivars/RootfsStatusSlotA-781e084c-a330-417c-b678-38e696380cb9
```

Remove partition B status flag:

```bash
chattr -i /sys/firmware/efi/efivars/RootfsStatusSlotB-781e084c-a330-417c-b678-38e696380cb9
rm /sys/firmware/efi/efivars/RootfsStatusSlotB-781e084c-a330-417c-b678-38e696380cb9
```

Expected: All three flag variables removed without errors.

### Phase 3 — Power down the system

Shut down and power off the Jetson device after clearing the flags.

### Phase 4 — Replace /boot/initrd file

1. Remove the SSD from the Jetson and connect it to a Linux PC using an SSD enclosure.
2. Mount the system root partition (RootFS) from the SSD.
3. Backup the existing `/boot/initrd` file.
4. Replace it with a known-good initrd image matching your L4T version:
   - L4T 36.4.0 (JetPack 6.1): [Download](https://seeedstudio88-my.sharepoint.com/:u:/g/personal/youjiang_yu_seeedstudio88_onmicrosoft_com/IQD15MxbJs_tTqEKA0ouhCygAR7LuRFU5wZzczSziLYUX2s?e=kM4KjT)
   - L4T 36.4.3 (JetPack 6.2): [Download](https://seeedstudio88-my.sharepoint.com/:u:/g/personal/youjiang_yu_seeedstudio88_onmicrosoft_com/IQCpm0jqIgDxRIvM3kk_40P6AX8bfvYF6AbEJ8fRWCNMS8c?e=4nMyMM)
   - L4T 36.4.4 (JetPack 6.2.1): [Download](https://seeedstudio88-my.sharepoint.com/:u:/g/personal/youjiang_yu_seeedstudio88_onmicrosoft_com/IQBFn84LQJqlQ7BgIzvCPp6gAcD9I80K2RBW0v88Uvjh8zs?e=IyaREq)
5. Unmount and reinstall the SSD into the Jetson.

### Phase 5 — Restart and verify

Power on the Jetson device.

Expected: System boots normally without UUID errors or recovery terminal.

## Method 2: Fresh Installation Approach

### Phase 1 — Prepare a blank SSD

1. Get a blank SSD and install it in the Jetson device.
2. Flash the system with the same JetPack version as the old SSD.

### Phase 2 — Swap back the old SSD

1. After successful flash, power off and swap back to the original SSD.
2. Power on the Jetson.

Expected: The old SSD boots normally with all content intact.

## Failure decision tree

| Symptom | Likely cause | Suggested fix |
|---|---|---|
| `mount -t efivarfs` fails | Already mounted or kernel issue | Check `mount \| grep efivarfs`; may already be mounted |
| `chattr -i` permission denied | Not running as root in recovery | Ensure you are in the `bash-5.1#` root shell |
| `rm` fails on EFI variable | File attribute still immutable | Re-run `chattr -i` on the specific file |
| System still enters recovery after initrd replace | Wrong initrd version | Verify L4T version matches the downloaded initrd |
| SSD not recognized on Linux PC | Enclosure or filesystem issue | Try different enclosure; check `lsblk` and `fdisk -l` |
| Fresh install method fails | JetPack version mismatch | Ensure the flashed JetPack version matches the old SSD exactly |

## Reference files

- `references/source.body.md` — Full original wiki content (reference only)
