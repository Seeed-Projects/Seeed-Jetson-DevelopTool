---
name: deploy-riva-llama2
description: Build a local voice chatbot on Jetson AGX Orin using NVIDIA Riva (ASR + TTS) and Meta Llama2 via text-generation-inference. Sets up NGC, Riva server, Llama2-7b-chat, and a Python voice chatbot demo with speaker/microphone. Requires JetPack 5.1.1+ and 16GB+ RAM.
---

# Local Voice Chatbot — Riva + Llama2 on Jetson

Combines NVIDIA Riva for speech recognition/synthesis with Llama2 for conversational AI, all running locally on Jetson for privacy and low latency.

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
| Hardware | Jetson AGX Orin 32GB+ (e.g. AGX Orin H01 Kit) |
| JetPack | 5.1.1 or later |
| Audio | Speaker + microphone (e.g. ReSpeaker USB Mic Array) |
| NGC account | Required for Riva model download |
| HuggingFace token | Required for Llama2 model access |
| Docker | Installed with NVIDIA runtime |

---

## Phase 1 — Configure NGC CLI (~3 min)

```bash
cd ~ && mkdir -p ngc_setup && cd ngc_setup
wget --content-disposition https://api.ngc.nvidia.com/v2/resources/nvidia/ngc-apps/ngc_cli/versions/3.36.0/files/ngccli_arm64.zip
unzip ngccli_arm64.zip
chmod u+x ngc-cli/ngc
echo "export PATH=\"\$PATH:$(pwd)/ngc-cli\"" >> ~/.bash_profile
source ~/.bash_profile
ngc config set
```

Enter your NGC API Key when prompted (obtain from NGC → Account → Setup → Get API Key).

`[OK]` when `ngc config set` completes. `[STOP]` if download or auth fails.

---

## Phase 2 — Install and start Riva server (~20–30 min)

```bash
cd ~ && mkdir -p riva_setup && cd riva_setup
ngc registry resource download-version nvidia/riva/riva_quickstart_arm64:2.13.1
cd riva_quickstart_v2.13.1
```

Edit `config.sh` to disable unused services:

```bash
sed -i 's/service_enabled_nlp=true/service_enabled_nlp=false/' config.sh
sed -i 's/service_enabled_nmt=true/service_enabled_nmt=false/' config.sh
```

Configure Docker for NVIDIA runtime:

```bash
sudo bash -c 'cat > /etc/docker/daemon.json << EOF
{
    "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "path": "nvidia-container-runtime",
            "runtimeArgs": []
        }
    }
}
EOF'
sudo systemctl restart docker
```

Initialize and start Riva:

```bash
sudo bash riva_init.sh
sudo bash riva_start.sh
```

Keep this terminal alive.

`[OK]` when Riva server starts and shows "Riva server is ready". `[STOP]` if init or start fails.

---

## Phase 3 — Install and run Llama2 via text-generation-inference (~15–20 min)

Open a new terminal:

```bash
cd ~
git clone https://github.com/dusty-nv/jetson-containers.git
cd jetson-containers
pip install -r requirements.txt
./run.sh $(./autotag text-generation-inference)
```

Inside the container:

```bash
export HUGGING_FACE_HUB_TOKEN=<your-huggingface-token>
text-generation-launcher --model-id meta-llama/Llama-2-7b-chat-hf --port 8899
```

Keep this terminal alive.

`[OK]` when the model loads and the server is listening on port 8899. `[STOP]` if OOM or auth fails.

---

## Phase 4 — Run the voice chatbot demo (~3 min)

Open a third terminal:

```bash
cd ~
git clone https://github.com/yuyoujiang/Deploy-Riva-LLama-on-Jetson.git
cd Deploy-Riva-LLama-on-Jetson
```

List audio devices:

```bash
python3 local_chatbot.py --list-input-devices
python3 local_chatbot.py --list-output-devices
```

Launch the chatbot with your device IDs:

```bash
python3 local_chatbot.py --input-device <INPUT_ID> --output-device <OUTPUT_ID>
```

`[OK]` when the chatbot responds to voice input with spoken output.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| NGC CLI download fails | Check internet. Retry wget. Verify arm64 architecture. |
| `ngc config set` auth error | Regenerate API key at https://ngc.nvidia.com. |
| `riva_init.sh` fails | Check Docker is running with NVIDIA runtime. Verify `/etc/docker/daemon.json`. |
| Riva server won't start | Check GPU memory: `jtop`. Stop other GPU processes. |
| text-generation-inference OOM | Llama2-7b needs ~16GB. Use AGX Orin 32GB+ or try a smaller model. |
| HuggingFace token rejected | Ensure you accepted the Llama2 license on HuggingFace. Regenerate token. |
| No audio devices found | Check USB mic/speaker: `aplay -l` and `arecord -l`. |
| Chatbot no response | Verify Riva (port 50051) and LLM (port 8899) are both running. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with Riva config.sh details, screenshots, and demo video (reference only)
