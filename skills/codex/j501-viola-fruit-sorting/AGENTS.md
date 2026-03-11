---
name: j501-viola-fruit-sorting
description: Build a fruit sorting system using J501 Mini (Jetson AGX Orin) with StarAI Viola robotic arm and LeRobot framework. Covers environment setup, arm calibration, teleoperation, data collection, ACT policy training, and autonomous deployment. Requires JetPack 6.2.1.
---

# Fruit Sorting with J501 Mini and StarAI Viola Arm

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
| Compute | J501 Mini with Jetson AGX Orin module, JetPack 6.2.1 |
| Arms | StarAI Viola follower (6+1 DoF) + StarAI Violin leader (6+1 DoF) |
| Cameras | 2× USB cameras (640×480 @ 30fps, MJPG) — wrist + front |
| Power | 12V 10A for each arm |
| Accessories | UC-01 debugging boards (×2), USB cables, fruits for sorting |

---

## Phase 1 — Install software environment (~15–30 min)

Install Miniconda:

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
chmod +x Miniconda3-latest-Linux-aarch64.sh
./Miniconda3-latest-Linux-aarch64.sh
source ~/.bashrc
```

Create LeRobot environment:

```bash
conda create -y -n lerobot python=3.10 && conda activate lerobot
git clone https://github.com/Seeed-Projects/lerobot.git ~/lerobot
cd ~/lerobot
conda install ffmpeg -c conda-forge
```

Install PyTorch GPU version for Jetson following: https://github.com/Seeed-Projects/reComputer-Jetson-for-Beginners/tree/main/3-Basic-Tools-and-Getting-Started/3.5-Pytorch

Then install LeRobot and fix dependencies for JetPack 6.0+:

```bash
cd ~/lerobot && pip install -e .

conda install -y -c conda-forge "opencv>=4.10.0.84"
conda remove opencv
pip3 install opencv-python==4.10.0.84
conda install -y -c conda-forge ffmpeg
conda uninstall numpy
pip3 install numpy==1.26.0
```

Install StarAI motor dependencies:

```bash
pip install lerobot_teleoperator_bimanual_leader
pip install lerobot_robot_bimanual_follower
```

Verify PyTorch GPU:

```python
import torch
print(torch.cuda.is_available())  # Must print True
```

If False, reinstall PyTorch GPU version per the Jetson tutorial above.

Remove brltty if it causes USB conflicts:

```bash
sudo apt remove brltty
```

`[OK]` when `torch.cuda.is_available()` returns True.

---

## Phase 2 — Hardware setup and calibration (~10–15 min)

Find USB ports:

```bash
cd ~/lerobot
lerobot-find-port
```

Grant access:

```bash
sudo chmod 666 /dev/ttyUSB*
```

Calibrate leader arm (move each joint to max/min positions):

```bash
lerobot-calibrate \
    --teleop.type=lerobot_teleoperator_violin \
    --teleop.port=/dev/ttyUSB0 \
    --teleop.id=my_violin_leader
```

Calibrate follower arm:

```bash
lerobot-calibrate \
    --robot.type=lerobot_robot_viola \
    --robot.port=/dev/ttyUSB1 \
    --robot.id=my_viola_follower
```

Find camera ports:

```bash
lerobot-find-cameras opencv
```

Mount wrist camera on gripper, front camera on desktop.

`[OK]` when both arms are calibrated and cameras are detected.

---

## Phase 3 — Teleoperation test (~5 min)

```bash
lerobot-teleoperate \
    --robot.type=lerobot_robot_viola \
    --robot.port=/dev/ttyUSB1 \
    --robot.id=my_viola_follower \
    --robot.cameras="{ wrist: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30, fourcc: 'MJPG'}, front: {type: opencv, index_or_path: /dev/video4, width: 640, height: 480, fps: 30, fourcc: 'MJPG'}}" \
    --teleop.type=lerobot_teleoperator_violin \
    --teleop.port=/dev/ttyUSB0 \
    --teleop.id=my_violin_leader \
    --display_data=true
