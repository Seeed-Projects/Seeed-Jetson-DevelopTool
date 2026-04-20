---
name: no-code-edge-ai
description: Deploy the No-Code Edge AI Tool (Node-RED based) on reComputer Jetson Nano for drag-and-drop object detection using a live camera. Requires Jetson Nano with JetPack 4.6.1 and a V4L2 USB camera.
---

# No-Code Edge AI Tool on Jetson Nano

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
| Hardware | reComputer J1010/J1020 with Jetson Nano module |
| Camera | Logitech C270 HD or other V4L2 USB camera supported by Jetson |
| JetPack | 4.6.1 (R32.7.1) |
| Display | Monitor + keyboard/mouse (or SSH/VNC) |
| Internet | Required for initial Docker download |

> **Note:** Only Jetson Nano is supported. Xavier NX is not supported at this time.

---

## Phase 1 — Preflight

Verify JetPack version and camera connection.

```bash
cat /etc/nv_tegra_release
ls /dev/video*
```

Expected: `R32.7.1` (JetPack 4.6.1), at least one `/dev/videoN` device. `[OK]` when both pass. `[STOP]` if wrong JetPack version or no camera detected.

---

## Phase 2 — Download and deploy Docker environment

```bash
git clone https://github.com/Seeed-Studio/node-red-contrib-ml.git
cd node-red-contrib-ml
sudo ./docker-ubuntu.sh
```

The installation and startup takes approximately 7–9 minutes.

Verify Docker containers are running:

```bash
sudo docker image ls
sudo docker ps
```

Expected: three Docker images listed, containers running. `[OK]` when all containers are up. `[STOP]` if any container is missing.

---

## Phase 3 — Configure and run object detection (manual)

1. Open Chrome browser on the Jetson and navigate to `http://127.0.0.1:1880`.
2. In the Block Area, find the "seeed recomputer" section with three blocks:
   - **video input** — camera source selection
   - **detection** — model selection (COCO dataset)
   - **video view** — output display
3. Drag all three blocks to the Programming Area and connect them left-to-right: `video input → detection → video view`.
4. Double-click **video input** → select Device type (local camera), choose your camera, set resolution.
5. Double-click **detection** → select Model name (COCO dataset).
6. Click **Deploy** in the top-right corner.

`[OK]` when the video stream shows detected objects with bounding boxes and confidence values.

---

## Phase 4 — Troubleshooting Docker (if needed)

If Docker did not start successfully or "seeed recomputer" blocks are missing:

```bash
cd node-red-contrib-ml/
sudo docker-compose --file docker-compose.yaml down
sudo docker-compose --file docker-compose.yaml up
```

If results are not showing or debug errors appear:

```bash
sudo docker image ls
# Verify all 3 required images are present
sudo docker ps
# Verify containers are running
```

`[OK]` when blocks appear and detection works after restart.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `cat /etc/nv_tegra_release` shows wrong version | Reflash with JetPack 4.6.1. This tool only supports R32.7.1. |
| No `/dev/video*` devices | Check USB camera connection. Try a different USB port. Verify camera is V4L2 compatible. |
| `docker-ubuntu.sh` fails | Check internet connectivity. Ensure Docker is installed: `sudo apt install docker.io`. |
| Missing Docker images after install | Re-run `sudo ./docker-ubuntu.sh` from the `node-red-contrib-ml` directory. |
| Node-RED UI not loading at port 1880 | Restart Docker containers with `docker-compose down` then `up`. Check `sudo docker ps`. |
| "seeed recomputer" blocks missing | Docker containers not fully started. Restart and wait for all 3 containers to be running. |
| Wrong resolution causes runtime error | Double-click video input block and select the correct resolution for your camera. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with block diagrams, UI screenshots, email notification project example, and advanced block operations (reference only)
