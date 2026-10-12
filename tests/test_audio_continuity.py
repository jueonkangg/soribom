"""콜백 지연/실제 유실을 구분하고 유실 앞 발화와 유한 전사 큐를 검증한다."""
from pathlib import Path
import queue
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audio.capture import BLOCK_HEADER, CaptureSink
from audio.recovery import AudioBuffer, DeviceController
from audio.vad import VoiceActivityDetector
from stt.pipeline import UtteranceBuffer, error_category


class ContinuityTests(unittest.TestCase):
    def controller(self):
        cfg = {"audio": {"block_ms": 30, "sample_rate": 16000}, "doa": {"enabled": False}}
        c = DeviceController(cfg, AudioBuffer(100), lambda *_: None)
        c.on_event = Mock()
        return c

    def payload(self, seq, callback, adc, overflows=0, dropped=0):
        return BLOCK_HEADER.pack(seq, callback, adc, adc + .02, overflows, dropped) + np.ones(480, dtype=np.float32).tobytes()

    def test_callback_jitter_keeps_queue_and_generation(self):
        c = self.controller()
        c._accept_block(self.payload(1, 100, 200), 100)
        c._accept_block(self.payload(2, 100.119, 200.03), 100.119)
        self.assertEqual(c.callback_jitters, 1)
        self.assertEqual(c.audio_gaps, 0)
        self.assertEqual(c.audio.generation, 0)
        self.assertEqual(c.audio.queue.qsize(), 2)
        self.assertEqual(c.audio.dropped_blocks, 0)

    def test_sequence_gap_marks_boundary_without_invalidating_prior_result(self):
        c = self.controller()
        c._accept_block(self.payload(1, 100, 200), 100)
        c._accept_block(self.payload(4, 100.09, 200.09, dropped=2), 100.09)
        self.assertEqual(c.audio_gaps, 1)
        self.assertEqual(c.pipe_dropped_blocks, 2)
        self.assertEqual(c.audio.generation, 0)
        self.assertEqual(len(c.audio.get()[1]), 480)
        self.assertEqual(len(c.audio.get()[1]), 0)
        self.assertEqual(len(c.audio.get()[1]), 480)
        self.assertTrue(c.audio.publish(0, lambda: None))

    def test_adc_gap_and_input_overflow_are_detected_without_sequence_gap(self):
        for overflow, adc in [(0, 200.12), (1, 200.03)]:
            with self.subTest(overflow=overflow):
                c = self.controller()
                c._accept_block(self.payload(1, 100, 200), 100)
                c._accept_block(self.payload(2, 100.12, adc, overflow), 100.12)
                self.assertEqual(c.audio_gaps, 1)
                self.assertEqual(c.capture_overflows, overflow)

    def test_failed_pipe_write_is_in_next_packet_metadata(self):
        sink = CaptureSink(Mock())
        info = SimpleNamespace(inputBufferAdcTime=1.0, currentTime=1.02)
        status = SimpleNamespace(input_overflow=False)
        with patch("audio.capture.send_audio_block", side_effect=[False, True]) as send:
            sink.put_capture(np.ones(480), info, status)
            sink.put_capture(np.ones(480), info, status)
        metadata = send.call_args.args[2]
        self.assertEqual(metadata[0], 2)
        self.assertEqual(metadata[-1], 1)

    def test_boundary_flushes_partial_speech_but_reconnect_discards_it(self):
        vad = VoiceActivityDetector.__new__(VoiceActivityDetector)
        vad.cfg = {"threshold": .5, "min_speech_ms": 32, "min_silence_ms": 32, "speech_pad_ms": 0}
        vad.model = SimpleNamespace(speech_prob=lambda w: float(w[0] > 0))
        q = queue.Queue()
        q.put((0, np.ones(512, dtype=np.float32)))
        q.put((0, np.zeros(0, dtype=np.float32)))
        q.put((0, np.full(512, 2, dtype=np.float32)))
        q.put((1, np.zeros(0, dtype=np.float32)))
        q.put(None)
        chunks = list(vad.stream(q, with_generation=True))
        self.assertEqual(len(chunks), 1)
        self.assertTrue(np.all(chunks[0][1] == 1))

    def test_pending_queue_is_bounded_and_preserves_latest_order(self):
        q = UtteranceBuffer(2)
        for i in range(100):
            q.put(0, i, [], "science")
        self.assertEqual(q.stats(), {"utterance_queue_depth": 2, "utterance_dropped": 98})
        self.assertEqual(q.get()[1], 98)
        self.assertEqual(q.get()[1], 99)
        q.close()
        self.assertIsNone(q.get())

    def test_expired_utterance_is_dropped_and_shutdown_wakes_waiter(self):
        q = UtteranceBuffer(4, 1)
        q.put(0, "expired", [(1, time.monotonic()-3)], "science")
        q.put(0, "fresh", [], "science")
        self.assertEqual(q.get()[1], "fresh")
        self.assertEqual(q.dropped, 1)
        finished = threading.Event()
        def wait():
            self.assertIsNone(q.get())
            finished.set()
        worker = threading.Thread(target=wait)
        worker.start()
        q.close()
        self.assertTrue(finished.wait(1))
        worker.join()

    def test_error_categories_do_not_return_exception_messages(self):
        self.assertEqual(error_category(RuntimeError("CUDA out of memory private")), "memory")
        self.assertEqual(error_category(RuntimeError("cuBLAS failure private")), "cuda")
        self.assertEqual(error_category(ValueError("private audio")), "input")
        self.assertEqual(error_category(RuntimeError("private")), "unknown")
