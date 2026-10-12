"""GPU 모델을 읽지 않고 출력 실패와 동시 합성 방지를 검증한다."""
import importlib.util
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np


class SpeakerTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "src/tts/speaker.py"
        spec = importlib.util.spec_from_file_location("speaker_under_test", path)
        module = importlib.util.module_from_spec(spec)
        self.output = SimpleNamespace(play=Mock(), wait=Mock(return_value=None), stop=Mock())
        with patch.dict("sys.modules", {"sherpa_onnx": SimpleNamespace(), "sounddevice": self.output}):
            spec.loader.exec_module(module)
        self.speaker = module.Speaker.__new__(module.Speaker)
        self.speaker.cfg = {"max_chars": 200}
        self.speaker._speech_lock = threading.RLock()
        self.speaker.output_device = None
        self.speaker.on_event = Mock()
        self.speaker.synthesize = Mock(return_value=(np.ones(10, dtype=np.float32), 16000))

    def test_output_error_closes_stream_and_next_request_succeeds(self):
        self.output.wait.side_effect = RuntimeError("disconnected")
        with self.assertRaises(RuntimeError):
            self.speaker.say("실패한 문장")
        self.output.stop.assert_called_once()
        self.output.wait.side_effect = None
        self.speaker.say("다시 말하기")
        self.assertEqual(self.output.play.call_count, 2)
        ends = [call for call in self.speaker.on_event.call_args_list if call.args[0] == "tts_end"]
        self.assertFalse(ends[0].kwargs["success"])
        self.assertEqual(ends[0].kwargs["error_type"], "RuntimeError")
        self.assertTrue(ends[1].kwargs["success"])
        for call in self.speaker.on_event.call_args_list:
            self.assertNotIn("text", call.kwargs)

    def test_concurrent_call_is_rejected_without_more_synthesis(self):
        started = threading.Event()
        release = threading.Event()
        self.output.wait.side_effect = lambda: (started.set(), release.wait(3), None)[-1]
        worker = threading.Thread(target=self.speaker.say, args=("첫 문장",))
        worker.start()
        try:
            self.assertTrue(started.wait(1))
            with self.assertRaisesRegex(RuntimeError, "이미 말하는 중"):
                self.speaker.say("두 번째 문장")
            self.speaker.synthesize.assert_called_once_with("첫 문장")
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())

    def test_empty_audio_and_long_text_never_start_playback(self):
        self.speaker.synthesize.return_value = (np.zeros(0), 16000)
        with self.assertRaisesRegex(RuntimeError, "음성이 없습니다"):
            self.speaker.say("문장")
        with self.assertRaises(ValueError):
            self.speaker.say("가" * 201)
        self.output.play.assert_not_called()

    def test_output_underflow_is_reported_instead_of_success(self):
        self.output.wait.return_value = SimpleNamespace(output_underflow=True)
        with self.assertRaisesRegex(RuntimeError, "출력"):
            self.speaker.say("문장")
        self.output.stop.assert_called_once()
