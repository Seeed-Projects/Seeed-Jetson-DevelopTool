---
name: deploy-depth-anything-v3
description: Deploy Depth Anything V3 monocular depth estimation on Jetson AGX Orin with ROS2 Humble integration. Builds a ROS2 workspace with TensorRT-optimized ONNX models for real-time depth map generation from USB camera or video input. Requires JetPack 6.2 and ROS2 Humble.
---

# Deploy Depth Anything V3 on Jetson AGX Orin

Depth Anything V3 generates high-quality depth maps from single RGB images. This skill deploys it on Jetson AGX Orin with ROS2 and TensorRT acceleration for real-time robotics use.

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
| Hardware | Jetson AGX Orin (e.g. reComputer Mini J501) |
| JetPack | 6.2 |
| ROS2 | Humble installed and sourced |
| Camera | USB camera connected |
| Network | Internet for cloning repos and downloading ONNX models |

---

## Phase 1 — Install system dependencies (~3 min)

```bash
sudo apt update
sudo apt install -y \
    build-essential cmake git libopencv-dev \
    python3-pip python3-colcon-common-extensions v4l-utils
pip3 install numpy opencv-python
```

`[OK]` when all packages install without error.

---

## Phase 2 — Configure CUDA environment (~1 min)

```bash
echo '
# CUDA Environment
export CUDA_HOME=/usr/local/cuda
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
export CUDACXX=$CUDA_HOME/bin/nvcc
' >> ~/.bashrc
source ~/.bashrc
nvcc --version
```

`[OK]` when `nvcc --version` prints CUDA version info. `[STOP]` if nvcc is not found.

---

## Phase 3 — Install ROS2 camera packages (~2 min)

```bash
sudo apt install -y ros-humble-usb-cam ros-humble-cv-bridge \
    ros-humble-image-transport ros-humble-image-geometry ros-humble-rviz2
```

`[OK]` when all ROS2 packages install successfully.

---

## Phase 4 — Clone and build the ROS2 workspace (~5 min)

```bash
git clone https://github.com/zibochen6/ros2-depth-anything-v3-trt.git
cd ros2-depth-anything-v3-trt
colcon build --packages-select depth_anything_v3 --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
```

`[OK]` when colcon build completes with no errors. `[STOP]` if build fails.

---

## Phase 5 — Download ONNX model and generate TensorRT engines (~10–20 min)

1. Download the `.onnx` model from https://huggingface.co/TillBeemelmanns/Depth-Anything-V3-ONNX
2. Place it in the `ros2-depth-anything-v3-trt/onnx/` directory
3. Generate engines:

```bash
chmod +x generate_engines.sh
./generate_engines.sh onnx
```

`[OK]` when `.engine` files appear in the `onnx/` directory. `[STOP]` if conversion fails.

---

## Phase 6 — Camera calibration (optional but recommended)

Install calibration tools:

```bash
sudo apt install -y ros-humble-camera-calibration ros-${ROS_DISTRO}-v4l2-camera
```

Launch camera and calibrate:

```bash
# Terminal 1: launch camera
ros2 run v4l2_camera v4l2_camera_node --ros-args -p image_size:=[640,480] -p pixel_format:=YUYV

# Terminal 2: run calibration
ros2 run camera_calibration cameracalibrator \
  --size 8x6 --square 0.025 \
  --ros-args --remap image:=/image_raw --remap camera:=/v4l2_camera
```

Save calibration parameters to `camera_info_example.yaml`.

`[OK]` when calibration completes and parameters are saved.

---

## Phase 7 — Run depth estimation (~1 min)

For USB camera:

```bash
CAMERA_INFO_FILE=camera_info_example.yaml ENABLE_UNDISTORTION=1 ./run_camera_depth.sh
```

For video file:

```bash
./run_video_depth.sh
```

`[OK]` when depth visualization appears.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `nvcc: command not found` | CUDA not installed or not in PATH. Verify JetPack 6.2 installation, re-run Phase 2. |
| `colcon build` fails with missing dependency | Install missing ROS2 or system package, then rebuild. |
| TensorRT engine generation fails | Check ONNX model is valid and placed in correct directory. Verify TensorRT is installed: `dpkg -l \| grep tensorrt`. |
| No `/dev/video*` devices found | USB camera not detected. Replug camera, check with `lsusb` and `v4l2-ctl --list-devices`. |
| ROS2 topic not publishing | Source the workspace: `source install/setup.bash`. Check camera node is running. |
| OOM during engine generation | Close other GPU processes. Engine generation for large models needs significant GPU memory. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with screenshots, calibration details, and video demo links (reference only)
