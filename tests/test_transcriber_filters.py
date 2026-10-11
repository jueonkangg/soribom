"""모델을 로딩하지 않고 정상 발화 보존과 환각 필터의 경계를 검증한다."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class TranscriberFilterTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "src/stt/transcriber.py"
        spec = importlib.util.spec_from_file_location("transcriber_under_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"faster_whisper": SimpleNamespace(WhisperModel=Mock())}):
            spec.loader.exec_module(module)
        self.stt = module.Transcriber.__new__(module.Transcriber)
        self.stt.cfg = {}
        self.stt.language = "ko"
        self.stt.beam_size = 1
        self.stt.keywords = ["이산화탄소", "포도당", "광합성"]
        self.stt.model = Mock()

    def segment(self, text, no_speech=0.1, logprob=-0.2):
        return SimpleNamespace(text=text, no_speech_prob=no_speech, avg_logprob=logprob)

    def transcribe(self, *segments):
        self.stt.model.transcribe.return_value = (iter(segments), None)
        return self.stt.transcribe([])

    def test_confident_science_lists_are_preserved(self):
        for text in ["이산화탄소, 포도당", "이산화탄소 포도당 광합성"]:
            with self.subTest(text=text):
                self.assertEqual(self.transcribe(self.segment(text)), text)

    def test_weak_keyword_lists_are_removed(self):
        for no_speech, logprob in [(0.6, -0.2), (0.1, -1.0)]:
            with self.subTest(no_speech=no_speech, logprob=logprob):
                self.assertEqual(self.transcribe(self.segment("이산화탄소, 포도당", no_speech, logprob)), "")

    def test_suspect_list_does_not_delete_valid_explanation(self):
        self.assertEqual(self.transcribe(
            self.segment("이산화탄소, 포도당", logprob=-1.0),
            self.segment("광합성은 빛 에너지를 이용합니다.")
        ), "광합성은 빛 에너지를 이용합니다.")

    def test_low_confidence_normal_sentence_is_not_treated_as_keyword_echo(self):
        text = "광합성에는 이산화탄소가 필요합니다."
        self.assertEqual(self.transcribe(self.segment(text, logprob=-1.0)), text)

    def test_existing_silence_and_very_low_confidence_guards_remain(self):
        self.assertEqual(self.transcribe(
            self.segment("안녕하세요", no_speech=0.9),
            self.segment("수업을 시작합니다", logprob=-1.4)
        ), "")

    def test_subject_change_during_inference_keeps_original_filter_vocabulary(self):
        def decode(*args, **kwargs):
            self.assertEqual(kwargs["hotwords"], "이산화탄소, 포도당, 광합성")
            self.stt.keywords = ["재정정책", "통화정책"]
            return iter([self.segment("이산화탄소, 포도당", logprob=-1.0)]), None
        self.stt.model.transcribe.side_effect = decode
        self.assertEqual(self.stt.transcribe([]), "")

    def test_empty_vocabulary_and_empty_output(self):
        self.stt.keywords = []
        self.assertEqual(self.transcribe(self.segment("이산화탄소, 포도당", logprob=-1.0)), "이산화탄소, 포도당")
        self.assertIsNone(self.stt.model.transcribe.call_args.kwargs["hotwords"])
        self.assertEqual(self.transcribe(), "")

    def test_echo_threshold_is_configurable(self):
        self.stt.cfg = {"echo_no_speech_prob": 0.7, "echo_avg_logprob": -1.2}
        text = "이산화탄소, 포도당"
        self.assertEqual(self.transcribe(self.segment(text, 0.6, -1.0)), text)


if __name__ == "__main__":
    unittest.main()
