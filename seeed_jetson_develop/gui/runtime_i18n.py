"""Runtime i18n helpers for the V2 GUI.

This keeps the original Chinese source text on widgets and applies
an English translation at runtime when requested.
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
    "烧录": "Flash",
    "设备管理": "Devices",
    "应用市场": "Apps",
    "远程开发": "Remote",
    "社区": "Community",
    "Jetson 开发工作台": "Jetson Workbench",
    "Jetson 本机": "Jetson Local",
    "远程已连接": "Remote Connected",
    "未连接设备": "No Device Connected",
    "就绪": "Ready",
    "语言": "Language",
    "烧录中心": "Flash Center",
    "选择设备型号与系统版本，一键完成固件刷写": "Select a device model and OS version for one-click flashing",
    "选择设备": "Select Device",
    "进入 Recovery": "Enter Recovery",
    "开始刷写": "Start Flash",
    "完成": "Done",
    "目标设备": "Target Device",
    "选择产品型号和对应的 L4T 系统版本": "Select a product model and matching L4T version",
    "产品型号": "Product",
    "L4T 版本": "L4T Version",
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
    "Jetson 初始化": "Jetson Init",
    "设备管理": "Device Manager",
    "查看 Jetson 状态、运行诊断、排查外设问题。": "Check Jetson status, run diagnostics, and troubleshoot peripherals.",
    "应用市场": "App Market",
    "安装常用 AI 应用、推理环境和开发工具。": "Install common AI apps, inference environments, and dev tools.",
    "用内置技能快速完成部署、修复和配置任务。": "Use built-in skills to complete deployment, repair, and setup tasks quickly.",
    "建立 SSH 连接，继续用电脑远程操作设备。": "Establish an SSH connection and keep working from your computer.",
    "查看文档、论坛和常见问题，继续深入使用。": "Open docs, forums, and FAQs to keep going.",
    "社区": "Community",
    "文档、论坛与常见问题解答": "Docs, forum, and common questions",
    "快速链接": "Quick Links",
    "购买商品": "Buy Product",
    "按产品型号打开对应商品页，购买整机或官方配套版本。": "Open the matching product page by model.",
    "Seeed 论坛": "Seeed Forum",
    "社区问答与经验分享": "Community Q&A and shared experience",
    "设备管理": "Devices",
    "查看已连接设备状态、运行诊断与外设检测": "View connected device status, diagnostics, and peripheral checks",
    "▶  运行全部检测": "Run All Checks",
    "设备型号": "Model",
    "内存使用": "Memory",
    "IP 地址": "IP Address",
    "采集中…": "Collecting...",
    "🔍 快速诊断": "Quick Diagnostics",
    "仅运行诊断": "Diagnostics Only",
    "自动检查网络、GPU Torch、Docker、jtop、摄像头等关键组件状态": "Automatically check network, GPU Torch, Docker, jtop, cameras, and other key components",
    "安装 PyTorch": "Install PyTorch",
    "待检测": "Pending",
    "🔌 外设状态": "Peripherals",
    "仅检测外设": "Peripherals Only",
    "存储：": "Storage:",
    "温度：": "Temp:",
    "检测中…": "Checking...",
    "串口连接 — 输入凭据": "Serial Login",
    "当前未建立 SSH 连接，将通过串口执行检测。": "No SSH connection is active. Detection will run through serial access.",
    "串口设备": "Serial Port",
    "用户名": "Username",
    "密码": "Password",
    "输入 Jetson 登录密码": "Enter the Jetson login password",
    "刷新": "Refresh",
    "确定": "OK",
    "取消": "Cancel",
    "应用市场": "App Market",
    "浏览、安装和管理 Jetson 应用与 Demo": "Browse, install, and manage Jetson apps and demos",
    "全部": "All",
    "已安装": "Installed",
    "🔍  搜索应用…": "Search apps...",
    "↻  刷新状态": "Refresh Status",
    "可安装": "Available",
    "卸载": "Uninstall",
    "安装": "Install",
    "暂无符合条件的应用": "No apps match the current filters",
    "需要远程连接": "Remote Connection Required",
    "当前运行在 PC 上，安装或部署前必须先在「远程开发」页连接 Jetson 设备。": "You are running on a PC. Connect to a Jetson in the Remote page before installing or deploying.",
    "Skills 中心": "Skills Center",
    "分类筛选、搜索、精选 / 全部切换、运行与文档查看": "Filter, search, switch featured/all, run skills, and read docs",
    "精选": "Featured",
    "全部 Skills": "All Skills",
    "搜索 Skills…": "Search skills...",
    "运行": "Run",
    "查看文档": "View Docs",
    "开始运行": "Run",
    "停止": "Stop",
    "关闭": "Close",
    "失败重试": "Retries",
    "无可执行命令": "No runnable commands",
    "执行日志": "Execution Log",
    "已取消": "Cancelled",
    "风险提示：": "Risk:",
    "需要先连接设备": "Connect a Device First",
    "请先连接 Jetson 设备": "Connect to a Jetson device first",
    "下一步这样做": "Next Step",
    "知道了": "OK",
    "远程开发": "Remote Development",
    "通过 VS Code / Web IDE / AI 辅助建立远程开发环境": "Build a remote development environment with VS Code, Web IDE, and AI assistance",
    "🤖 Claude API 配置": "Claude API Setup",
    "🔗 设备连接": "Device Connection",
    "设备 IP / 主机名": "Device IP / Hostname",
    "连接": "Connect",
    "扫描网段": "Subnet",
    "扫描局域网": "Scan LAN",
    "未开启": "Off",
    "🔵 VS Code Remote SSH 配置指南": "VS Code Remote SSH Guide",
    "Jupyter Lab 启动": "Jupyter Lab",
    "🧭 Jetson 初始化": "Jetson Init",
    "等待检测": "Waiting",
    "刷写完成后，可先通过串口进入首次开机向导，完成用户名、密码、时区和网络配置，再继续 SSH 或远程开发。": "After flashing, use serial setup for first boot, then continue with SSH or remote development.",
    "开发工具": "Developer Tools",
    "打开配置": "Setup",
    "部署": "Deploy",
    "测试连接": "Test",
    "启动": "Start",
    "打开": "Open",
    "VS Code Server (Web)": "VS Code Server (Web)",
    "Claude / AI 辅助": "Claude / AI Assistant",
    "远程桌面": "Remote Desktop",
    "AI Agent 安装": "AI Agent Install",
    "通过 SSH 远程连接，在本机 VS Code 中编辑 Jetson 代码": "Edit Jetson code in local VS Code over SSH",
    "在 Jetson 上运行 code-server，浏览器直接访问开发环境": "Run code-server on Jetson and access it from a browser",
    "接入 Claude API，在远程开发中获得 AI 代码辅助": "Use Claude API for AI coding help in remote development",
    "在 Jetson 上运行 Jupyter，浏览器访问交互式开发": "Run Jupyter on Jetson for browser-based interactive development",
    "通过 VNC/noVNC 查看和操控 Jetson 图形桌面": "View and control the Jetson desktop with VNC/noVNC",
    "通过 SSH 在 Jetson 上安装 Claude Code / Codex / OpenClaw CLI": "Install Claude Code / Codex / OpenClaw CLI on Jetson over SSH",
    "ℹ  需要本机安装 VS Code + Remote SSH 插件": "Requires local VS Code with the Remote SSH extension",
    "ℹ  需要先连接设备，点击「部署」自动安装并启动": "Connect a device first, then deploy automatically",
    "ℹ  需要配置 Anthropic API Key，点击「测试连接」验证": "Configure an Anthropic API key, then test the connection",
    "ℹ  需要先连接设备，点击「启动」自动安装并启动": "Connect a device first, then install and start automatically",
    "ℹ  需要先连接设备，Jetson 需有图形桌面环境": "Connect a device first. Jetson also needs a desktop environment",
    "ℹ  需要先连接设备，自动安装 Node.js 和选中的 Agent 到 Jetson": "Connect a device first to install Node.js and the selected agent on Jetson",
}


ZH_EN_PATTERNS = [
    (re.compile(r"^共 (\d+) 个应用$"), lambda m: f"{m.group(1)} apps total"),
    (re.compile(r"^将执行 (\d+) 条命令：$"), lambda m: f"Will run {m.group(1)} commands:"),
    (re.compile(r"^运行  (.+)$"), lambda m: f"Run {m.group(1)}"),
    (re.compile(r"^📖  (.+)$"), lambda m: f"Docs: {m.group(1)}"),
    (re.compile(r"^当前功能“(.+)”需要通过 SSH 与 Jetson 通信后才能继续。$"), lambda m: f'The feature "{m.group(1)}" requires an SSH connection to a Jetson device.'),
    (re.compile(r"^1\. 回到本页上方的“设备连接”卡片。\n2\. 输入 Jetson 的 IP、用户名和密码。\n3\. 点击“连接 / 检测 SSH”，连接成功后再回来使用这个功能。$"),
     lambda m: "1. Go to the Device Connection card at the top.\n2. Enter the Jetson IP, username, and password.\n3. Click Connect / Check SSH, then come back."),
    (re.compile(r"^共 (\d+) 个 Skills$"), lambda m: f"{m.group(1)} skills total"),
]


def translate_text(source: str, lang: str) -> str:
    if not source or lang == "zh":
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
