"""Skills 执行引擎 — 加载定义、参数化执行、日志回传"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from seeed_jetson_flash.core.runner import Runner

_DATA = Path(__file__).parent / "data" / "skills.json"


@dataclass
class Skill:
    id: str
    name: str
    desc: str
    category: str
    commands: list[str]
    duration_hint: str = "~5 min"
    verified: bool = False
    risk: str = ""
    params: dict = field(default_factory=dict)  # 参数化配置


def load_skills() -> list[Skill]:
    if _DATA.exists():
        raw = json.loads(_DATA.read_text(encoding="utf-8"))
        return [Skill(**s) for s in raw]
    return _DEFAULT_SKILLS


def run_skill(
    skill: Skill,
    runner: Runner,
    on_log: Callable[[str], None],
    params: Optional[dict] = None,
) -> tuple[bool, str]:
    """
    执行一个 Skill 的所有命令。
    返回 (success, final_message)。
    """
    merged_params = {**skill.params, **(params or {})}
    for cmd_tpl in skill.commands:
        cmd = cmd_tpl.format(**merged_params)
        on_log(f"$ {cmd}")
        rc, out = runner.run(cmd, timeout=300, on_output=on_log)
        if rc != 0:
            return False, f"命令失败 (rc={rc}): {cmd}"
    return True, f"{skill.name} 执行完成"


# 内置默认 Skill 列表（skills.json 未就绪时使用）
_DEFAULT_SKILLS = [
    Skill(
        id="usb_wifi",
        name="USB-WiFi 驱动适配",
        desc="自动检测并安装 USB-WiFi 网卡驱动",
        category="驱动 & 系统修复",
        commands=["sudo apt-get update", "sudo apt-get install -y rtl8821cu-dkms"],
        duration_hint="~5 min",
        verified=True,
    ),
    Skill(
        id="fix_browser",
        name="浏览器无法打开修复",
        desc="修复 Chromium/Firefox 启动异常",
        category="驱动 & 系统修复",
        commands=["sudo apt-get install --reinstall -y chromium-browser"],
        duration_hint="~2 min",
        verified=True,
    ),
    Skill(
        id="lerobot",
        name="LeRobot 开发环境配置",
        desc="一键配置 Hugging Face LeRobot 开发环境",
        category="应用 & 环境部署",
        commands=[
            "pip install lerobot",
            "python3 -c 'import lerobot; print(lerobot.__version__)'",
        ],
        duration_hint="~15 min",
        verified=True,
    ),
    Skill(
        id="qwen_demo",
        name="Qwen Demo 适配",
        desc="适配 Qwen 模型在 Jetson 上的推理环境",
        category="应用 & 环境部署",
        commands=[
            "pip install transformers accelerate",
            "python3 -c 'from transformers import AutoModelForCausalLM; print(\"ok\")'",
        ],
        duration_hint="~20 min",
        verified=True,
    ),
    Skill(
        id="install_jtop",
        name="jtop 监控工具安装",
        desc="安装 jetson-stats 系统监控工具",
        category="应用 & 环境部署",
        commands=["sudo pip3 install -U jetson-stats", "sudo systemctl restart jtop.service"],
        duration_hint="~2 min",
        verified=True,
    ),
]
