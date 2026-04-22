"""全局配置持久化"""
import json
import os
import locale
import logging
from pathlib import Path

_CONFIG_PATH = Path.home() / ".config" / "seeed-jetson-tool" / "config.json"
log = logging.getLogger("seeed.core.config")
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "fr", "es", "de", "zh-CN")
LANGUAGE_ALIASES = {
    "en": "en",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh_cn": "zh-CN",
    "zh-cn.utf-8": "zh-CN",
    "zh_cn.utf-8": "zh-CN",
    "en-us": "en",
    "en_us": "en",
    "en-us.utf-8": "en",
    "en_us.utf-8": "en",
    "en-gb": "en",
    "en_gb": "en",
    "fr": "fr",
    "fr-fr": "fr",
    "fr_fr": "fr",
    "fr-fr.utf-8": "fr",
    "fr_fr.utf-8": "fr",
    "es": "es",
    "es-es": "es",
    "es_es": "es",
    "es-es.utf-8": "es",
    "es_es.utf-8": "es",
    "de": "de",
    "de-de": "de",
    "de_de": "de",
    "de-de.utf-8": "de",
    "de_de.utf-8": "de",
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


def _canonical_language(lang: str | None) -> str | None:
    value = (lang or "").strip()
    if not value:
        return None

    # LANGUAGE may contain a priority list, for example "fr_FR:en_US".
    value = value.split(":", 1)[0].strip()
    value = value.split(".", 1)[0].strip()
    key = value.replace("_", "-").lower()
    if not key:
        return None

    if key in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[key]

    primary = key.split("-", 1)[0]
    if primary in {"en", "fr", "es", "de"}:
        return primary
    if primary == "zh":
        return "zh-CN"
    return None


def normalize_language(lang: str | None) -> str:
    return _canonical_language(lang) or DEFAULT_LANGUAGE


def detect_system_language() -> str:
    candidates = [
        os.environ.get("LANGUAGE"),
        os.environ.get("LC_ALL"),
        os.environ.get("LC_MESSAGES"),
        os.environ.get("LANG"),
    ]
    try:
        loc = locale.getlocale()[0]
    except Exception:
        loc = None
    candidates.append(loc)

    for candidate in candidates:
        normalized = _canonical_language(candidate)
        if normalized in SUPPORTED_LANGUAGES:
            return normalized
    return DEFAULT_LANGUAGE


def get_language() -> str:
    data = load()
    if "language" in data:
        return normalize_language(data.get("language"))
    return detect_system_language()


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
