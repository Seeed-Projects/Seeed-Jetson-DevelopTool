"""Tests for the NVIDIA Skills install dialog and list parsing.

NVIDIA skills are no longer bundled in the devtool; they are fetched
on demand via the `npx skills add nvidia/skills` CLI. These tests
verify the parsing logic and dialog structure.
"""
import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestNvidiaListParsing(unittest.TestCase):
    """Test the _parse method of _NvidiaListThread."""

    def _get_parse_method(self):
        """Import and return the static _parse method."""
        from seeed_jetson_develop.modules.skills.page import _NvidiaListThread
        return _NvidiaListThread._parse

    def test_parse_basic_output(self):
        """Parse a sample npx skills list output."""
        sample = """
◇ Found 349 skills

◇ Available Skills

| accelerated-computing-cudf
| Official NVIDIA-authored guidance for NVIDIA cuDF GPU DataFrames...

| aiq-deploy
| Use when asked to install, deploy, run, validate...

| deepstream-import-vision-model
| Use this skill to bring any vision model from HuggingFace...
"""
        parse = self._get_parse_method()
        skills = parse(sample)
        self.assertEqual(len(skills), 3)
        self.assertEqual(skills[0][0], "accelerated-computing-cudf")
        self.assertIn("cuDF", skills[0][1])
        self.assertEqual(skills[1][0], "aiq-deploy")
        self.assertEqual(skills[2][0], "deepstream-import-vision-model")

    def test_parse_empty_output(self):
        """Empty input should return empty list."""
        parse = self._get_parse_method()
        self.assertEqual(parse(""), [])
        self.assertEqual(parse("No skills found"), [])

    def test_parse_skips_header_lines(self):
        """Header lines like 'Available' should not be treated as skill names."""
        sample = """| Available Skills
| Source: https://github.com/nvidia/skills.git
"""
        parse = self._get_parse_method()
        skills = parse(sample)
        self.assertEqual(len(skills), 0)


class TestNvidiaSkillsDialogImport(unittest.TestCase):
    """Test that the dialog class can be imported."""

    def test_import_dialog(self):
        from seeed_jetson_develop.modules.skills.page import _NvidiaSkillsDialog
        self.assertTrue(callable(_NvidiaSkillsDialog))

    def test_import_threads(self):
        from seeed_jetson_develop.modules.skills.page import (
            _NvidiaListThread, _NvidiaInstallThread,
        )
        self.assertTrue(callable(_NvidiaListThread))
        self.assertTrue(callable(_NvidiaInstallThread))


if __name__ == "__main__":
    unittest.main()
