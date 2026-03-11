---
name: speech-vlm
description: Run a multimodal Visual Language Model (VLM) with speech interaction on reComputer Jetson (AGX Orin 64G or Orin NX 16G), combining NVIDIA VLM, SenseVoice speech-to-text, and Coqui-ai TTS for voice-driven visual scene understanding.
---

# Run VLM with Speech Interaction

## Execution model

Run one phase at a time. After each phase, verify the expected result before continuing.
- If a phase succeeds → print `[OK]` and move to the next phase.
- If a phase fails → print `[STOP]`, consult the failure decision tree, and ask the user before retrying.

## Phase 1 — Verify prerequisites

Required hardware:
- reComputer Jetson AGX Orin 64G or Orin NX 16G (16GB+ memory)
- USB driver-free speaker microphone
- IP camera with RTSP output (or use NVStreamer for local video)

```bash
# Check JetPack 6 and CUDA
cat /etc/nv_tegra_release
nvcc --version
# Check available memory
free -h
```

Expected: JetPack 6.x installed; CUDA available; 16GB+ RAM.

## Phase 2 — Initialize system environment

```bash
# Ensure nvidia-jetpack is fully installed
sudo apt-get install nvidia-jetpack

# Install system dependencies
sudo apt-get install libportaudio2 libportaudiocpp0 portaudio19-dev

# Install Python packages
sudo pip3 install pyaudio playsound subprocess wave keyboard
sudo pip3 --upgrade setuptools
sudo pip3 install sudachipy==0.5.2
```

Verify audio devices are working and network is stable:

```bash
arecord -l   # List recording devices
aplay -l     # List playback devices
ping -c 2 8.8.8.8
```

Expected: Audio devices listed; network reachable.

## Phase 3 — Install VLM

Follow the NVIDIA Jetson VLM installation guide. Ensure you can perform text-based inference with VLM before proceeding.

Reference: [Run VLM on reComputer](https://wiki.seeedstudio.com/run_vlm_on_recomputer)

## Phase 4 — Install PyTorch and Torchaudio

Install PyTorch, Torchaudio, and Torchvision matching your JetPack version.

Reference: [PyTorch installation for Jetson](https://github.com/Seeed-Projects/reComputer-Jetson-for-Beginners/blob/main/3-Basic-Tools-and-Getting-Started/3.3-Pytorch-and-Tensorflow/README.md)

```bash
# Verify PyTorch with CUDA
python3 -c "import torch; print(torch.cuda.is_available())"
```

Expected: `True`

## Phase 5 — Install Speech_vlm (SenseVoice)

```bash
cd ~/
git clone https://github.com/ZhuYaoHui1998/speech_vlm.git
cd ~/speech_vlm
sudo pip3 install -r requement.txt
```

Expected: All SenseVoice dependencies installed.

## Phase 6 — Install TTS (Coqui-ai)

```bash
cd ~/speech_vlm/TTS
sudo pip3 install .[all]
```

Expected: TTS package installed successfully.

## Phase 7 — Start VLM service

```bash
cd ~/speech_vlm
sudo docker compose up -d
```

```bash
# Verify containers are running
sudo docker ps
```

Expected: VLM containers running.

## Phase 8 — Add RTSP camera stream

Edit `set_streamer_id.sh` — replace `0.0.0.0` with Jetson IP and set your RTSP stream address:

```bash
cd ~/speech_vlm
# Edit the script with your Jetson IP and RTSP URL
nano set_streamer_id.sh
sudo chmod +x ./set_streamer_id.sh
./set_streamer_id.sh
```

Record the returned camera ID — it is needed for the next phase.

Expected: Camera ID returned in the response.

## Phase 9 — Run speech VLM

Edit `vlm_voice.py` — replace `0.0.0.0` with Jetson IP in `API_URL` and fill in the camera ID in `REQUEST_ID`.

```bash
cd ~/speech_vlm
sudo python3 vlm_voice.py
```

After launch, select the audio device index when prompted. Press `1` to record, `2` to send.

Expected: Program starts, audio device selection shown, speech interaction works.

## Phase 10 — View results (optional)

Edit `view_rtsp.py` — replace `0.0.0.0` in `rtsp_url` with Jetson IP.

```bash
sudo pip3 install opencv-python
cd ~/speech_vlm
sudo python3 view_rtsp.py
```

Expected: RTSP output stream displayed with VLM annotations.

## Failure decision tree

| Symptom | Likely cause | Suggested fix |
|---|---|---|
| `nvidia-jetpack` install fails | Incomplete JetPack flash | Reflash with full JetPack 6 image |
| `pyaudio` install fails | Missing portaudio dev headers | `sudo apt-get install portaudio19-dev` |
| No audio devices found | USB mic not recognized | Check `lsusb`; try different USB port |
| Docker compose fails | Docker not installed or no permissions | Install docker-ce; add user to docker group |
| Camera ID not returned | Wrong IP or RTSP URL | Verify Jetson IP and camera RTSP stream accessibility |
| VLM inference timeout | Insufficient memory | Ensure 16GB+ RAM; close other processes |
| TTS install fails | Missing build dependencies | `sudo apt-get install build-essential python3-dev` |

## Reference files

- `references/source.body.md` — Full original wiki content (reference only)
