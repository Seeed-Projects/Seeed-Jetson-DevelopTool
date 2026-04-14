"""PC 网络共享给 Jetson — 跨平台实现。

Linux:  sysctl ip_forward + iptables MASQUERADE
Windows: netsh ICS (简化版)

用法：
    enable_nat(wan="wlan0", lan="eth0")   → 开启
    disable_nat(wan="wlan0", lan="eth0")  → 关闭
"""
from __future__ import annotations

import re
import shlex
import subprocess
import sys

_IFACE_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _run(cmd: str, sudo_password: str = "") -> tuple[int, str]:
    """执行 shell 命令，Linux 下可用 sudo -S。"""
    if sys.platform == "win32":
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return r.returncode, (r.stdout + r.stderr).strip()
    if sudo_password:
        proc = subprocess.Popen(
            ["sudo", "-S", "bash", "-c", cmd],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        out, err = proc.communicate(input=sudo_password + "\n", timeout=30)
        # 过滤 sudo 密码提示行，避免污染日志
        combined = out
        if err:
            filtered = "\n".join(
                line for line in err.splitlines()
                if line.strip()
                and not line.strip().startswith("[sudo]")
                and "password for" not in line.lower()
                and "需要密码" not in line
                and "的密码" not in line
            )
            if filtered.strip():
                combined = (combined + "\n" + filtered).strip()
        return proc.returncode, combined.strip()
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=30)
    return r.returncode, (r.stdout + r.stderr).strip()


def _ps_quote(value: str) -> str:
    """将字符串安全地嵌入 PowerShell 单引号字面量。"""
    return "'" + value.replace("'", "''") + "'"


def _run_powershell(script: str, timeout: int = 30) -> tuple[int, str]:
    """用 -EncodedCommand 传脚本，彻底避免引号/中文编码被 shell 二次解析的问题。"""
    import base64
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    r = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
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
        rc, out = _run_powershell(
            "Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
            "Select-Object -First 1 -ExpandProperty InterfaceAlias",
            timeout=10,
        )
        if rc == 0:
            return out.strip() or None
    except Exception:
        pass
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
        rc, out = _run_powershell(
            "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | "
            "ForEach-Object { $ip = (Get-NetIPAddress -InterfaceIndex $_.ifIndex "
            "-AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress; "
            "\"$($_.Name)|$ip|$($_.Status)\" }",
            timeout=15,
        )
        if rc == 0:
            for line in out.strip().splitlines():
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
    return _enable_nat_linux_safe(wan, lan, sudo_password)


def _enable_nat_linux(wan: str, lan: str, sudo_password: str) -> tuple[bool, str]:
    steps = [
        # 持久化写入 sysctl.conf（重启后也生效），同时立即激活
        "grep -q 'net.ipv4.ip_forward=1' /etc/sysctl.conf 2>/dev/null || "
        "echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf; "
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
    wan_ps = _ps_quote(wan)
    lan_ps = _ps_quote(lan)
    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"$wan = {wan_ps}; "
        f"$lan = {lan_ps}; "
        "$wanFound = $false; "
        "$lanFound = $false; "
        "$m = New-Object -ComObject HNetCfg.HNetShare; "
        "$conns = $m.EnumEveryConnection; "
        "foreach ($c in $conns) { "
        "  $props = $m.NetConnectionProps($c); "
        "  $cfg = $m.INetSharingConfigurationForINetConnection($c); "
        "  if ($props.Name -eq $wan) { $cfg.EnableSharing(0); $wanFound = $true }; "
        "  if ($props.Name -eq $lan) { $cfg.EnableSharing(1); $lanFound = $true }; "
        "} "
        'if (-not $wanFound) { throw "未找到 WAN 网卡: $wan" }; '
        'if (-not $lanFound) { throw "未找到 LAN 网卡: $lan" }; '
        'Write-Output ("ICS enabled: " + $wan + " -> " + $lan)'
    )
    rc, out = _run_powershell(script)
    if rc == 0:
        return True, f"ICS 已开启：{wan} → {lan}\n{out}"
    return False, f"ICS 开启失败：{out}"


def disable_nat(wan: str, lan: str, sudo_password: str = "") -> tuple[bool, str]:
    """关闭 NAT 转发。"""
    if sys.platform == "win32":
        return _disable_nat_windows(wan, lan)
    return _disable_nat_linux_safe(wan, lan, sudo_password)


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
        "$ErrorActionPreference = 'Stop'; "
        "$m = New-Object -ComObject HNetCfg.HNetShare; "
        "$conns = $m.EnumEveryConnection; "
        "foreach ($c in $conns) { "
        "  $cfg = $m.INetSharingConfigurationForINetConnection($c); "
        "  $cfg.DisableSharing() "
        "} "
        "Write-Output 'ICS disabled'"
    )
    rc, out = _run_powershell(script)
    if rc == 0:
        return True, f"ICS 已关闭\n{out}"
    return False, f"ICS 关闭失败：{out}"


