---
name: yolov8-trt
description: Deploy YOLOv8 on NVIDIA Jetson using TensorRT for maximum inference performance. Covers object detection, segmentation, classification, pose estimation, and tracking. Supports pre-trained models, TensorRT FP16/INT8 export, custom model training via Roboflow/Ultralytics HUB, and one-line deployment. Requires JetPack 5.1.1+.
---

# Deploy YOLOv8 with TensorRT on Jetson

Deploy YOLOv8 models on Jetson with TensorRT acceleration for detection, segmentation, classification, pose estimation, and tracking. Includes one-line setup, pre-trained models, and custom model training workflows.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Jetson device | reComputer J4012 or any Jetson with JetPack 5.1.1+ |
| JetPack | 5.1.1 or higher |
| Host PC | Ubuntu (native or VM) for flashing if needed |
| Network | Internet access for downloading models and packages |

---

## Phase 1 — One-line YOLOv8 deployment (~10 min)

The fastest way to get started — this script installs all dependencies and downloads pre-trained models:

```bash
wget files.seeedstudio.com/YOLOv8-Jetson.py && python YOLOv8-Jetson.py
```

`[OK]` when the script completes and YOLOv8 is ready to use. `[STOP]` if download fails or dependency errors occur.

---

## Phase 2 — Run pre-trained models (PyTorch)

Object detection:

```bash
yolo detect predict model=yolov8n.pt source='https://ultralytics.com/images/bus.jpg' show=True
```

Image classification:

```bash
yolo classify predict model=yolov8n-cls.pt source='https://ultralytics.com/images/bus.jpg' show=True
```

Image segmentation:

```bash
yolo segment predict model=yolov8n-seg.pt source='https://ultralytics.com/images/bus.jpg' show=True
```

Pose estimation:

```bash
yolo pose predict model=yolov8n-pose.pt source='https://ultralytics.com/images/bus.jpg'
```

Object tracking (on video):

```bash
yolo track model=yolov8n.pt source="https://youtu.be/Zgi9g1ksQHc"
```

For webcam input, replace `source=` with `source='0'`. Add `device=0` if errors occur.

`[OK]` when predictions display correctly. `[STOP]` if model download or inference fails.

---

## Phase 3 — Export to TensorRT for GPU-accelerated inference (~5 min)

Export any PyTorch model to TensorRT:

```bash
yolo export model=yolov8n.pt format=engine device=0
```

For FP16 quantization (better performance):

```bash
yolo export model=yolov8n.pt format=engine half=True device=0
```

Run inference with the TensorRT engine:

```bash
yolo detect predict model=yolov8n.engine source='0' show=True
```

Available export options: `imgsz` (image size), `half` (FP16), `dynamic` (dynamic axes), `workspace` (GB).

`[OK]` when `.engine` file is created and inference runs on GPU. `[STOP]` if export fails.

---

## Phase 4 — (Optional) Train custom model

Use Roboflow for dataset annotation, then train via:

**Ultralytics HUB + Google Colab:** Integrate Roboflow workspace into Ultralytics HUB, configure training, and run on Colab.

**Roboflow + Google Colab:** Use the prepared Colab notebook with Roboflow API.

**Local PC:**

```bash
sudo apt install python3-pip -y
pip install ultralytics
```

Download dataset from Roboflow in YOLOv8 format, then train:

```bash
yolo detect train data=<path_to_data.yaml> model=yolov8s.pt epochs=100 imgsz=640
```

Copy `runs/detect/train/weights/best.pt` to Jetson and export to TensorRT.

`[OK]` when custom model runs inference on Jetson. `[STOP]` if training fails.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| One-line script fails | Check internet. Run `wget` and `python` commands separately to isolate the issue. |
| `yolo` command not found | Install ultralytics: `pip install ultralytics`. |
| Pre-trained model download fails | Check internet. Manually download `.pt` from Ultralytics assets releases. |
| TensorRT export fails — cmake error | Ignore cmake warnings. Wait for export to complete (can take several minutes). |
| TensorRT export OOM | Use smaller model (yolov8n). Close other GPU processes. |
| CUDA not available | Verify JetPack 5.1.1+: `cat /etc/nv_tegra_release`. Check `nvcc --version`. |
| Webcam not working (`source='0'`) | Check `ls /dev/video*`. Try `device=0` argument. |
| Classification model wrong imgsz | Pass `imgsz=224` for classification models when using TensorRT exports. |
| Custom training OOM | Reduce batch size and image size. Use yolov8n for edge devices. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with pre-trained model tables for all tasks, TensorRT export options, Roboflow/Ultralytics HUB training workflows, performance benchmarks, and exercise detector demo (reference only)
