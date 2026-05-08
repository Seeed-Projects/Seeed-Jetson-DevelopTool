"""Remote desktop core logic for deploying/managing x11vnc + noVNC on Jetson."""

from __future__ import annotations

import os
import textwrap
import shutil
import subprocess
import sys
import webbrowser

from seeed_jetson_develop.core.runner import SSHRunner


CHECK_VNC_CMD = "which x11vnc 2>/dev/null || dpkg -l x11vnc 2>/dev/null | grep '^ii'"
CHECK_NOVNC_CMD = "which websockify 2>/dev/null || pip3 show websockify 2>/dev/null | grep -i name"
CHECK_VNC_RUNNING_CMD = (
    "ss -tlnp 2>/dev/null | grep -q ':5900' && "
    "(pgrep -a x11vnc 2>/dev/null | head -n1 || echo systemd)"
)
CHECK_NOVNC_RUNNING_CMD = (
    "ss -tlnp 2>/dev/null | grep -q ':6080' && "
    "(pgrep -a websockify 2>/dev/null | head -n1 || echo systemd)"
)

# Installed to /usr/local/bin/seeed-x11vnc-launch.sh — picks DISPLAY from policy.
# NVIDIA's real :0 framebuffer can freeze after HDMI hot-unplug. Keep auto
# mode on the virtual :99 desktop so terminal control survives headless use.
SEED_X11VNC_LAUNCHER_SH = textwrap.dedent(
    r"""#!/bin/bash
set -euo pipefail
POLICY="${SEED_VNC_POLICY:-${SEeed_VNC_POLICY:-auto}}"
HINT="${DISPLAY_HINT:-}"
LOG=/tmp/x11vnc.log
LAUNCH_LOG=/tmp/seeed-x11vnc-launch.log
umask 022
{
  echo "---- $(date -Iseconds) ----"
  echo "launcher starting policy=$POLICY hint=${HINT:-}"
} >>"$LAUNCH_LOG" 2>&1 || true

_drm_any_connected() {
  local f
  for f in /sys/class/drm/*/status; do
    [ -f "$f" ] || continue
    if grep -qiw connected "$f" 2>/dev/null; then
      return 0
    fi
  done
  return 1
}

_disp_ok() {
  local d="$1" n="${d#:}"
  xdpyinfo -display "$d" >/dev/null 2>&1 || [ -S "/tmp/.X11-unix/X$n" ]
}

# Wait up to 30 s for a display socket to appear (avoids race with Xvfb startup).
_wait_disp() {
  local n="${1#:}" _wi
  _wi=0
  while [ $_wi -lt 30 ]; do
    [ -S "/tmp/.X11-unix/X$n" ] && return 0
    _wi=$((_wi+1))
    sleep 1
  done
  return 1
}

_resolve_auth() {
  local DISP="$1"
  AUTH_ARG="-auth guess"
  AUTH_FILE=""
  if [ "$DISP" = ":99" ]; then
    # Xvfb :99 is started with -ac. Do not pass -auth here; stale or
    # unreadable Xauthority files are the most common cause of headless VNC
    # deployment failures.
    AUTH_ARG=""
    AUTH_FILE="disabled-for-xvfb"
    printf '%s\n' "$AUTH_ARG" "$AUTH_FILE"
    return
  fi
  local p
  for p in /run/user/*/gdm/Xauthority /run/user/*/Xauthority \
      /var/run/gdm3/auth-for-*/database /var/lib/gdm3/.Xauthority \
      /var/lib/gdm/.Xauthority "$HOME/.Xauthority"; do
    [ -f "$p" ] || continue
    if XAUTHORITY="$p" xdpyinfo -display "$DISP" >/dev/null 2>&1; then
      AUTH_FILE="$p"
      AUTH_ARG="-auth $AUTH_FILE"
      printf '%s\n' "$AUTH_ARG" "$AUTH_FILE"
      return
    fi
  done
  while IFS= read -r p; do
    [ -f "$p" ] || continue
    if XAUTHORITY="$p" xdpyinfo -display "$DISP" >/dev/null 2>&1; then
      AUTH_FILE="$p"
      AUTH_ARG="-auth $AUTH_FILE"
      printf '%s\n' "$AUTH_ARG" "$AUTH_FILE"
      return
    fi
  done < <(find /run/user /var/run/gdm3 /var/lib/gdm3 /tmp -maxdepth 5 \
      \( -name Xauthority -o -name database \) 2>/dev/null)
  printf '%s\n' "$AUTH_ARG" "$AUTH_FILE"
}

_pick_first() {
  local d DISP=""
  for d in "$@"; do
    [ -n "$d" ] || continue
    if _disp_ok "$d"; then DISP=$d; break; fi
  done
  printf '%s' "$DISP"
}

hdmi=0
if _drm_any_connected; then hdmi=1; fi

DISP=""
case "$POLICY" in
  virtual)
    # Pure virtual: wait for Xvfb :99, then connect.
    _wait_disp :99 || true
    DISP="$(_pick_first :99)"
    ;;
  real)
    # Real display first; fall back to :99 if none available.
    DISP="$(_pick_first "$HINT" :0 :1 :2)"
    [ -n "$DISP" ] || { _wait_disp :99 || true; DISP="$(_pick_first :99)"; }
    ;;
  auto|*)
    # Auto: prefer real display when available (with dummy-xorg or HDMI connected);
    # fall back to :99 virtual desktop if no real display is reachable.
    # This restores the previous behaviour where unplugging the monitor only
    # blacks out the background while VNC terminal / camera streaming still work.
    DISP="$(_pick_first \"$HINT\" :0 :1 :2)"
    if [ -z "$DISP" ]; then
      _wait_disp :99 || true
      DISP="$(_pick_first :99)"
    fi
    ;;
esac
[ -n "$DISP" ] || DISP=:99

mapfile -t _auth < <(_resolve_auth "$DISP")
# Use '-' instead of ':-' so an intentionally empty AUTH_ARG for Xvfb :99 is
# preserved. With ':-', bash treats the empty string as unset and falls back to
# '-auth guess', which fails against Xvfb started with -ac.
AUTH_ARG="${_auth[0]--auth guess}"
AUTH_FILE="${_auth[1]:-}"

{
  echo "---- $(date -Iseconds) ----"
  echo "seeed-x11vnc-launch policy=$POLICY hdmi_connected=$hdmi DISPLAY=$DISP AUTH_FILE=${AUTH_FILE:-}"
} >>"$LOG" 2>&1 || true
{
  echo "resolved DISPLAY=$DISP AUTH_FILE=${AUTH_FILE:-}"
  echo "exec: /usr/bin/x11vnc ${AUTH_ARG:-} -display $DISP -forever -shared -rfbport 5900 -nopw ..."
} >>"$LAUNCH_LOG" 2>&1 || true

exec /usr/bin/x11vnc $AUTH_ARG -display "$DISP" -forever -shared -rfbport 5900 -nopw \
  -noxdamage -noxfixes -nowf -nowcr -noscr -o "$LOG"
"""
).strip()


