---
name: l4t-differences
description: Reference guide for differences between Seeed and NVIDIA L4T Board Support Packages across versions 35.3.1, 35.5, 36.3, 36.4, and 36.4.3. Covers added drivers for CAN bus, Wi-Fi, Ethernet, GMSL, TPM, audio codecs, and USB on Seeed Jetson devices.
---

# Differences in L4T between Seeed and NVIDIA

Seeed's Jetson BSPs are based on NVIDIA's L4T with modifications to support Seeed hardware. This skill identifies the specific driver and feature differences per L4T version so users can understand what Seeed adds on top of the NVIDIA baseline.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all output to the user.
- If output contains `[STOP]` → stop, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Hardware | Seeed Jetson device (reComputer series) |
| JetPack | Identify installed version before proceeding |

---

## Phase 1 — Identify L4T version (~30 s)

```bash
cat /etc/nv_tegra_release
```

Or:

```bash
dpkg -l | grep -i nvidia-l4t-core
```

`[OK]` when L4T version string is displayed (e.g. R36.4.3, R35.5).
`[STOP]` if file not found — device may not be running L4T.

---

## Phase 2 — Identify JetPack version (~30 s)

```bash
dpkg -l | grep -i jetpack
```

Map the L4T version to JetPack:

| L4T Version | JetPack |
|-------------|---------|
| 36.4.3 | 6.2 |
| 36.4 | 6.1 |
| 36.3 | 6.0 |
| 35.5 | 5.1.3 |
| 35.3.1 | 5.1.1 |

`[OK]` when JetPack version is confirmed.

---

## Phase 3 — Review Seeed BSP differences for your version

Based on the L4T version identified in Phase 1, here are the key additions Seeed makes over NVIDIA's default BSP:

### L4T 36.4.3 (JetPack 6.2)
- MCP251X / MCP251XFD CAN bus controllers
- Intel Wi-Fi driver (generic + modular + tracing)
- Microchip LAN743x Gigabit Ethernet
- PPP protocol support (async serial)
- Realtek 88-series Wi-Fi (8723D, 8723DU, 8723X, USB)
- TI TLV320AIC3X audio codec (I²C)
- MAX9296A / MAX96717 / MAX96724 GMSL deserializers + aggregator
- CRC-CCITT checksum, advanced video debug interface

### L4T 36.4 (JetPack 6.1)
- MCP251X / MCP251XFD CAN bus controllers
- Intel Wi-Fi MVM driver (generic + tracing + LED)
- Microchip LAN743x Gigabit Ethernet
- PPP protocol support (async serial)
- Realtek RTW88 Wi-Fi (8723D, 8723DU, 8723X, USB)
- CH341 USB-to-serial converter
- CRC-CCITT, compression libraries for PPP

### L4T 36.3 (JetPack 6.0)
- MCP251X / MCP251XFD CAN bus controllers
- Intel Wi-Fi (generic + tracing), I²C ATR protocol
- Microchip LAN743x Gigabit Ethernet
- Realtek 88-series Wi-Fi (8723D, 8723DU, 8723X)
- TI TLV320AIC3X audio codec (I²C)
- MAX96717 / MAX96724 / MAX9296A GMSL deserializers + aggregator
- TPM core + SPI + Infineon I²C, SELinux

### L4T 35.5 (JetPack 5.1.3)
- IMX219 camera compiled into kernel (NVIDIA: module)
- IMX390 camera disabled (NVIDIA: compiled in)
- LAN743x compiled into kernel (NVIDIA: module)
- TI DP83867 Ethernet PHY, NXP PTN5150 USB Type-C
- nvmem framework, STPMIC1 / TPS65090 power management
- LM90 temp sensor, NTC thermistors
- TLV320AIC3X audio codec (I²S + I²C)
- USB Type-C TCPCI, MT6370 Type-C controller
- USB console device, CH341 USB-to-serial

### L4T 35.3.1 (JetPack 5.1.1)
- TPM hardware RNG as entropy source
- `/sys/kernel/security` mount for SELinux/AppArmor
- TPM core interface + SPI bus access
- TPM secure boot and key storage

`[OK]` — informational phase, no commands to run.

---

## Phase 4 — Verify Seeed-specific drivers are loaded (optional)

Check for CAN bus support:

```bash
lsmod | grep mcp251
```

Check for Realtek Wi-Fi:

```bash
lsmod | grep rtw
```

Check for GMSL deserializer (L4T 36.x):

```bash
lsmod | grep max96
```

`[OK]` when relevant modules appear for your hardware configuration.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `/etc/nv_tegra_release` not found | Device may not be running L4T. Check if this is a Jetson device with `uname -a`. |
| L4T version not in the table | Seeed BSP may not be installed. Reflash with Seeed's BSP from their download page. |
| Expected driver module not loaded | Check if module exists: `find /lib/modules -name "*.ko" \| grep <driver>`. Load with `sudo modprobe <driver>`. |
| CAN interface not working | Verify MCP251X hardware is connected. Check `dmesg \| grep can` for errors. |
| Wi-Fi adapter not detected | Confirm USB/PCIe Wi-Fi adapter is plugged in. Check `lsusb` or `lspci`. |

---

## Reference files

- `references/source.body.md` — Full listing of all Seeed BSP differences per L4T version with additional context (reference only)
