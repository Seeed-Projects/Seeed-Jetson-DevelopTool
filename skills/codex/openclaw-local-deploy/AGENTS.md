---
name: openclaw-local-deploy
description: Deploy Codex (Clawdbot) locally on reComputer Jetson with Ollama for a self-contained AI control hub. Covers Ollama installation, model pulling, Codex setup, and local model configuration. Requires Jetson with ≥16GB RAM and JetPack 6.2.
---

# Local OpenClaw (Clawdbot) on reComputer Jetson with Ollama

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
| Hardware | reComputer Jetson series (e.g., reComputer Robotics J5011) |
| RAM | ≥ 16 GB |
| JetPack | 6.2 pre-installed |
| Storage | NVMe SSD recommended for faster model loading |
| Network | Stable internet for initial setup |
| Optional | Discord Bot Token (or WhatsApp — not mandatory) |

---

## Phase 1 — Preflight

Verify JetPack version, available RAM, and network.

```bash
cat /etc/nv_tegra_release
free -h
ping -c 3 ollama.com
```

Expected: R36.x (JP6.2), ≥16 GB RAM, ping succeeds. `[OK]` when all pass. `[STOP]` if RAM < 16 GB or no network.

---

## Phase 2 — Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify the local API is reachable:

```bash
curl http://localhost:11434/api/tags
```

Expected: JSON response with no errors. `[OK]` when API responds. `[STOP]` if connection refused.

---

## Phase 3 — Pull a local model

```bash
ollama pull qwen3-vl:2b
```

List installed models:

```bash
ollama list
```

Expected: `qwen3-vl:2b` appears in the list. `[OK]` when model is downloaded. `[STOP]` if download fails.

---

## Phase 4 — Install OpenClaw

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

The installer will enter a configuration wizard. You can skip the model configuration or temporarily set up a cloud model — the local model will be configured in the next phase.

`[OK]` when the setup wizard completes and OpenClaw is installed.

---

## Phase 5 — Configure OpenClaw for local Ollama model

Edit the OpenClaw configuration file to add the Ollama provider:

```bash
nano ~/.codex/openclaw.json
```

Add or modify the following sections in the JSON:

Under `"agents" > "defaults"`:
```json
"models": {"ollama":{}},
"model": {"primary": "ollama/qwen3-vl:2b"}
```

Under `"models" > "providers"`, add:
```json
"ollama":{
  "baseUrl": "http://127.0.0.1:11434/v1",
  "apiKey": "ollama-local",
  "api": "openai-completions",
  "models": [
    {
      "id": "qwen3-vl:2b",
      "name": "Qwen3 VL 2B",
      "reasoning": false,
      "input": ["text"],
      "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
      "contextWindow": 128000,
      "maxTokens": 8192
    }
  ]
}
```

See `references/source.body.md` for the complete configuration file example.

`[OK]` when the config file is saved with Ollama provider settings.

---

## Phase 6 — Restart OpenClaw and verify

```bash
openclaw gateway restart
```

Open the WebUI in the Jetson browser:

```
http://127.0.0.1:18789/
```

If the page shows an "unable to access" error, append the token from the config file:

```
http://127.0.0.1:18789/?token=<YOUR_TOKEN>
```

`[OK]` when the WebUI loads and responds to prompts using the local model.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| Ollama install script fails | Check internet. Verify `curl` is installed: `sudo apt install curl`. |
| `curl localhost:11434` connection refused | Ollama service not running. Try `ollama serve` in a separate terminal. |
| Model pull fails / slow | Check disk space: `df -h`. Ensure stable internet. Try `ollama pull` again. |
| OpenClaw install script fails | Verify Node.js 22+ is available. Check internet connectivity. |
| Config file syntax error | Validate JSON: `python3 -m json.tool ~/.codex/openclaw.json`. Fix trailing commas. |
| WebUI not loading | Check gateway is running: `openclaw gateway status`. Verify port 18789 is not blocked. |
| "unable to access" error on WebUI | Token authentication is enabled. Find token in `~/.codex/openclaw.json` under `gateway.auth.token` and append to URL. |
| Local model responses are poor | Adjust prompt settings or try a larger model (e.g., `qwen3-vl:8b`) if RAM allows. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with complete openclaw.json example, Discord integration, hardware photos, and effect demonstration video (reference only)
