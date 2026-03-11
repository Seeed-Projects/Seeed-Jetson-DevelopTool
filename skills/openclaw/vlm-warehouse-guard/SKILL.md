---
name: vlm-warehouse-guard
description: Deploy a VLM (LLaVa) on reComputer Industrial J4012 to monitor a warehouse using a USB camera. Integrates RS485 signal light control for safety status indication (green/yellow/red). Requires JP6, Ollama, and RS485 components (hub, color-changing light, light sensor).
---

# VLM Warehouse Guard on reComputer Industrial J4012

Deploy LLaVa via Ollama on a Jetson to monitor warehouse safety using a USB camera. The system controls an RS485 signal light: green for safe, yellow for danger (fire/weapon), red when warehouse lights are off.

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
| Jetson device | reComputer Industrial J4012 |
| JetPack | 6 (JP6) with CUDA libraries |
| RS485 hardware | RS485 hub, RS485 color-changing light, RS485 light sensor |
| USB camera | Connected to the Jetson |
| Network | Internet access for installing Ollama and cloning repo |

---

## Phase 1 — Initialize system environment (~10 min)

Verify CUDA and install nvidia-jetpack if needed:

```bash
sudo apt-get install nvidia-jetpack
```

Install Ollama:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Pull and run the LLaVa model:

```bash
ollama run llava-llama3:8b
```

`[OK]` when the model responds to a test prompt. `[STOP]` if Ollama install fails or model download errors out.

---

## Phase 2 — Install project (~5 min)

Install uv package manager:

```bash
pip install uv
```

Clone the project:

```bash
git clone https://github.com/Seeed-Projects/VLM-Guard.git
```

Set up the environment:

```bash
cd VLM_Guard
uv sync
source .venv/bin/activate
```

`[OK]` when `uv sync` completes and the venv activates. `[STOP]` if git clone or uv sync fails.

---

## Phase 3 — Run the project (~1 min)

```bash
./start_demo.sh
```

Open a browser and navigate to `http://localhost:5002` to access the application interface.

`[OK]` when the web interface loads and camera feed is visible. `[STOP]` if the script errors or the page does not load.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `nvidia-jetpack` install fails | Confirm JP6 is flashed. Check `cat /etc/nv_tegra_release`. |
| Ollama install fails | Check internet connectivity. Retry `curl -fsSL https://ollama.com/install.sh \| sh`. |
| `ollama run` hangs or OOM | Ensure 8GB+ RAM available. Close other GPU processes with `sudo fuser -v /dev/nvidia*`. |
| `git clone` fails | Check network. Verify `git` is installed: `sudo apt install git`. |
| `uv sync` fails | Ensure `pip install uv` succeeded. Check Python version ≥ 3.8. |
| Camera not detected | Run `ls /dev/video*` to confirm USB camera is connected. |
| RS485 devices not responding | Check RS485 hub wiring. Verify serial port permissions. |
| Web UI not loading on port 5002 | Check firewall: `sudo ufw allow 5002`. Confirm script is running without errors. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with hardware photos, RS485 wiring details, demo video, and result descriptions (reference only)
