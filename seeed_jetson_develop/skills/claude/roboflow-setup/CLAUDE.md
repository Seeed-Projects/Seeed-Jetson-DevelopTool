---
name: roboflow-setup
description: Deploy Roboflow inference server on NVIDIA Jetson for real-time AI model inference on webcam streams. Supports pip, Docker Hub, and local Docker build methods. Requires JetPack 5.1.1 and a Roboflow API key.
---

# Getting Started with Roboflow on NVIDIA Jetson

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
| Hardware | reComputer J4012 or any NVIDIA Jetson device |
| JetPack | 5.1.1 (verified version) |
| Camera | USB webcam connected to Jetson |
| Internet | Required for model download and API access |
| Roboflow account | Free account at https://app.roboflow.com |
| Roboflow API key | Private API key from workspace settings |

---

## Phase 1 — Preflight

```bash
cat /etc/nv_tegra_release
ls /dev/video*
```

Expected: JetPack 5.1.1 (R35.x), webcam device listed. `[OK]` when both pass. `[STOP]` if wrong JetPack or no camera.

---

## Phase 2 — Obtain Roboflow API key (manual)

1. Sign up at https://app.roboflow.com.
2. Navigate to Projects > Workspaces > your_workspace > Roboflow API.
3. Copy the "Private API Key".

Choose a model from [Roboflow Universe](https://universe.roboflow.com). Example: `people-detection-general/7`.

`[OK]` when you have the API key and model name.

---

## Phase 3 — Install and run (choose one method)

### Option A: pip package (fastest)

Install SDK components if not already present:

```bash
sudo apt update
sudo apt install nvidia-jetpack -y
sudo apt install python3-pip -y
pip install inference-gpu
```

Set your API key and run:

```bash
export ROBOFLOW_API_KEY=your_key_here
```

Create and run `webcam.py` (see `references/source.body.md` for full script):

```python
import cv2
import inference
import supervision as sv

annotator = sv.BoxAnnotator()

inference.Stream(
    source="webcam",
    model="people-detection-general/7",
    output_channel_order="BGR",
    use_main_thread=True,
    on_prediction=lambda predictions, image: (
        cv2.imshow("Prediction", annotator.annotate(
            scene=image,
            detections=sv.Detections.from_roboflow(predictions)
        )),
        cv2.waitKey(1)
    )
)
```

```bash
python3 webcam.py
```

### Option B: Docker Hub (no SDK install needed)

Start the inference server:

```bash
sudo docker run --network=host --runtime=nvidia roboflow/roboflow-inference-server-jetson-5.1.1
```

On a client (same device or same network), install client dependencies:

```bash
sudo apt update
sudo apt install python3-pip -y
git clone https://github.com/roboflow/roboflow-api-snippets
cd roboflow-api-snippets/Python/webcam
pip install -r requirements.txt
```

Create `roboflow_config.json` with your API key and model name, then:

```bash
python infer-simple.py
```

### Option C: Local Docker build (customizable, supports TensorRT)

```bash
git clone https://github.com/roboflow/inference
cd inference
sudo docker build \
    -f docker/dockerfiles/Dockerfile.onnx.jetson.5.1.1 \
    -t roboflow/roboflow-inference-server-jetson-5.1.1:custom .
```

Start the container:

```bash
docker run --privileged --net=host --runtime=nvidia \
    roboflow/roboflow-inference-server-jetson-5.1.1:custom
```

To enable TensorRT, add this to the Dockerfile before building:

```
ENV ONNXRUNTIME_EXECUTION_PROVIDERS=TensorrtExecutionProvider
```

`[OK]` when inference runs and detected objects are displayed with bounding boxes.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `nvidia-jetpack` install fails | Verify JetPack 5.1.1 is flashed. Run `sudo apt update` first. |
| `pip install inference-gpu` fails | Ensure pip is up to date: `pip install --upgrade pip`. Check CUDA is available. |
| Docker pull fails (19GB image) | Check disk space: `df -h`. Move Docker root to SSD if needed. |
| Inference server starts but no detections | Verify API key is correct. Check model name format: `model_name/version`. |
| Webcam not detected | Check `ls /dev/video*`. Try different USB port. Verify camera works with `v4l2-ctl --list-devices`. |
| Docker container exits immediately | Check logs: `sudo docker logs <container_id>`. Verify `--runtime=nvidia` flag is set. |
| Slow inference with Docker | Enable TensorRT via the `ONNXRUNTIME_EXECUTION_PROVIDERS` env var in the Dockerfile. |
| Client can't connect to server | Verify server is running on port 9001. Check network: `curl http://<jetson_ip>:9001/`. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with all three deployment methods, complete Python scripts, Roboflow Universe walkthrough, and TensorRT configuration (reference only)
