---
name: alwaysai-setup
description: Set up the alwaysAI computer vision platform to deploy ML-based object detection on Jetson devices. Supports live camera and video file inference with TensorRT acceleration. Requires JetPack 4.6 and a host PC.
---

# alwaysAI on NVIDIA Jetson

alwaysAI is a computer vision development platform for creating and deploying
ML applications on edge devices. Deploy object detection projects from a host PC
to Jetson via SSH, with TensorRT-optimized models for real-time inference.

Hardware: Jetson device (Nano/Xavier NX/AGX Xavier/AGX Orin), USB webcam or MIPI CSI camera
Software: JetPack 4.6 with all SDK components, host PC (Windows/Linux/Mac)

---

## Execution model

Run one phase at a time. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed

---

## Phase 1 — prerequisites check (~30 s)

On Jetson:
```bash
sudo apt-cache show nvidia-jetpack
# Confirm JetPack 4.6
```

```bash
ls /dev/video*
# Confirm camera is connected
```

`[OK]` when JetPack 4.6 confirmed and camera detected.

---

## Phase 2 — setup host PC (~5 min)

On the development PC:
1. Download and install alwaysAI from https://alwaysai.co/installer/windows (or Mac/Linux equivalent)
2. Verify CLI:
```bash
aai -v
```
3. Verify OpenSSH:
```bash
ssh -V
```

`[OK]` when `aai` and `ssh` both return version numbers.

---

## Phase 3 — setup Jetson environment (~2 min)

On Jetson:
```bash
sudo usermod -aG docker $USER
```

Log out and back in, then verify:
```bash
docker run hello-world
```

`[OK]` when hello-world runs without `sudo`.

---

## Phase 4 — create account & project (human action)

1. Sign up at https://console.alwaysai.co/auth?register=true
2. Create a new project: Dashboard → New Project → Object Detection
3. Delete the default `mobilenet_ssd` model (not optimized for Jetson)
4. Add optimized model: Model Catalog → search `ssd_mobilenet_v1_coco_2018_01_28_xavier_nx` → Add To Project

`[OK]` when project has the TensorRT-optimized model.

---

## Phase 5 — deploy to Jetson (~5 min)

On host PC, create a project folder and configure:
```bash
mkdir ~/alwaysai-project && cd ~/alwaysai-project
aai app configure
```

- Select your project
- Choose "Remote device" as destination
- Add Jetson device: enter `<username>@<jetson_ip>`
- Enter Jetson password when prompted

Edit `app.py` to use the optimized model and TensorRT engine:
```python
def main():
    obj_detect = edgeiq.ObjectDetection("alwaysai/ssd_mobilenet_v1_coco_2018_01_28_xavier_nx")
    obj_detect.load(engine=edgeiq.Engine.TENSOR_RT)
```

Install the app:
```bash
aai app install
```

`[OK]` when install completes successfully.
If errors → try `aai app install --clean`.

---

## Phase 6 — run object detection (~1 min)

```bash
aai app start
```

Open browser: `http://localhost:5000`

Expected: live video feed with detected objects and confidence percentages.

`[OK]` when detections are visible in the browser.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `aai app install` fails | Try `aai app install --clean`. Verify JetPack 4.6 with SDK components. |
| Docker permission denied on Jetson | Run `sudo usermod -aG docker $USER`, log out and back in. |
| SSH connection refused | Verify Jetson IP, ensure SSH is enabled (`sudo systemctl enable ssh`). |
| Low FPS with default model | Switch to TensorRT-optimized model as described in Phase 4. |
| Camera not found | Check camera index in `app.py` (`cam=0`). Try different indices. |
| `aai` command not found | Reinstall alwaysAI CLI. Check PATH. |

---

## Reference files

- `references/source.body.md` — Original Seeed wiki with screenshots, model catalog details, and enterprise edition info
