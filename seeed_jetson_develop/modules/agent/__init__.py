"""Agent module — local CLI (claude/codex) driven Jetson/Physical AI development."""
from __future__ import annotations

from qtpy.QtWidgets import QWidget


def build_page() -> QWidget:
    from seeed_jetson_develop.modules.agent.page import AgentPage
    return AgentPage()
