"""Remote connectivity helpers: SSH check and LAN scan."""

from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from seeed_jetson_develop.core.device import DeviceInfo


def check_ssh(host: str, port: int = 22, timeout: int = 5) -> bool:
    """Check whether the SSH port on target host is reachable."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _get_local_subnets() -> list[str]:
    """Return active local subnet prefixes, for example `192.168.1`."""
    subnets: list[str] = []
    try:
        import netifaces

        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
            for addr in addrs:
                ip = addr.get("addr", "")
                if ip and not ip.startswith("127."):
                    parts = ip.rsplit(".", 1)
                    if len(parts) == 2:
                        subnets.append(parts[0])
    except ImportError:
        pass

    if not subnets:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
            subnets.append(ip.rsplit(".", 1)[0])
        except OSError:
            subnets.append("192.168.1")

    return list(dict.fromkeys(subnets))


def scan_local_network(
    subnet: str | None = None,
    *,
    port: int = 22,
    timeout: float = 1.0,
    workers: int = 64,
    retries: int = 2,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[str]:
    """Scan LAN for reachable SSH hosts."""
    subnets = _get_local_subnets() if subnet is None else [subnet]
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
        futures = {pool.submit(_probe, host): host for host in all_hosts}
        for future in as_completed(futures):
            scanned += 1
            if on_progress:
                on_progress(scanned, total)
            result = future.result()
            if result:
                reachable.append(result)

    reachable.sort(key=lambda host: tuple(int(x) for x in host.split(".")))
    return reachable

