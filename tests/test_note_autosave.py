"""수업 기록 유실·덮어쓰기와 저장 실패 후 복구를 검증한다."""
from pathlib import Path
import sys
import tempfile
import threading
import subprocess
from datetime import datetime
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from summary.notes import NoteBuilder


class NoteAutosaveTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name)
        self.notes = NoteBuilder({"output_dir": directory.name, "autosave_seconds": 1})
        self.addCleanup(self.notes.stop_autosave)

    def test_sessions_have_unique_files_and_updates_keep_one_file(self):
        self.assertIsNone(self.notes.save())
        self.notes.add("첫 문장", 0)
        path = self.notes.save()
        self.notes.add("두 번째 문장", 90)
        self.assertEqual(self.notes.save(), path)
        self.assertIn("두 번째 문장", path.read_text())
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        other = NoteBuilder({"output_dir": str(self.folder)})
        other.add("다른 수업", 180)
        self.assertNotEqual(other.save(), path)
        self.assertIn("첫 문장", path.read_text())
        self.assertEqual(len(list(self.folder.glob("*.txt"))), 2)

    def test_weekday_and_selected_subject_match_preview_and_saved_file(self):
        self.notes.started_at = datetime(2026, 10, 11, 10, 30)
        self.notes.set_subject("math")
        self.notes.add("삼각형을 배웁니다", 0)
        preview = self.notes.build_email_transcript()
        self.assertIn("2026-10-11 (일요일) 10:30", preview)
        self.assertIn("과목: 수학", preview)
        self.assertEqual(self.notes.save().read_text(), preview + "\n")

    def test_subject_change_preserves_earlier_lines_and_groups_same_text(self):
        self.notes.add("첫 번째 설명", 0)
        first = self.notes.build_email_transcript()
        self.notes.set_subject("english")
        self.notes.add("첫 번째 설명", 0)
        transcript = self.notes.build_email_transcript()
        self.assertIn("과목: 과학, 영어", transcript)
        self.assertIn("[과학]\n• 첫 번째 설명.", transcript)
        self.assertIn("[영어]\n• 첫 번째 설명.", transcript)
        self.assertIn("발화 2개", transcript)
        self.assertNotIn("영어", first)

    def test_subject_captured_before_transcription_survives_selection_change(self):
        subject = self.notes.current_subject()
        self.notes.set_subject("economics")
        self.notes.add("전사 중 과목이 바뀌어도 원래 과목 유지", 0, subject=subject)
        self.assertIn("과목: 과학", self.notes.build_email_transcript())
        self.notes.add("새 과목의 발화", 0)
        self.assertIn("과목: 과학, 경제", self.notes.build_email_transcript())

    def test_disk_failure_keeps_previous_file_and_retries_pending_content(self):
        self.notes.add("저장된 문장", 0)
        path = self.notes.save()
        previous = path.read_bytes()
        self.notes.add("추가 문장", 90)
        with patch("summary.notes.os.replace", side_effect=OSError("disk full")):
            self.assertFalse(self.notes.save_safely())
        self.assertEqual(path.read_bytes(), previous)
        self.assertEqual(list(self.folder.glob("*.tmp")), [])
        self.assertTrue(self.notes.save_safely())
        self.assertIn("추가 문장", path.read_text())

    def test_forced_exit_preserves_autosaved_transcript(self):
        script = """
import sys, threading
sys.path.insert(0, sys.argv[1])
from summary.notes import NoteBuilder
saved = threading.Event()
notes = NoteBuilder({'output_dir': sys.argv[2], 'autosave_seconds': 1})
notes.start_autosave(lambda success, message: saved.set() if success else None)
notes.add('강제 종료 전 저장된 문장', 0)
if not saved.wait(5):
    raise SystemExit(1)
print('saved', flush=True)
threading.Event().wait()
"""
        source = str(Path(__file__).resolve().parents[1] / "src")
        process = subprocess.Popen([sys.executable, "-c", script, source, str(self.folder)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            # readline 자체의 무제한 대기를 피하고 파일을 최대 5초만 기다린다.
            import time
            deadline = time.monotonic() + 5
            while not list(self.folder.glob("*.txt")) and time.monotonic() < deadline:
                if process.poll() is not None:
                    self.fail(process.communicate()[1])
                time.sleep(0.02)
            paths = list(self.folder.glob("*.txt"))
            self.assertEqual(len(paths), 1)
            process.kill()
            process.communicate(timeout=3)
            self.assertIn("강제 종료 전 저장된 문장", paths[0].read_text())
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=3)

    def test_audio_arriving_during_save_is_included_in_next_save(self):
        self.notes.add("저장 시작 전", 0)
        import os
        original = os.replace
        def replace_and_add(source, destination):
            self.notes.add("저장 도중 도착", 0)
            original(source, destination)
        with patch("summary.notes.os.replace", side_effect=replace_and_add):
            path = self.notes.save()
        self.assertNotIn("저장 도중 도착", path.read_text())
        self.notes.save()
        self.assertIn("저장 도중 도착", path.read_text())

    def test_worker_saves_without_app_exit_and_stops_once(self):
        saved = threading.Event()
        self.notes.start_autosave(lambda success, message: saved.set() if success else None)
        worker = self.notes._worker
        self.notes.start_autosave(lambda *_: None)
        self.assertIs(self.notes._worker, worker)
        self.notes.add("자동으로 저장할 문장", 0)
        self.assertTrue(saved.wait(3))
        self.assertIn("자동으로", self.notes.path.read_text())
        self.notes.stop_autosave()
        self.assertFalse(worker.is_alive())

    def test_disabled_saving_and_blank_speech_create_no_file(self):
        self.notes.add("  ", 0)
        self.assertIsNone(self.notes.save())
        disabled = NoteBuilder({"enabled": False, "output_dir": str(self.folder)})
        disabled.start_autosave(lambda *_: self.fail("disabled worker started"))
        self.assertIsNone(disabled._worker)
        self.assertEqual(list(self.folder.iterdir()), [])
