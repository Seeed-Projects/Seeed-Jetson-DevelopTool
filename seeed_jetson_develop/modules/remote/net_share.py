"""PC 网络共享给 Jetson — 跨平台实现。

Linux:  sysctl ip_forward + iptables MASQUERADE
Windows: netsh ICS (简化版)

用法：
    enable_nat(wan="wlan0", lan="eth0")   → 开启
    disable_nat(wan="wlan0", lan="eth0")  → 关闭
"""
from __future__ import annotations

import re
import subprocess
import sys


def _run(cmd: str, sudo_password: str = "") -> tuple[int, str]:
    """执行 shell 命令，Linux 下可用 sudo -S。"""
    if sys.platform == "win32":
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return r.returncode, (r.stdout + r.stderr).strip()
    if sudo_password:
        proc = subprocess.Popen(
            ["sudo", "-S", "bash", "-c", cmd],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True,
        )
        out, _ = proc.communicate(input=sudo_password + "\n", timeout=30)
        return proc.returncode, out.strip()
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=30)
    return r.returncode, (r.stdout + r.stderr).strip()


# ── 网卡检测 ──────────────────────────────────────────────────────────────────

def detect_wan_interface() -> str | None:
    """检测有默认路由（能上网）的网卡名。"""
    if sys.platform == "win32":
        return _detect_wan_windows()
    return _detect_wan_linux()


def _detect_wan_linux() -> str | None:
    try:
        r = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True, timeout=10,
        )
        # default via 192.168.1.1 dev wlan0 proto ...
        m = re.search(r"default\s+via\s+\S+\s+dev\s+(\S+)", r.stdout)
        return m.group(1) if m else None
    except Exception:
        return None


def _detect_wan_windows() -> str | None:
    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
             "Select-Object -First 1 -ExpandProperty InterfaceAlias"],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() or None
    except Exception:
        return None


def list_interfaces() -> list[dict]:
    """列出所有网卡 [{name, ip, is_up}]。"""
    if sys.platform == "win32":
        return _list_ifaces_windows()
    return _list_ifaces_linux()


def _list_ifaces_linux() -> list[dict]:
    result = []
    try:
        r = subprocess.run(["ip", "-br", "addr"], capture_output=True, text=True, timeout=10)
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[0]
            state = parts[1]
            if name == "lo" or name.startswith(("docker", "virbr", "br-", "veth")):
                continue
            ip = ""
            for p in parts[2:]:
                if "/" in p and not p.startswith("fe80"):
                    ip = p.split("/")[0]
                    break
            result.append({"name": name, "ip": ip, "is_up": state == "UP"})
    except Exception:
        pass
    return result


def _list_ifaces_windows() -> list[dict]:
    result = []
    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | "
             "ForEach-Object { $ip = (Get-NetIPAddress -InterfaceIndex $_.ifIndex "
             "-AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress; "
             "\"$($_.Name)|$ip|$($_.Status)\" }"],
            capture_output=True, text=True, timeout=15,
        )
        for line in r.stdout.strip().splitlines():
            parts = line.split("|")
            if len(parts) >= 3:
                result.append({"name": parts[0], "ip": parts[1] or "", "is_up": parts[2] == "Up"})
    except Exception:
        pass
    return result


# ── NAT 开启 / 关闭 ──────────────────────────────────────────────────────────

def enable_nat(wan: str, lan: str, sudo_password: str = "") -> tuple[bool, str]:
    """开启 NAT 转发：wan 是上网网卡，lan 是连 Jetson 的网卡。"""
    if sys.platform == "win32":
        return _enable_nat_windows(wan, lan)
    return _enable_nat_linux(wan, lan, sudo_password)


