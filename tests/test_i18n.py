import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from seeed_jetson_develop.core import config
from seeed_jetson_develop.gui import i18n


class LanguageConfigTests(unittest.TestCase):
    def test_normalize_language_accepts_supported_regional_aliases(self):
        cases = {
            "en-US": "en",
            "fr-FR": "fr",
            "fr_FR.UTF-8": "fr",
            "es-ES": "es",
            "de_DE": "de",
            "zh": "zh-CN",
            "zh_CN.UTF-8": "zh-CN",
        }

        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(config.normalize_language(source), expected)

    def test_normalize_language_falls_back_to_english(self):
        self.assertEqual(config.normalize_language("ja-JP"), "en")
        self.assertEqual(config.normalize_language(""), "en")
        self.assertEqual(config.normalize_language(None), "en")

    def test_get_language_uses_system_language_when_config_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.json"
            with patch.object(config, "_CONFIG_PATH", cfg_path), patch.dict(
                os.environ,
                {"LANGUAGE": "", "LC_ALL": "", "LC_MESSAGES": "", "LANG": "fr_FR.UTF-8"},
                clear=False,
            ):
                self.assertEqual(config.get_language(), "fr")

    def test_get_language_saved_config_wins_over_system_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.json"
            cfg_path.write_text(json.dumps({"language": "de-DE"}), encoding="utf-8")
            with patch.object(config, "_CONFIG_PATH", cfg_path), patch.dict(
                os.environ,
                {"LANG": "fr_FR.UTF-8"},
                clear=False,
            ):
                self.assertEqual(config.get_language(), "de")


class GuiI18nTests(unittest.TestCase):
    def test_language_options_are_user_facing_and_ordered(self):
        self.assertEqual(
            i18n.language_options(),
            [
                ("en", "English"),
                ("fr", "Français"),
                ("es", "Español"),
                ("de", "Deutsch"),
                ("zh-CN", "中文"),
            ],
        )

    def test_t_uses_default_when_key_is_missing(self):
        self.assertEqual(
            i18n.t("missing.data.backed.string", lang="fr", default="Raw item name"),
            "Raw item name",
        )


if __name__ == "__main__":
    unittest.main()
