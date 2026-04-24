# Seeed Jetson Develop Tool

An all-in-one AI development workbench for Seeed Studio Jetson products — covering everything from firmware flashing to app deployment.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey.svg)]()

[中文文档](https://github.com/Seeed-Projects/Seeed-Jetson-DevelopTool/blob/main/README_zh.md)

![UI Preview](https://raw.githubusercontent.com/Seeed-Projects/Seeed-Jetson-DevelopTool/main/assets/Reference-UI.png)

---

## Features

| Module | Status | Description |
|--------|--------|-------------|
| Flash Center | ✅ | Download, verify (SHA256), and flash firmware for all Jetson series with one click |
| Device Management | ✅ | Quick diagnostics, peripheral detection, real-time device info |
| App Market | ✅ | Browse and install AI apps — YOLOv8, Ollama, DeepSeek, Node-RED, and more |
| Skills | ✅ | 50+ built-in automation skills covering drivers, AI deployment, and system tuning |
| Remote Dev | ✅ | SSH connection, VS Code Server, Jupyter Lab, VNC remote desktop, AI agent install |
| PC Network Sharing | ✅ | Share PC internet to Jetson over Ethernet, with automatic proxy forwarding |
| Jetson Init | ✅ | First-boot serial terminal wizard for username, network, and system setup |
| Community | ✅ | Quick links to Wiki, forum, Discord, and video tutorials |

---

## Requirements

- **Host OS**: Ubuntu 20.04 / 22.04 / 24.04 (Linux recommended for flashing)
- **Python**: 3.8+
- **Dependencies**: PyQt5, paramiko, requests

---

## Installation

```bash
pip install seeed-jetson-developer
```

Launch the GUI:

```bash
seeed-jetson-developer
```

Install from source:

```bash
git clone https://github.com/Seeed-Projects/Seeed-Jetson-DevelopTool.git
cd Seeed-Jetson-DevelopTool
pip install .
```

Or run directly from the repository:

```bash
python3 run_v2.py
```

---

## Supported Devices

### reComputer Super (Orin NX / Nano)
| Model | L4T |
|-------|-----|
| J4012s (16GB) / J4011s (8GB) | 36.4.3 |
| J3011s (8GB) / J3010s (4GB) | 36.4.3 |

### reComputer Mini (Orin NX / Nano)
| Model | L4T |
|-------|-----|
| J4012mini / J4011mini | 36.3.0, 35.5.0 |
| J3011mini / J3010mini | 36.4.3, 36.3.0, 35.5.0 |

### reComputer Robotics (GMSL, Orin NX / Nano)
| Model | L4T |
|-------|-----|
| J4012robotics / J4011robotics | 36.4.3 |
| J3011robotics / J3010robotics | 36.4.3 |

### reComputer Classic (Orin NX / Nano)
| Model | L4T |
|-------|-----|
| J4012classic / J4011classic | 36.4.3, 36.4.0, 36.3.0, 35.5.0 |
| J3011classic / J3010classic | 36.4.3, 36.4.0, 36.3.0, 35.5.0 |

### reComputer Industrial (Orin NX / Nano)
| Model | L4T |
|-------|-----|
| J4012industrial / J4011industrial | 36.4.3, 36.4.4, 36.4.0, 36.3.0, 35.5.0, 35.3.1 |
| J3011industrial / J3010industrial | 36.4.3, 36.4.0, 36.3.0, 35.5.0, 35.3.1 |
| J2012industrial / J2011industrial (Xavier NX) | 35.5.0, 35.3.1 |

### reServer Industrial (Orin NX / Nano)
| Model | L4T |
|-------|-----|
| J4012reserver / J4011reserver | 36.4.3, 36.4.0, 36.3.0 |
| J3011reserver / J3010reserver | 36.4.3, 36.4.0, 36.3.0 |

### J501 Carrier Board (AGX Orin)
| Model | L4T |
|-------|-----|
| 64GB / 32GB (standard + GMSL) | 36.4.3, 36.3.0, 35.5.0 |

---

## Flash Workflow

1. Select your device model and L4T version
2. Click **Download / Extract BSP** — firmware is downloaded with SHA256 verification and resume support
3. Put the device into Recovery mode (hold Recovery button while powering on)
4. Click **Detect Device** to confirm USB connection
5. Click **Start Flash** — takes 2–10 minutes

> Flashing requires a Linux host. Windows users can use WSL2 with USB passthrough.

---

## Remote Development

Connect to Jetson over SSH and access:

- **VS Code Server** — browser-based IDE running on Jetson
- **Jupyter Lab** — interactive Python notebooks
- **VNC Remote Desktop** — full graphical desktop via browser (noVNC) or VNC client
- **AI Agent Install** — install Claude Code, Codex, or OpenClaw CLI on Jetson
- **PC Network Sharing** — share PC internet to Jetson, with automatic proxy detection and forwarding

---

## Skills

50+ built-in skills across these categories:

- **Drivers & Fixes** — USB-WiFi (88x2bu), 5G modules, Bluetooth conflicts, NVMe boot, Docker cleanup
- **AI / LLM** — PyTorch, Ollama, DeepSeek, Qwen2, LeRobot, vLLM
- **Vision / YOLO** — YOLOv8, DeepStream, NVBLOX, depth estimation
- **Network & Remote** — VS Code Server, VNC, SSH keys, proxy setup
- **System Tuning** — max performance mode, swap config, fan control, cache cleanup

Community skills in [OpenClaw](https://github.com/Seeed-Studio/openclaw) format are auto-loaded from the `skills/openclaw/` directory.

---

## CLI

```bash
# Launch the packaged GUI entry point
python3 -m seeed_jetson_develop.cli
```

---

## Documentation

- [Quick Start](https://github.com/Seeed-Projects/Seeed-Jetson-DevelopTool/blob/main/docs/QUICKSTART.md) — Quick start guide
- [Usage](https://github.com/Seeed-Projects/Seeed-Jetson-DevelopTool/blob/main/docs/USAGE.md) — CLI reference
- [GUI Guide](https://github.com/Seeed-Projects/Seeed-Jetson-DevelopTool/blob/main/docs/GUI_GUIDE.md) — GUI user guide

---

## Support

- Wiki: https://wiki.seeedstudio.com/
- Forum: https://forum.seeedstudio.com/
- Discord: https://discord.gg/eWkprNDMU7

---

## License

MIT
