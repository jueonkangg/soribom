"""모델 없이 스피커 분리·재연결·출력 시간 제한·종료를 검증한다."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tts.pulse_output import PulseOutput


class PulseOutputTests(unittest.TestCase):
    def setUp(self):
        self.output = PulseOutput({"output_sink": "bluez_output.test.a2dp-sink",
                                   "bluetooth_address": "AA:BB:CC:DD:EE:FF"})
        self.process = Mock(returncode=0)
        self.process.poll.return_value = 0
        self.process.communicate.return_value = (None, b"")
        self.addCleanup(self.output.close)

    def test_each_playback_opens_current_sink_without_temp_files(self):
        with patch.object(self.output, "prepare"), \
             patch("tts.pulse_output.subprocess.Popen", return_value=self.process) as spawn:
            for _ in range(2):
                self.output.play(np.zeros(16000, dtype=np.float32), 16000, Mock())
        self.assertEqual(spawn.call_count, 2)
        command = spawn.call_args.args[0]
        self.assertIn("--device=bluez_output.test.a2dp-sink", command)
        self.assertIn("--format=float32le", command)
        self.assertEqual(self.process.communicate.call_args_list[0].kwargs["timeout"], 4)
        self.assertIsNone(self.output.process)

    def test_timeout_kills_and_reaps_player_and_allows_next_request(self):
        self.process.poll.return_value = None
        self.process.communicate.side_effect = [subprocess.TimeoutExpired("paplay", 4), (None, b"")]
        with patch.object(self.output, "prepare"), \
             patch("tts.pulse_output.subprocess.Popen", return_value=self.process):
            with self.assertRaises(TimeoutError):
                self.output.play(np.zeros(16000), 16000, Mock())
            self.process.kill.assert_called_once()
            self.assertIsNone(self.output.process)
            self.process.poll.return_value = 0
            self.process.communicate.side_effect = None
            self.output.play(np.zeros(16000), 16000, Mock())

    def test_missing_bose_never_plays_through_another_sink(self):
        result = Mock(returncode=0, stdout="2 alsa_output.respeaker PipeWire\n")
        with patch("tts.pulse_output.shutil.which", return_value="/usr/bin/paplay"), \
             patch("tts.pulse_output.subprocess.run", return_value=result), \
             patch("tts.pulse_output.subprocess.Popen") as spawn:
            with self.assertRaisesRegex(RuntimeError, "스피커"):
                self.output.play(np.zeros(16000), 16000, Mock())
        spawn.assert_not_called()

    def test_reconnect_checks_new_sink_before_use(self):
        absent = Mock(returncode=0, stdout="")
        present = Mock(returncode=0, stdout="7 bluez_output.test.a2dp-sink PipeWire\n")
        with patch("tts.pulse_output.shutil.which", return_value="/usr/bin/paplay"), \
             patch("tts.pulse_output.subprocess.run", side_effect=[absent, Mock(), present]) as run:
            self.output.prepare(reconnect=True)
        self.assertEqual(run.call_args_list[1].args[0],
                         ["bluetoothctl", "--timeout", "5", "connect", "AA:BB:CC:DD:EE:FF"])
        self.assertEqual(run.call_args_list[1].kwargs["timeout"], 6)

    def test_nonzero_exit_is_output_failure(self):
        self.process.returncode = 1
        with patch.object(self.output, "prepare"), \
             patch("tts.pulse_output.subprocess.Popen", return_value=self.process):
            with self.assertRaisesRegex(RuntimeError, "출력"):
                self.output.play(np.zeros(16000), 16000, Mock())

    def test_close_cancels_active_player_and_rejects_new_playback(self):
        self.output.process = self.process
        self.process.poll.return_value = None
        self.output.close()
        self.process.kill.assert_called_once()
        with self.assertRaisesRegex(RuntimeError, "종료"):
            self.output.prepare()
