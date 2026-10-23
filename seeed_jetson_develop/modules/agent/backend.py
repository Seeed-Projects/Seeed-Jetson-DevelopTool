"""Agent CLI session backend — wraps local `claude` / `codex` non-interactive runs.

Each user message spawns one non-interactive CLI process in a QThread and
streams parsed events back to the UI:

- Claude Code: ``claude -p <prompt> --output-format stream-json --verbose``
  (``--continue`` keeps the conversation for follow-up turns).
- Codex CLI:  ``codex exec --json <prompt>``
  (``codex exec resume --last`` for follow-up turns).

Parsing is tolerant: if the output is not JSONL (older CLI / unexpected
format), lines fall back to plain-text tokens with ANSI codes stripped.
"""
from __future__ import annotations

import json
import logging
import queue
import re
import subprocess
import threading

from qtpy.QtCore import QThread, Signal

from seeed_jetson_develop.modules.agent.cli_tools import (
    AGENT_CLAUDE,
    AGENT_CODEX,
    find_cli,
)

log = logging.getLogger("seeed.agent.backend")

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Non-JSON noise printed by CLIs on stderr (merged into stdout):
# - codex notices its stdin is piped
# - rust-style log lines, e.g. "2026-10-13T07:02:36Z ERROR codex_core::util: ..."
_NOISE_RE = re.compile(
    r"^(Reading additional input from stdin.*|"
    r"\d{4}-\d{2}-\d{2}T\S+\s+(ERROR|WARN|INFO)\s+\S+.*)$"
)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences (colors, cursor moves, etc.)."""
    return _ANSI_RE.sub("", text)


def build_command(agent: str, prompt: str, continue_session: bool = False,
                  full_access: bool = True, resume_id: str = "") -> list[str] | None:
    """Build the CLI argv for one turn. Returns None when CLI is missing."""
    exe = find_cli(agent)
    if not exe:
        return None
    if agent == AGENT_CLAUDE:
        cmd = [exe, "-p", prompt, "--output-format", "stream-json", "--verbose"]
        if continue_session:
            cmd += ["--resume", resume_id] if resume_id else ["--continue"]
        if full_access:
            cmd.append("--dangerously-skip-permissions")
        return cmd
    if agent == AGENT_CODEX:
        if continue_session:
            cmd = [exe, "exec", "resume", resume_id or "--last", "--json"]
        else:
            cmd = [exe, "exec", "--json"]
        # The default DevelopTool workspace is a regular directory, not a git repository.
        cmd.append("--skip-git-repo-check")
        # Surface reasoning chain (思考链) in the JSONL stream.
        cmd += ["-c", "hide_agent_reasoning=false",
                "-c", "show_raw_agent_reasoning=true",
                "-c", "model_reasoning_summary=detailed"]
        if full_access:
            # YOLO: no approvals, no sandbox — the default for driving hardware.
            cmd.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            cmd += ["-c", 'sandbox_mode="workspace-write"'] if continue_session else ["-s", "workspace-write"]
        cmd.append(prompt)
        return cmd
    return None


def parse_claude_blocks(obj: dict) -> list[tuple[str, str, str]]:
    """Flatten one Claude event into a list of ``(kind, title, text)``."""
    etype = obj.get("type")
    if etype == "assistant":
        out: list[tuple[str, str, str]] = []
        for block in (obj.get("message") or {}).get("content") or []:
            btype = block.get("type")
            if btype == "text":
                text = (block.get("text") or "").strip()
                if text:
                    out.append(("token", "", text))
            elif btype == "thinking":
                thinking = (block.get("thinking") or "").strip()
                if thinking:
                    out.append(("think", "", thinking))
            elif btype == "tool_use":
                name = block.get("name") or "tool"
                inp = block.get("input") or {}
                detail = inp.get("command") or inp.get("description") \
                    or json.dumps(inp, ensure_ascii=False)[:400]
                out.append(("tool", str(name), str(detail)))
        return out
    if etype == "system" and obj.get("subtype") == "init":
        return [("session", "", str(obj.get("session_id") or ""))]
    return []


def parse_codex_event(obj: dict) -> tuple[str, str, str] | None:
    """Parse one Codex JSONL event into ``(kind, title, text)`` or None."""
    etype = obj.get("type")
    if etype == "item.completed":
        item = obj.get("item") or {}
        itype = item.get("type")
        if itype == "agent_message":
            text = (item.get("text") or "").strip()
            return ("token", "", text) if text else None
        if itype == "reasoning":
            text = item.get("text") or ""
            if isinstance(text, list):
                text = "\n".join(str(t) for t in text)
            text = text.strip()
            return ("think", "", text) if text else None
        if itype == "command_execution":
            cmd = str(item.get("command") or "")
            out = str(item.get("aggregated_output") or "").strip()
            return ("tool", cmd, out[:1200])
        if itype == "error":
            message = str(item.get("message") or "")
            # User config warnings are noise, not actionable agent output.
            if message.startswith("Codex is ignoring"):
                return None
            return ("tool", "error", message[:600])
        return None
    if etype == "thread.started":
        return ("session", "", str(obj.get("thread_id") or ""))
    return None


class AgentCliSession(QThread):
    """Run one non-interactive agent turn in a worker thread."""

    token       = Signal(str)          # assistant text chunk
    tool_event  = Signal(str, str)     # tool title, detail
    think       = Signal(str)          # reasoning / thinking chain chunk
    session_id  = Signal(str)          # CLI session/thread id (first turn)
    done        = Signal(int)          # process return code
    error       = Signal(str)          # fatal error message

    def __init__(self, agent: str, prompt: str, workspace: str,
                 continue_session: bool = False, full_access: bool = True,
                 parent=None, resume_id: str = ""):
        super().__init__(parent)
        self._agent = agent
        self._prompt = prompt
        self._workspace = workspace
        self._continue = continue_session
        self._full_access = full_access
        self._resume_id = resume_id
        self._proc: subprocess.Popen | None = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        proc = self._proc
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
            def kill_if_running():
                try:
                    if proc.poll() is None:
                        proc.kill()
                except OSError:
                    pass
            timer = threading.Timer(2, kill_if_running)
            timer.daemon = True
            timer.start()

    # ── internals ────────────────────────────────────────────────────────

    def _handle_line(self, line: str):
        line = line.rstrip("\n")
        if not line.strip():
            return
        # Per-line detection: JSONL events when parseable, plain-text
        # fallback otherwise (older CLIs, fatal error messages, ...).
        obj = None
        if line.lstrip().startswith("{"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                obj = None
        if obj is not None:
            if self._agent == AGENT_CLAUDE:
                for kind, title, text in parse_claude_blocks(obj):
                    self._emit(kind, title, text)
            else:
                ev = parse_codex_event(obj)
                if ev:
                    self._emit(*ev)
            return
        text = strip_ansi(line).rstrip()
        if text and not _NOISE_RE.match(text):
            self.token.emit(text + "\n")

    def _emit(self, kind: str, title: str, text: str):
        if kind == "token":
            # Chunked per event; add spacing between message blocks.
            self.token.emit(text + "\n")
        elif kind == "tool":
            self.tool_event.emit(title, text)
        elif kind == "think":
            self.think.emit(text)
        elif kind == "session":
            self.session_id.emit(text)

    def run(self):
        if self._cancelled:
            self.done.emit(-1)
            return
        cmd = build_command(self._agent, self._prompt,
                            continue_session=self._continue,
                            full_access=self._full_access, resume_id=self._resume_id)
        if cmd is None:
            self.error.emit(f"{self._agent} CLI not found")
            return
        log.info("agent session start: %s (cwd=%s)", self._agent, self._workspace)
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                cwd=self._workspace or None,
                text=True, encoding="utf-8", errors="replace",
            )
            if self._cancelled:
                self._proc.terminate()
        except FileNotFoundError:
            self.error.emit(f"{self._agent} CLI not found")
            return
        except Exception as exc:
            self.error.emit(str(exc))
            return

        try:
            assert self._proc.stdout is not None
            lines = queue.Queue(maxsize=256)

            def read_output():
                def put(item):
                    while not self._cancelled:
                        try:
                            lines.put(item, timeout=0.1)
                            return
                        except queue.Full:
                            pass
                try:
                    for line in self._proc.stdout:
                        if self._cancelled:
                            break
                        put(line)
                finally:
                    put(None)

            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            while not self._cancelled:
                try:
                    line = lines.get(timeout=0.1)
                except queue.Empty:
                    continue
                if line is None:
                    break
                self._handle_line(line)
            try:
                self._proc.wait(timeout=2 if self._cancelled else None)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=2)
            reader.join(timeout=0.2)
            if not reader.is_alive():
                self._proc.stdout.close()
        except Exception as exc:
            self.error.emit(str(exc))
            return
        rc = self._proc.returncode if self._proc.returncode is not None else -1
        if self._cancelled:
            self.done.emit(-1)
        else:
            self.done.emit(rc)
