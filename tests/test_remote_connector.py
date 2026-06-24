from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seeed_jetson_develop.modules.remote.connector import normalize_subnet_prefix


def test_normalize_subnet_prefix_strips_trailing_dot():
    assert normalize_subnet_prefix("192.168.7.") == "192.168.7"


def test_normalize_subnet_prefix_rejects_incomplete_or_invalid_values():
    assert normalize_subnet_prefix("192.168.") is None
    assert normalize_subnet_prefix("192.168.300") is None
    assert normalize_subnet_prefix("jetson.local") is None
