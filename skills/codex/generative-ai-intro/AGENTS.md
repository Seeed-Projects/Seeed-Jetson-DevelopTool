---
name: generative-ai-intro
description: Overview and index of Generative AI capabilities on reComputer Jetson. Covers text generation (LLM chatbots), image generation, audio generation (Whisper STT), multimodal (VLM), RAG, LLM fine-tuning, and quantized inference. This is a reference/navigation skill — it links to specific deployment skills.
---

# Generative AI with reComputer Jetson

---

## Execution model

Run one phase at a time. After each phase:
- Relay all command output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree below.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Hardware | NVIDIA Jetson Orin (reComputer recommended) |
| JetPack | 5.x or 6.x depending on specific application |
| Internet | Required for container pulls and model downloads |

---

## Phase 1 — Identify the target application

This skill is an index of Generative AI topics on Jetson. Help the user identify which specific application they need:

**Text Generation (Local Chatbots)**
- Local AI Assistant with Ollama + AnythingLLM
- Local Voice Chatbot with Nvidia Riva + Llama2

**Image Generation**
- Local LLM Text-to-Image on reComputer

**Audio Generation**
- Speech Subtitle Generation on Jetson
- Deploy Whisper on Jetson Orin for real-time STT

**Multimodal**
- Run VLM on reComputer with Jetson Platform Services

**Retrieval Augmented Generation (RAG)**
- Local AI Assistant with Ollama + AnythingLLM
- Local RAG with LlamaIndex on Jetson

**Other**
- Fine-tune LLM with Llama-Factory on Jetson
- Quantized Llama2-7B with MLC LLM on Jetson Orin NX
- Zero-Shot Detection on reComputer
- Format LLM Output with Langchain on Jetson

`[OK]` — once the user selects a topic, direct them to the corresponding skill or wiki link.

---

## Phase 2 — Deploy jetson-examples (common entry point)

Many Generative AI applications on Jetson use the `jetson-examples` package for one-line deployment:

```bash
pip3 install jetson-examples
sudo reboot
```

After reboot, deploy the chosen application:

```bash
reComputer run <application-name>
```

`[OK]` when the application container starts and the service is accessible.

> For the full list of applications, wiki links, and detailed tutorials for each topic, see `references/source.body.md`.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `pip3 install jetson-examples` fails | Ensure Python3 and pip3 are installed. Try `sudo apt install python3-pip`. |
| `reComputer run` fails | Check Docker is installed and running. Verify internet connectivity. Check disk space. |
| OOM during model loading | Use a smaller model variant. Ensure no other heavy processes are running. Check available RAM with `free -h`. |
| Application not listed in jetson-examples | Check the jetson-examples GitHub for the latest supported applications. Some may require manual Docker setup. |

---

## Reference files

- `references/source.body.md` — full original Seeed index page with links to all Generative AI tutorials, screenshots, and application descriptions (reference only)
