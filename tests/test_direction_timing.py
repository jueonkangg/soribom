"""다음 화자의 방향이 이전 자막으로 연결되지 않는지 검증한다."""
from pathlib import Path
import queue
import sys
import time
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audio.recovery import AudioBuffer, DeviceController
from audio.vad import VoiceActivityDetector


class DirectionTimingTests(unittest.TestCase):
    def setUp(self):
        self.audio = AudioBuffer(100)
        self.controller = DeviceController({"audio": {}, "doa": {"enabled": True}}, self.audio, lambda *_: None)
        self.controller.mic_state = self.controller.doa_state = "ready"
        self.now = time.monotonic()

    def record(self, start, end, angle, generation=None):
        if generation is None:
            generation = self.audio.generation
        self.controller._record_direction(generation, start, end, angle)

    def test_next_speaker_during_transcription_cannot_replace_utterance_direction(self):
        self.record(self.now - 2.9, self.now - 2.89, 88)
        self.record(self.now - 2.7, self.now - 2.69, 92)
        # 전사 동안 다음 화자가 말했어도 현재 각도로 앞 자막을 덮지 않는다.
        self.record(self.now - 1, self.now - 0.99, 270)
        result = self.controller.direction_for(0, [(self.now - 3, self.now - 2)])
        self.assertAlmostEqual(result, 90)
        self.assertEqual(self.controller.current_angle(), 270)

    def test_silence_padding_and_slow_read_crossing_speaker_boundary_are_excluded(self):
        self.record(self.now - 2.9, self.now - 2.89, 90)
        self.record(self.now - 2.7, self.now - 2.69, 90)
        for _ in range(6):
            self.record(self.now - 2.3, self.now - 2.29, 270)  # 발화 사이 침묵
            self.record(self.now - 1.1, self.now - 0.8, 270)  # 읽기 완료가 발화 밖
        ranges = [(self.now - 3, self.now - 2.5), (self.now - 2, self.now - 1)]
        self.assertAlmostEqual(self.controller.direction_for(0, ranges), 90)

    def test_opposing_directions_and_insufficient_samples_are_unknown(self):
        self.record(self.now - 0.9, self.now - 0.89, 90)
        ranges = [(self.now - 1, self.now)]
        self.assertIsNone(self.controller.direction_for(0, ranges))
        self.record(self.now - 0.7, self.now - 0.69, 270)
        self.assertIsNone(self.controller.direction_for(0, ranges))
        self.assertIsNone(self.controller.direction_for(0, []))

    def test_round_boundary_and_small_outlier_use_dominant_circular_direction(self):
        for i, angle in enumerate([359, 1, 0, 180]):
            self.record(self.now - 0.9 + i * 0.1, self.now - 0.89 + i * 0.1, angle)
        angle = self.controller.direction_for(0, [(self.now - 1, self.now)])
        self.assertIsNotNone(angle)
        self.assertLess(abs(((angle + 180) % 360) - 180), 0.01)

    def test_reconnect_and_late_usb_reply_never_use_old_generation(self):
        old = self.audio.generation
        self.record(self.now - 0.9, self.now - 0.89, 90)
        self.record(self.now - 0.8, self.now - 0.79, 90)
        self.audio.reset()
        self.record(self.now - 0.7, self.now - 0.69, 270, generation=old)
        ranges = [(self.now - 1, self.now)]
        self.assertIsNone(self.controller.direction_for(old, ranges))
        self.assertIsNone(self.controller.direction_for(self.audio.generation, ranges))

    def test_history_is_bounded_and_expired_samples_are_unknown(self):
        for i in range(3000):
            self.record(self.now - 0.9, self.now - 0.89, 90)
        self.assertLessEqual(len(self.controller.direction_samples), 602)
        with patch("audio.recovery.time.monotonic", return_value=self.now + 61):
            self.assertIsNone(self.controller.direction_for(0, [(self.now - 1, self.now)]))
        self.record(self.now + 61, self.now + 61.01, 0)
        self.assertEqual(len(self.controller.direction_samples), 1)

    def test_periodic_sampling_uses_raw_angles_and_limits_usb_calls(self):
        device = Mock()
        device.raw_angle.return_value = 270
        self.controller.doa = device
        self.controller._poll_doa(self.now)
        first_next = self.controller.next_direction_sample
        self.controller._poll_doa(first_next - 0.001)
        device.raw_angle.assert_called_once()
        device.current.assert_not_called()
        self.assertEqual(self.controller.current_angle(), 90)
        self.controller._poll_doa(first_next + 0.001)
        self.assertEqual(device.raw_angle.call_count, 2)

    def make_vad(self, max_seconds=30):
        vad = VoiceActivityDetector.__new__(VoiceActivityDetector)
        vad.cfg = {"threshold": 0.5, "min_speech_ms": 32, "min_silence_ms": 32,
                   "speech_pad_ms": 32, "max_utterance_seconds": max_seconds}
        class Model:
            def speech_prob(self, window):
                return float(window[0] > 0)
        vad.model = Model()
        return vad

    def test_vad_uses_capture_clock_despite_delayed_processing_and_excludes_padding(self):
        q = queue.Queue()
        q.put((0, np.zeros(512, dtype=np.float32), 10.032))
        q.put((0, np.ones(1024, dtype=np.float32), 10.096))
        q.put((0, np.zeros(512, dtype=np.float32), 10.128))
        q.put(None)
        result = list(self.make_vad().stream(q, with_timing=True))
        self.assertEqual(len(result), 1)
        generation, audio, ranges = result[0]
        self.assertEqual(generation, 0)
        self.assertEqual(len(audio), 2048)  # 앞 패딩·끝 침묵은 오디오에는 유지
        self.assertEqual(len(ranges), 1)
        self.assertAlmostEqual(ranges[0][0], 10.032)
        self.assertAlmostEqual(ranges[0][1], 10.096)

    def test_vad_keeps_512_window_times_across_480_sample_callbacks(self):
        q = queue.Queue()
        values = np.concatenate([np.ones(1024), np.zeros(896)]).astype(np.float32)
        for i in range(4):
            q.put((0, values[i * 480:(i + 1) * 480], 10 + (i + 1) * 0.03))
        q.put(None)
        result = list(self.make_vad().stream(q, with_timing=True))
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0][2][0][0], 10)
        self.assertAlmostEqual(result[0][2][0][1], 10.064)

    def test_vad_reconnect_clears_old_times_and_long_chunks_have_separate_ranges(self):
        q = queue.Queue()
        q.put((0, np.ones(512, dtype=np.float32), 10.032))
        q.put((1, np.ones(2048, dtype=np.float32), 20.128))
        q.put(None)
        result = list(self.make_vad(max_seconds=0.064).stream(q, with_timing=True))
        self.assertEqual(len(result), 2)
        self.assertEqual([chunk[0] for chunk in result], [1, 1])
        self.assertAlmostEqual(result[0][2][0][0], 20)
        self.assertAlmostEqual(result[0][2][0][1], 20.064)
        self.assertAlmostEqual(result[1][2][0][0], 20.064)
        self.assertAlmostEqual(result[1][2][0][1], 20.128)
