"""AI 助手页面 — 独立的全页 AI 对话终端"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from seeed_jetson_develop.gui.theme import (
    C_BG, C_BG_DEEP, C_TEXT, C_TEXT3,
    pt as _pt, make_label as _lbl,
)
from seeed_jetson_develop.gui.ai_chat import AIChatPanel, _DEFAULT_SYSTEM


def build_page() -> QWidget:
    page = QWidget()
    page.setStyleSheet(f"background:{C_BG};")
    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    # 页头
    header = QWidget()
    header.setStyleSheet(f"background:{C_BG_DEEP};")
    header.setFixedHeight(_pt(64))
    hl = QHBoxLayout(header)
    hl.setContentsMargins(28, 0, 28, 0)
    hl.addWidget(_lbl("AI 助手", 18, C_TEXT, bold=True))
    hl.addSpacing(12)
    hl.addWidget(_lbl("由 Claude 驱动的 Jetson 开发智能助手", 12, C_TEXT3))
    hl.addStretch()
    root.addWidget(header)

    # 构建 system prompt（含 skills 列表）
    system = _DEFAULT_SYSTEM
    try:
        from seeed_jetson_develop.modules.skills.engine import load_skills
        skills = load_skills()
        skills_text = "\n".join(
            f"- {s.name}（{s.category}）: {s.desc}"
            for s in skills[:30]
        )
        system = _DEFAULT_SYSTEM + f"\n\n可用 Skills 列表（供参考，用户可在 Skills 页面一键运行）：\n{skills_text}"
    except Exception:
        pass

    chat = AIChatPanel(system_prompt=system, title="AI 终端", parent=page)
    root.addWidget(chat, 1)
    return page
