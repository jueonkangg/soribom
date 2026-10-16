"""모델·스피커 없이 중복 요청, 입력 보존, 재시도와 화면 갱신을 검증한다."""
import os
from pathlib import Path
import sys
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PySide6.QtWidgets import QApplication
from ui.app import SoribomUI


class SpeechUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ui = SoribomUI({"tts": {"max_chars": 200}})
        self.addCleanup(self.ui.window.close)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertTrue(predicate())

    def test_burst_requests_run_once_and_captions_continue(self):
        release = threading.Event()
        started = threading.Event()
        calls = []
        def speak(text):
            calls.append(text)
            started.set()
            release.wait(3)
        self.ui.on_speak = speak
        self.ui.input_box.setText("질문이 있습니다")
        try:
            self.ui._on_enter()
            self.assertTrue(started.wait(1))
            for _ in range(100):
                self.ui._on_enter()
                self.ui.speak_button.click()
            self.ui.set_models_ready(True)
            self.assertFalse(self.ui.speak_button.isEnabled())
            self.assertTrue(self.ui.input_box.isEnabled())
            self.assertTrue(all(not button.isEnabled() for button in self.ui.voice_buttons))
            self.ui.show_caption("말하기 중에도 새 자막")
            self.assertIn("새 자막", self.ui.caption_label.text())
            self.assertEqual(calls, ["질문이 있습니다"])
            self.assertEqual(self.ui.input_box.text(), "질문이 있습니다")
        finally:
            release.set()
            self.wait_for(lambda: not self.ui._speaking)
        self.assertEqual(self.ui.input_box.text(), "")
        self.assertTrue(self.ui.speak_button.isEnabled())
        self.assertTrue(all(button.isEnabled() for button in self.ui.voice_buttons))

    def test_voice_buttons_are_exclusive_and_follow_model_readiness(self):
        calls = []
        self.ui.on_voice_change = calls.append
        male, female = self.ui.voice_buttons
        self.assertTrue(female.isChecked())
        male.click()
        self.assertTrue(male.isChecked())
        self.assertFalse(female.isChecked())
        female.click()
        self.assertEqual(calls, [5, 0])
        self.ui.set_models_ready(False)
        male.click()
        self.assertEqual(calls, [5, 0])
        self.ui.set_models_ready(True)
        male.click()
        self.assertEqual(calls, [5, 0, 5])

    def test_configured_male_voice_is_selected_initially(self):
        ui = SoribomUI({"tts": {"sid": 5}})
        self.addCleanup(ui.window.close)
        self.assertEqual(ui.voice_group.checkedId(), 5)

    def test_editing_next_sentence_during_playback_preserves_it_and_allows_next_enter(self):
        release = threading.Event()
        entered = threading.Event()
        def speak(text):
            entered.set()
            release.wait(3)
        self.ui.on_speak = speak
        self.ui.input_box.setText("첫 문장")
        self.ui._on_enter()
        try:
            self.assertTrue(entered.wait(1))
            self.assertTrue(self.ui.input_box.isEnabled())
            self.ui.input_box.setText("다음 문장")
            self.ui.show_caption("음성 인식도 계속 진행")
            self.ui._on_enter()
        finally:
            release.set()
            self.wait_for(lambda: not self.ui._speaking)
        self.assertEqual(self.ui.input_box.text(), "다음 문장")
        calls = []
        self.ui.on_speak = calls.append
        self.ui._on_enter()
        self.wait_for(lambda: not self.ui._speaking)
        self.assertEqual(calls, ["다음 문장"])

    def test_output_failure_keeps_input_and_retry_succeeds_in_both_themes(self):
        def fail(text):
            raise RuntimeError("output disconnected")
        for theme in ("light", "dark"):
            self.ui.theme = theme
            self.ui._repaint_theme()
            self.ui.on_speak = fail
            self.ui.input_box.setText("다시 말할 문장")
            self.ui._on_enter()
            self.wait_for(lambda: not self.ui._speaking)
            self.assertEqual(self.ui.input_box.text(), "다시 말할 문장")
            self.assertIn("스피커 연결", self.ui.speech_status.text())
            self.assertTrue(self.ui.speak_button.isEnabled())
            self.ui._toggle_theme()
            self.assertIn("스피커 연결", self.ui.speech_status.text())
            self.ui.on_speak = lambda text: None
            self.ui._on_enter()
            self.wait_for(lambda: not self.ui._speaking)
            self.assertEqual(self.ui.input_box.text(), "")

    def test_long_input_is_preserved_without_starting_worker(self):
        calls = []
        self.ui.on_speak = calls.append
        self.ui.input_box.setText("가" * 201)
        self.ui._on_enter()
        self.assertEqual(calls, [])
        self.assertEqual(len(self.ui.input_box.text()), 201)
        self.assertIn("200자", self.ui.speech_status.text())

    def test_synthesis_failure_is_distinguished_from_output_failure(self):
        class SpeechSynthesisError(RuntimeError):
            pass
        def fail(text):
            raise SpeechSynthesisError("synthesis failed")
        self.ui.on_speak = fail
        self.ui.input_box.setText("다시 말할 문장")
        self.ui._on_enter()
        self.wait_for(lambda: not self.ui._speaking)
        self.assertIn("음성 합성", self.ui.speech_status.text())
        self.assertNotIn("스피커 연결", self.ui.speech_status.text())
        self.assertEqual(self.ui.input_box.text(), "다시 말할 문장")
        self.assertTrue(self.ui.speak_button.isEnabled())

    def test_save_failure_remains_visible_until_recovery(self):
        self.ui.show_note_status(False, "기록 저장 실패")
        for _ in range(2):
            self.ui._toggle_theme()
            self.assertIn("저장 실패", self.ui.note_status.text())
            self.assertTrue(self.ui.email_button.isEnabled())
        self.ui.show_note_status(True, "수업 기록 저장됨")
        self.assertFalse(self.ui._note_failed)
        self.assertEqual(self.ui.note_status.text(), "수업 기록 저장됨")
