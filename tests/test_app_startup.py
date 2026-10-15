"""모델 준비 중에도 화면을 유지하고 종료 뒤 장치를 늦게 열지 않는지 확인한다."""
import os
import gc
from pathlib import Path
import sys
import threading
import time
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import main
from ui.app import SoribomUI
from summary.notes import NoteBuilder


class AppStartupTests(unittest.TestCase):
    def setUp(self):
        # 이전 시험의 Qt 객체 정리는 새 모델 워커를 시작하기 전에 GUI 스레드에서 한다.
        gc.collect()

    def run_startup(self, close_early, save_notes=False):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        cfg = {"audio": {}, "doa": {"enabled": False}, "vad": {}, "stt": {},
               "tts": {}, "summary": {"enabled": save_notes, "output_dir": directory.name}, "events": {"enabled": False}}
        notes = NoteBuilder(cfg["summary"])
        self.addCleanup(notes.stop_autosave)
        ui = SoribomUI(cfg)
        started = threading.Event()
        release = threading.Event()
        workers = []
        device = Mock()
        device.start.side_effect = lambda: ui.show_device_status("waiting", "disabled")
        def load_stt(*_):
            started.set()
            release.wait(3)
            return Mock()
        vad = Mock()
        vad.stream.return_value = iter(())
        speaker = Mock()
        def wait_for(predicate):
            deadline = time.monotonic() + 3
            while not predicate() and time.monotonic() < deadline:
                ui.app.processEvents()
                time.sleep(0.01)
            self.assertTrue(predicate())
        def run_screen():
            wait_for(started.is_set)
            workers.extend(thread for thread in threading.enumerate() if thread.name == "model-loading")
            self.assertFalse(ui.speak_button.isEnabled())
            self.assertTrue(ui.email_button.isEnabled())
            if save_notes:
                self.assertTrue(notes._worker.is_alive())
                notes.add("종료 직전에 도착한 마지막 문장", 0)
            if close_early:
                return
            release.set()
            wait_for(lambda: ui._models_ready and device.start.called)
            self.assertTrue(ui.speak_button.isEnabled())
            self.assertTrue(ui.summary_button.isEnabled())
            self.assertIn("마이크 연결", ui.connection_label.text())
            ui.subject_box.setCurrentIndex(ui.subject_box.findData("math"))
            notes.add("과목 변경 연결 확인", 0)
            self.assertIn("과목: 수학", notes.build_email_transcript())
        modules = {"stt.transcriber": SimpleNamespace(Transcriber=load_stt),
                   "tts.speaker": SimpleNamespace(Speaker=speaker)}
        try:
            with patch.dict(sys.modules, modules), patch("main.load_config", return_value=cfg), \
                 patch("ui.app.SoribomUI", return_value=ui), \
                 patch("audio.vad.VoiceActivityDetector", return_value=vad), \
                 patch("audio.recovery.DeviceController", return_value=device), \
                 patch("summary.notes.NoteBuilder", return_value=notes), \
                 patch.object(ui, "run", side_effect=run_screen):
                main.main()
                release.set()
                for worker in workers:
                    worker.join(2)
                    self.assertFalse(worker.is_alive())
            device.stop.assert_called_once()
            if save_notes:
                self.assertFalse(notes._worker.is_alive())
                self.assertIn("마지막 문장", notes.path.read_text())
            if close_early:
                device.start.assert_not_called()
                speaker.assert_not_called()
            else:
                device.start.assert_called_once()
                speaker.assert_called_once()
        finally:
            release.set()
            ui.window.close()

    def test_ui_available_during_model_loading_and_without_microphone(self):
        self.run_startup(close_early=False)

    def test_close_during_loading_never_opens_microphone_later(self):
        self.run_startup(close_early=True)

    def test_shutdown_stops_autosave_and_flushes_latest_note_during_loading(self):
        self.run_startup(close_early=True, save_notes=True)

    def check_failed_model_retry(self, fail_warmup):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        cfg = {"audio": {}, "doa": {"enabled": False}, "vad": {},
               "stt": {"warmup": fail_warmup}, "tts": {},
               "summary": {"enabled": False, "output_dir": directory.name},
               "events": {"enabled": False}}
        ui = SoribomUI(cfg)
        self.addCleanup(ui.window.close)
        release = threading.Event()
        second_started = threading.Event()
        self.addCleanup(release.set)
        calls = []
        stt = Mock()
        stt.last_hotword_stats = {}
        if fail_warmup:
            stt.transcribe.side_effect = [RuntimeError("CUDA out of memory"), ""]
        def load_stt(*args):
            calls.append(1)
            if len(calls) == 1 and not fail_warmup:
                raise RuntimeError("CUDA out of memory")
            if len(calls) == 2:
                second_started.set()
                release.wait(3)
            return stt
        device = Mock()
        device.start.side_effect = lambda: ui.show_device_status("waiting", "disabled")
        vad = Mock()
        vad.stream.return_value = iter(())
        speaker = Mock()
        def wait_for(predicate):
            deadline = time.monotonic() + 3
            while not predicate() and time.monotonic() < deadline:
                ui.app.processEvents()
                time.sleep(0.01)
            self.assertTrue(predicate())
        def run_screen():
            wait_for(lambda: ui._device_state[0] == "model_failed")
            self.assertTrue(ui.startup_window.retry.isVisible())
            self.assertIn("준비에 실패", ui.startup_window.status.text())
            self.assertFalse(ui.input_box.isEnabled())
            self.assertTrue(ui.reconnect_button.isEnabled())
            self.assertEqual(ui.reconnect_button.text(), "모델 준비 재시도")
            self.assertIn("메모리", ui.connection_label.text())
            device.start.assert_not_called()
            speaker.assert_not_called()
            ui.startup_window.retry.click()
            self.assertTrue(second_started.wait(1))
            self.assertFalse(ui.reconnect_button.isEnabled())
            for _ in range(20):
                ui.on_retry_models()
            self.assertEqual(len(calls), 2)
            release.set()
            wait_for(lambda: ui._models_ready and device.start.called)
            self.assertTrue(ui.input_box.isEnabled())
            # 모델 준비 후에는 같은 버튼이 마이크 재연결로 돌아온다.
            ui.reconnect_button.click()
            device.retry.assert_called_once()
        modules = {"stt.transcriber": SimpleNamespace(Transcriber=load_stt),
                   "tts.speaker": SimpleNamespace(Speaker=speaker)}
        with patch.dict(sys.modules, modules), patch("main.load_config", return_value=cfg), \
             patch("ui.app.SoribomUI", return_value=ui), \
             patch("audio.vad.VoiceActivityDetector", return_value=vad), \
             patch("audio.recovery.DeviceController", return_value=device), \
             patch.object(ui, "run", side_effect=run_screen):
            main.main()
        self.assertEqual(len(calls), 2)
        device.start.assert_called_once()
        speaker.assert_called_once()

    def test_failed_model_load_can_retry_without_duplicate_workers(self):
        self.check_failed_model_retry(fail_warmup=False)

    def test_failed_warmup_retries_before_loading_speech_model(self):
        self.check_failed_model_retry(fail_warmup=True)


if __name__ == "__main__":
    unittest.main()
