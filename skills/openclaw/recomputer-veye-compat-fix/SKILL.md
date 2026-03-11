---
name: recomputer-veye-compat-fix
description: Fix VEYE camera not detected on reComputer Jetson. Upgrades the USB hub chip (VL822) firmware to resolve i2c detection failure.
---

# reComputer VEYE Camera Compatibility Fix

The reComputer carrier board uses a VL822 USB hub chip. Outdated VL822 firmware prevents the VEYE camera from appearing on the i2c bus. This procedure flashes updated firmware to the chip.

---

## Execution model

Run steps in order. Each step must complete cleanly before proceeding.
- If a step fails → stop and consult the failure decision tree.
- If a step succeeds → continue to the next step.
- Do not connect USB devices until Step 7 instructs you to.

---

## Prerequisites

- SSH access to the Jetson (the VEYE camera and all other USB devices must be disconnected before starting).
- The `vl822-fw.tar.bz2` firmware archive from Seeed/VEYE.
- `i2c-tools` installed on the Jetson (`sudo apt install i2c-tools`).

---

## Steps

### Step 1 — SSH into Jetson with no USB devices connected

Disconnect the VEYE camera and any other USB peripherals. Connect via SSH only.

```bash
ssh <user>@<jetson-ip>
```

Confirm no USB devices are attached:
```bash
lsusb
# Expected: only the internal hub, no camera entries
```

### Step 2 — Copy the firmware archive to the Jetson

From your host machine:
```bash
scp vl822-fw.tar.bz2 <user>@<jetson-ip>:~/
```

### Step 3 — Extract the archive and enter the directory

On the Jetson:
```bash
tar -xjvf vl822-fw.tar.bz2
cd vl822-fw
```

### Step 4 — Install the firmware

Follow the instructions in `readme.md` inside the extracted directory:
```bash
cat readme.md
# Read and follow the exact steps listed — they may vary by firmware version
```

The readme will instruct you to run a flash script (e.g., `./flash_vl822.sh` or similar). Run it as directed.

### Step 5 — Power cycle the board

A full power-off/on cycle is required for the new firmware to take effect. Do not just reboot.

```bash
sudo poweroff
```

Wait at least 5 seconds after the board powers off, then power it back on. Reconnect via SSH.

### Step 6 — Verify the firmware version

After the board comes back up:
```bash
cd ~/vl822-fw
./run_2822_ver.sh
```

Confirm the output shows the updated firmware version number.

### Step 7 — Verify VEYE camera i2c detection

Connect the VEYE camera, then run:
```bash
sudo i2cdetect -y -r 6
```

The VEYE camera should appear at address `0x3b`. A `--` at that address means the camera is still not detected.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `0x3b` not present after Step 7 | Check that `run_2822_ver.sh` shows the updated version. If it shows the old version, the firmware flash did not complete — repeat Steps 3–5. |
| `0x3b` still missing after re-flash | Perform a longer power cycle: power off, disconnect power cable for 10 s, reconnect, power on. Then repeat Step 7. |
| `run_2822_ver.sh` errors or shows no output | Confirm you are in the `vl822-fw` directory and the script is executable (`chmod +x run_2822_ver.sh`). |
| `i2cdetect` command not found | Install i2c-tools: `sudo apt install i2c-tools`, then repeat Step 7. |
| SSH drops during firmware flash (Step 4) | Do not interrupt. Wait 2 minutes, then power cycle and check the firmware version in Step 6. |
| Camera detected at wrong address | Wrong camera model or cable issue — verify the VEYE camera model and CSI/USB connection type. |

---

## Reference files

- `references/source.body.md` — original Seeed Wiki article with full background context on the VL822 chip and VEYE camera compatibility
