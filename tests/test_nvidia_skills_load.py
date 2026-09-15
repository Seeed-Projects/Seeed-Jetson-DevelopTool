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


class TestNvidiaCatalog(unittest.TestCase):
    """Test classification of NVIDIA skills by run target and scenario."""

    def test_jetson_skills_target(self):
        from seeed_jetson_develop.modules.skills.nvidia_catalog import (
            nvidia_target, TARGET_JETSON, TARGET_PC, TARGET_BOTH,
        )
        for name in ("jetson-quick-start", "jetson-flash-image",
                     "jetson-customize-clocks", "jetson-video-pipeline",
                     "jetson-llm-serve"):
            self.assertEqual(nvidia_target(name), TARGET_JETSON, name)
        self.assertEqual(nvidia_target("cuopt-install"), TARGET_PC)
        self.assertEqual(nvidia_target("unknown-skill-xyz"), TARGET_PC)

    def test_edge_video_stack_runs_on_both(self):
        from seeed_jetson_develop.modules.skills.nvidia_catalog import (
            nvidia_target, TARGET_BOTH,
        )
        for name in ("deepstream-dev", "vss-deploy-profile",
                     "holoscan-setup", "hsb-app", "rtvi-cv-customize-model",
                     "amc-run-video-calibration", "holohub-app-lifecycle"):
            self.assertEqual(nvidia_target(name), TARGET_BOTH, name)

    def test_categories(self):
        from seeed_jetson_develop.modules.skills.nvidia_catalog import (
            nvidia_category, CATEGORY_JETSON_SYSTEM, CATEGORY_VIDEO_AI,
            CATEGORY_EDGE_LLM, CATEGORY_GENAI, CATEGORY_VISION_TRAIN,
            CATEGORY_MEDICAL, CATEGORY_HPC, CATEGORY_DOCA, CATEGORY_ROBOTICS,
            CATEGORY_OTHER,
        )
        cases = {
            "jetson-flash-image": CATEGORY_JETSON_SYSTEM,
            "jetson-diagnostic": CATEGORY_JETSON_SYSTEM,
            "jetson-video-pipeline": CATEGORY_VIDEO_AI,
            "deepstream-sop": CATEGORY_VIDEO_AI,
            "vss-search-archive": CATEGORY_VIDEO_AI,
            "jetson-llm-serve": CATEGORY_EDGE_LLM,
            "jetson-speculative-decoding": CATEGORY_EDGE_LLM,
            "nemo-mbridge-perf-cuda-graphs": CATEGORY_GENAI,
            "nemotron-customize": CATEGORY_GENAI,
            "mcore-testing": CATEGORY_GENAI,
            "rag-blueprint": CATEGORY_GENAI,
            "tao-train-dino": CATEGORY_VISION_TRAIN,
            "dicom-series-to-volume": CATEGORY_MEDICAL,
            "nv-segment-ct": CATEGORY_MEDICAL,
            "medtech-model-evidence-export": CATEGORY_MEDICAL,
            "cuopt-numerical-optimization-api": CATEGORY_HPC,
            "cupynumeric-install": CATEGORY_HPC,
            "earth2studio-discover": CATEGORY_HPC,
            "warp-eval": CATEGORY_HPC,
            "doca-flow": CATEGORY_DOCA,
            "doca-setup": CATEGORY_DOCA,
            "omniverse-cad-to-simready": CATEGORY_ROBOTICS,
            "i4h-workflow": CATEGORY_ROBOTICS,
            "physical-ai-video-data-augmentation": CATEGORY_ROBOTICS,
            "paidf-auto-labeling": CATEGORY_ROBOTICS,
            "skill-card-generator": CATEGORY_OTHER,
            "totally-unknown-future-skill": CATEGORY_OTHER,
        }
        for name, cat in cases.items():
            self.assertEqual(nvidia_category(name), cat, name)

    def test_category_labels_exist(self):
        from seeed_jetson_develop.modules.skills.nvidia_catalog import (
            CATEGORIES, category_label, target_label,
        )
        for key in CATEGORIES:
            self.assertTrue(category_label(key))
        self.assertTrue(target_label("jetson"))
        self.assertTrue(target_label("pc"))
        self.assertTrue(target_label("both"))

    def test_target_matches_filter(self):
        from seeed_jetson_develop.modules.skills.nvidia_catalog import (
            target_matches, TARGET_JETSON, TARGET_PC, TARGET_BOTH,
        )
        self.assertTrue(target_matches(TARGET_JETSON, "all"))
        self.assertTrue(target_matches(TARGET_JETSON, TARGET_JETSON))
        self.assertFalse(target_matches(TARGET_JETSON, TARGET_PC))
        self.assertTrue(target_matches(TARGET_BOTH, TARGET_JETSON))
        self.assertTrue(target_matches(TARGET_BOTH, TARGET_PC))


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
