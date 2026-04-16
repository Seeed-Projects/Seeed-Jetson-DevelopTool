"""远程桌面核心逻辑 — 通过 SSH 在 Jetson 上部署/管理 x11vnc + noVNC。

客户端做控制面，Jetson 做服务面。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import webbrowser

from seeed_jetson_develop.core.runner import SSHRunner


# ── SSH 命令模板 ──────────────────────────────────────────────────────────────

CHECK_VNC_CMD = "which x11vnc 2>/dev/null || dpkg -l x11vnc 2>/dev/null | grep '^ii'"
CHECK_NOVNC_CMD = "which websockify 2>/dev/null || pip3 show websockify 2>/dev/null | grep -i name"
CHECK_VNC_RUNNING_CMD = "pgrep -a x11vnc 2>/dev/null"
CHECK_NOVNC_RUNNING_CMD = "pgrep -a websockify 2>/dev/null"
STOP_CMD = "pkill x11vnc 2>/dev/null; pkill websockify 2>/dev/null; echo 'stopped'"


# ── 状态检测 ──────────────────────────────────────────────────────────────────

def check_vnc_installed(runner: SSHRunner) -> bool:
    rc, out = runner.run(CHECK_VNC_CMD, timeout=10)
    return rc == 0 and bool(out.strip())


def check_novnc_installed(runner: SSHRunner) -> bool:
    rc, out = runner.run(CHECK_NOVNC_CMD, timeout=10)
    return rc == 0 and bool(out.strip())


def check_vnc_running(runner: SSHRunner) -> tuple[bool, str]:
    rc, out = runner.run(CHECK_VNC_RUNNING_CMD, timeout=5)
    if rc == 0 and out.strip():
        pid = out.strip().splitlines()[0].split()[0]
        return True, pid
    return False, ""


def check_novnc_running(runner: SSHRunner) -> tuple[bool, str]:
    rc, out = runner.run(CHECK_NOVNC_RUNNING_CMD, timeout=5)
    if rc == 0 and out.strip():
        pid = out.strip().splitlines()[0].split()[0]
        return True, pid
    return False, ""


# ── 命令生成 ──────────────────────────────────────────────────────────────────

def build_install_vnc_cmd(sudo_password: str) -> str:
    escaped = sudo_password.replace("'", "'\\''")
    return (
        f"echo '{escaped}' | sudo -S apt-get update -qq "
        f"&& echo '{escaped}' | sudo -S apt-get install -y x11vnc xvfb xauth dbus-x11 x11-xserver-utils"
    )


def build_enable_autologin_cmd(sudo_password: str, username: str) -> str:
    escaped_pwd = sudo_password.replace("'", "'\\''")
    escaped_user = username.replace("'", "'\\''")
    return (
        # 1. 找配置文件路径
        'CONF=""; '
        'for f in /etc/gdm3/custom.conf /etc/gdm/custom.conf; do '
        '  [ -f "$f" ] && CONF="$f" && break; '
        'done; '
        '[ -z "$CONF" ] && CONF=/etc/gdm3/custom.conf; '
        f"echo '{escaped_pwd}' | sudo -S mkdir -p \"$(dirname \"$CONF\")\" 2>/dev/null; "
        f"echo '{escaped_pwd}' | sudo -S touch \"$CONF\"; "
        # 2. 把当前配置读出来，用 python3 修改后写回（通过 tee，避免 sed 的 &&/|| 优先级 bug）
        "CONF_CONTENT=$(cat \"$CONF\" 2>/dev/null || echo ''); "
        "NEW_CONTENT=$(echo \"$CONF_CONTENT\" | python3 -c \""
        "import sys, re; "
        "txt = sys.stdin.read(); "
        "if '[daemon]' not in txt: txt = '[daemon]\\n' + txt; "
        "txt = re.sub(r'(?m)^AutomaticLoginEnable=.*', 'AutomaticLoginEnable=true', txt); "
        "txt = txt if 'AutomaticLoginEnable=' in txt else txt.replace('[daemon]', '[daemon]\\nAutomaticLoginEnable=true'); "
        f"txt = re.sub(r'(?m)^AutomaticLogin=.*', 'AutomaticLogin={escaped_user}', txt); "
        f"txt = txt if 'AutomaticLogin=' in txt else txt.replace('[daemon]', '[daemon]\\nAutomaticLogin={escaped_user}'); "
        "sys.stdout.write(txt)"
        "\"); "
        "echo \"$NEW_CONTENT\" | "
        f"(echo '{escaped_pwd}' | sudo -S tee \"$CONF\" >/dev/null); "
        "echo \"autologin config written to $CONF\"; "
        "cat \"$CONF\"; "
        # 3. 重启 display manager 让配置立即生效
        f"echo '{escaped_pwd}' | sudo -S systemctl restart gdm3 2>/dev/null "
        f"|| echo '{escaped_pwd}' | sudo -S systemctl restart gdm 2>/dev/null "
        f"|| echo '{escaped_pwd}' | sudo -S systemctl restart lightdm 2>/dev/null "
        "|| echo 'display manager restart skipped'; "
        "sleep 6; "
        "echo 'autologin setup done'"
    )


def build_start_vnc_cmd(password: str = "", display: str = "") -> str:
    """启动 x11vnc，始终以无密码模式运行。"""
    # 为了保证客户端和 noVNC 都不再弹出 VNC 密码，这里强制使用 -nopw。
    # password/display 参数保留仅用于兼容旧调用方。
    auth = "-nopw"
    # 自动探测 display：有真实桌面就接真实桌面；没有则启动 Xvfb :99 作为 headless 桌面
    detect_display = (
        # 等待最多 20 秒让 GDM 自动登录后的桌面 session 就绪
        'DISP=""; '
        'for i in $(seq 1 10); do '
        '  for d in :0 :1 :2; do '
        '    if xdpyinfo -display "$d" >/dev/null 2>&1; then DISP=$d; break 2; fi; '
        '  done; '
        '  sleep 2; '
        'done; '
        'HEADLESS=0; '
        'if [ -z "$DISP" ]; then '
        '  HEADLESS=1; DISP=:99; '
        '  pkill -f "Xvfb :99" 2>/dev/null || true; '
        '  rm -f /tmp/.X99-lock; '
        '  nohup Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset >/tmp/seeed-xvfb.log 2>&1 & '
        '  echo $! >/tmp/seeed-xvfb.pid; '
        '  sleep 2; '
        '  export DISPLAY=:99; '
        '  if command -v gnome-session >/dev/null 2>&1; then '
        '    nohup dbus-launch --exit-with-session gnome-session >/tmp/seeed-headless-desktop.log 2>&1 & '
        '    echo $! >/tmp/seeed-headless-session.pid; '
        '  elif command -v startxfce4 >/dev/null 2>&1; then '
        '    nohup dbus-launch --exit-with-session startxfce4 >/tmp/seeed-headless-desktop.log 2>&1 & '
        '    echo $! >/tmp/seeed-headless-session.pid; '
        '  elif command -v openbox-session >/dev/null 2>&1; then '
        '    nohup openbox-session >/tmp/seeed-headless-desktop.log 2>&1 & '
        '    echo $! >/tmp/seeed-headless-session.pid; '
        '  fi; '
        '  sleep 3; '
        'fi; '
        'echo "Using display: $DISP (headless=$HEADLESS)"; '
    )
    start_vnc = (
        f'pkill x11vnc 2>/dev/null; sleep 0.5; '
        # 删除所有可能的 x11vnc 密码文件，确保无密码模式
        'rm -f ~/.vnc/passwd ~/.x11vncrc /tmp/.x11vnc-passwd 2>/dev/null; '
        f'if [ "$HEADLESS" = "1" ]; then X11_AUTH=""; else X11_AUTH="-auth guess"; fi; '
        f'x11vnc $X11_AUTH -display $DISP -forever -shared -rfbport 5900 {auth} '
        f'-noxdamage -noxfixes -nowf -nowcr -noscr -o /tmp/x11vnc.log -bg 2>&1; '
        f'sleep 2; '
        f'if ss -tlnp 2>/dev/null | grep -q ":5900" || netstat -tlnp 2>/dev/null | grep -q ":5900"; then '
        f'  echo "x11vnc started OK on port 5900"; '
        f'else '
        f'  echo "x11vnc may have failed, check /tmp/x11vnc.log:"; '
        f'  tail -20 /tmp/x11vnc.log 2>/dev/null || echo "(no log)"; '
        f'  exit 1; '
        f'fi'
    )
    return detect_display + start_vnc


def build_install_novnc_cmd(sudo_password: str) -> str:
    escaped = sudo_password.replace("'", "'\\''")
    return (
        f"echo '{escaped}' | sudo -S apt-get install -y novnc websockify python3-websockify"
    )


def build_start_novnc_cmd(vnc_port: int = 5900, web_port: int = 6080) -> str:
    # 探测 novnc web 目录
    return (
        f'pkill websockify 2>/dev/null; sleep 0.3; '
        f'NOVNC_DIR=""; '
        f'for d in /usr/share/novnc /usr/local/share/novnc /opt/novnc; do '
        f'  if [ -f "$d/vnc.html" ] || [ -f "$d/index.html" ]; then NOVNC_DIR=$d; break; fi; '
        f'done; '
        f'if [ -n "$NOVNC_DIR" ]; then '
        f'  websockify --web="$NOVNC_DIR" {web_port} localhost:{vnc_port} --daemon 2>&1; '
        f'else '
        f'  websockify {web_port} localhost:{vnc_port} --daemon 2>&1; '
        f'fi; '
        f'sleep 2; '
        f'if ss -tlnp 2>/dev/null | grep -q ":{web_port}" || netstat -tlnp 2>/dev/null | grep -q ":{web_port}"; then '
        f'  echo "noVNC started OK on port {web_port}"; '
        f'else '
        f'  echo "websockify may have failed"; exit 1; '
        f'fi'
    )


def build_stop_cmd() -> str:
    return (
        STOP_CMD
        + ' ; '
        + 'rm -f ~/.vnc/passwd 2>/dev/null'
        + ' ; '
        + 'if [ -f /tmp/seeed-headless-session.pid ]; then kill "$(cat /tmp/seeed-headless-session.pid)" 2>/dev/null || true; rm -f /tmp/seeed-headless-session.pid; fi'
        + ' ; '
        + 'if [ -f /tmp/seeed-xvfb.pid ]; then kill "$(cat /tmp/seeed-xvfb.pid)" 2>/dev/null || true; rm -f /tmp/seeed-xvfb.pid; fi'
        + ' ; '
        + 'pkill -f "Xvfb :99" 2>/dev/null || true'
    )


# ── 地址格式化 ────────────────────────────────────────────────────────────────

def format_vnc_address(ip: str, port: int = 5900) -> str:
    return f"{ip}:{port}"


def format_novnc_url(ip: str, port: int = 6080) -> str:
    return f"http://{ip}:{port}/vnc.html"


# ── 平台工具 ──────────────────────────────────────────────────────────────────

def get_vnc_launch_cmd(ip: str, port: int = 5900) -> str | None:
    """返回当前平台打开 VNC 客户端的命令，找不到返回 None。"""
    addr = f"{ip}:{port}"
    if sys.platform == "win32":
        # Windows: 尝试 vnc:// 协议
        return f'start vnc://{addr}'
    # Linux: 尝试已知 VNC 客户端
    for cmd in ("vncviewer", "remmina", "xdg-open"):
        if shutil.which(cmd):
            if cmd == "remmina":
                return f'remmina -c vnc://{addr}'
            if cmd == "xdg-open":
                return f'xdg-open vnc://{addr}'
            return f'{cmd} {addr}'
    return None


def open_in_browser(url: str) -> None:
    webbrowser.open(url)


def launch_vnc_viewer(ip: str, port: int = 5900) -> bool:
    """尝试启动 VNC 客户端，成功返回 True。"""
    cmd = get_vnc_launch_cmd(ip, port)
    if not cmd:
        return False
    try:
        subprocess.Popen(cmd, shell=True)
        return True
    except Exception:
        return False
