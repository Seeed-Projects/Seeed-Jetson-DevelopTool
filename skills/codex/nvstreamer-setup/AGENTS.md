---
name: nvstreamer-setup
description: Set up NVStreamer for RTSP video streaming on reComputer J4012 with Jetson Platform Services. Covers installation, video upload, RTSP stream creation, and VST integration. Requires JetPack 6.0+ with CUDA 12.2.
---

# Getting Started with NVStreamer on reComputer Jetson

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
| Hardware | reComputer J4012 (Orin NX 16GB) |
| OS | Ubuntu 22.04+ |
| JetPack | 6.0 (Driver 535.113.01, CUDA 12.2) |
| Storage | Sufficient space for video files (hundreds of GB recommended) |
| Packages | `nvidia-jetpack` and `nvidia-jetson-services` |

---

## Phase 1 — Preflight and install dependencies

```bash
cat /etc/nv_tegra_release
df -h /
sudo apt-get install nvidia-jetpack
sudo apt install nvidia-jetson-services
```

Expected: R36.x (JP6.0+), sufficient disk space, packages installed. `[OK]` when all pass. `[STOP]` if JetPack < 6.0.

---

## Phase 2 — Install and start NVStreamer

Download `nvstreamer-1.1.0.tar.gz` from [NGC Reference Workflow and Resources](https://catalog.ngc.nvidia.com/orgs/nvidia/teams/jps/resources/reference-workflow-and-resources) (NGC credentials required).

```bash
tar -xvzf nvstreamer-1.1.0.tar.gz
```

Increase OS socket buffer sizes to avoid packet loss with high-bitrate video:

```bash
sudo sysctl -w net.core.wmem_max=2000000
sudo sysctl -w net.core.rmem_max=2000000
```

Start NVStreamer:

```bash
cd nvstreamer
sudo docker compose -f compose_nvstreamer.yaml up -d --force-recreate
```

Verify:

```bash
sudo docker ps | grep nvstreamer
```

`[OK]` when the NVStreamer container is running. `[STOP]` if Docker fails to start.

To stop NVStreamer later:

```bash
cd nvstreamer
sudo docker compose -f compose_nvstreamer.yaml down --remove-orphans
```

---

## Phase 3 — Upload video and create RTSP stream (manual)

1. Open Chrome and navigate to `http://<reComputer-IP>:31000`.
2. Select "File Upload" and drag-and-drop an mp4/mkv video file (h264/h265 codec).
3. Wait for the green progress bar to complete and transcoding to finish.
4. The file name appears in gray and an RTSP stream URL is automatically created.
5. Copy the RTSP address (including `rtsp://` prefix, no leading spaces).

`[OK]` when the RTSP URL is generated and copied.

---

## Phase 4 — Add RTSP stream to VST (manual)

1. Open browser to `http://<JETSON-IP>:30080/vst/` (HTTP, not HTTPS).

If VST fails to load, start the required services:

```bash
sudo systemctl start jetson-ingress
sudo systemctl start jetson-monitoring
sudo systemctl start jetson-sys-monitoring
sudo systemctl start jetson-gpu-monitoring
sudo systemctl start jetson-redis
sudo systemctl start jetson-vst
```

2. Click "Camera Management" tab → click "RTSP".
3. Paste the RTSP address from NVStreamer into the "rtsp url" box.
4. Fill "location" and "name" fields with the same string (becomes the camera name).
5. Click "Submit".
6. Click "Streams" tab to verify the video stream.

`[OK]` when the video stream is visible in the VST Streams tab.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `nvidia-jetson-services` install fails | Verify JetPack 6.0+ is installed. Run `sudo apt update` first. |
| NVStreamer Docker fails to start | Check Docker is installed and running: `sudo systemctl status docker`. Verify NGC download was complete. |
| Port 31000 not accessible | Check firewall rules. Verify NVStreamer container is running: `sudo docker ps`. |
| Video upload fails / transcoding stuck | Ensure video codec is h264 or h265 in mp4/mkv container. Check disk space. |
| Blocky artifacts in video | Socket buffer sizes not increased. Re-run the `sysctl` commands from Phase 2. |
| VST web UI not loading on port 30080 | Start all jetson services manually (see Phase 4 commands). Use HTTP, not HTTPS. |
| RTSP stream not playing in VST | Verify RTSP URL has no leading spaces. Ensure NVStreamer container is still running. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with NVStreamer UI screenshots, VST configuration details, and NGC download instructions (reference only)
