"""全局配置持久化"""
from __future__ import annotations

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
    tmp = _CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.rename(_CONFIG_PATH)


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


# ── Onboarding 引导配置 ──────────────────────────────────────────────────────

_ONBOARDING_KEY = "onboarding_dismissed"
_ONBOARDING_VERSION_KEY = "onboarding_version"
_CURRENT_ONBOARDING_VERSION = 1  # 引导内容更新时递增


def is_onboarding_dismissed() -> bool:
    """用户是否已勾选"不再显示"并完成过引导。"""
    data = load()
    # 如果引导版本已更新，即使之前 dismiss 过也重新显示
    if data.get(_ONBOARDING_VERSION_KEY, 0) < _CURRENT_ONBOARDING_VERSION:
        return False
    return data.get(_ONBOARDING_KEY, False)


def set_onboarding_dismissed(dismissed: bool = True):
    """设置引导的显示/隐藏状态。"""
    data = load()
    data[_ONBOARDING_KEY] = dismissed
    data[_ONBOARDING_VERSION_KEY] = _CURRENT_ONBOARDING_VERSION
    save(data)


def reset_onboarding():
    """重置引导状态（用于 Help 菜单手动打开）。"""
    data = load()
    data[_ONBOARDING_KEY] = False
    save(data)
