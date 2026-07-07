import unittest

from seeed_jetson_develop.modules.apps.registry import (
    AppParameterError,
    load_apps,
    mask_app_commands,
    render_app_commands,
)


def _param_app() -> dict:
    return {
        "id": "param-app",
        "install_cmds": [
            "curl -fsSL https://example.invalid/install.sh | bash -s -- --api-key {api_key} --yes"
        ],
        "install_params": [
            {
                "name": "api_key",
                "label": "API Key",
                "required": True,
                "secret": True,
                "help_url": "https://seeed-fleet.com/",
            }
        ],
    }


class AppRegistryTest(unittest.TestCase):
    def test_render_app_commands_quotes_secret_parameter(self):
        cmds = render_app_commands(_param_app(), {"api_key": "sk_test value"})

        self.assertEqual(
            cmds,
            [
                "curl -fsSL https://example.invalid/install.sh | bash -s -- --api-key 'sk_test value' --yes"
            ],
        )

    def test_render_app_commands_rejects_missing_required_parameter(self):
        with self.assertRaisesRegex(AppParameterError, "api_key"):
            render_app_commands(_param_app(), {"api_key": ""})

    def test_mask_app_commands_redacts_secret_parameter_value(self):
        cmds = render_app_commands(_param_app(), {"api_key": "sk_test_value"})

        self.assertEqual(
            mask_app_commands(_param_app(), cmds),
            [
                "curl -fsSL https://example.invalid/install.sh | bash -s -- --api-key *** --yes"
            ],
        )

    def test_mask_app_commands_redacts_secret_parameter_with_shell_special_chars(self):
        cmds = render_app_commands(_param_app(), {"api_key": "sk_test'value"})

        self.assertNotIn(
            "sk_test",
            mask_app_commands(_param_app(), cmds)[0],
        )

    def test_load_apps_contains_seeed_device_manager_metadata(self):
        app = next((item for item in load_apps() if item["id"] == "seeed-device-manager"), None)

        self.assertIsNotNone(app)
        self.assertEqual(app["name"], "Seeed Device Manager")
        self.assertEqual(app["category"], "Device Management")
        self.assertIn("{api_key}", app["install_cmds"][0])
        self.assertNotIn("sk_", app["install_cmds"][0])

        api_key_param = app["install_params"][0]
        self.assertEqual(api_key_param["name"], "api_key")
        self.assertIs(api_key_param["required"], True)
        self.assertIs(api_key_param["secret"], True)
        self.assertEqual(api_key_param["help_url"], "https://seeed-fleet.com/")

    def test_seeed_device_manager_installs_curl_before_download(self):
        app = next((item for item in load_apps() if item["id"] == "seeed-device-manager"), None)

        self.assertIsNotNone(app)
        command = app["install_cmds"][0]
        self.assertIn("command -v curl", command)
        self.assertIn("sudo apt-get install -y curl", command)
        self.assertLess(command.index("command -v curl"), command.index("curl -fsSL"))

    def test_seeed_device_manager_masks_api_key_with_shell_quotes(self):
        app = next((item for item in load_apps() if item["id"] == "seeed-device-manager"), None)

        self.assertIsNotNone(app)
        cmds = render_app_commands(app, {"api_key": "sk_test'value"})
        masked = mask_app_commands(app, cmds)[0]
        self.assertNotIn("sk_test", masked)
        self.assertNotIn("value", masked)
        self.assertTrue(masked.endswith("_ ***"))


if __name__ == "__main__":
    unittest.main()
