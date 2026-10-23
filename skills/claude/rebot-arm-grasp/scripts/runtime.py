#!/usr/bin/env python3
"""Portable, device-free checks and a native CASCADE stdio MCP launcher.

Only `serve` can attach hardware. Mock execution clears inherited selectors.
No SDK objects, cameras, sockets or arm connections are created by `check`.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


SKILL = Path(__file__).resolve().parents[1]
SELECTORS = ("CASCADE_ROBOT", "CASCADE_BASE", "CASCADE_ARMS", "CASCADE_ARM",
             "CASCADE_CAMERAS", "CASCADE_CAMERA")


def repository(value: str | None) -> Path:
    candidates = [Path(value).expanduser()] if value else [Path.cwd(), *Path.cwd().parents]
    for candidate in candidates:
        root = candidate.resolve()
        if all((root / p).is_file() for p in (
            "pyproject.toml", "configs/demo.yaml", "src/cascade/apps/mcp_server.py",
        )):
            return root
    raise ValueError("CASCADE source checkout not found; pass --repo /absolute/path/to/cascade")


def interpreter(repo: Path, explicit: str | None) -> str:
    # Do not resolve Python symlinks: that would bypass the venv's pyvenv.cfg.
    if explicit:
        candidates = [Path(explicit).expanduser().absolute()]
    else:
        candidates = [repo / ".venv/bin/python", repo / ".venv/Scripts/python.exe",
                      repo.parent / ".demo/bin/python", Path(sys.executable)]
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise ValueError("Python executable not found; create a uv venv or pass --python")


def selection(mode: str, arm: str | None, cameras: str | None) -> tuple[str, list[str]]:
    if mode == "hardware" and (not arm or not cameras):
        raise ValueError("hardware requires explicit --arm and --cameras; no rig is guessed")
    selected_arm = "mock" if arm is None else arm
    selected_cameras = [c.strip() for c in ("mock" if cameras is None else cameras).split(",")]
    for name in [selected_arm, *selected_cameras]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError(f"invalid profile name: {name!r}")
    if len(set(selected_cameras)) != len(selected_cameras):
        raise ValueError("duplicate camera profiles")
    return selected_arm, selected_cameras


def environment(repo: Path, mode: str, arm: str, cameras: list[str],
                inherited: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if inherited is None else inherited)
    if mode == "mock":
        env = {k: v for k, v in env.items() if not k.startswith("CASCADE_")}
        env.update(CASCADE_OCCUPANCY="0", CASCADE_GRASP_BACKEND="obb",
                   CASCADE_GRASP_EXECUTOR="analytic", CASCADE_BELIEFS="0",
                   CASCADE_PREWARM="0", CASCADE_EPISODIC="0", CASCADE_PROGRAMS="0")
    else:
        for key in SELECTORS:
            env.pop(key, None)
        env["CASCADE_START_STOPPED"] = "1"
    env.update(PYTHONPATH=str(repo / "src"), PYTHONUNBUFFERED="1",
               CASCADE_ARM=arm, CASCADE_CAMERAS=",".join(cameras),
               CASCADE_VIEW="0", CASCADE_STREAM="0")
    return env


def isolated_mock_paths(env: dict[str, str], output: Path) -> None:
    """Keep mock learning outcomes away from a physical rig's persistent priors."""
    env.update(CASCADE_RUN_DIR=str(output / "run"),
               CASCADE_BELIEFS_PATH=str(output / "beliefs.json"),
               CASCADE_GRASP_MEMORY_PATH=str(output / "grasp-memory.json"),
               CASCADE_ENVELOPE_PATH=str(output / "envelope.json"),
               CASCADE_EPISODIC_PATH=str(output / "episodic"))


