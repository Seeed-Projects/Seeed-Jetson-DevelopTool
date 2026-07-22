import unittest
import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QPushButton

from seeed_jetson_develop.core.runner import SSHRunner
from seeed_jetson_develop.modules.apps import page as apps_page


class SSHRunnerSudoWrapperTest(unittest.TestCase):
    def test_remote_shell_exports_sudo_function_for_nested_bash_scripts(self):
        runner = SSHRunner("192.0.2.10", password="pw", sudo_password="pw")

        command = runner._build_remote_shell_command("bash -lc 'sudo true'")

        self.assertIn("sudo() {", command)
        self.assertIn("command sudo -S -p", command)
        self.assertIn("export -f sudo", command)
        self.assertIn("SEEED_SUDO_PASSWORD=", command)

    def test_app_sudo_preflight_falls_back_to_ssh_login_password(self):
        runner = SSHRunner("192.0.2.10", password="login-pw", sudo_password="wrong-pw")
        saved = {
            "remote_last_password": "login-pw",
            "remote_last_sudo_password": "wrong-pw",
        }

        def fake_run(_cmd, timeout=30, **_kwargs):
            return (0, "") if runner.sudo_password == "login-pw" else (1, "incorrect password")

        runner.run = fake_run
        with patch.object(apps_page, "get_runner", return_value=runner), patch(
            "seeed_jetson_develop.core.config.load",
            side_effect=lambda: dict(saved),
        ), patch("seeed_jetson_develop.core.config.save") as save:
            ok = apps_page._ensure_ssh_sudo_password(None, ["sudo apt-get update"])

        self.assertTrue(ok)
        self.assertEqual(runner.sudo_password, "login-pw")
        self.assertEqual(save.call_args.args[0]["remote_last_sudo_password"], "login-pw")

    def test_sudo_command_detection_handles_nested_shell(self):
        self.assertTrue(apps_page._commands_require_sudo(["bash -lc 'sudo apt-get update'"]))
        self.assertFalse(apps_page._commands_require_sudo(["echo pseudo-command"]))


class AppInstallThreadCancelTest(unittest.TestCase):
    def test_install_thread_passes_cancel_callback_to_runner(self):
        original_get_runner = apps_page.get_runner
        thread = apps_page._InstallThread(["sleep 999"], app={"id": "test-app"})
        seen = {}

        class FakeRunner:
            def run(self, cmd, timeout=30, on_output=None, should_cancel=None):
                seen["cmd"] = cmd
                seen["timeout"] = timeout
                seen["has_cancel"] = should_cancel is not None
                thread.cancel()
                seen["cancelled"] = should_cancel()
                return -1, "cancelled"

        try:
            apps_page.get_runner = lambda: FakeRunner()
            thread.run()
        finally:
            apps_page.get_runner = original_get_runner

        self.assertEqual(seen["cmd"], "sleep 999")
        self.assertTrue(seen["has_cancel"])
        self.assertTrue(seen["cancelled"])


class AppsPageRefreshTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_show_event_refreshes_status_when_apps_are_loaded(self):
        page = apps_page.AppsPage()
        page.items_data = [{"id": "seeed-device-manager", "check_cmd": "true"}]
        calls = []
        page._start_check = lambda: calls.append("refresh")

        page.show()
        self._app.processEvents()

        self.assertIn("refresh", calls)

    def test_installed_app_with_stop_commands_shows_stop_button(self):
        page = apps_page.AppsPage()
        app = {
            "id": "test-service",
            "icon": "CV",
            "name": "Test Service",
            "desc": "Service with a stop action",
            "stop_cmds": ["pkill test-service"],
        }
        page._statuses[app["id"]] = "installed"

        row = page._build_row(app)
        button_texts = {button.text() for button in row.findChildren(QPushButton)}

        self.assertIn(apps_page._at("apps.action.stop"), button_texts)


class AppWebButtonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_web_url_uses_connected_ssh_host(self):
        runner = SSHRunner("192.0.2.25", password="pw", sudo_password="pw")

        self.assertEqual(
            apps_page._app_web_url({"web_port": 8080}, runner),
            "http://192.0.2.25:8080/",
        )

    @staticmethod
    def _web_app():
        return {
            "id": "jx-yolo26-tensorrt",
            "icon": "CV",
            "name": "YOLO26 TensorRT",
            "desc": "Native TensorRT browser preview",
            "web_port": 8080,
        }

    def test_successful_install_shows_web_button(self):
        dialog = apps_page._InstallDialog(
            self._web_app(),
            ["true"],
            mode="install",
        )

        dialog._on_done(True)

        self.assertFalse(dialog._web_btn.isHidden())

    def test_failed_install_keeps_web_button_hidden(self):
        dialog = apps_page._InstallDialog(
            self._web_app(),
            ["false"],
            mode="install",
        )

        dialog._on_done(False)

        self.assertTrue(dialog._web_btn.isHidden())

    def test_web_button_opens_browser_url(self):
        dialog = apps_page._InstallDialog(self._web_app(), ["true"], mode="install")

        with patch.object(apps_page, "_app_web_url", return_value="http://192.0.2.25:8080/"), patch.object(
            apps_page.QDesktopServices,
            "openUrl",
            return_value=True,
        ) as open_url:
            dialog._open_web_ui()

        self.assertEqual(open_url.call_count, 1)
        self.assertEqual(open_url.call_args.args[0].toString(), "http://192.0.2.25:8080/")


if __name__ == "__main__":
    unittest.main()
