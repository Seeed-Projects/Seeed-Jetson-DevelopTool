#!/usr/bin/env python3
"""
Build self-extracting installer packages for Seeed Jetson Develop Tool.

Usage:
    python scripts/build_installer.py

Output:
    dist/seeed-jetson-install-linux.sh
    dist/seeed-jetson-install-windows.exe  (when built on Windows with PyInstaller)
    dist/seeed-jetson-install-windows.ps1  (fallback)
    dist/seeed-jetson-install-windows.bat  (fallback launcher)
"""

import base64
import io
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).parent.parent
DIST = ROOT / "dist"
APP_NAME = "seeed-jetson-develop"
APP_VERSION = "0.2.0"
APP_ICON_PNG = "assets/seeed-jetson-develop-icon.png"
APP_ICON_ICO = "assets/seeed-jetson-develop-icon.ico"

# Directories/files to exclude from the archive
EXCLUDE_NAMES = {
    ".git", "__pycache__", "dist", "build", "venv", ".venv", "env",
    "node_modules", "prd_images", ".pytest_cache", ".mypy_cache",
    "=0.20.0", ".claude", ".kiro", ".vscode", ".snapshots",
    "tmp-refer", "scripts",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".docx"}
EXCLUDE_PREFIXES = ("video-cover", "video_cover")


def should_exclude(rel: Path) -> bool:
    for part in rel.parts:
        if part in EXCLUDE_NAMES:
            return True
        if part.endswith(".egg-info"):
            return True
        if any(part.startswith(p) for p in EXCLUDE_PREFIXES):
            return True
    if rel.suffix in EXCLUDE_SUFFIXES:
        return True
    # Skip large zip/tar inside assets
    if rel.suffix in {".zip", ".tar", ".tar.gz"} and "assets" in rel.parts:
        return True
    return False


def create_tar_gz() -> bytes:
    """Create tar.gz archive of the project source (for Linux)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=6) as tar:
        for item in sorted(ROOT.rglob("*")):
            if not item.is_file():
                continue
            rel = item.relative_to(ROOT)
            if should_exclude(rel):
                continue
            tar.add(item, arcname=str(rel))
    return buf.getvalue()


def create_zip() -> bytes:
    """Create zip archive of the project source (for Windows)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for item in sorted(ROOT.rglob("*")):
            if not item.is_file():
                continue
            rel = item.relative_to(ROOT)
            if should_exclude(rel):
                continue
            zf.write(item, str(rel).replace("\\", "/"))
    return buf.getvalue()


# ── Linux installer template ──────────────────────────────────────────────────

LINUX_TEMPLATE = r"""#!/bin/bash
# Seeed Jetson Develop Tool - Linux Self-Extracting Installer
# Version: {version}
set -e

APP_NAME="{app_name}"
APP_VERSION="{version}"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

info()    {{ echo -e "${{BLUE}}[INFO]${{NC}} $*"; }}
success() {{ echo -e "${{GREEN}}[OK]${{NC}}   $*"; }}
warn()    {{ echo -e "${{YELLOW}}[WARN]${{NC}} $*"; }}
error()   {{ echo -e "${{RED}}[ERR]${{NC}}  $*"; }}

echo -e "${{BOLD}}${{BLUE}}"
echo "╔══════════════════════════════════════════╗"
echo "║   Seeed Jetson Develop Tool Installer    ║"
echo "║   Version: $APP_VERSION                        ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${{NC}}"

# ── Check Python ──────────────────────────────────────────────────────────────
find_python() {{
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            ver=$("$cmd" -c "import sys; v=sys.version_info; print(v.major,v.minor)" 2>/dev/null)
            major=$(echo "$ver" | cut -d' ' -f1)
            minor=$(echo "$ver" | cut -d' ' -f2)
            if [ "${{major:-0}}" -ge 3 ] && [ "${{minor:-0}}" -ge 8 ]; then
                echo "$cmd"; return 0
            fi
        fi
    done
    return 1
}}

PYTHON=$(find_python) || {{
    error "Python 3.8+ is required but not found."
    echo "  Install with: sudo apt install python3 python3-venv python3-pip"
    echo "  Or visit: https://www.python.org/downloads/"
    exit 1
}}
success "Python: $PYTHON ($($PYTHON --version 2>&1))"

# ── Check venv module ─────────────────────────────────────────────────────────
if ! "$PYTHON" -m venv --help &>/dev/null; then
    error "Python venv module not found."
    echo "  Install with: sudo apt install python3-venv"
    exit 1
fi

# ── Prepare install directory ─────────────────────────────────────────────────
if [ -d "$INSTALL_DIR" ]; then
    warn "Existing installation found at $INSTALL_DIR — will overwrite."
fi
mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$DESKTOP_DIR"

# ── Extract embedded archive ──────────────────────────────────────────────────
info "Extracting application files..."
SCRIPT_PATH="$(readlink -f "${{BASH_SOURCE[0]}}")"
ARCHIVE_LINE=$(grep -n "^__ARCHIVE_BELOW__$" "$SCRIPT_PATH" | cut -d: -f1)
if [ -z "$ARCHIVE_LINE" ]; then
    error "Archive marker not found in installer. File may be corrupted."
    exit 1
fi
tail -n +$((ARCHIVE_LINE + 1)) "$SCRIPT_PATH" | base64 -d | tar -xzf - -C "$INSTALL_DIR"
success "Files extracted to $INSTALL_DIR"

# ── Create virtual environment ────────────────────────────────────────────────
info "Creating virtual environment..."
"$PYTHON" -m venv "$INSTALL_DIR/venv"
VENV_PY="$INSTALL_DIR/venv/bin/python"
VENV_PIP="$INSTALL_DIR/venv/bin/pip"
success "Virtual environment ready"

# ── Install dependencies ──────────────────────────────────────────────────────
info "Upgrading pip..."
"$VENV_PY" -m pip install --upgrade pip --quiet || warn "pip upgrade failed, continuing..."
info "Installing dependencies (this may take a few minutes)..."
"$VENV_PY" -m pip install -r "$INSTALL_DIR/requirements.txt" --quiet
success "Dependencies installed"

# ── Create launcher script ────────────────────────────────────────────────────
cat > "$BIN_DIR/$APP_NAME" << 'LAUNCHER_EOF'
#!/bin/bash
exec "$HOME/.local/share/seeed-jetson-develop/venv/bin/python" \
     "$HOME/.local/share/seeed-jetson-develop/run_v2.py" "$@"
LAUNCHER_EOF
chmod +x "$BIN_DIR/$APP_NAME"
success "Launcher: $BIN_DIR/$APP_NAME"

# ── Create .desktop entry ─────────────────────────────────────────────────────
ICON_PATH="$INSTALL_DIR/{app_icon_png}"
[ -f "$ICON_PATH" ] || ICON_PATH="utilities-terminal"
cat > "$DESKTOP_DIR/$APP_NAME.desktop" << DESKTOP_EOF
[Desktop Entry]
Name=Seeed Jetson Develop Tool
Comment=Seeed Jetson Development & Flash Tool
Exec=$BIN_DIR/$APP_NAME
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Development;Embedded;
StartupNotify=true
DESKTOP_EOF
success "Desktop entry created"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${{GREEN}}${{BOLD}}Installation complete!${{NC}}"
echo ""
echo "  Run:  $APP_NAME"
echo ""
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in your PATH."
    echo "  Add to ~/.bashrc or ~/.zshrc:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

exit 0
__ARCHIVE_BELOW__
"""

