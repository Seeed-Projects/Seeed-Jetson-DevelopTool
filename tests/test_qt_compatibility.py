from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _source_files(root: Path) -> list[Path]:
    return list(root.rglob("*.py"))


def test_no_pyqt5_imports_in_source() -> None:
    """源码中不应再直接 import PyQt5。"""
    targets = [REPO_ROOT / "run_v2.py", REPO_ROOT / "seeed_jetson_develop"]
    offenders: list[Path] = []
    for target in targets:
        for path in ([target] if target.is_file() else _source_files(target)):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module] if node.module else []
                else:
                    continue
                if any(name and name.startswith("PyQt5") for name in names):
                    offenders.append(path.relative_to(REPO_ROOT))
                    break
    assert not offenders, f"found PyQt5 imports in: {offenders}"


def test_run_v2_high_dpi_attributes_are_guarded() -> None:
    """run_v2.py 中必须在设置高 DPI 属性前用 hasattr 判断，避免 PyQt6 报错。"""
    source = (REPO_ROOT / "run_v2.py").read_text(encoding="utf-8")
    for attr in ("AA_EnableHighDpiScaling", "AA_UseHighDpiPixmaps"):
        assert f'hasattr(Qt, "{attr}")' in source, (
            f"run_v2.py must guard Qt.{attr} with hasattr"
        )


def test_pick_font_family_handles_pyqt5_and_pyqt6_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    """pick_font_family 同时兼容 PyQt6 静态 API 和 PyQt5 实例 API。"""
    from seeed_jetson_develop.gui import theme

    # Case 1: static method (PyQt6-like)
    mock_class = MagicMock()
    mock_class.families = MagicMock(return_value=["Arial", "Microsoft YaHei"])
    monkeypatch.setattr(theme, "QFontDatabase", mock_class)
    assert theme.pick_font_family(("Microsoft YaHei", "Sans Serif")) == "Microsoft YaHei"

    # Case 2: instance method (PyQt5-like): direct static call raises TypeError
    mock_class = MagicMock()
    mock_class.families = MagicMock(
        side_effect=TypeError(
            "families(self, ...): first argument of unbound method must have type 'QFontDatabase'"
        ),
    )
    mock_instance = MagicMock()
    mock_instance.families.return_value = ["Arial", "Microsoft YaHei"]
    mock_class.return_value = mock_instance
    monkeypatch.setattr(theme, "QFontDatabase", mock_class)
    assert theme.pick_font_family(("Microsoft YaHei", "Sans Serif")) == "Microsoft YaHei"


def test_pyproject_uses_pyqt6_not_pyqt5() -> None:
    """pyproject.toml 的依赖应该是 qtpy + PyQt6，不含 PyQt5。"""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "PyQt6" in pyproject, "pyproject.toml must declare PyQt6"
    assert "qtpy" in pyproject, "pyproject.toml must declare qtpy"
    assert "PyQt5" not in pyproject, "pyproject.toml must not declare PyQt5"


def test_requirements_use_pyqt6_not_pyqt5() -> None:
    """requirements.txt 也应与 pyproject.toml 保持一致。"""
    req = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "PyQt6" in req, "requirements.txt must include PyQt6"
    assert "qtpy" in req, "requirements.txt must include qtpy"
    assert "PyQt5" not in req, "requirements.txt must not include PyQt5"


def test_key_gui_modules_import_under_qtpy() -> None:
    """核心 GUI 模块在 qtpy 下能正常 import，没有 PyQt5/6 特有 API 导致失败。"""
    from seeed_jetson_develop.gui import theme
    from seeed_jetson_develop.gui import main_window_v2

    assert theme is not None
    assert main_window_v2 is not None
