"""실제 Qt에서 로딩 단계·실패 재시도·완료 화면 전환을 검증한다."""
import gc
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from PySide6.QtWidgets import QApplication
from ui.app import SoribomUI
from ui.loading import LoadingWindow


class LoadingUITests(unittest.TestCase):
    def setUp(self):
        gc.collect()
        self.app = QApplication.instance() or QApplication([])
        self.loading = LoadingWindow()
        self.addCleanup(self.loading.finish)

    def test_worker_updates_actual_stage_and_keeps_indeterminate_progress(self):
        self.loading.show_centered()
        thread = threading.Thread(target=self.loading.set_stage, args=(4, '말하기 모델을 읽고 있습니다.'))
        thread.start()
        thread.join()
        self.app.processEvents()
        self.assertIn('5/7', self.loading.status.text())
        self.assertIn('말하기 모델', self.loading.status.text())
        self.assertEqual(self.loading.progress.maximum(), 0)
        self.assertTrue(self.loading.isVisible())

    def test_failed_stage_exposes_retry_and_retry_returns_to_loading(self):
        self.loading.show_centered()
        self.loading.on_retry = Mock(side_effect=lambda: self.loading.set_stage(2))
        self.loading.fail('자막 모델 준비에 실패했습니다.')
        self.app.processEvents()
        self.assertTrue(self.loading.retry.isVisible())
        self.assertEqual(self.loading.progress.maximum(), 1)
        self.loading.retry.click()
        self.app.processEvents()
        self.loading.on_retry.assert_called_once()
        self.assertFalse(self.loading.retry.isVisible())
        self.assertIn('음성인식 모델', self.loading.status.text())

    def test_main_window_replaces_loading_only_after_models_ready(self):
        ui = SoribomUI({'ui': {}})
        self.addCleanup(ui.window.close)
        ui.startup_window = self.loading
        ui._running = True
        self.loading.show_centered()
        ui.set_models_ready(False)
        self.app.processEvents()
        self.assertFalse(ui.window.isVisible())
        ui.set_models_ready(True)
        self.app.processEvents()
        self.assertTrue(ui.window.isVisible())
        self.assertFalse(self.loading.isVisible())
