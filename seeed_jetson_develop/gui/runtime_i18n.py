"""Deprecated runtime i18n compatibility layer for legacy V2 widgets.

New or actively modified pages should use ``seeed_jetson_develop.gui.i18n``
with key-based locale files. This module remains only as a compatibility
fallback for untranslated legacy widget trees.
"""

from __future__ import annotations

import re

from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


ZH_EN_EXACT = {
    # ── devices/page.py ──────────────────────────────────────────────────────
    "Jetson 型号": "Jetson Model",
    "L4T 版本": "L4T Version",
    "内存使用": "Memory",
    "IP 地址": "IP Address",
    "🔍 快速诊断": "Quick Diagnostics",
    "仅运行诊断": "Diagnostics Only",
    "自动检查网络、GPU Torch、Docker、jtop、摄像头等关键组件状态": "Auto-check network, GPU Torch, Docker, jtop, cameras, and other key components",
    "🔌 外设状态": "Peripherals",
    "仅检测外设": "Peripherals Only",
    "存储": "Storage",
    "温度": "Temperature",
    "待检测": "Pending",
    "检测中…": "Checking...",
    "▶  运行全部检测": "Run All Checks",
    "Jetson 初始化": "Jetson Init",
    "安装 PyTorch": "Install PyTorch",
    "安装 PyTorch for Jetson": "Install PyTorch for Jetson",
    "安装日志": "Install Log",
    "▶  开始安装": "Start Install",
    "■  停止": "Stop",
    # ── diagnostics.py — DiagItem names ──────────────────────────────────────
    "网络连接": "Network",
    "Docker 服务": "Docker",
    "USB 摄像头": "USB Camera",
    "启动磁盘": "Boot Disk",
    "蓝牙": "Bluetooth",
    "HDMI 显示": "HDMI Display",
    # ── diagnostics.py — parse result status texts ────────────────────────────
    "正常": "OK",
    "无法连接": "Unreachable",
    "CUDA 可用": "CUDA OK",
    "CPU 模式": "CPU only",
    "未安装": "Not installed",
    "运行中": "Running",
    "未运行": "Not running",
    "已安装": "Installed",
    "未检测到": "Not found",
    "已连接": "Connected",
    "未连接": "Disconnected",
    "检测失败": "Check failed",
    "串口连接 — 输入凭据": "Serial Login",
    "当前未建立 SSH 连接，将通过串口执行检测。": "No SSH connection. Detection will run over serial.",
    "串口设备": "Serial Port",
    "用户名": "Username",
    "密码": "Password",
    "输入 Jetson 登录密码": "Enter Jetson login password",
    "刷新": "Refresh",
    "确定": "OK",
    "取消": "Cancel",
    "设备管理": "Devices",
    "查看已连接设备状态、运行诊断与外设检测": "View device status, run diagnostics, and check peripherals",

    # ── apps/page.py ─────────────────────────────────────────────────────────
    "应用市场": "App Market",
    "浏览、安装、运行并管理 Jetson 应用与示例": "Browse, install, run, and manage Jetson apps and demos",
    "全部": "All",
    "已安装": "Installed",
    "搜索应用...": "Search apps...",
    "刷新状态": "Refresh",
    "检测中...": "Checking...",
    "可安装": "Available",
    "卸载": "Uninstall",
    "安装": "Install",
    "运行": "Run",
    "清理": "Clean",
    "暂无符合当前筛选条件的应用": "No apps match the current filters",
    "需要远程连接": "Remote Connection Required",
    "当前运行在 PC 上，安装或部署前必须先在「远程开发」页连接 Jetson 设备。": "Running on PC. Connect to a Jetson in the Remote page before installing.",
    "L4T 检测失败": "L4T Detection Failed",
    "L4T 版本不兼容": "Incompatible L4T Version",
    "提示": "Notice",
    "确认清理": "Confirm Clean",
    "确认卸载": "Confirm Uninstall",
    "安装步骤": "Install Steps",
    "卸载步骤": "Uninstall Steps",
    "运行步骤": "Run Steps",
    "清理步骤": "Clean Steps",
    "安装日志": "Install Log",
    "卸载日志": "Uninstall Log",
    "运行日志": "Run Log",
    "清理日志": "Clean Log",
    "▶  开始安装": "Start Install",
    "▶  开始卸载": "Start Uninstall",
    "▶  开始运行": "Start Run",
    "▶  开始清理": "Start Clean",
    "问 AI": "Ask AI",
    "关闭": "Close",

    # ── skills/page.py ────────────────────────────────────────────────────────
    "Skills 中心": "Skills Center",
    "自动化执行环境修复、驱动适配与应用部署任务": "Automate environment fixes, driver setup, and app deployment",
    "Skills 是可编排的自动化执行单元": "Skills are composable automation units",
    "正在加载 OpenClaw / Claude / Codex 技能库…": "Loading OpenClaw / Claude / Codex skill libraries...",
    "🔍  搜索 Skill…": "Search skills...",
    "精选": "Featured",
    "全部 Skills": "All Skills",
    "开始运行": "Run",
    "停止": "Stop",
    "失败重试": "Retry on Fail",
    "无可执行命令": "No runnable commands",
    "执行日志": "Execution Log",
    "已取消": "Cancelled",
    "风险提示：": "Risk:",
    "需要先连接设备": "Connect a Device First",
    "请先连接 Jetson 设备": "Connect to a Jetson device first",
    "下一步这样做": "Next Steps",
    "知道了": "Got It",
    "暂无符合条件的 Skill": "No skills match the current filters",
    "正在扫描技能库，请稍候…": "Scanning skill library, please wait...",
    "加载更多": "Load More",
    "正在加载…": "Loading...",
    "安装 Skill": "Install Skill",
    "将复制以下": "Will copy the following",
    "个文件到 Jetson：": "files to Jetson:",
    "安装路径：": "Install path:",
    "安装日志": "Install Log",
    "开始安装": "Start Install",
    "无可安装文件": "No files to install",
    "查看文档": "View Docs",
    "📖": "📖",
    "已验证": "Verified",
    "已安装": "Installed",
    "有风险": "Has Risk",
    "精选": "Featured",
    "需要远程连接": "Remote Connection Required",
    "当前运行在 PC 上，运行 Skill 前必须先在「远程开发」页连接 Jetson 设备。": "Running on PC. Connect to a Jetson in the Remote page before running skills.",

    # ── remote/page.py ────────────────────────────────────────────────────────
    "远程开发": "Remote Dev",
    "通过 VS Code / Web IDE / AI 辅助建立远程开发环境": "Build a remote dev environment with VS Code, Web IDE, and AI",
    "🤖 Claude API 配置": "Claude API Setup",
    "配置 / 修改": "Configure",
    "用途说明：用于 Skills AI 执行（通过 claude-sonnet 执行操作手册）": "Used for Skills AI execution via claude-sonnet",
    "✅ 已配置": "✅ Configured",
    "⚠ 未配置": "⚠ Not configured",
    "🔗 设备连接": "Device Connection",
    "● 未连接": "● Disconnected",
    "设备 IP / 主机名": "Device IP / Hostname",
    "192.168.1.xxx 或 jetson.local": "192.168.1.xxx or jetson.local",
    "连接": "Connect",
    "扫描局域网": "Scan LAN",
    "用户名": "Username",
    "密码": "Password",
    "sudo 密码": "sudo Password",
    "网段（可选）": "Subnet (optional)",
    "连接中…": "Connecting...",
    "扫描中…": "Scanning...",
    "正在扫描局域网…": "Scanning LAN...",
    "● 已连接": "● Connected",
    "断开": "Disconnect",
    "测试连接": "Test",
    "配置 Anthropic API Key": "Configure Anthropic API Key",
    "API Key 用于 Skills AI 执行（通过 claude-sonnet 执行操作手册）。\n获取地址：console.anthropic.com": "API Key is used for Skills AI execution via claude-sonnet.\nGet yours at: console.anthropic.com",
    "Base URL（可选，留空使用默认）": "Base URL (optional, leave blank for default)",
    "💾  保存": "💾  Save",
    "🗑  清除": "🗑  Clear",
    "⚠ 尚未配置": "⚠ Not configured",
    "⚠ 已清除": "⚠ Cleared",
    "成功": "Success",
    "API Key 已保存到本地配置文件。": "API Key saved to local config.",
    "确认清除": "Confirm Clear",
    "确定要清除已保存的 API Key 吗？": "Are you sure you want to clear the saved API Key?",
    "请输入 API Key。": "Please enter an API Key.",
    "API Key 格式不正确（长度过短）。": "API Key format is invalid (too short).",
    "🌐 VS Code Server (Web) 部署": "VS Code Server (Web) Deploy",
    "VS Code Server (Web) 部署": "VS Code Server (Web) Deploy",
    "开始部署": "Deploy",
    "📓 Jupyter Lab 安装 & 启动": "Jupyter Lab Install & Start",
    "Jupyter Lab 安装 & 启动": "Jupyter Lab Install & Start",
    "安装并启动": "Install & Start",
    "🔵 VS Code Remote SSH 配置指南": "VS Code Remote SSH Guide",
    "VS Code Remote SSH 配置": "VS Code Remote SSH Setup",
    "📓 Jupyter Lab 使用指南": "Jupyter Lab Guide",
    "Jupyter Lab 启动": "Jupyter Lab Launch",
    "需要先连接设备": "Connect a Device First",
    "请先连接 Jetson 设备": "Connect to a Jetson device first",
    "下一步这样做": "Next Steps",
    "知道了": "Got It",
    "请先连接 Jetson 设备": "Connect to a Jetson device first",
    "开发工具": "Dev Tools",
    "通过 SSH 远程连接，在本机 VS Code 中编辑 Jetson 代码": "Edit Jetson code in local VS Code over SSH",
    "在 Jetson 上运行 code-server，浏览器直接访问开发环境": "Run code-server on Jetson, access from browser",
    "接入 Claude API，在远程开发中获得 AI 代码辅助": "Use Claude API for AI coding assistance",
    "在 Jetson 上运行 Jupyter，浏览器访问交互式开发": "Run Jupyter on Jetson for browser-based development",
    "通过 VNC/noVNC 查看和操控 Jetson 图形桌面": "View and control Jetson desktop via VNC/noVNC",
    "通过 SSH 在 Jetson 上安装 Claude Code / Codex / OpenClaw CLI": "Install Claude Code / Codex / OpenClaw CLI on Jetson over SSH",
    "打开配置": "Setup",
    "部署": "Deploy",
    "启动": "Start",
    "打开": "Open",
    "AI Agent 安装": "AI Agent Install",
    "🤖 AI Agent 安装（Jetson 端）": "AI Agent Install (Jetson)",
    "通过 SSH 在 Jetson 设备上安装 AI 编程助手 CLI。\n安装完成后可在 Jetson 终端中直接使用（如 claude、codex、openclaw 命令）。\n所有 Agent 均需要 Node.js 环境，会自动检测并安装。": "Install AI coding assistant CLIs on Jetson over SSH.\nAfter installation, you can use them directly in the Jetson terminal (for example, claude, codex, and openclaw).\nAll agents require Node.js, which will be detected and installed automatically.",
    "📦 Node.js 环境": "Node.js Environment",
    "选择要安装的 Agent": "Select Agents to Install",
    "Anthropic 官方终端 AI 编程助手": "Anthropic official terminal AI coding assistant",
    "OpenAI 官方终端 AI 编程助手": "OpenAI official terminal AI coding assistant",
    "开源 AI Agent 框架（原 ClawdBot）": "Open-source AI agent framework (formerly ClawdBot)",
    "🚀 安装选中的 Agent": "Install Selected Agents",
    "🚀 安装中…": "Installing...",
    "● 已安装": "● Installed",
    "● 未安装（安装时会自动安装）": "● Not installed (will be installed automatically)",
    "✅ 已安装": "✅ Installed",
    "请至少选择一个 Agent。": "Please select at least one agent.",
    "✅ 安装完成！可在 Jetson 终端中使用已安装的 Agent。": "✅ Installation complete! You can now use the installed agents in the Jetson terminal.",
    "排查建议：": "Troubleshooting:",
    "  • 确认 Jetson 可以联网（npm 需要下载包）": "  • Make sure Jetson has internet access (npm needs to download packages)",
    "  • 如果 npm 权限不足，可尝试在 Jetson 上手动执行安装命令": "  • If npm permissions are insufficient, try running the install command manually on Jetson",
    "远程桌面": "Remote Desktop",
    "未开启": "Off",
    "🧭 Jetson 初始化": "Jetson Init",
    "刷写完成后，可先通过串口进入首次开机向导，完成用户名、密码、时区和网络配置，再继续 SSH 或远程开发。": "After flashing, use serial for first-boot setup, then continue with SSH or remote dev.",
    "等待检测": "Waiting",
    "VS Code Server (Web)": "VS Code Server (Web)",
    "Claude / AI 辅助": "Claude / AI Assistant",
    "Jupyter Lab 启动": "Jupyter Lab",
    "ℹ  需要本机安装 VS Code + Remote SSH 插件": "Requires local VS Code with Remote SSH extension",
    "ℹ  需要先连接设备，点击「部署」自动安装并启动": "Connect a device first, then click Deploy",
    "ℹ  需要配置 Anthropic API Key，点击「测试连接」验证": "Configure an Anthropic API key, then test the connection",
    "ℹ  需要先连接设备，点击「启动」自动安装并启动": "Connect a device first, then click Start",
    "ℹ  需要先连接设备，Jetson 需有图形桌面环境": "Connect a device first. Jetson needs a desktop environment",
    "ℹ  需要先连接设备，自动安装 Node.js 和选中的 Agent 到 Jetson": "Connect a device first to install Node.js and the selected agent",
    # ── main_window_v2 / flash page ──────────────────────────────────────────
    "烧录": "Flash",
    "烧录中心": "Flash Center",
    "选择设备型号与系统版本，一键完成固件刷写": "Select a device model and OS version for one-click flashing",
    "选择设备": "Select Device",
    "进入 Recovery": "Enter Recovery",
    "开始刷写": "Start Flash",
    "完成": "Done",
    "目标设备": "Target Device",
    "选择产品型号和对应的 L4T 系统版本": "Select a product model and matching L4T version",
    "产品型号": "Product",
    "暂无图片": "No Image",
    "等待选择产品...": "Waiting for product selection...",
    "执行选项": "Options",
    "跳过 SHA256 校验（不推荐）": "Skip SHA256 verification (not recommended)",
    "Recovery 模式指南": "Recovery Guide",
    "请先选择设备": "Please select a device first",
    "客户端 Getting Started": "Client Getting Started",
    "刷写完成后，可以继续从这些板块开始上手。": "After flashing, continue from these sections.",
    "推荐路径": "Recommended",
    "下一步先完成设备首次开机初始化": "Start with first boot setup",
    "建议先重启设备，完成用户名、网络和基础系统设置，再进入设备管理或远程开发继续配置。": "Restart the device, finish username, network, and basic system setup, then continue with device management or remote development.",
    "查看 Jetson 状态、运行诊断、排查外设问题。": "Check Jetson status, run diagnostics, and troubleshoot peripherals.",
    "安装常用 AI 应用、推理环境和开发工具。": "Install common AI apps, inference environments, and dev tools.",
    "用内置技能快速完成部署、修复和配置任务。": "Use built-in skills to complete deployment, repair, and setup tasks quickly.",
    "建立 SSH 连接，继续用电脑远程操作设备。": "Establish an SSH connection and keep working from your computer.",
    "查看文档、论坛和常见问题，继续深入使用。": "Open docs, forums, and FAQs to keep going.",
    "文档、论坛与常见问题解答": "Docs, forum, and common questions",
    "快速链接": "Quick Links",
    "购买商品": "Buy Product",
    "按产品型号打开对应商品页，购买整机或官方配套版本。": "Open the matching product page by model.",
    "Seeed 论坛": "Seeed Forum",
    "社区问答与经验分享": "Community Q&A and shared experience",
    "查看已连接设备状态、运行诊断与外设检测": "View connected device status, diagnostics, and peripheral checks",
    "设备型号": "Model",
    "采集中…": "Collecting...",
    "存储：": "Storage:",
    "温度：": "Temp:",
    "浏览、安装和管理 Jetson 应用与 Demo": "Browse, install, and manage Jetson apps and demos",
    "🔍  搜索应用…": "Search apps...",
    "↻  刷新状态": "Refresh Status",
    "暂无符合条件的应用": "No apps match the current filters",
    "当前运行在 PC 上，安装或部署前必须先在「远程开发」页连接 Jetson 设备。": "Running on PC. Connect to a Jetson in the Remote page before installing.",
    "分类筛选、搜索、精选 / 全部切换、运行与文档查看": "Filter, search, switch featured/all, run skills, and read docs",
    "搜索 Skills…": "Search skills...",
    "下一步这样做": "Next Steps",
    "通过 VS Code / Web IDE / AI 辅助建立远程开发环境": "Build a remote development environment with VS Code, Web IDE, and AI assistance",
    "扫描网段": "Subnet",
    # ── titlebar / sidebar ───────────────────────────────────────────────────
    "Jetson 开发工作台": "Jetson Workbench",
    "Jetson 本机": "Jetson Local",
    "远程已连接": "Remote Connected",
    "未连接设备": "No Device Connected",
    "就绪": "Ready",
    "语言": "Language",
    # ── community page ────────────────────────────────────────────────────────
    "社区": "Community",
    # ── apps.json — names, descriptions, categories ───────────────────────────
    "jtop 监控": "jtop Monitor",
    "jetson-stats 系统监控工具，实时查看 GPU / CPU / 内存使用率": "jetson-stats system monitor — real-time GPU / CPU / memory usage",
    "交互式 Python 开发环境，支持 GPU 监控插件": "Interactive Python environment with GPU monitoring plugin",
    "可视化流程编排工具，IoT 与边缘计算场景适用": "Visual flow editor for IoT and edge computing",
    "基于双路 GMSL 相机的 YOLOv26 TensorRT 视觉系统，运行检测、姿态和分割三路推理。": "YOLOv26 TensorRT vision system with dual GMSL cameras — detection, pose, and segmentation.",
    "开发工具": "Dev Tools",
    # ── skills categories (CATEGORY_ICONS keys) ───────────────────────────────
    "驱动 & 系统修复": "Drivers & Fixes",
    "应用 & 环境部署": "Apps & Setup",
    "网络 & 远程":    "Network & Remote",
    "系统优化":       "System Tuning",
    "AI / 大模型":    "AI / LLM",
    "视觉 / YOLO":    "Vision / YOLO",
    "参考文档":       "Reference",
    # ── jetson_init dialog ────────────────────────────────────────────────────
    "Jetson 初始化": "Jetson Init",
    "烧录完成后，通过串口终端进入首次启动配置。选择串口后点击'连接串口终端'即可开始。": "After flashing, use the serial terminal for first-boot setup. Select a port and click Connect.",
    "串口设备": "Serial Port",
    "刷新串口": "Refresh Ports",
    "检测初始化状态": "Check Init Status",
    "连接串口终端": "Connect Terminal",
    "内嵌串口终端": "Built-in Terminal",
    "未连接": "Disconnected",
    "连接中": "Connecting",
    "已连接": "Connected",
    "断开": "Disconnect",
    "清屏": "Clear",
    "发送回车": "Send Enter",
    "使用说明": "Instructions",
    "确认 Jetson 已上电，并通过 USB 线连接到主机。": "Make sure Jetson is powered on and connected via USB.",
    "选择串口设备，点击'连接串口终端'，在右侧终端中完成初始化配置。": "Select a serial port, click Connect Terminal, and complete setup in the terminal on the right.",
    "按照向导完成 License 确认、用户名、密码、时区、网络等设置。": "Follow the wizard to confirm the license, set username, password, timezone, and network.",
    "看到 login: 提示后说明初始化完成，可关闭此窗口。": "When you see the login: prompt, initialization is complete. You can close this window.",
    "待检测": "Pending",
    "选择串口后点击'检测初始化状态'，或直接打开串口终端。": "Select a port and click Check Init Status, or open the terminal directly.",
    "检测中": "Checking",
    "未初始化": "Not Initialized",
    "已初始化": "Initialized",
    "检测失败": "Check Failed",
    "状态未知": "Unknown",
    "释放串口占用": "Release Port",
    "未发现串口设备": "No serial ports found",
    "当前未检测到串口设备。": "No serial devices detected.",
    "检测中…": "Checking...",
    "外部终端备选：": "External terminal: ",
    "未检测到可用的外部终端工具（可使用内嵌终端）。": "No external terminal tool found. Use the built-in terminal.",
    "等待检测到可用串口设备": "Waiting for a serial port...",
    "进入串口终端": "Open Terminal",
    "打开初始化面板": "Open Init Panel",
    # ── jetson_init probe results ─────────────────────────────────────────────
    "未读取到明确串口输出": "No clear serial output",
    "请确认设备已上电，并按回车后重试。": "Make sure the device is powered on, then press Enter and retry.",
    "检测到首次启动初始化向导": "First-boot setup wizard detected",
    "这台 Jetson 还未完成系统初始化，需要通过串口继续配置用户名、密码和基础系统设置。": "This Jetson has not completed system initialization. Continue setup via serial terminal.",
    "检测到正常登录提示": "Normal login prompt detected",
    "设备大概率已经完成初始化，可以直接通过串口登录或继续配置 SSH。": "The device is likely initialized. You can log in via serial or continue with SSH setup.",
    "串口已连通，但未识别到明确状态": "Serial connected, status unclear",
    "可能处于启动中、停留在其他菜单，或输出较少。建议继续查看串口终端。": "May be booting, in another menu, or producing little output. Check the terminal.",
    "串口检测失败": "Serial check failed",
    "用户名或密码错误（Login incorrect）。": "Incorrect username or password.",
    "登录失败，未检测到 shell 提示符。": "Login failed, no shell prompt detected.",
    # ── port lock messages ────────────────────────────────────────────────────
    "释放成功": "Released",
    "释放失败": "Release Failed",
    "是否尝试释放该串口占用？": "Try to release the port lock?",
    "请先选择串口。": "Please select a serial port first.",
    # ── remote/page.py — Device Connection card ───────────────────────────────
    "sudo 密码": "sudo Password",
    "留空则默认使用登录密码": "Leave blank to use login password",
    "用于 apt / systemctl / docker 等提权命令": "Used for apt / systemctl / docker etc.",
    "扫描网段": "Subnet",
    "🌐 PC 网络共享": "🌐 PC Net Share",
    "未开启": "Off",
    "● 共享中": "● Sharing",
    # ── net_share_dialog.py ──────────────────────────────────────────────────
    "PC 网络共享": "PC Network Sharing",
    "将 PC 的互联网连接共享给 Jetson，使 Jetson 通过 PC 上网。PC 需要有一个上网网卡（WiFi）和一个连接 Jetson 的网卡（以太网）。": "Share PC's internet connection with Jetson. PC needs one WAN interface (WiFi) and one LAN interface (Ethernet) connected to Jetson.",
    "当前 Jetson IP：": "Current Jetson IP: ",
    "（已根据 SSH 连接自动匹配 LAN 网卡）": "(LAN interface auto-matched via SSH connection)",
    "PC 上网网卡 (WAN)": "PC WAN Interface",
    "PC 连接 Jetson 的网卡 (LAN)": "PC LAN Interface (to Jetson)",
    "PC sudo 密码": "PC sudo Password",
    "本机管理员密码": "Local admin password",
    "刷新网卡": "Refresh Interfaces",
    "提示：开启后会自动通过 SSH 配置 Jetson 的网关和 DNS，使 Jetson 可以上网。如果未建立 SSH 连接，需手动在 Jetson 上配置网关指向 PC 的 LAN 网卡 IP。": "Tip: After enabling, Jetson's gateway and DNS will be auto-configured via SSH. If no SSH connection exists, manually configure Jetson's gateway to point to PC's LAN interface IP.",
    "开启网络共享": "Enable Sharing",
    "关闭网络共享": "Disable Sharing",
    "执行日志": "Execution Log",
    "关闭": "Close",
    "检测中…": "Detecting...",
    "正在检测网卡…": "Detecting interfaces...",
    "提示": "Notice",
    "请选择上网网卡和 Jetson 网卡。": "Please select WAN and LAN interfaces.",
    "上网网卡和 Jetson 网卡不能相同。": "WAN and LAN interfaces cannot be the same.",
    "请输入 PC 的 sudo 密码。": "Please enter PC sudo password.",
    "开启中…": "Enabling...",
    "正在配置…": "Configuring...",
    "已开启：": "Enabled: ",
    "开启失败，请查看日志": "Failed to enable, check log",
    "关闭中…": "Disabling...",
    "已关闭": "Disabled",
    "网络共享仍在运行": "Network Sharing Still Active",
    "关闭窗口不会停止网络共享。\n是否先关闭共享再退出？": "Closing window won't stop sharing.\nDisable sharing before exit?",
    # ── remote/page.py — Jetson Init card ────────────────────────────────────
    "进入串口终端": "Open Terminal",
    "打开初始化面板": "Open Init Panel",
    "配置网络 IP": "Configure Network IP",
    "🌐 网络共享": "🌐 Net Share",
    "● 已发现串口": "● Port Found",
    "● 未发现串口": "● No Port Found",
    "Jetson 系列完整文档": "Jetson series documentation",
    "开源代码与 Issue 反馈": "Open source code & issue tracker",
    "视频教程": "Video Tutorials",
    "YouTube 上手教程合集": "YouTube tutorial collection",
    "官方容器镜像仓库": "Official container image registry",
    "模型与数据集下载": "Model & dataset downloads",
    "打开 →": "Open →",
    # ── flash page ────────────────────────────────────────────────────────────
    "步骤一：准备固件": "Step 1: Prepare Firmware",
    "步骤二：进入 Recovery 模式": "Step 2: Enter Recovery Mode",
    "步骤三：开始刷写": "Step 3: Flash",
    "步骤四：完成": "Step 4: Done",
    "下载/解压 BSP": "Download / Extract BSP",
    "下载并解压 BSP 到本地，或使用已有缓存直接进入下一步": "Download and extract BSP locally, or use cached files to skip ahead",
    "下一步 →": "Next →",
    "开始刷写 →": "Start Flash →",
    "返回 Recovery": "Back to Recovery",
    "重新开始": "Restart",
    "重新烧录": "Re-flash",
    "跳过，直接下一步": "Skip, go to next step",
    "覆盖重新下载解压": "Re-download and extract",
    "选择「跳过」可直接使用现有目录进入下一步。": "Choose Skip to use the existing directory.",
    "检测到本地已有解压好的固件目录。\n是否覆盖重新下载并解压？": "A local extracted firmware directory already exists.\nOverwrite and re-download?",
    "已有解压目录": "Directory exists",
    "已有解压目录，直接进入刷写步骤": "Directory exists, proceeding to flash",
    "下载并解压完成，可进入下一步刷写": "Download and extraction complete, ready to flash",
    "初始化...": "Initializing...",
    "准备开始刷写...": "Preparing to flash...",
    "下载固件中...": "Downloading firmware...",
    "压缩包已存在，跳过下载": "Archive exists, skipping download",
    "校验 SHA256...": "Verifying SHA256...",
    "解压固件...": "Extracting firmware...",
    "刷写中...": "Flashing...",
    "刷写完成！": "Flash complete!",
    "刷写已完成。": "Flashing done.",
    "刷写失败": "Flash failed",
    "固件下载失败": "Firmware download failed",
    "固件下载完成（未刷写）": "Firmware downloaded (not flashed)",
    "固件解压失败": "Firmware extraction failed",
    "下载并解压完成，可进入下一步刷写": "Download and extraction complete, ready to flash",
    "处理中": "Processing",
    "尚未开始": "Not started",
    "日志": "Log",
    "保存日志": "Save Log",
    "保存烧录日志": "Save Flash Log",
    "清空": "Clear",
    "清除缓存": "Clear Cache",
    "选择清除压缩包或解压目录": "Select what to clear",
    "选择要清除的内容：": "Select content to clear:",
    "可只清除压缩包，或只清理解压后的工作目录。": "You can clear just the archive, or just the extracted directory.",
    "操作步骤：": "Steps:",
    "文档快捷入口：使用下方按钮打开": "Docs: use the buttons below to open",
    "打开该产品的 Getting Started Wiki": "Open Getting Started Wiki for this product",
    "打开该产品的 Hardware Interface Wiki": "Open Hardware Interface Wiki for this product",
    "图片加载中...": "Loading image...",
    "图片加载失败": "Image load failed",
    "滚轮可缩放图片，按住鼠标左键可拖动查看指定位置。": "Scroll to zoom, drag to pan.",
    "点击查看大图": "Click to enlarge",
    "暂无该设备的 Recovery 指南": "No Recovery guide available for this device",
    "然后点击「检测设备」确认设备已进入 Recovery 模式。": "Then click Detect Device to confirm Recovery mode.",
    "检测设备": "Detect Device",
    "等待检测...": "Waiting...",
    "有压缩包则跳过下载直接解压；有解压目录则弹窗确认是否覆盖": "Skip download if archive exists; confirm overwrite if directory exists",
    "未找到该产品的购买链接": "No purchase link found for this product",
    "需要本机管理员权限": "Local admin privileges required",
    "解压和烧录固件需要 sudo 权限。": "Extracting and flashing firmware requires sudo.",
    "输入密码…": "Enter password...",
    "输入本机密码…": "Enter local password...",
    "密码错误，请重试": "Wrong password, please try again",
    "页面加载失败，请重试或查看日志。": "Page failed to load. Please retry or check the log.",
    # ── flash page step 2 description ────────────────────────────────────────
    "将设备通过 USB 连接到本机，按住 Recovery 键后上电（或按 Reset），\n然后点击「检测设备」确认设备已进入 Recovery 模式。":
        "Connect the device via USB, hold the Recovery button while powering on (or press Reset),\nthen click Detect Device to confirm Recovery mode.",
    "← 返回": "← Back",
    "确认清除": "Confirm Clear",
    "关闭": "Close",
    "中文": "中文",

    # ── main_window_v2.py ────────────────────────────────────────────────────
    "切换界面语言": "Switch language",
    "页面加载失败，请重试或查看日志。": "Page failed to load. Please retry or check the log.",

    # ── remote/page.py ───────────────────────────────────────────────────────
    "需要先连接设备": "Connect a Device First",
    "下一步这样做": "Next Steps",
    "知道了": "Got It",
    "界面配置": "UI Configuration",
    "环境变量": "Environment Variable",
    "默认官方地址": "Default Official Address",
    '回到本页上方的"设备连接"卡片。': "Go back to the Device Connection card above.",
    "输入 Jetson 的 IP、用户名和密码。": "Enter Jetson's IP, username, and password.",
    '点击"连接 / 检测 SSH"，连接成功后再回来使用这个功能。': "Click Connect/Test SSH, then come back after successful connection.",
    "失败，尝试下一个…": "Failed, trying next...",
    "下载失败，文件不完整": "Download failed, file incomplete",
    "安装中…": "Installing...",
    "部署完成！访问地址：": "Deployment complete! Access address:",
    "密码见上方日志 password 行。": "Password is in the log above (password line).",
    "启动完成！访问地址：": "Started! Access address:",
    "步骤 1：确保本机已安装 VS Code": "Step 1: Make sure VS Code is installed locally",
    "步骤 2：在 VS Code 中安装扩展「Remote - SSH」（ms-vscode-remote.remote-ssh）": "Step 2: Install the Remote - SSH extension in VS Code",
    "步骤 3：按 F1 → 「Remote-SSH: Connect to Host…」→ 输入以下地址：": "Step 3: Press F1 → Remote-SSH: Connect to Host... → Enter the address:",
    "步骤 4：输入 Jetson 设备密码（默认 seeed 或 jetson）": "Step 4: Enter Jetson device password (default: seeed or jetson)",
    "步骤 5：连接成功后，在 VS Code 中打开远程文件夹即可编辑代码": "Step 5: After connecting, open a remote folder in VS Code to edit code",
    "提示：": "Tips:",
    "确保 Jetson 设备已启动 SSH 服务（sudo systemctl start ssh）": "Make sure SSH service is running on Jetson (sudo systemctl start ssh)",
    "可在设备上运行以下命令检查 SSH 状态：": "Run the following command on the device to check SSH status:",
    "步骤 1：在 Jetson 设备上安装 Jupyter Lab（若未安装）：": "Step 1: Install Jupyter Lab on Jetson (if not installed):",
    "步骤 2：启动 Jupyter Lab（允许远程访问）：": "Step 2: Start Jupyter Lab (allow remote access):",
    "步骤 3：在本机浏览器中访问：": "Step 3: Open in your browser:",
    "步骤 4：首次访问需要 token，从 Jetson 终端输出中复制 token 并粘贴": "Step 4: First access requires a token — copy it from the Jetson terminal output",
    "若需要后台运行，可使用：": "For background running, use:",
    "通过 Skills 市场可一键安装 Jupyter Lab": "One-click install Jupyter Lab via the Skills Market",

    # ── skills/page.py ───────────────────────────────────────────────────────
    "无可安装文件": "No files to install",
    "已取消": "Cancelled",
    "未连接 SSH，无法安装": "SSH not connected, cannot install",
    "skill 目录为空": "Skill directory is empty",
    "（无文件）": "(No files)",
    "✓ 已验证": "✓ Verified",
    "● 已安装": "● Installed",
    "⚠ 有风险": "⚠ Risk",
    "暂无符合条件的 Skill": "No matching skills",
    "正在加载…": "Loading...",

    # ── apps/page.py ─────────────────────────────────────────────────────────
    "需要远程连接": "Remote Connection Required",
    "当前运行在 PC 上，安装或部署前必须先在「远程开发」页连接 Jetson 设备。":
        "Running on PC. Connect to a Jetson in the Remote page before installing.",
    "其他": "Other",
    "可安装": "Available",
    "检测中": "Checking",
    "安装：": "Install:",
    "运行：": "Run:",

    # ── devices/page.py ──────────────────────────────────────────────────────
    "⚠ 已取消": "⚠ Cancelled",
    "JetPack 6.x (R36)": "JetPack 6.x (R36)",
    "JetPack 5.x (R35)": "JetPack 5.x (R35)",
    "✅ PyTorch 安装成功！CUDA 已可用。": "✅ PyTorch installed! CUDA is available.",
    "❌ 安装未完成，请检查日志。": "❌ Installation incomplete. Check the log.",
}


