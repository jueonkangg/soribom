"""호명 표현이 실제 STT 힌트에 포함되고 과목 변경 후에도 유지되는지 확인한다."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
import importlib.util
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from stt.vocab import build_hotwords, build_name_hotwords, fit_hotwords, load_terms, SUBJECTS


class VocabHotwordsTests(unittest.TestCase):
    def test_calling_forms_use_correct_korean_ending(self):
        terms = build_name_hotwords(["함도유", "도유", "주언"])
        for term in ["함도유", "함도유야", "함도유 학생", "함도유학생",
                     "도유야", "도유 학생", "주언아"]:
            self.assertIn(term, terms)
        self.assertNotIn("도유아", terms)
        self.assertNotIn("주언야", terms)

    def test_names_are_cleaned_and_non_korean_names_do_not_get_guessed_endings(self):
        terms = build_name_hotwords(["", " ", " 도유 ", "도유", "Alex"])
        self.assertEqual(terms.count("도유"), 1)
        self.assertIn("Alex 학생", terms)
        self.assertNotIn("Alex야", terms)
        self.assertEqual(build_name_hotwords(None), [])

    def test_each_subject_has_its_dictionary_and_common_classroom_words(self):
        extra = build_name_hotwords(["도유"])
        for subject in SUBJECTS:
            with self.subTest(subject=subject):
                terms = build_hotwords(subject, extra)
                self.assertTrue(load_terms(subject))
                for term in ["교과서", "학습지", "활동지", "대답해 주세요", "도유야"]:
                    self.assertIn(term, terms)
                self.assertEqual(len(terms), len(set(terms)))

    def test_subject_change_keeps_calling_forms_in_decoder_hotwords(self):
        path = Path(__file__).resolve().parents[1] / "src/stt/transcriber.py"
        spec = importlib.util.spec_from_file_location("transcriber_vocab_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"faster_whisper": SimpleNamespace(WhisperModel=Mock())}):
            spec.loader.exec_module(module)
        stt = module.Transcriber.__new__(module.Transcriber)
        stt.cfg = {}
        stt.language = "ko"
        stt.beam_size = 1
        stt.subject = "science"
        stt.model = Mock()
        stt.model.max_length = 448
        stt.model.hf_tokenizer.encode.side_effect = lambda text, **kwargs: SimpleNamespace(ids=text.split())
        stt.model.transcribe.return_value = ([], None)
        stt.set_extra_terms(build_name_hotwords(["함도유", "도유"]))
        for subject in ["science", "economics"]:
            stt.set_subject(subject)
            stt.transcribe([])
            hints = stt.model.transcribe.call_args.kwargs["hotwords"].split(", ")
            self.assertIn("함도유 학생", hints)
            self.assertIn("도유야", hints)
        self.assertIn("수요", hints)

    def test_names_precede_both_dictionaries(self):
        names = build_name_hotwords(["도유"])
        terms = build_hotwords("science", names)
        self.assertEqual(terms[:len(names)], names)
        self.assertEqual(terms[len(names):len(names) + 4], ["광합성", "선생님", "엽록체", "여러분"])

    def test_budget_keeps_complete_terms_and_skips_overlong_entry(self):
        tokenizer = SimpleNamespace(encode=lambda text, **kwargs: SimpleNamespace(ids=list(text)))
        selected = fit_hotwords(["도유야", "아주 긴 용어는 여기서 제외", "학생"], tokenizer, 9)
        self.assertEqual(selected, ["도유야", "학생"])
        self.assertLessEqual(len(tokenizer.encode(" " + ", ".join(selected)).ids), 9)

    def test_actual_whisper_tokenizer_keeps_names_within_library_budget(self):
        # GPU 모델 없이 설치된 모델의 토크나이저·라이브러리 프롬프트를 검증한다.
        from tokenizers import Tokenizer as HFTokenizer
        from faster_whisper import WhisperModel
        from faster_whisper.tokenizer import Tokenizer
        root = Path.home() / ".cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots"
        paths = list(root.glob("*/tokenizer.json"))
        if not paths:
            self.skipTest("로컬 small 토크나이저 없음")
        hf = HFTokenizer.from_file(str(paths[0]))
        tokenizer = Tokenizer(hf, multilingual=True, task="transcribe", language="ko")
        model = WhisperModel.__new__(WhisperModel)
        model.max_length = 448
        names = build_name_hotwords(["함도유", "도유"])
        for subject in SUBJECTS:
            with self.subTest(subject=subject):
                terms = fit_hotwords(build_hotwords(subject, names), hf, 223)
                text = ", ".join(terms)
                tokens = tokenizer.encode(" " + text)
                self.assertLessEqual(len(tokens), 223)
                for name in names:
                    self.assertIn(name, terms)
                prompt = model.get_prompt(tokenizer, [], hotwords=text)
                self.assertEqual(prompt[1:1 + len(tokens)], tokens)
                self.assertIn("함도유 학생", tokenizer.decode(prompt))


if __name__ == "__main__":
    unittest.main()
