#!/usr/bin/env python3
"""End-to-end native MCP smoke test, irrevocably restricted to mock profiles."""

from __future__ import annotations

import argparse
import contextlib
import json
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time

from runtime import checked, environment, interpreter, isolated_mock_paths, repository


class Client:
    def __init__(self, process):
        self.process = process
        self.inbox = queue.Queue()
        self.serial = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for line in self.process.stdout:
                self.inbox.put(json.loads(line))
        except (ValueError, OSError) as exc:
            self.inbox.put(exc)
        finally:
            self.inbox.put(EOFError("MCP server closed stdout"))

    def send(self, method, params=None, *, notification=False):
        self.serial += 1
        message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notification:
            message["id"] = self.serial
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()
        return self.serial

    def request(self, method, params=None, timeout=90):
        serial = self.send(method, params)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"MCP {method} exceeded {timeout}s")
            response = self.inbox.get(timeout=remaining)
            if isinstance(response, Exception):
                raise response
            if response.get("id") != serial:  # native notifications/tools/list_changed
                continue
            if "error" in response:
                raise ValueError(response["error"])
            return response["result"]

    def tool(self, name, arguments=None, *, expect_error=False):
        result = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        decoded = []
        for block in result.get("content", []):
            if block.get("type") == "text":
                try:
                    value = json.loads(block["text"])
                except (ValueError, KeyError):
                    continue
                if isinstance(value, dict):
                    decoded.append(value)
        if not decoded:
            raise ValueError(f"{name}: no structured result")
        value = decoded[-1]
        failed = bool(result.get("isError")) or value.get("ok") is False
        if failed != expect_error:
            raise ValueError(f"{name}: unexpected result {value}")
        return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--python", dest="python_path")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    repo = repository(args.repo)
    py = interpreter(repo, args.python_path)
    env = environment(repo, "mock", "mock", ["mock"])
    report = checked(repo, py, "mock", "mock", ["mock"], env)
    if not report["local_configuration_ok"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    output = Path(args.output).expanduser().absolute() if args.output else Path(tempfile.mkdtemp(prefix="rebot-skill-smoke-"))
    if args.output:
        output.mkdir(parents=True, exist_ok=False)  # never overwrite a prior receipt
    isolated_mock_paths(env, output)
    receipt = {"schema": "rebot-arm-grasp.smoke/1", "software_passed": False,
               "physical_validation": "not_performed", "mode": "mock",
               "contact_fixture": "synthetic MockArm gripper stop at 45% travel",
               "preflight": report, "output": str(output), "steps": []}
    with (output / "server.stderr.log").open("w") as log:
        process = subprocess.Popen([py, str(Path(__file__).with_name("mock_fixture_server.py"))], cwd=repo, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=log, text=True, bufsize=1)
        try:
            client = Client(process)
            client.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                          "clientInfo": {"name": "rebot-skill-smoke", "version": "1"}})
            client.send("notifications/initialized", notification=True)
            client.tool("world_state")  # force the actual runtime to exist before tools/list
            catalog = client.request("tools/list")["tools"]
            names = {spec["name"] for spec in catalog}
            required = {"world_state", "get_observation", "localize_object", "preview_grasp",
                        "grasp_object", "pick_and_place", "verify_last_action", "emergency_stop", "reset_stop", "move_home"}
            if required - names:
                raise ValueError(f"tools withheld unexpectedly: {sorted(required - names)}")
            receipt["catalog_size"] = len(catalog)
            for name, arguments, expect_error in [
                ("get_observation", {}, False),
                ("localize_object", {"label": "red cube"}, False),
                ("preview_grasp", {"label": "red cube"}, False),
                ("grasp_object", {"label": "absent purple teapot"}, True),
                ("pick_and_place", {"object": "red cube"}, False),
                ("verify_last_action", {}, False),
                ("emergency_stop", {}, False),
                ("move_home", {}, True),
                ("reset_stop", {}, False),
                ("world_state", {}, False),
            ]:
                value = client.tool(name, arguments, expect_error=expect_error)
                if name == "emergency_stop" and not value.get("stopped"):
                    raise ValueError("emergency_stop did not report stopped")
                if name == "world_state" and value.get("stopped"):
                    raise ValueError("reset_stop did not clear the mock latch")
                receipt["steps"].append({"tool": name, "expected_error": expect_error, "result": value})
            receipt["software_passed"] = True
        except Exception as exc:
            receipt["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            # This process can only own mock devices. Never reuse this teardown for hardware.
            with contextlib.suppress(BrokenPipeError, OSError):
                process.stdin.close()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            receipt["server_exit_code"] = process.returncode
    if receipt["server_exit_code"] != 0:
        receipt["software_passed"] = False
    (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"software_passed": receipt["software_passed"],
                      "physical_validation": "not_performed", "receipt": str(output / "receipt.json"),
                      **({"error": receipt["error"]} if "error" in receipt else {})}, ensure_ascii=False, indent=2))
    return 0 if receipt["software_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
