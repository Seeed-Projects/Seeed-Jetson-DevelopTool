---
name: maskcam-nano
description: Run MaskCam face mask detection on Jetson Nano 4GB using Docker. Streams results via RTSP. Requires JetPack 4.6 and a USB camera.
---

# MaskCam on Jetson Nano

> Hardware required: Jetson Nano 4GB, JetPack 4.6, USB camera, Docker with nvidia runtime, docker-compose. MaskCam detects face mask compliance and streams annotated video over RTSP.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all command output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree below.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Board | Jetson Nano 4GB |
| JetPack | 4.6 |
| Camera | USB camera connected before starting Docker |
| Docker | Installed with NVIDIA container runtime (`nvidia-docker2`) |
| Network | Jetson reachable on LAN for RTSP stream access |

---

## Phase 1 — Pull Docker image

```bash
sudo docker pull maskcam/maskcam-beta
```

Verify:

```bash
sudo docker images | grep maskcam
# Expected: maskcam/maskcam-beta listed with a recent tag
```

`[OK]` when the image appears in `docker images`. `[STOP]` if pull fails — see failure decision tree.

---

## Phase 2 — Get device IP address

```bash
sudo ifconfig
# Note the inet address for your active interface (e.g. eth0 or wlan0)
# Example: inet 192.168.1.42
```

`[OK]` when you have the Jetson's IP address noted. You will use it to access the RTSP stream in Phase 4.

---

## Phase 3 — Run MaskCam

```bash
sudo docker run --runtime nvidia -it --rm \
  --network host \
  -v /tmp/argus_socket:/tmp/argus_socket \
  maskcam/maskcam-beta
```

Expected: container starts and prints initialization logs, then begins processing camera frames. You should see inference output in the terminal.

`[OK]` when the container is running and printing frame inference results. `[STOP]` if the container exits immediately or errors — see failure decision tree.

---

## Phase 4 — View RTSP stream

With MaskCam running, open the stream in VLC or any RTSP-capable player on another machine:

```
rtsp://<jetson-ip>:8554/maskcam
```

Replace `<jetson-ip>` with the address noted in Phase 2.

In VLC: Media -> Open Network Stream -> paste the URL above.

`[OK]` when the annotated video stream is visible with mask detection overlays.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `docker run` fails with "unknown runtime: nvidia" | NVIDIA container runtime not configured. Install `nvidia-docker2`: `sudo apt install nvidia-docker2` then `sudo systemctl restart docker`. |
| Container exits immediately with "no cameras available" | USB camera not detected. Confirm camera is connected: `ls /dev/video*`. Reconnect camera and retry. |
| Container exits with "failed to open argus socket" | Argus socket not available. Ensure `/tmp/argus_socket` exists on the host: `ls /tmp/argus_socket`. If missing, reboot the Jetson. |
| RTSP stream URL not accessible from another machine | Check that port 8554 is not blocked: `sudo ufw status`. Allow if needed: `sudo ufw allow 8554`. Confirm you are using the correct Jetson IP from Phase 2. |
| RTSP stream connects but shows black screen | Camera may not be initializing correctly inside the container. Check container logs for camera errors. Try a different USB port. |
| Very low FPS or inference stalls | Ensure no other GPU-heavy processes are running. Check Jetson power mode: `sudo nvpmodel -m 0` (max performance). |

---

## Reference files

- `references/source.body.md` — full Seeed Wiki tutorial with screenshots and additional context (reference only)