ZH_EN_PATTERNS = [
    (re.compile(r"^共 (\d+) 个应用$"), lambda m: f"{m.group(1)} apps total"),
    (re.compile(r"^共 (\d+) 个 Skills$"), lambda m: f"{m.group(1)} skills total"),
    (re.compile(r"^共 (\d+) 个 Skill$"), lambda m: f"{m.group(1)} skills total"),
    (re.compile(r"^将执行 (\d+) 条命令：$"), lambda m: f"Will run {m.group(1)} commands:"),
    (re.compile(r"^运行  (.+)$"), lambda m: f"Run {m.group(1)}"),
    (re.compile(r"^📖  (.+)$"), lambda m: f"Docs: {m.group(1)}"),
    (re.compile(r"^加载更多  (\d+) 个  \((\d+) / (\d+)\)$"),
     lambda m: f"Load more  {m.group(1)}  ({m.group(2)} / {m.group(3)})"),
    (re.compile(r"^将复制以下 (\d+) 个文件到 Jetson：$"),
     lambda m: f"Will copy {m.group(1)} files to Jetson:"),
    (re.compile(r"^共 (\d+) 个 Skill，(\d+) 个有 OpenClaw / Claude / Codex 版本可安装$"),
     lambda m: f"{m.group(1)} skills, {m.group(2)} with installable OpenClaw/Claude/Codex versions"),
    (re.compile(r"^当前功能“(.+)”需要通过 SSH 与 Jetson 通信后才能继续。$"),
     lambda m: f'The feature "{m.group(1)}" requires an SSH connection to a Jetson device.'),
    (re.compile(r"^✅ 已配置（前缀：(.+)…）$"), lambda m: f"✅ Configured (prefix: {m.group(1)}…)"),
    (re.compile(r"^✅ 已保存（前缀：(.+)…）$"), lambda m: f"✅ Saved (prefix: {m.group(1)}…)"),
    (re.compile(r"^🔖 检测到 (.+)，将自动选择对应 NVIDIA 官方 wheel$"),
     lambda m: f"🔖 Detected {m.group(1)}, will auto-select the official NVIDIA wheel"),
    (re.compile(r"^API 连通正常，模型：(.+)$"),
     lambda m: f"API connection OK, model: {m.group(1)}"),
    (re.compile(r"^(\d+) 个$"), lambda m: f"{m.group(1)}"),
    (re.compile(r"^部署失败（rc=(\d+)）：(.*)$"), lambda m: f"Deployment failed (rc={m.group(1)}): {m.group(2)}"),
    (re.compile(r"^启动失败（rc=(\d+)）：(.*)$"), lambda m: f"Start failed (rc={m.group(1)}): {m.group(2)}"),
    (re.compile(r"^✖ 命令失败 \(rc=(\d+)\)$"), lambda m: f"✖ Command failed (rc={m.group(1)})"),
    (re.compile(r"^mkdir 失败 \(rc=(\d+)\)$"), lambda m: f"mkdir failed (rc={m.group(1)})"),
    (re.compile(r"^上传 (.+)$"), lambda m: f"Uploading {m.group(1)}"),
    (re.compile(r"^上传失败: (.+)$"), lambda m: f"Upload failed: {m.group(1)}"),
    (re.compile(r"^SFTP 打开失败: (.+)$"), lambda m: f"SFTP open failed: {m.group(1)}"),
    (re.compile(r"^安装路径：(.+)$"), lambda m: f"Install path: {m.group(1)}"),
    (re.compile(r"^尝试镜像: (.+)$"), lambda m: f"Trying mirror: {m.group(1)}"),
    (re.compile(r"^创建目录 (.+) …$"), lambda m: f"Creating directory {m.group(1)}..."),
]


