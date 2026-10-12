"""GPU 추론 직렬화·말하기 우선·예외 후 복구를 모델 없이 검증한다."""
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from inference import InferenceGate


class InferenceTests(unittest.TestCase):
    def test_speech_waits_for_active_transcription_then_precedes_queued_transcription(self):
        gate = InferenceGate()
        entered = threading.Event()
        release = threading.Event()
        order = []
        def first():
            entered.set()
            self.assertTrue(release.wait(2))
            order.append("active caption")
        a = threading.Thread(target=lambda: gate.run(first))
        a.start()
        self.assertTrue(entered.wait(1))
        b = threading.Thread(target=lambda: gate.run(lambda: order.append("speech"), speech=True))
        b.start()
        # 말하기가 실제로 대기열에 들어왔는지 잠금 안에서 확인한다.
        with gate.condition:
            while not gate.speech_waiters:
                gate.condition.wait(.01)
        c = threading.Thread(target=lambda: gate.run(lambda: order.append("queued caption")))
        c.start()
        release.set()
        for worker in [a, b, c]:
            worker.join(2)
            self.assertFalse(worker.is_alive())
        self.assertEqual(order, ["active caption", "speech", "queued caption"])

    def test_exception_releases_gate_and_wait_time_is_reported(self):
        gate = InferenceGate()
        def fail():
            raise RuntimeError("memory")
        with self.assertRaises(RuntimeError):
            gate.run(fail, speech=True)
        waits = []
        self.assertEqual(gate.run(lambda: "ok", on_wait=waits.append), "ok")
        self.assertEqual(gate.speech_waiters, 0)
        self.assertFalse(gate.active)
        self.assertEqual(len(waits), 1)
