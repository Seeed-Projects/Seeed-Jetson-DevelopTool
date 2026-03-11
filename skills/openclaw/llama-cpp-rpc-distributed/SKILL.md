---
name: llama-cpp-rpc-distributed
description: Distribute LLM inference across multiple Jetson devices using llama.cpp RPC backend with CUDA. Build from source with RPC+CUDA, convert models to GGUF, and run multi-node inference for horizontal scaling. Requires two Jetson devices with JetPack 6.x+.
---

# Distributed llama.cpp on Jetson (RPC Mode)

Run large language models across multiple Jetson devices by leveraging llama.cpp's RPC backend. This enables horizontal scaling — split model layers across GPUs on different machines connected via LAN.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all output to the user.
- If output contains `[STOP]` → stop, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Hardware | Two reComputer Jetson devices (e.g. Orin NX/AGX Orin) |
| JetPack | 6.x+ with working CUDA drivers |
| Network | Both devices on same LAN, able to ping each other |
| RAM | Client ≥ 64 GB, remote node ≥ 32 GB (unified memory) |
| Storage | ~5 GB free for build + model |

---

## Phase 1 — Clone and install build dependencies (~2 min)

Run on both machines:

```bash
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
sudo apt update
sudo apt install -y build-essential cmake git libcurl4-openssl-dev python3-pip
```

`[OK]` when clone and apt install complete on both machines.

---

## Phase 2 — Build with RPC + CUDA backend (~5 min)

Run on both machines:

```bash
cd llama.cpp
cmake -B build \
  -DGGML_CUDA=ON \
  -DGGML_RPC=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
```

Verify:

```bash
ls build/bin/llama-cli build/bin/rpc-server
```

`[OK]` when both `llama-cli` and `rpc-server` binaries exist.
`[STOP]` if cmake or build fails — see failure decision tree.

---

## Phase 3 — Install Python conversion tools (~1 min)

Run on the client machine (Machine A):

```bash
cd llama.cpp
pip3 install -e .
```

`[OK]` when pip install completes.

---

## Phase 4 — Download and convert model (~5–10 min)

Using TinyLlama-1.1B-Chat as an example:

```bash
pip3 install huggingface-hub
huggingface-cli download TinyLlama/TinyLlama-1.1B-Chat-v1.0 --local-dir ~/TinyLlama-1.1B-Chat-v1.0
```

Convert to GGUF:

```bash
cd llama.cpp
python3 convert_hf_to_gguf.py \
  --outfile ~/TinyLlama-1.1B.gguf \
  ~/TinyLlama-1.1B-Chat-v1.0
```

`[OK]` when GGUF file is created.
`[STOP]` if conversion fails — check model files are complete.

---

## Phase 5 — Verify single-machine inference (~1 min)

```bash
cd llama.cpp
./build/bin/llama-cli \
  -m ~/TinyLlama-1.1B.gguf \
  -p "Hello, how are you today?" \
  -n 64
```

`[OK]` when the model generates a text response.
`[STOP]` if inference fails — check CUDA with `nvidia-smi`.

---

## Phase 6 — Start RPC server on remote machine (Machine B)

SSH into Machine B and run:

```bash
cd llama.cpp
CUDA_VISIBLE_DEVICES=0 ./build/bin/rpc-server --host <MACHINE_B_IP>
```

Default port is `50052`. Customize with `-p <port>`.

`[OK]` when server prints "listening on <IP>:50052".

---

## Phase 7 — Start RPC server on local machine (Machine A)

In a separate terminal on Machine A:

```bash
cd llama.cpp
CUDA_VISIBLE_DEVICES=0 ./build/bin/rpc-server -p 50052
```

`[OK]` when server prints listening message.

---

## Phase 8 — Run distributed inference (~1 min)

On Machine A, in another terminal:

```bash
cd llama.cpp
./build/bin/llama-cli \
  -m ~/TinyLlama-1.1B.gguf \
  -p "Hello, my name is" \
  -n 64 \
  --rpc <MACHINE_B_IP>:50052,127.0.0.1:50052 \
  -ngl 99
```

`-ngl 99` offloads all layers to GPU across both RPC nodes.

`[OK]` when distributed inference produces output and both RPC servers show activity.
`[STOP]` if connection refused — check network and firewall.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| cmake fails with CUDA not found | Verify CUDA: `nvcc --version`. Ensure JetPack 6.x is installed. |
| Build fails with missing headers | Run `sudo apt install -y build-essential cmake libcurl4-openssl-dev`. |
| `rpc-server` startup failure | Check if port 50052 is occupied: `ss -tlnp \| grep 50052`. Check firewall: `sudo ufw allow 50052`. |
| Connection refused during distributed inference | Verify machines can ping each other. Confirm RPC servers are running on both. |
| Slower inference with RPC than single-node | Model too small for network overhead to pay off. Try a larger model (7B+). |
| Out of memory error | Reduce `-ngl` value to keep some layers on CPU. Close other GPU processes. |
| Model conversion fails | Ensure all model files downloaded completely. Check disk space. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with hardware topology diagrams, performance comparison screenshots, and troubleshooting details (reference only)
