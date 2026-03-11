---
name: deploy-frigate
description: Deploy Frigate open-source NVR with real-time TensorRT object detection on NVIDIA Jetson (Nano, Xavier NX, Orin). Uses Docker Compose with the Jetson-optimized Frigate image, YOLOv7 model, and RTSP IP camera streams. Requires JetPack 5.x and Docker.
---

# Deploy Frigate on Jetson

Frigate is an open-source NVR with real-time AI object detection. This skill deploys it on Jetson via Docker with TensorRT-accelerated YOLOv7 for IP camera surveillance.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Jetson device | Nano, Xavier NX, or Orin series |
| JetPack | 5.x (e.g. 5.1.3) |
| Docker | Installed with NVIDIA runtime |
| IP Camera | RTSP-compatible (e.g. Dahua) |
| Storage | 32GB+ SD/eMMC/NVMe |

---

## Phase 1 — Install Docker and dependencies (~5 min)

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3-pip python3-dev python3-venv \
    build-essential libssl-dev libffi-dev git \
    apt-transport-https ca-certificates curl software-properties-common
```

Install Docker:

```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=arm64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt-get update
sudo apt-get install -y docker-ce
```

Install Docker Compose:

```bash
sudo pip3 install docker-compose
docker-compose --version
```

Install NVIDIA Container Toolkit per https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html

`[OK]` when `docker-compose --version` prints a version. `[STOP]` if Docker install fails.

---

## Phase 2 — Pull Frigate Docker image (~5–10 min)

```bash
docker pull ghcr.io/blakeblackshear/frigate:stable-tensorrt-jp5
```

Use `stable-tensorrt-jp4` for JetPack 4.6 devices.

`[OK]` when pull completes. `[STOP]` if pull fails — check network and Docker permissions.

---

## Phase 3 — Create Frigate configuration (~5 min)

```bash
mkdir -p ~/frigate/config ~/frigate/storage
```

Create `~/frigate/config/config.yml` with your camera RTSP URL:

```yaml
mqtt:
  enabled: False

cameras:
  my_camera:
    enabled: True
    ffmpeg:
      hwaccel_args: preset-jetson-h264
      inputs:
        - path: rtsp://admin:password@<CAMERA_IP>:554/cam/realmonitor?channel=1&subtype=0
          roles:
            - detect

birdseye:
  enabled: True
  mode: objects

detectors:
  tensorrt:
    type: tensorrt
    device: 0

model:
  path: /config/model_cache/tensorrt/yolov7-320.trt
  input_tensor: nchw
  input_pixel_format: rgb
  width: 320
  height: 320

detect:
  fps: 20
  width: 1280
  height: 720

objects:
  track:
    - person
```

Create `~/frigate/docker-compose.yml`:

```yaml
services:
  frigate:
    privileged: true
    environment:
      - YOLO_MODELS=yolov7-320
      - USE_FP16=false
    container_name: frigate
    runtime: nvidia
    volumes:
      - /home/${USER}/frigate/config:/config
      - /home/${USER}/frigate/storage:/media/frigate
    ports:
      - "5000:5000"
      - "8554:8554"
    image: ghcr.io/blakeblackshear/frigate:stable-tensorrt-jp5
```

`[OK]` when both files are created.

---

## Phase 4 — Deploy and verify Frigate (~3 min)

```bash
cd ~/frigate
docker-compose up -d
docker ps | grep frigate
```

Check logs for TensorRT initialization:

```bash
docker logs frigate
```

`[OK]` when container is running and logs show TensorRT model loaded. `[STOP]` if container fails to start.

---

## Phase 5 — Access Frigate web interface

Open a browser on the same network and navigate to:

```
http://<jetson-ip>:5000
```

You should see the Frigate dashboard with live camera feeds and detection events. Detection latency should be ~33ms per frame on Xavier NX.

`[OK]` when the dashboard loads with live video.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `docker: command not found` | Docker not installed. Re-run Phase 1 Docker installation. |
| `docker pull` permission denied | Add user to docker group: `sudo usermod -aG docker $USER`, then log out/in. |
| Container exits immediately | Check logs: `docker logs frigate`. Common cause: invalid config.yml syntax. |
| TensorRT model not found | First run auto-generates the TRT model. Wait for initialization to complete in logs. |
| No video feed in dashboard | Verify RTSP URL is correct. Test with: `ffplay rtsp://...` from the Jetson. |
| GPU not detected in container | Ensure NVIDIA runtime is configured: check `/etc/docker/daemon.json` has `"default-runtime": "nvidia"`. Restart Docker. |
| Port 5000 not accessible | Check firewall: `sudo ufw allow 5000`. Verify container port mapping with `docker ps`. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with hardware prep, detailed config explanations, and troubleshooting (reference only)
