"""Runtime data refresh helpers.

The packaged JSON data is the offline fallback. When the client starts with
network access, BSP download metadata is refreshed from the wiki repository and
stored in a user-writable cache so installed packages do not need write access.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

log = logging.getLogger(__name__)

PACKAGE_DATA_DIR = Path(__file__).resolve().parent / "data"
CACHE_DATA_DIR = Path.home() / ".cache" / "seeed-jetson-develop" / "data"

GITHUB_OWNER = "Seeed-Studio"
GITHUB_REPO = "wiki-documents"
GITHUB_BRANCH = "docusaurus-version"
GITHUB_JETSON_DATA_PATH = "src/data/jetson"
LOCAL_BSP_DATA_NAME = "l4t_data.json"

_JSON_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "seeed-jetson-develop-tool",
}
_RAW_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "seeed-jetson-develop-tool",
}


def _normalized_filename(name: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "", name.lower())


def _cache_path(name: str) -> Path:
    return CACHE_DATA_DIR / name


def _package_path(name: str) -> Path:
    return PACKAGE_DATA_DIR / name


def _is_valid_bsp_data(data: Any) -> bool:
    if not isinstance(data, list) or not data:
        return False
    required = {"product", "l4t", "mainlink", "filename", "foldername", "sha256"}
    for item in data:
        if not isinstance(item, dict):
            return False
        if not required.issubset(item.keys()):
            return False
        if not item.get("product") or not item.get("l4t") or not item.get("filename"):
            return False
    return True


def _clean_bsp_item(item: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(item)
    sha256 = cleaned.get("sha256")
    if isinstance(sha256, str):
        cleaned["sha256"] = re.sub(r"\s+", "", sha256)
    return cleaned


def _clean_bsp_data(data: Any) -> Any:
    if not isinstance(data, list):
        return data
    return [_clean_bsp_item(item) if isinstance(item, dict) else item for item in data]


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(str(tmp), str(path))


def get_data_file(name: str) -> Path:
    """Return the best runtime data file, preferring valid user-cache updates."""
    cache = _cache_path(name)
    if cache.exists():
        if name == LOCAL_BSP_DATA_NAME:
            try:
                if _is_valid_bsp_data(_read_json(cache)):
                    return cache
            except Exception:
                log.debug("ignoring invalid cached BSP data: %s", cache, exc_info=True)
        else:
            return cache
    return _package_path(name)


def load_json_data(name: str, default: Any = None) -> Any:
    try:
        data = _read_json(get_data_file(name))
        if name == LOCAL_BSP_DATA_NAME:
            return _clean_bsp_data(data)
        return data
    except Exception:
        if default is not None:
            return default
        raise


def _github_contents_url() -> str:
    return (
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/"
        f"{GITHUB_JETSON_DATA_PATH}?ref={GITHUB_BRANCH}"
    )


def _raw_url(filename: str) -> str:
    return (
        f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/"
        f"{GITHUB_BRANCH}/{GITHUB_JETSON_DATA_PATH}/{filename}"
    )


def _find_remote_json_entry(entries: Iterable[Dict[str, Any]], local_name: str) -> Optional[Dict[str, Any]]:
    local_lower = local_name.lower()
    local_normalized = _normalized_filename(local_name)
    json_files: List[Dict[str, Any]] = [
        item for item in entries
        if item.get("type") == "file" and str(item.get("name", "")).lower().endswith(".json")
    ]

    for item in json_files:
        if str(item.get("name", "")).lower() == local_lower:
            return item
    for item in json_files:
        if _normalized_filename(str(item.get("name", ""))) == local_normalized:
            return item
    for item in json_files:
        normalized = _normalized_filename(str(item.get("name", "")))
        if "l4t" in normalized and "data" in normalized:
            return item
    return None


def _download_remote_bsp_data(timeout=(2, 5)) -> Any:
    resp = requests.get(_github_contents_url(), headers=_JSON_HEADERS, timeout=timeout)
    resp.raise_for_status()
    entries = resp.json()
    if not isinstance(entries, list):
        raise ValueError("GitHub contents response is not a directory listing")

    entry = _find_remote_json_entry(entries, LOCAL_BSP_DATA_NAME)
    if not entry:
        raise FileNotFoundError("BSP metadata JSON not found in remote jetson data directory")

    url = entry.get("download_url") or _raw_url(str(entry.get("name", LOCAL_BSP_DATA_NAME)))
    raw = requests.get(url, headers=_RAW_HEADERS, timeout=timeout)
    raw.raise_for_status()
    return raw.json()


def _merge_bsp_data(local_data: Any, remote_data: Any) -> Any:
    local_data = _clean_bsp_data(local_data)
    remote_data = _clean_bsp_data(remote_data)
    if not _is_valid_bsp_data(local_data):
        return remote_data

    merged = [dict(item) for item in local_data]
    index = {
        (str(item.get("product", "")), str(item.get("l4t", ""))): idx
        for idx, item in enumerate(merged)
    }
    for remote_item in remote_data:
        key = (str(remote_item.get("product", "")), str(remote_item.get("l4t", "")))
        if key in index:
            current = dict(merged[index[key]])
            current.update(remote_item)
            merged[index[key]] = current
        else:
            index[key] = len(merged)
            merged.append(dict(remote_item))
    return merged


_COMPARISON_FIELDS = ("mainlink", "mirrorlink", "filename", "foldername", "sha256")


def compare_bsp_data(local_data: Any, remote_data: Any) -> List[Dict[str, Any]]:
    """Compare local and remote BSP data and return structured differences.

    Each diff entry contains:
      - key: (product, l4t) tuple
      - status: "new" | "modified" | "identical" | "local_only"
      - fields_changed: list of field names that differ (only for "modified")
      - local_item: the local dict (or None)
      - remote_item: the remote dict (or None)
    """
    local_data = _clean_bsp_data(local_data)
    remote_data = _clean_bsp_data(remote_data)

    local_index = {
        (str(item.get("product", "")), str(item.get("l4t", ""))): item
        for item in local_data
    }
    remote_index = {
        (str(item.get("product", "")), str(item.get("l4t", ""))): item
        for item in remote_data
    }

    all_keys = sorted(set(local_index.keys()) | set(remote_index.keys()))
    diffs: List[Dict[str, Any]] = []

    for key in all_keys:
        local_item = local_index.get(key)
        remote_item = remote_index.get(key)

        if local_item is None:
            diffs.append({
                "key": key,
                "status": "new",
                "fields_changed": [],
                "local_item": None,
                "remote_item": remote_item,
            })
        elif remote_item is None:
            diffs.append({
                "key": key,
                "status": "local_only",
                "fields_changed": [],
                "local_item": local_item,
                "remote_item": None,
            })
        else:
            changed = []
            for field in _COMPARISON_FIELDS:
                if local_item.get(field) != remote_item.get(field):
                    changed.append(field)
            if changed:
                diffs.append({
                    "key": key,
                    "status": "modified",
                    "fields_changed": changed,
                    "local_item": local_item,
                    "remote_item": remote_item,
                })
            else:
                diffs.append({
                    "key": key,
                    "status": "identical",
                    "fields_changed": [],
                    "local_item": local_item,
                    "remote_item": remote_item,
                })
    return diffs


def apply_selected_updates(
    local_data: Any,
    remote_data: Any,
    selected_keys: Iterable[tuple[str, str]],
) -> Any:
    """Apply remote updates only for selected keys, keep everything else local."""
    local_data = _clean_bsp_data(local_data)
    remote_data = _clean_bsp_data(remote_data)
    selected_set = set(selected_keys)

    merged = [dict(item) for item in local_data]
    index = {
        (str(item.get("product", "")), str(item.get("l4t", ""))): idx
        for idx, item in enumerate(merged)
    }

    remote_index = {
        (str(item.get("product", "")), str(item.get("l4t", ""))): item
        for item in remote_data
    }

    for key in selected_set:
        remote_item = remote_index.get(key)
        if remote_item is None:
            continue
        if key in index:
            merged[index[key]] = dict(remote_item)
        else:
            index[key] = len(merged)
            merged.append(dict(remote_item))
    return merged


def update_bsp_links_from_github(timeout=(2, 5)) -> bool:
    """Refresh BSP download metadata from the wiki repo.

    Returns True when remote data was fetched and written. Returns False when
    offline, invalid, or otherwise unable to update; callers should keep using
    the bundled/cached fallback in that case.
    """
    try:
        data = _download_remote_bsp_data(timeout=timeout)
        if not _is_valid_bsp_data(data):
            raise ValueError("remote BSP metadata has an unexpected schema")
        data = _merge_bsp_data(load_json_data(LOCAL_BSP_DATA_NAME, []), data)

        _atomic_write_json(_cache_path(LOCAL_BSP_DATA_NAME), data)
        package_path = _package_path(LOCAL_BSP_DATA_NAME)
        try:
            _atomic_write_json(package_path, data)
        except Exception:
            log.debug("package data directory is not writable: %s", package_path, exc_info=True)
        log.info("BSP metadata refreshed from %s", GITHUB_JETSON_DATA_PATH)
        return True
    except Exception as exc:
        log.info("BSP metadata refresh skipped: %s", exc)
        return False
