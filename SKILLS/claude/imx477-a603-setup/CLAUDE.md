---
name: imx477-a603-setup
description: Install IMX477 camera driver on reComputer A603 carrier board. Downloads the JetPack-specific BSP with camera driver included and reflashes the device. Supports JP5.1.2, JP6.0, and JP6.2.
---

# IMX477 Camera Driver — A603 Carrier Board

The A603 carrier board requires a custom BSP that bundles the IMX477 driver.
The correct package depends on your JetPack version. The device must be reflashed
after download — there is no in-place driver install path.

Reference: `references/source.body.md` (Seeed wiki source, BSP download links)

---

## Execution model

Run **one phase at a time**. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase

---

## Phase 1 — preflight: check JetPack version (~10 s)

Identify the installed JetPack/L4T version to select the correct BSP package.

```bash
cat /etc/nv_tegra_release
```

Expected output contains a line like:
```
# R35 (release), REVISION: 4.1   → JetPack 5.1.2
# R36 (release), REVISION: 3.0   → JetPack 6.0
# R36 (release), REVISION: 4.0   → JetPack 6.2
```

Map the result to a BSP variant:

| L4T revision | JetPack | BSP package |
|---|---|---|
| R35.4.1 | JP5.1.2 | `A603-JP5.1.2-BSP-with-IMX477.tar.gz` |
| R36.3.0 | JP6.0   | `A603-JP6.0-BSP-with-IMX477.tar.gz`   |
| R36.4.0 | JP6.2   | `A603-JP6.2-BSP-with-IMX477.tar.gz`   |

Tell the user which BSP they need before proceeding.
`[OK]`

---

## Phase 2 — download BSP (~varies by connection)

Download the correct BSP package from the Seeed wiki.
Exact download URLs are in `references/source.body.md` under the matching JetPack section.

After download, verify the archive is intact:
```bash
tar -tzf <BSP_PACKAGE>.tar.gz | head -5
```

If the listing shows files without errors → `[OK]`
If `tar` reports an error → `[STOP] archive corrupt`

---

## Phase 3 — flash device (~15–30 min)

**This step erases the device. Confirm the user has backed up any data.**

Put the device into recovery mode:
1. Power off the reComputer
2. Hold the **REC** button, then connect USB-C to the host PC
3. Release REC after 2 seconds
4. Confirm the device is visible on the host:

```bash
lsusb | grep -i nvidia
```

Expected: `Bus ... NVIDIA Corp. APX`

Extract and run the flash script:
```bash
tar -xzvf <BSP_PACKAGE>.tar.gz
cd <extracted_folder>
sudo ./flash.sh
```

The flash script will take 15–30 minutes. The device reboots automatically when done.
`[OK]` when the device boots to the desktop.

---

## Phase 4 — verify camera (~30 s)

After the device boots, test the IMX477 camera:

```bash
nvgstcapture-1.0 --sensor-id=0
```

A preview window should open. Press `q` to quit.

```bash
# Alternative: check device node exists
ls /dev/video*
```

`[OK]` if preview opens or `/dev/video0` is present.

---

## Failure decision tree

| Symptom | Action |
|---|---|
| `[STOP] L4T revision not in table` | JetPack version may be unsupported. Check `references/source.body.md` for updated BSP list or ask user to confirm board revision |
| `[STOP] archive corrupt` | Re-download the BSP package. Check available disk space with `df -h` |
| `lsusb` does not show NVIDIA APX | Device not in recovery mode. Repeat REC button procedure; try a different USB-C cable |
| Flash script exits with error | Check host has `adb` and `fastboot` installed: `sudo apt install android-tools-adb android-tools-fastboot` |
| Device does not boot after flash | Wrong BSP for board revision. Re-check L4T version and re-flash with correct package |
| `nvgstcapture-1.0` — no such file | GStreamer tools not installed: `sudo apt install gstreamer1.0-tools` |
| `nvgstcapture-1.0` — no cameras available | Camera cable not seated. Power off, reseat the FPC cable, retry |
| `/dev/video0` missing after boot | Driver not loaded. Run `dmesg | grep imx477` and share output for diagnosis |