def translate_text(source: str, lang: str) -> str:
    if not source or lang in {"zh", "zh-CN"}:
        return source

    exact = ZH_EN_EXACT.get(source)
    if exact is not None:
        return exact

    for pattern, repl in ZH_EN_PATTERNS:
        match = pattern.match(source)
        if match:
            return repl(match)

    return source


def _translate_property(widget: QWidget, getter_name: str, setter_name: str, prop_name: str, lang: str):
    try:
        getter = getattr(widget, getter_name, None)
        setter = getattr(widget, setter_name, None)
    except RuntimeError:
        return
    if getter is None or setter is None:
        return

    try:
        current = getter()
    except RuntimeError:
        return
    if current is None:
        return

    try:
        source = widget.property(prop_name)
    except RuntimeError:
        return
    if source is None:
        source = current
        try:
            widget.setProperty(prop_name, source)
        except RuntimeError:
            return

    try:
        setter(translate_text(source, lang))
    except RuntimeError:
        return


def apply_language(widget: QWidget, lang: str):
    if widget is None:
        return

    try:
        all_widgets = [widget] + widget.findChildren(QWidget)
    except RuntimeError:
        return
    for item in all_widgets:
        try:
            item.property("_i18n_guard")
        except RuntimeError:
            continue
        _translate_property(item, "windowTitle", "setWindowTitle", "_i18n_source_window_title", lang)

        if isinstance(item, (QLabel, QPushButton, QCheckBox, QGroupBox)):
            _translate_property(item, "text", "setText", "_i18n_source_text", lang)

        if isinstance(item, QLineEdit):
            _translate_property(item, "placeholderText", "setPlaceholderText", "_i18n_source_placeholder", lang)

        if isinstance(item, QComboBox) and item.property("_i18n_translate_items"):
            try:
                source_items = item.property("_i18n_source_items")
            except RuntimeError:
                continue
            if source_items is None:
                try:
                    source_items = [item.itemText(i) for i in range(item.count())]
                    item.setProperty("_i18n_source_items", source_items)
                except RuntimeError:
                    continue
            try:
                current_index = item.currentIndex()
                item.blockSignals(True)
                item.clear()
                item.addItems([translate_text(text, lang) for text in source_items])
                item.setCurrentIndex(current_index)
                item.blockSignals(False)
            except RuntimeError:
                continue


def get_current_lang(widget=None) -> str:
    """从最近的主窗口获取当前语言，找不到则返回 'zh'。"""
    try:
        if widget is not None:
            win = widget.window()
            lang = getattr(win, "_lang", None)
            if lang:
                return lang
        # 遍历所有顶层窗口
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for w in app.topLevelWidgets():
                lang = getattr(w, "_lang", None)
                if lang:
                    return lang
    except Exception:
        pass
    return "zh"


def apply_dialog_language(dialog: QWidget, parent=None):
    """在弹窗显示前调用，自动检测当前语言并翻译弹窗内所有 widget。"""
    lang = get_current_lang(parent or dialog)
    if lang != "zh":
        apply_language(dialog, lang)
