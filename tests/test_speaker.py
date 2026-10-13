"""GPU 모델을 읽지 않고 출력 실패와 동시 합성 방지를 검증한다."""
import importlib.util
from pathlib import Path
import threading
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from inference import InferenceGate


class SpeakerTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "src/tts/speaker.py"
        spec = importlib.util.spec_from_file_location("speaker_under_test", path)
        module = importlib.util.module_from_spec(spec)
        self.stream = Mock()
        self.output = SimpleNamespace(OutputStream=Mock(return_value=self.stream),
                                      CallbackStop=type("CallbackStop", (Exception,), {}),
                                      CallbackAbort=type("CallbackAbort", (Exception,), {}))
        with patch.dict("sys.modules", {"sherpa_onnx": SimpleNamespace(), "sounddevice": self.output}):
            spec.loader.exec_module(module)
        self.module = module
        self.speaker = module.Speaker.__new__(module.Speaker)
        self.speaker.cfg = {"max_chars": 200}
        self.speaker._speech_lock = threading.RLock()
        self.speaker._output_lock = threading.Lock()
        self.speaker._output_stream = None
        self.speaker._closed = False
        self.speaker.inference_gate = None
        self.speaker.on_speech_pause = Mock()
        self.speaker._playback_done = threading.Event()
        self.speaker._playback_samples = None
        self.speaker._playback_offset = 0
        self.speaker._playback_error = False
        self.speaker.output_device = None
        self.speaker.on_event = Mock()
        self.speaker._synthesize = Mock(return_value=(np.ones(10, dtype=np.float32), 16000))
        self.stream.start.side_effect = self.play_to_completion

    def play_to_completion(self):
        output = np.empty((16, 1), dtype=np.float32)
        with self.assertRaises(self.output.CallbackStop):
            self.speaker._fill_output(output, 16, None, SimpleNamespace(output_underflow=False))
        np.testing.assert_array_equal(output[:10, 0], np.ones(10))
        np.testing.assert_array_equal(output[10:, 0], np.zeros(6))
        self.speaker._playback_done.set()

    def test_output_error_closes_stream_and_next_request_succeeds(self):
        self.stream.start.side_effect = RuntimeError("disconnected")
        with self.assertRaises(RuntimeError):
            self.speaker.say("실패한 문장")
        self.stream.abort.assert_called_once()
        self.stream.close.assert_called_once()
        self.stream.start.side_effect = self.play_to_completion
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
        def delayed_playback():
            started.set()
            release.wait(3)
            self.play_to_completion()
        self.stream.start.side_effect = delayed_playback
        worker = threading.Thread(target=self.speaker.say, args=("첫 문장",))
        worker.start()
        try:
            self.assertTrue(started.wait(1))
            with self.assertRaisesRegex(RuntimeError, "이미 말하는 중"):
                self.speaker.say("두 번째 문장")
            self.speaker._synthesize.assert_called_once_with("첫 문장")
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())

    def test_empty_audio_and_long_text_never_start_playback(self):
        self.speaker._synthesize.return_value = (np.zeros(0), 16000)
        with self.assertRaisesRegex(RuntimeError, "음성이 없습니다"):
            self.speaker.say("문장")
        with self.assertRaises(ValueError):
            self.speaker.say("가" * 201)
        self.output.OutputStream.assert_not_called()

    def test_output_underflow_is_reported_instead_of_success(self):
        def underflow():
            self.play_to_completion()
            self.speaker._playback_error = True
        self.stream.start.side_effect = underflow
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
        self.speaker._synthesize.assert_called_once_with("안녕하세요.")
        self.output.OutputStream.assert_not_called()

    def test_pulse_output_failure_releases_pause_and_next_request_succeeds(self):
        pulse = Mock()
        self.speaker.pulse_output = pulse
        pulse.play.side_effect = TimeoutError("disconnected")
        with self.assertRaises(self.module.SpeechOutputError):
            self.speaker.say("실패한 문장")
        self.assertFalse(self.speaker.on_speech_pause.call_args.args[0])
        pulse.play.side_effect = lambda samples, rate, on_start: on_start()
        self.speaker.say("다시 말하기")
        self.assertEqual(pulse.prepare.call_count, 2)
        self.output.OutputStream.assert_not_called()

    def test_missing_pulse_sink_does_not_synthesize_or_pause_recognition(self):
        self.speaker.pulse_output = Mock()
        self.speaker.pulse_output.prepare.side_effect = RuntimeError("missing Bose")
        with self.assertRaises(self.module.SpeechOutputError):
            self.speaker.say("문장")
        self.speaker._synthesize.assert_not_called()
        self.speaker.on_speech_pause.assert_not_called()

    def test_synthesis_error_preserves_cause_without_opening_output(self):
        cause = RuntimeError("GPU failure")
        self.speaker._synthesize.side_effect = cause
        with self.assertRaises(self.module.SpeechSynthesisError) as caught:
            self.speaker.say("문장")
        self.assertIs(caught.exception.__cause__, cause)
        self.output.OutputStream.assert_not_called()

    def test_disconnected_stream_cleanup_still_closes_and_allows_retry(self):
        self.stream.start.side_effect = RuntimeError("disconnected")
        self.stream.abort.side_effect = RuntimeError("already disconnected")
        with self.assertRaises(self.module.SpeechOutputError):
            self.speaker.say("문장")
        self.stream.close.assert_called_once()
        self.stream.start.side_effect = self.play_to_completion
        self.stream.abort.side_effect = None
        self.speaker.say("다시 말하기")
        self.assertEqual(self.output.OutputStream.call_count, 2)

    def test_missing_completion_times_out_closes_and_next_request_succeeds(self):
        self.speaker.cfg["playback_timeout_margin_seconds"] = 0.1
        self.stream.start.side_effect = None
        with self.assertRaises(self.module.SpeechOutputError) as caught:
            self.speaker.say("문장")
        self.assertIsInstance(caught.exception.__cause__, TimeoutError)
        self.stream.abort.assert_called_once()
        self.stream.close.assert_called_once()
        self.stream.start.side_effect = self.play_to_completion
        self.speaker.say("다시 말하기")
        self.assertEqual(self.output.OutputStream.call_count, 2)
        self.stream.write.assert_not_called()
        self.stream.stop.assert_not_called()
        self.speaker.on_speech_pause.assert_any_call(False)

    def test_transcription_resumes_only_after_playback_finishes(self):
        gate = InferenceGate()
        self.speaker.inference_gate = gate
        playing = threading.Event()
        transcribing = threading.Event()
        self.stream.start.side_effect = playing.set
        errors = []
        def say():
            try:
                self.speaker.say("문장")
            except Exception as exc:
                errors.append(exc)
        speech = threading.Thread(target=say)
        speech.start()
        self.assertTrue(playing.wait(1))
        caption = threading.Thread(target=lambda: gate.run(transcribing.set))
        caption.start()
        try:
            self.assertFalse(transcribing.wait(0.05))
            self.play_to_completion()
        finally:
            self.speaker._playback_done.set()
            speech.join(2)
            caption.join(2)
        self.assertTrue(transcribing.is_set())
        self.assertFalse(speech.is_alive())
        self.assertFalse(caption.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual([c.args[0] for c in self.speaker.on_speech_pause.call_args_list], [True, False])
