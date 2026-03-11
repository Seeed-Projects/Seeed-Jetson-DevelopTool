---
name: yolov5-object-detection
description: End-to-end YOLOv5 few-shot object detection pipeline on Jetson. Covers dataset collection, annotation with Roboflow, training (local PC, Google Colab, or Ultralytics HUB), and inference on Jetson using TensorRT or DeepStream SDK. Supports all Jetson platforms from Nano to AGX Xavier.
---

# YOLOv5 Object Detection with Roboflow on Jetson

Complete ML pipeline for YOLOv5: collect data, annotate with Roboflow, train on local PC or cloud, and deploy on Jetson with TensorRT acceleration for real-time object detection.

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
| Jetson device | Any NVIDIA Jetson (Nano, Xavier NX, AGX Xavier, Orin) |
| JetPack | 4.6.1+ with all SDK components |
| Host PC | Linux for local training, or any OS for cloud training |
| Roboflow account | For dataset annotation and export |
| Network | Internet access on both host and Jetson |

---

## Phase 1 — Prepare dataset and annotate with Roboflow

Collect images/video of target objects covering multiple angles, lighting, and conditions. Upload to Roboflow, annotate with bounding boxes, split into train/valid/test, and export in "YOLO v5 PyTorch" format as a `.zip` file.

`[OK]` when you have a downloaded `.zip` with YOLO v5 PyTorch format. `[STOP]` if Roboflow export fails.

---

## Phase 2 — Train the model (choose one method)

**Option A: Local PC (Linux)**

```bash
git clone https://github.com/ultralytics/yolov5
cd yolov5
pip install -r requirements.txt
```

Copy and extract the Roboflow `.zip` into the `yolov5` directory. Edit `data.yaml`:

```
train: train/images
val: valid/images
```

Train:

```bash
python3 train.py --data data.yaml --img-size 640 --batch-size -1 --epoch 100 --weights yolov5n6.pt
```

The trained model is saved at `runs/train/exp/weights/best.pt`.

**Option B: Google Colab** — Use the prepared Colab notebook with Roboflow API integration.

**Option C: Ultralytics HUB** — Upload dataset to HUB, configure training, and run on Colab.

`[OK]` when `best.pt` is generated. `[STOP]` if training fails with OOM (reduce batch size).

---

## Phase 3 — Set up Jetson for TensorRT inference (~15 min)

On the Jetson device:

```bash
sudo apt update
sudo apt install -y python3-pip
pip3 install --upgrade pip
git clone https://github.com/ultralytics/yolov5
cd yolov5
```

Edit `requirements.txt` to pin versions and comment out torch:

```
matplotlib==3.2.2
numpy==1.19.4
# torch>=1.7.0
# torchvision>=0.8.1
```

Install dependencies:

```bash
sudo apt install -y libfreetype6-dev
pip3 install -r requirements.txt
```

Install PyTorch and torchvision for Jetson:

```bash
cd ~
sudo apt-get install -y libopenblas-base libopenmpi-dev
wget https://nvidia.box.com/shared/static/fjtbno0vpo676a25cgvuqc1wty0fkkg6.whl -O torch-1.10.0-cp36-cp36m-linux_aarch64.whl
pip3 install torch-1.10.0-cp36-cp36m-linux_aarch64.whl
sudo apt install -y libjpeg-dev zlib1g-dev
git clone --branch v0.9.0 https://github.com/pytorch/vision torchvision
cd torchvision
sudo python3 setup.py install
```

`[OK]` when `import torch` succeeds on Jetson. `[STOP]` if torch wheel install fails.

---

## Phase 4 — Convert model and run TensorRT inference (~10 min)

Clone tensorrtx and generate engine:

```bash
cd ~
git clone https://github.com/wang-xinyu/tensorrtx
cp tensorrtx/yolov5/gen_wts.py yolov5/
cd yolov5
python3 gen_wts.py -w best.pt -o best.wts
```

Build the TensorRT engine:

```bash
cd ~/tensorrtx/yolov5
```

Edit `yololayer.h` and set `CLASS_NUM` to your number of classes.

```bash
mkdir build && cd build
cp ~/yolov5/best.wts .
cmake ..
make
sudo ./yolov5 -s best.wts best.engine n6
```

Run inference on images:

```bash
sudo ./yolov5 -d best.engine images/
```

`[OK]` when detection output images are generated with bounding boxes. `[STOP]` if engine serialization fails.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Training OOM on local PC | Reduce `--batch-size` to 16 or 8. Use `yolov5n6.pt` for smaller model. |
| CUDA not available on Jetson | Verify JetPack SDK components installed. Check `nvcc --version`. |
| Torch wheel install fails | Ensure correct Python version matches wheel (cp36 for Python 3.6). |
| `torchvision` build fails | Install build deps: `sudo apt install libjpeg-dev zlib1g-dev`. |
| `gen_wts.py` errors | Ensure `best.pt` is in the yolov5 directory. Check model compatibility. |
| `cmake` fails in tensorrtx | Verify TensorRT is installed: `dpkg -l \| grep tensorrt`. |
| Wrong CLASS_NUM | Edit `yololayer.h` to match your dataset class count before building. |
| Engine serialization OOM | Use `n6` (nano) variant. Close other GPU processes. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with Roboflow annotation walkthrough, Ultralytics HUB integration, DeepStream SDK deployment, INT8 calibration, and Jetson Nano vs Xavier NX benchmarks (reference only)
