---
name: run-vlm
description: Deploy a Visual Language Model (VLM) AI service on Jetson using Jetson Platform Services (JPS). Requires reComputer J4012 (Orin NX 16GB), JetPack 6.0, and the vlm-1.1.0 package.
---

# VLM Deployment — Jetson Platform Services

Deploys a Vision Language Model service on Jetson via JPS (Jetson Platform Services).
VLMs support image, video, and text prompts using a combination of LLM and vision transformer.
10 GB swap is strongly recommended due to model memory requirements.

Hardware: reComputer J4012 (Orin NX 16GB), JetPack 6.0, Ubuntu 22.04
Package: `vlm-1.1.0.tar.gz`

Reference: `references/source.body.md` (Seeed wiki source, package download link)

---

## Execution model

Run **one phase at a time**. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase

---

## Phase 1 — add swap (~2 min)

Check current swap:
```bash
free -h
```

If swap is already ≥ 10 GB → skip to Phase 2.

Add a 10 GB swapfile:
```bash
sudo fallocate -l 10G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

Verify:
```bash
free -h
```

Expected: `Swap:` row shows ~10G total.
`[OK]`

---

## Phase 2 — extract VLM package (~1 min)

Confirm the package is present:
```bash
ls -lh vlm-1.1.0.tar.gz
```

If missing → `[STOP] package not found`. Download link is in `references/source.body.md`.

Extract and enter the directory:
```bash
tar -xzvf vlm-1.1.0.tar.gz
cd vlm
```

`[OK]` when `cd vlm` succeeds and `ls` shows `config/` and `docker-compose.yml`.

---

## Phase 3 — copy configs (~30 s)

```bash
sudo cp config/platform-nginx.conf /etc/nginx/conf.d/
sudo cp config/prometheus.yml /etc/prometheus/
```

Verify:
```bash
ls /etc/nginx/conf.d/platform-nginx.conf
ls /etc/prometheus/prometheus.yml
```

`[OK]` if both files are present.

---

## Phase 4 — start platform services (~2 min)

Start the 6 JPS services in order:
```bash
sudo systemctl start jetson-monitoring
sudo systemctl start jetson-sys-monitoring
sudo systemctl start jetson-redis
sudo systemctl start jetson-ingress
sudo systemctl start jetson-vst
sudo systemctl start jetson-platform-services
```

Verify all are running:
```bash
systemctl is-active jetson-monitoring jetson-sys-monitoring jetson-redis \
  jetson-ingress jetson-vst jetson-platform-services
```

Expected: `active` for each service. Any `failed` or `inactive` → `[STOP] service failed: <name>`.
`[OK]` when all 6 show `active`.

---

## Phase 5 — start VLM service (~3–5 min first run)

```bash
docker compose up -d
```

Monitor startup (first run pulls the container image):
```bash
docker compose logs -f
```

Wait until logs show the service is ready. Then open in a browser:
```
http://<jetson-ip>/vlm
```

`[OK]` when the VLM web UI loads.

---

## Failure decision tree

| Symptom | Action |
|---|---|
| `[STOP] package not found` | Download `vlm-1.1.0.tar.gz` from the link in `references/source.body.md` |
| `[STOP] service failed: <name>` | Run `sudo systemctl status <name>` and `journalctl -u <name> -n 50` for logs |
| `jetson-ingress` fails | nginx config error — run `sudo nginx -t` to validate; check Phase 3 copy succeeded |
| `docker compose up` fails — image pull error | Check internet connectivity: `ping registry-1.docker.io`. Retry `docker compose up -d` |
| `docker compose up` fails — port conflict | Another service is using port 80. Run `sudo ss -tlnp | grep :80` to identify it |
| OOM / container exits immediately | Swap not active. Re-run Phase 1. Check `free -h` shows 10G swap |
| Web UI loads but model hangs | First inference loads the model into memory (~2–3 min). Wait before retrying |
| Web UI unreachable | Confirm Jetson IP: `ip addr show`. Ensure host and Jetson are on the same network |
