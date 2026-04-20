---
name: llm-interface-control
description: Deploy a local LLM agent on Jetson Orin NX that translates natural language into structured JSON commands for hardware interface control (GPIO, PWM, I2C). Uses Ollama with a custom system prompt, FastAPI backend, and confidence-gated execution. Requires JetPack and Python 3.8+.
---

# Local LLM Agent for Hardware Interface Control on Jetson

Use a local LLM running on Jetson to translate natural language commands into structured JSON for controlling hardware interfaces (lights, fans, thermostats, speakers) via GPIO, PWM, and I2C. The system uses Ollama with a custom prompt, FastAPI for the API layer, and confidence-based safety gating.

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
| Hardware | NVIDIA Jetson (Orin NX recommended) with JetPack |
| Python | 3.8+ |
| LLM Server | Ollama (installed in Phase 1) |
| Network | Local access for API calls |

---

## Phase 1 — Install Ollama (~2 min)

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify:

```bash
ollama --version
```

`[OK]` when Ollama version is printed.
`[STOP]` if install fails — check network connectivity.

---

## Phase 2 — Clone the project and install dependencies (~2 min)

```bash
git clone https://github.com/kouroshkarimi/llm_interface_controll.git
cd llm_interface_controll
pip install -r requirements.txt
```

`[OK]` when all packages install (FastAPI, uvicorn, etc.).
`[STOP]` if pip fails — check Python version.

---

## Phase 3 — Create the custom Ollama model (~2 min)

The project includes a system prompt file that constrains the LLM to output only structured JSON with fields: intent, device, action, location, parameters, confidence.

```bash
cd llm_interface_controll
ollama create jetson-controller -f models/jetson-controller.txt
```

Verify:

```bash
ollama list | grep jetson-controller
```

`[OK]` when `jetson-controller` appears in the model list.
`[STOP]` if creation fails — ensure the base model (llama3.2:1b) is available: `ollama pull llama3.2:1b`.

---

## Phase 4 — Start the FastAPI server (~1 min)

```bash
cd llm_interface_controll
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`[OK]` when uvicorn prints "Application startup complete".

---

## Phase 5 — Test command execution (~1 min)

In a separate terminal, send a test command:

```bash
curl -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{"text": "Turn on the kitchen lights"}'
```

Expected response: JSON with `intent: "control_device"`, `device: "lights"`, `action: "turn_on"`, `location: "kitchen"`, `confidence: >0.8`.

Test a query:

```bash
curl -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{"text": "What is the temperature in the bedroom?"}'
```

Expected: `intent: "query_status"`, `device: "thermostat"`.

Test rejection of off-topic input:

```bash
curl -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{"text": "Write me a poem about the ocean"}'
```

Expected: `intent: "unknown"`, `confidence: 0.0`.

`[OK]` when all three tests return properly structured JSON.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Ollama install fails | Check internet. Try manual download from ollama.com. |
| `ollama create` fails | Ensure base model is pulled: `ollama pull llama3.2:1b`. Check `models/jetson-controller.txt` exists. |
| FastAPI won't start | Check port 8000 not in use: `ss -tlnp \| grep 8000`. Verify requirements installed. |
| LLM returns non-JSON output | The system prompt may not be loaded. Recreate: `ollama create jetson-controller -f models/jetson-controller.txt`. |
| Low confidence on valid commands | Adjust temperature in `app/llm_agent.py`. Try a larger base model. |
| GPIO/hardware errors | Mock hardware during development. Ensure Jetson GPIO permissions: `sudo usermod -aG gpio $USER`. |
| Connection refused on port 8000 | Firewall: `sudo ufw allow 8000`. Verify uvicorn is running. |

---

## Reference files

- `references/source.body.md` — Full project documentation with architecture details, JSON schema specification, customization guide, and safety constraints (reference only)
