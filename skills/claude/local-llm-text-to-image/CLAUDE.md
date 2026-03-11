---
name: local-llm-text-to-image
description: Run local text-to-image generation on Jetson Orin NX 16GB using Stable Diffusion. Covers three approaches — KerasCV, Hugging Face diffusers, and NVIDIA Jetson Containers (AUTOMATIC1111 WebUI). Includes a Flask API for on-demand image generation. Requires JetPack 5.1.1+.
---

# Text-to-Image with Stable Diffusion on Jetson

Generate images from text prompts locally on Jetson using Stable Diffusion. Three deployment paths: KerasCV with TensorFlow, Hugging Face diffusers with PyTorch, and NVIDIA's containerized AUTOMATIC1111 WebUI.

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
| Hardware | Jetson Orin NX 16GB (e.g. reComputer J4012) |
| JetPack | 5.1.1+ |
| Storage | ~20 GB free (models are large) |
| RAM tips | Disable desktop GUI to save ~800 MB. Consider disabling ZRAM and using swap. |

---

## Path A — KerasCV Stable Diffusion

### Phase A1 — Create virtual environment and install TensorFlow (~10 min)

```bash
sudo apt install python3.8-venv
python3 -m venv kerasStableEnvironment
source kerasStableEnvironment/bin/activate
cd kerasStableEnvironment
pip install -U pip
pip install -U numpy grpcio absl-py py-cpuinfo psutil portpicker six mock requests gast h5py astor termcolor protobuf keras-applications keras-preprocessing wrapt google-pasta setuptools testresources
```

Install TensorFlow for your JetPack version (example for JP 5.1.1):

```bash
pip install --extra-index-url https://developer.download.nvidia.com/compute/redist/jp/v511 tensorflow==2.12.0+nv23.05
```

Verify:

```bash
python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"
```

`[OK]` when GPU device is listed.

### Phase A2 — Install PyTorch and KerasCV (~5 min)

```bash
sudo apt install libopenblas-dev
pip install --no-cache https://developer.download.nvidia.com/compute/redist/jp/v511/pytorch/torch-2.0.0+nv23.05-cp38-cp38-linux_aarch64.whl
pip install keras-cv==0.5.1 keras==2.12.0 Pillow
```

Verify PyTorch CUDA:

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

`[OK]` when both return True/GPU.

### Phase A3 — Generate an image (~2–5 min)

```bash
cat > generate_image.py << 'PYEOF'
import keras_cv
import keras
from PIL import Image

keras.mixed_precision.set_global_policy("mixed_float16")
model = keras_cv.models.StableDiffusion(img_width=512, img_height=512, jit_compile=True)
prompt = "a cute magical flying dog, fantasy art, golden color, high quality"
image = model.text_to_image(prompt, num_steps=25, batch_size=1)
Image.fromarray(image[0]).save("keras_generate_image.png")
print("Image saved: keras_generate_image.png")
PYEOF
python generate_image.py
```

`[OK]` when `keras_generate_image.png` is created.

---

## Path B — Hugging Face Diffusers

### Phase B1 — Create virtual environment and install PyTorch (~5 min)

```bash
python3 -m venv huggingfaceTesting
source huggingfaceTesting/bin/activate
cd huggingfaceTesting
sudo apt install libopenblas-dev
pip install --no-cache https://developer.download.nvidia.com/compute/redist/jp/v511/pytorch/torch-2.0.0+nv23.05-cp38-cp38-linux_aarch64.whl
pip install diffusers transformers accelerate
```

`[OK]` when all packages install.

### Phase B2 — Generate with Stable Diffusion v1.5 (~5–10 min first run)

```bash
cat > stableDiffusion.py << 'PYEOF'
from diffusers import StableDiffusionPipeline
import torch

model_id = "runwayml/stable-diffusion-v1-5"
pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=torch.float16)
pipe = pipe.to("cuda")
prompt = "a master jedi cat in star wars holding a lightsaber, cinematic lighting"
image = pipe(prompt).images[0]
image.save("cat_jedi.png")
print("Image saved: cat_jedi.png")
PYEOF
python stableDiffusion.py
```

First run downloads model checkpoints (~4 GB).

`[OK]` when `cat_jedi.png` is created.

### Phase B3 — Try SDXL-Turbo (optional, faster)

```bash
cat > sdxl_turbo.py << 'PYEOF'
from diffusers import AutoPipelineForText2Image
import torch

pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16")
pipe.to("cuda")
prompt = "full body, cat dressed as a Viking, with weapon, hyper-detail, cinematic"
image = pipe(prompt=prompt, num_inference_steps=1, guidance_scale=0.0).images[0]
image.save("sdxl-turbo.png")
print("Image saved: sdxl-turbo.png")
PYEOF
python sdxl_turbo.py
```

`[OK]` when image is generated (~30 s).

---

## Path C — NVIDIA Jetson Containers (AUTOMATIC1111 WebUI)

### Phase C1 — Install Jetson Containers (~3 min)

```bash
git clone https://github.com/dusty-nv/jetson-containers
cd jetson-containers
sudo apt update
sudo apt install -y python3-pip
pip3 install -r requirements.txt
```

`[OK]` when requirements install.

### Phase C2 — Run Stable Diffusion WebUI container (~10–20 min first run)

```bash
cd jetson-containers
./run.sh $(./autotag stable-diffusion-webui)
```

Accept the container pull when prompted. The container downloads the model and starts the WebUI on port 7860.

Open browser: `http://<jetson-ip>:7860`

`[OK]` when the AUTOMATIC1111 WebUI loads with a checkpoint selected.
`[STOP]` if no checkpoint appears — check disk space with `df -h`.

### Phase C3 — Add Stable Diffusion XL model (optional)

```bash
CONTAINERS_DIR=~/jetson-containers
MODEL_DIR=$CONTAINERS_DIR/data/models/stable-diffusion/models/Stable-diffusion/
sudo chown -R $USER $MODEL_DIR
wget -P $MODEL_DIR https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors
```

Refresh the checkpoint dropdown in the WebUI.

`[OK]` when SDXL model appears in the dropdown.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| TensorFlow GPU not detected | Verify JetPack version matches TF wheel. Check CUDA: `nvcc --version`. |
| PyTorch `torch.cuda.is_available()` returns False | Reinstall PyTorch wheel matching your JetPack. Check `nvidia-smi`. |
| OOM during image generation | Reduce image size (e.g. 256x256). Disable desktop GUI. Enable swap. |
| Model download fails | Check disk space: `df -h`. Clear cache: `rm -rf ~/.cache/huggingface`. |
| AUTOMATIC1111 no checkpoint | Disk full. Free space and restart container. |
| Container gets killed | Not enough RAM/swap. Add swap: `sudo fallocate -l 8G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`. |
| Flask API not accessible | Check firewall: `sudo ufw allow 8080`. Verify Flask is running on 0.0.0.0. |
| `pip install keras-cv` fails | Check Python version matches (3.8 for JP 5.1.1). Try `pip install --no-cache-dir`. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with all three deployment paths, Flask API code, screenshots, and additional model examples from Civitai (reference only)
