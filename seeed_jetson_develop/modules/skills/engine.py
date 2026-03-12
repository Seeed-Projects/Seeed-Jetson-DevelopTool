"""Skills 执行引擎 — 加载定义、参数化执行、日志回传"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from seeed_jetson_develop.core.runner import Runner

_DATA        = Path(__file__).parent / "data" / "skills.json"
_OPENCLAW    = Path(__file__).parent.parent.parent.parent / "skills" / "openclaw"

# 分类图标映射
CATEGORY_ICONS = {
    "驱动 & 系统修复": "🔧",
    "应用 & 环境部署": "📦",
    "网络 & 远程":    "🌐",
    "系统优化":       "⚙️",
    "AI / 大模型":    "🤖",
    "视觉 / YOLO":    "📹",
    "参考文档":       "📖",
}


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
    source:        str  = "builtin"   # "builtin" | "openclaw"
    md_path:       str  = ""          # SKILL.md 路径（openclaw 用）


# ── SKILL.md 解析器 ──────────────────────────────────────────────────────────
def _parse_skill_md(md_file: Path, slug: str) -> Optional[Skill]:
    try:
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
        # bash code blocks → commands
        cmds, in_bash = [], False
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
            cat = "驱动 & 系统修复"
        elif any(k in sl for k in ("yolo","yolov","vision","deepstream","nvblox","depth","detect","track","vlm","nvstreamer","maskcam","dashcam","traffic","zero-shot","efficient-vision","no-code","roboflow")):
            cat = "视觉 / YOLO"
        elif any(k in sl for k in ("llm","llama","deepseek","qwen","gpt","oss","rag","chatbot","whisper","speech","voice","subtitle","langchain","finetune","mlc","riva","dia","gr00t")):
            cat = "AI / 大模型"
        elif any(k in sl for k in ("docker","torch","install","setup","deploy","env","lerobot","ollama","frigate","pinocchio","jetson-ai","jetson-docker")):
            cat = "应用 & 环境部署"
        elif any(k in sl for k in ("vnc","ssh","remote","vscode","proxy","neqto","allxon","ota","update","network")):
            cat = "网络 & 远程"
        elif any(k in sl for k in ("power","swap","fan","cache","log","backup","encrypt","disk","bsp","ko-module","diy-bsp","spi","ethercat")):
            cat = "系统优化"
        else:
            cat = "参考文档"
        return Skill(
            id=slug, name=name, desc=desc or f"{slug} skill",
            category=cat, commands=cmds[:15],
            duration_hint="—", verified=False,
            source="openclaw", md_path=str(md_file),
        )
    except Exception:
        return None


def load_openclaw_skills() -> list[Skill]:
    """扫描 skills/openclaw/ 目录，解析所有 SKILL.md。"""
    if not _OPENCLAW.exists():
        return []
    skills = []
    for d in sorted(_OPENCLAW.iterdir()):
        if not d.is_dir():
            continue
        md = d / "SKILL.md"
        if md.exists():
            s = _parse_skill_md(md, d.name)
            if s:
                skills.append(s)
    return skills


def load_skills() -> list[Skill]:
    """加载技能列表：先读 skills.json，否则用内置默认值；追加 openclaw 参考技能。"""
    if _DATA.exists():
        raw = json.loads(_DATA.read_text(encoding="utf-8"))
        builtin = [Skill(**{k: v for k, v in s.items() if k in Skill.__dataclass_fields__}) for s in raw]
    else:
        builtin = list(_DEFAULT_SKILLS)
    # 补充 openclaw 技能（不重复）
    existing_ids = {s.id for s in builtin}
    for s in load_openclaw_skills():
        if s.id not in existing_ids:
            builtin.append(s)
    return builtin


def run_skill(
    skill: Skill,
    runner: Runner,
    on_log: Callable[[str], None],
    params: Optional[dict] = None,
) -> tuple[bool, str]:
    merged = {**skill.params, **(params or {})}
    for cmd_tpl in skill.commands:
        try:
            cmd = cmd_tpl.format(**merged)
        except KeyError:
            cmd = cmd_tpl
        on_log(f"$ {cmd}")
        rc, _ = runner.run(cmd, timeout=300, on_output=on_log)
        if rc != 0:
            return False, f"命令失败 (rc={rc})"
    return True, f"{skill.name} 执行完成"


# ── 内置精选技能列表 ──────────────────────────────────────────────────────────
_DEFAULT_SKILLS: list[Skill] = [

    # ── 驱动 & 系统修复 ────────────────────────────────────────────────────
    Skill(
        id="usb_wifi", name="USB-WiFi 驱动适配",
        desc="自动检测 USB-WiFi 网卡型号并安装驱动，支持 RTL8811/8812/8821CU 系列",
        category="驱动 & 系统修复",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y dkms git",
            "lsusb | grep -i '0bda' || echo '[提示] 未检测到 Realtek 网卡，请确认已插入'",
            "sudo apt-get install -y rtl8821cu-dkms 2>/dev/null || "
            "(git clone --depth=1 https://github.com/morrownr/8821cu-20210916.git /tmp/8821cu "
            "&& cd /tmp/8821cu && sudo bash install-driver.sh)",
        ],
        duration_hint="~5 min", verified=True,
    ),
    Skill(
        id="usb_wifi_88x2bu", name="USB-WiFi 88x2bu 驱动",
        desc="安装 RTL88x2BU 系列 USB-WiFi 驱动（reComputer 外接网卡常用）",
        category="驱动 & 系统修复",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y dkms git build-essential",
            "git clone --depth=1 https://github.com/morrownr/88x2bu-20210702.git /tmp/88x2bu",
            "cd /tmp/88x2bu && sudo bash install-driver.sh",
        ],
        duration_hint="~8 min", verified=True,
    ),
    Skill(
        id="5g_modem", name="5G 模组驱动安装",
        desc="支持 Quectel EC20/EC25/EM05/RM500Q 等主流 5G 模组驱动安装与配置",
        category="驱动 & 系统修复",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y usb-modeswitch usb-modeswitch-data ppp modemmanager",
            "lsusb | grep -iE 'quectel|sierra|huawei' || echo '[提示] 未检测到 5G 模组'",
            "sudo systemctl restart ModemManager",
            "mmcli -L",
        ],
        duration_hint="~8 min", verified=False,
        risk="安装后需重启生效",
    ),
    Skill(
        id="fix_browser", name="浏览器无法打开修复",
        desc="修复 Chromium/Firefox 在 Jetson 上启动崩溃或无法打开的问题",
        category="驱动 & 系统修复",
        commands=[
            "sudo apt-get install --reinstall -y chromium-browser",
            "chromium-browser --version",
        ],
        duration_hint="~2 min", verified=True,
    ),
    Skill(
        id="fix_bt_wifi", name="蓝牙 WiFi 冲突修复",
        desc="解决蓝牙与 WiFi 共用 2.4GHz 频段时的干扰和断连问题",
        category="驱动 & 系统修复",
        commands=[
            "sudo modprobe -r btusb && sudo modprobe btusb",
            "sudo rfkill unblock all",
            "sudo hciconfig hci0 up 2>/dev/null || true",
            "hciconfig",
        ],
        duration_hint="~3 min", verified=False,
    ),
    Skill(
        id="fix_nvme", name="NVMe SSD 启动修复",
        desc="诊断并修复 NVMe SSD 挂载、引导失败问题",
        category="驱动 & 系统修复",
        commands=[
            "lsblk -d -o NAME,TYPE,SIZE,MODEL",
            "sudo apt-get install -y nvme-cli",
            "sudo nvme list",
            "sudo parted -l 2>/dev/null | grep -A3 nvme",
        ],
        duration_hint="~5 min", verified=False,
        risk="操作磁盘分区前请确认已备份数据",
    ),
    Skill(
        id="fix_docker_space", name="Docker 磁盘空间清理",
        desc="清理悬空镜像、停止的容器和无用 volume，释放存储空间",
        category="驱动 & 系统修复",
        commands=[
            "df -h / && docker system df",
            "docker container prune -f",
            "docker image prune -f",
            "docker volume prune -f",
            "docker system df && df -h /",
        ],
        duration_hint="~2 min", verified=True,
        risk="将删除所有停止的容器和悬空镜像",
    ),

    # ── 应用 & 环境部署 ────────────────────────────────────────────────────
    Skill(
        id="install_torch", name="GPU PyTorch 安装",
        desc="安装 CUDA 版 PyTorch，自动检测 JetPack 版本选择对应 wheel",
        category="应用 & 环境部署",
        commands=[
            "sudo apt-get install -y python3-pip libopenblas-dev",
            "cat /etc/nv_tegra_release | head -1",
            "python3 -c \"import subprocess; r=subprocess.run('cat /etc/nv_tegra_release',shell=True,"
            "capture_output=True,text=True); print('JetPack 6.x' if 'R36' in r.stdout else 'JetPack 5.x')\"",
        ],
        duration_hint="~10 min", verified=True,
    ),
    Skill(
        id="install_jtop", name="jtop 监控工具安装",
        desc="安装 jetson-stats，提供 GPU/CPU/内存实时监控面板",
        category="应用 & 环境部署",
        commands=[
            "sudo pip3 install -U jetson-stats",
            "sudo systemctl restart jtop.service",
            "jtop --version",
        ],
        duration_hint="~2 min", verified=True,
    ),
    Skill(
        id="install_docker", name="Docker 环境初始化",
        desc="安装 Docker Engine，配置镜像加速，将当前用户加入 docker 组",
        category="应用 & 环境部署",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y docker.io",
            "sudo systemctl enable docker && sudo systemctl start docker",
            "sudo usermod -aG docker $USER",
            "docker --version",
        ],
        duration_hint="~5 min", verified=True,
        risk="需重新登录或执行 newgrp docker 后免 sudo 生效",
    ),
    Skill(
        id="lerobot", name="LeRobot 开发环境配置",
        desc="一键配置 Hugging Face LeRobot 机器人开发套件",
        category="应用 & 环境部署",
        commands=[
            "pip3 install lerobot",
            "python3 -c 'import lerobot; print(\"LeRobot:\", lerobot.__version__)'",
        ],
        duration_hint="~15 min", verified=True,
    ),
    Skill(
        id="qwen_demo", name="Qwen2 推理环境",
        desc="配置 Qwen2 模型在 Jetson 上的推理环境（transformers + accelerate）",
        category="应用 & 环境部署",
        commands=[
            "pip3 install transformers accelerate",
            "python3 -c 'from transformers import AutoModelForCausalLM; print(\"transformers ready\")'",
        ],
        duration_hint="~20 min", verified=True,
    ),
    Skill(
        id="install_ollama", name="Ollama 服务部署",
        desc="安装 Ollama，支持 Llama、Qwen、Mistral 等模型本地推理",
        category="应用 & 环境部署",
        commands=[
            "curl -fsSL https://ollama.com/install.sh | sh",
            "ollama --version",
            "sudo systemctl enable ollama",
        ],
        duration_hint="~5 min", verified=True,
    ),
    Skill(
        id="deepseek_deploy", name="DeepSeek 本地部署",
        desc="通过 Ollama 部署 DeepSeek-R1:7b（需 8GB+ 内存）",
        category="应用 & 环境部署",
        commands=[
            "which ollama || curl -fsSL https://ollama.com/install.sh | sh",
            "ollama pull deepseek-r1:7b",
            "ollama list",
        ],
        duration_hint="~30 min", verified=True,
        risk="模型文件约 4.7GB，需要至少 8GB RAM",
    ),
    Skill(
        id="install_frigate", name="Frigate NVR 部署",
        desc="基于 Docker 部署 Frigate 本地 AI 视频监控，支持多路摄像头",
        category="应用 & 环境部署",
        commands=[
            "docker info || (sudo apt-get install -y docker.io && sudo systemctl start docker)",
            "docker pull ghcr.io/blakeblackshear/frigate:stable",
            "echo '✓ 镜像拉取完成，请配置 config.yml 后启动容器'",
        ],
        duration_hint="~15 min", verified=False,
        risk="需要 Docker 环境，镜像约 1GB",
    ),
    Skill(
        id="install_yolov8", name="YOLOv8 环境配置",
        desc="安装 Ultralytics YOLOv8，适配 Jetson GPU 推理",
        category="应用 & 环境部署",
        commands=[
            "pip3 install ultralytics",
            "python3 -c 'import ultralytics; print(\"YOLOv8:\", ultralytics.__version__)'",
            "python3 -c 'import torch; print(\"CUDA:\", torch.cuda.is_available())'",
        ],
        duration_hint="~5 min", verified=True,
    ),

    # ── 网络 & 远程 ────────────────────────────────────────────────────────
    Skill(
        id="vscode_server", name="VS Code Server 部署",
        desc="在 Jetson 上部署 code-server，浏览器即可远程编码",
        category="网络 & 远程",
        commands=[
            "curl -fsSL https://code-server.dev/install.sh | sh",
            "sudo systemctl enable --now code-server@$USER",
            "echo \"访问地址: http://$(hostname -I | awk '{print $1}'):8080\"",
            "cat ~/.config/code-server/config.yaml | grep password",
        ],
        duration_hint="~8 min", verified=False,
    ),
    Skill(
        id="vnc_setup", name="VNC 远程桌面配置",
        desc="配置 x11vnc，通过 VNC 客户端远程访问 Jetson 桌面",
        category="网络 & 远程",
        commands=[
            "sudo apt-get install -y x11vnc",
            "x11vnc -storepasswd",
            "x11vnc -display :0 -forever -shared -bg -rfbauth ~/.vnc/passwd",
            "echo \"VNC 端口: 5900  |  IP: $(hostname -I | awk '{print $1}')\"",
        ],
        duration_hint="~5 min", verified=True,
    ),
    Skill(
        id="ssh_keygen", name="SSH 免密登录配置",
        desc="生成 RSA 密钥对，配置目标主机免密登录",
        category="网络 & 远程",
        commands=[
            "[ -f ~/.ssh/id_rsa ] || ssh-keygen -t rsa -b 4096 -N '' -f ~/.ssh/id_rsa",
            "cat ~/.ssh/id_rsa.pub",
            "echo '将以上公钥内容追加到目标机器的 ~/.ssh/authorized_keys'",
        ],
        duration_hint="~1 min", verified=True,
    ),
    Skill(
        id="proxy_config", name="网络代理配置",
        desc="为 apt / pip / docker 统一配置 HTTP 代理（国内加速）",
        category="网络 & 远程",
        commands=[
            "pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple",
            "pip3 config list",
            "echo '✓ pip 已配置清华源'",
        ],
        duration_hint="~1 min", verified=True,
    ),

    # ── 系统优化 ───────────────────────────────────────────────────────────
    Skill(
        id="max_performance", name="最大性能模式",
        desc="开启最大功率模式 + jetson_clocks，适合模型推理/训练场景",
        category="系统优化",
        commands=[
            "sudo nvpmodel -q",
            "sudo nvpmodel -m 0",
            "sudo jetson_clocks",
            "sudo nvpmodel -q",
        ],
        duration_hint="~1 min", verified=True,
        risk="功耗和温度将显著升高，请确保散热良好",
    ),
    Skill(
        id="swap_setup", name="Swap 内存扩展（8GB）",
        desc="创建 8GB Swap 文件并持久化，扩展可用内存，适合大模型推理",
        category="系统优化",
        commands=[
            "free -h",
            "sudo fallocate -l 8G /swapfile",
            "sudo chmod 600 /swapfile",
            "sudo mkswap /swapfile",
            "sudo swapon /swapfile",
            "grep -q '/swapfile' /etc/fstab || echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab",
            "free -h",
        ],
        duration_hint="~2 min", verified=True,
        risk="需要至少 8GB 可用磁盘空间",
    ),
    Skill(
        id="fan_fullspeed", name="风扇全速运行",
        desc="设置风扇转速到最大，适合高负载场景",
        category="系统优化",
        commands=[
            "sudo sh -c 'echo 255 > /sys/devices/pwm-fan/target_pwm' 2>/dev/null || "
            "sudo jetson_clocks --fan",
            "cat /sys/devices/pwm-fan/target_pwm 2>/dev/null || echo '风扇已设置为全速'",
        ],
        duration_hint="~1 min", verified=True,
    ),
    Skill(
        id="clear_cache", name="系统缓存清理",
        desc="清理 apt 缓存、pip 缓存和系统日志，释放磁盘空间",
        category="系统优化",
        commands=[
            "df -h /",
            "sudo apt-get autoremove -y && sudo apt-get autoclean",
            "pip3 cache purge 2>/dev/null || true",
            "sudo journalctl --vacuum-size=100M",
            "df -h /",
        ],
        duration_hint="~3 min", verified=True,
    ),
    Skill(
        id="software_upgrade", name="系统软件升级",
        desc="升级所有已安装的系统软件包到最新版本",
        category="系统优化",
        commands=[
            "sudo apt-get update",
            "sudo apt-get upgrade -y",
            "sudo apt-get autoremove -y",
        ],
        duration_hint="~10 min", verified=True,
        risk="升级过程中请勿断电，某些包升级后需重启",
    ),
]
