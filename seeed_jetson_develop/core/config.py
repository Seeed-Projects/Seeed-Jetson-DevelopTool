"""全局配置持久化"""
import json
import os
import logging
from pathlib import Path

_CONFIG_PATH = Path.home() / ".config" / "seeed-jetson-tool" / "config.json"
log = logging.getLogger("seeed.core.config")
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_LANGUAGE = "zh-CN"
LANGUAGE_ALIASES = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "en-us": "en",
    "en-gb": "en",
}


def load() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        log.warning("Invalid config JSON at %s: %s", _CONFIG_PATH, exc)
        return {}
    except OSError as exc:
        log.warning("Failed to read config %s: %s", _CONFIG_PATH, exc)
        return {}


def save(data: dict):
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def normalize_language(lang: str | None) -> str:
    value = (lang or "").strip()
    if not value:
        return DEFAULT_LANGUAGE
    return LANGUAGE_ALIASES.get(value.lower(), value)


def get_language() -> str:
    return normalize_language(load().get("language", DEFAULT_LANGUAGE))


def set_language(lang: str):
    data = load()
    data["language"] = normalize_language(lang)
    save(data)


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
