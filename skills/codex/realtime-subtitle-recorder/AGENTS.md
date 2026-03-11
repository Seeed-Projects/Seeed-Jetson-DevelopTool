---
name: realtime-subtitle-recorder
description: Deploy a real-time speech-to-subtitle recorder on Jetson using NVIDIA Riva ASR, Flask, and a USB microphone (reSpeaker). Keeps meeting transcription fully on-device for privacy. Requires Jetson with Riva ASR server running.
---

# Real-Time Subtitle Recorder on Jetson

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
| Hardware | reComputer (Jetson-based) — e.g., reComputer Industrial J3011 |
| Microphone | reSpeaker Mic Array v2.0 or other USB microphone |
| Riva ASR | NVIDIA Riva ASR server installed and running (see Phase 2) |
| JetPack | Compatible with Riva (JP5.x or JP6.x) |
| Display | Monitor or browser access for subtitle output |

---

## Phase 1 — Preflight

Verify JetPack, USB microphone, and Docker.

```bash
cat /etc/nv_tegra_release
arecord -l
sudo docker ps
```

Expected: L4T version shown, USB audio device listed, Docker running. `[OK]` when all pass. `[STOP]` if no audio device detected.

---

## Phase 2 — Install Riva ASR server

Follow the [Riva ASR installation guide](https://wiki.seeedstudio.com/Local_Voice_Chatbot/#install-riva-server) to set up the Riva server.

Verify Riva is running:

```bash
sudo docker ps | grep riva
```

Expected: Riva container is listed and running. `[OK]` when confirmed. `[STOP]` if Riva is not running — refer to the Riva installation wiki.

---

## Phase 3 — Install Python dependencies

```bash
pip3 install flask
python3 -c 'import flask; print(flask.__version__)'
```

Install Riva client:

```bash
git clone --depth=1 --recursive https://github.com/nvidia-riva/python-clients
cd python-clients
sudo pip3 install --upgrade pip setuptools wheel
pip3 install --no-cache-dir --verbose -r requirements.txt
python3 setup.py --verbose bdist_wheel
pip3 install --no-cache-dir --verbose dist/nvidia_riva_client*.whl
python3 -c 'import riva.client; print(riva.client.__version__)'
```

Install PyAudio:

```bash
sudo apt-get install -y --no-install-recommends python3-pyaudio
python3 -c 'import pyaudio; print(pyaudio.__version__)'
```

`[OK]` when all imports succeed (flask, riva.client, pyaudio). `[STOP]` if any import fails.

---

## Phase 4 — Run the subtitle recorder

```bash
git clone https://github.com/Seeed-Projects/Real-time-Subtitle-Recorder-on-Jetson.git
cd Real-time-Subtitle-Recorder-on-Jetson
python3 recorder.py
```

Open a browser to view the real-time subtitles on the web interface.

`[OK]` when speech is captured and subtitles appear in real time on the web page.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `arecord -l` shows no devices | Check USB microphone connection. Try a different USB port. Verify with `lsusb`. |
| Riva container not running | Re-start Riva: follow the installation wiki. Check Docker logs: `sudo docker logs <riva_container>`. |
| `pip3 install flask` fails | Upgrade pip: `sudo pip3 install --upgrade pip`. Check internet connectivity. |
| Riva client wheel build fails | Ensure `setuptools` and `wheel` are upgraded. Check Python version compatibility. |
| `import pyaudio` fails | Install system dependency: `sudo apt-get install portaudio19-dev`. Then reinstall pyaudio. |
| `recorder.py` crashes on start | Verify Riva ASR is running. Check microphone is detected. Review error output for missing dependencies. |
| No subtitles appearing | Speak clearly near the microphone. Check Riva ASR model is loaded (check Riva logs). |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with hardware connection diagram, step-by-step verification screenshots, and video demonstration (reference only)
