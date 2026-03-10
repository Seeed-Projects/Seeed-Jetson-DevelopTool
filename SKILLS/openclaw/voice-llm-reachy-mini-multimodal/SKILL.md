---
name: voice-llm-reachy-mini-multimodal
description: Deploy a fully local voice-interactive robotic assistant on reComputer Mini J501 with Reachy Mini. Integrates Ollama LLM, FunASR speech recognition, and Coqui TTS for an embodied conversational AI experience. Requires JP6.2 and Reachy Mini Lite.
---

# Local Voice LLM on reComputer Mini for Reachy Mini (Multimodal)

Build a low-latency, privacy-first voice assistant on reComputer Mini J501 paired with Reachy Mini robot. Uses local speech recognition, Ollama LLM, and speech synthesis for embodied human-robot interaction.

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
| Jetson device | reComputer Mini J501 Kit (carrier board + Jetson module + cooling) |
| Robot | Reachy Mini Lite, connected via USB Type-A to J501 |
| JetPack | 6.2 |
| Network | Internet access for model downloads and repo cloning |

---

## Phase 1 — Install Ollama and pull LLM (~15 min)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2-vision:11b
```

The model download takes approximately 10 minutes.

`[OK]` when `ollama pull` completes. `[STOP]` if install fails or download errors out.

---

## Phase 2 — Install conversation application (~5 min)

```bash
cd Downloads
git clone https://github.com/Seeed-Projects/reachy-mini-loacl-conversation.git
cd reachy-mini-loacl-conversation
pip install -r requirements.txt -i https://pypi.jetson-ai-lab.io/
pip install "reachy-mini"
```

`[OK]` when all pip installs complete without error. `[STOP]` if dependency installation fails.

---

## Phase 3 — Launch the application (~2 min)

In one terminal, start the Reachy Mini daemon:

```bash
reachy-mini-daemon
```

In a second terminal, set environment variables and launch:

```bash
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="qwen2.5:7b"
export COQUI_MODEL_NAME="tts_models/zh-CN/baker/tacotron2-DDC-GST"
export DEFAULT_VOLUME="1.5"
python main.py
```

Use `R` key to start recording and `S` key to stop. The LLM will generate a spoken response.

`[OK]` when the app starts and responds to voice input. `[STOP]` if daemon or main.py crashes.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Ollama install fails | Check internet connectivity. Retry the curl command. |
| Model pull OOM or timeout | Ensure sufficient disk space (11b model is ~6GB). Check RAM with `free -h`. |
| `pip install` fails on requirements | Ensure the Jetson AI Lab PyPI index is reachable. Try without `-i` flag as fallback. |
| `reachy-mini-daemon` not found | Confirm `pip install "reachy-mini"` succeeded. Check `which reachy-mini-daemon`. |
| Reachy Mini not detected | Verify USB connection to Type-A port. Run `lsusb` to check. |
| `python main.py` import errors | Re-run `pip install -r requirements.txt`. Check Python version. |
| TTS model download fails | Check internet. The Coqui model downloads on first run. |
| No audio output | Check speaker/audio device. Adjust `DEFAULT_VOLUME` env var. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with hardware photos, workflow diagram, demo video, and language model configuration options (reference only)
