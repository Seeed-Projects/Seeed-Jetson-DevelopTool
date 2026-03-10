---
name: usb-timeout-during-flashing
description: Diagnose and fix USB timeout errors during JetPack flashing on Jetson. Covers the 5 most common causes: VM USB instability, insufficient power, bad cable, USB hub, wrong package.
---

# USB Timeout During Flashing

USB timeouts during JetPack flashing are almost always caused by one of five environmental issues — not a firmware bug. Work through the checklist in order before retrying the flash script.

---

## Execution model

This is a diagnostic checklist, not a scripted install. Work through each check in order:
- If a check reveals the problem → apply the fix, then restart the flash script from the beginning.
- If a check passes → move to the next one.
- Use the failure decision tree to map your symptom directly to a fix.

---

## Diagnostic checklist

### Check 1 — Ubuntu VM USB instability

If you are flashing from inside a VirtualBox or VMware VM, USB passthrough is unreliable and is the most common cause of timeouts.

Verify:
- The Jetson USB device is exclusively assigned to the VM (not shared with the host).
- USB 3.0 controller is enabled in VM settings (not USB 2.0 emulation).
- No other USB devices are competing for bandwidth during the flash.

Fix: Flash from a native Ubuntu install (bare-metal or live USB) instead of a VM whenever possible.

### Check 2 — Insufficient DC power

The Jetson draws significant current during flashing. An underpowered supply causes USB enumeration to drop mid-flash.

Verify:
- Power supply meets the board's rated wattage (check your reComputer/Jetson model spec sheet).
- No other high-draw peripherals (drives, cameras) are connected during flashing.
- The power LED stays solid — a flickering LED indicates a power issue.

Fix: Use the official power adapter for your board. Disconnect all non-essential peripherals.

### Check 3 — Bad or incompatible Type-C cable

Not all USB-C cables support USB 2.0 data. Charging-only cables and cables over 1.5 m are common culprits.

Verify:
- Cable is rated for USB 2.0 data (not charge-only).
- Cable length is under 1.5 m.
- Try a different cable if in doubt — this is the fastest check to eliminate.

Fix: Replace with a short (<1 m), data-rated USB-C cable.

### Check 4 — USB hub interference

Flashing through a USB hub (even a powered one) introduces latency and packet loss that triggers timeouts.

Verify:
- The Jetson is connected directly to a port on the host machine, not through any hub or dock.
- No USB hubs are in the path between the Jetson and the host.

Fix: Plug the Jetson directly into a rear USB port on the host (rear ports are typically closer to the controller).

### Check 5 — Wrong flashing package

Using a JetPack BSP package that does not match your exact board revision will cause the flash to fail or stall.

Verify:
- The JetPack version matches the Jetson module (e.g., Jetson Orin NX requires JetPack 5.x, not 4.x).
- The BSP package matches your carrier board (reComputer J30x, J40x, etc.).
- You downloaded the package from the official Seeed or NVIDIA source and the checksum is valid.

Fix: Re-download the correct package from the Seeed Wiki or NVIDIA developer site for your exact board SKU.

---

## Restart the flash

Once you have resolved the identified issue:

```bash
# Re-enter recovery mode on the Jetson, then rerun the flash script
sudo ./flash.sh <board-config> mmcblk0p1
```

The exact command depends on your board and JetPack version — refer to your board's flashing guide.

---

## Failure decision tree

| Symptom | Most likely cause | Fix |
|---------|------------------|-----|
| Timeout happens consistently at the same percentage | VM USB passthrough dropping the device | Flash from bare-metal Ubuntu (Check 1) |
| Timeout happens randomly at different points | Power supply or cable issue | Check power adapter and swap cable (Checks 2 & 3) |
| Flash starts then Jetson disappears from `lsusb` | Insufficient power causing USB drop | Use correct power adapter, disconnect peripherals (Check 2) |
| Works on one USB port but not another | Hub or controller issue | Plug directly into a rear port, no hub (Check 4) |
| Flash script errors immediately with "device not supported" | Wrong BSP/JetPack package | Re-download correct package for your board SKU (Check 5) |
| Timeout only when using a dock or hub | USB hub interference | Direct connection required (Check 4) |
| Cable works for charging but not flashing | Charge-only USB-C cable | Replace with data-rated cable under 1.5 m (Check 3) |

---

## Reference files

- `references/source.body.md` — original Seeed Wiki article with full background context and additional notes
