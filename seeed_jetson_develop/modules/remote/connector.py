"""远程连接管理 — SSH 连通性检测"""
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from seeed_jetson_develop.core.device import DeviceInfo


def check_ssh(host: str, port: int = 22, timeout: int = 5) -> bool:
    """检测目标主机 SSH 端口是否可达"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _get_local_subnets() -> list[str]:
    """获取本机所有活跃网卡的子网前缀（如 192.168.1）。"""
    subnets = []
    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
            for a in addrs:
                ip = a.get("addr", "")
                if ip and not ip.startswith("127."):
                    parts = ip.rsplit(".", 1)
                    if len(parts) == 2:
                        subnets.append(parts[0])
    except ImportError:
        pass
    if not subnets:
        # fallback: 通过 UDP 探测本机出口 IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            subnets.append(ip.rsplit(".", 1)[0])
        except OSError:
            subnets.append("192.168.1")
    return list(dict.fromkeys(subnets))  # 去重保序


def scan_local_network(
    subnet: str | None = None,
    *,
    port: int = 22,
    timeout: float = 1.0,
    workers: int = 64,
    retries: int = 2,
    on_progress: "Callable[[int, int], None] | None" = None,
) -> list[str]:
    """
    并发扫描局域网内可达的 SSH 主机。

    - subnet: 子网前缀，如 "192.168.1"；None 时自动检测本机子网
    - workers: 并发线程数（默认 64，扫描 254 台约 2-4s）
    - on_progress: 可选回调 (scanned, total)
    """
    if subnet is None:
        subnets = _get_local_subnets()
    else:
        subnets = [subnet]

    all_hosts: list[str] = []
    for sn in subnets:
        all_hosts += [f"{sn}.{i}" for i in range(1, 255)]

    total = len(all_hosts)
    reachable: list[str] = []
    scanned = 0

    def _probe(host: str) -> str | None:
        for attempt in range(max(1, retries)):
            probe_timeout = timeout * (attempt + 1)
            try:
                with socket.create_connection((host, port), timeout=probe_timeout):
                    return host
            except OSError:
                continue
        return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_probe, h): h for h in all_hosts}
        for fut in as_completed(futures):
            scanned += 1
            if on_progress:
                on_progress(scanned, total)
            result = fut.result()
            if result:
                reachable.append(result)

    reachable.sort(key=lambda h: tuple(int(x) for x in h.split(".")))
    return reachable
