# Seeed Jetson Developer Tool v0.2.0

## Highlights

The biggest update since `v0.1.7`, focusing on cross-platform stability, JetPack 7.2 support, and remote development experience:

- **Migrated to PyQt6** with compatibility/regression tests for Python 3.10–3.13.
- **Full JetPack 7.2 support**: 27+ new BSP records and JP6.1/6.2 → JP7.2 OTA upgrade paths for Industrial/Robotics series.
- **Major remote file-transfer upgrade**: bi-directional, recursive folder upload/download, drag-and-drop, and byte-based progress.
- **Enhanced AI assistant**: auto-detects Anthropic / OpenAI / Codex providers and reads local config as fallback.
- **New Seeed Device Manager installer** in the App Market.

---

## Installation

### Linux / macOS (self-extracting script)

```bash
chmod +x seeed-jetson-install-linux.sh
./seeed-jetson-install-linux.sh
```

### Windows (executable installer)

Double-click `seeed-jetson-install-windows.exe`.

> The Windows `.exe` must be rebuilt on a Windows machine with PyInstaller.

### Any platform (pip / wheel)

```bash
pip install seeed-jetson-developer==0.2.0
```

Use `--user` if you do not have admin/root privileges.

Verify:

```bash
seeed-jetson-developer --version
# Expected: 0.2.0
```

```python
import seeed_jetson_develop
print(seeed_jetson_develop.__version__)
```

The `.whl` is `py3-none-any`, so it is cross-platform and contains no platform-specific binaries.

---

## What's New

### Core Runtime

- **Auto dependency management**: the launcher now detects and installs missing Python packages and system apt dependencies before starting the GUI.
- **PyQt6 migration**: migrated the whole project from Qt5 to PyQt6; added `test_qt_compatibility.py` and other regression tests.

### Flash & BSP Data

- **JetPack 7.2 BSP records**: merged 27 JetPack 7.2 BSP records covering J401, J301, ReServer Industrial, and more.
- **Cache merge fix**: fixed `data_update.py` so old local cache no longer overwrites newer in-package BSP records.
- **AGX Orin 64G JP7.2 link**: corrected the BSP download link to `mfi_seeed-agx-orin-64g-kit.tar.gz`.
- **Flash page polish**: L4T versions are now sorted descending with JetPack 7.2 selected by default; removed duplicate `j401-robotics-orin-nx/nano-*` records.
- **Recovery labels**: changed confusing `2/S3` and `3/S2` labels on AGX Orin recovery steps to plain button numbers.

### OTA Upgrades

- **JP6.1/6.2 → JP7.2 paths**: added OTA upgrade paths for reComputer Industrial, Robotics J501, Robotics Mini J501, and Robotics J401, all using SDK payloads based on L4T 39.2.0.
- **Faster & safer downloads**: large payload files now use `aria2c` multi-connection downloads.
- **Integrity checks**: added SHA256 verification after download.
- **Cache management**: added a cache card with a one-click clear-cache button (i18n supported).
- **Progress UX**: switched to 64-bit signals and added download speed / ETA display.
- **SharePoint URL fix**: downloader now auto-appends `download=1` to SharePoint payload URLs.

### Remote Development & File Transfer

- **Recursive SFTP upload**: upload local folders to Jetson while preserving directory structure.
- **Recursive SFTP download**: download remote folders from Jetson to PC while preserving directory structure.
- **Folder navigation**: double-click folders in the download dialog to navigate.
- **Drag-and-drop**: SSH file transfer now supports drag-and-drop.
- **Progress sync**: fixed the progress-bar staying at 0% while logs already showed 4%; progress is now based on total bytes transferred.
- **JetPack 5 static IP**: before applying a static IP over serial, competing NetworkManager connections on the target interface are disabled, fixing SSH failures when the default wired connection grabs `eth1`.
- **UI polish**: `Configure Network IP` and `Network Share` buttons in Jetson Initialization are now theme-green primary buttons.

### AI Assistant

- **Provider auto-detection**: automatically chooses Anthropic or OpenAI protocol; OpenAI endpoint is recognized by matching local Codex `base_url`.
- **Codex support**: reads Codex CLI `config.toml` and Claude Code / Claude Desktop `settings.json` as fallback config sources.
- **Explicit provider**: you can force `ai_provider` to `anthropic` or `openai` in `~/.config/seeed-jetson-tool/config.json`.
- **Proxy cleanup**: removed hard-coded third-party proxy domains; only official `api.anthropic.com` remains.
- **Socks proxy crash fix**: both Anthropic and OpenAI branches use `httpx.Client(trust_env=False)` to avoid crashes caused by system socks proxies like `socks://127.0.0.1:7890/`.

### App Market

- **Seeed Device Manager**: added a one-click installer entry for Seeed Device Manager.

### Documentation & Telemetry

- **Dynamic download chart**: added `scripts/generate_downloads_chart.py` and a GitHub Actions workflow to update `assets/downloads-chart.svg` daily.
- **README badges**: added PyPI total/monthly download badges and the live download trend chart to `README.md` and `README_zh.md`.

---

## Bug Fixes

- Fixed macOS + PyQt6 crash caused by `QPoint` vs `QPointF` in `QLinearGradient`.
- Stabilized macOS app-install flow and added regression tests.
- Fixed JetPack 5 static IP being overridden by competing NM connections.
- Fixed SFTP progress bar out of sync with log output.
- Fixed AGX Orin 64G JetPack 7.2 BSP download link.
- Fixed SharePoint payload URLs missing `download=1`.
- Fixed dependency-check package-name casing by using `importlib.metadata`.
- Prevented dependency-check from prompting for `sudo` by default.
- Fixed IP-input validation and OTA reboot bugs.
- Fixed confusing recovery labels for AGX Orin.
- Fixed socks-proxy crash in AI chat.

---

## Notes

- The wheel is `py3-none-any` and cross-platform.
- If you previously installed via the old `~/.local/share/seeed-jetson-develop` directory or a desktop shortcut, remove that directory or re-run the installer to avoid stale `v0.1.9.post4` sources shadowing the new PyPI package.

---

## Assets

| File | Description |
|---|---|
| `seeed_jetson_developer-0.2.0-py3-none-any.whl` | Cross-platform wheel |
| `seeed_jetson_developer-0.2.0.tar.gz` | Source distribution |
| `seeed-jetson-install-linux.sh` | Linux self-extracting installer |
| `seeed-jetson-install-windows.exe` | Windows installer (requires Windows build) |
| `seeed-jetson-install-windows.ps1` | Windows PowerShell fallback installer |
| `seeed-jetson-install-windows.bat` | Windows batch fallback launcher |

<!-- Replace the links below with the actual uploaded asset URLs -->
- Download: `seeed_jetson_developer-0.2.0-py3-none-any.whl`
- Download: `seeed_jetson_developer-0.2.0.tar.gz`
- Download: `seeed-jetson-install-linux.sh`
- Download: `seeed-jetson-install-windows.exe`
