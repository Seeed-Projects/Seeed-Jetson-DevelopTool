#!/usr/bin/env python3
"""
analyze_compatibility.py
Check Jetson facts against the compatibility matrix and produce a step plan.

Each step in `steps` has:
  status: "skip" | "run"
  reason: why it is skipped or needs to run

Exit codes:
  0 = ready or needs-adjustments
  2 = blocked (cannot proceed)

Usage:
  python3 analyze_compatibility.py \
    --facts /tmp/jetson-facts.json \
    --matrix references/jetpack_compatibility_matrix.json \
    --profile lerobot-env \
    --robot-type so-arm \
    --output /tmp/jetson-analysis-lerobot.json
"""

import argparse
import json
import re
import sys
from pathlib import Path


def ver_tuple(s: str) -> tuple:
    parts = re.findall(r"\d+", s or "")
    return tuple(int(p) for p in parts[:3]) if parts else (0,)


def step(status: str, reason: str) -> dict:
    return {"status": status, "reason": reason}


def analyze(facts: dict, profile: dict, robot_type: str) -> dict:
    issues   = []
    warnings = []
    actions  = []
    steps    = {}

    jp               = facts.get("jetpack", "")
    cuda             = facts.get("cuda", "")
    python           = facts.get("python", "")
    conda_installed  = facts.get("conda_installed", False)
    conda_envs       = facts.get("conda_envs", [])
    lerobot_inst     = facts.get("lerobot_installed", False)
    wheel_files      = facts.get("wheel_files", {})
    lerobot          = facts.get("lerobot_env", {})
    serial_group     = facts.get("serial_group", "unknown")
    brltty           = facts.get("brltty_installed", False)
    udev_rule        = facts.get("udev_rule", False)

    pinned           = profile.get("pinned_versions", {})
    pinned_torch     = pinned.get("torch", "")
    pinned_tv        = pinned.get("torchvision", "")
    pinned_numpy     = pinned.get("numpy", "1.26.0")
    pinned_opencv    = pinned.get("opencv_python", "4.10.0.84")

    torch_ver        = lerobot.get("torch_version", "")
    torch_cuda       = lerobot.get("torch_cuda", "")
    numpy_ver        = lerobot.get("numpy_version", "")
    opencv_ver       = lerobot.get("opencv_version", "")

    # ── Blocked checks ────────────────────────────────────────────────────────
    supported_jp = profile.get("supported_jetpack", [])
    if jp and not any(jp.startswith(v) for v in supported_jp):
        issues.append({
            "field": "jetpack", "found": jp, "required": supported_jp,
            "severity": "blocked",
            "detail": "JetPack 5.x / CUDA 11.x not supported — torch 2.8 requires CUDA 12+",
        })

    cuda_min = profile.get("cuda_min", "12.0")
    if cuda and ver_tuple(cuda) < ver_tuple(cuda_min):
        issues.append({
            "field": "cuda", "found": cuda, "required": f">={cuda_min}",
            "severity": "blocked",
        })

    py_required = profile.get("python_required", "3.10")
    # Python check applies to the conda env, not system python
    if "lerobot" in conda_envs:
        env_python = lerobot.get("torch_version", "")  # proxy: if torch exists env python ran
        # Only block on system python if no conda env yet
        pass
    elif python and not python.startswith(py_required):
        issues.append({
            "field": "python", "found": python, "required": py_required,
            "severity": "blocked",
            "detail": "Wheel files are cp310 only. Create the conda env with python=3.10.",
        })

    blocked = any(i["severity"] == "blocked" for i in issues)
    if blocked:
        overall = "blocked"
        return {
            "overall_status": overall,
            "facts_summary": _facts_summary(facts),
            "compatibility_status": overall,
            "issues": issues, "warnings": warnings,
            "recommended_actions": actions,
            "steps": {},
        }

    # ── Step plan ─────────────────────────────────────────────────────────────

    # §1a: miniconda
    if conda_installed:
        steps["miniconda"] = step("skip", f"conda already installed at {facts.get('conda_bin','')}")
    else:
        steps["miniconda"] = step("run", "conda not found — install Miniconda")
        actions.append({"action": "install_miniconda", "risk": "low"})

    # §1b: conda env
    if "lerobot" in conda_envs:
        steps["conda_env"] = step("skip", "conda env 'lerobot' already exists")
    else:
        steps["conda_env"] = step("run", "conda env 'lerobot' not found — create it")
        actions.append({
            "action": "create_conda_env",
            "commands": ["conda create -y -n lerobot python=3.10"],
            "risk": "low",
        })

    # §1c: git clone
    if lerobot_inst:
        steps["git_clone"] = step("skip", "lerobot package already installed in env")
    else:
        steps["git_clone"] = step("run", "lerobot not installed — clone Seeed-Projects/lerobot")

    # §2: download wheels
    torch_whl_ok = wheel_files.get("torch", False)
    tv_whl_ok    = wheel_files.get("torchvision", False)
    wheel_dir    = wheel_files.get("wheel_dir", "~/wheels")
    if torch_whl_ok and tv_whl_ok:
        steps["download_wheels"] = step("skip", f"both wheel files already present in {wheel_dir}")
    elif torch_whl_ok:
        steps["download_wheels"] = step("run", f"torchvision wheel missing in {wheel_dir}")
        actions.append({"action": "download_wheels", "missing": ["torchvision"], "risk": "low"})
    elif tv_whl_ok:
        steps["download_wheels"] = step("run", f"torch wheel missing in {wheel_dir}")
        actions.append({"action": "download_wheels", "missing": ["torch"], "risk": "low"})
    else:
        steps["download_wheels"] = step("run", f"wheel files not found in {wheel_dir}")
        actions.append({"action": "download_wheels", "missing": ["torch", "torchvision"], "risk": "low"})

    # §2: install torch (first time, before editable install)
    torch_ok = (
        torch_cuda == "True"
        and torch_ver
        and torch_ver.startswith(pinned_torch.split("+")[0] if pinned_torch else "2.8")
    )
    if torch_ok and lerobot_inst:
        steps["install_torch_pre"] = step("skip",
            f"torch {torch_ver} with CUDA already installed — lerobot also installed, "
            "skip pre-install; verify post-install still ok")
    else:
        steps["install_torch_pre"] = step("run",
            "install torch/torchvision wheels before editable install")

    # §3: opencv
    if opencv_ver and opencv_ver == pinned_opencv:
        steps["install_opencv"] = step("skip", f"opencv-python {opencv_ver} already correct")
    else:
        reason = f"opencv {opencv_ver or 'not installed'} → need {pinned_opencv}"
        steps["install_opencv"] = step("run", reason)
        warnings.append({"field": "opencv", "message": reason})

    # §3: ffmpeg
    ffmpeg_ver = lerobot.get("ffmpeg_version", "")
    if ffmpeg_ver:
        steps["install_ffmpeg"] = step("skip", f"ffmpeg {ffmpeg_ver} already in lerobot env")
    else:
        steps["install_ffmpeg"] = step("run", "ffmpeg not found in lerobot env")

    # §3: numpy
    numpy_ok = numpy_ver and ver_tuple(numpy_ver)[:2] == ver_tuple(pinned_numpy)[:2]
    if numpy_ok:
        steps["pin_numpy"] = step("skip", f"numpy {numpy_ver} already correct")
    else:
        reason = f"numpy {numpy_ver or 'not installed'} → need {pinned_numpy}"
        steps["pin_numpy"] = step("run", reason)
        if numpy_ver and ver_tuple(numpy_ver) >= (2, 0):
            warnings.append({"field": "numpy",
                              "message": f"numpy {numpy_ver} >= 2.0 breaks opencv {pinned_opencv}"})

    # §3: lerobot editable install
    if lerobot_inst:
        steps["install_lerobot"] = step("skip", "lerobot already installed in env")
    else:
        steps["install_lerobot"] = step("run", "lerobot not installed — run pip install -e")
        actions.append({"action": "install_lerobot",
                        "commands": [f'cd ~/lerobot && pip install -e ".[feetech]"'],
                        "risk": "medium"})

    # §4: reinstall torch AFTER editable install
    # Always run if lerobot was just installed OR torch CUDA is broken
    if lerobot_inst and torch_ok:
        steps["reinstall_torch_post"] = step("skip",
            f"lerobot already installed and torch {torch_ver} CUDA={torch_cuda} is correct")
    else:
        steps["reinstall_torch_post"] = step("run",
            "reinstall torch/torchvision wheels after editable install (mandatory)")
        if torch_cuda == "False":
            actions.append({
                "action": "reinstall_torch_gpu",
                "commands": [
                    f"pip install {wheel_dir}/torch-2.8.0a0+gitba56102-cp310-cp310-linux_aarch64.whl",
                    f"pip install {wheel_dir}/torchvision-0.23.0-cp310-cp310-linux_aarch64.whl",
                    "pip3 install numpy==1.26.0",
                ],
                "risk": "low",
                "verify": 'python3 -c "import torch; assert torch.cuda.is_available()"',
            })

    # §6: serial (only for so-arm / fashionstar)
    if robot_type in ("so-arm", "fashionstar"):
        serial_ok = serial_group == "ok" and not brltty and udev_rule
        if serial_ok:
            steps["serial"] = step("skip",
                "user in dialout, brltty absent, udev rule present")
        else:
            reasons = []
            if serial_group != "ok":   reasons.append("user not in dialout")
            if brltty:                 reasons.append("brltty installed")
            if not udev_rule:          reasons.append("udev rule missing")
            steps["serial"] = step("run", "; ".join(reasons))
            warnings.append({"field": "serial", "message": "; ".join(reasons)})
            actions.append({"action": "fix_serial", "risk": "low"})
    else:
        steps["serial"] = step("skip", f"robot-type={robot_type} — serial not required")

    # ── Overall status ────────────────────────────────────────────────────────
    run_count = sum(1 for s in steps.values() if s["status"] == "run")
    overall = "ready" if run_count == 0 else "needs-adjustments"

    return {
        "overall_status": overall,
        "facts_summary": _facts_summary(facts),
        "compatibility_status": overall,
        "steps": steps,
        "issues": issues,
        "warnings": warnings,
        "recommended_actions": actions,
    }


