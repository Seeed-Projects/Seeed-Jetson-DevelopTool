---
name: jetson-ai-tools
description: Knowledge base for Jetson AI developer tools and Seeed ecosystem partners — CVEDIA-RT, Lumeo, alwaysAI, YOLOv5/v8, Roboflow, Allxon, Deci, Edge Impulse, Cochl.Sense. Use to recommend tools or find getting-started guides.
---

# Jetson AI Developer Tools

This is a knowledge-base skill. Use it to recommend AI developer tools
available for Seeed Jetson devices and point users to getting-started guides.

---

## Execution model

This skill is informational — no destructive commands. Match the user's
use case to the appropriate tool and provide the relevant links.

---

## Phase 1 — identify the user's use case

Determine what the user needs:
- Video analytics / computer vision → CVEDIA-RT, Lumeo, YOLOv5/v8, Roboflow
- General CV application platform → alwaysAI
- Object detection with custom training → YOLOv5/v8 + Roboflow
- Device management / remote monitoring → Allxon
- Model optimization / deployment → Deci
- ML on edge with low-code → Edge Impulse
- Sound/audio detection → Cochl.Sense

`[OK]` when use case is identified.

---

## Tool directory

| Tool | Description | Links |
|------|-------------|-------|
| CVEDIA-RT | Modular cross-platform AI inference engine for decision support | [Site](https://www.cvedia.com/cvedia-rt) · [Jetson Guide](https://wiki.seeedstudio.com/CVEDIA-Jetson-Getting-Started) |
| Lumeo | No-code video analytics platform | [Site](https://lumeo.com/) · [Jetson Guide](https://wiki.seeedstudio.com/Lumeo-Jetson-Getting-Started) |
| alwaysAI | Platform for building/deploying CV apps on IoT | [Site](https://alwaysai.co/) · [Jetson Guide](https://wiki.seeedstudio.com/alwaysAI-Jetson-Getting-Started/) |
| YOLOv8 | SOTA object detection, segmentation, pose estimation | [GitHub](https://github.com/ultralytics/ultralytics) · [Jetson TRT+DeepStream](https://wiki.seeedstudio.com/YOLOv8-DeepStream-TRT-Jetson) |
| YOLOv5 | Real-time object detection | [Site](https://ultralytics.com/yolov5) · [Few-Shot Detection](https://wiki.seeedstudio.com/YOLOv5-Object-Detection-Jetson/) |
| Roboflow | Image annotation and model training platform | [Site](https://roboflow.com/) · [Road Signs](https://wiki.seeedstudio.com/YOLOv5-Road-Signs-Detection-Jetson/) · [Wildfire](https://wiki.seeedstudio.com/YOLOv5-Roboflow-Wildfire-Smoke-Detection-Jetson/) |
| Allxon | Edge device management for Jetson | [Site](https://www.allxon.com/) · [Jetson Guide](https://wiki.seeedstudio.com/Allxon-Jetson-Getting-Started/) |
| Deci | End-to-end DL model optimization and deployment | [Site](https://deci.ai/) · [Jetson Guide](https://wiki.seeedstudio.com/DeciAI-Getting-Started/) |
| Edge Impulse | Low-code ML development for edge devices | [Site](https://www.edgeimpulse.com/) · [Hard Hat Detection](https://wiki.seeedstudio.com/HardHat/) |
| Cochl.Sense | Machine listening / audio classification | [Site](https://www.cochl.ai/) · [Jetson Guide](https://wiki.seeedstudio.com/Cochl.Sense-Jetson-Getting-Started) |

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| User unsure which tool to use | Ask about their use case (vision, audio, management, training) and recommend from the table |
| Getting-started link is broken | Check the Seeed wiki directly: https://wiki.seeedstudio.com/ |
| Tool doesn't support user's JetPack version | Check tool's documentation for version requirements. Most require JetPack 4.6+. |

---

## Reference files

- `references/source.body.md` — Original Seeed wiki with partner logos and full tool descriptions
