from __future__ import annotations

import json
from pathlib import Path

from seeed_jetson_develop.core.config import (
    DEFAULT_LANGUAGE,
    get_language as _get_config_language,
    normalize_language,
    set_language as _set_config_language,
)


_LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"
_FALLBACK_LANGUAGE = DEFAULT_LANGUAGE
_cache: dict[str, dict[str, str]] = {}


def available_languages() -> list[str]:
    if not _LOCALES_DIR.exists():
        return []
    return sorted(
        path.name
        for path in _LOCALES_DIR.iterdir()
        if path.is_dir()
    )


def _locale_files(lang: str) -> list[Path]:
    locale_dir = _LOCALES_DIR / lang
    if not locale_dir.exists():
        return []
    return sorted(locale_dir.glob("*.json"))


def load_locale(lang: str) -> dict[str, str]:
    lang = normalize_language(lang)
    if lang in _cache:
        return _cache[lang]

    merged: dict[str, str] = {}
    for file_path in _locale_files(lang):
        try:
            # Accept both plain UTF-8 and UTF-8 with BOM.
            payload = json.loads(file_path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if isinstance(key, str) and isinstance(value, str):
                merged[key] = value

    _cache[lang] = merged
    return merged


def reload_locales() -> None:
    _cache.clear()


def get_language() -> str:
    return normalize_language(_get_config_language())


def set_language(lang: str) -> str:
    normalized = normalize_language(lang)
    _set_config_language(normalized)
    return normalized


def _lookup(key: str, lang: str) -> str | None:
    return load_locale(lang).get(key)


def t(key: str, lang: str | None = None, **kwargs) -> str:
    language = normalize_language(lang or get_language())
    text = (
        _lookup(key, language)
        or _lookup(key, _FALLBACK_LANGUAGE)
        or key
    )
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
