---
name: gpt-oss-live
description: Deploy GPT-OSS-20B on Jetson Orin using llama.cpp with CUDA. Builds llama.cpp from source, converts and quantizes the model to Q4_K, and runs inference. Optional OpenWebUI frontend. Requires Jetson Orin with ≥16GB RAM.
---

# GPT-OSS-20B on Jetson Orin

Runs OpenAI's GPT-OSS-20B open-weight model on a Jetson Orin device using llama.cpp
compiled with CUDA support. The model is converted from HuggingFace format to GGUF and
quantized to Q4_K for on-device inference. An optional OpenWebUI frontend is included.

Hardware: reComputer Super J4012 or other Jetson Orin
Prerequisites: JetPack 6.x, Miniconda installed, ~40GB free disk space

---

## Execution model

Run one phase at a time. After each phase:
- Relay all output lines to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Phase 1 — deps  (~5 min)

Install Miniconda (skip if already installed) and system build dependencies.

```bash
# Only if Miniconda is not yet installed:
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
chmod +x Miniconda3-latest-Linux-aarch64.sh
./Miniconda3-latest-Linux-aarch64.sh
source ~/.bashrc
```

```bash
sudo apt update
sudo apt install -y build-essential cmake git
```

Expected: `cmake --version` and `gcc --version` both return successfully. `[OK]`

---

## Phase 2 — build  (~2 hours)

Clone and build llama.cpp with CUDA enabled. This step is long — expect roughly 2 hours
on Jetson Orin. Do not interrupt the build.

```bash
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
cmake -B build -DGGML_CUDA=ON
cmake --build build --parallel
```

Expected: `./build/bin/llama-cli --version` prints a version string. `[OK]`

---

## Phase 3 — model  (varies)

Download the GPT-OSS-20B weights from HuggingFace, upload to Jetson, then convert and quantize.

1. Download from: https://huggingface.co/openai/gpt-oss-20b/tree/main
2. Transfer the downloaded model directory to the Jetson (e.g. via `scp` or USB drive).
3. Create the conda environment and convert to GGUF:

```bash
conda create -n gpt-oss python=3.10
conda activate gpt-oss
cd llama.cpp
pip install .
python convert_hf_to_gguf.py --outfile <path_of_output> <path_of_input_model>
```

4. Quantize to Q4_K:

```bash
./build/bin/llama-quantize <f16_gguf> <output_q4_gguf> Q4_K
```

Replace `<path_of_input_model>`, `<path_of_output>`, `<f16_gguf>`, and `<output_q4_gguf>` with your actual paths.

Expected: Q4_K `.gguf` file created, size roughly 10–12 GB. `[OK]`

---

## Phase 4 — run

Launch inference with the quantized model. `-ngl 40` offloads 40 layers to GPU.

```bash
cd llama.cpp
./build/bin/llama-cli -m <model_path> -ngl 40
```

Expected: model loads and accepts prompts interactively. `[OK]`

---

## Optional — WebUI

Serve a browser-based chat interface on port 8080, backed by llama.cpp on port 8081.

```bash
conda create -n open-webui python=3.11
conda activate open-webui
pip install open-webui
open-webui serve
```

Then open `http://<jetson-ip>:8080` in a browser and set the OpenAI connection URL to `http://127.0.0.1:8081`.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| cmake — CUDA not found / `DGGML_CUDA=ON` has no effect | Confirm CUDA toolkit is on PATH: `nvcc --version`. On JetPack 6 it should be at `/usr/local/cuda`. Re-run cmake: `cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc`. |
| build fails — compiler OOM / killed | Reduce parallelism: replace `--parallel` with `--parallel 2`. If it still fails, try `--parallel 1`. |
| `convert_hf_to_gguf.py` fails — missing module | Ensure you ran `pip install .` inside the `llama.cpp` directory with the `gpt-oss` conda env active. |
| `convert_hf_to_gguf.py` fails — unrecognised model architecture | Check that the downloaded model directory is complete and matches the expected GPT-OSS-20B structure. Re-download if files are missing. |
| `llama-cli` crashes on load — CUDA OOM | Reduce GPU layers: try `-ngl 20` or `-ngl 10`. Confirm no other GPU workloads are running. |
| `llama-cli` crashes mid-generation | Model file may be corrupt. Re-run quantization step or re-download source weights. |

---

## Reference files

- `references/source.body.md` — original tutorial article (background reading, not required for execution)
