---
name: dashcamnet-xavier-nx-multicamera
description: Deploy DashCamNet and PeopleNet pre-trained models on Jetson Xavier NX with multi-camera pipelines using DeepStream, TAO Toolkit, and jetson-multicamera-pipelines. Requires JetPack 4.5/4.6.
---

# DashCamNet & PeopleNet Multi-Camera on Xavier NX

Deploys NVIDIA pre-trained DashCamNet (vehicle detection) and PeopleNet (person detection)
models on Jetson Xavier NX with multi-camera support using DeepStream and the
jetson-multicamera-pipelines project. Achieves ~16.5% CPU for 6 camera streams.

Hardware: Jetson Xavier NX Dev Kit or Jetson SUB Mini PC, USB/CSI cameras, HDMI display
Software: JetPack 4.5 or 4.6, NGC account + API key

---

## Execution model

Run one phase at a time. After each phase:
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed

---

## Phase 1 — prerequisites check (~30 s)

```bash
sudo apt-cache show nvidia-jetpack
# Confirm JetPack 4.5 or 4.6
```

```bash
ls /dev/video*
# Confirm cameras connected
```

`[OK]` when JetPack 4.5/4.6 confirmed and cameras detected.

---

## Phase 2 — install Docker Engine (~5 min)

```bash
sudo apt-get purge docker docker-engine docker.io containerd runc
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io
```

Configure non-root access:
```bash
sudo groupadd docker
sudo usermod -aG docker $USER
```

Log out and back in, then verify:
```bash
docker run hello-world
```

`[OK]` when hello-world runs without sudo.

---

## Phase 3 — install NVIDIA Container Toolkit (~2 min)

```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
  && curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add - \
  && curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

`[OK]` when Docker restarts without errors.

---

## Phase 4 — install NGC CLI (~2 min)

```bash
wget -O ngccli_arm64.zip https://ngc.nvidia.com/downloads/ngccli_arm64.zip
unzip -o ngccli_arm64.zip
chmod u+x ngc
echo "export PATH=\"\$PATH:$(pwd)\"" >> ~/.bash_profile
source ~/.bash_profile
```

Generate an NGC API key at https://catalog.ngc.nvidia.com → Setup → Get API Key

```bash
ngc config set
# Enter API key when prompted
```

`[OK]` when `ngc` is configured.

---

## Phase 5 — install TAO Toolkit (~3 min)

```bash
sudo apt install -y python3 python3-pip
pip3 install virtualenv
virtualenv venv
source venv/bin/activate
pip3 install nvidia-pyindex
pip3 install nvidia-tao
```

Verify:
```bash
tao --help
```

If `tao` not found:
```bash
export PATH=$PATH:~/.local/bin
tao --help
```

`[OK]` when `tao --help` shows available tasks.

---

## Phase 6 — install DeepStream 5.1 (~3 min)

Edit apt sources to use r32.5:
```bash
sudo nano /etc/apt/sources.list.d/nvidia-l4t-apt-source.list
# Change r32.6 to r32.5 for both lines
```

```bash
sudo apt update
sudo -H pip3 install pyds-ext
```

`[OK]` when pyds-ext installs.

---

## Phase 7 — install multicamera pipelines (~5 min)

```bash
git clone https://github.com/NVIDIA-AI-IOT/jetson-multicamera-pipelines.git
cd jetson-multicamera-pipelines
bash scripts/install_dependencies.sh
sudo -H pip3 install Cython
sudo -H pip3 install .
```

`[OK]` when package installs without errors.

---

## Phase 8 — run multi-camera detection (~2 min)

```bash
source scripts/env_vars.sh
cd examples
sudo -H python3 example.py
```

Edit `example.py` to match your camera indices:
```python
pipeline = CameraPipelineDNN(
    cameras=[0, 1, 2],  # adjust to your camera device indices
    models=[
        PeopleNet.DLA1,
        DashCamNet.DLA0,
    ],
    save_video=True,
    save_video_folder="/home/$USER/logs/videos",
    display=True,
)
```

`[OK]` when multi-camera detection is running with overlays visible.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Docker install fails | Verify internet. Remove old Docker versions first. |
| `nvidia-docker2` install fails | Check NVIDIA apt sources are correct for your L4T version. |
| `tao` command not found | Run `export PATH=$PATH:~/.local/bin`. |
| DeepStream install fails | Verify apt sources point to r32.5. |
| `EGL Not found` error | Check EGLDevice setup. See NVIDIA EGL documentation. |
| Camera not detected in example.py | Check camera indices with `ls /dev/video*`. Adjust `cameras=[]` list. |
| Low FPS | Use DLA accelerators instead of GPU. Reduce camera count. |
| NGC API key error | Regenerate key at catalog.ngc.nvidia.com. |

---

## Reference files

- `references/source.body.md` — Original Seeed wiki with screenshots, NGC setup, and license plate detector example