# ── Windows PowerShell installer template ─────────────────────────────────────

WINDOWS_PS1_TEMPLATE = r"""# Seeed Jetson Develop Tool - Windows Installer
# Version: {version}
# Run with: powershell -ExecutionPolicy Bypass -File install-windows.ps1

$AppName    = "{app_name}"
$AppVersion = "{version}"
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName
$ErrorActionPreference = "Stop"

function Write-Step  {{ param($msg) Write-Host "[....] $msg" -ForegroundColor Cyan }}
function Write-Ok    {{ param($msg) Write-Host "[ OK ] $msg" -ForegroundColor Green }}
function Write-Fail  {{ param($msg) Write-Host "[FAIL] $msg" -ForegroundColor Red }}
function Write-Warn  {{ param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }}

Write-Host ""
Write-Host "  Seeed Jetson Develop Tool Installer  " -ForegroundColor Blue -BackgroundColor White
Write-Host "  Version: $AppVersion  " -ForegroundColor Blue -BackgroundColor White
Write-Host ""

# ── Find Python ───────────────────────────────────────────────────────────────
Write-Step "Checking Python..."
$PythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {{
    try {{
        $ver = & $cmd -c "import sys; v=sys.version_info; print(v.major, v.minor)" 2>$null
        if ($ver) {{
            $parts = $ver.Trim().Split(" ")
            if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 8) {{
                $PythonCmd = $cmd; break
            }}
        }}
    }} catch {{ }}
}}
if (-not $PythonCmd) {{
    Write-Fail "Python 3.8+ not found."
    Write-Host "  Download from: https://www.python.org/downloads/"
    Write-Host "  Make sure to check 'Add Python to PATH' during installation."
    Read-Host "`nPress Enter to exit"
    exit 1
}}
$PyVer = & $PythonCmd --version 2>&1
Write-Ok "Python: $PythonCmd ($PyVer)"

# ── Prepare install directory ─────────────────────────────────────────────────
Write-Step "Preparing install directory: $InstallDir"
if (Test-Path $InstallDir) {{
    Write-Warn "Existing installation found — will overwrite."
}}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Write-Ok "Directory ready"

# ── Extract embedded archive ──────────────────────────────────────────────────
Write-Step "Extracting application files..."
$ArchiveBase64 = @"
{archive_base64}
"@
try {{
    $ArchiveBytes = [Convert]::FromBase64String($ArchiveBase64.Trim())
    $ZipPath = Join-Path $env:TEMP "seeed-jetson-install-$([System.Guid]::NewGuid().ToString('N')).zip"
    [IO.File]::WriteAllBytes($ZipPath, $ArchiveBytes)
    Expand-Archive -Path $ZipPath -DestinationPath $InstallDir -Force
    Remove-Item $ZipPath -ErrorAction SilentlyContinue
    Write-Ok "Files extracted to $InstallDir"
}} catch {{
    Write-Fail "Extraction failed: $_"
    Read-Host "Press Enter to exit"; exit 1
}}

# ── Create virtual environment ────────────────────────────────────────────────
Write-Step "Creating virtual environment..."
& $PythonCmd -m venv "$InstallDir\venv"
$VenvPy  = "$InstallDir\venv\Scripts\python.exe"
$VenvPythonw = "$InstallDir\venv\Scripts\pythonw.exe"
if (Test-Path $VenvPythonw) {{ $AppPython = $VenvPythonw }} else {{ $AppPython = $VenvPy }}
$VenvPip = "$InstallDir\venv\Scripts\pip.exe"
Write-Ok "Virtual environment ready"

# ── Upgrade pip first (use python -m pip to avoid stale pip.exe on Windows) ───
Write-Step "Upgrading pip..."
try {{
    & $VenvPy -m pip install --upgrade pip --quiet
    Write-Ok "pip upgraded"
}} catch {{
    Write-Warn "pip upgrade failed (non-fatal): $_"
}}

# ── Install dependencies ──────────────────────────────────────────────────────
Write-Step "Installing dependencies (this may take a few minutes)..."
& $VenvPy -m pip install -r "$InstallDir\requirements.txt" --quiet
Write-Ok "Dependencies installed"

# ── Create launcher batch file ────────────────────────────────────────────────
$LauncherPath = "$InstallDir\launch.vbs"
$DebugLauncherPath = "$InstallDir\launch-debug.bat"
$LauncherContent = "Set shell = CreateObject(`"WScript.Shell`")`r`nshell.Run `"`"`"$AppPython`"`" `"`"$InstallDir\run_v2.py`"`"`", 0, False`r`n"
[IO.File]::WriteAllText($LauncherPath, $LauncherContent)
$DebugLauncherContent = "@echo off`r`nset SEEED_JETSON_DEBUG_CONSOLE=1`r`n`"$VenvPy`" `"$InstallDir\run_v2.py`" --debug-console %*`r`n"
[IO.File]::WriteAllText($DebugLauncherPath, $DebugLauncherContent)
Write-Ok "Launcher: $LauncherPath"

# ── Create desktop shortcut ───────────────────────────────────────────────────
try {{
    $WshShell  = New-Object -ComObject WScript.Shell
    $Shortcut  = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Seeed Jetson Develop.lnk")
    $Shortcut.TargetPath       = $AppPython
    $Shortcut.Arguments        = "`"$InstallDir\run_v2.py`""
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description      = "Seeed Jetson Develop Tool"
    $IconPath = "$InstallDir\{app_icon_ico_win}"
    if (Test-Path $IconPath) {{ $Shortcut.IconLocation = $IconPath }}
    $Shortcut.Save()
    Write-Ok "Desktop shortcut created"
}} catch {{
    Write-Warn "Could not create desktop shortcut: $_"
}}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Launch: double-click 'Seeed Jetson Develop' on your Desktop"
Write-Host "  Or run: $LauncherPath"
Write-Host ""
Read-Host "Press Enter to exit"
"""

