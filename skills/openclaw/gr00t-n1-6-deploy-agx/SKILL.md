---
name: gr00t-n1-6-deploy-agx
description: Fine-tune NVIDIA Isaac GR00T N1.6 for the LeRobot SO-101 arm and deploy on AGX Orin 64G. Covers environment setup on AGX Orin and fine-tuning server, SO-ARM data collection, dataset format conversion, L20 GPU training, and inference deployment. Requires JetPack 6.2 and ≥48GB VRAM for fine-tuning.
---

# Fine-tune GR00T N1.6 for LeRobot SO-101 Arm and Deploy on AGX Orin

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
| Inference device | AGX Orin 64G with JetPack 6.2 |
| Robot arm | LeRobot SO-101 (leader + follower) |
| Cameras | 2× USB cameras (named `wrist` and `front`) |
| Fine-tuning server | GPU with ≥48GB VRAM (L20 recommended, server rental OK) |
| Tools | `uv` package manager, Python 3.10 |

---

## Phase 1 — Set up GR00T N1.6 environment on AGX Orin (~15–30 min)

Clone and checkout the specific commit:

```bash
git clone https://github.com/NVIDIA/Isaac-GR00T.git
cd Isaac-GR00T
git checkout d483f00b1c13116bda020bead9d16dca497b2f6d
git submodule update --init --recursive
```

Create virtual environment and install LeRobot dependencies:

```bash
uv venv .venv --python python3.10
source .venv/bin/activate

cd gr00t/eval/real_robot/SO100
uv pip install -e . --verbose
uv pip install --no-deps -e ../../../../
```

Download pre-compiled `.whl` files for AGX Orin (PyTorch, TorchVision, Flash-Attention, TorchCodec, Triton) from links in `references/source.body.md`. More wheels at https://pypi.jetson-ai-lab.io/jp6/cu126

Install wheels (flash-attn and torchvision must be installed AFTER pytorch):

```bash
source .venv/bin/activate
pip install torch-*.whl
pip install flash_attn-*.whl torchvision-*.whl torchcodec-*.whl triton-*.whl
```

Complete final dependency installation:

```bash
cd Isaac-GR00T
source .venv/bin/activate
pip install -e .[base]
sudo apt update && sudo apt install ffmpeg
```

`[OK]` when `python -c "import torch; print(torch.cuda.is_available())"` returns `True`.

---

## Phase 2 — Set up environment on fine-tuning server (~10–20 min)

```bash
git clone https://github.com/NVIDIA/Isaac-GR00T.git
cd Isaac-GR00T
git checkout d483f00b1c13116bda020bead9d16dca497b2f6d
git submodule update --init --recursive
```

```bash
uv venv .venv --python python3.10
source .venv/bin/activate

cd gr00t/eval/real_robot/SO100
uv pip install -e . --verbose
uv pip install --no-deps -e ../../../../
```

Install PyTorch for your server's CUDA version (find commands at https://pytorch.org/get-started/previous-versions/):

```bash
source .venv/bin/activate
# Example for CUDA 12.8:
# pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 --index-url https://download.pytorch.org/whl/cu128
```

Complete installation (flash-attn AFTER pytorch):

```bash
cd Isaac-GR00T
source .venv/bin/activate
pip install --no-build-isolation flash-attn==2.8.2.post1
pip install -e .[base]
pip install torchcodec==0.4.0
sudo apt update && sudo apt install ffmpeg
```

`[OK]` when environment is ready on the server.

---

## Phase 3 — Collect data with SO-ARM

Follow the complete SO-ARM tutorial: https://wiki.seeedstudio.com/lerobot_so100m_new/

Key steps: configure motors → assemble → calibrate (no cameras during calibration) → add cameras → record dataset.

Camera parameter names for GR00T N1.6 must be `wrist` and `front`:

```
--robot.cameras="{ wrist: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}, front: {type: opencv, index_or_path: 6, width: 640, height: 480, fps: 30}}"
```

