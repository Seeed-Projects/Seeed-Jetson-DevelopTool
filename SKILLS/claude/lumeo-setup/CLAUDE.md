---
name: lumeo-setup
description: Install and configure Lumeo no-code video analytics gateway on NVIDIA Jetson. Covers account creation, gateway deployment, camera linking, and building a people detection pipeline. Requires Jetson with JetPack 5.1+ and internet access.
---

# Getting Started with Lumeo on NVIDIA Jetson

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
| Hardware | NVIDIA Jetson device (tested on reComputer J4012) |
| JetPack | 5.1+ with all SDK components installed |
| Internet | Required on both Jetson and host PC |
| Host PC | Windows, Linux, or Mac with browser access |
| Lumeo account | Free account at https://console.lumeo.com/register |

---

## Phase 1 — Preflight

Verify JetPack version and network connectivity.

```bash
cat /etc/nv_tegra_release
ping -c 3 lumeo.com
```

Expected: L4T version shown, ping succeeds. `[OK]` when both pass. `[STOP]` if no network.

---

## Phase 2 — Create Lumeo account (manual)

1. Visit https://console.lumeo.com/register — sign up with email and password.
2. Sign in at https://console.lumeo.com/login.
3. Enter an organization name and workspace name, click "Start using Lumeo".
4. Delete the default cloud gateway under Gateways (free accounts allow only one gateway).

`[OK]` when Lumeo console is accessible and default cloud gateway is deleted.

---

## Phase 3 — Install Lumeo Gateway on Jetson

Run the installer script on the Jetson device:

```bash
bash <(wget -qO- https://link.lumeo.com/setup)
```

Respond to prompts (defaults are fine). When the installer completes successfully, type `install` at the prompt to deploy a new gateway container:

```
Enter the command: install
```

Enter a container name and log in with your Lumeo credentials when prompted.

Verify the container is running:

```
Enter the command: list
```

Type `exit` to quit the script.

```bash
# Verify gateway appears in Lumeo console under Gateways
```

`[OK]` when the gateway shows as online in the Lumeo console. `[STOP]` if installer fails or gateway does not appear.

---

## Phase 4 — Add cameras to the gateway

1. Connect a USB camera to the Jetson or ensure an ONVIF camera is on the same network.
2. In Lumeo console, click "Add Camera" under your gateway.
3. Click "Link" next to a discovered camera (or "Manually add cameras" if auto-discovery fails).
4. Enter camera name, provide credentials if needed, click "Connect camera".
5. Click the linked camera to verify a preview snapshot appears.

For RTSP/HTTP streams: navigate to Deploy > Streams, click "Add input stream".

`[OK]` when camera preview is visible in the Lumeo console.

---

## Phase 5 — Build a people detection pipeline

1. In Lumeo console, go to Design > Solutions, select "Basics - Detect Objects".
2. Keep default blocks (people detection model, tracker, WebRTC encoder) and click "Deploy".
3. Select your Jetson gateway, choose the configured camera, click "Deploy".
4. Wait for a green "running" status indicator.
5. Click the play button to view the output stream via WebRTC.

`[OK]` when the live detection stream is visible with bounding boxes.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Installer script fails to download | Check internet: `ping -c 3 link.lumeo.com`. Verify `wget` is installed: `sudo apt install wget`. |
| Gateway not appearing in console | Ensure the default cloud gateway was deleted first (free tier limit). Re-run installer if needed. |
| Camera not discovered | Click "Discover" again. For USB cameras, check `ls /dev/video*`. For ONVIF, verify same network/subnet. |
| Pipeline deployment fails | Check gateway is online (green status). Verify camera is linked and producing preview snapshots. |
| WebRTC stream not loading | Try a different browser (Chrome recommended). Check Jetson network firewall rules. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with screenshots, camera setup details, and pipeline configuration (reference only)
