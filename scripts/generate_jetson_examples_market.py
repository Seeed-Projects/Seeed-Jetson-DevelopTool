from __future__ import annotations

import json
import os
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_EXAMPLES_ROOT = REPO_ROOT.parent / "jetson-examples" / "reComputer" / "scripts"
EXAMPLES_ROOT = Path(
    os.environ.get("JETSON_EXAMPLES_ROOT", str(_DEFAULT_EXAMPLES_ROOT))
).expanduser().resolve()
OUTPUT = (
    REPO_ROOT
    / "seeed_jetson_develop"
    / "modules"
    / "apps"
    / "data"
    / "jetson_examples.json"
)


def parse_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    versions = re.findall(r"^\s*-\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$", text, re.MULTILINE)
    disk = re.search(r"REQUIRED_DISK_SPACE:\s*([0-9]+)", text)
    mem = re.search(r"REQUIRED_MEM_SPACE:\s*([0-9]+)", text)
    docker = re.search(r"DOCKER:\s*\n\s*ENABLE:\s*(true|false)", text, re.IGNORECASE)
    return {
        "jetpack_versions": versions,
        "required_disk_gb": int(disk.group(1)) if disk else None,
        "required_mem_gb": int(mem.group(1)) if mem else None,
        "docker_enabled": docker and docker.group(1).lower() == "true",
    }


def infer_category(name: str) -> str:
    slug = name.lower()
    if "ros1" in slug or "noetic" in slug:
        return "Robotics / ROS 1"
    if "ros2" in slug or "humble" in slug or "nvblox" in slug:
        return "Robotics / ROS 2"
    if any(token in slug for token in ("whisper", "parler", "audiocraft")):
        return "Audio"
    if any(token in slug for token in ("llama", "llava", "ollama", "text-generation", "gpt", "qwen", "deepseek")):
        return "LLM / GenAI"
    if "nanodb" in slug:
        return "RAG / Vector DB"
    if any(token in slug for token in ("depth", "yolo", "movenet", "nanoowl", "stable-diffusion", "comfyui", "cam")):
        return "CV / Vision"
    return "Jetson Example"


def infer_icon(category: str) -> str:
    return {
        "Audio": "AUD",
        "LLM / GenAI": "LLM",
        "RAG / Vector DB": "DB",
        "CV / Vision": "CV",
        "Robotics / ROS 1": "ROS",
        "Robotics / ROS 2": "BOT",
        "Jetson Example": "AI",
    }.get(category, "APP")


def prettify_name(name: str) -> str:
    aliases = {
        "comfyui": "ComfyUI",
        "gpt-oss": "GPT-OSS",
        "llava": "LLaVA",
        "live-llava": "Live LLaVA",
        "llava-v1.5-7b": "LLaVA v1.5 7B",
        "llava-v1.6-vicuna-7b": "LLaVA v1.6 Vicuna 7B",
        "llama3": "Llama 3",
        "llama3.2": "Llama 3.2",
        "nvblox": "NVBlox",
        "text-generation-webui": "Text Generation WebUI",
        "stable-diffusion-webui": "Stable Diffusion WebUI",
        "MoveNet-Lightning": "MoveNet Lightning",
        "MoveNet-Thunder": "MoveNet Thunder",
        "MoveNetJS": "MoveNet JS",
        "Sheared-LLaMA-2.7B-ShareGPT": "Sheared-LLaMA 2.7B ShareGPT",
        "ros1-jp6": "ROS 1 Noetic (JP6)",
    }
    if name in aliases:
        return aliases[name]
    title = name.replace("-", " ").replace("_", " ").strip()
    return " ".join(
        part.upper() if part.lower() in {"llm", "cv"} else part.title()
        for part in title.split()
    )


def build_desc(name: str, meta: dict) -> str:
    if name == "ros1-jp6":
        bits = [
            "Install ROS 1 Noetic Docker image from the built-in OneDrive archive",
            "Import image as `ros:noetic`",
            "Verify with `rosversion -d`",
        ]
        if meta["jetpack_versions"]:
            bits.append(f"JetPack/L4T {', '.join(meta['jetpack_versions'][:4])}")
        return ". ".join(bits) + "."
    bits = [f"Launch `{name}` from jetson-examples"]
    if meta["required_disk_gb"] is not None:
        bits.append(f"Disk {meta['required_disk_gb']}GB")
    if meta["required_mem_gb"] is not None:
        bits.append(f"RAM {meta['required_mem_gb']}GB")
    if meta["jetpack_versions"]:
        bits.append(f"JetPack/L4T {', '.join(meta['jetpack_versions'][:4])}")
    return ". ".join(bits) + "."