def _validate_iface_name(name: str, field: str) -> str:
    value = (name or "").strip()
    if not value or not _IFACE_RE.fullmatch(value):
        raise ValueError(f"invalid interface name for {field}: {name!r}")
    return value


def _run_argv(args: list[str], sudo_password: str = "", timeout: int = 30) -> tuple[int, str]:
    if sudo_password:
        proc = subprocess.Popen(
            ["sudo", "-S", *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = proc.communicate(input=sudo_password + "\n", timeout=timeout)
        return proc.returncode, ((out or "") + (err or "")).strip()
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def _ensure_iptables_rule(
    check_args: list[str], add_args: list[str], sudo_password: str, logs: list[str]
) -> tuple[bool, int]:
    rc, out = _run_argv(["iptables", *check_args], sudo_password)
    logs.append(f"$ iptables {' '.join(check_args)}")
    if out:
        logs.append(out)
    if rc == 0:
        return True, 0
    rc2, out2 = _run_argv(["iptables", *add_args], sudo_password)
    logs.append(f"$ iptables {' '.join(add_args)}")
    if out2:
        logs.append(out2)
    return rc2 == 0, rc2


def _remove_iptables_rule_if_exists(
    check_args: list[str], del_args: list[str], sudo_password: str, logs: list[str]
) -> tuple[bool, int]:
    rc, out = _run_argv(["iptables", *check_args], sudo_password)
    logs.append(f"$ iptables {' '.join(check_args)}")
    if out:
        logs.append(out)
    if rc != 0:
        logs.append("rule not present, skip delete")
        return True, 0
    rc2, out2 = _run_argv(["iptables", *del_args], sudo_password)
    logs.append(f"$ iptables {' '.join(del_args)}")
    if out2:
        logs.append(out2)
    return rc2 == 0, rc2


def _enable_nat_linux_safe(wan: str, lan: str, sudo_password: str) -> tuple[bool, str]:
    try:
        wan = _validate_iface_name(wan, "wan")
        lan = _validate_iface_name(lan, "lan")
    except ValueError as exc:
        return False, str(exc)

    logs: list[str] = []
    rc, out = _run(
        "grep -q 'net.ipv4.ip_forward=1' /etc/sysctl.conf 2>/dev/null || "
        "echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf; "
        "sysctl -w net.ipv4.ip_forward=1",
        sudo_password,
    )
    logs.append("$ ensure ip_forward")
    if out:
        logs.append(out)
    if rc != 0:
        return False, "\n".join(logs) + f"\n\ncommand failed (rc={rc})"

    ok, rc = _ensure_iptables_rule(
        ["-t", "nat", "-C", "POSTROUTING", "-o", wan, "-j", "MASQUERADE"],
        ["-t", "nat", "-A", "POSTROUTING", "-o", wan, "-j", "MASQUERADE"],
        sudo_password,
        logs,
    )
    if not ok:
        return False, "\n".join(logs) + f"\n\nfailed to ensure NAT rule (rc={rc})"

    ok, rc = _ensure_iptables_rule(
        ["-C", "FORWARD", "-i", lan, "-o", wan, "-j", "ACCEPT"],
        ["-A", "FORWARD", "-i", lan, "-o", wan, "-j", "ACCEPT"],
        sudo_password,
        logs,
    )
    if not ok:
        return False, "\n".join(logs) + f"\n\nfailed to ensure FORWARD LAN->WAN rule (rc={rc})"

    ok, rc = _ensure_iptables_rule(
        ["-C", "FORWARD", "-i", wan, "-o", lan, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
        ["-A", "FORWARD", "-i", wan, "-o", lan, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
        sudo_password,
        logs,
    )
    if not ok:
        return False, "\n".join(logs) + f"\n\nfailed to ensure FORWARD WAN->LAN rule (rc={rc})"

    return True, "\n".join(logs)


def _disable_nat_linux_safe(wan: str, lan: str, sudo_password: str) -> tuple[bool, str]:
    try:
        wan = _validate_iface_name(wan, "wan")
        lan = _validate_iface_name(lan, "lan")
    except ValueError as exc:
        return False, str(exc)

    logs: list[str] = []
    ok, rc = _remove_iptables_rule_if_exists(
        ["-t", "nat", "-C", "POSTROUTING", "-o", wan, "-j", "MASQUERADE"],
        ["-t", "nat", "-D", "POSTROUTING", "-o", wan, "-j", "MASQUERADE"],
        sudo_password,
        logs,
    )
    if not ok:
        return False, "\n".join(logs) + f"\n\nfailed to delete NAT rule (rc={rc})"

    ok, rc = _remove_iptables_rule_if_exists(
        ["-C", "FORWARD", "-i", lan, "-o", wan, "-j", "ACCEPT"],
        ["-D", "FORWARD", "-i", lan, "-o", wan, "-j", "ACCEPT"],
        sudo_password,
        logs,
    )
    if not ok:
        return False, "\n".join(logs) + f"\n\nfailed to delete FORWARD LAN->WAN rule (rc={rc})"

    ok, rc = _remove_iptables_rule_if_exists(
        ["-C", "FORWARD", "-i", wan, "-o", lan, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
        ["-D", "FORWARD", "-i", wan, "-o", lan, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
        sudo_password,
        logs,
    )
    if not ok:
        return False, "\n".join(logs) + f"\n\nfailed to delete FORWARD WAN->LAN rule (rc={rc})"

    return True, "\n".join(logs)


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


def get_interface_ip(iface_name: str) -> str | None:
    """获取指定网卡的 IPv4 地址。"""
    if sys.platform == "win32":
        try:
            rc, out = _run_powershell(
                f"(Get-NetIPAddress -InterfaceAlias {_ps_quote(iface_name)} "
                f"-AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress",
                timeout=10,
            )
            if rc == 0:
                return out.strip() or None
        except Exception:
            return None
    try:
        r = subprocess.run(
            ["ip", "-4", "-br", "addr", "show", iface_name],
            capture_output=True, text=True, timeout=10,
        )
        for part in r.stdout.split():
            if "/" in part and not part.startswith("fe80"):
                return part.split("/")[0]
    except Exception:
        pass
    return None


def build_jetson_gateway_cmd(
    sudo_password: str, gateway: str, dns: str = "8.8.8.8",
) -> str:
    """生成在 Jetson 上通过 SSH 配置默认网关和 DNS 的命令。
    SSHRunner 已通过 _wrap_with_sudo_password 自动注入 sudo 密码，直接用 sudo 即可。
    sudo_password 参数保留以兼容调用方，不再使用。
    """
    script = _build_jetson_gateway_script(gateway, dns)
    return f"sudo bash -lc {shlex.quote(script)}"


def build_jetson_gateway_manual_cmd(gateway: str, dns: str = "8.8.8.8") -> str:
    """生成在 Jetson 上手动执行的网关 / DNS 配置命令。"""
    return f"sudo bash -lc {shlex.quote(_build_jetson_gateway_script(gateway, dns))}"


def build_jetson_time_sync_cmd(sudo_password: str) -> str:
    """生成在 Jetson 上通过 SSH 执行的时间同步命令。
    SSHRunner 已通过 _wrap_with_sudo_password 自动注入 sudo 密码，直接用 sudo 即可。
    sudo_password 参数保留以兼容调用方，不再使用。
    """
    script = r"""
set -e
if command -v timedatectl >/dev/null 2>&1; then
  timedatectl set-ntp true >/dev/null 2>&1 || true
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl restart systemd-timesyncd >/dev/null 2>&1 || true
fi

synced=""
if command -v timedatectl >/dev/null 2>&1; then
  for _ in 1 2 3 4 5; do
    synced="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || true)"
    [ "$synced" = "yes" ] && break
    sleep 1
  done
fi

date_now="$(date '+%Y-%m-%d %H:%M:%S %Z')"
if [ "$synced" = "yes" ]; then
  echo "time_sync=ok now=$date_now"
elif command -v timedatectl >/dev/null 2>&1; then
  tz="$(timedatectl show -p Timezone --value 2>/dev/null || echo unknown)"
  echo "time_sync=pending now=$date_now timezone=$tz"
else
  echo "time_sync=unknown now=$date_now"
fi
""".strip()
    return f"sudo bash -lc {shlex.quote(script)}"


def _build_jetson_gateway_script(gateway: str, dns: str = "8.8.8.8") -> str:
    gateway_q = shlex.quote(gateway)
    dns_q = shlex.quote(dns)
    return f"""
set -e
GW={gateway_q}
DNS_LIST={dns_q}
IFACE="$(ip -4 route get "$GW" 2>/dev/null | awk '{{for(i=1;i<=NF;i++) if($i=="dev") {{print $(i+1); exit}}}}')"
if [ -z "$IFACE" ]; then
  IFACE="$(ip -4 -o addr show | awk -v gw="$GW" '
    function same24(ip, gw, a, b) {{
      split(ip, a, ".");
      split(gw, b, ".");
      return a[1]==b[1] && a[2]==b[2] && a[3]==b[3];
    }}
    $4 ~ /^[0-9.]+\\/[0-9]+$/ {{
      split($4, parts, "/");
      if (same24(parts[1], gw)) {{
        print $2;
        exit;
      }}
    }}
  ')"
fi

ip route replace default via "$GW"

if command -v nmcli >/dev/null 2>&1 && [ -n "$IFACE" ]; then
  CON="$(nmcli -t -f NAME,DEVICE connection show --active | awk -F: -v dev="$IFACE" '$2==dev {{print $1; exit}}')"
  if [ -n "$CON" ]; then
    nmcli connection modify "$CON" \
      ipv4.gateway "$GW" \
      ipv4.ignore-auto-dns yes \
      ipv4.dns "$DNS_LIST" >/dev/null
    nmcli connection up "$CON" >/dev/null || nmcli device reapply "$IFACE" >/dev/null || true
  fi
fi

if command -v resolvectl >/dev/null 2>&1 && command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet systemd-resolved && [ -n "$IFACE" ]; then
  resolvectl dns "$IFACE" $DNS_LIST >/dev/null || true
  resolvectl domain "$IFACE" '~.' >/dev/null || true
  ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
else
  if [ -L /etc/resolv.conf ] && readlink /etc/resolv.conf | grep -q 'stub-resolv.conf'; then
    rm -f /etc/resolv.conf
  fi
  : > /etc/resolv.conf
  for dns in $DNS_LIST; do
    printf 'nameserver %s\\n' "$dns" >> /etc/resolv.conf
  done
fi

echo "gateway=$GW dns=$DNS_LIST iface=${{IFACE:-unknown}} configured"
""".strip()


# ── 代理检测与转发 ────────────────────────────────────────────────────────────

# 常见代理软件的默认端口（按优先级排序）
_PROXY_CANDIDATE_PORTS = [7890, 1080, 10808, 8080, 1087, 7891, 20171, 20172]


def detect_local_proxy() -> tuple[str, int] | None:
    """检测本机是否有代理端口在监听，返回 (host, port) 或 None。
    只检测 127.0.0.1，不检测 0.0.0.0（避免误判其他服务）。
    """
    import socket
    for port in _PROXY_CANDIDATE_PORTS:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return ("127.0.0.1", port)
        except OSError:
            continue
    return None


def build_jetson_proxy_cmd(proxy_host: str, proxy_port: int) -> str:
    """生成在 Jetson 上配置 http_proxy/https_proxy 的命令（写入 /etc/environment 持久化）。"""
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    return f"""
set -e
PROXY_URL={shlex.quote(proxy_url)}
ENV_FILE=/etc/environment

# 删除旧的代理配置行
sudo sed -i '/^http_proxy=/d;/^https_proxy=/d;/^HTTP_PROXY=/d;/^HTTPS_PROXY=/d;/^no_proxy=/d;/^NO_PROXY=/d' "$ENV_FILE" 2>/dev/null || true

# 写入新配置
printf 'http_proxy=%s\\nhttps_proxy=%s\\nHTTP_PROXY=%s\\nHTTPS_PROXY=%s\\nno_proxy=localhost,127.0.0.1\\nNO_PROXY=localhost,127.0.0.1\\n' \\
  "$PROXY_URL" "$PROXY_URL" "$PROXY_URL" "$PROXY_URL" | sudo tee -a "$ENV_FILE" >/dev/null

# 同时对当前 shell 生效（供后续命令使用）
export http_proxy="$PROXY_URL" https_proxy="$PROXY_URL" HTTP_PROXY="$PROXY_URL" HTTPS_PROXY="$PROXY_URL"
export no_proxy=localhost,127.0.0.1 NO_PROXY=localhost,127.0.0.1

echo "proxy_set=$PROXY_URL"
""".strip()


def build_jetson_clear_proxy_cmd() -> str:
    """生成在 Jetson 上清除代理配置的命令。"""
    return (
        "sudo sed -i '/^http_proxy=/d;/^https_proxy=/d;/^HTTP_PROXY=/d;"
        "/^HTTPS_PROXY=/d;/^no_proxy=/d;/^NO_PROXY=/d' /etc/environment 2>/dev/null || true; "
        "echo 'proxy_cleared'"
    )
