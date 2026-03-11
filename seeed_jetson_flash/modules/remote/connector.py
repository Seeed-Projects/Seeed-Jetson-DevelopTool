"""远程连接管理 — SSH 连通性检测"""
import socket
from seeed_jetson_flash.core.device import DeviceInfo


def check_ssh(host: str, port: int = 22, timeout: int = 5) -> bool:
    """检测目标主机 SSH 端口是否可达"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def scan_local_network(subnet: str = "192.168.1") -> list[str]:
    """
    简单扫描局域网内可达的 SSH 主机。
    TODO: 替换为 nmap 或 avahi-browse 实现更准确的发现。
    """
    reachable = []
    for i in range(1, 255):
        host = f"{subnet}.{i}"
        if check_ssh(host, timeout=0.3):
            reachable.append(host)
    return reachable
