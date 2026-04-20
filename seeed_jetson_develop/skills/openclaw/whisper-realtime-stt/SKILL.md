---
name: whisper-realtime-stt
description: Deploy OpenAI Whisper on NVIDIA Jetson Orin for real-time speech-to-text. Clones the deployment repo, installs dependencies including ffmpeg, tests the environment, and runs real-time STT from a USB microphone (e.g. reSpeaker). Includes Riva vs Whisper comparison context.
---

# Real-Time Speech-to-Text with Whisper on Jetson Orin

Deploy Whisper on Jetson Orin for real-time speech-to-text processing directly on-device, eliminating network dependency and enhancing privacy. Uses a USB microphone for audio input.

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
| Jetson device | reComputer or other Jetson Orin-based device |
| Microphone | reSpeaker Mic Array v2.0 or other USB microphone |
| JetPack | With CUDA support |
| Network | Internet access for cloning repo and installing packages |

---

## Phase 1 — Install dependencies (~5 min)

```bash
git clone https://github.com/LJ-Hao/Deploy-Whisper-on-NVIDIA-Jetson-Orin-for-Real-time-Speech-to-Text.git
cd Deploy-Whisper-on-NVIDIA-Jetson-Orin-for-Real-time-Speech-to-Text
pip install -r requirements.txt
sudo apt update && sudo apt install ffmpeg
```

Configure the microphone sample rate:

```bash
arecord -D hw:2,0 --dump-hw-params
```

`[OK]` when all packages install and ffmpeg is available. `[STOP]` if pip or apt install fails.

---

## Phase 2 — Test environment (~1 min)

```bash
python test.py
```

Verify ffmpeg is installed:

```bash
ffmpeg -version
```

`[OK]` when `test.py` prints successful library import messages and `ffmpeg -version` shows version info. `[STOP]` if imports fail or ffmpeg is not found.

---

## Phase 3 — Run real-time speech-to-text

```bash
python main.py
```

Speak into the microphone and observe real-time transcription output.

`[OK]` when transcription appears in the terminal as you speak. `[STOP]` if audio device errors or model loading fails.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `pip install -r requirements.txt` fails | Check Python version ≥ 3.8. Try `pip install --upgrade pip` first. |
| `ffmpeg` not found after install | Run `sudo apt install ffmpeg` again. Verify with `which ffmpeg`. |
| `arecord` — no soundcard found | Check USB microphone connection. Run `arecord -l` to list devices. Adjust device ID (`hw:X,0`). |
| `test.py` import errors | Re-run `pip install -r requirements.txt`. Check for missing system libraries. |
| `main.py` — CUDA out of memory | Close other GPU processes. Use a smaller Whisper model variant. |
| `main.py` — no audio input | Verify microphone with `arecord -D hw:2,0 -f S16_LE -r 16000 -d 5 test.wav`. |
| Poor transcription accuracy | Ensure microphone sample rate is 16000 Hz. Reduce background noise. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with hardware setup photos, environment test screenshots, Riva vs Whisper comparison video, and project outlook (reference only)
