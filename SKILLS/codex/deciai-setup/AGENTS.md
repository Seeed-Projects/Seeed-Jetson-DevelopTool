---
name: deciai-setup
description: Set up the Deci AI platform on NVIDIA Jetson devices (Nano, Xavier NX, AGX Xavier, AGX Orin) for model optimization, benchmarking, and deployment. Covers Deci account creation, INFERY SDK installation, model zoo usage, custom model optimization via AutoNAC, and on-device performance benchmarking with ONNX/TensorRT. Requires JetPack 4.6.
---

# Getting Started with Deci AI on Jetson

Deci accelerates deep-learning inference 2–10× on any hardware via its AutoNAC compiler and INFERY runtime. This skill walks through account setup, model zoo exploration, custom model optimization, and on-device benchmarking on Jetson.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Jetson device | Nano, Xavier NX, TX2, AGX Xavier, or AGX Orin (Seeed reComputer or NVIDIA devkit) |
| JetPack | 4.6 |
| Python | 3.6+ with pip3 |
| Network | Internet access for Deci platform and NGC |
| Deci account | Free sign-up at https://console.deci.ai/sign-up |

---

## Phase 1 — System update and pip setup (~2 min)

```bash
sudo apt update
sudo apt install -y python3-pip
python3 -m pip install -U pip
```

`[OK]` when pip3 reports its version. `[STOP]` if apt or pip fails.

---

## Phase 2 — Create Deci account (manual, ~3 min)

1. Visit https://console.deci.ai/sign-up
2. Complete the registration form
3. Log in to Deci Lab — you should see the dashboard with the default ResNet50 Baseline model

`[OK]` when the user confirms they can see the Deci Lab dashboard.

---

## Phase 3 — Explore Model Zoo and optimize a model (manual, ~5–10 min)

In Deci Lab:
1. Click **Model Zoo** → **List** to browse pre-optimized models
2. Search for a model (e.g. `YOLOX`) to see base and hardware-optimized variants
3. To optimize a custom model: click **+ New Model** → select task → upload ONNX model → choose target hardware → set throughput goal → click **Start**
4. Wait for optimization to complete

`[OK]` when the optimized model appears in the dashboard.

---

## Phase 4 — Install INFERY on Jetson (~3 min)

```bash
sudo python3 -m pip install https://deci-packages-public.s3.amazonaws.com/infery_jetson-3.2.2-cp36-cp36m-linux_aarch64.whl
```

Verify:

```bash
python3 -c "import infery; print('INFERY installed')"
```

`[OK]` when import succeeds. `[STOP]` if the wheel download or install fails.

---

## Phase 5 — Deploy and benchmark model on Jetson (~5 min)

1. In Deci Lab, hover over your model → click **Deploy** → **Download model** to get the `.onnx` file
2. Copy the model file to the Jetson home directory
3. Load and benchmark:

```bash
python3 << 'EOF'
import infery, numpy as np

model = infery.load(model_path='<MODEL_FILE>.onnx', framework_type='onnx', inference_hardware='gpu')
print("Model loaded successfully")

result = model.benchmark(batch_size=1)
print(result)
EOF
```

Expected output includes `batch_inf_time`, `throughput`, and `memory` metrics.

`[OK]` when benchmark results are printed. `[STOP]` if model load or benchmark fails.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `pip install` fails with SSL or network error | Check internet connectivity. Retry with `--trusted-host pypi.org`. |
| INFERY wheel install fails — architecture mismatch | Confirm you are on aarch64 Jetson with Python 3.6. Check wheel URL matches your platform. |
| `import infery` fails | Verify pip installed to the correct Python: `python3 -m pip show infery`. |
| Model load fails — `framework_type` error | Ensure model format matches: use `onnx` for `.onnx` files, `trt` for TensorRT engines. |
| Benchmark OOM / killed | Model too large for device memory. Try a smaller model or reduce batch size. |
| Deci Lab optimization stuck | Check Deci status page. Re-upload model and retry. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with hardware list, screenshots, and detailed Deci Lab walkthrough (reference only)
