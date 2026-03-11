"""应用注册表 — 从 apps.json 加载，管理安装状态"""
import json
from pathlib import Path
from typing import Optional

_DATA = Path(__file__).parent / "data" / "apps.json"


def load_apps() -> list[dict]:
    """加载应用列表，若 JSON 不存在返回内置默认值"""
    if _DATA.exists():
        return json.loads(_DATA.read_text(encoding="utf-8"))
    return _DEFAULT_APPS


def get_app(app_id: str) -> Optional[dict]:
    return next((a for a in load_apps() if a["id"] == app_id), None)


# 内置默认应用列表（apps.json 未就绪时使用）
_DEFAULT_APPS = [
    {"id": "yolov8",    "icon": "🎯", "name": "YOLOv8 目标检测",  "category": "CV / 视觉",   "desc": "实时目标检测，支持摄像头输入",          "skill_id": None,       "status": "installed"},
    {"id": "qwen2",     "icon": "🤖", "name": "Qwen2 本地推理",   "category": "大语言模型",  "desc": "阿里 Qwen2 模型，支持中文对话",         "skill_id": "qwen_demo","status": "available"},
    {"id": "lerobot",   "icon": "🦾", "name": "LeRobot 机器人",   "category": "机器人",      "desc": "Hugging Face LeRobot 开发套件",         "skill_id": "lerobot",  "status": "available"},
    {"id": "kokoro",    "icon": "🗣", "name": "Kokoro TTS",       "category": "TTS 语音",    "desc": "高质量文字转语音，支持多语言",           "skill_id": None,       "status": "available"},
    {"id": "sd",        "icon": "🌊", "name": "Stable Diffusion", "category": "CV / 视觉",   "desc": "本地图像生成，SDXL-Turbo 优化版",       "skill_id": None,       "status": "available"},
    {"id": "jupyter",   "icon": "📊", "name": "Jupyter Lab",      "category": "开发工具",    "desc": "交互式 Python 开发环境",                "skill_id": None,       "status": "installed"},
    {"id": "nodered",   "icon": "🔴", "name": "Node-RED",         "category": "开发工具",    "desc": "可视化流程编排，IoT 场景适用",           "skill_id": None,       "status": "available"},
    {"id": "ollama",    "icon": "🦙", "name": "Ollama",           "category": "大语言模型",  "desc": "本地 LLM 运行框架，支持多种模型",        "skill_id": None,       "status": "available"},
]
