"""Smoke tests for the installer build script.

These tests avoid the heavy full-archive creation and only check the
exclusion logic and generated source compilation.
"""

import sys
from pathlib import Path

import pytest

# scripts/build_installer.py is not inside a package, so load it directly.
BUILD_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_installer.py"
spec = __import__("importlib.util").util.spec_from_file_location("build_installer", BUILD_SCRIPT)
build_installer = __import__("importlib.util").util.module_from_spec(spec)
sys.modules["build_installer"] = build_installer
spec.loader.exec_module(build_installer)


class TestShouldExclude:
    def test_duplicate_assets_are_excluded(self):
        # Any byte-identical file that lives in both assets/ and
        # seeed_jetson_develop/assets/ should be excluded from the root copy.
        dup = build_installer._ASSET_DUPLICATES
        assert dup, "expected at least one duplicated asset in the repo"
        for rel in dup:
            root_rel = Path("assets") / rel
            assert build_installer.should_exclude(root_rel), (
                f"expected root asset {root_rel} to be excluded"
            )

    def test_unique_root_assets_are_kept(self):
        # Assets that only exist at the top level must remain in the archive.
        root_only = [
            Path("assets") / "Reference-UI.png",
            Path("assets") / "downloads-chart.svg",
        ]
        for rel in root_only:
            if (build_installer.ROOT / rel).exists():
                assert not build_installer.should_exclude(rel), (
                    f"expected unique root asset {rel} to be kept"
                )

    def test_package_assets_are_kept(self):
        # The package copy of duplicated assets must stay in the archive.
        dup = build_installer._ASSET_DUPLICATES
        for rel in dup:
            pkg_rel = Path("seeed_jetson_develop") / "assets" / rel
            assert not build_installer.should_exclude(pkg_rel), (
                f"expected package asset {pkg_rel} to be kept"
            )

    def test_video_covers_excluded(self):
        assert build_installer.should_exclude(Path("assets/video-cover-en.png"))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
