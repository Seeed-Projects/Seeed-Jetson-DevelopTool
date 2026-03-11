---
name: train-deploy-yolov8
description: Train and deploy YOLOv8 object detection models entirely on reComputer Jetson (JetPack 5.0+), covering dataset preparation, Label Studio annotation, model training, validation, TensorRT quantization, and real-time inference.
---

# Train and Deploy YOLOv8 on reComputer

## Execution model

Run one phase at a time. After each phase, verify the expected result before continuing.
- If a phase succeeds → print `[OK]` and move to the next phase.
- If a phase fails → print `[STOP]`, consult the failure decision tree, and ask the user before retrying.

## Phase 1 — Verify prerequisites

```bash
cat /etc/nv_tegra_release
dpkg -l | grep nvidia-jetpack
python3 --version
nvcc --version
```

Expected: JetPack 5.0+ installed; CUDA available.

## Phase 2 — Prepare dataset

### Option A: Download public dataset

Download a traffic detection dataset from Kaggle:
- [Traffic Detection Project](https://www.kaggle.com/datasets/yusufberksardoan/traffic-detection-project)

After extraction, update paths in `data.yaml`:

```yaml
train: ./train/images
val: ./valid/images
test: ./test/images

nc: 5
names: ['bicycle', 'bus', 'car', 'motorbike', 'person']
```

### Option B: Collect and annotate custom data with Label Studio

```bash
sudo groupadd docker
sudo gpasswd -a ${USER} docker
sudo systemctl restart docker
sudo chmod a+rw /var/run/docker.sock

mkdir label_studio_data
sudo chmod -R 776 label_studio_data
docker run -it -p 8080:8080 -v $(pwd)/label_studio_data:/label-studio/data heartexlabs/label-studio:latest
```

Access Label Studio at `http://localhost:8080`, create a project, annotate images, and export in YOLO format. Merge annotated data into the public dataset's `train/images` and `train/labels` folders.

## Phase 3 — Install YOLOv8

```bash
git clone https://github.com/ultralytics/ultralytics.git
cd ultralytics
```

Edit `requirements.txt` — comment out torch and torchvision (install Jetson-specific versions separately):

```bash
sed -i 's/^torch>=/#torch>=/' requirements.txt
sed -i 's/^torchvision>=/#torchvision>=/' requirements.txt
pip3 install -e .
cd ..
```

## Phase 4 — Install Jetson PyTorch and TorchVision

```bash
sudo apt-get install -y libopenblas-base libopenmpi-dev
wget https://developer.download.nvidia.cn/compute/redist/jp/v512/pytorch/torch-2.1.0a0+41361538.nv23.06-cp38-cp38-linux_aarch64.whl -O torch-2.1.0a0+41361538.nv23.06-cp38-cp38-linux_aarch64.whl
pip3 install torch-2.1.0a0+41361538.nv23.06-cp38-cp38-linux_aarch64.whl

sudo apt install -y libjpeg-dev zlib1g-dev
git clone --branch v0.16.0 https://github.com/pytorch/vision torchvision
cd torchvision
python3 setup.py install --user
cd ..
```

Verify YOLO installation:

```bash
yolo detect predict model=yolov8s.pt source='https://ultralytics.com/images/bus.jpg'
```

Expected: Inference runs and saves detection results.

## Phase 5 — Train the model

Create `train.py`:

```python
from ultralytics import YOLO

model = YOLO('yolov8s.pt')
results = model.train(
    data='<path_to>/data.yaml',
    batch=8, epochs=100, imgsz=640, save_period=5
)
```

```bash
python3 train.py
```

Consider using `tmux` for long training sessions to prevent disconnection issues.

Expected: Training completes; weight files saved in `runs/detect/train/weights/`.

## Phase 6 — Validate the model

```bash
yolo detect predict \
    model='./runs/detect/train/weights/best.pt' \
    source='./datas/test/images/<test_image>.jpg' \
    save=True show=False
```

Expected: Detection results saved showing correct object detection.

## Phase 7 — Deploy with TensorRT quantization

```bash
pip3 install onnx
yolo export model=./runs/detect/train/weights/best.pt format=engine half=True device=0
```

This takes 10-20 minutes. A `.engine` file is generated alongside the `.pt` file.

Test quantized model inference:

```bash
# Update inference.py to use the .engine file path instead of .pt
python3 inference.py
```

Expected: Significant FPS improvement with the TensorRT engine compared to the original .pt model.

## Failure decision tree

| Symptom | Likely cause | Suggested fix |
|---|---|---|
| `yolo` command not found | YOLOv8 not installed in PATH | Run `pip3 install -e .` from ultralytics directory |
| PyTorch CUDA not available | Wrong wheel for JetPack version | Verify JetPack version and download matching wheel |
| TorchVision build fails | Missing build deps | `sudo apt install libjpeg-dev zlib1g-dev` |
| Training OOM (out of memory) | Batch size too large | Reduce `batch` parameter (try 4 or 2) |
| TensorRT export fails | ONNX not installed or CUDA issue | `pip3 install onnx`; verify `nvcc --version` |
| Label Studio container fails | Docker permissions | Run `sudo chmod a+rw /var/run/docker.sock` |
| Low detection accuracy | Insufficient training data or epochs | Increase dataset size or training epochs |

## Reference files

- `references/source.body.md` — Full original wiki content (reference only)
