from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_ROOT = REPO_ROOT.parent / "jetson-examples" / "reComputer" / "scripts"
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
    if any(token in slug for token in ("whisper", "parler", "audiocraft")):
        return "Audio"
    if any(token in slug for token in ("llama", "llava", "ollama", "text-generation")):
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
        "Jetson Example": "AI",
    }.get(category, "APP")


def prettify_name(name: str) -> str:
    aliases = {
        "comfyui": "ComfyUI",
        "llava": "LLaVA",
        "live-llava": "Live LLaVA",
        "llava-v1.5-7b": "LLaVA v1.5 7B",
        "llava-v1.6-vicuna-7b": "LLaVA v1.6 Vicuna 7B",
        "llama3": "Llama 3",
        "llama3.2": "Llama 3.2",
        "text-generation-webui": "Text Generation WebUI",
        "stable-diffusion-webui": "Stable Diffusion WebUI",
        "MoveNet-Lightning": "MoveNet Lightning",
        "MoveNet-Thunder": "MoveNet Thunder",
        "MoveNetJS": "MoveNet JS",
        "Sheared-LLaMA-2.7B-ShareGPT": "Sheared-LLaMA 2.7B ShareGPT",
    }
    if name in aliases:
        return aliases[name]
    title = name.replace("-", " ").replace("_", " ").strip()
    return " ".join(
        part.upper() if part.lower() in {"llm", "cv"} else part.title()
        for part in title.split()
    )


def build_desc(name: str, meta: dict) -> str:
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
    for script_dir in sorted(EXAMPLES_ROOT.iterdir()):
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