def source_status(repo: Path) -> dict:
    manifest = json.loads((SKILL / "references/source-manifest.json").read_text())
    changed = []
    for relative, digest in manifest["contract_sha256"].items():
        path = repo / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            changed.append(relative)
    try:
        result = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=False)
        commit = result.stdout.strip() if result.returncode == 0 else None
    except FileNotFoundError:
        commit = None  # source distributions can retain the files without Git
    return {"reviewed_commit": manifest["source_commit"],
            "current_commit": commit,
            "contract_matches": not changed, "changed_contract_files": changed}


def calibration_problem(camera, record, arm_name: str, ee_frame: str) -> str | None:
    ext = camera.get("extrinsics")
    if record is None:
        return "missing or rejected hand_eye_json; inline/reference transforms are not admitted"
    expected = {"camera": camera.get("name"), "camera_serial": camera.get("serial"),
                "arm": arm_name, "ee_frame": ee_frame,
                "mode": ext.get("mode") if ext else None}
    for key, value in expected.items():
        if not value or str(getattr(record, key, "")) != str(value):
            return f"hand-eye binding mismatch: {key} (check this rig's profile and record)"
    return None


def local_weight_problem(value: str, repo: Path) -> str | None:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo / path  # serve uses this exact working directory
    if not path.is_file() or path.stat().st_size == 0:
        return f"detector weights absent/empty: {path}; prepare locally before hardware startup"
    with path.open("rb") as stream:
        if stream.read(256).startswith(b"version https://git-lfs.github.com/spec/v1"):
            return f"detector weights are a Git LFS pointer: {path}"
    return None