```

> Camera names MUST be `wrist` and `front` for ACT model training.

`[OK]` when follower arm mirrors leader arm movements and camera feeds display.

---

## Phase 4 — Collect fruit sorting data (~30–60 min)

(Optional) Login to Hugging Face:

```bash
huggingface-cli login --token ${HUGGINGFACE_TOKEN} --add-to-git-credential
HF_USER=$(huggingface-cli whoami | head -n 1)
```

Record 50 episodes:

```bash
lerobot-record \
    --robot.type=lerobot_robot_viola \
    --robot.port=/dev/ttyUSB1 \
    --robot.id=my_viola_follower \
    --robot.cameras="{ wrist: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30, fourcc: 'MJPG'}, front: {type: opencv, index_or_path: /dev/video4, width: 640, height: 480, fps: 30, fourcc: 'MJPG'}}" \
    --teleop.type=lerobot_teleoperator_violin \
    --teleop.port=/dev/ttyUSB0 \
    --teleop.id=my_violin_leader \
    --display_data=true \
    --dataset.repo_id=${HF_USER}/fruit_sorting \
    --dataset.episode_time_s=30 \
    --dataset.reset_time_s=30 \
    --dataset.num_episodes=50 \
    --dataset.push_to_hub=true \
    --dataset.single_task="Sort fruits into containers"
```

Keyboard controls: → skip episode, ← re-record, ESC stop and save.

`[OK]` when 50 episodes are recorded.

---

## Phase 5 — Train ACT policy (~8–20 hours)

```bash
lerobot-train \
    --dataset.repo_id=${HF_USER}/fruit_sorting \
    --policy.type=act \
    --output_dir=outputs/train/fruit_sorting_act \
    --job_name=fruit_sorting_act \
    --policy.device=cuda \
    --wandb.enable=false \
    --policy.repo_id=${HF_USER}/fruit_sorting_policy \
    --steps=100000 \
    --batch_size=8 \
    --eval.batch_size=8 \
    --eval.n_episodes=10 \
    --eval_freq=5000
```

To resume interrupted training:

```bash
lerobot-train \
    --config_path=outputs/train/fruit_sorting_act/checkpoints/last/pretrained_model/train_config.json \
    --resume=true \
    --steps=200000
```

`[OK]` when training completes and checkpoint is saved.

---

## Phase 6 — Deploy and evaluate

Run evaluation with the trained model:

```bash
lerobot-record \
    --robot.type=lerobot_robot_viola \
    --robot.port=/dev/ttyUSB1 \
    --robot.id=my_viola_follower \
    --robot.cameras="{ wrist: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30, fourcc: 'MJPG'}, front: {type: opencv, index_or_path: /dev/video4, width: 640, height: 480, fps: 30, fourcc: 'MJPG'}}" \
    --display_data=false \
    --dataset.repo_id=${HF_USER}/eval_fruit_sorting \
    --dataset.single_task="Sort fruits into containers" \
    --dataset.num_episodes=10 \
    --policy.path=outputs/train/fruit_sorting_act/checkpoints/last/pretrained_model
```

`[OK]` when the robot autonomously sorts fruits into containers.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| USB port not detected | Run `sudo apt remove brltty`. Check with `lsusb` and `sudo dmesg \| grep ttyUSB`. Grant permissions with `sudo chmod 777 /dev/ttyUSB*`. |
| Camera not working | Don't use USB hub. Connect cameras directly. Re-check with `lerobot-find-cameras opencv`. |
| `torch.cuda.is_available()` returns False | pip installs CPU PyTorch. Reinstall GPU version per Jetson tutorial. |
| Training OOM | Reduce `--batch_size=4`. Close other applications. Reduce image resolution. |
| Keyboard controls don't work during recording | Install `pip install pynput==1.6.8`. |
| Poor inference performance | Collect more data (100–200 episodes). Ensure consistent lighting and camera angles. Verify calibration. |
| Arm movements are jerky | Re-calibrate arms. Ensure each joint reached full range during calibration. |
| Camera names mismatch | ACT model requires `wrist` and `front`. Re-collect data with correct names or modify source code. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with hardware photos, calibration images, training parameters, troubleshooting details, and demo video (reference only)