WINDOWS_BAT_TEMPLATE = r"""@echo off
:: Seeed Jetson Develop Tool - Windows Installer Launcher
:: Double-click this file to start installation.
echo Starting Seeed Jetson Develop Tool installer...
powershell -ExecutionPolicy Bypass -File "%~dp0seeed-jetson-install-windows.ps1"
if errorlevel 1 (
    echo.
    echo Installation failed. See messages above.
    pause
)
"""

WINDOWS_EXE_PY_TEMPLATE = r'''#!/usr/bin/env python3
"""Seeed Jetson Develop Tool Windows installer (Tkinter GUI).

This file is generated by scripts/build_installer.py and is intended to be
packaged with PyInstaller (--onefile --windowed) into
seeed-jetson-install-windows.exe.
"""

import base64
import ctypes
import io
import os
import queue
import subprocess
import sys
import threading
import urllib.request
import urllib.error
import zipfile
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "__APP_NAME__"
APP_VERSION = "__APP_VERSION__"
APP_ICON_ICO = "__APP_ICON_ICO__"
ARCHIVE_BASE64 = """
__ARCHIVE_BASE64__
"""

CREATE_NO_WINDOW = 0x08000000
SUBPROCESS_FLAGS = CREATE_NO_WINDOW if os.name == "nt" else 0
ERROR_ALREADY_EXISTS = 183
SINGLE_INSTANCE_MUTEX = "Local\\SeeedJetsonDevelopInstaller"
_single_instance_handle = None

# If no suitable Python is found on the user's machine, we download this
# official installer and run it silently. 3.11 is the sweet spot: long-term
# support through 2027 and ships with tcl/tk so tkinter works out of the box.
PYTHON_DOWNLOAD_VERSION = "3.11.9"
PYTHON_DOWNLOAD_URL = (
    "https://www.python.org/ftp/python/%s/python-%s-amd64.exe"
    % (PYTHON_DOWNLOAD_VERSION, PYTHON_DOWNLOAD_VERSION)
)

# ── i18n ──────────────────────────────────────────────────────────────
# Detect Windows UI language at startup and pick zh/en. Any non-Chinese
# system falls back to English. Users don't pick — it matches the OS.
def _detect_lang():
    if os.name == "nt":
        try:
            import ctypes
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            # Primary language id is the low 10 bits; 0x04 == Chinese.
            if (lcid & 0x3FF) == 0x04:
                return "zh"
        except Exception:
            pass
    try:
        import locale
        lang = (locale.getdefaultlocale()[0] or "").lower()
        if lang.startswith("zh"):
            return "zh"
    except Exception:
        pass
    return "en"


STRINGS = {
    "zh": {
        "window_title":       "Seeed Jetson Develop Tool 安装向导",
        "header_subtitle":    "版本 {version}   Windows 安装向导",
        "status_initial":     "准备开始安装…",
        "log_show":           "▶ 显示详细日志",
        "log_hide":           "▼ 隐藏详细日志",
        "btn_install":        "开始安装",
        "btn_installing":     "安装中…",
        "btn_cancel":         "取消",
        "btn_launch":         "启动程序",
        "btn_close":          "关闭",
        "status_done":        "安装完成！",
        "status_failed":      "安装失败,请展开详细日志查看原因",
        "dlg_cancel_title":   "取消安装",
        "dlg_cancel_body":    "安装正在进行中,确定要中止吗?\n已解压的文件不会被自动清理。",
        "dlg_failed_title":   "安装失败",
        "dlg_unknown":        "未知错误。",
        "dlg_winonly_title":  "不支持的平台",
        "dlg_winonly_body":   "此安装程序仅适用于 Windows。",
        "dlg_running_title":  "安装程序已在运行",
        "dlg_running_body":   "已有一个安装引导正在运行。请先完成或关闭当前安装窗口，再启动新的安装程序。",
        "log_running":        "Installer is already running.",
        "stage_check_python":  "检查 Python 环境",
        "stage_install_python":"下载并安装 Python",
        "stage_prepare_dir":   "准备安装目录",
        "stage_extract":       "解压应用文件",
        "stage_create_venv":   "创建 Python 虚拟环境",
        "stage_upgrade_pip":   "升级 pip",
        "stage_install_deps":  "安装依赖(可能需要几分钟)",
        "stage_shortcut":      "创建启动器和桌面快捷方式",
        "stage_arrow":         ">>> {label}\n",
        "log_py_missing_tk":   "检测到 Python {label} ({ver}),但缺少 tkinter(tcl/tk)模块。\n",
        "log_will_install":    "将为您下载并安装包含完整组件的 Python {ver}。\n",
        "log_no_python":       "未检测到 Python,正在为您自动下载安装 Python {ver}...\n",
        "err_reinstall":       "Python 自动安装似乎已完成,但仍未检测到可用的 Python 环境。\n\n请手动从 https://www.python.org/downloads/ 下载并安装,安装时务必勾选 “Add Python to PATH” 和 “tcl/tk and IDLE”,然后重新运行本安装程序。",
        "log_python":          "Python: {label} ({ver})\n",
        "log_overwrite":       "检测到旧版本安装,将覆盖更新。\n",
        "log_install_dir":     "安装目录:{dir}\n",
        "log_url":             "下载地址:{url}\n",
        "progress_download":   "下载 Python 安装包",
        "err_download_fail":   "下载 Python 安装包失败:{err}\n\n请检查网络连接后重试,或手动从\n  {url}\n下载后再运行本程序。",
        "status_py_installing":"正在静默安装 Python,请稍候…",
        "log_py_running":      "\n运行 Python 安装程序(静默、用户级别、含 tcl/tk、加入 PATH)...\n",
        "err_py_launch":       "启动 Python 安装程序失败:{err}",
        "err_py_exit":         "Python 安装程序返回错误码 {code}。您可以尝试手动运行:\n  {path}",
        "log_py_done":         "Python 安装完成。\n",
        "status_py_waiting":   "等待系统识别新安装的 Python…",
        "log_download_done":   "下载完成:{path} ({mb:.1f} MB)\n",
        "progress_extract_n":  "解压应用文件 ({i}/{total})",
        "log_extract_done":    "已解压 {n} 个文件\n",
        "log_venv_ready":      "虚拟环境创建完成\n",
        "log_pip_fail":        "pip 升级失败(不影响继续安装):{err}\n",
        "log_launcher":        "启动器:{path}\n",
        "log_shortcut_ok":     "桌面快捷方式已创建\n",
        "log_shortcut_fail":   "无法创建桌面快捷方式:{err}\n",
        "err_cancelled":       "用户取消安装",
        "err_cmd_fail":        "命令执行失败 (exit {code}):{cmd}",
        "progress_deps_lines": "安装依赖(已处理 {n} 行日志)",
    },
    "en": {
        "window_title":       "Seeed Jetson Develop Tool Setup",
        "header_subtitle":    "Version {version}   Windows Installer",
        "status_initial":     "Ready to install…",
        "log_show":           "▶ Show detailed log",
        "log_hide":           "▼ Hide detailed log",
        "btn_install":        "Install",
        "btn_installing":     "Installing…",
        "btn_cancel":         "Cancel",
        "btn_launch":         "Launch",
        "btn_close":          "Close",
        "status_done":        "Installation complete!",
        "status_failed":      "Installation failed. Expand the log for details.",
        "dlg_cancel_title":   "Cancel installation",
        "dlg_cancel_body":    "Installation is in progress. Abort now?\nExtracted files will not be cleaned up automatically.",
        "dlg_failed_title":   "Installation failed",
        "dlg_unknown":        "Unknown error.",
        "dlg_winonly_title":  "Unsupported platform",
        "dlg_winonly_body":   "This installer only runs on Windows.",
        "dlg_running_title":  "Installer already running",
        "dlg_running_body":   "Another installer window is already running. Please finish or close it before starting a new one.",
        "log_running":        "Installer is already running.",
        "stage_check_python":  "Checking Python environment",
        "stage_install_python":"Downloading and installing Python",
        "stage_prepare_dir":   "Preparing install directory",
        "stage_extract":       "Extracting application files",
        "stage_create_venv":   "Creating Python virtual environment",
        "stage_upgrade_pip":   "Upgrading pip",
        "stage_install_deps":  "Installing dependencies (may take a few minutes)",
        "stage_shortcut":      "Creating launcher and desktop shortcut",
        "stage_arrow":         ">>> {label}\n",
        "log_py_missing_tk":   "Detected Python {label} ({ver}), but the tkinter (tcl/tk) module is missing.\n",
        "log_will_install":    "Downloading Python {ver} with all required components...\n",
        "log_no_python":       "No Python detected — downloading and installing Python {ver} for you...\n",
        "err_reinstall":       "The automatic Python installation appears to have finished, but no usable Python is detected yet.\n\nPlease install Python manually from https://www.python.org/downloads/ — be sure to tick 'Add Python to PATH' and 'tcl/tk and IDLE' — then run this installer again.",
        "log_python":          "Python: {label} ({ver})\n",
        "log_overwrite":       "Previous installation detected — it will be overwritten.\n",
        "log_install_dir":     "Install directory: {dir}\n",
        "log_url":             "Download URL: {url}\n",
        "progress_download":   "Downloading Python installer",
        "err_download_fail":   "Failed to download the Python installer: {err}\n\nCheck your internet connection and try again, or download it manually from\n  {url}\nand re-run this setup.",
        "status_py_installing":"Installing Python silently, please wait…",
        "log_py_running":      "\nRunning Python installer (silent, per-user, with tcl/tk, adds to PATH)...\n",
        "err_py_launch":       "Failed to launch the Python installer: {err}",
        "err_py_exit":         "The Python installer returned exit code {code}. You can run it manually:\n  {path}",
        "log_py_done":         "Python install finished.\n",
        "status_py_waiting":   "Waiting for the system to register the new Python…",
        "log_download_done":   "Download complete: {path} ({mb:.1f} MB)\n",
        "progress_extract_n":  "Extracting application files ({i}/{total})",
        "log_extract_done":    "Extracted {n} files\n",
        "log_venv_ready":      "Virtual environment ready\n",
        "log_pip_fail":        "pip upgrade failed (non-fatal): {err}\n",
        "log_launcher":        "Launcher: {path}\n",
        "log_shortcut_ok":     "Desktop shortcut created\n",
        "log_shortcut_fail":   "Could not create desktop shortcut: {err}\n",
        "err_cancelled":       "Installation cancelled by user",
        "err_cmd_fail":        "Command failed (exit {code}): {cmd}",
        "progress_deps_lines": "Installing dependencies ({n} log lines processed)",
    },
}

LANG = _detect_lang()


def t(key, **kwargs):
    s = STRINGS.get(LANG, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    if kwargs:
        try:
            return s.format(**kwargs)
        except (KeyError, IndexError):
            return s
    return s


def _acquire_single_instance():
    global _single_instance_handle
    if os.name != "nt":
        return True
    try:
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX)
        if not handle:
            return True
        if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            ctypes.windll.kernel32.CloseHandle(handle)
            return False
        _single_instance_handle = handle
        return True
    except Exception:
        return True


def _release_single_instance():
    global _single_instance_handle
    if os.name != "nt":
        return
    handle = _single_instance_handle
    _single_instance_handle = None
    if not handle:
        return
    try:
        ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass


# (key, stage-label-key, target-progress-after-stage)
STAGES = [
    ("check_python",   "stage_check_python",   3),
    ("install_python", "stage_install_python", 12),
    ("prepare_dir",    "stage_prepare_dir",    15),
    ("extract",        "stage_extract",        30),
    ("create_venv",    "stage_create_venv",    40),
    ("upgrade_pip",    "stage_upgrade_pip",    45),
    ("install_deps",   "stage_install_deps",   90),
    ("shortcut",       "stage_shortcut",       100),
]


def python_version(command):
    try:
        output = subprocess.check_output(
            command + ["-c", "import sys; v=sys.version_info; print(v.major, v.minor)"],
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=SUBPROCESS_FLAGS,
        ).strip()
    except Exception:
        return None
    parts = output.split()
    if len(parts) < 2:
        return None
    try:
        major, minor = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    # Require 3.9-3.12: PyQt5 wheels don't cover 3.13 yet, and <3.9 misses
    # typing features the project uses.
    if major == 3 and 9 <= minor <= 12:
        return (major, minor)
    return None


def python_has_tkinter(command):
    try:
        subprocess.check_call(
            command + ["-c", "import tkinter, tkinter.ttk"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=SUBPROCESS_FLAGS,
        )
        return True
    except Exception:
        return False


def _candidate_python_commands():
    """All reasonable ways to invoke Python on a Windows user's machine.

    Order matters: try 3.11 first (what we auto-install and what PyQt5 is
    best tested against), then adjacent supported minors. 3.13 is omitted
    because PyQt5 has no official wheels for it yet.
    """
    commands = []
    # Prefer py launcher with explicit versions (PEP 514).
    for tag in ("-3.11", "-3.12", "-3.10", "-3.9"):
        commands.append(["py", tag])
    # Generic fallbacks — will be rejected by python_version() if outside 3.9-3.12.
    commands.append(["py", "-3"])
    commands.append(["python"])
    commands.append(["python3"])
    # Well-known per-user and all-users install roots, 3.11 first.
    roots = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python310"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python39"),
        r"C:\Python311", r"C:\Python312", r"C:\Python310", r"C:\Python39",
        r"C:\Program Files\Python311", r"C:\Program Files\Python312",
        r"C:\Program Files\Python310", r"C:\Program Files\Python39",
    ]
    for root in roots:
        exe = os.path.join(root, "python.exe")
        if os.path.exists(exe):
            commands.append([exe])
    return commands


def find_python(require_tkinter=True):
    for command in _candidate_python_commands():
        version = python_version(command)
        if not version:
            continue
        if require_tkinter and not python_has_tkinter(command):
            continue
        return command, " ".join(command), "%s.%s" % version
    return None, None, None


def powershell_quote(value):
    return "'" + value.replace("'", "''") + "'"


def create_desktop_shortcut(install_dir, target_path, arguments=""):
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    shortcut_path = os.path.join(desktop, "Seeed Jetson Develop.lnk")
    icon_path = os.path.join(install_dir, *APP_ICON_ICO.split("/"))
    ps_lines = [
        "$WshShell = New-Object -ComObject WScript.Shell",
        "$Shortcut = $WshShell.CreateShortcut(%s)" % powershell_quote(shortcut_path),
        "$Shortcut.TargetPath = %s" % powershell_quote(target_path),
        "$Shortcut.WorkingDirectory = %s" % powershell_quote(install_dir),
        "$Shortcut.Description = 'Seeed Jetson Develop Tool'",
    ]
    if arguments:
        ps_lines.append("$Shortcut.Arguments = %s" % powershell_quote(arguments))
    if os.path.exists(icon_path):
        ps_lines.append("$Shortcut.IconLocation = %s" % powershell_quote(icon_path))
    ps_lines.append("$Shortcut.Save()")
    subprocess.check_call(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", "; ".join(ps_lines)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=SUBPROCESS_FLAGS,
    )


class InstallerGUI:
    def __init__(self, root):
        self.root = root
        self.queue = queue.Queue()
        self.install_thread = None
        self.cancelled = False
        self.finished = False
        self.success = False
        self.install_dir = None
        self.launcher_path = None
        self._build_ui()
        self._poll_queue()

    def _build_ui(self):
        self.root.title(t("window_title"))
        self.root.geometry("640x260")
        self.root.minsize(640, 260)
        self.root.configure(bg="#f5f5f5")

        # ── Header ─────────────────────────────────────────────
        header = tk.Frame(self.root, bg="#0D1822", height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Seeed Jetson Develop Tool",
                 font=("Microsoft YaHei UI", 16, "bold"),
                 fg="#8DC21F", bg="#0D1822").pack(anchor="w", padx=24, pady=(16, 0))
        tk.Label(header, text=t("header_subtitle", version=APP_VERSION),
                 font=("Microsoft YaHei UI", 9),
                 fg="#B0BAC5", bg="#0D1822").pack(anchor="w", padx=24)

        # ── Body ───────────────────────────────────────────────
        body = tk.Frame(self.root, bg="#f5f5f5")
        body.pack(fill=tk.BOTH, expand=True, padx=24, pady=(16, 0))

        self.status_var = tk.StringVar(value=t("status_initial"))
        tk.Label(body, textvariable=self.status_var,
                 font=("Microsoft YaHei UI", 10),
                 bg="#f5f5f5", fg="#333", anchor="w").pack(fill=tk.X)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Install.Horizontal.TProgressbar",
                        troughcolor="#E1E5EA", background="#8DC21F",
                        thickness=18, borderwidth=0, lightcolor="#8DC21F",
                        darkcolor="#8DC21F")
        self.progress = ttk.Progressbar(body, length=580, mode="determinate",
                                        style="Install.Horizontal.TProgressbar")
        self.progress.pack(pady=(8, 12), fill=tk.X)

        # log toggle row
        toggle_row = tk.Frame(body, bg="#f5f5f5")
        toggle_row.pack(fill=tk.X)
        self.log_visible = False
        self.toggle_btn = tk.Label(toggle_row, text=t("log_show"),
                                   font=("Microsoft YaHei UI", 9),
                                   bg="#f5f5f5", fg="#5A6472", cursor="hand2")
        self.toggle_btn.pack(anchor="w")
        self.toggle_btn.bind("<Button-1>", lambda _e: self._toggle_log())

        # log area (hidden by default)
        self.log_frame = tk.Frame(body, bg="#f5f5f5")
        log_container = tk.Frame(self.log_frame, bg="#1E1E1E",
                                 highlightthickness=1, highlightbackground="#D0D5DB")
        log_container.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        scrollbar = tk.Scrollbar(log_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text = tk.Text(log_container, height=10,
                                font=("Consolas", 9),
                                bg="#1E1E1E", fg="#CCCCCC",
                                insertbackground="#CCCCCC",
                                yscrollcommand=scrollbar.set,
                                wrap=tk.WORD, bd=0, padx=8, pady=6)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        scrollbar.config(command=self.log_text.yview)

        # ── Footer ─────────────────────────────────────────────
        footer = tk.Frame(self.root, bg="#f5f5f5")
        footer.pack(fill=tk.X, padx=24, pady=16, side=tk.BOTTOM)

        self.primary_btn = tk.Button(footer, text=t("btn_install"),
                                     font=("Microsoft YaHei UI", 10, "bold"),
                                     bg="#8DC21F", fg="white",
                                     activebackground="#7AB01A",
                                     activeforeground="white",
                                     width=12, bd=0, cursor="hand2",
                                     relief="flat", padx=6, pady=6,
                                     command=self._on_primary)
        self.primary_btn.pack(side=tk.RIGHT, padx=(8, 0))
        self.secondary_btn = tk.Button(footer, text=t("btn_cancel"),
                                       font=("Microsoft YaHei UI", 10),
                                       bg="#E1E5EA", fg="#333",
                                       activebackground="#CBD1D8",
                                       width=10, bd=0, cursor="hand2",
                                       relief="flat", padx=6, pady=6,
                                       command=self._on_secondary)
        self.secondary_btn.pack(side=tk.RIGHT)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _toggle_log(self):
        if self.log_visible:
            self.log_frame.pack_forget()
            self.toggle_btn.config(text=t("log_show"))
            self.root.geometry("640x260")
            self.log_visible = False
        else:
            self.log_frame.pack(fill=tk.BOTH, expand=True)
            self.toggle_btn.config(text=t("log_hide"))
            self.root.geometry("640x500")
            self.log_visible = True

    def _append_log(self, text):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _set_progress(self, value, status):
        self.progress["value"] = value
        if status:
            self.status_var.set(status)

    def _on_primary(self):
        if self.finished:
            if self.success and self.launcher_path and os.path.exists(self.launcher_path):
                try:
                    os.startfile(self.launcher_path)  # type: ignore[attr-defined]
                except Exception:
                    pass
            self.root.destroy()
            return
        if self.install_thread and self.install_thread.is_alive():
            return
        self.primary_btn.config(state=tk.DISABLED, text=t("btn_installing"),
                                bg="#B6D672", disabledforeground="white")
        self.secondary_btn.config(state=tk.DISABLED)
        self.install_thread = threading.Thread(target=self._install_worker, daemon=True)
        self.install_thread.start()

    def _on_secondary(self):
        if self.finished:
            self.root.destroy()
            return
        if self.install_thread and self.install_thread.is_alive():
            if messagebox.askyesno(t("dlg_cancel_title"), t("dlg_cancel_body")):
                self.cancelled = True
                self.root.destroy()
        else:
            self.root.destroy()

    def _on_close(self):
        self._on_secondary()

    def _poll_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    self._set_progress(msg[1], msg[2])
                elif kind == "log":
                    self._append_log(msg[1])
                elif kind == "done":
                    self._on_install_done(True)
                elif kind == "error":
                    self._on_install_done(False, msg[1])
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    def _on_install_done(self, success, error=None):
        self.finished = True
        self.success = success
        if success:
            self.progress["value"] = 100
            self.status_var.set(t("status_done"))
            self.primary_btn.config(state=tk.NORMAL, text=t("btn_launch"),
                                    bg="#8DC21F", fg="white")
            self.secondary_btn.config(state=tk.NORMAL, text=t("btn_close"))
        else:
            self.status_var.set(t("status_failed"))
            self.primary_btn.config(state=tk.NORMAL, text=t("btn_close"),
                                    bg="#E1E5EA", fg="#333")
            self.secondary_btn.pack_forget()
            if not self.log_visible:
                self._toggle_log()
            messagebox.showerror(t("dlg_failed_title"),
                                 str(error) if error else t("dlg_unknown"))

    # ── Worker ────────────────────────────────────────────────
    def _install_worker(self):
        try:
            self._do_install()
            self.queue.put(("done",))
        except Exception as exc:
            self.queue.put(("log", "\n[ERROR] %s\n" % exc))
            self.queue.put(("error", exc))

    def _stage(self, key):
        for name, label_key, pct in STAGES:
            if name == key:
                label = t(label_key)
                self.queue.put(("progress", pct, label))
                self.queue.put(("log", "\n" + t("stage_arrow", label=label)))
                return

    def _log(self, text):
        self.queue.put(("log", text))

    def _install_python_automatically(self):
        """Download the official Python installer and run it silently.

        Goes through stage=install_python so the user sees a dedicated row
        on the progress bar. Uses per-user install (no admin prompt) with
        tcl/tk and pip included.
        """
        self._stage("install_python")
        tmp_dir = os.environ.get("TEMP") or os.path.expanduser("~")
        installer_path = os.path.join(
            tmp_dir, "python-%s-amd64.exe" % PYTHON_DOWNLOAD_VERSION)

        # Download with progress updates.
        self._log(t("log_url", url=PYTHON_DOWNLOAD_URL))
        try:
            self._download_with_progress(PYTHON_DOWNLOAD_URL, installer_path,
                                         progress_base=3, progress_span=5,
                                         label=t("progress_download"))
        except Exception as exc:
            raise RuntimeError(
                t("err_download_fail", err=exc, url=PYTHON_DOWNLOAD_URL)
            )

        # Run installer silently — per-user, add to PATH, include tcl/tk & pip.
        self.queue.put(("progress", 9, t("status_py_installing")))
        self._log(t("log_py_running"))
        install_args = [
            installer_path,
            "/quiet",
            "InstallAllUsers=0",
            "PrependPath=1",
            "Include_tcltk=1",
            "Include_pip=1",
            "Include_launcher=1",
            "SimpleInstall=1",
            "SimpleInstallDescription=Seeed Jetson Develop Tool dependencies",
        ]
        try:
            proc = subprocess.Popen(install_args, creationflags=SUBPROCESS_FLAGS)
            ret = proc.wait()
        except Exception as exc:
            raise RuntimeError(t("err_py_launch", err=exc))
        if ret != 0:
            raise RuntimeError(t("err_py_exit", code=ret, path=installer_path))
        self._log(t("log_py_done"))

        # Give Windows a beat to register the new PATH / py launcher.
        self.queue.put(("progress", 11, t("status_py_waiting")))
        try:
            os.remove(installer_path)
        except OSError:
            pass

    def _download_with_progress(self, url, dest, progress_base, progress_span,
                                label):
        """Stream a URL to disk, updating the progress bar as bytes arrive."""
        req = urllib.request.Request(url, headers={"User-Agent": "SeeedJetsonInstaller"})
        last_reported = -1
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            read = 0
            with open(dest, "wb") as f:
                while True:
                    if self.cancelled:
                        raise RuntimeError(t("err_cancelled"))
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    read += len(chunk)
                    if total:
                        pct_of_download = read / total
                        overall = progress_base + int(progress_span * pct_of_download)
                        if overall != last_reported:
                            self.queue.put((
                                "progress", overall,
                                "%s (%.1f/%.1f MB)" % (
                                    label, read / 1048576, total / 1048576),
                            ))
                            last_reported = overall
        self._log(t("log_download_done", path=dest, mb=read / 1048576))

    def _do_install(self):
        self._stage("check_python")
        python_cmd, python_label, python_ver = find_python(require_tkinter=True)
        if not python_cmd:
            # Check if there's a Python but it lacks tkinter, for a clearer log.
            partial_cmd, partial_label, partial_ver = find_python(require_tkinter=False)
            if partial_cmd:
                self._log(t("log_py_missing_tk",
                            label=partial_label, ver=partial_ver))
                self._log(t("log_will_install", ver=PYTHON_DOWNLOAD_VERSION))
            else:
                self._log(t("log_no_python", ver=PYTHON_DOWNLOAD_VERSION))
            self._install_python_automatically()
            # Re-scan after install.
            python_cmd, python_label, python_ver = find_python(require_tkinter=True)
            if not python_cmd:
                raise RuntimeError(t("err_reinstall"))
        self._log(t("log_python", label=python_label, ver=python_ver))

        self._stage("prepare_dir")
        local_app_data = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local")
        install_dir = os.path.join(local_app_data, APP_NAME)
        self.install_dir = install_dir
        if os.path.exists(install_dir):
            self._log(t("log_overwrite"))
        os.makedirs(install_dir, exist_ok=True)
        self._log(t("log_install_dir", dir=install_dir))

        self._stage("extract")
        archive_bytes = base64.b64decode(ARCHIVE_BASE64.strip())
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
            members = archive.namelist()
            total = max(1, len(members))
            for i, member in enumerate(members):
                if self.cancelled:
                    raise RuntimeError(t("err_cancelled"))
                archive.extract(member, install_dir)
                if i % 40 == 0 or i == total - 1:
                    pct = 10 + int(15 * (i + 1) / total)
                    self.queue.put(("progress", pct,
                                    t("progress_extract_n",
                                      i=i + 1, total=total)))
        self._log(t("log_extract_done", n=total))

        self._stage("create_venv")
        venv_dir = os.path.join(install_dir, "venv")
        self._run_capture(python_cmd + ["-m", "venv", venv_dir])
        venv_py = os.path.join(venv_dir, "Scripts", "python.exe")
        venv_pythonw = os.path.join(venv_dir, "Scripts", "pythonw.exe")
        app_python = venv_pythonw if os.path.exists(venv_pythonw) else venv_py
        self._log(t("log_venv_ready"))

        self._stage("upgrade_pip")
        try:
            self._run_capture([venv_py, "-m", "pip", "install", "--upgrade", "pip"])
        except Exception as exc:
            self._log(t("log_pip_fail", err=exc))

        self._stage("install_deps")
        requirements = os.path.join(install_dir, "requirements.txt")
        self._run_capture(
            [venv_py, "-m", "pip", "install", "--progress-bar", "off",
             "-r", requirements],
            progress_base=45, progress_span=45,
        )

        self._stage("shortcut")
        launcher_path = os.path.join(install_dir, "launch.vbs")
        debug_launcher_path = os.path.join(install_dir, "launch-debug.bat")
        run_script = os.path.join(install_dir, "run_v2.py")
        with open(launcher_path, "w", encoding="utf-8", newline="") as f:
            command = '"%s" "%s"' % (app_python, run_script)
            f.write('Set shell = CreateObject("WScript.Shell")\r\n')
            f.write('shell.Run "%s", 0, False\r\n' % command.replace('"', '""'))
        with open(debug_launcher_path, "w", encoding="utf-8", newline="") as f:
            f.write('@echo off\r\n')
            f.write('set SEEED_JETSON_DEBUG_CONSOLE=1\r\n')
            f.write('"%s" "%s" --debug-console %%*\r\n' % (venv_py, run_script))
        self.launcher_path = launcher_path
        self._log(t("log_launcher", path=launcher_path))
        self._log("Debug launcher: %s\n" % debug_launcher_path)
        try:
            create_desktop_shortcut(install_dir, app_python, '"%s"' % run_script)
            self._log(t("log_shortcut_ok"))
        except Exception as exc:
            self._log(t("log_shortcut_fail", err=exc))

        self.queue.put(("progress", 100, t("status_done")))

    def _run_capture(self, args, progress_base=None, progress_span=None):
        self._log("$ %s\n" % " ".join(args))
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, creationflags=SUBPROCESS_FLAGS,
        )
        line_count = 0
        assert proc.stdout is not None
        for line in proc.stdout:
            if self.cancelled:
                try:
                    proc.terminate()
                except Exception:
                    pass
                raise RuntimeError(t("err_cancelled"))
            self._log(line)
            line_count += 1
            if progress_base is not None and progress_span is not None:
                pct = progress_base + min(progress_span, line_count // 3)
                self.queue.put(("progress", pct,
                                t("progress_deps_lines", n=line_count)))
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(t("err_cmd_fail", code=ret, cmd=" ".join(args)))


def main():
    if os.name != "nt":
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(t("dlg_winonly_title"), t("dlg_winonly_body"))
        except Exception:
            print("This installer is for Windows only.")
        return 1

    if not _acquire_single_instance():
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(t("dlg_running_title"), t("dlg_running_body"))
            root.destroy()
        except Exception:
            print(t("log_running"))
        return 0

    try:
        root = tk.Tk()
        InstallerGUI(root)
        root.mainloop()
        return 0
    finally:
        _release_single_instance()


if __name__ == "__main__":
    raise SystemExit(main())
'''


