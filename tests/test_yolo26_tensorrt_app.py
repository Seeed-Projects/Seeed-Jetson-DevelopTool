from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MARKET_PATH = (
    REPO_ROOT
    / "seeed_jetson_develop"
    / "modules"
    / "apps"
    / "data"
    / "jetson_examples.json"
)
ASSET_ROOT = (
    REPO_ROOT
    / "seeed_jetson_develop"
    / "modules"
    / "apps"
    / "assets"
    / "yolo26-tensorrt"
)


def _apps() -> list[dict]:
    return json.loads(MARKET_PATH.read_text(encoding="utf-8"))


def test_native_tensorrt_entry_is_distinct_from_docker_yolo26():
    by_id = {app["id"]: app for app in _apps()}

    assert "jx-yolo26" in by_id
    assert "jx-yolo26-tensorrt" in by_id
    assert by_id["jx-yolo26"]["name"] == "YOLO26 (Docker)"
    assert by_id["jx-yolo26-tensorrt"]["name"] == "YOLO26 TensorRT C++ (Native)"
    assert by_id["jx-yolo26-tensorrt"]["requirements"]["docker_enabled"] is False


def test_native_tensorrt_entry_supports_jetpack_6_and_7():
    app = next(app for app in _apps() if app["id"] == "jx-yolo26-tensorrt")
    versions = app["requirements"]["jetpack_versions"]
    dependency_command = app["install_cmds"][0]

    assert "36.3.0" in versions
    assert "36.4.3" in versions
    assert "38.4.0" in versions
    assert "39.2.0" in versions
    assert app["pc_download_assets"] is True
    assert app["web_port"] == 8080
    assert "--build-only" not in app["install_cmds"][-1]
    assert "pkill" in app["stop_cmds"][0]
    assert "rm -rf" not in app["stop_cmds"][0]
    assert "[b]uild/yolo26_tensorrt" in app["uninstall_cmds"][0]
    assert "rm -rf" in app["uninstall_cmds"][0]
    assert "pkill -f yolo26_tensorrt" not in app["uninstall_cmds"][0]
    assert "--no-upgrade" in dependency_command
    assert "apt-get install -y --no-upgrade build-essential cmake libopencv-dev" in dependency_command
    assert "apt-get install" not in dependency_command.split("libnvinfer-dev", 1)[0].rsplit("&&", 1)[-1]


def test_native_tensorrt_sources_are_bundled_with_client():
    assert (ASSET_ROOT / "run.sh").is_file()
    assert (ASSET_ROOT / "src" / "main.cpp").is_file()
    source = (ASSET_ROOT / "src" / "main.cpp").read_text(encoding="utf-8")

    assert "NV_TENSORRT_MAJOR >= 10" in source
    assert "enqueueV2" in source
    assert "enqueueV3" in source


def test_engine_build_handles_tensorrt_8_and_10_cli_options():
    run_script = (ASSET_ROOT / "run.sh").read_text(encoding="utf-8")

    assert "--workspace=4096" in run_script
    assert "--memPoolSize=workspace:4096" in run_script
    assert "--minShapes" not in run_script
    assert "2e947b787d9e787b93a16772a5f55b1d4d8c4d86f53146149c5d6a642442d6f7" in run_script
