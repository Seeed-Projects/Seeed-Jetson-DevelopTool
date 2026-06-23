from __future__ import annotations

import json
from pathlib import Path

from seeed_jetson_develop.modules.ota.page import (
    _find_matching_path,
    _path_display_name,
    _paths_for_product,
)


OTA_PATHS_FILE = (
    Path(__file__).resolve().parents[1]
    / "seeed_jetson_develop"
    / "modules"
    / "ota"
    / "data"
    / "ota_paths.json"
)


def _load_paths() -> list[dict]:
    return json.loads(OTA_PATHS_FILE.read_text(encoding="utf-8"))["ota_paths"]


def test_orin_nano_jp62_detects_jp72_path() -> None:
    path = _find_matching_path(_load_paths(), "orin-nano-devkit-super", "36.4.3")

    assert path is not None
    assert path["id"] == "jp62-to-jp72-orin-nano-devkit"
    assert path["target_jetpack"] == "7.2"
    assert path["target_l4t"] == "39.2.0"
    assert "IQDHQcQZB0dYS5WzzQ-9vhE0AbXdsvLU0FEl7dVbq2c9tqc" in path["payload_options"][0]["url"]


def test_orin_nano_jp513_still_detects_jp62_path() -> None:
    path = _find_matching_path(_load_paths(), "orin-nano-devkit-super", "35.5.0")

    assert path is not None
    assert path["id"] == "jp513-to-jp62-orin-nano-devkit"
    assert path["target_jetpack"] == "6.2"


def test_orin_nano_path_labels_disambiguate_source_and_target_l4t() -> None:
    labels = [
        _path_display_name(path)
        for path in _paths_for_product(_load_paths(), "orin-nano-devkit-super")
    ]

    assert len(labels) == 2
    assert "L4T 35.5.0 -> 36.4.3" in labels[0]
    assert "L4T 36.4.3 -> 39.2.0" in labels[1]
