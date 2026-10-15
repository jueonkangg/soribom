"""발화 방향에 따른 문단 구분과 화면 보관량을 검증한다."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PySide6.QtWidgets import QApplication
from ui.app import CaptionView, SoribomUI


class CaptionGroupingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ui = SoribomUI({})
        self.ui.show_device_status("ready", "ready")
        self.addCleanup(self.ui.window.close)

    def test_same_direction_joins_and_exact_threshold_starts_paragraph(self):
        for text, angle in (("첫 문장.", 10), ("둘째 문장.", 14.9), ("새 방향.", 19.9)):
            self.ui.show_caption(text, angle)
        self.assertEqual(self.ui.caption_label.text(), "첫 문장. 둘째 문장.\n새 방향.")

    def test_layout_diagnostics_report_angles_and_reason_without_text(self):
        events = []
        self.ui.on_caption_layout = lambda **values: events.append(values)
        for text, angle in (("첫 문장", 359), ("둘째 문장", 1), ("새 문단", 6), ("미확정", None)):
            self.ui.show_caption(text, angle)
        self.assertEqual([event["layout_reason"] for event in events],
                         ["first", "same_direction", "direction_change", "unknown"])
        self.assertEqual(events[1]["direction_difference"], 2)
        self.assertFalse(events[1]["paragraph_break"])
        self.assertEqual(events[2]["direction_difference"], 5)
        self.assertTrue(events[2]["paragraph_break"])
        self.assertNotIn("text", events[0])

    def test_angle_is_visible_and_preserved_after_theme_change(self):
        self.ui.show_caption("방향 확인", 12.34)
        self.assertIn("12.3°", self.ui.dial_title.text())
        self.ui._toggle_theme()
        self.assertIn("12.3°", self.ui.dial_title.text())

    def test_wraparound_and_comparison_with_previous_utterance(self):
        for text, angle in (("하나", 359), ("둘", 1), ("셋", 5), ("넷", 10)):
            self.ui.show_caption(text, angle)
        self.assertEqual(self.ui.caption_label.text(), "하나 둘 셋\n넷")

    def test_unknown_and_invalid_direction_do_not_join_known_speaker(self):
        for text, angle in (("확정", 10), ("미확정", None), ("복귀", 10),
                            ("오류", float("nan")), ("다시", 10)):
            self.ui.show_caption(text, angle)
        self.assertEqual(self.ui.caption_label.text(), "확정\n미확정\n복귀\n오류\n다시")

    def test_disconnect_resets_direction_even_without_caption(self):
        self.ui.show_caption("연결 전", 10)
        self.ui.show_device_status("ready", "waiting")
        self.ui.show_device_status("ready", "ready")
        self.ui.show_caption("연결 후", 10)
        self.assertEqual(self.ui.caption_label.text(), "연결 전\n연결 후")

    def test_empty_caption_does_not_change_previous_utterance_direction(self):
        self.ui.show_caption("하나", 10)
        self.ui.show_caption("", 90)
        self.ui.show_caption("둘", 10)
        self.assertEqual(self.ui.caption_label.text(), "하나 둘")

    def test_long_pause_keeps_blank_line(self):
        with patch("ui.app.time.monotonic", side_effect=[100, 130]):
            self.ui.show_caption("이전", 10)
            self.ui.show_caption("이후", 10)
        self.assertEqual(self.ui.caption_label.text(), "이전\n\n이후")

    def test_threshold_is_configurable(self):
        ui = SoribomUI({"ui": {"caption_direction_break_degrees": 10}})
        self.addCleanup(ui.window.close)
        ui.show_device_status("ready", "ready")
        ui.show_caption("하나", 10)
        ui.show_caption("둘", 16)
        ui.show_caption("셋", 26)
        self.assertEqual(ui.caption_label.text(), "하나 둘\n셋")

    def test_character_limit_bounds_single_paragraph_and_keeps_latest_text(self):
        view = CaptionView(20, history_characters=100)
        self.addCleanup(view.close)
        for _ in range(100):
            view.append_caption("긴 문장입니다.", continue_paragraph=True)
        self.assertLessEqual(view.document().characterCount() - 1, 100)
        self.assertTrue(view.text().endswith("긴 문장입니다."))
        self.assertEqual(view.document().blockCount(), 1)

    def test_block_limit_and_automatic_scroll_remain(self):
        view = CaptionView(20)
        self.addCleanup(view.close)
        view.resize(300, 100)
        view.show()
        for number in range(100):
            view.append_caption(f"문장 {number}")
        self.app.processEvents()
        self.assertEqual(view.document().blockCount(), 20)
        self.assertTrue(view.text().endswith("문장 99"))
        self.assertEqual(view.verticalScrollBar().value(), view.verticalScrollBar().maximum())


if __name__ == "__main__":
    unittest.main()