# ── Build functions ───────────────────────────────────────────────────────────

def build_linux(archive_bytes: bytes) -> str:
    b64 = base64.b64encode(archive_bytes).decode("ascii")
    # Split into 76-char lines (standard base64 line length)
    lines = "\n".join(b64[i:i+76] for i in range(0, len(b64), 76))
    script = LINUX_TEMPLATE.format(
        app_name=APP_NAME,
        version=APP_VERSION,
        app_icon_png=APP_ICON_PNG,
    )
    return script + lines + "\n"


def build_windows_ps1(archive_bytes: bytes) -> str:
    b64 = base64.b64encode(archive_bytes).decode("ascii")
    lines = "\n".join(b64[i:i+76] for i in range(0, len(b64), 76))
    return WINDOWS_PS1_TEMPLATE.format(
        app_name=APP_NAME,
        version=APP_VERSION,
        app_icon_ico_win=APP_ICON_ICO.replace("/", "\\"),
        archive_base64=lines,
    )


def build_windows_bat() -> str:
    return WINDOWS_BAT_TEMPLATE


def build_windows_exe_source(archive_bytes: bytes) -> str:
    b64 = base64.b64encode(archive_bytes).decode("ascii")
    lines = "\n".join(b64[i:i+76] for i in range(0, len(b64), 76))
    return (
        WINDOWS_EXE_PY_TEMPLATE
        .replace("__APP_NAME__", APP_NAME)
        .replace("__APP_VERSION__", APP_VERSION)
        .replace("__APP_ICON_ICO__", APP_ICON_ICO)
        .replace("__ARCHIVE_BASE64__", lines)
    )


