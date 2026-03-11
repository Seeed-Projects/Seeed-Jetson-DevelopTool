---
name: yolov26-jetson-setup
description: Set up the YOLOv26 dual USB camera system on NVIDIA Jetson (JetPack 6.0+). Installs GPU-enabled torch 2.8, torchvision 0.23 with CUDA NMS support, onnxruntime-gpu 1.23, and ultralytics, then validates TensorRT engine compatibility. Use when the user asks to install, rebuild, or fix YOLOv26 on Jetson.
---

# YOLOv26 Jetson Setup (Dual USB Camera / TensorRT)

---

## Execution model

Run the install script **one phase at a time**. After each phase:
- Relay the output to the user (show `[install]` lines)
- If it printed `[STOP]` → stop, follow the failure decision tree below
- If it ended with `[install] Phase ... done.` or `[OK]` → proceed to next phase

> **Why phases?** The torch/torchvision download is ~900 MB and takes 15–25 min.
> Running everything in one call risks silent timeout. Phases give the user
> visibility and a recovery point at each step.

---

## Phase commands

Replace `<ENV>` with the env name the user requested (default: `yolov26`).
All phases use the same script — the script is idempotent; already-done steps
are skipped automatically.

### Phase 1 — Environment + clone  (fast, ~1 min)
```bash
bash ~/.agents/skills/yolov26_jetson_fixed/scripts/install_yolov26.sh \
  --env <ENV> --phase env
```

### Phase 2 — Download wheels  (slow, 15–25 min, shows % progress)
```bash
bash ~/.agents/skills/yolov26_jetson_fixed/scripts/install_yolov26.sh \
  --env <ENV> --phase download
```

### Phase 3 — Install torch + verify CUDA  (fast, ~2 min)
```bash
bash ~/.agents/skills/yolov26_jetson_fixed/scripts/install_yolov26.sh \
  --env <ENV> --phase torch-pre
```

### Phase 4 — onnxruntime / numpy / opencv + ultralytics  (medium, ~8 min)
```bash
bash ~/.agents/skills/yolov26_jetson_fixed/scripts/install_yolov26.sh \
  --env <ENV> --phase deps
```

### Phase 5 — Reinstall torch + validate CUDA NMS  (fast, ~3 min)
```bash
bash ~/.agents/skills/yolov26_jetson_fixed/scripts/install_yolov26.sh \
  --env <ENV> --phase torch-post
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

## After all phases pass — Camera setup

```bash
# Add user to video group
if ! id -nG | grep -qw video; then sudo usermod -aG video $USER; fi

# Create udev rules for USB cameras (takes effect immediately)
if [[ ! -f /etc/udev/rules.d/99-usb-cameras.rules ]]; then
  sudo tee /etc/udev/rules.d/99-usb-cameras.rules > /dev/null <<'EOF'
KERNEL=="video[0-9]*", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="046d", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="05a3", MODE="0666"
EOF
  sudo udevadm control --reload-rules && sudo udevadm trigger
fi
```

## After all phases pass — Export TensorRT engines

Models are stored in `~/ultralytics_data/`. Export once per device (takes ~5 min each):

```bash
conda activate <ENV>
cd ~/ultralytics_data

# Detection engine
yolo export model=yolo26n.pt format=engine device=0 half=True

# Pose estimation engine
yolo export model=yolo26n-pose.pt format=engine device=0 half=True

# Segmentation engine
yolo export model=yolo26n-seg.pt format=engine device=0 half=True
```

## After all phases pass — Run the system

```bash
conda activate <ENV>
cd ~/yolov26_jetson

# Optional: maximum performance
sudo nvpmodel -m 0 && sudo jetson_clocks

# Launch dual camera system
bash run_dual_camera_local.sh
```

---

## Reference files

- `references/conflict_resolution_playbook.md` — F1–F7 fix playbook
- `references/yolov26_jetson_setup.md`           — detailed install notes
- `references/jetpack_compatibility_matrix.json` — version gates
- `references/dependency_mapping_rules.md`       — install order rules
