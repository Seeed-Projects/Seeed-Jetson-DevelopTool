---
name: yolov8-deepstream-trt
description: Deploy YOLOv8 on NVIDIA Jetson using TensorRT and DeepStream SDK for high-performance video inference. Covers JetPack flashing, DeepStream installation, PyTorch/torchvision setup, DeepStream-Yolo configuration, INT8 calibration, and multistream benchmarks. Supports JetPack 4.6+ with DeepStream 6.0+.
---

# YOLOv8 with TensorRT and DeepStream SDK on Jetson

Deploy YOLOv8 models on Jetson using DeepStream SDK and TensorRT for maximum inference performance. Supports FP32, FP16, and INT8 precision with single and multistream configurations.

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
| Jetson device | reComputer J4012 or any Jetson with JetPack 4.6+ |
| JetPack | 4.6+ (DeepStream 6.0+) or 5.1.1 (DeepStream 6.2) |
| DeepStream SDK | Matching JetPack version (see compatibility table in source) |
| Host PC | Ubuntu (native or VM) for flashing |
| Network | Internet access for cloning repos and downloading models |

---

## Phase 1 — Install DeepStream dependencies (~5 min)

After JetPack is flashed with DeepStream SDK via SDK Manager, install additional dependencies:

```bash
sudo apt install \
  libssl1.1 \
  libgstreamer1.0-0 \
  gstreamer1.0-tools \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav \
  libgstreamer-plugins-base1.0-dev \
  libgstrtspserver-1.0-0 \
  libjansson4 \
  libyaml-cpp-dev
```

`[OK]` when all packages install. `[STOP]` if packages not found (check JetPack/DeepStream version).

---

## Phase 2 — Install Ultralytics and PyTorch (~15 min)

```bash
sudo apt update
sudo apt install -y python3-pip
pip3 install --upgrade pip
git clone https://github.com/ultralytics/ultralytics.git
cd ultralytics
```

Edit `requirements.txt` to comment out torch/torchvision:

```
# torch>=1.7.0
# torchvision>=0.8.1
```

```bash
pip3 install -r requirements.txt
```

Install PyTorch for Jetson (example for JP5.0.2 / PyTorch 1.12):

```bash
sudo apt-get install -y libopenblas-base libopenmpi-dev
wget https://developer.download.nvidia.com/compute/redist/jp/v50/pytorch/torch-1.12.0a0+2c916ef.nv22.3-cp38-cp38-linux_aarch64.whl -O torch-1.12.0.whl
pip3 install torch-1.12.0.whl
```

Install matching torchvision:

```bash
sudo apt install -y libjpeg-dev zlib1g-dev
git clone --branch v0.13.0 https://github.com/pytorch/vision torchvision
cd torchvision
python3 setup.py install --user
```

`[OK]` when `import torch` and `import torchvision` succeed. `[STOP]` if wheel install fails.

---

## Phase 3 — Configure DeepStream for YOLOv8 (~10 min)

```bash
cd ~
git clone https://github.com/marcoslucianops/DeepStream-Yolo
cd DeepStream-Yolo
git checkout 68f762d5bdeae7ac3458529bfe6fed72714336ca
```

Generate config and weights:

```bash
cp utils/gen_wts_yoloV8.py ~/ultralytics
cd ~/ultralytics
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8s.pt
python3 gen_wts_yoloV8.py -w yolov8s.pt
```

Copy generated files and compile:

```bash
cp yolov8s.cfg ~/DeepStream-Yolo
cp yolov8s.wts ~/DeepStream-Yolo
cp labels.txt ~/DeepStream-Yolo
cd ~/DeepStream-Yolo
CUDA_VER=11.4 make -C nvdsinfer_custom_impl_Yolo
```

Edit `config_infer_primary_yoloV8.txt`:

```
custom-network-config=yolov8s.cfg
model-file=yolov8s.wts
num-detected-classes=80
```

Edit `deepstream_app_config.txt` to set:

```
config-file=config_infer_primary_yoloV8.txt
```

`[OK]` when `make` completes and config files are updated. `[STOP]` if CUDA_VER mismatch or compile errors.

---

## Phase 4 — Run inference

```bash
deepstream-app -c deepstream_app_config.txt
```

`[OK]` when video plays with detection overlays. `[STOP]` if DeepStream crashes or engine build fails.

---

## Phase 5 — (Optional) INT8 calibration for higher performance

```bash
sudo apt-get install libopencv-dev
cd ~/DeepStream-Yolo
CUDA_VER=11.4 OPENCV=1 make -C nvdsinfer_custom_impl_Yolo
```

Download COCO val2017, select calibration images:

```bash
mkdir calibration
for jpg in $(ls -1 val2017/*.jpg | sort -R | head -1000); do cp ${jpg} calibration/; done
realpath calibration/*jpg > calibration.txt
export INT8_CALIB_IMG_PATH=calibration.txt
export INT8_CALIB_BATCH_SIZE=1
```

Update `config_infer_primary_yoloV8.txt`:

```
model-engine-file=model_b1_gpu0_int8.engine
int8-calib-file=calib.table
network-mode=1
```

```bash
deepstream-app -c deepstream_app_config.txt
```

`[OK]` when INT8 inference runs with higher FPS. `[STOP]` if calibration fails.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| DeepStream deps not found | Verify JetPack version matches DeepStream version. Reflash if needed. |
| PyTorch wheel install fails | Use Jetson-specific wheel from NVIDIA forums. Match Python version. |
| `torchvision` build fails | Install build deps: `sudo apt install libjpeg-dev zlib1g-dev`. |
| `make` fails — CUDA_VER wrong | Use `CUDA_VER=11.4` for DS 6.2/6.1, `CUDA_VER=10.2` for DS 6.0.x. |
| `gen_wts_yoloV8.py` errors | Ensure correct DeepStream-Yolo commit is checked out. Verify `.pt` file exists. |
| `deepstream-app` crashes | Check config file paths. Verify `.cfg` and `.wts` files are in DeepStream-Yolo dir. |
| Low FPS on screen | Set `type=1` under `[sink0]` in config to disable display and get true FPS. |
| INT8 calibration OOM | Reduce `INT8_CALIB_BATCH_SIZE` or number of calibration images. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with DeepStream/JetPack version table, multistream configuration, trtexec benchmarking, INT8 calibration walkthrough, and performance benchmarks across Jetson devices (reference only)
