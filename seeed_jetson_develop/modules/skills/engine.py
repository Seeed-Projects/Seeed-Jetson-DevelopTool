"""Skills execution engine."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from seeed_jetson_develop.core.runner import Runner

_DATA        = Path(__file__).parent / "data" / "skills.json"
_SKILLS_ROOT = Path(__file__).parent.parent.parent.parent / "skills"
_OPENCLAW    = _SKILLS_ROOT / "openclaw"
_CLAUDE      = _SKILLS_ROOT / "claude"
_CODEX       = _SKILLS_ROOT / "codex"

# Canonical category keys.
CATEGORY_DRIVER_REPAIR = "driver_repair"
CATEGORY_APP_ENV_DEPLOY = "app_env_deploy"
CATEGORY_NETWORK_REMOTE = "network_remote"
CATEGORY_SYSTEM_TUNING = "system_tuning"
CATEGORY_AI_LLM = "ai_llm"
CATEGORY_VISION_YOLO = "vision_yolo"
CATEGORY_REFERENCE = "reference"

CATEGORY_LABEL_KEYS = {
    CATEGORY_DRIVER_REPAIR: "skills.category.driver_repair",
    CATEGORY_APP_ENV_DEPLOY: "skills.category.app_env_deploy",
    CATEGORY_NETWORK_REMOTE: "skills.category.network_remote",
    CATEGORY_SYSTEM_TUNING: "skills.category.system_tuning",
    CATEGORY_AI_LLM: "skills.category.ai_llm",
    CATEGORY_VISION_YOLO: "skills.category.vision_yolo",
    CATEGORY_REFERENCE: "skills.category.reference",
}

CATEGORY_ALIASES = {
    CATEGORY_DRIVER_REPAIR: CATEGORY_DRIVER_REPAIR,
    "\u9a71\u52a8 \u7cfb\u7edf\u4fee\u590d": CATEGORY_DRIVER_REPAIR,
    "\u9a71\u52a8 & \u7cfb\u7edf\u4fee\u590d": CATEGORY_DRIVER_REPAIR,
    CATEGORY_APP_ENV_DEPLOY: CATEGORY_APP_ENV_DEPLOY,
    "\u5e94\u7528 \u73af\u5883\u90e8\u7f72": CATEGORY_APP_ENV_DEPLOY,
    "\u5e94\u7528 & \u73af\u5883\u90e8\u7f72": CATEGORY_APP_ENV_DEPLOY,
    CATEGORY_NETWORK_REMOTE: CATEGORY_NETWORK_REMOTE,
    "\u7f51\u7edc \u8fdc\u7a0b": CATEGORY_NETWORK_REMOTE,
    "\u7f51\u7edc & \u8fdc\u7a0b": CATEGORY_NETWORK_REMOTE,
    CATEGORY_SYSTEM_TUNING: CATEGORY_SYSTEM_TUNING,
    "\u7cfb\u7edf\u4f18\u5316": CATEGORY_SYSTEM_TUNING,
    CATEGORY_AI_LLM: CATEGORY_AI_LLM,
    "AI / \u5927\u6a21\u578b": CATEGORY_AI_LLM,
    CATEGORY_VISION_YOLO: CATEGORY_VISION_YOLO,
    "\u89c6\u89c9 / YOLO": CATEGORY_VISION_YOLO,
    CATEGORY_REFERENCE: CATEGORY_REFERENCE,
    "\u53c2\u8003\u6587\u6863": CATEGORY_REFERENCE,
}

# Category icon mapping uses canonical keys.
CATEGORY_ICONS = {
    CATEGORY_DRIVER_REPAIR: "🔧",
    CATEGORY_APP_ENV_DEPLOY: "📦",
    CATEGORY_NETWORK_REMOTE: "🌐",
    CATEGORY_SYSTEM_TUNING: "⚙️",
    CATEGORY_AI_LLM: "🤖",
    CATEGORY_VISION_YOLO: "📹",
    CATEGORY_REFERENCE: "📖",
}


def normalize_category(category: str) -> str:
    value = (category or "").strip()
    if not value:
        return CATEGORY_REFERENCE
    return CATEGORY_ALIASES.get(value, value)


@dataclass
class Skill:
    id:            str
    name:          str
    desc:          str
    category:      str
    commands:      list[str]
    duration_hint: str  = "~5 min"
    verified:      bool = False
    risk:          str  = ""
    params:        dict = field(default_factory=dict)
    source:        str  = "builtin"   # "builtin" | "openclaw" | "claude" | "codex"
    md_path:       str  = ""          # SKILL.md / CLAUDE.md / AGENTS.md path
    wiki_url:      str  = ""          # Seeed Wiki page URL


# slug -> Seeed Wiki URL mapping.
_WIKI_URL_MAP: dict[str, str] = {
    # AI / LLM
    "deepseek-quick-deploy":        "https://wiki.seeedstudio.com/deploy_deepseek_on_jetson/",
    "deploy-deepseek-mlc":          "https://wiki.seeedstudio.com/deploy_deepseek_on_jetson/",
    "quantized-llama2-7b-mlc":      "https://wiki.seeedstudio.com/Quantized_Llama2_7B_with_MLC_LLM_on_Jetson/",
    "local-rag-llamaindex":         "https://wiki.seeedstudio.com/Local_RAG_based_on_Jetson_with_LlamaIndex/",
    "local-llm-text-to-image":      "https://wiki.seeedstudio.com/How_to_run_local_llm_text_to_image_on_reComputer/",
    "local-chatbot-multimodal":     "https://wiki.seeedstudio.com/local_ai_ssistant/",
    "local-chatbot-physical":       "https://wiki.seeedstudio.com/local_chatbot_recomputer/",
    "finetune-llm-llama-factory":   "https://wiki.seeedstudio.com/Finetune_LLM_on_Jetson/",
    "llama-cpp-rpc-distributed":    "https://wiki.seeedstudio.com/ai_robotics_distributed_llama_cpp_rpc_jetson/",
    "deploy-riva-llama2":           "https://wiki.seeedstudio.com/Quantized_Llama2_7B_with_MLC_LLM_on_Jetson/",
    "generative-ai-intro":          "https://wiki.seeedstudio.com/Generative_AI_Intro/",
    "gpt-oss-live":                 "https://wiki.seeedstudio.com/deploy_gptoss_on_jetson/",
    "llm-interface-control":        "https://wiki.seeedstudio.com/llm_interface_control_jetson/",
    "deploy-ollama-anythingllm":    "https://wiki.seeedstudio.com/local_ai_ssistant/",
    "deploy-dia":                   "https://wiki.seeedstudio.com/local_chatbot_recomputer/",
    # Vision / YOLO
    "yolov8-trt":                   "https://wiki.seeedstudio.com/YOLOv8-TRT-Jetson/",
    "yolov8-deepstream-trt":        "https://wiki.seeedstudio.com/YOLOv8-DeepStream-TRT-Jetson/",
    "yolov8-custom-classification": "https://wiki.seeedstudio.com/train_and_deploy_a_custom_classification_model_with_yolov8/",
    "train-deploy-yolov8":          "https://wiki.seeedstudio.com/YOLOv8-TRT-Jetson/",
    "yolov5-object-detection":      "https://wiki.seeedstudio.com/YOLOv8-TRT-Jetson/",
    "yolov11-depth-distance":       "https://wiki.seeedstudio.com/yolov11_with_depth_camera/",
    "yolov26_jetson":               "https://wiki.seeedstudio.com/ai_roboticsyolov26_dual_camera_system/",
    "zero-shot-detection":          "https://wiki.seeedstudio.com/run_zero_shot_detection_on_recomputer/",
    "run-vlm":                      "https://wiki.seeedstudio.com/run_vlm_on_recomputer/",
    "vlm-warehouse-guard":          "https://wiki.seeedstudio.com/vlm/",
    "deploy-live-vlm-webui":        "https://wiki.seeedstudio.com/deploy_live_vlm_webui_on_jetson/",
    "speech-vlm":                   "https://wiki.seeedstudio.com/speech_vlm/",
    "deploy-depth-anything-v3":     "https://wiki.seeedstudio.com/deploy_depth_anything_v3_jetson_agx_orin/",
    "traffic-deepstream":           "https://wiki.seeedstudio.com/Traffic-Management-DeepStream-SDK/",
    "dashcamnet-xavier-nx-multicamera": "https://wiki.seeedstudio.com/DashCamNet-with-Jetson-Xavier-NX-Multicamera/",
    "maskcam-nano":                 "https://wiki.seeedstudio.com/Jetson-Nano-MaskCam/",
    "hardhat-setup":                "https://wiki.seeedstudio.com/Jetson-AI-developer-tools/",
    "roboflow-setup":               "https://wiki.seeedstudio.com/Roboflow-Jetson-Getting-Started/",
    "no-code-edge-ai":              "https://wiki.seeedstudio.com/Jetson-AI-developer-tools/",
    "deploy-efficient-vision-engine": "https://wiki.seeedstudio.com/Jetson-AI-developer-tools/",
    "ai-nvr":                       "https://wiki.seeedstudio.com/ai_nvr_with_jetson/",
    "deploy-nvblox":                "https://wiki.seeedstudio.com/Jetson-AI-developer-tools/",
    "multi-gmsl-3d-reconstruction": "https://wiki.seeedstudio.com/ai_roboticsyolov26_dual_camera_system/",
    # Apps & Environment Deployment
    "torch-install":                "https://wiki.seeedstudio.com/install_torch_on_recomputer/",
    "jetson-docker-setup":          "https://wiki.seeedstudio.com/jetson-docker-getting-started/",
    "lerobot-env-setup":            "https://wiki.seeedstudio.com/lerobot_so100m_new/",
    "deploy-frigate":               "https://wiki.seeedstudio.com/deploy_frigate_on_jetson/",
    "openclaw-local-deploy":        "https://wiki.seeedstudio.com/local_openclaw_on_recomputer_jetson/",
    "clawdbot-development":         "https://wiki.seeedstudio.com/local_openclaw_on_recomputer_jetson/",
    "jetson-ai-tools":              "https://wiki.seeedstudio.com/Jetson-AI-developer-tools/",
    "pinocchio-install":            "https://wiki.seeedstudio.com/Jetson-AI-developer-tools/",
    # Network & Remote Access
    "vnc-setup":                    "https://wiki.seeedstudio.com/vnc_for_recomputer/",
    "allxon-setup":                 "https://wiki.seeedstudio.com/Allxon-Jetson-Getting-Started/",
    "allxon-ota-update":            "https://wiki.seeedstudio.com/Update-Jetson-Linux-OTA-Using-Allxon/",
    "neqto-engine-setup":           "https://wiki.seeedstudio.com/neqto_engine_for_linux_recomputer/",
    "lumeo-setup":                  "https://wiki.seeedstudio.com/Lumeo-Jetson-Getting-Started/",
    "nvstreamer-setup":             "https://wiki.seeedstudio.com/getting_started_with_nvstreamer/",
    "gapi-setup":                   "https://wiki.seeedstudio.com/gapi_getting_started-with_jetson/",
    # System Tuning
    "disk-encryption":              "https://wiki.seeedstudio.com/how_to_encrypt_the_disk_for_jetson/",
    "bsp-source-build":             "https://wiki.seeedstudio.com/how_to_build_the_source_code_project_for_seeed_jetson_bsp/",
    "ko-module-build":              "https://wiki.seeedstudio.com/how_to_build_the_ko_module_for_seeed_jetson/",
    "ethercat-communication":       "https://wiki.seeedstudio.com/how_to_establish_the_ethercat_on_jetson/",
    "ethercat-setup":               "https://wiki.seeedstudio.com/how_to_establish_the_ethercat_on_jetson/",
    "jetpack-ota-update":           "https://wiki.seeedstudio.com/updating_jetpack_with_ota/",
    "software-package-upgrade":     "https://wiki.seeedstudio.com/updating_jetpack_with_ota/",
    # Driver & System Repair
    "usb-wifi-88x2bu-setup":        "https://wiki.seeedstudio.com/Jetson-AI-developer-tools/",
    "imx477-a603-setup":            "https://wiki.seeedstudio.com/Use_IMX477_Camera_with_A603_Jetson_Carrier_Board/",
    # References
    "jetpack-jetson-overview":      "https://wiki.seeedstudio.com/NVIDIA_Jetson/",
    "jetson-tutorial-exercises":    "https://wiki.seeedstudio.com/reComputer_Jetson_Series_Tutorials_Exercise/",
    "jetson-project-gallery":       "https://wiki.seeedstudio.com/NVIDIA_Jetson/",
    "jetson-resource-index":        "https://wiki.seeedstudio.com/NVIDIA_Jetson/",
    "jetson-faq":                   "https://wiki.seeedstudio.com/NVIDIA_Jetson/",
    # Speech / Subtitle
    "whisper-realtime-stt":         "https://wiki.seeedstudio.com/Whisper_on_Jetson_for_Real_Time_Speech_to_Text/",
    "realtime-subtitle-recorder":   "https://wiki.seeedstudio.com/Real_Time_Subtitle_Recoder_on_Nvidia_Jetson/",
    "voice-llm-motor-control":      "https://wiki.seeedstudio.com/control_motor_by_voice_llm_on_jetson/",
    "voice-llm-reachy-mini-multimodal": "https://wiki.seeedstudio.com/local_voice_llm_on_recomputer_jetson_for_reachy_mini_bk/",
    "voice-llm-reachy-mini-physical":   "https://wiki.seeedstudio.com/local_voice_llm_on_recomputer_jetson_for_reachy_mini_bk/",
    # GR00T
    "gr00t-n1-5-deploy-thor":       "https://wiki.seeedstudio.com/control_robotic_arm_via_gr00t/",
    "gr00t-n1-6-deploy-agx":        "https://wiki.seeedstudio.com/fine_tune_gr00t_n1.6_for_lerobot_so_arm_and_deploy_on_agx_orin/",
    # Third-party Platforms
    "alwaysai-setup":               "https://wiki.seeedstudio.com/alwaysAI-Jetson-Getting-Started/",
    "cvedia-setup":                 "https://wiki.seeedstudio.com/CVEDIA-Jetson-Getting-Started/",
    "deciai-setup":                 "https://wiki.seeedstudio.com/DeciAI-Getting-Started/",
    "scailable-setup":              "https://wiki.seeedstudio.com/Scailable-Jetson-Getting-Started/",
    # Built-in skills (ID uses underscore).
    "usb_wifi":                     "https://wiki.seeedstudio.com/Jetson-AI-developer-tools/",
    "install_torch":                "https://wiki.seeedstudio.com/install_torch_on_recomputer/",
    "install_docker":               "https://wiki.seeedstudio.com/jetson-docker-getting-started/",
    "install_ollama":               "https://wiki.seeedstudio.com/local_ai_ssistant/",
    "deepseek_deploy":              "https://wiki.seeedstudio.com/deploy_deepseek_on_jetson/",
    "install_frigate":              "https://wiki.seeedstudio.com/deploy_frigate_on_jetson/",
    "install_yolov8":               "https://wiki.seeedstudio.com/YOLOv8-TRT-Jetson/",
    "vnc_setup":                    "https://wiki.seeedstudio.com/vnc_for_recomputer/",
    "lerobot":                      "https://wiki.seeedstudio.com/lerobot_so100m_new/",
}


# SKILL.md / CLAUDE.md / AGENTS.md parser
def _parse_skill_md(md_file: Path, slug: str, source: str = "openclaw", fast: bool = False) -> Optional[Skill]:
    """Parse skill file. When fast=True, read only frontmatter."""
    try:
        if fast:
            with open(md_file, encoding="utf-8", errors="replace") as f:
                lines = []
                for _ in range(40):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line)
            text = "".join(lines)
        else:
            text = md_file.read_text(encoding="utf-8", errors="replace")

        name, desc = slug, ""
        # frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].splitlines():
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip()[:120]

        # Extract bash code blocks as commands (skipped in fast mode).
        cmds: list[str] = []
        if not fast:
            in_bash = False
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("```bash"):
                    in_bash = True
                    continue
                if stripped == "```" and in_bash:
                    in_bash = False
                    continue
                if in_bash and stripped and not stripped.startswith("#"):
                    cmds.append(line.rstrip())

        # category from slug keywords
        sl = slug.lower()
        if any(k in sl for k in ("wifi","driver","fix","repair","usb-timeout","uuid","recomp")):
            cat = CATEGORY_DRIVER_REPAIR
        elif any(k in sl for k in ("yolo","yolov","vision","deepstream","nvblox","depth","detect","track","vlm","nvstreamer","maskcam","dashcam","traffic","zero-shot","efficient-vision","no-code","roboflow")):
            cat = CATEGORY_VISION_YOLO
        elif any(k in sl for k in ("llm","llama","deepseek","qwen","gpt","oss","rag","chatbot","whisper","speech","voice","subtitle","langchain","finetune","mlc","riva","dia","gr00t")):
            cat = CATEGORY_AI_LLM
        elif any(k in sl for k in ("docker","torch","install","setup","deploy","env","lerobot","ollama","frigate","pinocchio","jetson-ai","jetson-docker")):
            cat = CATEGORY_APP_ENV_DEPLOY
        elif any(k in sl for k in ("vnc","ssh","remote","vscode","proxy","neqto","allxon","ota","update","network")):
            cat = CATEGORY_NETWORK_REMOTE
        elif any(k in sl for k in ("power","swap","fan","cache","log","backup","encrypt","disk","bsp","ko-module","diy-bsp","spi","ethercat")):
            cat = CATEGORY_SYSTEM_TUNING
        else:
            cat = CATEGORY_REFERENCE
        return Skill(
            id=slug, name=name, desc=desc or f"{slug} skill",
            category=cat, commands=cmds[:15],
            duration_hint="—", verified=False,
            source=source, md_path=str(md_file),
            wiki_url=_WIKI_URL_MAP.get(slug, ""),
        )
    except Exception:
        return None


def _scan_skill_dir(root: Path, filename: str, source: str, cap: int = 60, fast: bool = False) -> list[Skill]:
    """Scan directory and load skills by metadata file."""
    if not root.exists():
        return []
    skills = []
    for d in sorted(root.iterdir()):
        if len(skills) >= cap:
            break
        if not d.is_dir():
            continue
        md = d / filename
        if md.exists():
            s = _parse_skill_md(md, d.name, source, fast=fast)
            if s:
                skills.append(s)
    return skills


def load_openclaw_skills() -> list[Skill]:
    """Load skills/openclaw/ SKILL.md entries."""
    return _scan_skill_dir(_OPENCLAW, "SKILL.md", "openclaw", cap=60)


def load_external_skills() -> list[Skill]:
    """Load external skills (openclaw + claude + codex) and deduplicate by id."""
    skills: list[Skill] = []
    seen: set[str] = set()
    for s in (
        _scan_skill_dir(_OPENCLAW, "SKILL.md",  "openclaw", cap=60)
        + _scan_skill_dir(_CLAUDE,  "CLAUDE.md", "claude",  cap=60)
        + _scan_skill_dir(_CODEX,   "AGENTS.md", "codex",   cap=60)
    ):
        if s.id not in seen:
            seen.add(s.id)
            skills.append(s)
    return skills


_variants_cache: list | None = None

def load_all_variants(fast: bool = False) -> list[Skill]:
    """Return all external skills without deduplication."""
    global _variants_cache
    if _variants_cache is not None:
        return _variants_cache
    result = []
    result.extend(_scan_skill_dir(_OPENCLAW, "SKILL.md",  "openclaw", cap=100, fast=fast))
    result.extend(_scan_skill_dir(_CLAUDE,   "CLAUDE.md", "claude",   cap=100, fast=fast))
    result.extend(_scan_skill_dir(_CODEX,    "AGENTS.md", "codex",    cap=100, fast=fast))
    if not fast:
        _variants_cache = result
    return result


def load_builtin_skills() -> list[Skill]:
    """Load built-in skills from JSON."""
    if _DATA.exists():
        raw = json.loads(_DATA.read_text(encoding="utf-8"))
        skills = [Skill(**{k: v for k, v in s.items() if k in Skill.__dataclass_fields__}) for s in raw]
    else:
        skills = list(_DEFAULT_SKILLS)
    # Backfill wiki_url if missing in JSON.
    for s in skills:
        s.category = normalize_category(s.category)
        if not s.wiki_url:
            s.wiki_url = _WIKI_URL_MAP.get(s.id, "")
    return skills


def load_skills() -> list[Skill]:
    """Load all skills: builtin + openclaw + claude + codex."""
    builtin = load_builtin_skills()
    existing_ids = {s.id for s in builtin}
    for s in load_external_skills():
        if s.id not in existing_ids:
            builtin.append(s)
    return builtin


def run_skill(
    skill: Skill,
    runner: Runner,
    on_log: Callable[[str], None],
    params: Optional[dict] = None,
    max_retries: int = 1,
) -> tuple[bool, str]:
    """Execute all commands in a skill with optional retries."""
    merged = {**skill.params, **(params or {})}
    for cmd_tpl in skill.commands:
        try:
            cmd = cmd_tpl.format(**merged)
        except KeyError:
            cmd = cmd_tpl

        last_rc = 0
        for attempt in range(max_retries + 1):
            if attempt > 0:
                on_log(f"  Retry ({attempt}/{max_retries})...")
            on_log(f"$ {cmd}")
            last_rc, _ = runner.run(cmd, timeout=300, on_output=on_log)
            if last_rc == 0:
                break

        if last_rc != 0:
            return False, f"Command failed (rc={last_rc}): {cmd[:80]}"

    return True, f"{skill.name} completed"


# Use JSON as the canonical source for built-in skills.
_DEFAULT_SKILLS: list[Skill] = []