def _enable_nat_linux(wan: str, lan: str, sudo_password: str) -> tuple[bool, str]:
    steps = [
        "sysctl -w net.ipv4.ip_forward=1",
        f"iptables -t nat -C POSTROUTING -o {wan} -j MASQUERADE 2>/dev/null || "
        f"iptables -t nat -A POSTROUTING -o {wan} -j MASQUERADE",
        f"iptables -C FORWARD -i {lan} -o {wan} -j ACCEPT 2>/dev/null || "
        f"iptables -A FORWARD -i {lan} -o {wan} -j ACCEPT",
        f"iptables -C FORWARD -i {wan} -o {lan} -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || "
        f"iptables -A FORWARD -i {wan} -o {lan} -m state --state RELATED,ESTABLISHED -j ACCEPT",
    ]
    logs = []
    for cmd in steps:
        rc, out = _run(cmd, sudo_password)
        logs.append(f"$ {cmd}\n{out}" if out else f"$ {cmd}")
        if rc != 0:
            return False, "\n".join(logs) + f"\n\n命令失败 (rc={rc})"
    return True, "\n".join(logs)


def _enable_nat_windows(wan: str, lan: str) -> tuple[bool, str]:
    # Windows ICS 通过 COM 接口，用 PowerShell 脚本
    script = (
        f'$m = New-Object -ComObject HNetCfg.HNetShare; '
        f'$conns = $m.EnumEveryConnection; '
        f'foreach ($c in $conns) {{ '
        f'  $props = $m.NetConnectionProps($c); '
        f'  $cfg = $m.INetSharingConfigurationForINetConnection($c); '
        f'  if ($props.Name -eq "{wan}") {{ $cfg.EnableSharing(0) }}; '  # 0 = public
        f'  if ($props.Name -eq "{lan}") {{ $cfg.EnableSharing(1) }}; '  # 1 = private
        f'}}'
    )
    rc, out = _run(f'powershell -Command "{script}"')
    if rc == 0:
        return True, f"ICS 已开启：{wan} → {lan}\n{out}"
    return False, f"ICS 开启失败：{out}"


def disable_nat(wan: str, lan: str, sudo_password: str = "") -> tuple[bool, str]:
    """关闭 NAT 转发。"""
    if sys.platform == "win32":
        return _disable_nat_windows(wan, lan)
    return _disable_nat_linux(wan, lan, sudo_password)


def _disable_nat_linux(wan: str, lan: str, sudo_password: str) -> tuple[bool, str]:
    steps = [
        f"iptables -t nat -D POSTROUTING -o {wan} -j MASQUERADE 2>/dev/null; true",
        f"iptables -D FORWARD -i {lan} -o {wan} -j ACCEPT 2>/dev/null; true",
        f"iptables -D FORWARD -i {wan} -o {lan} -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null; true",
    ]
    logs = []
    for cmd in steps:
        rc, out = _run(cmd, sudo_password)
        logs.append(f"$ {cmd}")
    return True, "\n".join(logs)


def _disable_nat_windows(wan: str, lan: str) -> tuple[bool, str]:
    script = (
        f'$m = New-Object -ComObject HNetCfg.HNetShare; '
        f'$conns = $m.EnumEveryConnection; '
        f'foreach ($c in $conns) {{ '
        f'  $cfg = $m.INetSharingConfigurationForINetConnection($c); '
        f'  $cfg.DisableSharing() '
        f'}}'
    )
    rc, out = _run(f'powershell -Command "{script}"')
    return True, f"ICS 已关闭\n{out}"


def configure_jetson_dns_via_serial(
    port: str, username: str, password: str,
    gateway: str, dns: str = "8.8.8.8",
) -> str:
    """通过串口给 Jetson 配置默认网关和 DNS（返回要执行的命令）。"""
    pwd_escaped = password.replace("'", "'\\''")
    inner = (
        f"nmcli con mod $(nmcli -t -f NAME con show --active | head -1) "
        f"ipv4.gateway {gateway} ipv4.dns '{dns}'"
        f" && nmcli con up $(nmcli -t -f NAME con show --active | head -1)"
    )
    return f"echo '{pwd_escaped}' | sudo -S bash -c '{inner}'"
