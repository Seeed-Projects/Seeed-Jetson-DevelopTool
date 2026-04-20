"""App registry for App Market."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).parent / "data"
_BASE_DATA = _DATA_DIR / "apps.json"
_GENERATED_DATA = _DATA_DIR / "jetson_examples.json"

_JX_BOOTSTRAP_CMD = (
    "bash -c 'export PATH=$HOME/.local/bin:$PATH && "
    "which reComputer >/dev/null 2>&1 || pip install jetson-examples'"
)

_DA3_RUN_CMDS = [
    "bash -lc 'set -e; echo [1/5] display auth precheck; DISP=${DISPLAY:-}; if [ -z \"$DISP\" ]; then if [ -S /tmp/.X11-unix/X99 ]; then DISP=:99; elif [ -S /tmp/.X11-unix/X1 ]; then DISP=:1; else DISP=:0; fi; fi; echo \"[info] use DISPLAY=$DISP\"; if [ \"$DISP\" = \":99\" ]; then echo \"[info] headless VNC display :99 detected\"; elif test -f $HOME/.Xauthority; then echo \"[ok] ~/.Xauthority found\"; else echo \"[warn] ~/.Xauthority not found; RViz may fail in GUI mode\"; fi'",
    "bash -lc 'echo; echo \"[2/5] optional swap (run manually only if engine build fails due to OOM)\"; echo \"sudo mkdir -p /mnt/nvme\"; echo \"sudo fallocate -l 16G /mnt/nvme/swapfile\"; echo \"sudo chmod 600 /mnt/nvme/swapfile\"; echo \"sudo mkswap /mnt/nvme/swapfile\"; echo \"sudo swapon /mnt/nvme/swapfile\"; echo'",
    "bash -lc 'set -e; echo \"[3/5] start tutorial container + run GUI preview in background xauth mode\"; DISP=${DISPLAY:-}; if [ -z \"$DISP\" ]; then if [ -S /tmp/.X11-unix/X99 ]; then DISP=:99; elif [ -S /tmp/.X11-unix/X1 ]; then DISP=:1; else DISP=:0; fi; fi; XAUTH=\"\"; XAUTH_ENV=\"\"; XAUTH_MOUNT=\"\"; if [ \"$DISP\" != \":99\" ]; then XAUTH=/run/user/1000/gdm/Xauthority; if [ ! -f \"$XAUTH\" ]; then XAUTH=/home/seeed/.Xauthority; fi; if [ -f \"$XAUTH\" ]; then XAUTH_ENV=\"-e XAUTHORITY=$XAUTH\"; XAUTH_MOUNT=\"-v $XAUTH:$XAUTH:ro\"; fi; fi; pick_cam(){ for d in /dev/video0 /dev/video3 /dev/video1 /dev/video2; do [ -e \"$d\" ] || continue; if timeout 3s v4l2-ctl -d \"$d\" --stream-mmap --stream-count=1 --stream-to=/tmp/cam_probe.raw >/dev/null 2>&1; then echo ${d#/dev/video}; return 0; fi; done; echo 0; }; CAM=$(pick_cam); echo \"[info] start container with DISPLAY=$DISP XAUTH=${XAUTH:-none} CAMERA_ID=$CAM\"; sudo docker rm -f depth_anything_v3 >/dev/null 2>&1 || true; sudo docker run -d --name depth_anything_v3 --restart unless-stopped --runtime=nvidia --network host --ipc host --privileged -e DISPLAY=$DISP $XAUTH_ENV -e CAMERA_ID=$CAM -e QT_X11_NO_MITSHM=1 -e LIBGL_ALWAYS_SOFTWARE=1 -v /tmp/.X11-unix:/tmp/.X11-unix $XAUTH_MOUNT -v /dev:/dev chenduola6/depth_anything_v3:jp6.2 bash -lc \"set -e; cd /workspace/ros2-depth-anything-v3-trt; source install/setup.bash; if ls onnx/*.engine >/dev/null 2>&1; then printf \\\"[skip] engine already exists\\\\n\\\"; else printf \\\"[info] first run building TensorRT engine, this can take several minutes\\\\n\\\"; ros2 run depth_anything_v3 generate_engines onnx; fi; exec ./run_camera_depth.sh\"; sudo docker ps -a --filter name=depth_anything_v3'",
    "bash -lc 'echo \"[4/5] show depth_anything_v3 status (if started by reComputer path)\"; sudo docker ps -a --filter name=depth_anything_v3'",
    "bash -lc 'echo \"[5/5] follow logs for 120s\"; timeout 120s sudo docker logs -f depth_anything_v3 2>&1 || true; echo \"[hint] if still building engine, rerun Run and keep logs open\"'",
]


def _read_apps(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _prepend_bootstrap(app: dict) -> dict:
    """For jetson-examples apps, prepend reComputer bootstrap to install/run cmds."""
    if app.get("id") == "jx-depth-anything-v3":
        app["run_cmds"] = _DA3_RUN_CMDS[:]
    for key in ("install_cmds", "run_cmds"):
        cmds = app.get(key)
        if cmds and any("reComputer" in c for c in cmds):
            app[key] = [_JX_BOOTSTRAP_CMD] + cmds
    return app


def load_apps() -> list[dict]:
    """Load built-in apps and generated jetson-examples apps."""
    apps = _read_apps(_BASE_DATA)
    if not apps:
        apps = list(_DEFAULT_APPS)

    by_id = {app["id"]: app for app in apps}
    for app in _read_apps(_GENERATED_DATA):
        by_id[app["id"]] = _prepend_bootstrap(app)
    return list(by_id.values())


def get_app(app_id: str) -> Optional[dict]:
    return next((a for a in load_apps() if a["id"] == app_id), None)


_DEFAULT_APPS = [
    {
        "id": "yolov8",
        "icon": "CV",
        "name": "YOLOv8 Object Detection",
        "category": "CV / Vision",
        "desc": "Real-time object detection for Jetson devices.",
        "skill_id": None,
        "check_cmd": "python3 -c 'import ultralytics' 2>/dev/null",
        "install_cmds": [
            "pip3 install ultralytics",
            "python3 -c 'import ultralytics; print(\"YOLOv8:\", ultralytics.__version__)'",
        ],
    },
    {
        "id": "qwen2",
        "icon": "LLM",
        "name": "Qwen2 Local Inference",
        "category": "LLM",
        "desc": "Local Qwen2 inference optimized for Jetson.",
        "skill_id": "qwen_demo",
        "check_cmd": "python3 -c 'import transformers' 2>/dev/null",
        "install_cmds": None,
    },
    {
        "id": "lerobot",
        "icon": "BOT",
        "name": "LeRobot",
        "category": "Robotics",
        "desc": "LeRobot toolkit for robot control and imitation learning.",
        "skill_id": "lerobot",
        "check_cmd": "python3 -c 'import lerobot' 2>/dev/null",
        "install_cmds": None,
    },
]
