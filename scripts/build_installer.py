#!/usr/bin/env python3
"""
Build self-extracting installer packages for Seeed Jetson Develop Tool.

Usage:
    python scripts/build_installer.py

Output:
    dist/seeed-jetson-install-linux.sh
    dist/seeed-jetson-install-windows.ps1
    dist/seeed-jetson-install-windows.bat  (launcher)
"""

import base64
import filecmp
import io
import os
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).parent.parent
DIST = ROOT / "dist"
APP_NAME = "seeed-jetson-develop"
PACKAGE_NAME = "seeed-jetson-developer"
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


def read_app_version() -> str:
    """Keep installer metadata aligned with the packaged app version."""
    init_file = ROOT / "seeed_jetson_develop" / "__init__.py"
    text = init_file.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"Could not find __version__ in {init_file}")
    return match.group(1)


APP_VERSION = read_app_version()


def _asset_duplicates() -> set[Path]:
    """Return relative paths that exist identically in both top-level and package assets.

    The runtime resolver (seeed_jetson_develop.resources.resolve_runtime_path)
    already falls back from ``assets/<rel>`` to ``seeed_jetson_develop/assets/<rel>``,
    so embedding both copies is redundant and bloats the installer.
    """
    dup: set[Path] = set()
    root_assets = ROOT / "assets"
    pkg_assets = ROOT / "seeed_jetson_develop" / "assets"
    if not root_assets.exists() or not pkg_assets.exists():
        return dup
    for src in root_assets.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(root_assets)
        dst = pkg_assets / rel
        if dst.exists() and filecmp.cmp(src, dst, shallow=False):
            dup.add(rel)
    return dup


_ASSET_DUPLICATES = _asset_duplicates()


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
    # Omit root assets that are byte-identical to the package copy; the runtime
    # resolver will fall back to seeed_jetson_develop/assets/<rel> automatically.
    if (
        len(rel.parts) >= 2
        and rel.parts[0] == "assets"
        and rel.parts[1] != "seeed_jetson_develop"
    ):
        if Path(*rel.parts[1:]) in _ASSET_DUPLICATES:
            return True
    # The app loads skills from seeed_jetson_develop/skills/; the top-level
    # skills/ directory is the source copy and is redundant in the installer.
    if rel.parts[0] == "skills" and len(rel.parts) >= 2:
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
"$VENV_PY" -m pip install --upgrade pip --no-input --disable-pip-version-check --quiet || warn "pip upgrade failed, continuing..."
info "Installing dependencies (this may take a few minutes)..."
"$VENV_PY" -m pip install --no-input --disable-pip-version-check -r "$INSTALL_DIR/requirements.txt" --quiet
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
    & $VenvPy -m pip install --upgrade pip --no-input --disable-pip-version-check --quiet
    Write-Ok "pip upgraded"
}} catch {{
    Write-Warn "pip upgrade failed (non-fatal): $_"
}}

# ── Install dependencies ──────────────────────────────────────────────────────
Write-Step "Installing dependencies (this may take a few minutes)..."
& $VenvPy -m pip install --no-input --disable-pip-version-check -r "$InstallDir\requirements.txt" --quiet
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


def ensure_build_package(python_exe: str = sys.executable) -> Optional[str]:
    check_cmd = [python_exe, "-m", "build", "--version"]
    try:
        subprocess.run(
            check_cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=ROOT.parent,
        )
        return None
    except (OSError, subprocess.CalledProcessError):
        pass

    print()
    print(f"Python package 'build' is not available for {python_exe}. Installing with pip...",
          flush=True)
    try:
        subprocess.run(
            [python_exe, "-m", "pip", "install", "build"],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return f"build package auto-install failed: {exc}"

    try:
        subprocess.run(
            check_cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=ROOT.parent,
        )
    except (OSError, subprocess.CalledProcessError):
        return "The 'build' package was installed but is still not available."

    return None


def build_python_distributions() -> Tuple[Path, Path]:
    """Build the PyPI artifacts and fail fast if the wheel is missing."""
    build_error = ensure_build_package(sys.executable)
    if build_error:
        raise RuntimeError(build_error)

    cmd = [
        sys.executable,
        "-m",
        "build",
        "--sdist",
        "--wheel",
        "--outdir",
        str(DIST),
        str(ROOT),
    ]
    try:
        subprocess.run(cmd, check=True, cwd=ROOT.parent)
    except subprocess.CalledProcessError as exc:
        if sys.platform != "win32":
            raise RuntimeError(
                f"Python package build failed with exit code {exc.returncode}."
            ) from exc

        print()
        print("Standard `python -m build` failed on Windows. Falling back to setup.py sdist/bdist_wheel...",
              flush=True)
        fallback_cmd = [
            sys.executable,
            "setup.py",
            "sdist",
            "bdist_wheel",
            "--dist-dir",
            str(DIST),
        ]
        try:
            subprocess.run(fallback_cmd, check=True, cwd=ROOT)
        except subprocess.CalledProcessError as fallback_exc:
            raise RuntimeError(
                "Python package build failed with both `python -m build` "
                f"(exit {exc.returncode}) and setup.py fallback "
                f"(exit {fallback_exc.returncode})."
            ) from fallback_exc

    dist_name = PACKAGE_NAME.replace("-", "_")
    sdist_path = DIST / f"{dist_name}-{APP_VERSION}.tar.gz"
    wheel_path = DIST / f"{dist_name}-{APP_VERSION}-py3-none-any.whl"
    missing = [path.name for path in (sdist_path, wheel_path) if not path.exists()]
    if missing:
        raise RuntimeError(
            "Python package build did not produce expected artifact(s): "
            + ", ".join(missing)
        )
    return sdist_path, wheel_path


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    DIST.mkdir(exist_ok=True)

    print(f"Building distributions for {APP_NAME} v{APP_VERSION}")
    print(f"Source: {ROOT}")
    print(f"Output: {DIST}")
    print()

    print("Building Python package (sdist + wheel)...")
    sdist_path, wheel_path = build_python_distributions()
    print(f"  sdist: {sdist_path}")
    print(f"  wheel: {wheel_path}")
    print()

    print(f"Building installers for {APP_NAME} v{APP_VERSION}")
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
    print(f"Writing {ps1_path.name}...", end=" ", flush=True)
    ps1_path.write_text(build_windows_ps1(zip_bytes), encoding="utf-8")
    print(f"{ps1_path.stat().st_size / 1024:.0f} KB")

    bat_path.write_text(build_windows_bat(), encoding="utf-8")
    print(f"Writing {bat_path.name}... done")

    print()
    print("Done! Installers:")
    print(f"  sdist:   {sdist_path}")
    print(f"  wheel:   {wheel_path}")
    print(f"  Linux:   {linux_path}")
    print(f"  Windows: {bat_path}  (runs {ps1_path.name})")
    print()
    print("Linux usage:")
    print("  chmod +x seeed-jetson-install-linux.sh")
    print("  ./seeed-jetson-install-linux.sh")
    print()
    print("Windows usage:")
    print("  Double-click seeed-jetson-install-windows.bat")
    print("  Fallback: powershell -ExecutionPolicy Bypass -File seeed-jetson-install-windows.ps1")


if __name__ == "__main__":
    main()
