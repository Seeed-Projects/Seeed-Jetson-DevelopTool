"""Remote desktop helpers for x11vnc + noVNC deployment over SSH."""
from __future__ import annotations

import shutil
import subprocess
import sys
import webbrowser

from seeed_jetson_develop.core.runner import SSHRunner


CHECK_VNC_CMD = "which x11vnc 2>/dev/null || dpkg -l x11vnc 2>/dev/null | grep '^ii'"
CHECK_NOVNC_CMD = "which websockify 2>/dev/null || pip3 show websockify 2>/dev/null | grep -i name"
CHECK_VNC_RUNNING_CMD = "pgrep -a x11vnc 2>/dev/null"
CHECK_NOVNC_RUNNING_CMD = "pgrep -a websockify 2>/dev/null"
STOP_CMD = "pkill x11vnc 2>/dev/null; pkill websockify 2>/dev/null; echo 'stopped'"


def _escape_single_quotes(text: str) -> str:
    return text.replace("'", "'\\''")


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


def build_enable_autologin_cmd(sudo_password: str, username: str) -> str:
    escaped_pwd = _escape_single_quotes(sudo_password)
    escaped_user = _escape_single_quotes(username or "seeed")
    return (
        f"echo '{escaped_pwd}' | sudo -S bash -lc "
        f"'set -e; "
        f"TARGET_USER='\"'\"'{escaped_user}'\"'\"'; "
        "DM=\"\"; "
        "if command -v systemctl >/dev/null 2>&1; then "
        "  DM=$(basename \"$(readlink -f /etc/systemd/system/display-manager.service 2>/dev/null || true)\" 2>/dev/null || true); "
        "fi; "
        "if [ -z \"$DM\" ]; then "
        "  if dpkg -s gdm3 >/dev/null 2>&1; then DM=gdm3; "
        "  elif dpkg -s lightdm >/dev/null 2>&1; then DM=lightdm; "
        "  fi; "
        "fi; "
        "if [ \"$DM\" = \"gdm.service\" ] || [ \"$DM\" = \"gdm\" ]; then DM=gdm3; fi; "
        "echo \"Detected display manager: ${DM:-unknown}\"; "
        "if [ \"$DM\" = \"gdm3\" ]; then "
        "  mkdir -p /etc/gdm3; touch /etc/gdm3/custom.conf; "
        "  grep -q \"^\\[daemon\\]\" /etc/gdm3/custom.conf || printf \"\\n[daemon]\\n\" >> /etc/gdm3/custom.conf; "
        "  if grep -q \"^AutomaticLoginEnable=\" /etc/gdm3/custom.conf; then "
        "    sed -i \"s/^AutomaticLoginEnable=.*/AutomaticLoginEnable=true/\" /etc/gdm3/custom.conf; "
        "  else "
        "    sed -i \"/^\\[daemon\\]/a AutomaticLoginEnable=true\" /etc/gdm3/custom.conf; "
        "  fi; "
        "  if grep -q \"^AutomaticLogin=\" /etc/gdm3/custom.conf; then "
        "    sed -i \"s/^AutomaticLogin=.*/AutomaticLogin=$TARGET_USER/\" /etc/gdm3/custom.conf; "
        "  else "
        "    sed -i \"/^\\[daemon\\]/a AutomaticLogin=$TARGET_USER\" /etc/gdm3/custom.conf; "
        "  fi; "
        "elif [ \"$DM\" = \"lightdm\" ]; then "
        "  mkdir -p /etc/lightdm/lightdm.conf.d; "
        "  printf \"%s\n%s\n%s\n%s\n%s\n\" "
        "    \"[Seat:*]\" "
        "    \"autologin-user=$TARGET_USER\" "
        "    \"autologin-user-timeout=0\" "
        "    \"greeter-hide-users=false\" "
        "    \"greeter-show-manual-login=true\" "
        "    >/etc/lightdm/lightdm.conf.d/50-seeed-autologin.conf; "
        "else "
        "  echo \"Unsupported display manager for autologin: ${DM:-unknown}\"; "
        "  exit 0; "
        "fi; "
        "echo \"Autologin configured for $TARGET_USER\"'"
    )


def build_install_vnc_cmd(sudo_password: str) -> str:
    escaped = _escape_single_quotes(sudo_password)
    return (
        f"echo '{escaped}' | sudo -S apt-get update -qq "
        f"&& echo '{escaped}' | sudo -S apt-get install -y x11vnc xvfb xauth dbus-x11 x11-xserver-utils"
    )


