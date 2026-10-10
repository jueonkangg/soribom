"""모델 준비 중에도 화면을 유지하고 종료 뒤 장치를 늦게 열지 않는지 확인한다."""
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import main
from ui.app import SoribomUI


class AppStartupTests(unittest.TestCase):
    def run_startup(self, close_early):
        cfg = {"audio": {}, "doa": {"enabled": False}, "vad": {}, "stt": {},
               "tts": {}, "summary": {"enabled": False}, "events": {"enabled": False}}
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
            if close_early:
                return
            release.set()
            wait_for(lambda: ui._models_ready and device.start.called)
            self.assertTrue(ui.speak_button.isEnabled())
            self.assertTrue(ui.summary_button.isEnabled())
            self.assertIn("마이크 연결", ui.connection_label.text())
        modules = {"stt.transcriber": SimpleNamespace(Transcriber=load_stt),
                   "tts.speaker": SimpleNamespace(Speaker=speaker)}
        try:
            with patch.dict(sys.modules, modules), patch("main.load_config", return_value=cfg), \
                 patch("ui.app.SoribomUI", return_value=ui), \
                 patch("audio.vad.VoiceActivityDetector", return_value=vad), \
                 patch("audio.recovery.DeviceController", return_value=device), \
                 patch.object(ui, "run", side_effect=run_screen):
                main.main()
                release.set()
                for worker in workers:
                    worker.join(2)
                    self.assertFalse(worker.is_alive())
            device.stop.assert_called_once()
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


if __name__ == "__main__":
    unittest.main()
