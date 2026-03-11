---
name: finetune-llm-llama-factory
description: Fine-tune LLMs on Jetson using Llama-Factory via jetson-examples one-line deployment. Covers installation, WebUI-based training with alpaca_zh dataset on Phi-1.5, and testing the fine-tuned model. Requires Jetson with ≥16GB RAM.
---

# Fine-tune LLM with Llama-Factory on Jetson

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
| Hardware | Jetson device with ≥16GB RAM (tested on Orin NX 16GB and AGX Orin 64GB) |
| Peripherals | Monitor, mouse, keyboard, network (optional but recommended) |
| JetPack | 5.x or 6.x |
| Internet | Required for initial container pull |

---

## Phase 1 — Install jetson-examples (~2 min)

```bash
pip3 install jetson-examples
sudo reboot
```

`[OK]` after reboot completes and you can log back in.

---

## Phase 2 — Deploy Llama-Factory (~5–15 min)

Launch Llama-Factory using the one-line deployment:

```bash
reComputer run llama-factory
```

This pulls the container and starts the Llama-Factory service.

Once running, open a web browser and navigate to:

```
http://127.0.0.1:7860
```

(Or replace `127.0.0.1` with the Jetson's IP for remote access.)

`[OK]` when the Llama-Factory WebUI loads in the browser. `[STOP]` if the container fails to start.

---

## Phase 3 — Start training (~18 hours for default config)

In the WebUI:
1. Set Model name to `Phi-1.5` (or your chosen model)
2. Set Dataset to `alpaca_zh` (or your chosen dataset)
3. Keep other training parameters as default
4. Click the `Start` button

Monitor training progress in the WebUI.

`[OK]` when training completes and the fine-tuned model appears in the save directory.

---

## Phase 4 — Test the fine-tuned model (~2 min)

In the Llama-Factory WebUI:
1. Navigate to the Chat tab
2. Load the fine-tuned model by selecting the checkpoint path
3. Enter a prompt in the Input text box (e.g. a Chinese language prompt if using alpaca_zh)
4. Click Submit and check the output in the Chatbot text box

`[OK]` when the model responds with coherent output reflecting the fine-tuning data.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `pip3 install jetson-examples` fails | Check Python3 and pip3 are installed. Try `sudo apt install python3-pip` first. |
| `reComputer run llama-factory` fails | Check internet connectivity. Ensure Docker is installed and running. Check available disk space. |
| WebUI not accessible at port 7860 | Verify the container is running with `docker ps`. Check firewall rules. Try `http://<jetson-ip>:7860`. |
| OOM during training | Model too large for available RAM. Use a smaller model or reduce batch size in training parameters. |
| Training stalls or crashes | Check GPU temperature with `jtop`. Ensure adequate cooling. Reduce training parameters. |
| Fine-tuned model produces poor results | Use more diverse fine-tuning data. Increase training epochs. Check dataset quality. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with screenshots, video demo, and detailed WebUI configuration (reference only)
