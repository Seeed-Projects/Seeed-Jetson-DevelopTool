"""全局配置持久化"""
import json
from pathlib import Path

_CONFIG_PATH = Path.home() / ".config" / "seeed-jetson-tool" / "config.json"


def load() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(data: dict):
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
