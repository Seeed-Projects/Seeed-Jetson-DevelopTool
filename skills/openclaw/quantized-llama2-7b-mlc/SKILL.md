---
name: quantized-llama2-7b-mlc
description: Deploy quantized Llama2-7B with MLC LLM on Jetson Orin NX for fast edge inference. Uses jetson-containers Docker workflow with 4-bit quantization (q4f16_ft). Requires Jetson Orin with ≥16GB RAM, JetPack 5.x, and HuggingFace access token.
---

# Quantized Llama2-7B with MLC LLM on Jetson

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
| RAM | ≥ 16 GB |
| JetPack | 5.x (R35.x) |
| Storage | SSD recommended — model weights + Docker images are large |
| Internet | Required for Docker pull and model download |
| HuggingFace | Access token with Llama2 model access granted |

---

## Phase 1 — Preflight

```bash
cat /etc/nv_tegra_release
free -h
df -h /
```

Expected: R35.x (JP5), ≥16 GB RAM, ≥50 GB disk free. `[OK]` when all pass. `[STOP]` if insufficient RAM or disk.

---

## Phase 2 — Install dependencies and clone jetson-containers

```bash
sudo apt-get update
sudo apt-get install -y git python3-pip
git clone --depth=1 https://github.com/dusty-nv/jetson-containers
cd jetson-containers
pip3 install -r requirements.txt
```

Clone the MLC-LLM helper scripts:

```bash
cd ./data
git clone https://github.com/LJ-Hao/MLC-LLM-on-Jetson-Nano.git
cd ..
```

`[OK]` when both repos are cloned and requirements installed. `[STOP]` if git clone fails.

---

## Phase 3 — Pull MLC Docker image and download Llama2 model

Replace `<YOUR-ACCESS-TOKEN>` with your HuggingFace token:

```bash
./run.sh --env HUGGINGFACE_TOKEN=<YOUR-ACCESS-TOKEN> $(./autotag mlc) \
  /bin/bash -c 'ln -s $(huggingface-downloader meta-llama/Llama-2-7b-chat-hf) /data/models/mlc/dist/models/Llama-2-7b-chat-hf'
```

Verify the Docker image was created:

```bash
sudo docker images | grep mlc
```

`[OK]` when MLC image is listed and model download completed. `[STOP]` if image not found or download failed.

---

## Phase 4 — Quantize the model with MLC

```bash
./run.sh $(./autotag mlc) \
  python3 -m mlc_llm.build \
  --model Llama-2-7b-chat-hf \
  --quantization q4f16_ft \
  --artifact-path /data/models/mlc/dist \
  --max-seq-len 4096 \
  --target cuda \
  --use-cuda-graph \
  --use-flash-attn-mqa
```

`[OK]` when quantization completes without errors. `[STOP]` if OOM or build errors.

---

## Phase 5 — Run inference

Enter the Docker container (use the image name from Phase 3):

```bash
./run.sh <YOUR_MLC_IMAGE_NAME>
# e.g.: ./run.sh dustynv/mlc:51fb0f4-builder-r35.4.1
```

Inside the container, run the quantized model:

```bash
cd /data/MLC-LLM-on-Jetson
python3 Llama-2-7b-chat-hf-q4f16_ft.py
```

For comparison, you can also try the non-quantized version (will likely OOM on 16GB):

```bash
python3 Llama-2-7b-chat-hf.py
```

`[OK]` when the quantized model generates text responses successfully.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `git clone` fails | Check internet connectivity. Verify git is installed. |
| HuggingFace download fails | Verify token is valid and has Llama2 access. Visit https://huggingface.co/meta-llama/Llama-2-7b-chat-hf to request access. |
| Docker image not found after `./run.sh` | Run `sudo docker images` to check. Re-run the Phase 3 command. |
| OOM during quantization | Close other processes. Ensure ≥16 GB RAM. Try reducing `--max-seq-len`. |
| Non-quantized model fails to run | Expected on 16 GB — the full model requires more memory. Use the quantized version. |
| `./autotag mlc` returns wrong tag | Verify JetPack version matches. The autotag script selects based on L4T version. |
| Slow inference | Ensure `--use-cuda-graph` and `--use-flash-attn-mqa` flags were used during quantization. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with Docker screenshots, comparison between quantized and non-quantized inference, and video demonstration (reference only)
