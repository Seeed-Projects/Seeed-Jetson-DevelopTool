---
name: jetpack-jetson-overview
description: Knowledge base for the relationship between JetPack and Jetson — JetPack components (L4T + SDK), Ubuntu version mapping, supported Seeed products, Super Mode, and JetPack archive links.
---

# Overview of JetPack and Jetson

This is a knowledge-base skill. Use it to answer questions about JetPack
composition, version mappings, and Seeed product compatibility.

---

## Execution model

This skill is informational — no destructive commands. Present relevant
sections to the user based on their question.

---

## Phase 1 — identify the user's question

Determine which topic the user needs:
- What JetPack is composed of → Section A
- JetPack ↔ Ubuntu version mapping → Section B
- Which JetPack versions Seeed products support → Section C
- JetPack 6.2 and Super Mode → Section D
- How to find contents of each JetPack version → Section E

`[OK]` when topic is identified.

---

## Section A — JetPack composition

JetPack has two major components:

**① L4T (Linux for Tegra)** — middleware Linux distribution for Jetson:
- Ubuntu root filesystem
- Linux kernel (with NVIDIA patches)
- Drivers (GPU, ISP, CSI, I2C, etc.)
- Firmware (Bootloader, UEFI, U-Boot, initrd)
- BSP (Board Support Package) — device trees, boot configs, flash tools

**② JetPack SDK** — upper software layer for application development:
- CUDA Toolkit
- cuDNN (Deep Learning Library)
- TensorRT (AI Model Inference Engine)

---

## Section B — JetPack / L4T / Ubuntu version mapping

| JetPack | L4T | Ubuntu |
|---------|-----|--------|
| 6.2 | 36.4.3 | 22.04 |
| 6.1 | 36.4.0 | 22.04 |
| 6.0 | 36.3.0 | 22.04 |
| 5.1.3 | 35.5.0 | 20.04 |
| 5.1.1 | 35.3.1 | 20.04 |
| 4.6.6 | 32.7.6 | 18.04 |

Check current version on device:
```bash
cat /etc/nv_tegra_release
```

---

## Section C — Seeed product JetPack support

Full compatibility matrix:
https://docs.google.com/spreadsheets/d/1Sf7IdmVkKTAUH95XwxHK0ojV5aFq3ItKZ-iT28egzIk/edit?pli=1&gid=0#gid=0

---

## Section D — JetPack 6.2 and Super Mode

Devices flashed with JetPack 6.2 support Super Mode activation.
Super Mode is currently available only on select Seeed products.

---

## Section E — JetPack version archive

Official NVIDIA JetPack archive with contents of each release:
https://developer.nvidia.com/embedded/jetpack-archive

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| User unsure which JetPack version they have | Run `cat /etc/nv_tegra_release` on the Jetson device |
| L4T version doesn't match any known JetPack | Check NVIDIA archive: https://developer.nvidia.com/embedded/jetpack-archive |
| Seeed product not in compatibility matrix | Contact Seeed support or check the Seeed wiki for latest updates |

---

## Reference files

- `references/source.body.md` — Original Seeed wiki with full version tables and diagrams
