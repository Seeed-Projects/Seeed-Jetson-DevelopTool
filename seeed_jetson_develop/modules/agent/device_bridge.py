"""Authenticated loopback bridge from a local agent CLI to DevelopTool's SSH runner.

Credentials stay in the application. The private manifest contains a temporary
capability token and public device identity, and is removed on shutdown.
"""
from __future__ import annotations

import hmac
import json
import math
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from seeed_jetson_develop.core import config
from seeed_jetson_develop.core.runner import SSHRunner, get_runner, set_runner


def device_target(runner=None) -> dict:
    runner = get_runner() if runner is None else runner
    if isinstance(runner, SSHRunner):
        return {"host": runner.host, "username": runner.username, "port": runner.port}
    saved = config.load()
    return {"host": saved.get("remote_last_host", ""),
            "username": saved.get("remote_last_user", "seeed") or "seeed", "port": 22}


def validate_values(values) -> dict:
    if not isinstance(values, dict) or not values or len(values) > 64:
        raise ValueError("Expected 1–64 named readings")
    for key, value in values.items():
        if not isinstance(key, str) or not key or len(key) > 100:
            raise ValueError("Invalid reading name")
        if not isinstance(value, (str, int, float, bool, type(None))) or len(str(value)) > 500:
            raise ValueError("Readings must be scalar values with units in the name")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Readings must be finite")
    return values


class DeviceBridge:
    def __init__(self, dispatch, connected, parent_dir=None):
        self._dispatch = dispatch
        self._connected = connected
        self._target = device_target()
        self.allow_commands = False
        self._closed = False
        self._connect_lock = threading.Lock()
        self._token = secrets.token_urlsafe(32)
        self._temp = tempfile.TemporaryDirectory(prefix="seeed-agent-", dir=parent_dir)
        self.manifest = Path(self._temp.name) / "runtime.json"
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass  # Neither commands nor capability tokens belong in HTTP logs.

            def do_POST(self):
                if self.headers.get("Origin") or not hmac.compare_digest(
                        self.headers.get("Authorization", ""), "Bearer " + bridge._token):
                    self.send_error(403)
                    return
                try:
                    if self.path != "/action":
                        raise ValueError("Unknown endpoint")
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 65536:
                        raise ValueError("Invalid request size")
                    self.connection.settimeout(5)
                    payload = json.loads(self.rfile.read(size))
                    result = bridge.handle(payload)
                    body = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
                    self.send_response(200)
                except (ValueError, TypeError, KeyError) as exc:
                    body = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                    self.send_response(400)
                except Exception:
                    body = b'{"ok": false, "error": "Device bridge request failed"}'
                    self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.manifest.write_text(json.dumps({
            "url": f"http://127.0.0.1:{self._server.server_port}/action",
            "token": self._token, "target": self._target,
        }), encoding="utf-8")
        self.manifest.chmod(0o600)
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        kwargs={"poll_interval": 0.1}, daemon=True)
        self._thread.start()

    @property
    def target(self):
        return dict(self._target)

    def _runner(self) -> SSHRunner:
        runner = get_runner()
        if not isinstance(runner, SSHRunner) or device_target(runner) != self._target:
            raise ValueError("Target disconnected or changed; start a new task with the current device")
        return runner

    def _connect(self) -> SSHRunner:
        with self._connect_lock:
            if isinstance(get_runner(), SSHRunner):
                return self._runner()
            if not self._target["host"] or device_target() != self._target:
                raise ValueError("No matching saved SSH target; configure Remote Dev first")
            saved = config.load()
            runner = SSHRunner(self._target["host"], username=self._target["username"],
                               port=self._target["port"], password=saved.get("remote_last_password", ""),
                               sudo_password=saved.get("remote_last_sudo_password", ""))
            rc, output = runner.run("true", timeout=10, should_cancel=lambda: self._closed or not self.allow_commands)
            if rc:
                raise ValueError(f"SSH connection failed: {output}")
            if self._closed or not self.allow_commands or isinstance(get_runner(), SSHRunner) or device_target() != self._target:
                raise ValueError("Device selection changed during connection")
            set_runner(runner)
            self._connected({"ip": runner.host, "name": runner.host, "username": runner.username})
            return runner

    def handle(self, payload: dict) -> dict:
        if self._closed:
            raise ValueError("Runtime closed")
        if not isinstance(payload, dict) or payload.get("target") != self._target:
            raise ValueError("Request does not match this runtime's device")
        action = payload.get("action")
        if action == "status":
            runner = get_runner()
            return {"ok": True, "target": self.target, "connected": isinstance(runner, SSHRunner)
                    and device_target(runner) == self._target, "commands_enabled": self.allow_commands}
        if action in ("ssh", "connect"):
            if not self.allow_commands:
                raise ValueError("Enable Auto-execute to use the SSH command bridge")
            runner = self._connect() if action == "connect" else self._runner()
            if action == "connect":
                return {"ok": True, "target": self.target}
            command = payload.get("command")
            if not isinstance(command, str) or not command.strip() or len(command) > 32768:
                raise ValueError("Expected a nonempty remote command")
            timeout = max(1, min(int(payload.get("timeout", 30)), 600))
            rc, output = runner.run(command, timeout=timeout, should_cancel=lambda: self._closed or not self.allow_commands)
            return {"ok": rc == 0, "returncode": rc, "output": output[-48000:]}
        self._runner()  # Reject stale publications and visual controls after a device change.
        if action == "publish":
            values = validate_values(payload.get("values"))
            source = str(payload.get("source", "agent"))[:100]
            self._dispatch("publish", {"values": values, "source": source, "target": self.target})
        elif action in ("camera", "monitor"):
            operation = payload.get("operation", "start")
            if operation not in ("start", "stop"):
                raise ValueError("Expected start or stop")
            source = str(payload.get("source", "/dev/video0"))
            if len(source) > 2048:
                raise ValueError("Camera source too long")
            self._dispatch(action, {"operation": operation, "source": source, "target": self.target})
        elif action == "network":
            self._dispatch("network", {"target": self.target})
        else:
            raise ValueError("Unknown action")
        return {"ok": True, "queued": True, "action": action}

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.allow_commands = False
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1)
        self._temp.cleanup()
