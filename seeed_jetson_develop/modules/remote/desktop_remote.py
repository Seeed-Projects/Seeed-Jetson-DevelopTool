"""Remote desktop core logic for deploying/managing x11vnc + noVNC on Jetson."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
import webbrowser

from seeed_jetson_develop.core.runner import SSHRunner


CHECK_VNC_CMD = "which x11vnc 2>/dev/null || dpkg -l x11vnc 2>/dev/null | grep '^ii'"
CHECK_NOVNC_CMD = "which websockify 2>/dev/null || pip3 show websockify 2>/dev/null | grep -i name"
CHECK_VNC_RUNNING_CMD = "systemctl is-active seeed-x11vnc.service 2>/dev/null || pgrep -a x11vnc 2>/dev/null"
CHECK_NOVNC_RUNNING_CMD = (
    "systemctl is-active seeed-novnc.service 2>/dev/null || pgrep -a websockify 2>/dev/null"
)
STOP_CMD = (
    "sudo systemctl stop seeed-novnc.service seeed-x11vnc.service seeed-headless-session.service seeed-headless-xvfb.service 2>/dev/null || true; "
    "pkill x11vnc 2>/dev/null || true; "
    "pkill websockify 2>/dev/null || true; "
    "pkill -x Xvfb 2>/dev/null || true; "
    "echo 'stopped'"
)


def check_vnc_installed(runner: SSHRunner) -> bool:
    rc, out = runner.run(CHECK_VNC_CMD, timeout=10)
    return rc == 0 and bool(out.strip())


def check_novnc_installed(runner: SSHRunner) -> bool:
    rc, out = runner.run(CHECK_NOVNC_CMD, timeout=10)
    return rc == 0 and bool(out.strip())


def check_vnc_running(runner: SSHRunner) -> tuple[bool, str]:
    rc, out = runner.run(CHECK_VNC_RUNNING_CMD, timeout=8)
    if rc == 0 and out.strip():
        lines = out.strip().splitlines()
        if "active" in lines[0]:
            rc2, out2 = runner.run("pgrep -a x11vnc 2>/dev/null | head -n1", timeout=5)
            if rc2 == 0 and out2.strip():
                return True, out2.strip().split()[0]
            return True, "systemd"
        pid = lines[0].split()[0]
        return True, pid
    return False, ""


def check_novnc_running(runner: SSHRunner) -> tuple[bool, str]:
    rc, out = runner.run(CHECK_NOVNC_RUNNING_CMD, timeout=8)
    if rc == 0 and out.strip():
        lines = out.strip().splitlines()
        if "active" in lines[0]:
            rc2, out2 = runner.run("pgrep -a websockify 2>/dev/null | head -n1", timeout=5)
            if rc2 == 0 and out2.strip():
                return True, out2.strip().split()[0]
            return True, "systemd"
        pid = lines[0].split()[0]
        return True, pid
    return False, ""


def build_install_vnc_cmd(sudo_password: str) -> str:
    escaped = sudo_password.replace("'", "'\\''")
    return (
        f"echo '{escaped}' | sudo -S apt-get update && "
        f"echo '{escaped}' | sudo -S apt-get install -y "
        "x11vnc xvfb xauth dbus-x11 x11-xserver-utils novnc websockify python3-websockify openbox xterm xfce4 xfce4-terminal"
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
        'grep -q "^\\[daemon\\]" "$CONF" || '
        f"printf '\\n[daemon]\\n' | (echo '{escaped_pwd}' | sudo -S tee -a \"$CONF\" >/dev/null); "
        'grep -q "^AutomaticLoginEnable=" "$CONF" && '
        f"(echo '{escaped_pwd}' | sudo -S sed -i 's/^AutomaticLoginEnable=.*/AutomaticLoginEnable=true/' \"$CONF\") || "
        f"(echo '{escaped_pwd}' | sudo -S sed -i '/^\\[daemon\\]/a AutomaticLoginEnable=true' \"$CONF\"); "
        'grep -q "^AutomaticLogin=" "$CONF" && '
        f"(echo '{escaped_pwd}' | sudo -S sed -i \"s/^AutomaticLogin=.*/AutomaticLogin={escaped_user}/\" \"$CONF\") || "
        f"(echo '{escaped_pwd}' | sudo -S sed -i '/^\\[daemon\\]/a AutomaticLogin={escaped_user}' \"$CONF\"); "
        'echo "auto-login ensured in $CONF"'
    )


def build_start_vnc_cmd(password: str = "", display: str = "", sudo_password: str = "") -> str:
    """Create and start persistent systemd services for headless-friendly VNC/noVNC."""
    if not password:
        # keep behavior explicit: no anonymous VNC session
        return "echo '[error] VNC password is required for secure mode'; exit 2"

    escaped_pwd = sudo_password.replace("'", "'\\''")
    escaped_vnc = password.replace("'", "'\\''")
    display_hint = (display or "").replace('"', "").replace("'", "")

    xvfb_service = (
        "[Unit]\n"
        "Description=Seeed Headless Xvfb\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        "User=$USER_NAME\n"
        "Environment=HOME=$HOME_DIR\n"
        "ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac\n"
        "Restart=always\n"
        "RestartSec=2\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    x11vnc_service = (
        "[Unit]\n"
        "Description=Seeed x11vnc server\n"
        "After=display-manager.service seeed-headless-xvfb.service seeed-headless-session.service\n"
        "Wants=seeed-headless-xvfb.service seeed-headless-session.service\n\n"
        "[Service]\n"
        "Type=simple\n"
        "User=$USER_NAME\n"
        "Environment=HOME=$HOME_DIR\n"
        f"Environment=DISPLAY_HINT={display_hint}\n"
        "ExecStart=/bin/bash -lc 'set -e; DISP=\"$DISPLAY_HINT\"; if [ -n \"$DISP\" ] && ! xdpyinfo -display \"$DISP\" >/dev/null 2>&1; then DISP=\"\"; fi; if [ -z \"$DISP\" ]; then for d in :99 :1 :2 :0; do if xdpyinfo -display \"$d\" >/dev/null 2>&1; then DISP=$d; break; fi; done; fi; [ -n \"$DISP\" ] || DISP=:99; XAUTH=\"\"; for p in /run/user/1000/gdm/Xauthority \"$HOME/.Xauthority\"; do [ -f \"$p\" ] && XAUTH=$p && break; done; if [ -n \"$XAUTH\" ]; then AUTH_ARG=\"-auth $XAUTH\"; else AUTH_ARG=\"-auth guess\"; fi; exec /usr/bin/x11vnc $AUTH_ARG -display \"$DISP\" -forever -shared -rfbport 5900 -rfbauth \"$HOME/.vnc/passwd\" -noxdamage -noxfixes -nowf -nowcr -noscr -o /tmp/x11vnc.log'\n"
        "Restart=always\n"
        "RestartSec=2\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    session_service = (
        "[Unit]\n"
        "Description=Seeed Headless Desktop Session on :99\n"
        "After=seeed-headless-xvfb.service\n"
        "Wants=seeed-headless-xvfb.service\n\n"
        "[Service]\n"
        "Type=simple\n"
        "User=$USER_NAME\n"
        "Environment=HOME=$HOME_DIR\n"
        "Environment=DISPLAY=:99\n"
        "ExecStart=/bin/bash -lc 'set -e; export DISPLAY=:99; export XDG_RUNTIME_DIR=/run/user/1000; if command -v startxfce4 >/dev/null 2>&1; then dbus-launch --exit-with-session startxfce4; elif command -v openbox >/dev/null 2>&1; then dbus-launch --exit-with-session openbox; else xterm -geometry 120x40+20+20; fi'\n"
        "Restart=always\n"
        "RestartSec=2\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    novnc_service = (
        "[Unit]\n"
        "Description=Seeed noVNC websockify\n"
        "After=network.target seeed-x11vnc.service\n"
        "Wants=seeed-x11vnc.service\n\n"
        "[Service]\n"
        "Type=simple\n"
        "ExecStart=/usr/bin/websockify --web=/usr/share/novnc 6080 localhost:5900\n"
        "Restart=always\n"
        "RestartSec=2\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    b64_xvfb = base64.b64encode(xvfb_service.encode("utf-8")).decode("ascii")
    b64_x11vnc = base64.b64encode(x11vnc_service.encode("utf-8")).decode("ascii")
    b64_session = base64.b64encode(session_service.encode("utf-8")).decode("ascii")
    b64_novnc = base64.b64encode(novnc_service.encode("utf-8")).decode("ascii")

    return (
        "set -e; "
        f"VNC_PASS='{escaped_vnc}'; "
        f"SUDO_PASS='{escaped_pwd}'; "
        'USER_NAME="$(id -un)"; '
        'HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"; '
        'mkdir -p "$HOME_DIR/.vnc"; '
        'x11vnc -storepasswd "$VNC_PASS" "$HOME_DIR/.vnc/passwd" >/dev/null; '
        'chmod 600 "$HOME_DIR/.vnc/passwd"; '
        'chown "$USER_NAME":"$USER_NAME" "$HOME_DIR/.vnc/passwd"; '
        f"echo '{b64_xvfb}' | base64 -d > /tmp/seeed-headless-xvfb.service; "
        f"echo '{b64_x11vnc}' | base64 -d > /tmp/seeed-x11vnc.service; "
        f"echo '{b64_session}' | base64 -d > /tmp/seeed-headless-session.service; "
        f"echo '{b64_novnc}' | base64 -d > /tmp/seeed-novnc.service; "
        'echo "$SUDO_PASS" | sudo -S systemctl stop seeed-novnc.service seeed-x11vnc.service seeed-headless-session.service seeed-headless-xvfb.service 2>/dev/null || true; '
        "pkill x11vnc 2>/dev/null || true; "
        "pkill websockify 2>/dev/null || true; "
        "pkill -x Xvfb 2>/dev/null || true; "
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-headless-xvfb.service /etc/systemd/system/seeed-headless-xvfb.service; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-headless-session.service /etc/systemd/system/seeed-headless-session.service; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-x11vnc.service /etc/systemd/system/seeed-x11vnc.service; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-novnc.service /etc/systemd/system/seeed-novnc.service; '
        'echo "$SUDO_PASS" | sudo -S systemctl daemon-reload; '
        'echo "$SUDO_PASS" | sudo -S systemctl enable --now seeed-headless-xvfb.service seeed-headless-session.service seeed-x11vnc.service seeed-novnc.service; '
        'echo "$SUDO_PASS" | sudo -S systemctl restart seeed-headless-session.service seeed-x11vnc.service seeed-novnc.service; '
        'sleep 2; '
        'echo "$SUDO_PASS" | sudo -S systemctl --no-pager --full status seeed-headless-session.service seeed-x11vnc.service seeed-novnc.service | sed -n "1,60p"; '
        'if ss -tlnp 2>/dev/null | grep -q ":5900" && ss -tlnp 2>/dev/null | grep -q ":6080"; then '
        "  echo 'x11vnc/noVNC started OK on 5900/6080'; "
        "else "
        "  echo 'service started but port check failed'; "
        "  exit 1; "
        "fi"
    )


def build_install_novnc_cmd(sudo_password: str) -> str:
    escaped = sudo_password.replace("'", "'\\''")
    return f"echo '{escaped}' | sudo -S apt-get install -y novnc websockify python3-websockify"


def build_prepare_vnc_password_cmd(password: str) -> str:
    escaped = password.replace("'", "'\\''")
    return (
        "set -e; "
        f"VNC_PASS='{escaped}'; "
        "mkdir -p ~/.vnc; "
        'x11vnc -storepasswd "$VNC_PASS" ~/.vnc/passwd >/dev/null; '
        "chmod 600 ~/.vnc/passwd; "
        "echo 'vnc password prepared'"
    )


def build_write_headless_xvfb_unit_cmd(username: str) -> str:
    user = username.replace("'", "")
    return (
        "cat > /tmp/seeed-headless-xvfb.service <<'EOF'\n"
        "[Unit]\n"
        "Description=Seeed Headless Xvfb\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"User={user}\n"
        f"Environment=HOME=/home/{user}\n"
        "ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac\n"
        "Restart=always\n"
        "RestartSec=2\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
        "EOF"
    )


def build_write_headless_session_unit_cmd(username: str) -> str:
    user = username.replace("'", "")
    return (
        "cat > /tmp/seeed-headless-session.service <<'EOF'\n"
        "[Unit]\n"
        "Description=Seeed Headless Desktop Session on :99\n"
        "After=seeed-headless-xvfb.service\n"
        "Wants=seeed-headless-xvfb.service\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"User={user}\n"
        f"Environment=HOME=/home/{user}\n"
        "Environment=DISPLAY=:99\n"
        "ExecStart=/bin/bash -lc 'set -e; export DISPLAY=:99; export XDG_RUNTIME_DIR=/run/user/1000; if command -v startxfce4 >/dev/null 2>&1; then dbus-launch --exit-with-session startxfce4; elif command -v openbox >/dev/null 2>&1; then dbus-launch --exit-with-session openbox; else xterm -geometry 120x40+20+20; fi'\n"
        "Restart=always\n"
        "RestartSec=2\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
        "EOF"
    )


def build_write_x11vnc_unit_cmd(username: str, display: str = "") -> str:
    user = username.replace("'", "")
    display_hint = (display or "").replace('"', "").replace("'", "")
    return (
        "cat > /tmp/seeed-x11vnc.service <<'EOF'\n"
        "[Unit]\n"
        "Description=Seeed x11vnc server\n"
        "After=display-manager.service seeed-headless-xvfb.service seeed-headless-session.service\n"
        "Wants=seeed-headless-xvfb.service seeed-headless-session.service\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"User={user}\n"
        f"Environment=HOME=/home/{user}\n"
        f"Environment=DISPLAY_HINT={display_hint}\n"
        "ExecStart=/bin/bash -lc 'set -e; DISP=\"$DISPLAY_HINT\"; if [ -n \"$DISP\" ] && ! xdpyinfo -display \"$DISP\" >/dev/null 2>&1; then DISP=\"\"; fi; if [ -z \"$DISP\" ]; then for d in :99 :1 :2 :0; do if xdpyinfo -display \"$d\" >/dev/null 2>&1; then DISP=$d; break; fi; done; fi; [ -n \"$DISP\" ] || DISP=:99; XAUTH=\"\"; for p in /run/user/1000/gdm/Xauthority \"$HOME/.Xauthority\"; do [ -f \"$p\" ] && XAUTH=$p && break; done; if [ -n \"$XAUTH\" ]; then AUTH_ARG=\"-auth $XAUTH\"; else AUTH_ARG=\"-auth guess\"; fi; exec /usr/bin/x11vnc $AUTH_ARG -display \"$DISP\" -forever -shared -rfbport 5900 -rfbauth \"$HOME/.vnc/passwd\" -noxdamage -noxfixes -nowf -nowcr -noscr -o /tmp/x11vnc.log'\n"
        "Restart=always\n"
        "RestartSec=2\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
        "EOF"
    )


def build_write_novnc_unit_cmd() -> str:
    return (
        "cat > /tmp/seeed-novnc.service <<'EOF'\n"
        "[Unit]\n"
        "Description=Seeed noVNC websockify\n"
        "After=network.target seeed-x11vnc.service\n"
        "Wants=seeed-x11vnc.service\n\n"
        "[Service]\n"
        "Type=simple\n"
        "ExecStart=/usr/bin/websockify --web=/usr/share/novnc 6080 localhost:5900\n"
        "Restart=always\n"
        "RestartSec=2\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
        "EOF"
    )


def build_install_enable_units_cmd(sudo_password: str) -> str:
    escaped = sudo_password.replace("'", "'\\''")
    return (
        "set -e; "
        f"SUDO_PASS='{escaped}'; "
        'echo "$SUDO_PASS" | sudo -S systemctl stop seeed-novnc.service seeed-x11vnc.service seeed-headless-session.service seeed-headless-xvfb.service 2>/dev/null || true; '
        "pkill x11vnc 2>/dev/null || true; "
        "pkill websockify 2>/dev/null || true; "
        "pkill -x Xvfb 2>/dev/null || true; "
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-headless-xvfb.service /etc/systemd/system/seeed-headless-xvfb.service; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-headless-session.service /etc/systemd/system/seeed-headless-session.service; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-x11vnc.service /etc/systemd/system/seeed-x11vnc.service; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-novnc.service /etc/systemd/system/seeed-novnc.service; '
        'echo "$SUDO_PASS" | sudo -S systemctl daemon-reload; '
        'echo "$SUDO_PASS" | sudo -S systemctl enable --now seeed-headless-xvfb.service seeed-headless-session.service seeed-x11vnc.service seeed-novnc.service; '
        'echo "$SUDO_PASS" | sudo -S systemctl restart seeed-headless-session.service seeed-x11vnc.service seeed-novnc.service; '
        "sleep 2; "
        "ss -tlnp | grep -E ':5900|:6080' >/dev/null; "
        "echo 'vnc/novnc services started'"
    )


def build_start_novnc_cmd(vnc_port: int = 5900, web_port: int = 6080) -> str:
    # noVNC is started by systemd in secure mode; keep compatibility for legacy button flow.
    return (
        "set -e; "
        "if systemctl list-unit-files 2>/dev/null | grep -q '^seeed-novnc.service'; then "
        "  sudo systemctl restart seeed-novnc.service >/dev/null 2>&1 || true; "
        f"  echo 'noVNC ensured by systemd on port {web_port}'; "
        "else "
        f"  pkill websockify 2>/dev/null; sleep 0.3; websockify --web=/usr/share/novnc {web_port} localhost:{vnc_port} --daemon 2>&1; "
        f"  echo 'noVNC started on port {web_port}'; "
        "fi"
    )


def build_stop_cmd() -> str:
    return (
        STOP_CMD
        + "; "
        + "sudo systemctl disable seeed-novnc.service seeed-x11vnc.service seeed-headless-session.service seeed-headless-xvfb.service 2>/dev/null || true"
    )


def build_diagnose_cmd() -> str:
    return (
        "set -e; "
        "echo '== systemd services =='; "
        "sudo systemctl --no-pager --full status seeed-headless-xvfb.service seeed-headless-session.service seeed-x11vnc.service seeed-novnc.service || true; "
        "echo '== display/xauth =='; "
        "echo DISPLAY=${DISPLAY:-}; "
        "echo XAUTHORITY=${XAUTHORITY:-}; "
        "ls -l /run/user/1000/gdm/Xauthority ~/.Xauthority 2>/dev/null || true; "
        "echo '== listening ports =='; "
        "ss -tlnp 2>/dev/null | grep -E ':5900|:6080' || true; "
        "echo '== tail x11vnc log =='; "
        "tail -n 80 /tmp/x11vnc.log 2>/dev/null || true"
    )


def build_rollback_cmd(sudo_password: str) -> str:
    escaped = sudo_password.replace("'", "'\\''")
    return (
        f"echo '{escaped}' | sudo -S systemctl stop seeed-novnc.service seeed-x11vnc.service seeed-headless-session.service seeed-headless-xvfb.service 2>/dev/null || true; "
        f"echo '{escaped}' | sudo -S systemctl disable seeed-novnc.service seeed-x11vnc.service seeed-headless-session.service seeed-headless-xvfb.service 2>/dev/null || true; "
        f"echo '{escaped}' | sudo -S rm -f /etc/systemd/system/seeed-headless-xvfb.service /etc/systemd/system/seeed-headless-session.service /etc/systemd/system/seeed-x11vnc.service /etc/systemd/system/seeed-novnc.service; "
        f"echo '{escaped}' | sudo -S systemctl daemon-reload; "
        "pkill x11vnc 2>/dev/null || true; pkill websockify 2>/dev/null || true; pkill -x Xvfb 2>/dev/null || true; "
        "echo 'rollback done'"
    )


def format_vnc_address(ip: str, port: int = 5900) -> str:
    return f"{ip}:{port}"


def format_novnc_url(ip: str, port: int = 6080) -> str:
    return f"http://{ip}:{port}/vnc.html"


def get_vnc_launch_cmd(ip: str, port: int = 5900) -> str | None:
    """Get OS-specific launch command for installed VNC viewer."""
    addr = f"{ip}:{port}"
    if sys.platform == "win32":
        roots = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ]
        candidates = [
            r"RealVNC\VNC Viewer\VNCViewer.exe",
            r"TigerVNC\vncviewer.exe",
            r"TightVNC\tvnviewer.exe",
            r"UltraVNC\vncviewer.exe",
        ]
        for rel in candidates:
            for root in roots:
                if not root:
                    continue
                exe = os.path.join(root, rel)
                if os.path.exists(exe):
                    return f'"{exe}" {addr}'
        return f'cmd /c start "" "vnc://{addr}"'

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
    """Launch local VNC viewer if found."""
    cmd = get_vnc_launch_cmd(ip, port)
    if not cmd:
        return False
    try:
        proc = subprocess.Popen(cmd, shell=True)
        try:
            rc = proc.wait(timeout=1.2)
            if rc not in (0, None):
                return False
        except Exception:
            pass
        return True
    except Exception:
        return False
