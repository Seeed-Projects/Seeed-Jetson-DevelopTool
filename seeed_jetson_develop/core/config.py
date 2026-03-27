"""全局配置持久化"""
import json
import os
from pathlib import Path

_CONFIG_PATH = Path.home() / ".config" / "seeed-jetson-tool" / "config.json"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"


def load() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(data: dict):
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_runtime_anthropic_settings() -> dict:
    data = load()

    config_key = (data.get("anthropic_api_key") or "").strip()
    env_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    api_key = config_key or env_key
    api_key_source = "config" if config_key else ("env" if env_key else "none")

    config_url = (data.get("anthropic_base_url") or "").strip()
    env_url = (os.environ.get("ANTHROPIC_BASE_URL") or "").strip()
    base_url = config_url or env_url or DEFAULT_ANTHROPIC_BASE_URL
    if config_url:
        base_url_source = "config"
    elif env_url:
        base_url_source = "env"
    else:
        base_url_source = "default"

    return {
        "api_key": api_key,
        "api_key_source": api_key_source,
        "base_url": base_url,
        "base_url_source": base_url_source,
    }
