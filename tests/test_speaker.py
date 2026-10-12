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
        self.stream = Mock()
        self.stream.write.return_value = False
        self.output = SimpleNamespace(OutputStream=Mock(return_value=self.stream))
        with patch.dict("sys.modules", {"sherpa_onnx": SimpleNamespace(), "sounddevice": self.output}):
            spec.loader.exec_module(module)
        self.module = module
        self.speaker = module.Speaker.__new__(module.Speaker)
        self.speaker.cfg = {"max_chars": 200}
        self.speaker._speech_lock = threading.RLock()
        self.speaker._output_lock = threading.Lock()
        self.speaker._output_stream = None
        self.speaker._closed = False
        self.speaker.output_device = None
        self.speaker.on_event = Mock()
        self.speaker.synthesize = Mock(return_value=(np.ones(10, dtype=np.float32), 16000))

    def test_output_error_closes_stream_and_next_request_succeeds(self):
        self.stream.write.side_effect = RuntimeError("disconnected")
        with self.assertRaises(RuntimeError):
            self.speaker.say("실패한 문장")
        self.stream.abort.assert_called_once()
        self.stream.close.assert_called_once()
        self.stream.write.side_effect = None
        self.speaker.say("다시 말하기")
        self.assertEqual(self.output.OutputStream.call_count, 2)
        ends = [call for call in self.speaker.on_event.call_args_list if call.args[0] == "tts_end"]
        self.assertFalse(ends[0].kwargs["success"])
        self.assertEqual(ends[0].kwargs["error_type"], "SpeechOutputError")
        self.assertTrue(ends[1].kwargs["success"])
        for call in self.speaker.on_event.call_args_list:
            self.assertNotIn("text", call.kwargs)

    def test_concurrent_call_is_rejected_without_more_synthesis(self):
        started = threading.Event()
        release = threading.Event()
        self.stream.write.side_effect = lambda *_: (started.set(), release.wait(3), False)[-1]
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
        self.output.OutputStream.assert_not_called()

    def test_output_underflow_is_reported_instead_of_success(self):
        self.stream.write.return_value = True
        with self.assertRaisesRegex(RuntimeError, "출력"):
            self.speaker.say("문장")
        self.stream.abort.assert_called_once()

    def test_stream_is_reused_and_shutdown_closes_it(self):
        self.speaker.say("첫 문장")
        self.speaker.say("두 번째 문장")
        self.output.OutputStream.assert_called_once()
        self.assertEqual(self.stream.start.call_count, 2)
        self.speaker.close()
        self.stream.close.assert_called_once()
        with self.assertRaisesRegex(RuntimeError, "종료"):
            self.speaker.say("종료 후 문장")

    def test_warmup_synthesizes_without_playback(self):
        self.speaker.warmup()
        self.speaker.synthesize.assert_called_once_with("안녕하세요.")
        self.output.OutputStream.assert_not_called()

    def test_synthesis_error_preserves_cause_without_opening_output(self):
        cause = RuntimeError("GPU failure")
        self.speaker.synthesize.side_effect = cause
        with self.assertRaises(self.module.SpeechSynthesisError) as caught:
            self.speaker.say("문장")
        self.assertIs(caught.exception.__cause__, cause)
        self.output.OutputStream.assert_not_called()

    def test_disconnected_stream_cleanup_still_closes_and_allows_retry(self):
        self.stream.write.side_effect = RuntimeError("disconnected")
        self.stream.abort.side_effect = RuntimeError("already disconnected")
        with self.assertRaises(self.module.SpeechOutputError):
            self.speaker.say("문장")
        self.stream.close.assert_called_once()
        self.stream.write.side_effect = None
        self.stream.abort.side_effect = None
        self.speaker.say("다시 말하기")
        self.assertEqual(self.output.OutputStream.call_count, 2)
