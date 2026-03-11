---
name: deepseek-quick-deploy
description: "Quickly deploy DeepSeek-R1 on Jetson using Ollama. Two-command setup. Requires Jetson with >8GB RAM and JetPack 5.1.1+."
---

# DeepSeek-R1 Quick Deploy on Jetson

> Hardware required: Jetson with >8GB RAM, JetPack 5.1.1+. This is the fastest path to running DeepSeek-R1 locally. For optimized MLC-based deployment with better throughput, see the `deploy-deepseek-mlc` skill instead.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all command output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree below.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| RAM | >8 GB (unified memory) |
| JetPack | 5.1.1 or later |
| Internet | Required for install script and model download |
| Disk space | ≥10 GB free for model weights |

---

## Phase 1 — Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify:

```bash
ollama --version
# Expected: ollama version x.x.x
```

`[OK]` when `ollama --version` prints a version string. `[STOP]` if the install script fails — see failure decision tree.

---

## Phase 2 — Run DeepSeek-R1

```bash
ollama run deepseek-r1
```

The first run downloads the model weights (~4–8 GB depending on quantization). Subsequent runs start immediately from cache.

Expected: after download, an interactive prompt appears:

```
>>> Send a message (/? for help)
```

Test with a simple prompt to confirm the model responds. Type `/bye` to exit.

`[OK]` when the model responds to a prompt. `[STOP]` if the process is killed or hangs — see failure decision tree.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `curl` install script fails with network error | Check internet connectivity. If behind a proxy, set `https_proxy` env var before running curl. Try downloading the script manually and inspecting it. |
| `curl` install script fails with permission error | Run with `sudo` or ensure `/usr/local/bin` is writable. |
| Model download stalls or fails mid-way | Retry `ollama run deepseek-r1` — Ollama resumes partial downloads. Check available disk space: `df -h`. |
| Process killed during model pull (OOM) | Not enough RAM. Free memory by stopping other processes, or use a smaller quantization: `ollama run deepseek-r1:1.5b`. |
| Model loads but inference is very slow | Expected on smaller Jetson modules. For better performance use the `deploy-deepseek-mlc` skill which uses MLC-optimized kernels. |
| `ollama: command not found` after install | Add Ollama to PATH: `export PATH=$PATH:/usr/local/bin`, then reload shell or open a new terminal. |

---

## Reference files

- `references/source.body.md` — full source tutorial with additional context (reference only)
