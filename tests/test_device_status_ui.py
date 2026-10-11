"""장치 장애 중 화면 기능을 유지하고 오래된 방향을 지우는지 확인한다."""
import os
from pathlib import Path
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PySide6.QtWidgets import QApplication
from ui.app import SoribomUI


class DeviceStatusUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_disconnect_preserves_captions_and_other_controls_in_both_themes(self):
        for theme in ("light", "dark"):
            ui = SoribomUI({"ui": {"theme": theme}})
            ui.show_device_status("ready", "ready")
            ui.show_caption("이미 기록된 문장", angle=90)
            self.assertEqual(ui.dial._angle, 90)
            ui.show_device_status("waiting", "waiting", "USB 연결 오류")
            self.assertIsNone(ui.dial._angle)
            self.assertIn("이미 기록된 문장", ui.caption_label.text())
            self.assertIn("기록되지 않습니다", ui.connection_label.text())
            self.assertTrue(ui.reconnect_button.isEnabled())
            for button in (ui.speak_button, ui.email_button, ui.summary_button):
                self.assertTrue(button.isEnabled())
            ui._toggle_theme()
            self.assertIn("USB", ui.connection_label.toolTip())
            ui.window.close()

    def test_doa_only_failure_still_shows_captions_but_never_stale_arrow(self):
        ui = SoribomUI({})
        ui.show_device_status("ready", "ready")
        ui.show_caption("첫 문장", angle=120)
        ui.show_device_status("ready", "waiting")
        ui.show_caption("방향 없이 새 문장", angle=120)
        self.assertIn("새 문장", ui.caption_label.text())
        self.assertIsNone(ui.dial._angle)
        self.assertIn("방향 확인 불가", ui.dial_title.text())
        ui.show_device_status("ready", "ready")
        ui.show_caption("재연결 후 문장", angle=45)
        self.assertEqual(ui.dial._angle, 45)
        ui.show_caption("방향 미확정", angle=None)
        self.assertIsNone(ui.dial._angle)
        self.assertIn("미확정", ui.dial_title.text())
        ui._toggle_theme()
        self.assertIn("미확정", ui.dial_title.text())
        ui.show_caption("방향 확정", angle=30)
        self.assertNotIn("미확정", ui.dial_title.text())
        ui.window.close()

    def test_preparation_and_reconnect_disable_duplicate_requests(self):
        ui = SoribomUI({})
        calls = []
        ui.on_reconnect = lambda: calls.append(1)
        ui.set_models_ready(False)
        self.assertFalse(ui.speak_button.isEnabled())
        self.assertTrue(ui.email_button.isEnabled())
        self.assertFalse(ui.reconnect_button.isEnabled())
        ui.set_models_ready(True)
        ui.show_device_status("waiting", "waiting")
        ui.reconnect_button.click()
        ui.reconnect_button.click()
        self.assertEqual(calls, [1])
        ui.show_device_status("connecting", "waiting")
        self.assertFalse(ui.reconnect_button.isEnabled())
        ui.show_device_status("waiting", "waiting")
        self.assertTrue(ui.reconnect_button.isEnabled())
        ui.show_device_status("ready", "disabled")
        self.assertTrue(ui.reconnect_button.isHidden())
        self.assertEqual(ui.dial_title.text(), "방향 표시 꺼짐")
        ui.window.close()


if __name__ == "__main__":
    unittest.main()
