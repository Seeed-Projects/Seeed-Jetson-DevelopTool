"""Local AI agent CLI detection and skills-directory conventions.

Single source of truth for:
- which local CLIs are supported (Claude Code / Codex),
- where each agent reads its skills on the local PC and on a remote Jetson,
- how to detect whether a CLI is installed locally.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

AGENT_CLAUDE = "claude"
AGENT_CODEX = "codex"
# Codex first: default agent for interactive sessions (YOLO mode).
SUPPORTED_AGENTS = (AGENT_CODEX, AGENT_CLAUDE)

# Agent metadata shared with the setup dialog / skills page.
AGENT_INFO = {
    AGENT_CLAUDE: {
        "name": "Claude Code CLI",
        "icon": "🟣",
        "npm_pkg": "@anthropic-ai/claude-code",
        # `npx skills add ... --agent <arg>`
        "npx_agent_arg": "claude-code",
    },
    AGENT_CODEX: {
        "name": "Codex CLI",
        "icon": "🟢",
        "npm_pkg": "@openai/codex",
        "npx_agent_arg": "codex",
    },
}

# Local skills dirs scanned per agent (first is the canonical install target).
_LOCAL_SKILLS_DIRS: dict[str, tuple[Path, ...]] = {
    AGENT_CLAUDE: (Path.home() / ".claude" / "skills",),
    AGENT_CODEX: (
        Path.home() / ".agents" / "skills",
        Path.home() / ".codex" / "skills",
    ),
}

# Remote (Jetson) skills dir relative to $HOME, per agent.
_REMOTE_SKILLS_DIRS: dict[str, str] = {
    AGENT_CLAUDE: ".claude/skills",
    AGENT_CODEX: ".codex/skills",
}


def local_skills_dirs(agent: str) -> tuple[Path, ...]:
    """Local skills dirs for an agent (canonical first)."""
    return _LOCAL_SKILLS_DIRS.get(agent, ())


def local_skills_dir(agent: str) -> Path:
    """Canonical local skills dir for an agent."""
    dirs = local_skills_dirs(agent)
    return dirs[0] if dirs else Path.home() / ".agents" / "skills"


def remote_skills_dir(agent: str) -> str:
    """Remote skills dir relative to $HOME on the Jetson."""
    return _REMOTE_SKILLS_DIRS.get(agent, ".agents/skills")


def npx_agent_arg(agent: str) -> str:
    """Agent argument for `npx skills add --agent <arg>`."""
    return AGENT_INFO.get(agent, {}).get("npx_agent_arg", agent)


def npm_package(agent: str) -> str:
    return AGENT_INFO.get(agent, {}).get("npm_pkg", agent)


def find_cli(agent: str) -> str | None:
    """Return the executable path of an agent CLI, or None."""
    return shutil.which(agent)


def cli_version(agent: str, timeout: float = 8.0) -> str | None:
    """Return `<agent> --version` output, or None when unavailable."""
    exe = find_cli(agent)
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, "--version"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, timeout=timeout,
            text=True, encoding="utf-8", errors="replace",
        )
        lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
        return lines[-1] if proc.returncode == 0 and lines else None
    except Exception:
        return None


def detect_local_agents(agents=SUPPORTED_AGENTS) -> dict[str, dict]:
    """Detect local CLI availability.

    Returns ``{agent: {"installed": bool, "version": str, "path": str}}``.
    Blocking (runs `--version`); call from a worker thread.
    """
    result: dict[str, dict] = {}
    for agent in agents:
        path = find_cli(agent)
        version = cli_version(agent) if path else None
        result[agent] = {
            "installed": bool(path and version),
            "version": version or "",
            "path": path or "",
        }
    return result


def node_version(timeout: float = 8.0) -> str | None:
    """Return local Node.js version (e.g. 'v20.18.3'), or None."""
    exe = shutil.which("node")
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, "--version"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, timeout=timeout,
            text=True, encoding="utf-8", errors="replace",
        )
        out = proc.stdout.strip()
        return out if proc.returncode == 0 and out.startswith("v") else None
    except Exception:
        return None


def installed_nvidia_skills(agent: str | None = None) -> set[str]:
    """Names of skills installed locally for the given agent (or any)."""
    if agent is not None:
        bases = local_skills_dirs(agent)
    else:
        bases = tuple(d for dirs in _LOCAL_SKILLS_DIRS.values() for d in dirs)
    installed: set[str] = set()
    for base in bases:
        if base.exists():
            for child in base.iterdir():
                if child.is_dir() and (child / "SKILL.md").exists():
                    installed.add(child.name)
    return installed