def _facts_summary(facts: dict) -> dict:
    return {
        "board":            facts.get("board"),
        "jetpack":          facts.get("jetpack"),
        "l4t":              facts.get("l4t"),
        "cuda":             facts.get("cuda"),
        "python":           facts.get("python"),
        "conda_installed":  facts.get("conda_installed"),
        "lerobot_installed":facts.get("lerobot_installed"),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--facts",      required=True)
    p.add_argument("--matrix",     required=True)
    p.add_argument("--profile",    required=True)
    p.add_argument("--robot-type", default="other")
    p.add_argument("--output",     required=True)
    args = p.parse_args()

    facts   = json.loads(Path(args.facts).read_text())
    matrix  = json.loads(Path(args.matrix).read_text())
    profile = matrix.get("profiles", {}).get(args.profile)

    if not profile:
        avail = list(matrix.get("profiles", {}).keys())
        print(f"[error] Profile '{args.profile}' not found. Available: {avail}", file=sys.stderr)
        sys.exit(1)

    result = analyze(facts, profile, args.robot_type)
    Path(args.output).write_text(json.dumps(result, indent=2))

    print(f"[analysis] overall_status = {result['overall_status']}")
    for name, s in result.get("steps", {}).items():
        tag = "skip" if s["status"] == "skip" else "RUN "
        print(f"  [{tag}] {name}: {s['reason']}")
    for w in result.get("warnings", []):
        print(f"[warn]  {w['field']}: {w['message']}")
    for i in result.get("issues", []):
        print(f"[issue] {i['field']}: found={i['found']} required={i['required']}")
    print(f"[analysis] Written to {args.output}")

    if result["overall_status"] == "blocked":
        sys.exit(2)


if __name__ == "__main__":
    main()
