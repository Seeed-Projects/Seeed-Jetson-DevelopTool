---
name: deploy-deepseek-mlc
description: Deploy DeepSeek on Jetson Orin using MLC (Machine Learning Compilation) for optimized edge inference. Uses Docker/jetson-containers. Requires Jetson with >8GB RAM and JetPack 5.1.1+.
---

# Deploy DeepSeek on Jetson with MLC

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
| Hardware | reComputer J4012 (Jetson Orin NX 16GB) or equivalent |
| RAM | >8 GB (16 GB recommended for DeepSeek-R1 7B+) |
| JetPack | 5.1.1+ (JetPack 6.x preferred) |
| Storage | SSD strongly recommended — model weights are large |
| Internet | Required for Docker pull and model download |

---

## Phase 1 — Preflight

Verify JetPack version, available RAM, and disk space before touching Docker.

```bash
cat /etc/nv_tegra_release
free -h
df -h /
df -h /ssd 2>/dev/null || true
```

Expected: L4T R35.x (JP5) or R36.x (JP6), ≥8 GB RAM free, ≥50 GB disk available. `[OK]` when all three pass. `[STOP]` if RAM or disk is insufficient.

---

## Phase 2 — Install Docker + nvidia-container

```bash
sudo apt update

# JetPack 5.x
sudo apt install -y nvidia-container

# JetPack 6.x — also install curl, then Docker
sudo apt install -y nvidia-container curl
curl https://get.docker.com | sh
sudo systemctl --now enable docker

# Add current user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

Verify:

```bash
docker --version
docker run --rm --runtime nvidia --gpus all ubuntu:22.04 nvidia-smi
```

Expected: `nvidia-smi` output shows the Jetson GPU. `[OK]` when GPU is visible inside the container.

### Move Docker storage to SSD (strongly recommended)

Edit `/etc/docker/daemon.json`:

```json
{
  "data-root": "/ssd/docker",
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  }
}
```

```bash
sudo systemctl restart docker
docker info | grep "Docker Root Dir"
```

`[OK]` when `Docker Root Dir` points to your SSD path.

---

## Phase 3 — Pull MLC container and download DeepSeek model

```bash
# JP5.x:
docker pull dustynv/mlc-llm:r35.4.1

# JP6.x:
docker pull dustynv/mlc-llm:r36.2.0

docker images | grep mlc-llm
```

Download model weights inside the container:

```bash
docker run -it --rm \
  --runtime nvidia \
  --network host \
  -v /ssd/models:/models \
  dustynv/mlc-llm:r36.2.0 \
  bash -c "huggingface-cli download deepseek-ai/DeepSeek-R1-Distill-Qwen-7B --local-dir /models/deepseek-r1-7b"
```

`[OK]` when model files are present under `/ssd/models/`. `[STOP]` if download fails — see failure decision tree.

---

## Phase 4 — Launch inference

```bash
docker run -it --rm \
  --runtime nvidia \
  --network host \
  -v /ssd/models:/models \
  dustynv/mlc-llm:r36.2.0 \
  python3 -m mlc_llm serve /models/deepseek-r1-7b \
    --device cuda \
    --host 0.0.0.0 \
    --port 8080
```

Test the endpoint:

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-r1-7b","messages":[{"role":"user","content":"Hello"}]}'
```

`[OK]` when the API returns a JSON response with a completion.

> For full step-by-step commands, screenshots, and model configuration options, read `references/source.body.md`.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `docker: command not found` | Re-run the `curl https://get.docker.com \| sh` step. Confirm `sudo systemctl enable --now docker`. |
| `nvidia-container` install fails | Confirm JetPack version with `cat /etc/nv_tegra_release`. JP5 and JP6 have different package names — check `references/source.body.md` for the exact apt source. |
| `nvidia-smi` not visible inside container | nvidia-container-runtime not configured. Verify `/etc/docker/daemon.json` has the `nvidia` runtime entry and restart Docker. |
| OOM / killed during inference | Model too large for available RAM. Try a smaller distill variant (1.5B or 7B). Ensure no other heavy processes are running. |
| Model download fails / times out | Check internet connectivity. Retry with `huggingface-cli download --resume-download`. If HuggingFace is blocked, use a mirror or pre-download on another machine. |
| `docker pull` fails with no space | Docker root is on eMMC. Move Docker data root to SSD (Phase 2 SSD step). |
| Inference endpoint returns 500 | Model path inside container may be wrong. Verify the `-v` mount and the path passed to `mlc_llm serve`. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with complete MLC configuration, model options, and effect demonstration (reference only)