def ensure_pyinstaller(python_exe: str = sys.executable) -> Optional[str]:
    try:
        subprocess.run(
            [python_exe, "-m", "PyInstaller", "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return None
    except (OSError, subprocess.CalledProcessError):
        pass

    print()
    print(f"PyInstaller is not installed for {python_exe}. Installing with pip...",
          flush=True)
    try:
        subprocess.run(
            [python_exe, "-m", "pip", "install", "pyinstaller"],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return f"PyInstaller auto-install failed: {exc}"

    try:
        subprocess.run(
            [python_exe, "-m", "PyInstaller", "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return "PyInstaller was installed but is still not available."

    return None


def _python_has_tkinter(python_exe: str) -> bool:
    try:
        subprocess.run(
            [python_exe, "-c", "import tkinter, tkinter.ttk"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _find_python_with_tkinter() -> Optional[str]:
    """Return a Python interpreter path that has tkinter available.

    Searches (in order): sys.executable, `py -3`, `python`, `python3`, and
    common Windows install roots. Needed because PyInstaller cannot bundle
    tkinter if the building Python is missing it (e.g. PlatformIO's embedded
    penv, some minimal/embeddable distributions).
    """
    candidates = [sys.executable]

    if sys.platform == "win32":
        # py launcher — prefer newer versions first
        for tag in ("-3.13", "-3.12", "-3.11", "-3.10", "-3.9", "-3"):
            try:
                out = subprocess.check_output(
                    ["py", tag, "-c", "import sys; print(sys.executable)"],
                    stderr=subprocess.DEVNULL, text=True,
                ).strip()
                if out and out not in candidates:
                    candidates.append(out)
            except (OSError, subprocess.CalledProcessError):
                pass
        # common install roots
        for root in (
            r"C:\Python313", r"C:\Python312", r"C:\Python311", r"C:\Python310",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python313"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python310"),
        ):
            exe = os.path.join(root, "python.exe")
            if os.path.exists(exe) and exe not in candidates:
                candidates.append(exe)

    for name in ("python", "python3"):
        try:
            out = subprocess.check_output(
                [name, "-c", "import sys; print(sys.executable)"],
                stderr=subprocess.DEVNULL, text=True,
            ).strip()
            if out and out not in candidates:
                candidates.append(out)
        except (OSError, subprocess.CalledProcessError):
            pass

    for exe in candidates:
        if _python_has_tkinter(exe):
            return exe
    return None


def build_windows_exe(installer_source: Path) -> Tuple[Optional[Path], Optional[str]]:
    """Build a Windows .exe installer with PyInstaller when possible."""
    exe_path = DIST / "seeed-jetson-install-windows.exe"
    if sys.platform != "win32":
        return None, "Windows exe can only be built on Windows."

    builder_py = sys.executable
    if not _python_has_tkinter(builder_py):
        print()
        print(f"Current Python ({builder_py}) has no tkinter module — "
              f"searching for another interpreter...", flush=True)
        alt = _find_python_with_tkinter()
        if not alt:
            return None, (
                "No Python interpreter with tkinter found. Install the "
                "official Python from https://www.python.org/downloads/ "
                "(ensure 'tcl/tk and IDLE' is checked during setup), then "
                "re-run this build script. Installers generated without "
                "tkinter cannot launch the GUI."
            )
        print(f"Using {alt} for PyInstaller.", flush=True)
        builder_py = alt

    pyinstaller_error = ensure_pyinstaller(builder_py)
    if pyinstaller_error:
        return None, pyinstaller_error

    build_dir = ROOT / "build" / "installer-pyinstaller"
    icon_path = ROOT / APP_ICON_ICO
    cmd = [
        builder_py,
        "-m",
        "PyInstaller",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "seeed-jetson-install-windows",
        "--distpath",
        str(DIST),
        "--workpath",
        str(build_dir / "work"),
        "--specpath",
        str(build_dir),
    ]
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])
    cmd.append(str(installer_source))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        return None, f"PyInstaller failed with exit code {exc.returncode}."
    return exe_path, None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    DIST.mkdir(exist_ok=True)

    print(f"Building installers for {APP_NAME} v{APP_VERSION}")
    print(f"Source: {ROOT}")
    print(f"Output: {DIST}")
    print()

    # Create archives
    print("Creating Linux archive (tar.gz)...", end=" ", flush=True)
    tar_bytes = create_tar_gz()
    print(f"{len(tar_bytes) / 1024:.0f} KB")

    print("Creating Windows archive (zip)...", end=" ", flush=True)
    zip_bytes = create_zip()
    print(f"{len(zip_bytes) / 1024:.0f} KB")

    # Generate Linux installer
    linux_path = DIST / "seeed-jetson-install-linux.sh"
    print(f"Writing {linux_path.name}...", end=" ", flush=True)
    content = build_linux(tar_bytes)
    linux_path.write_text(content, encoding="utf-8")
    linux_path.chmod(0o755)
    print(f"{linux_path.stat().st_size / 1024:.0f} KB")

    # Generate Windows installer
    ps1_path = DIST / "seeed-jetson-install-windows.ps1"
    bat_path = DIST / "seeed-jetson-install-windows.bat"
    exe_source_path = ROOT / "build" / "installer-pyinstaller" / "seeed-jetson-install-windows.py"
    exe_source_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing {exe_source_path.relative_to(ROOT)}...", end=" ", flush=True)
    exe_source_path.write_text(build_windows_exe_source(zip_bytes), encoding="utf-8")
    print("done")

    print("Building seeed-jetson-install-windows.exe...", end=" ", flush=True)
    exe_path, exe_skip_reason = build_windows_exe(exe_source_path)
    if exe_path:
        print(f"{exe_path.stat().st_size / 1024:.0f} KB")
    else:
        print(f"skipped ({exe_skip_reason})")

    print(f"Writing {ps1_path.name}...", end=" ", flush=True)
    ps1_path.write_text(build_windows_ps1(zip_bytes), encoding="utf-8")
    print(f"{ps1_path.stat().st_size / 1024:.0f} KB")

    bat_path.write_text(build_windows_bat(), encoding="utf-8")
    print(f"Writing {bat_path.name}... done")

    print()
    print("Done! Installers:")
    print(f"  Linux:   {linux_path}")
    if exe_path:
        print(f"  Windows: {exe_path}")
        print(f"  Windows fallback: {bat_path}  (runs {ps1_path.name})")
    else:
        print(f"  Windows exe: skipped - {exe_skip_reason}")
        print(f"  Windows fallback: {bat_path}  (runs {ps1_path.name})")
    print()
    print("Linux usage:")
    print("  chmod +x seeed-jetson-install-linux.sh")
    print("  ./seeed-jetson-install-linux.sh")
    print()
    print("Windows usage:")
    if exe_path:
        print("  Double-click seeed-jetson-install-windows.exe")
    else:
        print("  Build on Windows with PyInstaller to produce seeed-jetson-install-windows.exe")
    print("  Fallback: double-click seeed-jetson-install-windows.bat")
    print("  Fallback: powershell -ExecutionPolicy Bypass -File seeed-jetson-install-windows.ps1")


if __name__ == "__main__":
    main()
