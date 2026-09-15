"""Classification catalog for the official NVIDIA skills repo (nvidia/skills).

The `npx skills add nvidia/skills --list` CLI only returns (name, description)
pairs, so this module provides a lightweight, prefix-rule based classification:

- Run target: where the skill is meant to run — on the Jetson device, on the
  PC dev machine, or on either (edge-deployable video stack).
- Scenario: the use-case category, mirroring the product families in the
  official repo (https://github.com/nvidia/skills).

Rules are evaluated in order; the first prefix match wins. Unknown names fall
back to the "other" category and the "pc" target.
"""
from __future__ import annotations

# ── Run targets ─────────────────────────────────────────────────────────────
TARGET_JETSON = "jetson"   # runs on the Jetson device
TARGET_PC = "pc"           # runs on the PC dev machine / server
TARGET_BOTH = "both"       # runs on PC or Jetson (edge-deployable)

# ── Scenario categories (order == display order) ───────────────────────────
CATEGORY_JETSON_SYSTEM = "jetson_system"
CATEGORY_VIDEO_AI = "video_ai"
CATEGORY_EDGE_LLM = "edge_llm"
CATEGORY_GENAI = "genai"
CATEGORY_VISION_TRAIN = "vision_train"
CATEGORY_MEDICAL = "medical"
CATEGORY_HPC = "hpc"
CATEGORY_DOCA = "doca_net"
CATEGORY_ROBOTICS = "robotics"
CATEGORY_OTHER = "other"

# key -> (zh label, icon)
CATEGORIES: dict[str, tuple[str, str]] = {
    CATEGORY_JETSON_SYSTEM: ("Jetson 设备与系统", "🛠"),
    CATEGORY_VIDEO_AI:      ("视频 AI 与视觉分析", "📹"),
    CATEGORY_EDGE_LLM:      ("边缘大模型推理", "🧠"),
    CATEGORY_GENAI:         ("大模型与生成式 AI", "🤖"),
    CATEGORY_VISION_TRAIN:  ("视觉模型训练 (TAO)", "🎯"),
    CATEGORY_MEDICAL:       ("医疗影像", "🏥"),
    CATEGORY_HPC:           ("科学计算与加速计算", "📐"),
    CATEGORY_DOCA:          ("网络与 DPU (DOCA)", "🌐"),
    CATEGORY_ROBOTICS:      ("机器人与物理 AI", "🦾"),
    CATEGORY_OTHER:         ("其他", "📦"),
}

# (prefix, category) — evaluated in order, first match wins
_CATEGORY_RULES: tuple[tuple[str, str], ...] = (
    ("jetson-video", CATEGORY_VIDEO_AI),
    ("jetson-llm", CATEGORY_EDGE_LLM),
    ("jetson-speculative-decoding", CATEGORY_EDGE_LLM),
    ("jetson", CATEGORY_JETSON_SYSTEM),
    ("deepstream", CATEGORY_VIDEO_AI),
    ("vss-", CATEGORY_VIDEO_AI),
    ("rtvi-", CATEGORY_VIDEO_AI),
    ("amc-", CATEGORY_VIDEO_AI),
    ("hsb-", CATEGORY_VIDEO_AI),
    ("holoscan", CATEGORY_VIDEO_AI),
    ("holohub", CATEGORY_VIDEO_AI),
    ("tao-", CATEGORY_VISION_TRAIN),
    ("dicom-", CATEGORY_MEDICAL),
    ("digital-health-", CATEGORY_MEDICAL),
    ("nv-generate-", CATEGORY_MEDICAL),
    ("nv-segment-", CATEGORY_MEDICAL),
    ("nv-reason-", CATEGORY_MEDICAL),
    ("medtech-", CATEGORY_MEDICAL),
    ("nemo", CATEGORY_GENAI),          # nemo-*, nemoclaw-*
    ("nemotron-", CATEGORY_GENAI),
    ("mcore-", CATEGORY_GENAI),
    ("dynamo-", CATEGORY_GENAI),
    ("aiq-", CATEGORY_GENAI),
    ("rag-", CATEGORY_GENAI),
    ("launch-nemo-rl", CATEGORY_GENAI),
    ("data-designer", CATEGORY_GENAI),
    ("nvidia-skill-finder", CATEGORY_GENAI),
    ("cuopt", CATEGORY_HPC),
    ("cupynumeric", CATEGORY_HPC),
    ("cudaq", CATEGORY_HPC),
    ("physicsnemo", CATEGORY_HPC),
    ("earth2studio", CATEGORY_HPC),
    ("warp-", CATEGORY_HPC),
    ("tilegym-", CATEGORY_HPC),
    ("accelerated-computing", CATEGORY_HPC),
    ("dali-", CATEGORY_HPC),
    ("portfolio-optimization", CATEGORY_HPC),
    ("doca", CATEGORY_DOCA),
    ("omniverse", CATEGORY_ROBOTICS),
    ("i4h-", CATEGORY_ROBOTICS),
    ("physical-ai-", CATEGORY_ROBOTICS),
    ("paidf-", CATEGORY_ROBOTICS),
)

# Prefixes of skills that also run on Jetson (edge video / sensor stack)
_BOTH_PREFIXES: tuple[str, ...] = (
    "deepstream", "vss-", "rtvi-", "amc-", "hsb-", "holoscan", "holohub",
)


def nvidia_category(name: str) -> str:
    """Return the scenario category key for a NVIDIA skill name."""
    name = (name or "").strip().lower()
    for prefix, category in _CATEGORY_RULES:
        if name.startswith(prefix):
            return category
    return CATEGORY_OTHER


def nvidia_target(name: str) -> str:
    """Return the run target for a NVIDIA skill name."""
    name = (name or "").strip().lower()
    if name.startswith("jetson"):
        return TARGET_JETSON
    if name.startswith(_BOTH_PREFIXES):
        return TARGET_BOTH
    return TARGET_PC


def category_label(category: str) -> str:
    """Return the zh label of a category key."""
    return CATEGORIES.get(category, CATEGORIES[CATEGORY_OTHER])[0]


def target_label(target: str) -> str:
    """Return the zh label of a run target."""
    return {
        TARGET_JETSON: "Jetson 设备",
        TARGET_PC: "PC 开发机",
        TARGET_BOTH: "PC / Jetson",
    }.get(target, "PC 开发机")


def target_matches(target: str, wanted: str) -> bool:
    """Check if a skill target passes the target filter.

    wanted: "all" | TARGET_JETSON | TARGET_PC
    A "both" skill shows up under either Jetson or PC filters.
    """
    if wanted in ("all", "", None):
        return True
    if target == TARGET_BOTH:
        return True
    return target == wanted
