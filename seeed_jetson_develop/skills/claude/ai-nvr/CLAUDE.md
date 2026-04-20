---
name: ai-nvr
description: Deploy a local AI NVR (Network Video Recorder) on Jetson Orin using NVIDIA VST and Jetson Platform Services with DeepStream pedestrian detection. Requires Jetson Orin with JetPack 6.0 and an IP camera.
---

# AI NVR with Jetson Orin

Deploys a local AI NVR using NVIDIA VST and Jetson Platform Services.
DeepStream performs pedestrian detection; results display alongside the original
video stream on the VST video wall.

Hardware: Jetson Orin device (e.g. reServer Industrial J4012), IP camera, network
Software: JetPack 6.0 (L4T r36.3)

---

## Execution model

Run one phase at a time. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed

---

## Phase 1 — prerequisites check (~30 s)

Confirm JetPack 6.0:
```bash
cat /etc/nv_tegra_release
# Expected: R36 (release), REVISION: 3.0
```

Confirm IP camera is reachable:
```bash
ping -c 2 <CAMERA_IP>
```

`[OK]` when JetPack 6.0 confirmed and camera responds.
`[STOP]` if JetPack version is wrong or camera unreachable.

---

## Phase 2 — install Jetson Platform Services (~2 min)

```bash
sudo apt update
sudo apt install -y nvidia-jetson-services
```

Verify services are available:
```bash
ls /opt/nvidia/jetson/services/
```

Expected: directories including `ingress/`, `vst/`, etc.
`[OK]`

---

## Phase 3 — configure ingress & storage (~1 min)

Create the AI NVR nginx config:
```bash
sudo tee /opt/nvidia/jetson/services/ingress/config/ai-nvr-nginx.conf > /dev/null << 'EOF'
location /emdx/ {
    rewrite ^/emdx/?(.*)$ /$1 break;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    access_log /var/log/nginx/access.log timed_combined;
    proxy_pass http://emdx_api;
}

location /ws-emdx/ {
    rewrite ^/ws-emdx/?(.*)$ /$1 break;
    proxy_set_header Host $host;
    proxy_pass http://emdx_websocket;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
EOF
```

(Optional) Modify VST storage path:
```bash
sudo nano /opt/nvidia/jetson/services/vst/config/vst_storage.json
# Change data_path and video_path as needed
```

`[OK]`

---

## Phase 4 — start VST services (~1 min)

```bash
sudo systemctl start jetson-redis
sudo systemctl start jetson-ingress
sudo systemctl start jetson-vst
```

Verify containers are running:
```bash
sudo docker ps
```

Verify web UI is accessible at `http://<JETSON_IP>:81/`

`[OK]` when VST web UI loads.

---

## Phase 5 — download & configure AI NVR (~5 min)

Download the AI NVR package from NGC:
https://catalog.ngc.nvidia.com/orgs/nvidia/teams/jps/resources/reference-workflow-and-resources

Extract:
```bash
cd <DOWNLOAD_PATH>
unzip files.zip
cd files
tar -xvf ai_nvr-1.1.0.tar.gz
cd ai_nvr
```

Modify DeepStream config for RTSP output. Select the correct config for your module:
- Orin NX 16GB: `config/deepstream/pn26/service-maker/ds-config-0_nx16.yaml`
- Orin AGX / NX8 / Nano: use the corresponding file

Add RTSP sink to the DeepStream YAML (replace the existing sink section with `nvrtspoutsinkbin` on port 8555).

Add the WDM environment variable in the compose file:
```yaml
WDM_WL_NAME_IGNORE_REGEX: ".*deepstream.*"
```

`[OK]` when config files are modified.

---

## Phase 6 — launch AI NVR (~3 min)

Select the correct compose file for your Jetson module:
```bash
cd <DOWNLOAD_PATH>/files/ai_nvr

# Orin AGX:
# sudo docker compose -f compose_agx.yaml up -d --force-recreate
# Orin NX 16GB:
sudo docker compose -f compose_nx16.yaml up -d --force-recreate
# Orin NX 8GB:
# sudo docker compose -f compose_nx8.yaml up -d --force-recreate
# Orin Nano:
# sudo docker compose -f compose_nano.yaml up -d --force-recreate
```

Verify all containers are running:
```bash
sudo docker ps
```

`[OK]` when DeepStream and other AI NVR containers appear.

---

## Phase 7 — configure cameras via web UI (~2 min)

Open browser: `http://<JETSON_IP>:30080/vst/`

Add cameras manually:
- Sensor Management → Add device manually → enter IP camera RTSP URL → Submit
- Add DeepStream output stream: `rtsp://<JETSON_IP>:8555/ds-test`
  (camera name MUST contain the word "deepstream")

View results: Video Wall → Select All → Start

`[OK]` when video wall shows camera feeds with AI detection overlays.

---

## Shutdown

```bash
cd <DOWNLOAD_PATH>/files/ai_nvr
sudo docker compose -f compose_nx16.yaml down --remove-orphans
sudo systemctl stop jetson-vst
sudo systemctl stop jetson-ingress
sudo systemctl stop jetson-redis
```

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `apt install nvidia-jetson-services` fails | Confirm JetPack 6.0 is installed. Run `sudo apt update` first. |
| VST web UI not loading on port 81 | Check `sudo systemctl status jetson-vst`. Verify firewall allows port 81. |
| Docker compose fails | Verify Docker + nvidia-container-runtime installed. Check disk space. |
| DeepStream container exits immediately | Check `sudo docker logs <container>`. Verify correct compose file for your module. |
| No detection overlay on video wall | Confirm DeepStream config has RTSP sink on port 8555. Camera name must contain "deepstream". |
| Camera not visible in VST | Verify camera RTSP URL is correct and reachable from Jetson. |

---

## Reference files

- `references/source.body.md` — Original Seeed wiki with screenshots and detailed config examples
