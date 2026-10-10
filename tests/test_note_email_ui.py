"""실제 메일·마이크 없이 Qt 전송 창과 자막 갱신을 검증한다."""
import os
from pathlib import Path
import sys
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication
from summary.email_sender import NoteEmailError
from ui.app import NoteEmailDialog, SoribomUI


class NoteEmailUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_for(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertTrue(predicate())

    def test_both_themes_and_empty_snapshot(self):
        for theme in ["light", "dark"]:
            ui = SoribomUI({"ui": {"theme": theme}})
            dialog = NoteEmailDialog(ui.window, "", lambda *_: None, ui._styles())
            self.assertTrue(dialog.preview.isReadOnly())
            self.assertFalse(dialog.send_button.isEnabled())
            self.assertEqual(dialog.recipient.text(), "")
            self.assertEqual(ui.email_button.text(), "노트 보내기")
            ui._toggle_theme()
            self.assertEqual(ui.email_button.styleSheet(), ui._styles()["summary_button"])
            dialog.close()
            ui.window.close()

    def test_sending_blocks_duplicates_and_close_but_not_captions(self):
        ui = SoribomUI({})
        ui.show_device_status("ready", "ready")
        calls = []
        release = threading.Event()

        def send(address, transcript):
            calls.append((address, transcript))
            release.wait(2)

        snapshot = "수업 기록\n• 첫 문장."
        dialog = NoteEmailDialog(ui.window, snapshot, send, ui._styles())
        ui._email_dialog = dialog
        ui.window.show()
        dialog.show()
        dialog.recipient.setText("student@example.com")
        try:
            dialog.send_button.click()
            dialog._send()
            self.wait_for(lambda: len(calls) == 1)
            dialog.reject()
            dialog.close()
            ui.window.close()
            self.assertTrue(dialog.isVisible())
            self.assertTrue(ui.window.isVisible())
            self.assertFalse(dialog.close_button.isEnabled())
            ui.show_caption("전송 중 들어온 새 자막", angle=90)
            self.app.processEvents()
            self.assertIn("새 자막", ui.caption_label.text())
            self.assertEqual(ui.dial._angle, 90)
            self.assertEqual(dialog.preview.toPlainText(), snapshot)
            release.set()
            self.wait_for(lambda: not dialog.sending)
            self.assertIn("메일 서버에 전송했습니다", dialog.status.text())
            self.assertFalse(dialog.send_button.isEnabled())
            self.assertEqual(calls, [("student@example.com", snapshot)])
        finally:
            release.set()
            self.wait_for(lambda: not dialog.sending)
            ui._email_dialog = None
            dialog.close()
            ui.window.close()

    def test_invalid_address_and_failure_keep_input_and_allow_retry(self):
        ui = SoribomUI({})
        calls = []

        def fail(*args):
            calls.append(args)
            raise NoteEmailError("인터넷 연결을 확인해주세요.")

        dialog = NoteEmailDialog(ui.window, "• 수업 기록.", fail, ui._styles())
        dialog.recipient.setText("잘못된 주소")
        dialog.send_button.click()
        self.assertEqual(calls, [])
        self.assertIn("주소", dialog.status.text())
        dialog.recipient.setText("student@example.com")
        dialog.send_button.click()
        self.wait_for(lambda: not dialog.sending)
        self.assertEqual(dialog.recipient.text(), "student@example.com")
        self.assertEqual(dialog.preview.toPlainText(), "• 수업 기록.")
        self.assertTrue(dialog.send_button.isEnabled())
        self.assertTrue(dialog.close_button.isEnabled())
        self.assertIn("인터넷", dialog.status.text())
        dialog.close()
        ui.window.close()


if __name__ == "__main__":
    unittest.main()