def inspect(repo: Path, mode: str, arm: str, cameras: list[str]) -> dict:
    """Load config/geometry only, never build_runtime or make_arm/make_camera."""
    report = {"local_configuration_ok": False, "runtime_readiness": "unverified",
              "devices_accessed": False, "mode": mode, "repo": str(repo),
              "python": sys.executable, "arm": arm, "cameras": cameras,
              "errors": [], "warnings": []}
    errors = report["errors"]
    report["source"] = source_status(repo)
    if not report["source"]["contract_matches"]:
        (errors if mode == "hardware" else report["warnings"]).append(
            "core source differs from reviewed contract; audit before hardware use")
    required = ["numpy", "yaml", "cv2", "jsonschema", "pinocchio"]
    if mode == "hardware":
        required += ["motorbridge", "ultralytics", "torch", "zmq", "msgpack", "msgpack_numpy", "scipy"]
    report["dependencies"] = {name: importlib.util.find_spec(name) is not None for name in required}
    errors.extend(f"missing dependency: {name}" for name, found in report["dependencies"].items() if not found)
    if errors:
        return report
    sys.path.insert(0, str(repo / "src"))
    from cascade.config import Cfg, load_demo_config
    cfg = load_demo_config(arm=arm, cameras=cameras, llm="mock")
    camera_profiles = [Cfg(c) for c in cfg.cameras]
    # Match MCP's global model override, then primary-camera detector precedence.
    if os.environ.get("CASCADE_DETECTOR_MODEL"):
        cfg._data["detector"]["model"] = os.environ["CASCADE_DETECTOR_MODEL"]
    detector = cfg.camera.get("detector") or cfg.detector
    report["configured_detector"] = {key: detector.get(key) for key in ("type", "model", "device", "prompt_free")}
    import cascade.config as config_module
    report["imported_config"] = str(Path(config_module.__file__).resolve())
    if Path(config_module.__file__).resolve() != repo / "src/cascade/config.py":
        errors.append("imported a different checkout")
    if mode == "mock":
        if cfg.arm.type != "mock" or any(c.type != "mock" for c in camera_profiles):
            errors.append("mock mode accepts only mock arm AND mock cameras")
    else:
        if cfg.arm.type != "rebot_rs":
            errors.append("hardware launcher admits only type rebot_rs; never substitute rebot_rs_mb/DM")
        if any(c.type != "realsense" for c in camera_profiles):
            errors.append("hardware launcher admits calibrated serial-bound RealSense RGB-D profiles")
        if importlib.util.find_spec("pyrealsense2") is None:
            errors.append("missing dependency: pyrealsense2 (use this camera's platform build)")
        if cfg.arm.get("n_joints") != 6 or list(cfg.arm.get("joint_signs", [])) != [-1] * 6:
            errors.append("B601 RS requires six controlled joints and its signed URDF convention")
        if not cfg.occupancy.get("enabled") or not cfg.occupancy.get("required"):
            errors.append("reBot occupancy must remain enabled and required")
        contact = cfg.safety.get("contact_monitor")
        if not contact or not contact.get("enabled") or contact.get("mode") != "enforce":
            errors.append("reBot contact monitor must remain enabled in enforce mode")
        for key in ("wrist_camera_up", "tool_volume"):
            if not cfg.safety.get(key):
                errors.append(f"missing reBot safety configuration: {key}")
        if not cfg.get("verify_effects"):
            errors.append("verify_effects must remain enabled")
        if detector.type != "yoloe":
            errors.append("hardware launcher admits the local YOLOE detector; no synthetic/VLM substitution")
        else:
            from cascade.perception.detector import OpenVocabDetector
            paths = [str(detector.model)]
            if detector.get("prompt_free", True):
                # Reuse the real filename rule without constructing/loading the detector.
                probe = object.__new__(OpenVocabDetector)
                probe._model_path = str(detector.model)
                prompt_free = probe._pf_path()
                if prompt_free:
                    paths.append(prompt_free)
            for value in dict.fromkeys(paths):
                problem = local_weight_problem(value, repo)
                if problem:
                    errors.append(problem)
        sdk = Path(cfg.arm.get("sdk_path", ""))
        if not (sdk / "reBotArm_control_py/actuator.py").is_file():
            errors.append(f"SDK actuator.py missing under arm.sdk_path: {sdk}")
        from cascade.calibration.dataset import load_hand_eye
        for camera in camera_profiles:
            ext = camera.get("extrinsics")
            path = ext.get("hand_eye_json") if ext else None
            record = load_hand_eye(path) if path else None
            problem = calibration_problem(camera, record, arm, cfg.arm.get("ee_frame", ""))
            if problem:
                errors.append(f"camera {camera.name}: {problem}")
        report["warnings"].append(
            "Calibration quality/bindings are local checks; confirm the actual camera/base mounting onsite. "
            "CAN ownership, SDK import dependencies, sensor captures and sidecar readiness are NOT probed.")
    n = int(cfg.arm.get("n_joints", 0))
    for key in ["home_q", "handover_q"] + (["park_q"] if mode == "hardware" else []):
        values = cfg.arm.get(key, [])
        if len(values) != n or not all(math.isfinite(float(v)) for v in values):
            errors.append(f"{key} must contain {n} finite joint values")
    if not errors:
        from cascade.control.kinematics import Kinematics
        kin = Kinematics(cfg.arm.model, cfg.arm.ee_frame, n_controlled=n,
                         joint_signs=list(cfg.arm.joint_signs))
        report["model"] = cfg.arm.model
        report["home_tcp_m"] = kin.fk(cfg.arm.home_q)[:3, 3].tolist()
        if mode == "hardware":
            from cascade.perception.robot_mask import build_mesh_body_mask
            # Loading geometry with a callback that cannot read hardware.
            mask = build_mesh_body_mask(cfg.arm, kin, lambda: None, name=arm)
            if mask is None:
                errors.append("reBot requires a loadable URDF mesh body mask, no capsule fallback")
    report["configured_grasp_backend"] = cfg.grasp.get("backend")
    report["resolved_configuration_sha256"] = hashlib.sha256(
        json.dumps(cfg.as_dict(), sort_keys=True).encode()).hexdigest()
    report["local_configuration_ok"] = not errors
    return report


