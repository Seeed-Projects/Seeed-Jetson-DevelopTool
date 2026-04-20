---
name: jetson-docker-setup
description: Set up Docker on Seeed reComputer Jetson devices — verify Docker and CUDA, install Docker Compose, run containers with GPU access, and monitor with JTOP. Based on reComputer J1020 (Jetson Nano).
---

# Getting Started with Docker on Jetson

Set up and use Docker on Seeed reComputer Jetson devices. Docker comes
pre-installed on reComputer. This skill covers verification, Docker Compose
installation, CUDA testing, and GPU-enabled container workflows.

Hardware: reComputer J1020 (Jetson Nano) or compatible Jetson device
Software: JetPack 4.6+ (Docker pre-installed)

---

## Execution model

Run one phase at a time. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed

---

## Phase 1 — verify Docker installation (~30 s)

```bash
sudo docker version
```

Expected: Docker Engine 20.10+ with `OS/Arch: linux/arm64`.

```bash
docker info | grep -i runtime
```

Expected: `nvidia` should appear in the runtimes list.

`[OK]` when Docker is running and nvidia runtime is available.
`[STOP]` if Docker is not installed or nvidia runtime missing.

---

## Phase 2 — verify CUDA (~1 min)

```bash
cd /usr/local/cuda/samples/1_Utilities/deviceQuery
sudo make
./deviceQuery
```

Expected: `Result = PASS` with device info (e.g. "NVIDIA Tegra X1").

`[OK]` when CUDA deviceQuery passes.

---

## Phase 3 — install Docker Compose (~2 min)

```bash
export DOCKER_COMPOSE_VERSION=2.6.0
sudo apt-get install -y libhdf5-dev libssl-dev
sudo pip3 install docker-compose=="${DOCKER_COMPOSE_VERSION}"
```

If pip3 is not available:
```bash
sudo apt-get install -y python3 python3-pip
pip install docker-compose
```

`[OK]` when `docker-compose --version` returns successfully.

---

## Phase 4 — install CUDA toolkit (optional, ~5 min)

Only needed if upgrading CUDA beyond the pre-installed version:

```bash
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/sbsa/cuda-ubuntu1804.pin
sudo mv cuda-ubuntu1804.pin /etc/apt/preferences.d/cuda-repository-pin-600
wget https://developer.download.nvidia.com/compute/cuda/11.3.1/local_installers/cuda-repo-ubuntu1804-11-3-local_11.3.1-465.19.01-1_arm64.deb
sudo dpkg -i cuda-repo-ubuntu1804-11-3-local_11.3.1-465.19.01-1_arm64.deb
sudo apt-key add /var/cuda-repo-ubuntu1804-11-3-local/7fa2af80.pub
sudo apt-get update
sudo apt-get -y install cuda
```

`[OK]` when CUDA installs without errors.

---

## Phase 5 — run a test container (~1 min)

```bash
sudo docker run arm64v8/python:slim python3 -c "print('Hello from Jetson Docker!')"
```

`[OK]` when the container runs and prints output.

---

## Phase 6 — set up JTOP monitoring container (optional, ~3 min)

Create a Dockerfile:
```dockerfile
FROM python:3-alpine
RUN apk update \
    && apk --no-cache add bash \
    && pip install jetson-stats \
    && rm -rf /var/cache/apk/*
```

Build and run:
```bash
docker build -t jetson-stats-nano .
docker run --rm -it --gpus all -v /run/jtop.sock:/run/jtop.sock jetson-stats-nano jtop
```

`[OK]` when JTOP displays CPU/GPU/memory stats.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Docker not found | Install: `sudo apt-get install -y docker.io`. Reboot and retry. |
| nvidia runtime not listed | Install nvidia-container-runtime: `sudo apt-get install -y nvidia-container-runtime`. Restart Docker. |
| CUDA deviceQuery fails to compile | Ensure CUDA samples are installed: `sudo apt-get install -y cuda-samples-*`. |
| Docker Compose install fails | Check Python version (`python3 --version`). Try `pip3 install --upgrade pip` first. |
| Container can't access GPU | Use `--gpus all` flag. Verify nvidia runtime with `docker info`. |
| JTOP socket error | Ensure `jtop` service is running on host: `sudo systemctl start jtop`. |

---

## Reference files

- `references/source.body.md` — Original blog post with hardware details, screenshots, and application examples
