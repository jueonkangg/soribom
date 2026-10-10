"""실제 USB/GPU 없이 재연결, 메모리 제한, 오디오 세대 분리를 검증한다."""
import os
from pathlib import Path
import queue
import sys
import time
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audio.capture import MicArray, send_audio_block
from audio.recovery import AudioBuffer, DeviceController
from audio.vad import VoiceActivityDetector


def fake_capture(cfg, blocks, control, stop):
    """새 프로세스에서 모델 없이 무음 블록을 보내고, 요청 시 실제로 종료한다."""
    os.set_blocking(blocks.fileno(), False)
    control.send(("opened", ""))
    while not stop.poll(0.03):
        send_audio_block(blocks, np.zeros(480, dtype=np.float32))
    control.close()
    blocks.close()
    stop.close()


class AudioRecoveryTests(unittest.TestCase):
    def config(self):
        return {
            "audio": {"device": "ReSpeaker", "channels": 6, "block_ms": 30,
                      "sample_rate": 16000, "queue_max_blocks": 8,
                      "health_timeout_seconds": 2, "open_timeout_seconds": 5,
                      "retry_seconds": 5},
            "doa": {"enabled": False},
        }

    def wait_for(self, predicate):
        deadline = time.monotonic() + 8
        while not predicate() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(predicate())

    def test_missing_respeaker_never_uses_default_microphone(self):
        mic = MicArray(self.config()["audio"], queue.Queue())
        with patch("audio.capture.sd.query_devices", return_value=[
            {"name": "Other microphone", "max_input_channels": 2}
        ]), patch("audio.capture.sd.InputStream") as stream:
            with self.assertRaisesRegex(RuntimeError, "ReSpeaker"):
                mic.start()
            stream.assert_not_called()

    def test_queue_limit_discards_old_generation_and_late_results(self):
        buffer = AudioBuffer(2)
        old = buffer.generation
        for _ in range(1000):
            buffer.put(np.zeros(480, dtype=np.float32))
        self.assertLessEqual(buffer.queue.qsize(), 2)
        calls = []
        self.assertFalse(buffer.publish(old, lambda: calls.append("old")))
        self.assertTrue(buffer.publish(buffer.generation, lambda: calls.append("new")))
        self.assertEqual(calls, ["new"])
        buffer.close()
        buffer.put(np.zeros(480))
        self.assertIsNone(buffer.get())
        self.assertFalse(buffer.publish(buffer.generation, lambda: calls.append("closed")))

    def test_vad_drops_partial_speech_at_reconnect_and_bounds_long_speech(self):
        # 우선 1창짜리 미완성 발화, 재연결, 새 발화 2창을 넣는다.
        vad = VoiceActivityDetector.__new__(VoiceActivityDetector)
        vad.cfg = {"threshold": 0.5, "min_speech_ms": 32, "min_silence_ms": 32,
                   "speech_pad_ms": 0, "max_utterance_seconds": 0.064}
        class Model:
            def speech_prob(self, window):
                return float(window[0] > 0)
        vad.model = Model()
        q = queue.Queue()
        q.put((0, np.ones(512, dtype=np.float32)))
        q.put((1, np.full(1024, 2, dtype=np.float32)))
        q.put(None)
        chunks = list(vad.stream(q, with_generation=True))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0][0], 1)
        self.assertEqual(len(chunks[0][1]), 1024)
        self.assertTrue(np.all(chunks[0][1] == 2))

    def test_doa_failure_does_not_stop_audio_and_disabled_doa_is_not_opened(self):
        cfg = self.config()
        audio = AudioBuffer(8)
        controller = DeviceController(cfg, audio, lambda *_: None)
        controller.mic_state = "ready"
        with patch("audio.recovery.DoaTracker") as doa:
            controller._poll_doa(time.monotonic())
            doa.assert_not_called()
        controller.doa_state = "waiting"
        with patch("audio.recovery.DoaTracker", side_effect=RuntimeError("USB missing")):
            controller._poll_doa(time.monotonic())
        self.assertEqual(controller.mic_state, "ready")
        self.assertEqual(controller.doa_state, "waiting")
        self.assertIsNone(controller.current_angle())
        audio.put(np.ones(480))
        self.assertEqual(len(audio.get()[1]), 480)

    def test_read_failure_closes_doa_and_clears_angle(self):
        from unittest.mock import Mock
        controller = DeviceController(self.config(), AudioBuffer(8), lambda *_: None)
        controller.doa_state = controller.mic_state = "ready"
        device = Mock()
        device.current.side_effect = RuntimeError("USB disconnected")
        controller.doa = device
        controller.angle = 90
        controller.request_direction(controller.audio.generation)
        controller._poll_doa(time.monotonic())
        device.close.assert_called_once()
        self.assertEqual(controller.mic_state, "ready")
        self.assertEqual(controller.doa_state, "waiting")
        self.assertIsNone(controller.current_angle())

    def test_callback_stall_resets_audio_and_schedules_retry(self):
        from unittest.mock import Mock
        audio = AudioBuffer(8)
        controller = DeviceController(self.config(), audio, lambda *_: None)
        controller.control = Mock()
        controller.control.poll.return_value = False
        controller.process = Mock()
        controller.process.is_alive.return_value = True
        controller.blocks = Mock()
        controller.blocks.poll.return_value = False
        controller.last_block = time.monotonic() - 3
        controller.mic_state = "ready"
        generation = audio.generation
        with patch.object(controller, "_close_mic") as close:
            controller._poll_mic(time.monotonic())
        close.assert_called_once()
        self.assertEqual(controller.mic_state, "waiting")
        self.assertGreater(audio.generation, generation)
        self.assertGreater(controller.next_mic, time.monotonic())

    def test_slow_doa_never_blocks_microphone_delivery(self):
        from unittest.mock import Mock
        cfg = self.config()
        cfg["audio"]["queue_max_blocks"] = 100
        cfg["doa"]["enabled"] = True
        audio = AudioBuffer(100)
        controller = DeviceController(cfg, audio, lambda *_: None)
        device = Mock()
        def slow_angle():
            time.sleep(0.3)
            return 90
        device.current.side_effect = slow_angle
        with patch("audio.recovery.capture_process", fake_capture), patch("audio.recovery.DoaTracker", return_value=device):
            controller.start()
            try:
                self.wait_for(lambda: controller.mic_state == controller.doa_state == "ready")
                generation = audio.generation
                controller.request_direction(generation)
                time.sleep(0.4)
                self.assertLess(time.monotonic() - controller.last_block, 0.15)
                self.assertEqual(audio.generation, generation)
                self.assertEqual(controller.current_angle(), 90)
            finally:
                controller.stop()
        self.assertFalse(controller.direction_thread.is_alive())
        device.close.assert_called_once()

    def test_real_process_restarts_without_accumulating_workers_or_memory(self):
        states = []
        audio = AudioBuffer(8)
        controller = DeviceController(self.config(), audio, lambda *args: states.append(args))
        parent_rss = []
        child_rss = []
        with patch("audio.recovery.capture_process", fake_capture):
            controller.start()
            try:
                self.wait_for(lambda: controller.mic_state == "ready")
                worker = controller.thread
                for _ in range(4):
                    process = controller.process
                    pid = process.pid
                    for target_pid, measurements in [(os.getpid(), parent_rss), (pid, child_rss)]:
                        status = Path(f"/proc/{target_pid}/status").read_text()
                        line = next(line for line in status.splitlines() if line.startswith("VmRSS:"))
                        measurements.append(int(line.split()[1]))
                    self.assertLessEqual(audio.queue.qsize(), 8)
                    process.terminate()  # 케이블 분리를 재현: 오디오 콜백도 중단된다
                    self.wait_for(lambda: controller.process is None)
                    self.assertEqual(controller.mic_state, "waiting")
                    for _ in range(20):
                        controller.retry()
                    self.wait_for(lambda: controller.mic_state == "ready")
                    self.assertIs(controller.thread, worker)
                    self.assertNotEqual(controller.process.pid, pid)
                    self.assertFalse(Path(f"/proc/{pid}").exists())
                # 모델 없는 녹음 프로세스의 재연결 전후 메모리도 비교한다.
                self.assertLess(max(parent_rss) - min(parent_rss), 16 * 1024)
                self.assertLess(max(child_rss) - min(child_rss), 16 * 1024)
                self.assertTrue(any(state[0] == "waiting" for state in states))
            finally:
                last_pid = controller.process.pid if controller.process is not None else None
                controller.stop()
            self.assertFalse(controller.thread.is_alive())
            self.assertIsNone(controller.process)
            if last_pid:
                self.assertFalse(Path(f"/proc/{last_pid}").exists())
        controller.start()  # 앱 종료 뒤 모델 준비가 끝나도 장치를 다시 열지 않는다
        self.assertFalse(controller.thread.is_alive())
        print(f"[재연결 테스트] parent RSS KiB={parent_rss}; child RSS KiB={child_rss}")


if __name__ == "__main__":
    unittest.main()
