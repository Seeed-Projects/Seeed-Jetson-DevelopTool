"""Behavioral checks for the robot-operation skill's hardware boundary."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import yaml


SKILL = Path(__file__).resolve().parents[1]
HELPER = SKILL / "scripts/runtime.py"
spec = importlib.util.spec_from_file_location("rebot_skill_runtime", HELPER)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
if os.environ.get("REBOT_GRASP_REPO"):
    REPO = runtime.repository(os.environ["REBOT_GRASP_REPO"])
else:
    try:
        REPO = runtime.repository(str(SKILL.parent.parent))
    except ValueError:
        REPO = runtime.repository(None)


def invoke(*args, env=None):
    return subprocess.run([sys.executable, str(HELPER), *args, "--repo", str(REPO),
                           "--python", sys.executable],
                          env=env, text=True, capture_output=True, timeout=60)


def test_mock_environment_cannot_inherit_physical_selectors():
    inherited = {"PATH": "/bin", "CASCADE_ARM": "rebot_rs", "CASCADE_ARMS": "rebot_rs,rebot_rs_mb",
                 "CASCADE_CAMERAS": "d455f_scene", "CASCADE_ROBOT": "mixed_physical",
                 "CASCADE_BASE": "microduck", "CASCADE_OCCUPANCY": "1",
                 "CASCADE_GRASP_EXECUTOR": "vla", "CASCADE_START_STOPPED": "1",
                 "CASCADE_BELIEFS_PATH": "/operator/beliefs.json",
                 "CASCADE_MCP_TOKEN": "do-not-leak"}
    env = runtime.environment(REPO, "mock", "mock", ["mock"], inherited)
    assert env["CASCADE_ARM"] == "mock"
    assert env["CASCADE_CAMERAS"] == "mock"
    assert env["CASCADE_GRASP_BACKEND"] == "obb"
    assert env["CASCADE_GRASP_EXECUTOR"] == "analytic"
    assert env["CASCADE_OCCUPANCY"] == "0"
    assert env["CASCADE_BELIEFS"] == "0"
    assert not any(name in env for name in ["CASCADE_ROBOT", "CASCADE_BASE", "CASCADE_ARMS",
                                           "CASCADE_BELIEFS_PATH", "CASCADE_MCP_TOKEN"])
    assert inherited["CASCADE_ARM"] == "rebot_rs"  # no mutation of caller context


def test_hardware_starts_stopped_with_explicit_single_arm():
    env = runtime.environment(REPO, "hardware", "rebot_rs", ["onsite_scene"], {
        "CASCADE_ARMS": "wrong,arm", "CASCADE_ROBOT": "wrong", "CASCADE_BASE": "wrong",
        "CASCADE_START_STOPPED": "0", "CASCADE_OCCUPANCY_PORT": "45557",
    })
    assert env["CASCADE_START_STOPPED"] == "1"
    assert env["CASCADE_ARM"] == "rebot_rs"
    assert env["CASCADE_CAMERAS"] == "onsite_scene"
    assert env["CASCADE_OCCUPANCY_PORT"] == "45557"
    assert not any(key in env for key in ["CASCADE_ARMS", "CASCADE_ROBOT", "CASCADE_BASE"])


def test_all_mock_learning_paths_are_isolated(tmp_path):
    env = runtime.environment(REPO, "mock", "mock", ["mock"], {})
    runtime.isolated_mock_paths(env, tmp_path)
    for key in ["CASCADE_RUN_DIR", "CASCADE_BELIEFS_PATH", "CASCADE_GRASP_MEMORY_PATH",
                "CASCADE_ENVELOPE_PATH", "CASCADE_EPISODIC_PATH"]:
        assert Path(env[key]).is_relative_to(tmp_path)


@pytest.mark.parametrize("arm,cameras", [(None, None), ("rebot_rs", None), (None, "onsite")])
def test_hardware_requires_explicit_profile_selection(arm, cameras):
    with pytest.raises(ValueError, match="explicit"):
        runtime.selection("hardware", arm, cameras)


@pytest.mark.parametrize("name", ["../rebot_rs", "a,b", "$(touch /tmp/unwanted)", ""])
def test_profiles_are_names_not_paths_or_shell(name):
    with pytest.raises(ValueError, match="profile name"):
        runtime.selection("mock", name, "mock")


def test_interpreter_preserves_venv_symlink(tmp_path):
    binary = tmp_path / "python"
    binary.symlink_to(sys.executable)
    assert runtime.interpreter(REPO, str(binary)) == str(binary)


def test_generated_configuration_roundtrips_paths_and_excludes_secrets():
    import tomllib
    repo = REPO
    py = str(repo / '.venv/bin/a "quoted" interpreter')
    env = runtime.environment(repo, "hardware", "rebot_rs", ["onsite"], {
        "CASCADE_MCP_TOKEN": "secret-value", "CASCADE_API_KEY": "secret-key",
        "CASCADE_PRIVATE_KEY": "never-serialize-unknown-env",
        "CASCADE_OCCUPANCY_PORT": "45557", "CUDA_VISIBLE_DEVICES": "GPU-test-id",
    })
    text = runtime.configuration(repo, py, "hardware", "rebot_rs", ["onsite"], env)
    data = tomllib.loads(text)["mcp_servers"]["cascade_rebot"]
    assert data["command"] == py
    assert str(repo) in data["args"]
    assert data["env"]["CASCADE_START_STOPPED"] == "1"
    assert data["env"]["CASCADE_OCCUPANCY_PORT"] == "45557"
    assert data["env"]["CUDA_VISIBLE_DEVICES"] == "GPU-test-id"
    assert "secret-value" not in text and "secret-key" not in text
    assert "never-serialize-unknown-env" not in text


def test_calibration_must_match_device_and_robot():
    camera = {"name": "onsite", "serial": "camera-123", "extrinsics": {"mode": "eye_to_hand"}}
    fields = {"camera": "onsite", "camera_serial": "camera-123", "arm": "rebot_rs",
              "ee_frame": "gripper_end", "mode": "eye_to_hand"}
    assert runtime.calibration_problem(camera, None, "rebot_rs", "gripper_end")
    assert runtime.calibration_problem(camera, SimpleNamespace(**fields), "rebot_rs", "gripper_end") is None
    for key in fields:
        bad = SimpleNamespace(**{**fields, key: "other"})
        assert key in runtime.calibration_problem(camera, bad, "rebot_rs", "gripper_end")


def test_detector_weight_check_never_accepts_missing_empty_or_lfs(tmp_path):
    path = tmp_path / "model.pt"
    assert "absent" in runtime.local_weight_problem("model.pt", tmp_path)
    path.touch()
    assert "empty" in runtime.local_weight_problem(str(path), tmp_path)
    path.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 99999\n")
    assert "LFS pointer" in runtime.local_weight_problem(str(path), tmp_path)
    path.write_bytes(b"local binary fixture")
    assert runtime.local_weight_problem("model.pt", tmp_path) is None


@pytest.mark.parametrize("arm,cameras,extras", [
    ("rebot_rs", "mock", {}), ("mock", "d455f_scene", {}),
    ("mock", "mock", {"CASCADE_ARMS": "mock,rebot_rs"}),
])
def test_contact_fixture_refuses_physical_or_composed_selectors(arm, cameras, extras):
    env = runtime.environment(REPO, "mock", "mock", ["mock"])
    env.update(CASCADE_ARM=arm, CASCADE_CAMERAS=cameras, **extras)
    result = subprocess.run([sys.executable, str(SKILL / "scripts/mock_fixture_server.py")],
                            env=env, text=True, capture_output=True, timeout=10)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "refuses" in result.stderr


def test_source_drift_is_detected_from_file_bytes(tmp_path, monkeypatch):
    skill = tmp_path / "skill"
    (skill / "references").mkdir(parents=True)
    (skill / "references/source-manifest.json").write_text(json.dumps({
        "source_commit": "test", "contract_sha256": {"contract.py": "0" * 64},
    }))
    (tmp_path / "contract.py").write_text("changed source")
    monkeypatch.setattr(runtime, "SKILL", skill)
    state = runtime.source_status(tmp_path)
    assert not state["contract_matches"]
    assert state["changed_contract_files"] == ["contract.py"]


def test_smoke_refuses_hardware_before_launch():
    result = invoke("smoke", "--mode", "hardware", "--arm", "rebot_rs", "--cameras", "d455f_scene")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "smoke is fixed" in result.stderr


def test_serve_failure_does_not_corrupt_protocol_stdout():
    result = invoke("serve", "--mode", "hardware")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "explicit" in result.stderr


def test_mock_mode_refuses_physical_camera():
    pytest.importorskip("pinocchio")
    result = invoke("check", "--cameras", "d455f_scene")
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert not report["local_configuration_ok"]
    assert report["devices_accessed"] is False
    assert any("only mock" in error for error in report["errors"])


def test_check_is_source_bound_and_not_hardware_readiness():
    pytest.importorskip("pinocchio")
    result = invoke("check")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["local_configuration_ok"]
    assert report["runtime_readiness"] == "unverified"
    assert report["devices_accessed"] is False
    assert Path(report["imported_config"]) == REPO / "src/cascade/config.py"


def test_standard_skill_and_every_reference_are_distributed():
    import re
    text = (SKILL / "SKILL.md").read_text()
    metadata = yaml.safe_load(text.split("---", 2)[1])
    assert metadata["name"] == SKILL.name
    for relative in re.findall(r"\]\((references/[^)]+)\)", text):
        assert (SKILL / relative).is_file(), relative
    assert (SKILL / "agents/openai.yaml").is_file()
    assert (SKILL / "LICENSE").read_bytes() == (REPO / "LICENSE").read_bytes()