def build_write_seeed_x11vnc_launcher_sh_cmd(sudo_password: str) -> str:
    """Install the HDMI-aware x11vnc launcher to /usr/local/bin."""
    escaped = sudo_password.replace("'", "'\\''")
    # Use a quoted heredoc so the remote shell does not expand $variables inside the script.
    return (
        f"cat > /tmp/seeed-x11vnc-launch.sh << 'SEEDLAUNCHER_EOF'\n"
        f"{SEED_X11VNC_LAUNCHER_SH}\n"
        "SEEDLAUNCHER_EOF\n"
        f"echo '{escaped}' | sudo -S install -m 755 /tmp/seeed-x11vnc-launch.sh /usr/local/bin/seeed-x11vnc-launch.sh\n"
    )


def build_restart_x11vnc_cmd(sudo_password: str = "") -> str:
    """Restart only x11vnc so display selection re-runs (e.g. after HDMI hot-unplug)."""
    escaped = sudo_password.replace("'", "'\\''") if sudo_password else ""
    sudo = f"echo '{escaped}' | sudo -S" if escaped else "sudo"
    return (
        f"{sudo} systemctl restart seeed-x11vnc.service; "
        "sleep 2; "
        "ss -tlnp 2>/dev/null | grep -q ':5900' && echo 'x11vnc restarted OK' || "
        "{ echo 'x11vnc restart failed'; tail -n 60 /tmp/x11vnc.log 2>/dev/null || true; exit 1; }"
    )


def build_apply_x11vnc_unit_and_restart_cmd(sudo_password: str) -> str:
    """Install /tmp/seeed-x11vnc.service then reload systemd and restart x11vnc only."""
    escaped = sudo_password.replace("'", "'\\''")
    return (
        f"echo '{escaped}' | sudo -S cp /tmp/seeed-x11vnc.service /etc/systemd/system/seeed-x11vnc.service; "
        f"echo '{escaped}' | sudo -S systemctl daemon-reload; "
        f"echo '{escaped}' | sudo -S systemctl restart seeed-x11vnc.service; "
        "sleep 2; "
        "ss -tlnp 2>/dev/null | grep -q ':5900' && echo 'x11vnc unit applied OK' || "
        "{ echo 'x11vnc apply failed'; tail -n 80 /tmp/x11vnc.log 2>/dev/null || true; exit 1; }"
    )


