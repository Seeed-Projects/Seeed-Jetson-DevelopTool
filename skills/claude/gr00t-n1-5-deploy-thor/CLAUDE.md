---
name: gr00t-n1-5-deploy-thor
description: Fine-tune NVIDIA Isaac GR00T N1.5 for the LeRobot SO-101 arm and deploy on Jetson AGX Thor. Covers Thor flashing, dev environment setup, SO-ARM data collection, cloud training via NVIDIA Brev, and GR00T N1.5 inference on Thor. Requires Jetson AGX Thor and SO-101 arm hardware.
---

# Fine-tune GR00T N1.5 for LeRobot SO-101 Arm and Deploy on Jetson Thor

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
| Hardware | NVIDIA Jetson AGX Thor Developer Kit |
| Robot arm | LeRobot SO-101 (leader + follower) |
| Cameras | 2× USB cameras (wrist + front) |
| Flashing | USB drive ≥16GB, monitor, DP/HDMI cable, 240W+ power, USB keyboard |
| Cloud training | GPU with ≥25GB VRAM (Ampere or newer — V100 not supported) |
| System image | Thor v38.2 (latest as of Sept 2025) |

---

## Phase 1 — Flash Thor system image (~20 min)

Download the ISO image from https://developer.nvidia.com/embedded/jetpack/downloads (select Thor 38.2).

Create bootable USB with Balena Etcher (https://etcher.balena.io/):
1. Select the ISO image
2. Select the USB drive as target
3. Click Flash and wait for completion

Insert USB, keyboard, display cable, and power into Thor. Boot and select:
- `Boot Manager` → select USB drive → `Esc` → `Continue`
- `Jetson Thor options` → `Flash Jetson AGX Thor Developer Kit on NVMe`

Wait ~15 minutes for flashing, then wait for Update Progress to reach 100%.

`[OK]` when Ubuntu 24.04 initial setup screen appears. `[STOP]` if screen goes black — see FAQ in source.

---

## Phase 2 — Install development dependencies (~10–20 min)

Install JetPack SDK:

```bash
sudo apt update
sudo apt install nvidia-jetpack
```

Install additional tools:

```bash
sudo apt install firefox python3 python3-pip
sudo pip3 install -U pip
sudo pip3 install jetson-stats
```

Install Miniconda:

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
chmod +x Miniconda3-latest-Linux-aarch64.sh
./Miniconda3-latest-Linux-aarch64.sh
source ~/.bashrc
conda --version
```

For GPU PyTorch on Thor, download pre-compiled wheels (Python 3.10 + CUDA 13):
- PyTorch 2.9 and TorchVision 0.24 wheels from Seeed SharePoint links in `references/source.body.md`
- Additional wheels at https://pypi.jetson-ai-lab.io/sbsa/cu130

`[OK]` when `conda --version` and `python3 -c "import torch; print(torch.cuda.is_available())"` both succeed.

---

## Phase 3 — Data collection with SO-ARM

Follow the complete SO-ARM tutorial at:
https://wiki.seeedstudio.com/lerobot_so100m_new/

Key steps:
1. Configure motors before assembly
2. Assemble leader and follower arms
3. Calibrate both arms (do NOT connect cameras during calibration)
4. Add cameras (wrist + front)
5. Record dataset episodes

> On Thor, two USB cameras must be on different USB hub controllers. Use one USB-A port and one external USB-C hub.

`[OK]` when dataset is collected and saved locally.

---

## Phase 4 — Train GR00T N1.5 on cloud (~varies)

Set up NVIDIA Brev (https://login.brev.nvidia.com/signin) or equivalent cloud GPU.

On the cloud server, install Conda and clone Isaac-GR00T:

```bash
mkdir -p ~/miniconda3 && cd ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
bash miniconda.sh -b -u -p ~/miniconda3
source ~/miniconda3/bin/activate
conda init --all
```

```bash
git clone https://github.com/NVIDIA/Isaac-GR00T
cd Isaac-GR00T
conda create -n gr00t python=3.10
conda activate gr00t
pip install --upgrade setuptools
pip install -e .[base]
pip install --no-build-isolation flash-attn==2.7.1.post4
```

Fine-tune:

```bash
python scripts/gr00t_finetune.py \
   --dataset-path ./demo_data/so101-table-cleanup/ \
   --num-gpus 1 \
   --output-dir ./so101-checkpoints \
   --max-steps 10000 \
   --data-config so100_dualcam \
   --video-backend torchvision_av
```

> Default fine-tuning requires ~25GB VRAM. Add `--no-tune_diffusion_model` to reduce VRAM usage.

Download the trained checkpoint from the cloud server.

`[OK]` when checkpoint files are available locally on Thor.

---

## Phase 5 — Run GR00T N1.5 inference on Thor

Pull the reference Docker image (or use your own environment):

```bash
docker pull johnnync/isaac-gr00t:r38.2.arm64-sbsa-cu130-24.04
```

Start the container:

```bash
sudo docker run --rm -it \
  --network=host \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,video,graphics \
  --runtime nvidia \
  --privileged \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /etc/X11:/etc/X11 \
  --device /dev/nvhost-vic \
  -v /dev:/dev \
  johnnync/isaac-gr00t:r38.2.arm64-sbsa-cu130-24.04
```

Inside the container, install GR00T:

```bash
git clone https://github.com/NVIDIA/Isaac-GR00T.git
cd Isaac-GR00T
pip install --upgrade setuptools
pip install -e .[thor]
```

Terminal 1 — Start inference server:

```bash
python scripts/inference_service.py --server \
    --model_path ./so101-checkpoints \
    --embodiment-tag new_embodiment \
    --data-config so100_dualcam \
    --denoising-steps 4
```

Terminal 2 — Start inference client (in same container via `docker exec`):

```bash
python examples/SO-100/eval_lerobot.py \
    --robot.type=so100_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=my_awesome_follower_arm \
    --robot.cameras="{ wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, front: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}}" \
    --policy_host=0.0.0.0 \
    --lang_instruction="Grab pens and place into pen holder."
```

Replace `index_or_path` with your camera indices (find with `ls /dev/video*`).

`[OK]` when the robot arm executes the learned behavior.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Thor screen goes black during flash | Enable SoC Display Hand-Off in UEFI setup menu. Flashing continues in background. |
| No HDMI signal after flash | Switch to DisplayPort (DP) connector. |
| No keyboard input during flash | Use a wired USB keyboard. Wireless keyboards may not work. |
| KVM no video output | Connect monitor directly to Thor, bypassing KVM. |
| Cloud fine-tuning "GPU not supported" | Use Ampere or newer GPU (RTX A6000, RTX 4090). V100 is not supported. |
| `/dev/ttyACM0` not found for arm | Thor may lack CH34x drivers. Install from https://github.com/juliagoda/CH341SER |
| Type-C hub not recognized | Use the Type-C port closest to the QSFP28 connector. |
| OOM during fine-tuning | Add `--no-tune_diffusion_model` flag. Or use a GPU with more VRAM. |
| Two USB cameras can't stream simultaneously | Cameras must be on different USB hub controllers. Use USB-A + external USB-C hub. |
| ACT inference fails in GR00T Docker image | The GR00T Docker image (Python 3.12) doesn't support LeRobot ACT inference. Use external environment. |
| User password incorrect after flash with capture card | Keyboard input bug with capture cards. Re-flash and verify password carefully. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with Thor flashing screenshots, Docker image pip list, Brev platform walkthrough, and FAQ (reference only)
