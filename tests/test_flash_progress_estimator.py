from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seeed_jetson_develop.modules.flash.thread import _FlashProgressEstimator


def test_qspi_success_phrase_marks_flash_near_complete():
    est = _FlashProgressEstimator()
    pct = est.update("[ 224]: l4t_flash_from_kernel: Successfully flash the qspi")
    assert pct == 99


def test_qspi_success_legacy_phrase_marks_flash_near_complete():
    est = _FlashProgressEstimator()
    pct = est.update("Successfully flashed the QSPI.")
    assert pct == 99
