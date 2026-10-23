"""Device routing and authenticated bridge behavior without physical hardware."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from seeed_jetson_develop.core.runner import SSHRunner
from seeed_jetson_develop.modules.agent import device_bridge
from seeed_jetson_develop.modules.agent.device_bridge import DeviceBridge, validate_values
from seeed_jetson_develop.modules.agent.task_context import match_task, resolve_skills


class FakeSSH(SSHRunner):
    def run(self, command, **kwargs):
        self.last_command = command
        return 0, "jetson-fake"


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    runner = FakeSSH("192.0.2.12", "seeed", "private-password", port=2222)
    active = [runner]
    events = []
    monkeypatch.setattr(device_bridge, "get_runner", lambda: active[0])
    bridge = DeviceBridge(lambda *event: events.append(event), lambda _payload: None, tmp_path)
    yield bridge, active, events
    bridge.close()


def request(bridge, payload, token=None):
    runtime = json.loads(bridge.manifest.read_text())
    req = urllib.request.Request(runtime["url"], data=json.dumps({
        "target": runtime["target"], **payload,
    }).encode(), headers={"Authorization": "Bearer " + (token or runtime["token"])})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=2) as response:
        return json.load(response)


def test_bridge_keeps_credentials_private_and_requires_permission(runtime):
    bridge, active, _ = runtime
    manifest = bridge.manifest.read_text()
    assert active[0].password not in manifest
    assert json.loads(manifest)["target"]["port"] == 2222
    if os.name != "nt":
        assert bridge.manifest.stat().st_mode & 0o077 == 0
    with pytest.raises(urllib.error.HTTPError) as denied:
        request(bridge, {"action": "ssh", "command": "hostname"})
    assert denied.value.code == 400
    bridge.allow_commands = True
    assert request(bridge, {"action": "ssh", "command": "hostname"})["output"] == "jetson-fake"
    assert active[0].last_command == "hostname"


def test_bridge_rejects_invalid_token_and_changed_device(runtime):
    bridge, active, _ = runtime
    with pytest.raises(urllib.error.HTTPError) as denied:
        request(bridge, {"action": "status"}, token="wrong")
    assert denied.value.code == 403
    bridge.allow_commands = True
    active[0] = FakeSSH("192.0.2.13")
    with pytest.raises(urllib.error.HTTPError):
        request(bridge, {"action": "ssh", "command": "hostname"})
    with pytest.raises(urllib.error.HTTPError):
        request(bridge, {"action": "publish", "values": {"angle_deg": 1}})


def test_standalone_helper_and_visual_publication(runtime):
    bridge, _, events = runtime
    helper = Path(device_bridge.__file__).with_name("bridge_client.py")
    result = subprocess.run([sys.executable, str(helper), "--runtime", str(bridge.manifest),
                             "publish", "--source", "arm", "--json", '{"joint_deg": 14.5}'],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["queued"]
    assert events == [("publish", {"source": "arm", "values": {"joint_deg": 14.5}, "target": bridge.target})]
    assert request(bridge, {"action": "camera", "source": "/dev/video2"})["queued"]
    assert events[-1] == ("camera", {"operation": "start", "source": "/dev/video2", "target": bridge.target})


def test_connect_uses_saved_credentials_and_verifies_before_activation(monkeypatch, tmp_path):
    saved = {"remote_last_host": "192.0.2.42", "remote_last_user": "robot",
             "remote_last_password": "secret", "remote_last_sudo_password": "sudo-secret"}
    active = [None]
    connected = []
    monkeypatch.setattr(device_bridge.config, "load", lambda: saved)
    monkeypatch.setattr(device_bridge, "get_runner", lambda: active[0])
    monkeypatch.setattr(device_bridge, "set_runner", lambda runner: active.__setitem__(0, runner))
    monkeypatch.setattr(SSHRunner, "run", lambda self, *args, **kwargs: (1, "unreachable"))
    bridge = DeviceBridge(lambda *_: None, connected.append, tmp_path)
    try:
        bridge.allow_commands = True
        with pytest.raises(ValueError, match="unreachable"):
            bridge.handle({"action": "connect", "target": bridge.target})
        assert active[0] is None
        monkeypatch.setattr(SSHRunner, "run", lambda self, *args, **kwargs: (0, ""))
        assert bridge.handle({"action": "connect", "target": bridge.target})["ok"]
        assert active[0].password == "secret"
        assert active[0].sudo_password == "sudo-secret"
        assert connected[0]["ip"] == saved["remote_last_host"]
    finally:
        manifest = bridge.manifest
        bridge.close()
    assert not manifest.exists()


@pytest.mark.parametrize("text, expected", [
    ("读取机械臂关节状态", "arm_read"), ("控制机械臂抓取", "arm"),
    ("read robot arm joints", "arm_read"), ("move so-arm to target", "arm"),
    ("打开摄像头", "camera"), ("network sharing", "network"),
    ("连接 SSH", "ssh"), ("read lidar sensor", "radar"), ("build my project", "free"),
])
def test_task_routes(text, expected):
    assert match_task(text) == expected


def test_skill_resolution_uses_exact_paths_and_installed_precedence(monkeypatch, tmp_path):
    from seeed_jetson_develop.modules.agent import task_context
    installed = tmp_path / "developtool-device" / "SKILL.md"
    installed.parent.mkdir()
    installed.write_text("installed skill")
    monkeypatch.setattr(task_context, "local_skills_dirs", lambda _agent: (tmp_path,))
    monkeypatch.setattr(Path, "rglob", lambda *_: pytest.fail("Must not scan skill trees"))
    paths = resolve_skills("codex", "network")
    assert paths[0] == installed
    assert paths[1].parent.name == "jetson-pc-wired-share"


@pytest.mark.parametrize("values", [[], {}, {"x": []}, {"x": "a" * 501}, {"": 1}, {"x": float("nan")}])
def test_invalid_readings_are_rejected(values):
    with pytest.raises(ValueError):
        validate_values(values)


def test_new_skill_copies_and_bilingual_placeholders_match():
    from string import Formatter
    root = Path(__file__).resolve().parents[1]
    for slug in ("developtool-device", "jetson-pc-wired-share", "soarm-control"):
        copies = [
            (root / base / agent / slug / marker).read_text(encoding="utf-8")
            for base in ("skills", "seeed_jetson_develop/skills")
            for agent, marker in (("openclaw", "SKILL.md"), ("claude", "CLAUDE.md"), ("codex", "AGENTS.md"))
        ]
        assert len(set(copies)) == 1
    locales = root / "seeed_jetson_develop/locales"
    english = json.loads((locales / "en/agent.json").read_text())
    chinese = json.loads((locales / "zh-CN/agent.json").read_text())
    assert english.keys() == chinese.keys()
    for key in english:
        fields = lambda value: {field for _, field, _, _ in Formatter().parse(value) if field}
        assert fields(english[key]) == fields(chinese[key]), key


def test_resume_uses_the_specific_session(monkeypatch):
    from seeed_jetson_develop.modules.agent import backend
    monkeypatch.setattr(backend, "find_cli", lambda agent: agent)
    codex = backend.build_command("codex", "next", continue_session=True, resume_id="thread-id")
    claude = backend.build_command("claude", "next", continue_session=True, resume_id="session-id")
    assert codex[1:4] == ["exec", "resume", "thread-id"]
    assert "--last" not in codex
    assert claude[claude.index("--resume") + 1] == "session-id"
    assert "--continue" not in claude
    assert "--skip-git-repo-check" in codex
    restricted = backend.build_command("codex", "next", continue_session=True,
                                       full_access=False, resume_id="thread-id")
    assert "-s" not in restricted  # exec resume does not accept this option.
    assert 'sandbox_mode="workspace-write"' in restricted


def test_device_stream_decodes_frames_and_readings_and_closes_channel(monkeypatch):
    import base64
    import paramiko
    from unittest.mock import MagicMock
    from seeed_jetson_develop.modules.agent.visual_panel import DeviceStream

    client = MagicMock()
    stdout = MagicMock()
    client.exec_command.return_value = (None, stdout, None)
    channel = stdout.channel
    chunks = [b'SEEED_FRAME:' + base64.b64encode(b'jpeg-bytes') + b'\nSEEED_DATA:{"cpu_percent": 7}\n']
    channel.recv_ready.side_effect = lambda: bool(chunks)
    channel.recv.side_effect = lambda _size: chunks.pop(0)
    channel.exit_status_ready.return_value = True
    monkeypatch.setattr(paramiko, "SSHClient", lambda: client)
    worker = DeviceStream(FakeSSH("192.0.2.1", password="secret", port=2222), "camera", "/dev/video2")
    frames, readings = [], []
    worker.frame.connect(frames.append)
    worker.readings.connect(readings.append)
    worker.run()
    assert frames == [b"jpeg-bytes"]
    assert readings == [{"cpu_percent": 7}]
    assert client.connect.call_args.kwargs["port"] == 2222
    assert "python3 -u -c" in client.exec_command.call_args.args[0]
    client.close.assert_called_once()
    assert worker._channel is None


def test_camera_source_stays_data_and_stream_stop_closes_connection():
    import ast
    from unittest.mock import MagicMock
    from seeed_jetson_develop.modules.agent.visual_panel import camera_script, DeviceStream
    source = "rtsp://camera/path'; $(touch /tmp/not-a-command)"
    tree = ast.parse(camera_script(source))
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "source")
    assert ast.literal_eval(assignment.value) == source
    worker = DeviceStream(FakeSSH("192.0.2.1"), "camera")
    worker._channel = channel = MagicMock()
    worker._client = client = MagicMock()
    worker.stop()
    channel.close.assert_called_once()
    client.close.assert_called_once()


def test_cancelling_an_unresponsive_cli_finishes_the_worker(monkeypatch):
    import threading
    from qtpy.QtCore import Qt
    from seeed_jetson_develop.modules.agent import backend
    script = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready',flush=True); time.sleep(60)"
    monkeypatch.setattr(backend, "build_command", lambda *args, **kwargs: [sys.executable, "-u", "-c", script])
    worker = backend.AgentCliSession("codex", "", "")
    ready = threading.Event()
    results = []
    worker.token.connect(lambda _text: ready.set(), Qt.DirectConnection)
    worker.done.connect(results.append, Qt.DirectConnection)
    worker.start()
    try:
        assert ready.wait(3), "CLI did not start"
        worker.cancel()
        assert worker.wait(5000), "Cancelled CLI left a running QThread"
        assert results == [-1]
    finally:
        if worker.isRunning():
            worker.cancel()
            worker.wait(5000)
