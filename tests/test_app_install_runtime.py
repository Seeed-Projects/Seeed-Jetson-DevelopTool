import unittest
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

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


if __name__ == "__main__":
    unittest.main()
