---
name: deploy-dia
description: Deploy the Dia neural text-to-speech model on reComputer Jetson for expressive, multi-speaker audio generation. Installs custom aarch64 PyTorch/torchaudio/triton wheels, clones the Dia repo, patches pyproject.toml, and launches a Gradio WebUI. Requires Jetson with 8GB+ RAM and JetPack 6.1+.
---

# Deploy Dia TTS on reComputer Jetson

Dia is an expressive neural speech generation model that produces natural multi-speaker audio from text. This skill deploys it on Jetson with a Gradio web interface.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Jetson device | 8GB+ RAM (e.g. reComputer J4012 with Orin NX 16GB) |
| JetPack | 6.1 or later |
| Python | 3.10 with pip |
| Network | Internet access for downloading wheels and cloning repo |

---

## Phase 1 — Download and install aarch64 PyTorch wheels (~5–10 min)

Download the following wheels from the Seeed shared drive:
- `torch-2.7.0-cp310-cp310-linux_aarch64.whl`
- `torchaudio-2.7.0-cp310-cp310-linux_aarch64.whl`
- `triton-3.3.0-cp310-cp310-linux_aarch64.whl`

Install them:

```bash
pip install torch-2.7.0-cp310-cp310-linux_aarch64.whl
pip install torchaudio-2.7.0-cp310-cp310-linux_aarch64.whl
pip install triton-3.3.0-cp310-cp310-linux_aarch64.whl
```

Verify:

```bash
python3 -c "import torch; print(torch.__version__); print('CUDA:', torch.cuda.is_available())"
```

`[OK]` when torch imports and CUDA is available. `[STOP]` if wheel install fails.

---

## Phase 2 — Clone Dia and patch dependencies (~2 min)

```bash
git clone https://github.com/nari-labs/dia.git
cd dia
```

Edit `pyproject.toml` to comment out the torch, torchaudio, and triton dependency lines (lines 19–22) since we installed custom Jetson wheels:

```bash
sed -i 's/^\(\s*"torch.*\)/#\1/' pyproject.toml
sed -i 's/^\(\s*"torchaudio.*\)/#\1/' pyproject.toml
sed -i 's/^\(\s*"triton.*\)/#\1/' pyproject.toml
```

Install Dia and fix numpy:

```bash
pip install -e .
pip install numpy==1.26.4
```

`[OK]` when `pip install -e .` completes without error. `[STOP]` if dependency resolution fails.

---

## Phase 3 — Launch Dia Gradio WebUI (~2 min to start, model download on first run)

```bash
export GRADIO_SERVER_NAME=0.0.0.0
cd dia
python app.py
```

Open a browser and navigate to `http://<jetson-ip>:7860`.

`[OK]` when the Gradio interface loads and you can generate audio from text.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Wheel install fails — platform mismatch | Confirm you are on aarch64 with Python 3.10: `python3 --version` and `uname -m`. |
| `import torch` fails after install | Check pip target: `python3 -m pip show torch`. Ensure no conflicting system torch. |
| CUDA not available in torch | Verify JetPack 6.1+ is installed: `cat /etc/nv_tegra_release`. Check `nvcc --version`. |
| `pip install -e .` fails on dependency | Ensure torch/torchaudio/triton lines are commented out in `pyproject.toml`. |
| Gradio WebUI not accessible remotely | Confirm `GRADIO_SERVER_NAME=0.0.0.0` is set. Check firewall: `sudo ufw allow 7860`. |
| OOM when generating audio | Close other GPU processes. 8GB is minimum — larger models may need 16GB. |
| Model download hangs on first run | Check internet connectivity. Retry or manually download model weights. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with screenshots, demo video, and sample dialogue text (reference only)
