"""App registry for App Market."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Optional

from seeed_jetson_develop.modules.devices.diagnostics import python_module_check_cmd

_DATA_DIR = Path(__file__).parent / "data"
_BASE_DATA = _DATA_DIR / "apps.json"
_GENERATED_DATA = _DATA_DIR / "jetson_examples.json"


class AppParameterError(ValueError):
    """Raised when an app command parameter is missing or invalid."""


_PARAM_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_SHELL_WORD_RE = r"(?:'[^']*'|\"[^\"]*\"|[^\s'\"]+)+"

_JX_BOOTSTRAP_CMD = (
    "bash -c 'export PATH=$HOME/.local/bin:$PATH && "
    "which reComputer >/dev/null 2>&1 || pip install jetson-examples'"
)

_DA3_RUN_CMDS = [
    "bash -lc 'set -e; echo [1/5] display auth precheck; DISP=:99; if xdpyinfo -display :99 >/dev/null 2>&1; then DISPLAY=:99 xhost +local: 2>/dev/null && echo \"[ok] xhost +local: on :99\" || echo \"[warn] xhost failed (non-fatal)\"; echo \"[info] DISPLAY will be :99 (noVNC display)\"; else echo \"[warn] :99 not available, falling back to :0\"; DISP=:0; XAUTH_SRC=/run/user/1000/gdm/Xauthority; [ -f \"$XAUTH_SRC\" ] && xauth -f $HOME/.Xauthority merge \"$XAUTH_SRC\" 2>/dev/null; DISPLAY=:0 xhost +local: 2>/dev/null || true; fi'",
    "bash -lc 'echo; echo \"[2/5] optional swap (run manually only if engine build fails due to OOM)\"; echo \"sudo mkdir -p /mnt/nvme\"; echo \"sudo fallocate -l 16G /mnt/nvme/swapfile\"; echo \"sudo chmod 600 /mnt/nvme/swapfile\"; echo \"sudo mkswap /mnt/nvme/swapfile\"; echo \"sudo swapon /mnt/nvme/swapfile\"; echo'",
    "bash -lc 'set -e; echo \"[3/5] start tutorial container + run GUI preview\"; DISP=:99; xdpyinfo -display :99 >/dev/null 2>&1 || DISP=:0; pick_cam(){ for d in /dev/video0 /dev/video3 /dev/video1 /dev/video2; do [ -e \"$d\" ] || continue; if timeout 3s v4l2-ctl -d \"$d\" --stream-mmap --stream-count=1 --stream-to=/tmp/cam_probe.raw >/dev/null 2>&1; then echo ${d#/dev/video}; return 0; fi; done; echo 0; }; CAM=$(pick_cam); echo \"[info] start container with DISPLAY=$DISP CAMERA_ID=$CAM\"; sudo docker rm -f depth_anything_v3 >/dev/null 2>&1 || true; sudo docker run -d --name depth_anything_v3 --restart unless-stopped --runtime=nvidia --network host --ipc host --privileged -e DISPLAY=$DISP -e CAMERA_ID=$CAM -e QT_X11_NO_MITSHM=1 -v /tmp/.X11-unix:/tmp/.X11-unix -v /dev:/dev chenduola6/depth_anything_v3:jp6.2 bash -lc \"set -e; export DISPLAY=$DISP; cd /workspace/ros2-depth-anything-v3-trt; source install/setup.bash; if ls onnx/*.engine >/dev/null 2>&1; then printf \\\"[skip] engine already exists\\\\n\\\"; else printf \\\"[info] first run building TensorRT engine, this can take several minutes\\\\n\\\"; ros2 run depth_anything_v3 generate_engines onnx; fi; exec ./run_camera_depth.sh\"; sudo docker ps -a --filter name=depth_anything_v3'",
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


def _install_params_by_name(app: dict) -> dict[str, dict]:
    return {
        str(param.get("name")): param
        for param in app.get("install_params") or []
        if param.get("name")
    }


def render_app_commands(
    app: dict,
    params: dict[str, str] | None = None,
    command_key: str = "install_cmds",
) -> list[str]:
    """Render app commands with shell-quoted install parameters."""
    params = params or {}
    param_specs = _install_params_by_name(app)

    for name, spec in param_specs.items():
        value = str(params.get(name) or "")
        if spec.get("required") and not value.strip():
            raise AppParameterError(f"required app parameter is missing: {name}")

    rendered: list[str] = []
    for cmd in app.get(command_key) or []:
        def _replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in param_specs:
                return match.group(0)
            value = str(params.get(name) or "")
            return shlex.quote(value)

        rendered.append(_PARAM_RE.sub(_replace, cmd))
    return rendered


def mask_app_commands(app: dict, cmds: list[str]) -> list[str]:
    """Mask secret install parameter values in rendered commands."""
    masked = list(cmds)
    for name, spec in _install_params_by_name(app).items():
        if not spec.get("secret"):
            continue
        template_values = app.get("install_cmds") or []
        for template in template_values:
            marker = "{" + name + "}"
            if marker not in template:
                continue
            prefix, suffix = template.split(marker, 1)
            quoted_prefix = re.escape(prefix)
            quoted_suffix = re.escape(suffix)
            pattern = re.compile(quoted_prefix + _SHELL_WORD_RE + quoted_suffix)
            replacement = prefix + "***" + suffix
            masked = [pattern.sub(replacement, cmd) for cmd in masked]
    return masked


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
        "check_cmd": python_module_check_cmd("import ultralytics"),
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
        "check_cmd": python_module_check_cmd("import transformers"),
        "install_cmds": None,
    },
    {
        "id": "lerobot",
        "icon": "BOT",
        "name": "LeRobot",
        "category": "Robotics",
        "desc": "LeRobot toolkit for robot control and imitation learning.",
        "skill_id": "lerobot",
        "check_cmd": python_module_check_cmd("import lerobot"),
        "install_cmds": None,
    },
]
