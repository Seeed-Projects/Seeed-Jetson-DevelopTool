"""诊断项定义 — 每项包含名称、检测命令、结果解析"""
from dataclasses import dataclass
from typing import Callable, Optional
from seeed_jetson_flash.core.runner import Runner


@dataclass
class DiagItem:
    id: str
    icon: str
    name: str
    cmd: str
    parse: Callable[[int, str], tuple[str, str]]  # (returncode, output) -> (status, color)


def _net(rc, out):
    return ("正常", "ok") if rc == 0 else ("无法连接", "error")

def _torch(rc, out):
    if rc == 0 and "True" in out: return ("CUDA 可用", "ok")
    if rc == 0: return ("CPU 模式", "warn")
    return ("未安装", "error")

def _docker(rc, out):
    return ("运行中", "ok") if rc == 0 else ("未运行", "error")

def _jtop(rc, out):
    return ("已安装", "ok") if rc == 0 else ("未安装", "warn")

def _camera(rc, out):
    return ("已检测到", "ok") if rc == 0 and out.strip() else ("未检测到", "warn")

def _disk(rc, out):
    return (out.strip()[:40] if out.strip() else "未知", "info") if rc == 0 else ("检测失败", "error")


DIAG_ITEMS = [
    DiagItem("network", "🌐", "网络连接",       "ping -c 1 -W 2 8.8.8.8",                                    _net),
    DiagItem("torch",   "⚡", "GPU Torch",      "python3 -c 'import torch; print(torch.cuda.is_available())'", _torch),
    DiagItem("docker",  "🐳", "Docker 服务",    "docker ps -q",                                               _docker),
    DiagItem("jtop",    "📊", "jtop 监控",      "which jtop",                                                 _jtop),
    DiagItem("camera",  "📷", "USB 摄像头",     "ls /dev/video0",                                             _camera),
    DiagItem("disk",    "💾", "磁盘启动方式",   "lsblk -d -o NAME,TYPE | grep disk | head -1",                _disk),
]


def run_all(runner: Runner, on_result: Callable[[str, str, str], None]):
    """
    逐项执行诊断。
    on_result(item_id, status_text, color_key) 每项完成后回调。
    color_key: "ok" | "warn" | "error" | "info"
    """
    for item in DIAG_ITEMS:
        rc, out = runner.run(item.cmd, timeout=10)
        status, color = item.parse(rc, out)
        on_result(item.id, status, color)
