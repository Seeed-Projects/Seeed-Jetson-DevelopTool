---
name: local-chatbot-physical
description: Build a voice-interactive AI chatbot on Jetson for physical AI applications using Ollama (LLM), NVIDIA Riva (STT/TTS), and Docker. Fully offline voice assistant with real-time speech recognition and synthesis. Requires JetPack 6.0+ and NGC API key.
---

# Voice-Interactive Chatbot on Jetson (Physical AI)

Deploy a fully local voice chatbot for physical AI use cases — the system listens, reasons with a local LLM, and speaks back. Uses NVIDIA Riva for speech processing and Ollama for inference, all running in Docker on Jetson hardware.

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
| Hardware | NVIDIA Jetson (AGX Orin recommended for larger models) |
| JetPack | 6.0+ |
| Docker | Installed with NVIDIA runtime |
| NGC Account | API key from catalog.ngc.nvidia.com |
| Audio | Microphone and speaker connected to Jetson |

---

## Phase 1 — Install Jetson Containers and Ollama (~5 min)

```bash
git clone https://github.com/dusty-nv/jetson-containers
bash jetson-containers/install.sh
```

Run Ollama and pull a model:

```bash
jetson-containers run --name ollama $(autotag ollama)
```

Inside the container:

```bash
ollama run llama3.2:1b
```

Type `/bye` to exit after confirming the model loads.

Verify from host:

```bash
curl http://localhost:11434/api/tags
```

`[OK]` when curl returns JSON listing the model.
`[STOP]` if Ollama container fails to start — check Docker and NVIDIA runtime.

---

## Phase 2 — Install and configure NGC CLI (~3 min)

```bash
mkdir -p ~/ngc_setup && cd ~/ngc_setup
wget --content-disposition https://api.ngc.nvidia.com/v2/resources/nvidia/ngc-apps/ngc_cli/versions/3.36.0/files/ngccli_arm64.zip
unzip ngccli_arm64.zip
chmod u+x ngc-cli/ngc
echo "export PATH=\"\$PATH:$(pwd)/ngc-cli\"" >> ~/.bash_profile
source ~/.bash_profile
ngc config set
```

Enter your NGC API key when prompted.

`[OK]` when `ngc config current` shows your org/team.
`[STOP]` if API key is rejected — regenerate at catalog.ngc.nvidia.com.

---

## Phase 3 — Install NVIDIA Riva (~15–30 min)

```bash
mkdir -p ~/riva_setup && cd ~/riva_setup
ngc registry resource download-version nvidia/riva/riva_quickstart_arm64:2.16.0
cd riva_quickstart_arm64_v2.16.0
```

Edit `config.sh` to disable unused services:

```bash
sed -i 's/service_enabled_nlp=.*/service_enabled_nlp=false/' config.sh
sed -i 's/service_enabled_nmt=.*/service_enabled_nmt=false/' config.sh
```

Configure Docker NVIDIA runtime (if not already set):

```bash
sudo tee /etc/docker/daemon.json > /dev/null << 'EOF'
{
  "default-runtime": "nvidia",
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  }
}
EOF
sudo systemctl restart docker
```

Initialize and start Riva:

```bash
sudo bash riva_init.sh
sudo bash riva_start.sh
```

`[OK]` when Riva services start without error (check `docker ps` for riva containers).
`[STOP]` if init fails — check disk space (Riva models are large) and JetPack compatibility.

---

## Phase 4 — Clone and run the chatbot (~2 min)

```bash
git clone https://github.com/kouroshkarimi/local_chatbot_jetson.git
cd local_chatbot_jetson
pip3 install -r requirements.txt
```

List audio devices:

```bash
python3 app.py --list-input-devices
python3 app.py --list-output-devices
```

Start the chatbot with your audio devices:

```bash
python3 app.py --input-device <input_id> --output-device <output_id>
```

`[OK]` when the chatbot starts listening and responds to voice input.
`[STOP]` if audio devices not found — check connections and ALSA config.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Ollama container won't start | Check NVIDIA runtime: `docker info \| grep -i runtime`. Install nvidia-container-runtime if missing. |
| NGC download fails | Verify API key: `ngc config current`. Check network connectivity. |
| Riva init fails with disk space error | Riva models need ~15 GB. Free space or use external storage. |
| Riva init fails with JetPack mismatch | Check Riva support matrix at docs.nvidia.com/deeplearning/riva. |
| No audio input detected | Check `arecord -l` for recording devices. Verify microphone is connected. |
| No audio output | Check `aplay -l` for playback devices. Test with `speaker-test -t wav`. |
| LLM response too slow | Use a smaller model (llama3.2:1b). Check GPU utilization with `jtop`. |
| Docker permission denied | Add user to docker group: `sudo usermod -aG docker $USER`. Log out and back in. |

---

## Reference files

- `references/source.body.md` — Full project documentation with system architecture, Ollama model table, Riva setup details, and usage examples (reference only)
