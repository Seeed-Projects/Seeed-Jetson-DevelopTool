---
name: hardhat-setup
description: Train and deploy a hard hat detection ML model using Edge Impulse on Jetson Nano/NX/AGX. Covers Edge Impulse project setup, data collection (public datasets, PC camera, or Jetson camera), model training, and deployment via Edge Impulse CLI or Linux Python SDK.
---

# Hard Hat Detection with Edge Impulse on Jetson

---

## Execution model

Run one phase at a time. After each phase:
- Relay all command output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree below.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Hardware | NVIDIA Jetson Nano, Xavier NX, or Xavier AGX |
| Peripherals | USB camera, HDMI display, keyboard, mouse |
| Account | Edge Impulse account (https://studio.edgeimpulse.com) |
| Network | Internet connection on both PC and Jetson |
| Software | Ubuntu on Jetson, Edge Impulse CLI |

---

## Phase 1 — Create Edge Impulse project (~2 min)

1. Register/login at https://studio.edgeimpulse.com
2. Click "Create new project", name it "Hard hat detection"
3. Select "Image" as the data type
4. Set configuration to "Classify multiple objects (object detection)"

`[OK]` when the project dashboard is visible.

---

## Phase 2 — Collect and label data (~15–30 min)

Choose one of three data collection methods:

**Option A — Upload public datasets:**
- Download from Flickr-Faces-HQ Dataset (https://github.com/NVlabs/ffhq-dataset)
- Upload via "Data acquisition" → "Upload data" in Edge Impulse

**Option B — PC camera:**
- From Dashboard, click "LET'S COLLECT SOME DATA" → select computer
- Grant camera access, capture images
- Label as "Hard Hat" and "Head"

**Option C — Jetson camera:**
- Connect Jetson to Edge Impulse:

```bash
ping -c 3 www.google.com
edge-impulse-linux
```

- Select USB camera, name the device
- Capture and label images from the "Data acquisition" page

After collection, go to "Labeling queue" and draw bounding boxes around heads. Label as "Hard Hat" or "Head".

`[OK]` when labeled data appears in Data acquisition. `[STOP]` if Jetson can't connect to Edge Impulse.

---

## Phase 3 — Train the model (~10–30 min)

1. Go to "Impulse design" → add image processing block and object detection learning block → Save impulse
2. Click "Image" → configure as "RGB" → "Save Parameters" → "Generate features"
3. Click "Object detection" → "Start training"
4. When training completes, click "Model testing" to evaluate

`[OK]` when model testing shows detection results.

---

## Phase 4 — Deploy to Jetson (~5 min)

**Option A — Edge Impulse CLI runner:**

Ensure Jetson is connected to Edge Impulse (see Phase 2 Option C), then:

```bash
edge-impulse-linux-runner
```

Copy the displayed URL and open in a browser to see live detection.

**Option B — Linux Python SDK:**

```bash
sudo apt-get install libatlas-base-dev libportaudio2 libportaudiocpp0 portaudio19-dev
pip3 install edge_impulse_linux
```

Install Edge Impulse CLI for Linux:

```bash
sudo apt install python3.7-dev
wget -q -O - https://cdn.edgeimpulse.com/firmware/linux/jetson.sh | bash
```

Download the model:

```bash
edge-impulse-linux-runner --download modelfile.eim
```

Run the detection script:

```bash
python3 hardhat_detectation.py /home/jetson-nano/modelfile.eim
```

`[OK]` when detection output shows "Hard Hat" or "Head" labels on the display.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `edge-impulse-linux` command not found | Install Edge Impulse CLI: `wget -q -O - https://cdn.edgeimpulse.com/firmware/linux/jetson.sh \| bash` |
| Jetson can't reach Edge Impulse | Check internet with `ping -c 3 www.google.com`. Verify DNS settings. |
| Camera not detected | Ensure USB camera is connected. Try a different USB port. Check with `ls /dev/video*`. |
| Training accuracy is low | Collect more data. Ensure balanced labels. Improve labeling quality with tight bounding boxes. |
| `edge-impulse-linux-runner` fails | Re-run `edge-impulse-linux` to reconnect. Check account credentials. |
| Model download fails | Add `--clean` flag to switch projects. Check internet connectivity. |
| Python SDK import errors | Ensure `libatlas-base-dev` and other dependencies are installed. Reinstall `edge_impulse_linux`. |
| Detection display not showing | Verify camera is accessible. Check the browser URL from the runner output. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with step-by-step screenshots, Python SDK code, and deployment details (reference only)
