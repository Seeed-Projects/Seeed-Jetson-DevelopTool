"""全局配置持久化"""
from __future__ import annotations

import json
import locale
import os
import logging
from pathlib import Path

_CONFIG_PATH = Path.home() / ".config" / "seeed-jetson-tool" / "config.json"
log = logging.getLogger("seeed.core.config")
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
AI_PROVIDER_ANTHROPIC = "anthropic"
AI_PROVIDER_OPENAI = "openai"
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
    tmp.replace(_CONFIG_PATH)


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


def _claude_code_settings_paths() -> list[Path]:
    """Return candidate paths for Claude Code settings.json."""
    paths: list[Path] = []
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata) / "Claude"
            paths.extend([base / "settings.json", base / "claude_desktop_config.json"])
    else:
        paths.append(Path.home() / ".claude" / "settings.json")
        paths.append(Path.home() / "Library" / "Application Support" / "Claude" / "settings.json")
        paths.append(Path.home() / ".config" / "Claude" / "settings.json")
    return paths


def _load_claude_code_settings() -> dict[str, str]:
    """Read API key/base URL from local Claude Code / Claude Desktop config."""
    for path in _claude_code_settings_paths():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            env = data.get("env", {})
            return {
                "api_key": (env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY") or "").strip(),
                "base_url": (env.get("ANTHROPIC_BASE_URL") or "").strip(),
            }
        except Exception:
            continue
    return {"api_key": "", "base_url": ""}


def _load_codex_settings() -> dict[str, str]:
    """Read API key/base URL/provider from local Codex CLI config.toml/config.json."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            tomllib = None

    candidates = [
        Path.home() / ".codex" / "config.toml",
        Path.home() / ".codex" / "config.json",
    ]
    for path in candidates:
        try:
            if path.suffix == ".toml" and tomllib is not None:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                continue
            provider = data.get("model_provider", "OpenAI")
            provider_cfg = data.get("model_providers", {}).get(provider, {})
            # Codex stores the API key either inline (when available) or in env/keyring.
            api_key = (provider_cfg.get("api_key") or os.environ.get("OPENAI_API_KEY") or "").strip()
            return {
                "api_key": api_key,
                "base_url": (provider_cfg.get("base_url") or "").strip(),
                "provider": provider.lower(),
            }
        except Exception:
            continue
    return {"api_key": "", "base_url": "", "provider": ""}


def _detect_ai_provider(base_url: str, api_key: str, codex_cfg: dict,
                         explicit_provider: str = "") -> str:
    """Detect whether the configured endpoint is Anthropic or OpenAI-compatible.

    Heuristics (in order):
      1. Explicit `ai_provider` setting in config -> use it
      2. If the base URL matches the local Codex config -> OpenAI
      3. If the base URL is the official Anthropic host -> Anthropic
      4. If the API key looks like an Anthropic key -> Anthropic
      5. Default -> Anthropic

    Only the official Anthropic host is hard-coded; personal proxies are
    recognised via the explicit setting or the local Codex config.
    """
    explicit = (explicit_provider or "").strip().lower()
    if explicit in (AI_PROVIDER_ANTHROPIC, AI_PROVIDER_OPENAI):
        return explicit

    codex_url = (codex_cfg.get("base_url") or "").strip().rstrip("/")
    url = (base_url or "").strip().rstrip("/")

    if codex_url and url == codex_url:
        return AI_PROVIDER_OPENAI

    try:
        host = url.split("://", 1)[1].split("/", 1)[0].lower()
        if host == "api.anthropic.com":
            return AI_PROVIDER_ANTHROPIC
    except Exception:
        pass

    if api_key.startswith("sk-ant-"):
        return AI_PROVIDER_ANTHROPIC

    return AI_PROVIDER_ANTHROPIC


def get_runtime_anthropic_settings() -> dict:
    """Resolve AI API settings from app config, Claude Code, env, or Codex.

    Priority (highest first):
      1. Seeed Jetson Tool config file
      2. Claude Code / Claude Desktop local settings
      3. Environment variables (ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL)
      4. Codex CLI local config (OpenAI-compatible fallback)
      5. Built-in Anthropic defaults
    """
    data = load()
    claude_cfg = _load_claude_code_settings()
    codex_cfg = _load_codex_settings()

    config_key = (data.get("anthropic_api_key") or "").strip()
    claude_key = claude_cfg.get("api_key", "").strip()
    env_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    codex_key = codex_cfg.get("api_key", "").strip()

    if config_key:
        api_key, api_key_source = config_key, "config"
    elif claude_key:
        api_key, api_key_source = claude_key, "claude_code"
    elif env_key:
        api_key, api_key_source = env_key, "env"
    elif codex_key:
        api_key, api_key_source = codex_key, "codex"
    else:
        api_key, api_key_source = "", "none"

    config_url = (data.get("anthropic_base_url") or "").strip()
    claude_url = claude_cfg.get("base_url", "").strip()
    env_url = (os.environ.get("ANTHROPIC_BASE_URL") or "").strip()
    codex_url = codex_cfg.get("base_url", "").strip()

    if config_url:
        base_url, base_url_source = config_url, "config"
    elif claude_url:
        base_url, base_url_source = claude_url, "claude_code"
    elif env_url:
        base_url, base_url_source = env_url, "env"
    elif codex_url:
        base_url, base_url_source = codex_url, "codex"
    else:
        base_url, base_url_source = DEFAULT_ANTHROPIC_BASE_URL, "default"

    explicit_provider = (data.get("ai_provider") or "").strip().lower()
    provider = _detect_ai_provider(base_url, api_key, codex_cfg, explicit_provider)

    return {
        "api_key": api_key,
        "api_key_source": api_key_source,
        "base_url": base_url,
        "base_url_source": base_url_source,
        "provider": provider,
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


# ── Proxy settings ───────────────────────────────────────────────────────────

PROXY_KEYS = ("http_proxy", "https_proxy", "all_proxy")


def _proxy_from_env() -> dict[str, str]:
    """Read proxy URLs from environment variables (uppercase, then lowercase)."""
    found: dict[str, str] = {}
    for key in PROXY_KEYS:
        value = (os.environ.get(key.upper()) or os.environ.get(key) or "").strip()
        if value:
            found[key] = value
    return found


def get_proxy_settings() -> dict[str, str | None]:
    """Resolve HTTP/HTTPS/SOCKS proxy settings.

    Priority (highest first):
      1. App config file (~/.config/seeed-jetson-tool/config.json)
      2. Environment variables (HTTP_PROXY, HTTPS_PROXY, ALL_PROXY and lowercase)

    Returns a dict with keys ``http``, ``https``, ``all``. Values are either a
    proxy URL string or ``None``.
    """
    data = load()
    proxies: dict[str, str] = {}

    # 1. App config takes precedence.
    for key in PROXY_KEYS:
        value = (data.get(key) or data.get(key.upper()) or "").strip()
        if value:
            proxies[key] = value

    # 2. Environment variables fill the gaps.
    env_proxies = _proxy_from_env()
    for key in PROXY_KEYS:
        if key not in proxies and key in env_proxies:
            proxies[key] = env_proxies[key]

    return {
        "http": proxies.get("http_proxy"),
        "https": proxies.get("https_proxy"),
        "all": proxies.get("all_proxy"),
    }


def get_effective_https_proxy() -> str | None:
    """Return the proxy URL that should be used for HTTPS API calls.

    Falls back from explicit HTTPS proxy to ALL_PROXY. Returns ``None`` when no
    suitable proxy is configured.
    """
    proxies = get_proxy_settings()
    return proxies.get("https") or proxies.get("all")


# ── Proxy settings ───────────────────────────────────────────────────────────

PROXY_KEYS = ("http_proxy", "https_proxy", "all_proxy")


def _proxy_from_env() -> dict[str, str]:
    """Read proxy URLs from environment variables (uppercase, then lowercase)."""
    found: dict[str, str] = {}
    for key in PROXY_KEYS:
        value = (os.environ.get(key.upper()) or os.environ.get(key) or "").strip()
        if value:
            found[key] = value
    return found


def get_proxy_settings() -> dict[str, str | None]:
    """Resolve HTTP/HTTPS/SOCKS proxy settings.

    Priority (highest first):
      1. App config file (~/.config/seeed-jetson-tool/config.json)
      2. Environment variables (HTTP_PROXY, HTTPS_PROXY, ALL_PROXY and lowercase)

    Returns a dict with keys ``http``, ``https``, ``all``. Values are either a
    proxy URL string or ``None``.
    """
    data = load()
    proxies: dict[str, str] = {}

    # 1. App config takes precedence.
    for key in PROXY_KEYS:
        value = (data.get(key) or data.get(key.upper()) or "").strip()
        if value:
            proxies[key] = value

    # 2. Environment variables fill the gaps.
    env_proxies = _proxy_from_env()
    for key in PROXY_KEYS:
        if key not in proxies and key in env_proxies:
            proxies[key] = env_proxies[key]

    return {
        "http": proxies.get("http_proxy"),
        "https": proxies.get("https_proxy"),
        "all": proxies.get("all_proxy"),
    }


def get_effective_https_proxy() -> str | None:
    """Return the proxy URL that should be used for HTTPS API calls.

    Falls back from explicit HTTPS proxy to ALL_PROXY. Returns ``None`` when no
    suitable proxy is configured.
    """
    proxies = get_proxy_settings()
    return proxies.get("https") or proxies.get("all")

# ── npm registry (used by npx when installing NVIDIA skills) ───────────────
DEFAULT_NPM_REGISTRY = "https://registry.npmjs.org/"
DEFAULT_NPM_REGISTRY_CN = "https://registry.npmmirror.com/"


def _is_chinese_locale() -> bool:
    """Return True if the OS default locale is Chinese (any region)."""
    try:
        # getdefaultlocale() is deprecated but still returns POSIX names
        # like 'zh_CN' on Windows, while getlocale() may return the
        # localized display name (e.g. 'Chinese (Simplified)_China').
        for loc in (locale.getdefaultlocale()[0], locale.getlocale()[0]):
            if loc:
                low = loc.lower()
                if low.startswith("zh") or "chinese" in low:
                    return True
    except Exception:
        pass
    return False


def get_npm_registry() -> str:
    """Return the npm registry URL to use for npx installs.

    Priority:
      1. Explicit ``npm_registry`` config value (e.g. set via settings).
      2. Chinese system locale -> npmmirror.com.
      3. Fallback -> official npm registry.
    """
    cfg = load()
    explicit = cfg.get("npm_registry", "auto")
    if explicit and explicit.lower() != "auto":
        return explicit
    if _is_chinese_locale():
        return DEFAULT_NPM_REGISTRY_CN
    return DEFAULT_NPM_REGISTRY


def set_npm_registry(url: str | None):
    """Persist npm registry preference.  ``None`` resets to auto."""
    data = load()
    if url is None:
        data.pop("npm_registry", None)
    else:
        data["npm_registry"] = url
    save(data)
