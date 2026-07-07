import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from seeed_jetson_develop.gui.theme import pt
from seeed_jetson_develop.gui.widgets.onboarding_guide import OnboardingGuide, StepPage


class OnboardingLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_welcome_tip_has_room_for_supported_device_copy(self):
        page = StepPage(1, lang="zh-CN")

        self.assertIsNotNone(page._tip_container)
        self.assertIsNotNone(page._tip_lbl)
        self.assertGreaterEqual(page._tip_container.minimumWidth(), 360)
        self.assertGreaterEqual(page._tip_lbl.minimumWidth(), 320)
        self.assertEqual(page._tip_lbl.maximumHeight(), 16777215)

    def test_dismiss_and_skip_controls_share_header_centerline(self):
        guide = OnboardingGuide(lang="zh-CN")
        guide.show()
        self._app.processEvents()

        dismiss_center = guide._dismiss_cb.geometry().center().y()
        skip_center = guide._skip_btn.geometry().center().y()

        self.assertEqual(dismiss_center, skip_center)
        self.assertEqual(guide._dismiss_cb.minimumHeight(), pt(28))
        self.assertEqual(guide._dismiss_cb.maximumHeight(), pt(28))
        self.assertEqual(guide._skip_btn.minimumHeight(), pt(28))
        self.assertEqual(guide._skip_btn.maximumHeight(), pt(28))


if __name__ == "__main__":
    unittest.main()
