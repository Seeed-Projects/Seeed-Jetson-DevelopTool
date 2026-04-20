---
name: ultralytics-jetson-setup
description: Set up the Ultralytics YOLO environment on NVIDIA Jetson (JetPack 6.0+) for YOLOv8, YOLOv11, or YOLOv26. Installs GPU-enabled torch 2.8, torchvision with CUDA NMS support, onnxruntime-gpu, and ultralytics, then validates TensorRT engine compatibility. Use when the user asks to install, deploy, or fix any YOLO model (v8 / v11 / v26) on Jetson.
---

# Ultralytics YOLO Jetson Setup (YOLOv8 / YOLOv11 / YOLOv26)

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

Replace `<ENV>` with the env name the user requested (default: `ultralytics`).
Replace `<FAMILY>` with the model family: `yolov8` | `yolo11` | `yolo26` (default: `yolo11`).
All phases use the same script — the script is idempotent; already-done steps
are skipped automatically.

### Phase 1 — Environment + setup  (fast, ~1 min)
```bash
bash ~/.agents/skills/ultralytics-jetson-setup/scripts/install_ultralytics.sh \
  --env <ENV> --model-family <FAMILY> --phase env
```

### Phase 2 — Download wheels  (slow, 15–25 min, shows % progress)
```bash
bash ~/.agents/skills/ultralytics-jetson-setup/scripts/install_ultralytics.sh \
  --env <ENV> --model-family <FAMILY> --phase download
```

### Phase 3 — Install torch + verify CUDA  (fast, ~2 min)
```bash
bash ~/.agents/skills/ultralytics-jetson-setup/scripts/install_ultralytics.sh \
  --env <ENV> --model-family <FAMILY> --phase torch-pre
```

### Phase 4 — onnxruntime / numpy / opencv + ultralytics  (medium, ~8 min)
```bash
bash ~/.agents/skills/ultralytics-jetson-setup/scripts/install_ultralytics.sh \
  --env <ENV> --model-family <FAMILY> --phase deps
```

### Phase 5 — Reinstall torch + validate CUDA NMS  (fast, ~3 min)
```bash
bash ~/.agents/skills/ultralytics-jetson-setup/scripts/install_ultralytics.sh \
  --env <ENV> --model-family <FAMILY> --phase torch-post
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

---

## After all phases pass — Model download & TensorRT engine export

### YOLOv8
```bash
conda activate <ENV>
mkdir -p ~/ultralytics_data && cd ~/ultralytics_data

# Download .pt models (auto-downloads on first use)
python3 -c "from ultralytics import YOLO; YOLO('yolov8n.pt'); YOLO('yolov8n-pose.pt'); YOLO('yolov8n-seg.pt')"

# Export TensorRT engines (~3-5 min each)
yolo export model=yolov8n.pt      format=engine device=0 half=True
yolo export model=yolov8n-pose.pt format=engine device=0 half=True
yolo export model=yolov8n-seg.pt  format=engine device=0 half=True
```

### YOLOv11
```bash
conda activate <ENV>
mkdir -p ~/ultralytics_data && cd ~/ultralytics_data

python3 -c "from ultralytics import YOLO; YOLO('yolo11n.pt'); YOLO('yolo11n-pose.pt'); YOLO('yolo11n-seg.pt')"

yolo export model=yolo11n.pt      format=engine device=0 half=True
yolo export model=yolo11n-pose.pt format=engine device=0 half=True
yolo export model=yolo11n-seg.pt  format=engine device=0 half=True
```

### YOLOv26
```bash
conda activate <ENV>
# Models are in ~/yolov26_jetson/ultralytics_data/ (cloned in phase 1)
cd ~/ultralytics_data

yolo export model=yolo26n.pt      format=engine device=0 half=True
yolo export model=yolo26n-pose.pt format=engine device=0 half=True
yolo export model=yolo26n-seg.pt  format=engine device=0 half=True
```

---

## After all phases pass — Run inference

```bash
conda activate <ENV>

# Quick inference test on an image
python3 -c "
from ultralytics import YOLO
model = YOLO('~/ultralytics_data/yolov8n.engine')   # or yolo11n / yolo26n
results = model('path/to/image.jpg', device=0)
results[0].show()
"

# Optional: maximum Jetson performance
sudo nvpmodel -m 0 && sudo jetson_clocks
```

---

## Reference files

- `references/conflict_resolution_playbook.md` — F1–F7 fix playbook
- `references/ultralytics_jetson_setup.md`     — detailed install notes
- `references/jetpack_compatibility_matrix.json` — version gates
- `references/dependency_mapping_rules.md`     — install order rules