def build_start_vnc_cmd(password: str = "", display: str = "") -> str:
    if password:
        auth = f"-passwd {password}"
    else:
        auth = "-nopw"
    escaped_auth = _escape_single_quotes(auth)
    escaped_display = _escape_single_quotes(display)
    return (
        "cat >/tmp/seeed-start-vnc.sh <<'EOF'\n"
        "#!/usr/bin/env bash\n"
        "set -e\n"
        "DISP=\"${DISPLAY:-}\"\n"
        "HEADLESS=0\n"
        "if [ -n \"$DISP\" ] && ! xdpyinfo -display \"$DISP\" >/dev/null 2>&1; then DISP=\"\"; fi\n"
        "if [ -z \"$DISP\" ]; then\n"
        "  for d in :0 :1 :2; do\n"
        "    if xdpyinfo -display \"$d\" >/dev/null 2>&1; then DISP=\"$d\"; break; fi\n"
        "  done\n"
        "fi\n"
        f"if [ -z \"$DISP\" ] && [ -n '{escaped_display}' ]; then DISP='{escaped_display}'; fi\n"
        "if [ -z \"$DISP\" ]; then\n"
        "  HEADLESS=1\n"
        "  DISP=:99\n"
        "  pkill -f \"Xvfb :99\" 2>/dev/null || true\n"
        "  rm -f /tmp/.X99-lock\n"
        "  nohup Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset </dev/null >/tmp/seeed-xvfb.log 2>&1 &\n"
        "  echo $! >/tmp/seeed-xvfb.pid\n"
        "  sleep 2\n"
        "  export DISPLAY=:99\n"
        "  export XDG_RUNTIME_DIR=/run/user/$(id -u)\n"
        "  export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus\n"
        "  : >/tmp/seeed-headless-desktop.log\n"
        "  if command -v xfwm4 >/dev/null 2>&1; then\n"
        "    nohup xfwm4 </dev/null >/tmp/seeed-headless-desktop.log 2>&1 &\n"
        "    echo $! >/tmp/seeed-headless-session.pid\n"
        "  elif command -v openbox >/dev/null 2>&1; then\n"
        "    nohup openbox </dev/null >/tmp/seeed-headless-desktop.log 2>&1 &\n"
        "    echo $! >/tmp/seeed-headless-session.pid\n"
        "  elif command -v fluxbox >/dev/null 2>&1; then\n"
        "    nohup fluxbox </dev/null >/tmp/seeed-headless-desktop.log 2>&1 &\n"
        "    echo $! >/tmp/seeed-headless-session.pid\n"
        "  fi\n"
        "  sleep 8\n"
        "fi\n"
        "echo \"Using display: $DISP (headless=$HEADLESS)\" >/tmp/seeed-vnc-bootstrap.log\n"
        "# 等待 X server 完全就绪\n"
        "for i in {1..10}; do\n"
        "  if xdpyinfo -display \"$DISP\" >/dev/null 2>&1; then break; fi\n"
        "  sleep 1\n"
        "done\n"
        "pkill x11vnc 2>/dev/null || true\n"
        "sleep 0.5\n"
        "if [ \"$HEADLESS\" = \"1\" ]; then X11_AUTH=\"\"; else X11_AUTH=\"-auth guess\"; fi\n"
        f"x11vnc $X11_AUTH -display \"$DISP\" -forever -shared -rfbport 5900 {escaped_auth} -noxdamage -noxfixes -o /tmp/x11vnc.log -bg >/tmp/seeed-vnc-launch.log 2>&1\n"
        "EOF\n"
        "chmod +x /tmp/seeed-start-vnc.sh\n"
        "nohup /tmp/seeed-start-vnc.sh </dev/null >/tmp/seeed-vnc-bootstrap.out 2>&1 &\n"
        "sleep 12\n"
        "if ss -tln 2>/dev/null | grep -q ':5900' || netstat -tln 2>/dev/null | grep -q ':5900'; then\n"
        "  echo 'x11vnc started OK on port 5900'\n"
        "else\n"
        "  echo 'x11vnc may have failed, check logs:'\n"
        "  tail -20 /tmp/x11vnc.log 2>/dev/null || true\n"
        "  tail -20 /tmp/seeed-headless-desktop.log 2>/dev/null || true\n"
        "  tail -20 /tmp/seeed-xvfb.log 2>/dev/null || true\n"
        "  exit 1\n"
        "fi"
    )


def build_install_novnc_cmd(sudo_password: str) -> str:
    escaped = _escape_single_quotes(sudo_password)
    return f"echo '{escaped}' | sudo -S apt-get install -y novnc websockify python3-websockify"


def build_start_novnc_cmd(vnc_port: int = 5900, web_port: int = 6080) -> str:
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
        + ' ; if [ -f /tmp/seeed-headless-session.pid ]; then kill "$(cat /tmp/seeed-headless-session.pid)" 2>/dev/null || true; rm -f /tmp/seeed-headless-session.pid; fi'
        + ' ; if [ -f /tmp/seeed-xvfb.pid ]; then kill "$(cat /tmp/seeed-xvfb.pid)" 2>/dev/null || true; rm -f /tmp/seeed-xvfb.pid; fi'
        + ' ; pkill -f "Xvfb :99" 2>/dev/null || true'
    )


def format_vnc_address(ip: str, port: int = 5900) -> str:
    return f"{ip}:{port}"


def format_novnc_url(ip: str, port: int = 6080) -> str:
    return f"http://{ip}:{port}/vnc.html"


def get_vnc_launch_cmd(ip: str, port: int = 5900) -> str | None:
    addr = f"{ip}:{port}"
    if sys.platform == "win32":
        return f"start vnc://{addr}"
    for cmd in ("vncviewer", "remmina", "xdg-open"):
        if shutil.which(cmd):
            if cmd == "remmina":
                return f"remmina -c vnc://{addr}"
            if cmd == "xdg-open":
                return f"xdg-open vnc://{addr}"
            return f"{cmd} {addr}"
    return None


def open_in_browser(url: str) -> None:
    webbrowser.open(url)


def launch_vnc_viewer(ip: str, port: int = 5900) -> bool:
    cmd = get_vnc_launch_cmd(ip, port)
    if not cmd:
        return False
    try:
        subprocess.Popen(cmd, shell=True)
        return True
    except Exception:
        return False
