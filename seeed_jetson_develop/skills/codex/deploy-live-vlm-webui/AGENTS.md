---
name: deploy-live-vlm-webui
description: Deploy Live VLM WebUI on reComputer Jetson for real-time Vision Language Model interaction via webcam. Installs Ollama with llama3.2-vision model and the live-vlm-webui Python package for browser-based VLM streaming and benchmarking. Requires JetPack 6.2 and USB camera.
---

# Deploy Live VLM WebUI on reComputer Jetson

Live VLM WebUI streams your webcam to any VLM for live AI-powered visual analysis. This skill installs Ollama + llama3.2-vision and the WebUI on Jetson.

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
| Hardware | reComputer Super J4012 (Orin NX 16GB) or similar |
| JetPack | 6.2 |
| Camera | USB camera connected to Type-A port |
| Network | Internet for model download (~7GB) |

---

## Phase 1 — Install and configure Ollama (~10–15 min)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2-vision:11b
```

Verify:

```bash
ollama list
# Expected: llama3.2-vision:11b listed
```

`[OK]` when model appears in `ollama list`. `[STOP]` if download fails or OOM.

---

## Phase 2 — Install Live VLM WebUI (~3 min)

```bash
sudo apt install -y openssl python3-pip
python3 -m pip install --user live-vlm-webui
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Verify:

```bash
which live-vlm-webui
```

`[OK]` when the binary path is printed. `[STOP]` if pip install fails.

---

## Phase 3 — Launch and configure WebUI (~2 min)

```bash
live-vlm-webui
```

Open browser at `https://localhost:8090`, then configure:
1. VLM API Configuration → select `ollama` engine → select `llama3.2-vision` model
2. Camera and App Control → select `USB Camera`
3. Click **Run** to start inference

`[OK]` when inference results appear in the browser.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Ollama install fails | Check internet. Retry: `curl -fsSL https://ollama.com/install.sh \| sh`. |
| Model pull OOM or killed | 16GB RAM minimum for 11b model. Free memory by stopping other processes. |
| `live-vlm-webui: command not found` | Ensure `~/.local/bin` is in PATH: `source ~/.bashrc`. |
| WebUI not accessible at port 8090 | Check firewall: `sudo ufw allow 8090`. Verify process is running. |
| USB camera not detected in WebUI | Check camera: `ls /dev/video*`. Replug camera. |
| Inference very slow | Expected on 16GB devices. Consider using a smaller vision model. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with screenshots, demo video, and configuration details (reference only)
