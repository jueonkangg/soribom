"""모델을 로딩하지 않고 정상 발화 보존과 환각 필터의 경계를 검증한다."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class TranscriberFilterTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "src/stt/transcriber.py"
        spec = importlib.util.spec_from_file_location("transcriber_under_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"faster_whisper": SimpleNamespace(WhisperModel=Mock())}):
            spec.loader.exec_module(module)
        self.module = module
        self.stt = module.Transcriber.__new__(module.Transcriber)
        self.stt.cfg = {}
        self.stt.language = "ko"
        self.stt.subject = "science"
        self.stt.beam_size = 1
        self.stt.keywords = ["이산화탄소", "포도당", "광합성"]
        self.stt.model = Mock()
        self.stt.model.detect_language.return_value = ("en", 0.9, [("en", 0.9), ("ko", 0.1)])

    def segment(self, text, no_speech=0.1, logprob=-0.2):
        return SimpleNamespace(text=text, no_speech_prob=no_speech, avg_logprob=logprob)

    def transcribe(self, *segments):
        self.stt.model.transcribe.return_value = (iter(segments), None)
        return self.stt.transcribe([])

    def test_confident_science_lists_are_preserved(self):
        for text in ["이산화탄소, 포도당", "이산화탄소 포도당 광합성"]:
            with self.subTest(text=text):
                self.assertEqual(self.transcribe(self.segment(text)), text)

    def test_short_audio_repetition_is_cleaned_before_caption_and_record_consumers(self):
        text = "질문입니다. " + "말하고 있을 때, " * 45 + "다음 설명입니다."
        self.stt.model.transcribe.return_value = (iter([self.segment(text)]), None)
        result = self.stt.transcribe([0.0] * (3 * 16000))
        self.assertEqual(result, "질문입니다. 말하고 있을 때, 다음 설명입니다.")
        self.assertEqual(self.stt.last_filter_counts["repetition_removed"], 44)
        self.assertEqual(self.transcribe(self.segment("다음 정상 문장")), "다음 정상 문장")
        self.assertEqual(self.stt.last_filter_counts["repetition_removed"], 0)

    def test_default_retry_budget_and_legacy_settings_can_be_restored(self):
        self.transcribe(self.segment("함도유 학생, 질문이 있나요?"))
        options = self.stt.model.transcribe.call_args.kwargs
        self.assertEqual(options["temperature"], [0.0, 0.2])
        self.assertEqual(options["best_of"], 1)
        self.assertEqual(options["beam_size"], 1)
        self.stt.cfg.update(temperatures=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0], best_of=5)
        self.transcribe(self.segment("수업을 시작합니다."))
        self.assertEqual(self.stt.model.transcribe.call_args.kwargs["best_of"], 5)
        self.assertEqual(len(self.stt.model.transcribe.call_args.kwargs["temperature"]), 6)

    def test_decoder_metrics_forward_backend_results_and_reset(self):
        backend = Mock()
        backend.device = "cuda"
        backend.generate.return_value = ["결과"]
        metrics = self.module.DecodeMetrics(backend)
        self.assertEqual(metrics.device, "cuda")
        self.assertEqual(metrics.generate("입력", beam_size=1), ["결과"])
        metrics.generate("입력", sampling_temperature=0.2)
        self.assertEqual((metrics.calls, metrics.sampling_calls), (2, 1))
        self.assertGreaterEqual(metrics.seconds, 0)
        backend.generate.side_effect = ValueError("비공개 오류")
        with self.assertRaises(ValueError):
            metrics.generate("입력")
        self.assertEqual(metrics.calls, 3)
        metrics.reset()
        self.assertEqual((metrics.calls, metrics.sampling_calls, metrics.seconds), (0, 0, 0))

    def test_installed_library_fallback_really_obeys_retry_budget(self):
        # 모델 파일이나 GPU 없이 설치된 라이브러리의 실제 재시도 루프를 실행한다.
        from faster_whisper import WhisperModel
        model = WhisperModel.__new__(WhisperModel)
        model.max_length = 448
        model.time_precision = 0.02
        model.logger = Mock()
        backend = Mock()
        backend.generate.return_value = [SimpleNamespace(
            sequences_ids=[[1, 2]], scores=[-2.0], no_speech_prob=0.1)]
        model.model = self.module.DecodeMetrics(backend)
        tokenizer = Mock()
        tokenizer.decode.return_value = "시험 문장"
        for temperatures, best_of, expected_calls in (
                ([0.0, 0.2, 0.4, 0.6, 0.8, 1.0], 5, 6), ([0.0, 0.2], 1, 2)):
            options = SimpleNamespace(
                temperatures=temperatures, best_of=best_of, beam_size=1, patience=1,
                max_initial_timestamp=1, max_new_tokens=None, length_penalty=1,
                repetition_penalty=1, no_repeat_ngram_size=0, suppress_blank=True,
                suppress_tokens=[], compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0, no_speech_threshold=0.6)
            model.model.reset()
            backend.generate.reset_mock()
            model.generate_with_fallback(None, [], tokenizer, options)
            self.assertEqual(model.model.calls, expected_calls)
            self.assertEqual(model.model.sampling_calls, expected_calls - 1)
            self.assertEqual(backend.generate.call_args_list[0].kwargs["beam_size"], 1)
            self.assertEqual(backend.generate.call_args_list[-1].kwargs["num_hypotheses"], best_of)

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
        self.assertEqual(self.stt.last_filter_counts["no_speech_filtered"], 1)
        self.assertEqual(self.stt.last_filter_counts["low_confidence_filtered"], 1)

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

    def test_auto_language_is_detected_for_each_utterance_without_translation(self):
        self.stt.language = None
        self.stt.subject = "english"
        for language, text in [("en", "What is photosynthesis?"), ("ko", "광합성은 빛 에너지를 이용합니다."), ("en", "Thank you.")]:
            self.stt.model.detect_language.return_value = (language, 0.9, [(language, 0.9)])
            self.assertEqual(self.transcribe(self.segment(text)), text)
            options = self.stt.model.transcribe.call_args.kwargs
            self.assertEqual(options["language"], language)
            self.assertEqual(options["task"], "transcribe")
            self.assertFalse(options["condition_on_previous_text"])
        self.assertEqual(self.stt.model.detect_language.call_count, 3)

    def test_other_detected_languages_use_only_korean_or_english_scores(self):
        self.stt.language = None
        self.stt.subject = "english"
        for scores, expected in [([("fr", 0.8), ("ko", 0.15), ("en", 0.05)], "ko"),
                                 ([("fr", 0.8), ("ko", 0.05), ("en", 0.15)], "en")]:
            self.stt.model.detect_language.return_value = ("fr", 0.8, scores)
            self.transcribe(self.segment("시험 문장"))
            self.assertEqual(self.stt.model.transcribe.call_args.kwargs["language"], expected)

    def test_explicit_language_skips_detection(self):
        self.stt.subject = "english"
        for language in ("ko", "en"):
            self.stt.language = language
            self.transcribe(self.segment("시험 문장"))
            self.assertEqual(self.stt.model.transcribe.call_args.kwargs["language"], language)
        self.stt.model.detect_language.assert_not_called()

    def test_initialization_accepts_auto_and_explicit_language(self):
        for configured, expected in [("auto", None), (None, None), ("ko", "ko"), ("en", "en")]:
            with self.subTest(language=configured), patch.object(self.module.Transcriber, "_apply_vocab"):
                stt = self.module.Transcriber({"language": configured, "model": "small",
                                              "device": "cuda", "compute_type": "int8"})
                self.assertEqual(stt.language, expected)
        with self.assertRaisesRegex(ValueError, "auto, ko, en"):
            self.module.Transcriber({"language": "fr"})

    def test_non_english_subjects_use_korean_without_detection(self):
        self.stt.language = None
        for subject in ("korean", "math", "science", "economics"):
            with self.subTest(subject=subject):
                self.stt.subject = subject
                self.transcribe(self.segment("수업을 시작합니다."))
                self.assertEqual(self.stt.model.transcribe.call_args.kwargs["language"], "ko")
        self.stt.model.detect_language.assert_not_called()

    def test_subject_switch_applies_to_next_utterance_without_model_reload(self):
        self.stt.language = None
        model = self.stt.model
        with patch.object(self.stt, "_apply_vocab"):
            for subject, expected in [("science", "ko"), ("english", "en"),
                                      ("korean", "ko"), ("english", "en")]:
                self.stt.set_subject(subject)
                self.transcribe(self.segment("시험 문장"))
                self.assertEqual(model.transcribe.call_args.kwargs["language"], expected)
        self.assertIs(self.stt.model, model)
        self.assertEqual(model.detect_language.call_count, 2)

    def test_subject_change_during_detection_does_not_change_current_language(self):
        self.stt.language = None
        self.stt.subject = "english"
        def detect(chunk):
            self.stt.subject = "science"
            return "en", 0.9, [("en", 0.9), ("ko", 0.1)]
        self.stt.model.detect_language.side_effect = detect
        self.transcribe(self.segment("Teacher, I have a question."))
        self.assertEqual(self.stt.last_language, "en")
        self.transcribe(self.segment("선생님, 질문이 있어요."))
        self.assertEqual(self.stt.last_language, "ko")
        self.assertEqual(self.stt.model.detect_language.call_count, 1)


if __name__ == "__main__":
    unittest.main()
