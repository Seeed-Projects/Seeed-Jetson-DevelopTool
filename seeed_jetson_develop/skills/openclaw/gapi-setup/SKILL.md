---
name: gapi-setup
description: Deploy Gapi embeddable API gateway on Jetson Orin for streaming AI micro service integrations. Covers Docker-based installation, workflow engine setup, and community micro services. Requires any Jetson Orin with Docker and 1.3GB storage.
---

# Getting Started with Gapi on Jetson

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
| Hardware | Any NVIDIA Jetson Orin |
| Software | Docker installed and running |
| Storage | ≥1.3 GB for Gapi server |
| Network | Required for Docker pull and web access |

---

## Phase 1 — Install Gapi server (~5 min)

```bash
mkdir ~/gapiData && cd ~/gapiData
curl -L https://raw.githubusercontent.com/genai-nerds/Gapi/main/gapiConfigs.zip -o gapiConfigs.zip
unzip -q gapiConfigs.zip
docker run -d --name gapi --network host -v ~/gapiData:/opt/gapi/vdata genainerds/gapi:arm64 /bin/bash -c "cd /opt/gapi/bin && ./startGapi.sh"
```

Verify the container is running:

```bash
docker ps | grep gapi
```

`[OK]` when the `gapi` container is listed as running. `[STOP]` if Docker pull or container start fails.

---

## Phase 2 — Log in to Gapi WebUI (~1 min)

Open a browser and navigate to:

```
http://<jetson-ip>:8090
```

Default credentials:
- User: `root`
- Password: `!gapi2024`

Change the password in Settings after first login. SSL cert setup is covered in the Gapi docs.

`[OK]` when you can log in and see the Gapi dashboard.

---

## Phase 3 — Explore workflows and micro services

Workflows visually connect Nodes that talk to Micro Services and APIs. Each Node can append or reference rolling Transaction data.

To set up Community Micro Services:
1. Go to the Micro Services tab in the Gapi UI
2. Follow the instructions in the blue box to download your custom configuration
3. Follow the per-service install instructions below that

Community Micro Service storage requirements: ~4 GB to ~10 GB each.

`[OK]` when at least one micro service is connected and visible in the UI.

> For workflow tips, micro service architecture details, and custom on_message handlers, see `references/source.body.md`.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `docker: command not found` | Install Docker: `curl https://get.docker.com \| sh && sudo systemctl enable --now docker` |
| Docker pull fails | Check internet connectivity. Verify Docker daemon is running with `sudo systemctl status docker`. |
| Container exits immediately | Check logs: `docker logs gapi`. Ensure `~/gapiData` contains the unzipped config files. |
| Cannot access port 8090 | Verify container is running with `docker ps`. Check firewall. Try `http://localhost:8090` from the Jetson itself. |
| Login fails | Use default credentials `root` / `!gapi2024`. Clear browser cache if needed. |
| Micro service won't connect | Ensure the micro service container has network access. Check the streaming websocket connection in logs. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with workflow diagrams, micro service architecture, and integration details (reference only)