def build_app(script_dir: Path) -> dict:
    name = script_dir.name
    meta = parse_config(script_dir / "config.yaml")
    category = infer_category(name)
    path_prefix = "bash -c 'export PATH=$HOME/.local/bin:$PATH && "
    run_cmd = f"{path_prefix}reComputer run {name}'"
    clean_cmd = f"{path_prefix}reComputer clean {name}'"
    if name == "depth-anything-v3":
        return {
            "id": "jx-depth-anything-v3",
            "icon": "CV",
            "name": "Depth Anything V3",
            "category": "CV / Vision",
            "desc": "Follow official full tutorial flow: install jetson-examples, run reComputer demo, enter container, build engine, and run USB camera demo.",
            "source": "jetson-examples",
            "example_name": "depth_anything_v3",
            "check_cmd": "bash -lc 'sudo docker ps --format \"{{.Names}}\" | grep -q \"^depth_anything_v3$\"'",
            "install_cmds": [
                "bash -lc 'set -e; echo [1/2] pip install jetson-examples; python3 -m pip install -U jetson-examples'",
                "bash -lc 'set -e; echo [2/2] start demo container with reComputer; export PATH=$HOME/.local/bin:$PATH; reComputer run depth-anything-v3'",
            ],
            "run_cmds": [
                "bash -lc 'set -e; echo [1/5] display auth precheck; XAUTH_SRC=/run/user/1000/gdm/Xauthority; if [ -f \"$XAUTH_SRC\" ]; then xauth -f $HOME/.Xauthority merge \"$XAUTH_SRC\" 2>/dev/null && echo \"[ok] merged gdm Xauthority into ~/.Xauthority\"; DISPLAY=:0 XAUTHORITY=\"$XAUTH_SRC\" xhost +local: 2>/dev/null && echo \"[ok] xhost +local: done\" || echo \"[warn] xhost +local: failed (non-fatal)\"; else echo \"[warn] gdm Xauthority not found, RViz may fail\"; fi; echo \"[info] DISPLAY will be forced to :0\"'",
                "bash -lc 'echo; echo \"[2/5] optional swap (run manually only if engine build fails due to OOM)\"; echo \"sudo mkdir -p /mnt/nvme\"; echo \"sudo fallocate -l 16G /mnt/nvme/swapfile\"; echo \"sudo chmod 600 /mnt/nvme/swapfile\"; echo \"sudo mkswap /mnt/nvme/swapfile\"; echo \"sudo swapon /mnt/nvme/swapfile\"; echo'",
                "bash -lc 'set -e; echo \"[3/5] start tutorial container + run GUI preview in background xauth mode\"; DISP=:0; XAUTH_SRC=/run/user/1000/gdm/Xauthority; [ -f \"$XAUTH_SRC\" ] || XAUTH_SRC=$HOME/.Xauthority; echo \"[info] start container with DISPLAY=$DISP XAUTHORITY=$XAUTH_SRC\"; sudo docker rm -f depth_anything_v3 >/dev/null 2>&1 || true; sudo docker run -d --name depth_anything_v3 --restart unless-stopped --runtime=nvidia --network host --ipc host --privileged -e DISPLAY=$DISP -e XAUTHORITY=/tmp/.docker.xauth -e QT_X11_NO_MITSHM=1 -v /tmp/.X11-unix:/tmp/.X11-unix -v \"$XAUTH_SRC\":/tmp/.docker.xauth:ro -v /dev:/dev chenduola6/depth_anything_v3:jp6.2 bash -lc \"set -e; export DISPLAY=:0; export XAUTHORITY=/tmp/.docker.xauth; cd /workspace/ros2-depth-anything-v3-trt; source install/setup.bash; if ls onnx/*.engine >/dev/null 2>&1; then echo \\\"[skip] engine already exists\\\"; else echo \\\"[info] first run will build TensorRT engine; this can take several minutes\\\"; ros2 run depth_anything_v3 generate_engines onnx; fi; exec ./run_camera_depth.sh\"; sudo docker ps -a --filter name=depth_anything_v3'",
                "bash -lc 'echo \"[4/5] show depth_anything_v3 status (if started by reComputer path)\"; sudo docker ps -a --filter name=depth_anything_v3'",
                "bash -lc 'echo \"[5/5] follow logs for 120s\"; timeout 120s sudo docker logs -f depth_anything_v3 2>&1 || true; echo \"[hint] if still building engine, rerun Run and keep logs open\"'",
            ],
            "clean_cmds": [
                "bash -lc 'set -e; export PATH=$HOME/.local/bin:$PATH; if reComputer clean depth-anything-v3; then echo \"[ok] reComputer clean depth-anything-v3\"; else echo \"[warn] reComputer clean failed, fallback to docker rm only\"; sudo docker rm -f depth_anything_v3 >/dev/null 2>&1 || true; fi; echo depth_anything_v3 cleaned'",
            ],
            "uninstall_cmds": [
                "bash -lc 'sudo docker stop depth_anything_v3 2>/dev/null; sudo docker rm -f depth_anything_v3 2>/dev/null; echo \"[ok] container removed\"'",
                "bash -lc 'sudo docker rmi chenduola6/depth_anything_v3:jp6.2 2>/dev/null && echo \"[ok] image removed\" || echo \"[warn] image not found or already removed\"'",
                "bash -lc 'export PATH=$HOME/.local/bin:$PATH; reComputer clean depth-anything-v3 2>/dev/null && echo \"[ok] reComputer clean done\" || echo \"[warn] reComputer clean skipped\"'",
            ],
            "requirements": {
                "jetpack_versions": ["36.4.x"],
                "required_disk_gb": 20,
                "required_mem_gb": 8,
                "docker_enabled": True,
            },
        }
    if name == "ros1-jp6":
        return {
            "id": f"jx-{name}",
            "icon": infer_icon(category),
            "name": prettify_name(name),
            "category": category,
            "desc": build_desc(name, meta),
            "source": "jetson-examples",
            "example_name": name,
            "check_cmd": "bash -lc 'docker image inspect ros:noetic >/dev/null 2>&1'",
            "install_cmds": [
                f"{path_prefix}ROS1_JP6_SKIP_RUN=1 reComputer run {name}'",
            ],
            "run_cmds": [
                f"{path_prefix}ROS1_JP6_COMMAND=\"source /opt/ros/noetic/setup.bash && rosversion -d\" reComputer run {name}'",
            ],
            "clean_cmds": [clean_cmd] if (script_dir / "clean.sh").exists() else [],
            "uninstall_cmds": [
                "bash -lc 'docker image rm ros:noetic || true'",
                "bash -lc 'rm -f ~/.cache/jetson-examples/ros1-jp6/ros-noetic-jp6.tar || true'",
            ],
            "requirements": meta,
        }
    return {
        "id": f"jx-{name}",
        "icon": infer_icon(category),
        "name": prettify_name(name),
        "category": category,
        "desc": build_desc(name, meta),
        "source": "jetson-examples",
        "example_name": name,
        "check_cmd": f"{path_prefix}which reComputer' 2>/dev/null",
        "install_cmds": [
            run_cmd,
        ],
        "run_cmds": [run_cmd],
        "clean_cmds": [clean_cmd] if (script_dir / "clean.sh").exists() else [],
        "uninstall_cmds": [],
        "requirements": meta,
    }


def main() -> None:
    apps = []
    if not EXAMPLES_ROOT.exists():
        raise SystemExit(f"jetson-examples scripts directory not found: {EXAMPLES_ROOT}")
    for script_dir in sorted(EXAMPLES_ROOT.iterdir(), key=lambda p: p.name.lower()):
        if not script_dir.is_dir():
            continue
        config = script_dir / "config.yaml"
        run_script = script_dir / "run.sh"
        if not config.exists() or not run_script.exists():
            continue
        apps.append(build_app(script_dir))
    OUTPUT.write_text(json.dumps(apps, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(apps)} apps to {OUTPUT}")


if __name__ == "__main__":
    main()
