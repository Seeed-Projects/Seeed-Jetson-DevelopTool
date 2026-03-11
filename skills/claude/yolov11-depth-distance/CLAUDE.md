---
name: yolov11-depth-distance
description: Deploy YOLOv11 with an Orbbec Gemini 2 depth camera on reComputer J4012 (Jetson Orin NX 16GB) for real-time object detection and 3D distance measurement between detected objects. Uses TensorRT for accelerated inference and pyorbbecsdk for depth data. Requires JetPack 5.1.3.
---

# YOLOv11 + Depth Camera Distance Measurement on Jetson Orin

Combine YOLOv11 object detection with Orbbec Gemini 2 depth camera on reComputer J4012 to detect objects and measure real-world 3D distances between them in real time using TensorRT acceleration.

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
| Jetson device | reComputer J4012 (Orin NX 16GB) or similar reComputer |
| JetPack | 5.1.3 pre-installed |
| Camera | Orbbec Gemini 2 Depth Camera + USB Type-C cable |
| TensorRT | 8.x (included with JetPack 5.x) |
| Python | 3.8 |

---

## Phase 1 — Install Orbbec Gemini 2 Python SDK (~10 min)

Clone and install dependencies:

```bash
git clone https://github.com/orbbec/pyorbbecsdk.git
sudo apt-get install python3-dev python3-venv python3-pip python3-opencv cmake g++ gcc
pip install pybind11
```

Install Python requirements:

```bash
cd pyorbbecsdk
pip install -r requirements.txt
```

Build the SDK:

```bash
mkdir build
cd build
cmake \
  -Dpybind11_DIR=`pybind11-config --cmakedir` \
  -DPython3_EXECUTABLE=/usr/bin/python3.8 \
  -DPython3_INCLUDE_DIR=/usr/include/python3.8 \
  -DPython3_LIBRARY=/usr/lib/aarch64-linux-gnu/libpython3.8.so \
  ..
make -j4
make install
```

Install the Python wheel:

```bash
cd /path/to/pyorbbecsdk
pip install wheel
python setup.py bdist_wheel
pip install dist/*.whl
```

`[OK]` when `import pyorbbecsdk` works in Python. `[STOP]` if cmake or make fails.

---

## Phase 2 — Test depth camera (~2 min)

Create a test script or use the SDK examples to verify the camera outputs both RGB and depth frames. Connect the Gemini 2 via USB-C and run:

```bash
python test.py
```

Expected: A window showing RGB image on the left and depth colormap on the right.

`[OK]` when both streams display correctly. `[STOP]` if camera is not detected or frames are empty.

---

## Phase 3 — Deploy YOLOv11 with TensorRT (~15 min)

Clone the TensorRT implementation:

```bash
git clone https://github.com/wang-xinyu/tensorrtx.git
cd tensorrtx/yolo11
```

Download the YOLOv11n model:

```bash
wget -O yolo11n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt
```

Generate the `.wts` file:

```bash
python gen_wts.py -w yolo11n.pt -o yolo11n.wts -t detect
```

Build the TensorRT engine:

```bash
mkdir build
cd build
cmake ..
make -j4
./yolo11_det -s yolo11n.wts yolo11n.engine n
```

Install pycuda for Python inference:

```bash
pip install pycuda
```

`[OK]` when `yolo11n.engine` file is generated in the build directory. `[STOP]` if cmake/make fails or engine serialization errors.

---

## Phase 4 — Run distance measurement

Run the combined detection + distance measurement script (see `source.body.md` for the full `distance_measurement.py` script):

```bash
python distance_measurement.py
```

The script detects objects (e.g., cup and mouse) and calculates 3D Euclidean distance between them using depth camera intrinsics:
- `fx=616.707275, fy=616.707275, cx=648.300171, cy=404.478149`

Expected: Real-time video with bounding boxes and distance overlay.

`[OK]` when distance measurements appear on screen. `[STOP]` if engine loading fails or camera errors.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `cmake` fails — pybind11 not found | Verify `pip install pybind11` and check `pybind11-config --cmakedir` output. |
| `make` fails — Python headers missing | Install `python3-dev`: `sudo apt-get install python3-dev`. |
| Camera not detected | Check USB-C connection. Run `lsusb` to verify Orbbec device. Try different USB port. |
| `import pyorbbecsdk` fails | Ensure the `.whl` was installed. Re-run `pip install dist/*.whl`. |
| TensorRT engine build fails | Confirm TensorRT 8.x is installed: `dpkg -l \| grep tensorrt`. JetPack 6+ requires code modifications. |
| `pycuda` import error | Install: `pip install pycuda`. Ensure CUDA toolkit is in PATH. |
| OOM during engine serialization | Close other GPU processes. Orin NX 16GB should be sufficient for yolo11n. |
| Distance values seem wrong | Verify camera intrinsics with `get_camera_parameters.py`. Ensure HW D2C alignment is enabled. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with hardware connection photo, SDK build details, test scripts, distance calculation math, and complete `distance_measurement.py` source code (reference only)
