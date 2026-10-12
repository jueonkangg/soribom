"""진단 실패·과부하가 앱에 영향을 주지 않고 원문을 파일에 남기지 않는지 확인한다."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from diagnostics import DiagnosticRecorder, resource_sample
from audio.recovery import AudioBuffer


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def recorder(self, **options):
        cfg = {"enabled": True, "output_dir": self.directory.name, **options}
        recorder = DiagnosticRecorder(cfg, sample=lambda: {"rss_kib": 100})
        self.addCleanup(recorder.close)
        return recorder

    def read(self, recorder):
        return [json.loads(line) for line in recorder.path.read_text().splitlines()]

    def test_shutdown_drains_events_and_excludes_private_fields(self):
        recorder = self.recorder()
        recorder.start()
        recorder.record("caption", duration_s=0.5, has_text=True,
                        text="비공개 수업 내용", password="비밀번호", exception="민감한 오류",
                        error_type="RuntimeError", microphone="개인정보")
        recorder.close()
        rows = self.read(recorder)
        self.assertEqual(rows[0]["event"], "session_start")
        self.assertEqual(rows[-1]["event"], "session_end")
        caption = next(row for row in rows if row["event"] == "caption")
        self.assertEqual(caption["duration_s"], 0.5)
        content = recorder.path.read_text()
        for value in ["비공개", "비밀번호", "민감한", "개인정보"]:
            self.assertNotIn(value, content)
        self.assertEqual(recorder.path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(recorder.worker.is_alive())

    def test_rotation_bounds_disk_and_keeps_valid_json(self):
        recorder = self.recorder(max_bytes=2048, backups=2)
        for index in range(200):
            recorder.record("caption", duration_s=index)
        recorder.start()
        recorder.close()
        self.assertEqual(self.read(recorder)[-1]["event"], "session_end")
        files = list(Path(self.directory.name).glob("runtime.jsonl*"))
        self.assertLessEqual(len(files), 3)
        self.assertGreater(len(files), 1)
        for path in files:
            self.assertLessEqual(path.stat().st_size, 2048)
            for line in path.read_text().splitlines():
                json.loads(line)

    def test_full_queue_drops_diagnostics_without_blocking(self):
        recorder = self.recorder()
        for _ in range(1000):
            recorder.record("caption", has_text=True)
        self.assertEqual(recorder.queue.qsize(), 256)
        self.assertEqual(recorder.dropped, 744)
        recorder.start()
        recorder.close()
        self.assertEqual(self.read(recorder)[-1]["event"], "session_end")

    def test_analyzer_reports_memory_errors_and_loss_without_original_text(self):
        import importlib.util
        path = Path(__file__).resolve().parents[1] / "scripts/analyze_diagnostics.py"
        spec = importlib.util.spec_from_file_location("diagnostic_analysis", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows = [{"session": "s", "time": "2026-10-12", "event": "session_start"},
                {"session": "s", "time": "2026-10-12", "event": "resources",
                 "rss_kib": 102400, "queue_dropped_blocks": 5},
                {"session": "s", "time": "2026-10-12", "event": "caption",
                 "has_text": True, "duration_s": 0.5},
                {"session": "s", "time": "2026-10-12", "event": "error",
                 "stage": "caption", "error_type": "RuntimeError"},
                {"session": "s", "time": "2026-10-12", "event": "session_end", "clean": True}]
        report = module.summarize(rows)
        self.assertIn("100.0", report)
        self.assertIn("queue_dropped_blocks: 5", report)
        self.assertIn("caption/RuntimeError: 1건", report)
        self.assertIn("종료: 정상", report)

    def test_disk_failure_disables_logging_and_app_can_continue(self):
        recorder = self.recorder()
        with patch.object(recorder, "_write", side_effect=OSError("민감한 경로")):
            recorder.start()
            recorder.worker.join(2)
        self.assertFalse(recorder.enabled)
        recorder.record("caption", has_text=True)
        recorder.close()

    def test_disabled_recorder_does_not_create_files_or_worker(self):
        recorder = self.recorder(enabled=False)
        recorder.start()
        recorder.record("caption", has_text=True)
        recorder.close()
        self.assertIsNone(recorder.worker)
        self.assertFalse(recorder.path.exists())

    def test_queue_counters_distinguish_discarded_audio_and_stale_results(self):
        audio = AudioBuffer(2)
        audio.put(np.ones(480))
        audio.put(np.ones(480))
        audio.put(np.ones(480))
        self.assertFalse(audio.publish(0, lambda: self.fail("이전 결과가 게시됨")))
        stats = audio.stats()
        self.assertEqual(stats["queue_dropped_blocks"], 2)
        self.assertEqual(stats["queue_depth"], 1)
        self.assertEqual(stats["stale_results"], 1)
        self.assertEqual(stats["resets"], 1)
        self.assertEqual(stats["queue_overflows"], 1)

    def test_resource_sample_reads_current_resident_memory(self):
        sample = resource_sample()
        self.assertGreater(sample["rss_kib"], 0)
        self.assertGreater(sample["available_kib"], 0)


if __name__ == "__main__":
    unittest.main()
