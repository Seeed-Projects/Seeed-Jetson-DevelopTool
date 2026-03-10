# jetson-develop

面向 Seeed Studio Jetson 全系列产品的 AI 开发工具集，包含可执行的 Agent Skills 和客户端应用。

## 设计理念

本项目围绕两个核心维度构建：

- **Skills** — 将 Jetson 开发中的高频操作（环境配置、模型部署、驱动适配、故障排查等）封装为 AI Agent 可直接执行的技能包，支持 OpenClaw / Claude Code / Codex (AGENTS.md) 三种主流 Agent 格式
- **Apps** — 提供烧录、诊断、项目脚手架等客户端工具，配合 Skills 实现从刷机到部署的完整开发流程

Skills 覆盖的领域：

| 维度 | 示例 |
|------|------|
| CV / 大模型 / AI 生成 / 机器人 | YOLOv8、DeepSeek、TTS (Dia)、LeRobot |
| 本地部署 / 容器部署 | Ollama、Frigate、NVIDIA Demo 容器 |
| 开发工具链 | PyTorch 安装、vLLM、Docker、jtop |
| 驱动与 BSP | USB-WiFi 适配、SPI、EtherCAT、内核模块编译 |
| 故障排查 | 浏览器修复、SSD 启动、UUID 错误、apt upgrade 防护 |

## 项目结构

```
jetson-develop/
├── SKILLS/
│   ├── openclaw/          # OpenClaw 格式 (SKILL.md) — 优先验证平台
│   ├── claude/            # Claude Code 格式 (CLAUDE.md)
│   ├── codex/             # Codex / AGENTS.md 开放标准格式
│   └── .snapshots/
├── apps/
│   ├── client/            # CLI 入口
│   ├── flashing/          # Jetson 刷机工具 (CLI + GUI)
│   ├── diagnostics/       # 设备诊断日志收集
│   ├── development/       # 项目脚手架生成
│   └── projects/          # 用户项目目录
└── README.md
```

## Skills

当前共 **94 个 Skills**，每个 Skill 同时提供三种 Agent 格式：

| 格式 | 指令文件 | 安装路径 | 说明 |
|------|---------|---------|------|
| OpenClaw | `SKILL.md` | `~/.agents/skills/<name>/` | 优先验证平台 |
| Claude | `CLAUDE.md` | `~/.claude/skills/<name>/` | Claude Code 适配 |
| Codex | `AGENTS.md` | `~/.codex/skills/<name>/` | OpenAI 开放标准 |

每个 Skill 目录结构：

```
<skill-name>/
├── SKILL.md / CLAUDE.md / AGENTS.md   # Agent 指令文件
├── scripts/                            # 可执行脚本（可选）
└── references/                         # 参考数据（可选）
```

### Skill 分类概览

**计算机视觉**：yolov5-object-detection、yolov8-trt、yolov8-deepstream-trt、yolov8-custom-classification、yolov11-depth-distance、yolov26_jetson、train-deploy-yolov8、zero-shot-detection、dashcamnet-xavier-nx-multicamera、traffic-deepstream、maskcam-nano、ai-nvr

**生成式 AI**：deepseek-quick-deploy、deploy-deepseek-mlc、deploy-ollama-anythingllm、deploy-riva-llama2、quantized-llama2-7b-mlc、generative-ai-intro、finetune-llm-llama-factory、local-llm-text-to-image、langchain-output-formatting、local-rag-llamaindex、llama-cpp-rpc-distributed

**多模态 AI**：run-vlm、deploy-live-vlm-webui、speech-vlm、vlm-warehouse-guard、local-chatbot-multimodal、deploy-depth-anything-v3、deploy-efficient-vision-engine

**物理 AI / 机器人**：lerobot-env-setup、gr00t-n1-5-deploy-thor、gr00t-n1-6-deploy-agx、local-chatbot-physical、voice-llm-motor-control、voice-llm-reachy-mini-multimodal、voice-llm-reachy-mini-physical、deploy-nvblox、pinocchio-install、j501-viola-fruit-sorting

