---
name: traffic-deepstream
description: Deploy an intelligent traffic management system using NVIDIA DeepStream SDK on Jetson devices, with DashCamNet for vehicle detection and VehicleTypeNet/VehicleMakeNet for classification. Tested on reComputer J1010 with JetPack 4.6.1.
---

# Traffic Management with DeepStream SDK

## Execution model

Run one phase at a time. After each phase, verify the expected result before continuing.
- If a phase succeeds → print `[OK]` and move to the next phase.
- If a phase fails → print `[STOP]`, consult the failure decision tree, and ask the user before retrying.

## Phase 1 — Verify prerequisites

Required:
- Jetson device with JetPack installed (tested on reComputer J1010 + JetPack 4.6.1)
- SDK Components and DeepStream SDK installed
- Keyboard, HDMI display
- USB webcam or MIPI CSI camera

```bash
cat /etc/nv_tegra_release
dpkg -l | grep deepstream
```

Expected: L4T version shown; DeepStream SDK package listed.

## Phase 2 — Download configuration files

```bash
git clone https://github.com/NVIDIA-AI-IOT/deepstream_reference_apps.git
cd deepstream_reference_apps/deepstream_app_tao_configs/
sudo cp -a * /opt/nvidia/deepstream/deepstream/samples/configs/tao_pretrained_models/
```

Expected: Config files copied to DeepStream samples directory.

## Phase 3 — Download pre-trained models

```bash
sudo apt install -y wget zip
cd /opt/nvidia/deepstream/deepstream/samples/configs/tao_pretrained_models/
sudo ./download_models.sh
```

Expected: DashCamNet, VehicleMakeNet, and VehicleTypeNet models downloaded.

## Phase 4 — Configure DeepStream application

Edit the configuration file:

```bash
cd /opt/nvidia/deepstream/deepstream/samples/configs/tao_pretrained_models/
sudo vi deepstream_app_source1_dashcamnet_vehiclemakenet_vehicletypenet.txt
```

Make these changes:

1. Under `[sink0]`, change `sync=1` to `sync=0`
2. Under `[primary-gie]`, set `model-engine-file=../../models/tao_pretrained_models/dashcamnet/resnet18_dashcamnet_pruned.etlt_b1_gpu0_fp16.engine`
3. Under `[secondary-gie0]`, set `model-engine-file=../../models/tao_pretrained_models/vehiclemakenet/resnet18_vehiclemakenet_pruned.etlt_b4_gpu0_fp16.engine`
4. Under `[secondary-gie1]`, set `model-engine-file=../../models/tao_pretrained_models/vehicletypenet/resnet18_vehicletypenet_pruned.etlt_b4_gpu0_fp16.engine`

## Phase 5 — Run the traffic management demo

Connect camera, keyboard, and HDMI display to the Jetson device.

```bash
cd /opt/nvidia/deepstream/deepstream/samples/configs/tao_pretrained_models/
sudo deepstream-app -c deepstream_app_source1_dashcamnet_vehiclemakenet_vehicletypenet.txt
```

Expected: Live video with vehicle detection, type classification, and make classification displayed on HDMI.

To try other demos:

```bash
sudo deepstream-app -c deepstream_app_source1_$MODEL.txt
```

## Failure decision tree

| Symptom | Likely cause | Suggested fix |
|---|---|---|
| `deepstream-app` not found | DeepStream SDK not installed | Install via NVIDIA SDK Manager |
| Model download fails | No internet or script error | Check connectivity; run `download_models.sh` manually |
| Engine file not found | First run needs TensorRT engine build | Wait for engine generation on first launch (may take several minutes) |
| No display output | Wrong sink type or sync setting | Verify `type=2` (EglSink) and `sync=0` in `[sink0]` |
| Camera not detected | Unsupported camera or wrong source config | Check `v4l2-ctl --list-devices`; update `[source0]` in config |
| Low FPS | GPU not fully utilized | Ensure `batch-size` is appropriate; check `tegrastats` for GPU usage |

## Reference files

- `references/source.body.md` — Full original wiki content (reference only)
