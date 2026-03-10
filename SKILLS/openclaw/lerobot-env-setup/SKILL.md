---
name: lerobot-env-setup
description: Set up the LeRobot environment on NVIDIA Jetson (SO-ARM / JetPack 6.0+). Installs Seeed-fork LeRobot with GPU-enabled torch 2.8, pinned numpy 1.26, OpenCV 4.10, and resolves the torch-overwrite trap from editable install. Use when the user asks to install, rebuild, or fix LeRobot on Jetson.
---

# LeRobot Environment Setup (Jetson / SO-ARM)

---

## Execution model

Run the install script **one phase at a time**. After each phase:
- Relay the output to the user (show `[install]` lines)
- If it printed `[STOP]` → stop, follow the failure decision tree below
- If it ended with `[install] Step N:` or `[OK]` → proceed to next phase

> **Why phases?** The torch download is ~254 MB and takes 10–20 min.
> Running everything in one call risks silent timeout. Phases give the user
> visibility and a recovery point at each step.

---

## Phase commands

Replace `<ENV>` with the env name the user requested (default: `lerobot`).
All phases use the same script — the script is idempotent; already-done steps
are skipped automatically.

### Phase 1 — Environment + clone  (fast, ~1 min)
```bash
bash ~/.agents/skills/lerobot-env-setup/scripts/install_lerobot.sh \
  --env <ENV> --robot-type so-arm --phase env
```

### Phase 2 — Download wheels  (slow, 10–20 min, shows % progress)
```bash
bash ~/.agents/skills/lerobot-env-setup/scripts/install_lerobot.sh \
  --env <ENV> --robot-type so-arm --phase download
```

### Phase 3 — Install torch + verify CUDA  (fast, ~2 min)
```bash
bash ~/.agents/skills/lerobot-env-setup/scripts/install_lerobot.sh \
  --env <ENV> --robot-type so-arm --phase torch-pre
```

### Phase 4 — opencv / ffmpeg / numpy + lerobot editable  (medium, ~5 min)
```bash
bash ~/.agents/skills/lerobot-env-setup/scripts/install_lerobot.sh \
  --env <ENV> --robot-type so-arm --phase deps
```

### Phase 5 — Reinstall torch + validate  (fast, ~2 min)
```bash
bash ~/.agents/skills/lerobot-env-setup/scripts/install_lerobot.sh \
  --env <ENV> --robot-type so-arm --phase torch-post
```

---

## Failure decision tree

| Output | Action |
|--------|--------|
| `[STOP] conda not found` | Ask user: "Please confirm miniconda is installed at ~/miniconda3 or give path" |
| `[STOP] conda env ... exists but has Python X.Y` | Should not happen (script auto-fixes). If seen, run `conda env remove -n <ENV>` then re-run phase 1 |
| `[STOP] torch wheel not found after download` | SharePoint URL expired. Ask user to re-share wheel files or place them manually in `~/wheels/` |
| `[STOP] torch.cuda.is_available() = False` | Wheel may be corrupt. Run: `rm ~/wheels/*.whl` then re-run phase 2 and 3 |
| `[FAIL] Some checks failed` | Read which line shows ✗, then check `references/conflict_resolution_playbook.md` for F1–F7 |
| Script hangs with no output >5 min | Report to user, ask whether to cancel and retry |

---

## After all phases pass — Serial port (SO-ARM only)

```bash
if dpkg -l brltty 2>/dev/null | grep -q '^ii'; then sudo apt remove brltty; fi
if ! id -nG | grep -qw dialout; then sudo usermod -aG dialout $USER; fi
if [[ ! -f /etc/udev/rules.d/99-serial-ports.rules ]]; then
  sudo tee /etc/udev/rules.d/99-serial-ports.rules > /dev/null <<'EOF'
KERNEL=="ttyUSB[0-9]*", MODE="0666"
KERNEL=="ttyACM[0-9]*", MODE="0666"
EOF
  sudo udevadm control --reload-rules && sudo udevadm trigger
fi
```

---

## Reference files

- `references/conflict_resolution_playbook.md` — F1–F7 fix playbook
- `references/lerobot_env_setup.md`            — detailed install notes
- `references/jetpack_compatibility_matrix.json` — version gates
- `references/dependency_mapping_rules.md`     — install order rules
