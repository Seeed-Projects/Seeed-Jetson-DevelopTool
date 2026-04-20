---
name: multi-gmsl-3d-reconstruction
description: Deploy real-time YOLO11 object detection and VGGT 3D reconstruction on Jetson AGX Orin with up to 8 GMSL cameras via the reServer Industrial J501 carrier board and GMSL extension board. Requires JetPack 6.2 and CUDA 12.6.
---

# Multi-GMSL Cameras for Real-Time Object Detection and 3D Reconstruction

---

## Execution model

Run one phase at a time. After each phase:
- Relay all command output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree below.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Minimum |
|-------------|---------|
| Hardware | NVIDIA Jetson AGX Orin 32GB/64GB + reServer Industrial J501 + J501-GMSL extension board |
| Cameras | GMSL cameras (up to 8 supported) |
| JetPack | 6.2 (with GMSL expansion board support) |
| CUDA | 12.6 |
| Internet | Required for package and model downloads |

---

## Phase 1 — Preflight

Verify JetPack version, CUDA, and connected cameras.

```bash
cat /etc/nv_tegra_release
nvcc --version
ls /dev/video*
```

Expected: R36.x (JP6.2), CUDA 12.6, video devices listed. `[OK]` when all pass. `[STOP]` if JetPack < 6.2 or no video devices.

---

## Phase 2 — Configure GMSL cameras

Create the media-ctl configuration script:

```bash
cat > media-setup.sh << 'EOF'
#!/bin/bash
# Set Serializer & Deserializer Formats
media-ctl -d /dev/media0 --set-v4l2 '"ser_0_ch_0":1[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"ser_1_ch_1":1[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"ser_2_ch_2":1[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"ser_3_ch_3":1[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"ser_4_ch_0":1[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"ser_5_ch_1":1[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"ser_6_ch_2":1[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"ser_7_ch_3":1[fmt:YUYV8_1X16/1920x1536]'

media-ctl -d /dev/media0 --set-v4l2 '"des_0_ch_0":0[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"des_0_ch_1":0[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"des_0_ch_2":0[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"des_0_ch_3":0[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"des_1_ch_0":0[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"des_1_ch_1":0[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"des_1_ch_2":0[fmt:YUYV8_1X16/1920x1536]'
media-ctl -d /dev/media0 --set-v4l2 '"des_1_ch_3":0[fmt:YUYV8_1X16/1920x1536]'
EOF
chmod +x media-setup.sh
sudo cp media-setup.sh /usr/local/bin/media-setup.sh
```

Create a systemd service for auto-configuration at boot:

```bash
sudo tee /etc/systemd/system/mediactl-init.service << 'EOF'
[Unit]
Description=Set media-ctl formats at boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/media-setup.sh
RemainAfterExit=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable mediactl-init.service
sudo systemctl start mediactl-init.service
```

Reboot and verify:

```bash
sudo reboot
# After reboot:
sudo systemctl status mediactl-init.service
gst-launch-1.0 v4l2src device=/dev/video0 ! xvimagesink -ev
```

`[OK]` when the service is active and at least one camera stream displays. `[STOP]` if service fails or no video output.

---

## Phase 3 — Install YOLO11 and run multi-camera detection

Download required wheels (built for JP6.2 / CUDA 12.6) and install:

```bash
sudo apt update
sudo apt install python3-pip -y
pip install -U pip

# Download wheels from pypi.jetson-ai-lab.dev (see source.body.md for exact URLs)
pip install onnxruntime_gpu-1.22.0-cp310-cp310-linux_aarch64.whl
pip install torch-2.7.0-cp310-cp310-linux_aarch64.whl
pip install torchvision-0.22.0-cp310-cp310-linux_aarch64.whl
pip install ultralytics
```

Download pretrained weights and export TensorRT engines:

```bash
mkdir -p models
wget -P models/ https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt
wget -P models/ https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n-seg.pt
wget -P models/ https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n-pose.pt

yolo export model=./models/yolo11n.pt format=engine device=0 half=True dynamic=True
yolo export model=./models/yolo11n-seg.pt format=engine device=0 half=True dynamic=True
yolo export model=./models/yolo11n-pose.pt format=engine device=0 half=True dynamic=True
```

Run the multi-camera detection script (see `references/source.body.md` for full `detect.py`):

```bash
python3 detect.py
```

`[OK]` when the 8-camera grid displays with bounding boxes and FPS overlay. `[STOP]` if CUDA errors or cameras not found.

---

## Phase 4 — Deploy VGGT for 3D reconstruction

```bash
git clone https://github.com/facebookresearch/vggt.git
cd vggt
pip install -r requirements.txt
pip install -r requirements_demo.txt
```

Run the 3D reconstruction demo (see `references/source.body.md` for full `demo.py`):

```bash
python3 demo.py --port 8080
```

Open browser to `http://localhost:8080` to view the 3D reconstruction via viser.

`[OK]` when the viser web UI loads and shows the 3D point cloud. `[STOP]` if model download fails or OOM.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| No `/dev/video*` devices | Check physical GMSL cable connections. Verify GMSL extension board is seated properly. |
| `mediactl-init.service` fails | Run `media-setup.sh` manually to see errors. Verify `/dev/media0` exists. |
| `gst-launch` shows no video | Confirm camera format matches `YUYV8_1X16/1920x1536`. Try different `/dev/videoN` index. |
| pip wheel install fails | Ensure wheels match Python 3.10 and aarch64. Re-download if corrupted. |
| TensorRT export OOM | Close other processes. Export one model at a time. |
| VGGT model download slow/fails | Model is ~4GB. Check internet. Use `torch.hub` cache or pre-download. |
| viser web UI not loading | Check port 8080 is not blocked. For remote access, use the Jetson's IP instead of localhost. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with hardware connection diagrams, complete Python scripts (detect.py, demo.py), and VGGT configuration details (reference only)
