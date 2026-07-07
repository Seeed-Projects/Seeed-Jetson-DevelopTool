import os
import subprocess
import sys
import unittest
from pathlib import Path


class RunV2MacOSTest(unittest.TestCase):
    def test_bootstrap_only_does_not_require_x11_display_on_macos(self):
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.pop("DISPLAY", None)
        env["SEEED_SKIP_DEPS_CHECK"] = "1"
        env["SEEED_BOOTSTRAP_ONLY"] = "1"

        result = subprocess.run(
            [sys.executable, "run_v2.py", "--debug-console"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("bootstrap-only", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