def checked(repo: Path, py: str, mode: str, arm: str, cameras: list[str], env: dict) -> dict:
    command = [py, str(Path(__file__).resolve()), "_inspect", "--repo", str(repo),
               "--mode", mode, "--arm", arm, "--cameras", ",".join(cameras)]
    completed = subprocess.run(command, cwd=repo, env=env, capture_output=True,
                               text=True, timeout=60, check=False)
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("runtime inspection did not return valid JSON; inspect stderr") from exc
    if completed.returncode != 0:
        raise ValueError(report.get("error", "runtime inspection failed"))
    return report


def configuration(repo: Path, py: str, mode: str, arm: str, cameras: list[str], env: dict) -> str:
    args = [str(Path(__file__).resolve()), "serve", "--repo", str(repo), "--python", py,
            "--mode", mode, "--arm", arm, "--cameras", ",".join(cameras)]
    lines = ["[mcp_servers.cascade_rebot]", f"command = {json.dumps(py, ensure_ascii=False)}",
             f"args = {json.dumps(args, ensure_ascii=False)}", "startup_timeout_sec = 90",
             "tool_timeout_sec = 240", "", "[mcp_servers.cascade_rebot.env]"]
    # Use the runtime's registry, which explicitly excludes credentials.
    registry_spec = importlib.util.spec_from_file_location(
        "rebot_skill_mcp_env", repo / "src/cascade/apps/mcp_env.py")
    registry = importlib.util.module_from_spec(registry_spec)
    registry_spec.loader.exec_module(registry)
    allowed = set(registry.FORWARDED) | {"PYTHONPATH", "CASCADE_ARM", "CASCADE_CAMERAS",
                                        "CASCADE_START_STOPPED", "CASCADE_RUN_DIR"}
    for key, value in sorted(env.items()):
        if key in allowed \
                and not any(s in key.upper() for s in ("TOKEN", "SECRET", "PASSWORD", "API_KEY")):
            lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "mcp-config", "serve", "smoke", "_inspect"])
    parser.add_argument("--repo")
    parser.add_argument("--python", dest="python_path")
    parser.add_argument("--mode", choices=["mock", "hardware"], default="mock")
    parser.add_argument("--arm")
    parser.add_argument("--cameras")
    parser.add_argument("--output", help="new directory for smoke receipts/logs (smoke only)")
    args = parser.parse_args(argv)
    try:
        repo = repository(args.repo)
        arm, cameras = selection(args.mode, args.arm, args.cameras)
        if args.command == "smoke" and (args.mode != "mock" or arm != "mock" or cameras != ["mock"]):
            raise ValueError("smoke is fixed to --mode mock --arm mock --cameras mock")
        env = environment(repo, args.mode, arm, cameras)
        if args.command == "_inspect":
            # Also isolate direct calls to this internal, read-only endpoint.
            os.environ.clear()
            os.environ.update(env)
            with contextlib.redirect_stdout(sys.stderr):
                report = inspect(repo, args.mode, arm, cameras)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        py = interpreter(repo, args.python_path)
        report = checked(repo, py, args.mode, arm, cameras, env)
        if args.command == "check":
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["local_configuration_ok"] else 2
        if not report["local_configuration_ok"]:
            print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        if args.command == "mcp-config":
            print(configuration(repo, py, args.mode, arm, cameras, env), end="")
        elif args.command == "serve":
            if args.mode == "mock":
                output = Path(tempfile.mkdtemp(prefix="rebot-skill-mock-"))
                isolated_mock_paths(env, output)
                print(f"[rebot-skill] isolated mock records: {output}", file=sys.stderr)
            print("[rebot-skill] local configuration checked; runtime/onsite readiness unverified", file=sys.stderr)
            os.chdir(repo)
            os.execve(py, [py, "-m", "cascade.apps.mcp_server"], env)
        else:
            command = [py, str(SKILL / "scripts/smoke_test.py"), "--repo", str(repo), "--python", py]
            if args.output:
                command += ["--output", args.output]
            return subprocess.run(command, cwd=repo, env=env, check=False).returncode
        return 0
    except (OSError, ValueError, ImportError, subprocess.TimeoutExpired) as exc:
        # In serve mode stdout is exclusively the MCP protocol, including on failure.
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
