---
name: jetson-resource-index
description: Knowledge base index of Jetson software stack, modules, and resources — JetPack SDK, CUDA, TensorRT, DeepStream, TAO, Triton, Riva, Isaac, and Seeed reComputer module lineup with flash guides.
---

# Jetson Resource Index

This is a knowledge-base skill. Use it to direct users to NVIDIA Jetson
software, hardware modules, and Seeed reComputer documentation.

---

## Execution model

This skill is informational — no destructive commands. Match the user's
question to the relevant resource section below.

---

## Phase 1 — identify what the user needs

Determine the category:
- Jetson software stack / SDK → Section A
- Jetson hardware modules → Section B
- Seeed reComputer flash guides → Section C
- NVIDIA Jetson forums → Section D

`[OK]` when category is identified.

---

## Section A — Jetson software stack

| Component | Description | Link |
|-----------|-------------|------|
| JetPack SDK | Complete dev environment (CUDA-X, Linux kernel, drivers, flash tools) | https://developer.nvidia.com/embedded/jetpack |
| Jetson Linux | L4T driver package, bootloader, kernel | https://developer.nvidia.com/embedded/linux-tegra |
| Cloud-Native | Container runtime for edge | https://developer.nvidia.com/embedded/jetson-cloud-native |
| NVIDIA TAO | Transfer learning toolkit for DL workflows | https://developer.nvidia.com/tao |
| Pretrained Models | Ready-to-use AI models | https://developer.nvidia.com/tao-toolkit |
| Triton Inference Server | Scalable multi-model inference | https://developer.nvidia.com/nvidia-triton-inference-server |
| NVIDIA Riva | Conversational AI SDK (speech, NLP) | https://developer.nvidia.com/riva |
| DeepStream SDK | Stream analytics for video AI | https://developer.nvidia.com/deepstream-sdk |
| NVIDIA Isaac | Robotics SDK (ROS GEM + Isaac Sim) | https://developer.nvidia.com/isaac-sdk |

Full software overview: https://developer.nvidia.com/embedded/develop/software

---

## Section B — Jetson modules used in reComputer

| Module | Compute | reComputer Products |
|--------|---------|-------------------|
| Jetson Xavier NX | Up to 21 TOPS | [J2011](https://www.seeedstudio.com/Jetson-20-1-H1-p-5328.html), [J2012](https://www.seeedstudio.com/Jetson-20-1-H2-p-5329.html) |
| Jetson Nano | 0.5 TFLOPS (FP16), 128 CUDA cores | [J1010](https://www.seeedstudio.com/Jetson-10-1-A0-p-5336.html), [J1020](https://www.seeedstudio.com/Jetson-10-1-H0-p-5335.html) |

All Jetson modules: https://developer.nvidia.com/embedded/jetson-modules

---

## Section C — Seeed reComputer flash guides

| Board | Flash Guide |
|-------|------------|
| J1010 carrier | https://wiki.seeedstudio.com/reComputer_J1010_J101_Flash_Jetpack/ |
| A206 carrier (J1020) | https://wiki.seeedstudio.com/reComputer_J1020_A206_Flash_JetPack/ |

reComputer comes with 16 GB eMMC pre-installed with Ubuntu 18.04 LTS and
JetPack 4.6. Re-flashing is only needed if you want to change the OS.

---

## Section D — NVIDIA Jetson forums

| Forum | Link |
|-------|------|
| Jetson Nano | https://forums.developer.nvidia.com/c/agx-autonomous-machines/jetson-embedded-systems/jetson-nano |
| Jetson Xavier NX | https://forums.developer.nvidia.com/c/agx-autonomous-machines/jetson-embedded-systems/jetson-xavier-nx |

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| User needs a resource not listed | Check https://developer.nvidia.com/embedded/develop/software for the full catalog |
| Link is broken | Search the NVIDIA developer site or Seeed wiki for updated URLs |
| User unsure which module they have | Run `cat /proc/device-tree/model` on the Jetson device |

---

## Reference files

- `references/source.body.md` — Original Seeed wiki with full software stack diagrams and module images