**语音 AI**：whisper-realtime-stt、realtime-subtitle-recorder、deploy-dia

**开发工具**：torch-install、jetson-docker-setup、jetson-ai-tools、vnc-setup、gpt-oss-live、llm-interface-control、nvstreamer-setup、no-code-edge-ai

**驱动与 BSP**：bsp-source-build、diy-bsp-build、ko-module-build、spi-enable-jetsonnano、usb-wifi-88x2bu-setup、ethercat-setup、ethercat-communication、imx477-a603-setup、recomputer-veye-compat-fix、l4t-differences

**刷机与系统**：jetpack-flash-wsl2、jetpack-ota-update、jetpack-jetson-overview、jetpack5-ssd-boot-fix、backup-restore、disk-encryption、ota-deploy、software-package-upgrade、fix-browser-snap-jetson、uuid-error-fix、usb-timeout-during-flashing、security-scan、system-log-j30-j40

**第三方平台集成**：allxon-setup、allxon-ota-update、alwaysai-setup、cochl-sense-setup、cvedia-setup、deciai-setup、deploy-frigate、gapi-setup、hardhat-setup、lumeo-setup、neqto-engine-setup、roboflow-setup、scailable-setup

**知识库**：jetson-faq、jetson-resource-index、jetson-project-gallery、jetson-tutorial-exercises

### 编写新 Skill

参考各格式目录下的 `HOW_TO_WRITE_SKILLS.md`：

- [OpenClaw 编写指南](SKILLS/openclaw/HOW_TO_WRITE_SKILLS.md)
- [Claude 编写指南](SKILLS/claude/HOW_TO_WRITE_SKILLS.md)
- [Codex 编写指南](SKILLS/codex/HOW_TO_WRITE_SKILLS.md)

核心原则：
1. 长操作拆分为 Phase，每个 Phase 幂等可重入
2. 使用 `[install]` / `[STOP]` / `[OK]` 日志协议让 Agent 可解析输出
3. 每个 Skill 必须包含 Failure Decision Table

## Apps

### 刷机工具 (`apps/flashing/`)

支持 Seeed 全系列 Jetson 产品的固件刷写，提供 CLI 和 GUI 两种模式。

```bash
# CLI
seeed-jetson-flash flash -p j4012mini -l 36.3.0

# GUI
seeed-jetson-flash gui
```

详见 [apps/flashing/README.md](apps/flashing/README.md)

### 诊断工具 (`apps/diagnostics/`)

一键收集 Jetson 设备的系统信息、日志、硬件状态，打包为 tar.gz 归档。

```bash
bash apps/diagnostics/collect_jetson_logs.sh
```

### 项目脚手架 (`apps/development/`)

按模板（cv / genai / robotics / general）快速创建 Jetson 应用项目结构。

```bash
bash apps/development/create_app_workspace.sh my-app cv
```

### CLI 入口 (`apps/client/`)

统一的交互式命令行入口，整合刷机、脚手架、诊断功能。

```bash
bash apps/client/jetson_dev_cli.sh
```

## 快速开始

```bash
# 克隆仓库
git clone <repo-url>
cd jetson-develop

# 安装刷机工具
pip install -e apps/flashing/

# 使用 CLI
bash apps/client/jetson_dev_cli.sh
```

Skills 的使用取决于你的 Agent 平台：

```bash
# OpenClaw
cp -r SKILLS/openclaw/<skill-name> ~/.agents/skills/<skill-name>

# Claude Code
cp -r SKILLS/claude/<skill-name> ~/.claude/skills/<skill-name>

# Codex / AGENTS.md 兼容 Agent
cp -r SKILLS/codex/<skill-name> ~/.codex/skills/<skill-name>
```


## 技术支持

- Wiki: https://wiki.seeedstudio.com/
- 论坛: https://forum.seeedstudio.com/
- Discord: https://discord.gg/eWkprNDMU7

## License

MIT
