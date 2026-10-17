"""로딩 중 스피커 복구가 다른 연결·재생을 손상하지 않는지 확인한다."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audio import output_recovery as recovery


class OutputRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"bluetooth_address": "AA:BB:CC:DD:EE:FF",
                    "output_sink": "bluez_output.AA_BB_CC_DD_EE_FF.a2dp-sink"}
        self.sinks = [{"index": 7, "name": self.cfg["output_sink"]}]
        self.cards = [{"name": "bluez_card.AA_BB_CC_DD_EE_FF", "active_profile": "a2dp-sink",
                       "profiles": {"off": {}, "a2dp-sink": {}}}]
        self.inputs = []

    def listing(self, kind):
        return {"sinks": self.sinks, "cards": self.cards, "sink-inputs": self.inputs}[kind]

    def run_recovery(self, run=None, cancelled=lambda: False):
        with patch.object(recovery, "_listing", side_effect=self.listing), \
             patch.object(recovery, "_wifi_check", return_value=(True, True)), \
             patch.object(recovery, "_run", run or Mock(return_value=Mock(returncode=0))):
            return recovery.prepare_system_output(self.cfg, cancelled)

    def test_ready_bose_resets_only_audio_profile_without_bluetooth_disconnect(self):
        run = Mock(return_value=Mock(returncode=0))
        result = self.run_recovery(run)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[:2], [
            ["pactl", "set-card-profile", self.cards[0]["name"], "off"],
            ["pactl", "set-card-profile", self.cards[0]["name"], "a2dp-sink"]])
        self.assertTrue(result["speaker_ready"])
        self.assertTrue(result["audio_profile_reset"])
        self.assertFalse(any("bluetoothctl" in command for command in commands))

    def test_active_playback_and_unknown_inputs_never_reset_profile(self):
        for inputs in ([{"sink": 7}], None):
            self.inputs = inputs
            run = Mock(return_value=Mock(returncode=0))
            result = self.run_recovery(run)
            self.assertTrue(result["audio_recovery_skipped"])
            self.assertFalse(any("set-card-profile" in call.args[0] for call in run.call_args_list))

    def test_profile_reset_preserves_volume_balance_and_mute(self):
        self.sinks[0].update(mute=True, volume={"left": {"value": 16384}, "right": {"value": 32768}})
        run = Mock(return_value=Mock(returncode=0))
        self.run_recovery(run)
        run.assert_any_call(["pactl", "set-sink-volume", self.cfg["output_sink"], "16384", "32768"])
        run.assert_any_call(["pactl", "set-sink-mute", self.cfg["output_sink"], "1"])

    def test_other_bose_profile_playback_is_preserved(self):
        self.sinks = [{"index": 8, "name": "bluez_output.AA_BB_CC_DD_EE_FF.headset-head-unit"}]
        self.inputs = [{"sink": 8}]
        run = Mock(return_value=Mock(returncode=0))
        with patch.object(recovery.time, "monotonic", side_effect=[0, 3]):
            result = self.run_recovery(run)
        self.assertTrue(result["audio_recovery_skipped"])
        self.assertFalse(any("set-card-profile" in call.args[0] for call in run.call_args_list))

    def test_cancel_after_profile_off_still_restores_a2dp(self):
        cancelled = Mock(return_value=False)
        def command(args, *unused):
            if args[-1] == "off":
                cancelled.return_value = True
            return Mock(returncode=0)
        run = Mock(side_effect=command)
        self.run_recovery(run, cancelled)
        self.assertEqual(run.call_args_list[-1].args[0][-1], "a2dp-sink")

    def test_failed_profile_restore_is_retried_without_false_success(self):
        run = Mock(side_effect=[Mock(returncode=0), None, Mock(returncode=0), Mock(returncode=0)])
        result = self.run_recovery(run)
        self.assertFalse(result["audio_profile_reset"])
        self.assertEqual(run.call_args_list[2].args[0][-1], "a2dp-sink")

    def test_unavailable_bose_gets_one_bounded_connect_attempt(self):
        self.sinks = [];self.cards = []
        run = Mock(return_value=None)
        with patch.object(recovery.time, "monotonic", side_effect=[0, 3]):
            result = self.run_recovery(run)
        run.assert_called_once_with(["bluetoothctl", "--timeout", "5", "connect", self.cfg["bluetooth_address"]], 6)
        self.assertFalse(result["speaker_ready"])

    def test_cancel_before_start_never_changes_system(self):
        with patch.object(recovery, "_run") as run:
            recovery.prepare_system_output(self.cfg, lambda: True)
        run.assert_not_called()

    def test_wifi_runtime_change_never_disconnects_or_reactivates_network(self):
        on = Mock(returncode=0, stdout="Power save: on")
        off = Mock(returncode=0, stdout="Power save: off")
        with patch.object(recovery, "_run", side_effect=[
                Mock(returncode=0, stdout="wifi0:wifi:connected\n"), on,
                Mock(returncode=0), off]) as run:
            self.assertEqual(recovery._wifi_check(lambda: False), (True, True))
        self.assertEqual(run.call_args_list[2].args[0],
                         ["nmcli", "device", "modify", "wifi0", "802-11-wireless.powersave", "2"])

    def test_wifi_off_is_only_checked_and_denied_change_is_not_success(self):
        for state,expected in (("off", True), ("on", False)):
            def command(args, *unused):
                if args[0] == "nmcli" and args[-1] == "device":
                    return Mock(returncode=0, stdout="wifi0:wifi:connected\n")
                return Mock(returncode=0, stdout="Power save: " + state)
            with patch.object(recovery, "_run", side_effect=command) as run:
                self.assertEqual(recovery._wifi_check(lambda: False), (True, expected))
            if expected:
                self.assertEqual(run.call_count, 2)

    def test_missing_tools_timeouts_and_invalid_json_are_nonfatal(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("pactl", 2)):
            with patch.object(recovery.subprocess, "run", side_effect=error):
                self.assertIsNone(recovery._run(["pactl"]))
        with patch.object(recovery, "_run", return_value=Mock(returncode=0, stdout="invalid")):
            self.assertIsNone(recovery._listing("cards"))


if __name__ == "__main__":
    unittest.main()
