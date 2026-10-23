"""Tests for the Agent page backend (local claude/codex CLI wrapper)."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seeed_jetson_develop.modules.agent.backend import (
    build_command, parse_claude_blocks, parse_codex_event, strip_ansi,
)
from seeed_jetson_develop.modules.agent.cli_tools import (
    AGENT_CLAUDE, AGENT_CODEX, local_skills_dir, local_skills_dirs,
    npx_agent_arg, npm_package, remote_skills_dir,
)


class TestBuildCommand(unittest.TestCase):
    def setUp(self):
        # Patch CLI lookup so tests do not depend on the host environment.
        patcher = patch(
            "seeed_jetson_develop.modules.agent.backend.find_cli",
            side_effect=lambda agent: f"/usr/bin/{agent}",
        )
        self._mock = patcher.start()
        self.addCleanup(patcher.stop)

    def test_claude_first_turn(self):
        cmd = build_command(AGENT_CLAUDE, "hello", continue_session=False,
                            full_access=True)
        self.assertEqual(cmd[0], "/usr/bin/claude")
        self.assertIn("-p", cmd)
        self.assertIn("hello", cmd)
        self.assertIn("--output-format", cmd)
        self.assertIn("stream-json", cmd)
        self.assertIn("--verbose", cmd)
        self.assertIn("--dangerously-skip-permissions", cmd)
        self.assertNotIn("--continue", cmd)

    def test_claude_continue_no_full_access(self):
        cmd = build_command(AGENT_CLAUDE, "next", continue_session=True,
                            full_access=False)
        self.assertIn("--continue", cmd)
        self.assertNotIn("--dangerously-skip-permissions", cmd)

    def test_codex_first_turn(self):
        cmd = build_command(AGENT_CODEX, "hello", continue_session=False,
                            full_access=False)
        self.assertEqual(cmd[0], "/usr/bin/codex")
        self.assertEqual(cmd[1], "exec")
        self.assertIn("--json", cmd)
        self.assertIn("-s", cmd)
        self.assertIn("workspace-write", cmd)
        self.assertEqual(cmd[-1], "hello")

    def test_codex_resume_full_access(self):
        cmd = build_command(AGENT_CODEX, "next", continue_session=True,
                            full_access=True)
        self.assertEqual(cmd[1:4], ["exec", "resume", "--last"])
        self.assertIn("--json", cmd)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", cmd)
        self.assertEqual(cmd[-1], "next")

    def test_missing_cli_returns_none(self):
        with patch("seeed_jetson_develop.modules.agent.backend.find_cli",
                   return_value=None):
            self.assertIsNone(build_command(AGENT_CLAUDE, "hi"))
        self.assertIsNone(build_command("unknown-agent", "hi"))


class TestClaudeEventParsing(unittest.TestCase):
    def test_assistant_text(self):
        obj = {"type": "assistant",
               "message": {"content": [{"type": "text", "text": "OK"}]}}
        events = parse_claude_blocks(obj)
        self.assertEqual(events, [("token", "", "OK")])

    def test_assistant_tool_use(self):
        obj = {"type": "assistant",
               "message": {"content": [
                   {"type": "text", "text": "Let me check."},
                   {"type": "tool_use", "name": "Bash",
                    "input": {"command": "ls -la"}},
               ]}}
        events = parse_claude_blocks(obj)
        self.assertIn(("token", "", "Let me check."), events)
        self.assertIn(("tool", "Bash", "ls -la"), events)

    def test_assistant_thinking(self):
        obj = {"type": "assistant",
               "message": {"content": [
                   {"type": "thinking", "thinking": "Reasoning here..."},
                   {"type": "text", "text": "Answer."},
               ]}}
        events = parse_claude_blocks(obj)
        self.assertIn(("think", "", "Reasoning here..."), events)
        self.assertIn(("token", "", "Answer."), events)

    def test_session_init(self):
        obj = {"type": "system", "subtype": "init", "session_id": "abc-123"}
        events = parse_claude_blocks(obj)
        self.assertEqual(events, [("session", "", "abc-123")])

    def test_noise_events_ignored(self):
        self.assertEqual(parse_claude_blocks(
            {"type": "system", "subtype": "thinking_tokens"}), [])
        self.assertEqual(parse_claude_blocks(
            {"type": "result", "subtype": "success", "result": "OK"}), [])
        self.assertEqual(parse_claude_blocks({"type": "user"}), [])


class TestCodexEventParsing(unittest.TestCase):
    def test_agent_message(self):
        obj = {"type": "item.completed",
               "item": {"id": "item_2", "type": "agent_message", "text": "OK"}}
        self.assertEqual(parse_codex_event(obj), ("token", "", "OK"))

    def test_command_execution(self):
        obj = {"type": "item.completed",
               "item": {"type": "command_execution",
                        "command": "v4l2-ctl --list-devices",
                        "aggregated_output": "video0\n"}}
        kind, title, text = parse_codex_event(obj)
        self.assertEqual(kind, "tool")
        self.assertEqual(title, "v4l2-ctl --list-devices")
        self.assertIn("video0", text)

    def test_error_item(self):
        obj = {"type": "item.completed",
               "item": {"type": "error", "message": "boom"}}
        self.assertEqual(parse_codex_event(obj), ("tool", "error", "boom"))

    def test_config_warning_filtered(self):
        obj = {"type": "item.completed",
               "item": {"type": "error",
                        "message": "Codex is ignoring 3 unrecognized "
                                   "configuration settings."}}
        self.assertIsNone(parse_codex_event(obj))

    def test_thread_started(self):
        obj = {"type": "thread.started", "thread_id": "tid-1"}
        self.assertEqual(parse_codex_event(obj), ("session", "", "tid-1"))

    def test_reasoning_item(self):
        obj = {"type": "item.completed",
               "item": {"type": "reasoning",
                        "text": "**Planning**\n\nFirst check cameras."}}
        kind, _title, text = parse_codex_event(obj)
        self.assertEqual(kind, "think")
        self.assertIn("Planning", text)
        # text may also be a list of chunks
        obj2 = {"type": "item.completed",
                "item": {"type": "reasoning", "text": ["a", "b"]}}
        self.assertEqual(parse_codex_event(obj2), ("think", "", "a\nb"))

    def test_turn_events_ignored(self):
        self.assertIsNone(parse_codex_event({"type": "turn.started"}))
        self.assertIsNone(parse_codex_event(
            {"type": "turn.completed", "usage": {}}))
        self.assertIsNone(parse_codex_event(
            {"type": "item.completed",
             "item": {"type": "unknown_type", "text": "..."}}))


class TestAnsiStrip(unittest.TestCase):
    def test_strip_ansi(self):
        self.assertEqual(strip_ansi("\x1b[32mgreen\x1b[0m"), "green")
        self.assertEqual(strip_ansi("plain"), "plain")


class TestCliToolsConventions(unittest.TestCase):
    def test_skills_dirs(self):
        self.assertTrue(str(local_skills_dir(AGENT_CLAUDE)).endswith(
            ".claude/skills"))
        codex_dirs = [str(d) for d in local_skills_dirs(AGENT_CODEX)]
        self.assertTrue(any(d.endswith(".agents/skills") for d in codex_dirs))
        self.assertTrue(any(d.endswith(".codex/skills") for d in codex_dirs))

    def test_remote_skills_dir(self):
        self.assertEqual(remote_skills_dir(AGENT_CLAUDE), ".claude/skills")
        self.assertEqual(remote_skills_dir(AGENT_CODEX), ".codex/skills")

    def test_npx_agent_arg(self):
        self.assertEqual(npx_agent_arg(AGENT_CLAUDE), "claude-code")
        self.assertEqual(npx_agent_arg(AGENT_CODEX), "codex")

    def test_npm_package(self):
        self.assertEqual(npm_package(AGENT_CLAUDE), "@anthropic-ai/claude-code")
        self.assertEqual(npm_package(AGENT_CODEX), "@openai/codex")


class TestNvidiaInstallAgentArg(unittest.TestCase):
    """The skills page install thread must accept an agent parameter."""

    def test_install_thread_signature(self):
        import inspect
        from seeed_jetson_develop.modules.skills.page import (
            _NvidiaInstallThread, _NvidiaRemoteInstallThread,
            _AgentCheckThread, _CodexCheckThread,
        )
        self.assertIn("agent",
                      inspect.signature(_NvidiaInstallThread.__init__).parameters)
        self.assertIn("agent",
                      inspect.signature(_NvidiaRemoteInstallThread.__init__).parameters)
        self.assertIn("agent",
                      inspect.signature(_AgentCheckThread.__init__).parameters)
        # Backward-compat alias still constructible with runner only.
        self.assertEqual(
            list(inspect.signature(_CodexCheckThread.__init__).parameters),
            ["self", "runner"],
        )

    def test_get_installed_accepts_agent(self):
        import inspect
        from seeed_jetson_develop.modules.skills.page import (
            _get_installed_nvidia_skills,
        )
        self.assertIn("agent", inspect.signature(
            _get_installed_nvidia_skills).parameters)


if __name__ == "__main__":
    unittest.main()
