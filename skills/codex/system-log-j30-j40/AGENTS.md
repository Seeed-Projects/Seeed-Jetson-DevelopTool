---
name: system-log-j30-j40
description: Retrieve boot and system logs from reComputer J30/J40 series devices via the Jetson serial port (J15 header) using a USB-to-TTL adapter and serial debugging tool (PuTTY, XShell, or MobaXterm).
---

# Get System Log of reComputer J30/J40

## Execution model

Run one phase at a time. After each phase, verify the expected result before continuing.
- If a phase succeeds → print `[OK]` and move to the next phase.
- If a phase fails → print `[STOP]`, consult the failure decision tree, and ask the user before retrying.

## Phase 1 — Verify prerequisites

Required hardware:
- reComputer J4012, J4011, J3010, or J3011
- USB to Serial (TTL) module (e.g., CH340G)
- Host PC with a serial port debugging tool (PuTTY, XShell, or MobaXterm)

Install a serial debugging tool on the host PC if not already available.

## Phase 2 — Hardware connection

1. Connect the J15 interface pins on the reComputer to the USB2TTL module:
   - TX → RX
   - RX → TX
   - GND → GND
2. Connect the USB2TTL module to the host PC via USB.

Expected: USB2TTL module recognized by the host PC.

## Phase 3 — Identify the serial port

On the host PC, find the USB2TTL device identifier:

```bash
# Linux
ls /dev/ttyUSB* /dev/ttyACM*
dmesg | tail -20
```

On Windows: Open Device Manager and look under "Ports (COM & LPT)" for the COM port number.

Expected: Serial device identified (e.g., `/dev/ttyUSB0` on Linux or `COM3` on Windows).

## Phase 4 — Configure serial debugging tool

Open your serial debugging tool and configure:
- Serial port: the port identified in Phase 3
- Baud rate: `115200`
- Data bits: 8
- Stop bits: 1
- Parity: None
- Flow control: None

Click **Connect** / **Open** to start the serial session.

Expected: Serial session opens without errors.

## Phase 5 — Capture boot logs

Power on (or reboot) the Jetson device. The boot logs should appear in the serial debugging tool window.

```bash
# If you need to reboot the Jetson remotely
sudo reboot
```

Expected: System boot logs stream in the serial terminal, showing kernel messages and boot sequence.

## Failure decision tree

| Symptom | Likely cause | Suggested fix |
|---|---|---|
| No serial device found on host | USB2TTL driver not installed | Install CH340 or CP2102 driver for your OS |
| Serial port opens but no output | TX/RX wires swapped | Swap TX and RX connections between J15 and USB2TTL |
| Garbled text in terminal | Wrong baud rate | Ensure baud rate is set to `115200` |
| No output on power-on | Wrong pins on J15 header | Verify pin mapping from reComputer J30/J40 datasheet |
| Permission denied on Linux | User not in dialout group | `sudo usermod -aG dialout $USER` then re-login |

## Reference files

- `references/source.body.md` — Full original wiki content (reference only)
