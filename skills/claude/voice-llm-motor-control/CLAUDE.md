---
name: voice-llm-motor-control
description: Build an end-to-end voice-controlled motor system on Jetson (reComputer Robotics J4012). Integrates Whisper ASR, Ollama LLM (Qwen 2.5) for intent understanding, and CAN bus motor control for MyActuator X Series Motors via natural voice commands.
---

# Voice-Controlled Motor System on Jetson

Build a voice-to-motor pipeline on reComputer Robotics J4012: Whisper captures speech → Qwen 2.5 LLM interprets intent → CAN bus drives MyActuator X Series Motors. Users can say commands like "Rotate 90 degrees clockwise."

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
| Jetson device | reComputer Robotics J4012 |
| Microphone | reSpeaker XVF3800 |
| Motor | MyActuator X Series Motors (CAN bus) |
| JetPack | With CUDA 12.6 |
| Network | Internet access for cloning repos and pulling models |

---

## Phase 1 — Install Whisper ASR server (~10 min)

Clone and build the Whisper server:

```bash
git clone https://github.com/jjjadand/whisper-stable4curl
cd whisper-stable4curl
export PATH=/usr/local/cuda-12.6/bin${PATH:+:${PATH}}
export LD_LIBRARY_PATH=/usr/local/cuda-12.6/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}
cmake --build build -j --config Release
```

Launch the Whisper inference service (in this terminal):

```bash
./build/bin/whisper-stream -m ./models/ggml-base.en-q5_1.bin -t 8 --step 0 --length 7000 -vth 0.7 --keep 1200
```

`[OK]` when Whisper starts listening for audio input. `[STOP]` if cmake build fails or CUDA paths are wrong.

---

## Phase 2 — Install Ollama and pull Qwen 2.5 (~10 min)

Open a new terminal and install Ollama:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Pull the Qwen 2.5 model:

```bash
ollama pull qwen2.5
```

`[OK]` when `ollama pull` completes successfully. `[STOP]` if Ollama install fails or model download errors.

---

## Phase 3 — Install and run motor control script (~5 min)

Clone the voice control project:

```bash
git clone https://github.com/yuyoujiang/voice_control.git
cd voice_control
```

Configure and bring up the CAN interface:

```bash
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
```

Run the application:

```bash
python app.py
```

`[OK]` when the app starts and responds to voice commands. `[STOP]` if CAN interface fails or Python errors occur.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| cmake build fails — CUDA not found | Verify CUDA 12.6 path: `ls /usr/local/cuda-12.6/bin/nvcc`. Set PATH/LD_LIBRARY_PATH exports. |
| Whisper model file not found | Ensure `./models/ggml-base.en-q5_1.bin` exists. Re-clone if missing. |
| Ollama install fails | Check internet. Retry the curl command. |
| `ollama pull qwen2.5` OOM | Close other GPU processes. Ensure 8GB+ RAM available. |
| CAN interface `can0` not found | Check hardware connection. Run `ip link show` to list interfaces. Install `can-utils` if needed. |
| `python app.py` import errors | Install missing deps: `pip install -r requirements.txt` if available. |
| Microphone not detected | Run `arecord -l` to list audio devices. Check reSpeaker USB connection. |
| Motor not responding | Verify CAN wiring and bitrate. Test with `cansend can0 001#0000000000000000`. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with hardware connection diagram, workflow explanation, and demo video (reference only)
