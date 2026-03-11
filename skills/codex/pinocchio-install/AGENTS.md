---
name: pinocchio-install
description: Install the Pinocchio rigid-body dynamics library (stack-of-tasks/pinocchio) into a specified conda environment or a local Python venv. Supports conda (conda-forge), pip, and from-source (cmake) methods. Use when the user asks to install, set up, or build Pinocchio for robotics, MPC, or trajectory optimisation work.
---

# Pinocchio Install Skill

Pinocchio is a fast C++ library for rigid-body dynamics (FK/IK/Jacobians/derivatives)
with Python bindings. Source: https://github.com/stack-of-tasks/pinocchio

---

## Execution model

Run **one phase at a time**. After each phase:
- Relay all `[install]` lines to the user
- If output contains `[STOP]` → stop immediately, consult the failure decision tree
- If output ends with `[OK]` → tell the user "Phase N complete" and run the next phase

---

## Parameters

| Flag | Default | Notes |
|------|---------|-------|
| `--env <name>` | `pinocchio` | conda env name **or** `system` for system Python **or** `venv:<path>` for a virtualenv |
| `--method <m>` | `conda` | `conda` / `pip` / `source` |
| `--prefix <path>` | `~/.local` | cmake install prefix (source method only) |
| `--phase <p>` | `all` | `detect` / `deps` / `build` / `validate` / `all` |

**Ask the user for `--env` if they haven't specified a target.**
Default method: `conda` (fastest, works on x86-64 and most arm64 platforms).
Use `source` on Jetson / arm64 if conda pre-built binaries are unavailable.

---

## Phase commands

Replace `<ENV>` with the user's requested environment name.

### Phase 1 — detect  (fast, ~5 s)
Checks system architecture, Python, conda/venv, and whether pinocchio is already installed.
```bash
bash ~/.codex/skills/pinocchio-install/scripts/install_pinocchio.sh \
  --env <ENV> --method <METHOD> --phase detect
```

### Phase 2 — deps  (fast–medium, ~2–5 min)
Installs system-level and build-time dependencies (apt packages, cmake, eigen3, boost, eigenpy).
Skipped automatically when `--method conda` or `--method pip`.
```bash
bash ~/.codex/skills/pinocchio-install/scripts/install_pinocchio.sh \
  --env <ENV> --method <METHOD> --phase deps
```

### Phase 3 — build  (variable: conda ~2 min / pip ~1 min / source 10–30 min)
Runs the actual install: `conda install`, `pip install pin`, or cmake clone+build.
```bash
bash ~/.codex/skills/pinocchio-install/scripts/install_pinocchio.sh \
  --env <ENV> --method <METHOD> --prefix <PREFIX> --phase build
```

### Phase 4 — validate  (fast, ~15 s)
Imports pinocchio in the target env and runs a quick sanity check (creates a model, runs FK).
```bash
bash ~/.codex/skills/pinocchio-install/scripts/install_pinocchio.sh \
  --env <ENV> --method <METHOD> --prefix <PREFIX> --phase validate
```

---

## Failure decision tree

| Output | Action |
|--------|--------|
| `[STOP] conda not found` | Ask user to confirm Miniconda/Mamba path or use `--method pip` / `--method source` |
| `[STOP] conda env <name> already has pinocchio` | Tell user: pinocchio is already installed. Run validate to confirm. |
| `[STOP] pip install failed — unsupported platform` | pip wheels not available for this OS/arch. Retry with `--method source` |
| `[STOP] cmake not found` | Run: `sudo apt install cmake` then re-run phase deps |
| `[STOP] eigen3 missing` | Run: `sudo apt install libeigen3-dev` then re-run phase deps |
| `[STOP] eigenpy not found after deps` | See `references/build_troubleshooting.md` section B2 |
| `[STOP] git clone failed` | Check network. Re-run phase build (clone is idempotent). |
| `[STOP] cmake configure failed` | Check `references/build_troubleshooting.md` section B3 for missing deps |
| `[STOP] make failed` | Check compiler errors. See `references/build_troubleshooting.md` section B4 |
| `[STOP] import pinocchio failed` | PYTHONPATH not set. See `references/build_troubleshooting.md` section B5 |
| `[FAIL] sanity check failed` | Build incomplete. Re-run build phase or check B4 |
| No output for >10 min | Report to user; ask whether to cancel and retry with `-j2` (fewer parallel jobs) |

---

## After validate passes — activate the environment

**conda:**
```bash
conda activate <ENV>
python -c "import pinocchio; print(pinocchio.__version__)"
```

**venv:**
```bash
source <VENV_PATH>/bin/activate
python -c "import pinocchio; print(pinocchio.__version__)"
```

**source build (system / no env):**
```bash
export PYTHONPATH=<PREFIX>/lib/python3.x/site-packages:$PYTHONPATH
export LD_LIBRARY_PATH=<PREFIX>/lib:$LD_LIBRARY_PATH
python -c "import pinocchio; print(pinocchio.__version__)"
```
The script prints the exact export lines at the end of the validate phase.

---

## Reference files

- `references/install_notes.md`         — detailed per-method install notes and known issues
- `references/build_troubleshooting.md` — B1–B5 recovery playbook for source builds
