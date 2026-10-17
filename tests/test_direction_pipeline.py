"""VAD→STT→화면·노트 통합 경로에서 다음 화자의 각도를 잘못 쓰지 않는지 확인한다."""
import os
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audio.recovery import DeviceController
from summary.notes import NoteBuilder
from ui.app import SoribomUI
import main


class DirectionPipelineTests(unittest.TestCase):
    def test_delayed_transcription_publishes_matching_direction_to_ui_and_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = {"audio": {}, "doa": {"enabled": True}, "vad": {}, "stt": {},
                   "tts": {}, "summary": {"enabled": False, "output_dir": directory},
                   "events": {"enabled": False},
                   "diagnostics": {"enabled": True, "output_dir": str(Path(directory) / "diagnostics")}}
            ui = SoribomUI(cfg)
            notes = NoteBuilder(cfg["summary"])
            ready = threading.Event()
            stt_entered = threading.Event()
            vad_advanced = threading.Event()
            holder = {}
            now = time.monotonic()
            ranges = [(now - 3, now - 2)]

            def make_devices(config, audio, on_status):
                controller = DeviceController(config, audio, on_status)
                holder["devices"] = controller
                def start():
                    controller.mic_state = controller.doa_state = "ready"
                    controller._record_direction(0, now - 2.9, now - 2.89, 90)
                    controller._record_direction(0, now - 2.7, now - 2.69, 90)
                    on_status("ready", "ready", "")
                    ready.set()
                controller.start = start
                return controller

            def stream(audio, with_timing=False):
                if not ready.wait(2):
                    return
                if not with_timing:
                    raise AssertionError("main이 발화 시각을 요청하지 않았습니다")
                yield audio.generation, np.zeros(512, dtype=np.float32), ranges
                if stt_entered.wait(2):
                    vad_advanced.set()

            def transcribe(chunk):
                stt_entered.set()
                self.assertTrue(vad_advanced.wait(2), "전사 중에도 VAD가 계속 실행되어야 합니다")
                # STT가 실행되는 동안 실제로 다음 화자 방향 표본이 들어온 상황.
                holder["devices"]._record_direction(0, now - 1, now - 0.99, 270)
                return "첫 화자의 문장"

            vad = SimpleNamespace(stream=stream)
            stt = Mock()
            stt.transcribe.side_effect = transcribe
            modules = {"stt.transcriber": SimpleNamespace(Transcriber=lambda *_: stt),
                       "tts.speaker": SimpleNamespace(Speaker=lambda *_: Mock())}

            def run_screen():
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    ui.app.processEvents()
                    if "첫 화자의 문장" in ui.caption_label.text() and notes.lines:
                        break
                    time.sleep(0.01)
                self.assertIn("첫 화자의 문장", ui.caption_label.text())
                self.assertAlmostEqual(ui.dial._angle, 90)
                self.assertAlmostEqual(ui._last_speech_timing[0], ranges[-1][1])
                self.assertAlmostEqual(notes.lines[0]["angle"], 90)
                self.assertEqual(holder["devices"].current_angle(), 270)

            try:
                with patch.dict(sys.modules, modules), patch("main.load_config", return_value=cfg), \
                     patch("ui.app.SoribomUI", return_value=ui), \
                     patch("audio.vad.VoiceActivityDetector", return_value=vad), \
                     patch("audio.recovery.DeviceController", side_effect=make_devices), \
                     patch("summary.notes.NoteBuilder", return_value=notes), \
                     patch.object(ui, "run", side_effect=run_screen):
                    main.main()
                self.assertTrue(holder["devices"].audio.closed)
                log = Path(directory) / "diagnostics/runtime.jsonl"
                rows = [json.loads(line) for line in log.read_text().splitlines()]
                caption = next(row for row in rows if row["event"] == "caption")
                self.assertTrue(caption["has_text"])
                self.assertTrue(caption["direction_known"])
                self.assertGreater(caption["dispatch_delay_s"], 2)
                self.assertEqual(rows[-1]["event"], "session_end")
                self.assertNotIn("첫 화자의 문장", log.read_text())
            finally:
                ui.window.close()