> If you use different names, you'll need to modify parameter files and keywords in the source code during training and deployment.

Upload the collected dataset to your fine-tuning server manually (recommended over Hugging Face Hub download due to network issues).

`[OK]` when dataset is available on the fine-tuning server.

---

## Phase 4 — Convert dataset and fine-tune (~varies)

Convert LeRobot v3 dataset to v2 format (if needed):

```bash
cd Isaac-GR00T/scripts/lerobot_conversion
python convert_v3_to_v2.py --repo-id seeed/grap_fruit
```

If `modality.json` is missing, copy from: https://github.com/NVIDIA/Isaac-GR00T/blob/main/demo_data/cube_to_bowl_5/meta/modality.json

Download pre-trained model from https://huggingface.co/nvidia/GR00T-N1.6-3B

For single-GPU fine-tuning, modify `Isaac-GR00T/gr00t/data/dataset/factory.py`:

```python
# Change torch.distributed.barrier() to:
import torch.distributed as dist
if dist.is_available() and dist.is_initialized():
    dist.barrier()
```

Run fine-tuning:

```bash
export NUM_GPUS=1
CUDA_VISIBLE_DEVICES=0 python \
    gr00t/experiment/launch_finetune.py \
    --base-model-path nvidia/GR00T-N1.6-3B \
    --dataset-path ./demo_data/cube_to_bowl_5 \
    --embodiment-tag NEW_EMBODIMENT \
    --modality-config-path examples/SO100/so100_config.py \
    --num-gpus $NUM_GPUS \
    --output-dir /tmp/so100 \
    --save-total-limit 5 \
    --save-steps 2000 \
    --max-steps 2000 \
    --use-wandb \
    --global-batch-size 32 \
    --dataloader-num-workers 4
```

`[OK]` when training completes and checkpoint is saved. Transfer checkpoint to AGX Orin.

---

## Phase 5 — Run inference on AGX Orin 64G

Terminal 1 — Start inference server:

```bash
source .venv/bin/activate

uv run python gr00t/eval/run_gr00t_server.py \
  --model-path /tmp/so100_finetune/checkpoint-10000 \
  --embodiment-tag NEW_EMBODIMENT
```

Terminal 2 — Start inference client:

```bash
source .venv/bin/activate

uv run python gr00t/eval/real_robot/SO100/eval_so100.py \
  --robot.type=so101_follower --robot.port=/dev/ttyACM0 \
  --robot.id=orange_follower \
  --robot.cameras="{ wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, front: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}}" \
  --policy_host=localhost --policy_port=5555 \
  --lang_instruction="grasp fruit into plate"
```

Adjust `--robot.port` and camera `index_or_path` for your setup.

Expected: 8 actions output per inference cycle. Robot arm executes the learned grasping behavior.

`[OK]` when the robot successfully performs the task.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `uv` not found | Install with `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh`. |
| Wheel install fails on AGX Orin | Ensure flash-attn and torchvision are installed AFTER pytorch. Check Python version matches wheel (3.10). |
| `torch.cuda.is_available()` returns False | Reinstall GPU PyTorch wheel. Verify CUDA is installed with `nvcc --version`. |
| Dataset conversion fails | Ensure dataset is in LeRobot v3 format. Check `modality.json` exists in meta folder. |
| Single-GPU training crashes with distributed error | Apply the `torch.distributed.barrier()` fix in `factory.py`. |
| OOM during fine-tuning | Ensure ≥48GB VRAM. Reduce `--global-batch-size`. |
| Camera names mismatch | GR00T N1.6 expects `wrist` and `front`. Re-collect data or modify source code parameter files. |
| Serial port not found | Check `ls /dev/ttyACM*`. Ensure arm is connected before cameras to avoid port conflicts. |
| Inference server won't start | Verify checkpoint path is correct. Check CUDA and PyTorch are working. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with wheel download links, fine-tuning parameter tables, dataset structure requirements, and demo video (reference only)
