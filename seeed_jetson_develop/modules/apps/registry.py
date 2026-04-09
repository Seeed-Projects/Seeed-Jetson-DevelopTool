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


def _read_apps(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _prepend_bootstrap(app: dict) -> dict:
    """For jetson-examples apps, prepend reComputer bootstrap to install/run cmds."""
    for key in ("install_cmds", "run_cmds"):
        cmds = app.get(key)
        if cmds:
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