def _start_services_and_wait_snippet(success_msg: str) -> str:
    return (
        'echo "$SUDO_PASS" | sudo -S systemctl enable seeed-headless-session.service seeed-x11vnc.service seeed-novnc.service; '
        'echo "$SUDO_PASS" | sudo -S systemctl start --no-block seeed-headless-session.service seeed-x11vnc.service seeed-novnc.service; '
        'echo "$SUDO_PASS" | sudo -S systemctl restart --no-block seeed-headless-session.service seeed-x11vnc.service seeed-novnc.service; '
        "_n=0; while [ $_n -lt 60 ]; do "
        "  sleep 1; "
        "  if ss -tlnp 2>/dev/null | grep -q ':5900' && ss -tlnp 2>/dev/null | grep -q ':6080'; then break; fi; "
        "  if [ $((_n % 10)) -eq 0 ]; then "
        "    echo \"waiting for VNC ports... ${_n}s\"; "
        "    systemctl is-active seeed-headless-session.service seeed-x11vnc.service seeed-novnc.service 2>/dev/null | tr '\\n' ' '; echo; "
        "    tail -n 12 /tmp/seeed-x11vnc-launch.log 2>/dev/null || true; "
        "    tail -n 12 /tmp/x11vnc.log 2>/dev/null || true; "
        "  fi; "
        "  _n=$((_n+1)); "
        "done; "
        "if ! ss -tlnp 2>/dev/null | grep -q ':5900'; then "
        "  echo 'x11vnc port 5900 not listening after deploy'; "
        "  echo '--- seeed-x11vnc status ---'; "
        "  systemctl status seeed-x11vnc.service --no-pager --full 2>/dev/null | head -50 || true; "
        "  echo '--- launcher log ---'; "
        "  tail -n 120 /tmp/seeed-x11vnc-launch.log 2>/dev/null || true; "
        "  echo '--- x11vnc log ---'; "
        "  tail -n 120 /tmp/x11vnc.log 2>/dev/null || true; "
        "  exit 1; "
        "fi; "
        "if ! ss -tlnp 2>/dev/null | grep -q ':6080'; then "
        "  echo 'noVNC port 6080 not listening after deploy'; "
        "  systemctl status seeed-novnc.service --no-pager --full 2>/dev/null | head -50 || true; "
        "  exit 1; "
        "fi; "
        f"echo '{success_msg}'"
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
    # Use a heredoc so that $(seq ...) and other shell metacharacters inside
    # the script are NOT expanded by the local shell when building the string.
    return (
        f"echo '{escaped}' | sudo -S bash -s << 'INSTALL_EOF'\n"
        "for _i in $(seq 1 24); do\n"
        "  lsof /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || break\n"
        "  echo 'Waiting for dpkg lock...' >&2; sleep 5\n"
        "done\n"
        "apt-get update && apt-get install -y "
        "x11vnc xvfb xauth dbus-x11 x11-xserver-utils novnc websockify "
        "python3-websockify openbox xterm xfce4 xfce4-terminal\n"
        "INSTALL_EOF"
    )


def build_enable_autologin_cmd(sudo_password: str, username: str) -> str:
    escaped_pwd = sudo_password.replace("'", "'\\''")
    # Write python script to a temp file to avoid any quoting issues.
    # Does NOT restart GDM — autologin takes effect on next natural restart.
    return (
        'CONF=""; '
        'for f in /etc/gdm3/custom.conf /etc/gdm/custom.conf; do '
        '  [ -f "$f" ] && CONF="$f" && break; '
        'done; '
        '[ -z "$CONF" ] && CONF=/etc/gdm3/custom.conf; '
        f"echo '{escaped_pwd}' | sudo -S mkdir -p \"$(dirname \"$CONF\")\" 2>/dev/null; "
        f"echo '{escaped_pwd}' | sudo -S touch \"$CONF\"; "
        'CONF_CONTENT=$(cat "$CONF" 2>/dev/null || echo ""); '
        f"cat > /tmp/seeed_autologin.py << 'PYEOF'\n"
        "import sys, re\n"
        "user = sys.argv[1]\n"
        "txt = sys.stdin.read()\n"
        "if '[daemon]' not in txt:\n"
        "    txt = '[daemon]\\n' + txt\n"
        "txt = re.sub(r'(?m)^AutomaticLoginEnable=.*', 'AutomaticLoginEnable=true', txt)\n"
        "if 'AutomaticLoginEnable=' not in txt:\n"
        "    txt = txt.replace('[daemon]', '[daemon]\\nAutomaticLoginEnable=true')\n"
        "txt = re.sub(r'(?m)^AutomaticLogin=.*', f'AutomaticLogin={user}', txt)\n"
        "if 'AutomaticLogin=' not in txt:\n"
        "    txt = txt.replace('[daemon]', f'[daemon]\\nAutomaticLogin={user}')\n"
        "sys.stdout.write(txt)\n"
        "PYEOF\n"
        f'NEW_CONTENT=$(echo "$CONF_CONTENT" | python3 /tmp/seeed_autologin.py "{username}"); '
        f"echo \"$NEW_CONTENT\" | (echo '{escaped_pwd}' | sudo -S tee \"$CONF\" >/dev/null); "
        'echo "autologin config written to $CONF"; '
        'cat "$CONF"; '
        "echo 'autologin setup done (no GDM restart — takes effect on next reboot)'"
    )


def build_start_vnc_cmd(
    password: str = "",
    display: str = "",
    sudo_password: str = "",
    username: str = "",
    policy: str = "auto",
) -> str:
    """Create and start persistent systemd services for headless-friendly VNC/noVNC."""
    escaped_pwd = sudo_password.replace("'", "'\\''")
    display_hint = (display or "").replace('"', "").replace("'", "")
    pol = policy if policy in ("auto", "real", "virtual") else "auto"
    launcher_install = build_write_seeed_x11vnc_launcher_sh_cmd(sudo_password)

    # If username is known at call time, embed it directly so systemd gets a
    # real user name.  Otherwise fall back to a shell-time substitution via a
    # small wrapper that rewrites the unit file before installing it.
    if username:
        svc_user = username.replace("'", "")
        svc_home = f"/home/{svc_user}"
        # Shell snippet that writes the four unit files with the real values
        write_units_cmd = (
            f"cat > /tmp/seeed-headless-xvfb.service << 'EOXVFB'\n"
            "[Unit]\n"
            "Description=Seeed Headless Xvfb\n"
            "After=network.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"User={svc_user}\n"
            f"Environment=HOME={svc_home}\n"
            "ExecStartPre=/bin/bash -c 'rm -f /tmp/.X99-lock /tmp/.X11-unix/X99'\n"
            "ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac\n"
            "Restart=always\n"
            "RestartSec=2\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
            "EOXVFB\n"
            f"cat > /tmp/seeed-x11vnc.service << 'EOX11'\n"
            "[Unit]\n"
            "Description=Seeed x11vnc server\n"
            "After=display-manager.service seeed-headless-xvfb.service seeed-headless-session.service\n"
            "Wants=seeed-headless-xvfb.service seeed-headless-session.service\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"Environment=HOME={svc_home}\n"
            f"Environment=DISPLAY_HINT={display_hint}\n"
            f"Environment=SEED_VNC_POLICY={pol}\n"
            "ExecStartPre=/bin/bash -c '_xi=0; while [ $_xi -lt 30 ]; do [ -S /tmp/.X11-unix/X99 ] && exit 0; _xi=$((_xi+1)); sleep 1; done; exit 0'\n"
            "ExecStart=/usr/local/bin/seeed-x11vnc-launch.sh\n"
            "Restart=always\n"
            "RestartSec=3\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
            "EOX11\n"
            f"cat > /tmp/seeed-headless-session.service << 'EOSESS'\n"
            "[Unit]\n"
            "Description=Seeed Headless Desktop Session on :99\n"
            "After=seeed-headless-xvfb.service\n"
            "Wants=seeed-headless-xvfb.service\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"User={svc_user}\n"
            f"Environment=HOME={svc_home}\n"
            "Environment=DISPLAY=:99\n"
            r"""ExecStart=/bin/bash -lc 'set -e; export DISPLAY=:99; unset XAUTHORITY; R=/run/user/$(id -u); if [ ! -d "$R" ]; then R=/tmp/seeed-runtime-$(id -u); mkdir -p "$R"; chmod 700 "$R"; fi; export XDG_RUNTIME_DIR="$R"; if command -v startxfce4 >/dev/null 2>&1; then dbus-launch --exit-with-session startxfce4; elif command -v openbox >/dev/null 2>&1; then dbus-launch --exit-with-session openbox; else xterm -geometry 120x40+20+20; fi'"""
            "\n"
            "Restart=always\n"
            "RestartSec=2\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
            "EOSESS\n"
            "cat > /tmp/seeed-novnc.service << 'EONOVNC'\n"
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
            "EONOVNC\n"
        )
    else:
        # username unknown at Python call time — derive it on the remote shell
        # and write all four unit files using printf with shell variables.
        write_units_cmd = (
            'USER_NAME="$(id -un)"; '
            'HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"; '
            'USER_UID="$(id -u)"; '
            # xvfb unit
            'printf "[Unit]\\nDescription=Seeed Headless Xvfb\\nAfter=network.target\\n\\n'
            '[Service]\\nType=simple\\nUser=%s\\nEnvironment=HOME=%s\\n'
            "ExecStartPre=/bin/bash -c 'rm -f /tmp/.X99-lock /tmp/.X11-unix/X99'\\n"
            'ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac\\n'
            'Restart=always\\nRestartSec=2\\n\\n[Install]\\nWantedBy=multi-user.target\\n"'
            ' "$USER_NAME" "$HOME_DIR" > /tmp/seeed-headless-xvfb.service; '
            # session unit
            'printf "[Unit]\\nDescription=Seeed Headless Desktop Session on :99\\n'
            'After=seeed-headless-xvfb.service\\nWants=seeed-headless-xvfb.service\\n\\n'
            '[Service]\\nType=simple\\nUser=%s\\nEnvironment=HOME=%s\\nEnvironment=DISPLAY=:99\\n'
            "ExecStart=/bin/bash -lc 'set -e; export DISPLAY=:99; unset XAUTHORITY; R=/run/user/$(id -u); if [ ! -d \"$R\" ]; then R=/tmp/seeed-runtime-$(id -u); mkdir -p \"$R\"; chmod 700 \"$R\"; fi; export XDG_RUNTIME_DIR=\"$R\"; "
            "if command -v startxfce4 >/dev/null 2>&1; then dbus-launch --exit-with-session startxfce4; "
            "elif command -v openbox >/dev/null 2>&1; then dbus-launch --exit-with-session openbox; "
            "else xterm -geometry 120x40+20+20; fi'\\n"
            'Restart=always\\nRestartSec=2\\n\\n[Install]\\nWantedBy=multi-user.target\\n"'
            ' "$USER_NAME" "$HOME_DIR" > /tmp/seeed-headless-session.service; '
            # x11vnc unit
            'printf "[Unit]\\nDescription=Seeed x11vnc server\\n'
            'After=display-manager.service seeed-headless-xvfb.service seeed-headless-session.service\\n'
            'Wants=seeed-headless-xvfb.service seeed-headless-session.service\\n\\n'
            '[Service]\\nType=simple\\nEnvironment=HOME=%s\\n'
            f'Environment=DISPLAY_HINT={display_hint}\\n'
            f'Environment=SEED_VNC_POLICY={pol}\\n'
            "ExecStartPre=/bin/bash -c '_xi=0; while [ $_xi -lt 30 ]; do [ -S /tmp/.X11-unix/X99 ] && exit 0; _xi=$((_xi+1)); sleep 1; done; exit 0'\\n"
            'ExecStart=/usr/local/bin/seeed-x11vnc-launch.sh\\n'
            'Restart=always\\nRestartSec=3\\n\\n[Install]\\nWantedBy=multi-user.target\\n"'
            ' "$HOME_DIR" > /tmp/seeed-x11vnc.service; '
            # novnc unit (no user substitution needed)
            'printf "[Unit]\\nDescription=Seeed noVNC websockify\\n'
            'After=network.target seeed-x11vnc.service\\nWants=seeed-x11vnc.service\\n\\n'
            '[Service]\\nType=simple\\n'
            'ExecStart=/usr/bin/websockify --web=/usr/share/novnc 6080 localhost:5900\\n'
            'Restart=always\\nRestartSec=2\\n\\n[Install]\\nWantedBy=multi-user.target\\n"'
            ' > /tmp/seeed-novnc.service; '
        )

    return (
        launcher_install
        + "set -e; "
        f"SUDO_PASS='{escaped_pwd}'; "
        + (f'USER_NAME="{svc_user}"; HOME_DIR="{svc_home}"; ' if username else
           'USER_NAME="$(id -un)"; HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"; ')
        + write_units_cmd
        + 'echo "$SUDO_PASS" | sudo -S systemctl stop seeed-novnc.service seeed-x11vnc.service seeed-headless-session.service seeed-headless-xvfb.service 2>/dev/null || true; '
        "pkill x11vnc 2>/dev/null || true; "
        "pkill websockify 2>/dev/null || true; "
        "pkill -x Xvfb 2>/dev/null || true; "
        'echo "$SUDO_PASS" | sudo -S rm -f /tmp/seeed-xvfb.auth /tmp/.X99-lock /tmp/.X11-unix/X99 /tmp/seeed-x11vnc-launch.log 2>/dev/null || true; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-headless-xvfb.service /etc/systemd/system/seeed-headless-xvfb.service; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-headless-session.service /etc/systemd/system/seeed-headless-session.service; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-x11vnc.service /etc/systemd/system/seeed-x11vnc.service; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-novnc.service /etc/systemd/system/seeed-novnc.service; '
        'echo "$SUDO_PASS" | sudo -S systemctl daemon-reload; '
        # Start Xvfb first and wait for socket — avoids race with x11vnc
        'echo "$SUDO_PASS" | sudo -S systemctl enable --now seeed-headless-xvfb.service; '
        '_xi=0; while [ $_xi -lt 30 ]; do [ -S /tmp/.X11-unix/X99 ] && break; sleep 1; _xi=$((_xi+1)); done; '
        '[ -S /tmp/.X11-unix/X99 ] || { '
        '  echo "ERROR: Xvfb :99 socket not ready after 30 s — Xvfb failed to start."; '
        '  echo "$SUDO_PASS" | sudo -S systemctl status seeed-headless-xvfb.service --no-pager --full 2>/dev/null | head -40 || true; '
        '  exit 1; }; '
        'echo "Xvfb :99 socket ready, starting VNC services..."; '
        + _start_services_and_wait_snippet("x11vnc/noVNC started OK on 5900/6080")
    )


def build_install_novnc_cmd(sudo_password: str) -> str:
    escaped = sudo_password.replace("'", "'\\''")
    return (
        f"echo '{escaped}' | sudo -S bash -s << 'NOVNC_EOF'\n"
        "for _i in $(seq 1 24); do\n"
        "  lsof /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || break\n"
        "  echo 'Waiting for dpkg lock...' >&2; sleep 5\n"
        "done\n"
        "apt-get install -y novnc websockify python3-websockify\n"
        "NOVNC_EOF"
    )


def build_prepare_vnc_password_cmd(password: str) -> str:
    return "echo 'vnc password disabled (no-password mode)'"


def build_write_headless_xvfb_unit_cmd(username: str) -> str:
    user = username.replace("'", "")
    # Resolution: auto-detect from current display, fallback to 1920x1080.
    # Runs as a pre-start script so the Xvfb gets the right geometry.
    return (
        "cat > /tmp/seeed-headless-xvfb.service <<'EOF'\n"
        "[Unit]\n"
        "Description=Seeed Headless Xvfb\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"User={user}\n"
        f"Environment=HOME=/home/{user}\n"
        # Generate xauth cookie
        "ExecStartPre=/bin/bash -c 'rm -f /tmp/.X99-lock /tmp/.X11-unix/X99'\n"
        # Auto-detect resolution from active display, fallback 1920x1080
        "ExecStartPre=/bin/bash -c '"
        "RES=$(xrandr --display :0 2>/dev/null | grep \" connected\" | "
        "grep -oP \"\\d+x\\d+\" | head -1); "
        "[ -z \"$RES\" ] && RES=1920x1080; "
        "echo $RES > /tmp/seeed-xvfb-res.txt'\n"
        "ExecStart=/bin/bash -c '"
        "RES=$(cat /tmp/seeed-xvfb-res.txt 2>/dev/null || echo 1920x1080); "
        "echo \"Starting Xvfb :99 at ${RES}\"; "
        "exec /usr/bin/Xvfb :99 -screen 0 ${RES}x24 -nolisten tcp -ac'\n"
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
        # Use a private runtime dir when the user has not logged in locally and
        # /run/user/$uid has not been created by PAM/systemd-logind.
        "ExecStart=/bin/bash -lc 'set -e; export DISPLAY=:99; unset XAUTHORITY; R=/run/user/$(id -u); if [ ! -d \"$R\" ]; then R=/tmp/seeed-runtime-$(id -u); mkdir -p \"$R\"; chmod 700 \"$R\"; fi; export XDG_RUNTIME_DIR=\"$R\"; if command -v startxfce4 >/dev/null 2>&1; then dbus-launch --exit-with-session startxfce4; elif command -v openbox >/dev/null 2>&1; then dbus-launch --exit-with-session openbox; else xterm -geometry 120x40+20+20; fi'\n"
        "Restart=always\n"
        "RestartSec=2\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
        "EOF"
    )


def build_write_x11vnc_unit_cmd(username: str, display: str = "", policy: str = "auto") -> str:
    user = username.replace("'", "")
    display_hint = (display or "").replace('"', "").replace("'", "")
    pol = policy if policy in ("auto", "real", "virtual") else "auto"
    return (
        "cat > /tmp/seeed-x11vnc.service <<'EOF'\n"
        "[Unit]\n"
        "Description=Seeed x11vnc server\n"
        "After=display-manager.service seeed-headless-xvfb.service seeed-headless-session.service\n"
        "Wants=seeed-headless-xvfb.service seeed-headless-session.service\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"Environment=HOME=/home/{user}\n"
        f"Environment=DISPLAY_HINT={display_hint}\n"
        f"Environment=SEED_VNC_POLICY={pol}\n"
        "ExecStartPre=/bin/bash -c '_xi=0; while [ $_xi -lt 30 ]; do [ -S /tmp/.X11-unix/X99 ] && exit 0; _xi=$((_xi+1)); sleep 1; done; exit 0'\n"
        "ExecStart=/usr/local/bin/seeed-x11vnc-launch.sh\n"
        "Restart=always\n"
        "RestartSec=3\n\n"
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
        'echo "$SUDO_PASS" | sudo -S rm -f /tmp/seeed-xvfb.auth /tmp/.X99-lock /tmp/.X11-unix/X99 /tmp/seeed-x11vnc-launch.log 2>/dev/null || true; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-headless-xvfb.service /etc/systemd/system/seeed-headless-xvfb.service; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-headless-session.service /etc/systemd/system/seeed-headless-session.service; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-x11vnc.service /etc/systemd/system/seeed-x11vnc.service; '
        'echo "$SUDO_PASS" | sudo -S cp /tmp/seeed-novnc.service /etc/systemd/system/seeed-novnc.service; '
        'echo "$SUDO_PASS" | sudo -S systemctl daemon-reload; '
        # Start Xvfb first and wait for socket before launching x11vnc
        'echo "$SUDO_PASS" | sudo -S systemctl enable --now seeed-headless-xvfb.service; '
        '_xi=0; while [ $_xi -lt 30 ]; do [ -S /tmp/.X11-unix/X99 ] && break; sleep 1; _xi=$((_xi+1)); done; '
        '[ -S /tmp/.X11-unix/X99 ] || { '
        '  echo "ERROR: Xvfb :99 socket not ready after 30 s — Xvfb failed to start."; '
        '  echo "$SUDO_PASS" | sudo -S systemctl status seeed-headless-xvfb.service --no-pager --full 2>/dev/null | head -40 || true; '
        '  exit 1; }; '
        'echo "Xvfb :99 socket ready, starting VNC services..."; '
        + _start_services_and_wait_snippet("vnc/novnc services started")
    )


def build_start_novnc_cmd(sudo_password: str = "", vnc_port: int = 5900, web_port: int = 6080) -> str:
    # noVNC is started by systemd in secure mode; keep compatibility for legacy button flow.
    escaped = sudo_password.replace("'", "'\\''") if sudo_password else ""
    return (
        "set -e; "
        f"SUDO_PASS='{escaped}'; "
        "if systemctl list-unit-files 2>/dev/null | grep -q '^seeed-novnc.service'; then "
        "  if [ -n \"$SUDO_PASS\" ]; then "
        "    printf '%s\\n' \"$SUDO_PASS\" | sudo -S -p '' systemctl restart --no-block seeed-novnc.service 2>&1 || true; "
        "  else "
        "    sudo -n systemctl restart --no-block seeed-novnc.service 2>&1 || true; "
        "  fi; "
        "else "
        f"  pkill websockify 2>/dev/null; sleep 0.3; websockify --web=/usr/share/novnc {web_port} localhost:{vnc_port} --daemon 2>&1; "
        "fi; "
        f"_n=0; while [ $_n -lt 8 ]; do sleep 1; ss -tlnp 2>/dev/null | grep -q ':{web_port}' && break; _n=$((_n+1)); done; "
        f"if ss -tlnp 2>/dev/null | grep -q ':{web_port}' || netstat -tlnp 2>/dev/null | grep -q ':{web_port}'; then "
        f"  echo 'noVNC ensured on port {web_port}'; "
        "else "
        "  echo 'noVNC start check failed'; "
        "  systemctl --no-pager --full status seeed-novnc.service seeed-x11vnc.service 2>/dev/null | sed -n '1,80p' || true; "
        "  ss -tlnp 2>/dev/null | grep -E ':5900|:6080' || true; "
        "  exit 1; "
        "fi"
    )


def build_stop_cmd(sudo_password: str = "") -> str:
    escaped = sudo_password.replace("'", "'\\''") if sudo_password else ""
    sudo = f"echo '{escaped}' | sudo -S" if escaped else "sudo"
    return (
        # Kill processes first (immediate) — don't wait for systemctl stop
        "pkill x11vnc 2>/dev/null || true; "
        "pkill websockify 2>/dev/null || true; "
        # Stop services with a short timeout so we don't block
        f"{sudo} systemctl stop --no-block seeed-novnc.service seeed-x11vnc.service 2>/dev/null || true; "
        # Session service (xfce4/openbox) can take a while — send SIGTERM and move on
        f"{sudo} systemctl kill seeed-headless-session.service 2>/dev/null || true; "
        f"{sudo} systemctl stop --no-block seeed-headless-session.service seeed-headless-xvfb.service 2>/dev/null || true; "
        "pkill -x Xvfb 2>/dev/null || true; "
        # Disable so services don't restart on next boot
        f"{sudo} systemctl disable seeed-novnc.service seeed-x11vnc.service seeed-headless-session.service seeed-headless-xvfb.service 2>/dev/null || true; "
        "echo 'stopped'"
    )


def build_diagnose_cmd() -> str:
    return (
        "set -e; "
        "echo '== systemd services =='; "
        "sudo systemctl --no-pager --full status seeed-headless-xvfb.service seeed-headless-session.service seeed-x11vnc.service seeed-novnc.service || true; "
        "echo '== display/xauth =='; "
        "echo DISPLAY=${DISPLAY:-}; "
        "echo XAUTHORITY=${XAUTHORITY:-}; "
        "ls -l /tmp/.X11-unix/X99 /tmp/seeed-xvfb.auth /run/user/$(id -u)/gdm/Xauthority ~/.Xauthority 2>/dev/null || true; "
        "echo '== listening ports =='; "
        "ss -tlnp 2>/dev/null | grep -E ':5900|:6080' || true; "
        "echo '== tail x11vnc log =='; "
        "tail -n 80 /tmp/x11vnc.log 2>/dev/null || true; "
        "echo '== tail launcher log =='; "
        "tail -n 80 /tmp/seeed-x11vnc-launch.log 2>/dev/null || true"
    )


def check_headless_active(runner: SSHRunner) -> bool:
    """Return True if the virtual headless VNC desktop is installed/active."""
    rc, out = runner.run(
        "systemctl is-active seeed-headless-xvfb.service seeed-headless-session.service 2>/dev/null "
        "&& [ -S /tmp/.X11-unix/X99 ] && echo YES || echo NO",
        timeout=8,
    )
    return rc == 0 and "YES" in out


def build_check_hdmi_connected_cmd() -> str:
    """Check whether any HDMI/DP display is physically connected on the Jetson."""
    return (
        "connected=0; "
        "for f in /sys/class/drm/*/status; do "
        "  [ -f \"$f\" ] && grep -qi 'connected' \"$f\" && connected=1 && break; "
        "done; "
        "if [ $connected -eq 1 ]; then echo 'HDMI_CONNECTED'; else echo 'HDMI_DISCONNECTED'; fi"
    )


def build_write_dummy_xorg_cmd(sudo_password: str, resolution: str = "1920x1080") -> str:
    """Write dummy xorg.conf so the desktop survives HDMI unplug.

    Only writes the config file — does NOT restart GDM or the desktop.
    The new config takes effect on next reboot or next GDM restart.
    x11vnc uses -display WAIT:0 so it reconnects automatically.
    """
    escaped = sudo_password.replace("'", "'\\''")
    parts = resolution.split("x")
    w, h = (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else ("1920", "1080")

    modeline_map = {
        "1920x1080": "148.50 1920 2008 2052 2200 1080 1084 1089 1125 +hsync +vsync",
        "1280x720":  " 74.25 1280 1390 1430 1650  720  725  730  750 +hsync +vsync",
        "1024x768":  " 65.00 1024 1048 1184 1344  768  771  777  806 -hsync -vsync",
    }
    modeline_params = modeline_map.get(f"{w}x{h}", modeline_map["1920x1080"])
    mode_name = f"{w}x{h}_60"

    write_xorg = (
        f"echo '{escaped}' | sudo -S bash -c '"
        "cat > /etc/X11/xorg.conf << __XORGEOF__\n"
        "Section \"Device\"\n"
        "    Identifier  \"DummyDevice\"\n"
        "    Driver      \"dummy\"\n"
        "    VideoRam    256000\n"
        "EndSection\n\n"
        "Section \"Monitor\"\n"
        "    Identifier  \"DummyMonitor\"\n"
        "    HorizSync   28-80\n"
        "    VertRefresh 48-75\n"
        f"    Modeline    \"{mode_name}\" {modeline_params}\n"
        "EndSection\n\n"
        "Section \"Screen\"\n"
        "    Identifier  \"DummyScreen\"\n"
        "    Device      \"DummyDevice\"\n"
        "    Monitor     \"DummyMonitor\"\n"
        "    DefaultDepth 24\n"
        "    SubSection \"Display\"\n"
        "        Depth   24\n"
        f"        Modes   \"{mode_name}\"\n"
        "    EndSubSection\n"
        "EndSection\n"
        "__XORGEOF__\n"
        "'"
    )

    return (
        "set -e; "
        # Install dummy driver
        f"echo '{escaped}' | sudo -S bash -s << 'DUMMY_APT_EOF'\n"
        "for _i in $(seq 1 12); do\n"
        "  lsof /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || break\n"
        "  echo 'Waiting for dpkg lock...' >&2; sleep 5\n"
        "done\n"
        "apt-get install -y xserver-xorg-video-dummy 2>&1 | tail -3\n"
        "DUMMY_APT_EOF\n"
        # Backup existing xorg.conf
        f"echo '{escaped}' | sudo -S bash -c '"
        "[ -f /etc/X11/xorg.conf ] && "
        "cp /etc/X11/xorg.conf /etc/X11/xorg.conf.seeed-backup 2>/dev/null || true"
        "'; "
        # Write xorg.conf
        + write_xorg + "; "
        "echo 'dummy xorg.conf written (takes effect on next reboot):'; "
        "cat /etc/X11/xorg.conf; "
        "echo 'NOTE: reboot Jetson once to activate dummy display permanently.'; "
        "echo 'headless config done'"
    )


def build_remove_dummy_xorg_cmd(sudo_password: str) -> str:
    """Restore original xorg.conf (or remove dummy one) to re-enable real GPU display."""
    escaped = sudo_password.replace("'", "'\\''")
    return (
        f"echo '{escaped}' | sudo -S bash -c \""
        "if [ -f /etc/X11/xorg.conf.seeed-backup ]; then "
        "  cp /etc/X11/xorg.conf.seeed-backup /etc/X11/xorg.conf && echo 'xorg.conf restored from backup'; "
        "else "
        "  rm -f /etc/X11/xorg.conf && echo 'xorg.conf removed (no backup found)'; "
        "fi"
        "\""
    )


def build_rollback_cmd(sudo_password: str) -> str:
    escaped = sudo_password.replace("'", "'\\''")
    return (
        f"echo '{escaped}' | sudo -S systemctl stop seeed-novnc.service seeed-x11vnc.service seeed-headless-session.service seeed-headless-xvfb.service 2>/dev/null || true; "
        f"echo '{escaped}' | sudo -S systemctl disable seeed-novnc.service seeed-x11vnc.service seeed-headless-session.service seeed-headless-xvfb.service 2>/dev/null || true; "
        f"echo '{escaped}' | sudo -S rm -f /etc/systemd/system/seeed-headless-xvfb.service /etc/systemd/system/seeed-headless-session.service /etc/systemd/system/seeed-x11vnc.service /etc/systemd/system/seeed-novnc.service; "
        f"echo '{escaped}' | sudo -S rm -f /usr/local/bin/seeed-x11vnc-launch.sh; "
        f"echo '{escaped}' | sudo -S systemctl daemon-reload; "
        "pkill x11vnc 2>/dev/null || true; pkill websockify 2>/dev/null || true; pkill -x Xvfb 2>/dev/null || true; "
        # Also restore xorg.conf if dummy was installed
        + build_remove_dummy_xorg_cmd(sudo_password) + "; "
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
