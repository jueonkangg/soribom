"""비정상 생성 반복을 줄이되 실제 반복·수업 목록·앞뒤 설명을 보존한다."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from stt.repetition import trim_repetition_loops


class RepetitionTests(unittest.TestCase):
    def test_observed_phrase_loop_preserves_first_phrase_and_surroundings(self):
        text = "설명입니다. " + "말하고 있을 때, " * 45 + "말."
        cleaned, removed = trim_repetition_loops(text, 2.976)
        self.assertEqual(cleaned, "설명입니다. 말하고 있을 때, 말.")
        self.assertEqual(removed, 44)

    def test_single_syllable_loop_preserves_surrounding_sentence(self):
        text = "오, " * 110 + "오. 다음 설명입니다."
        self.assertEqual(trim_repetition_loops(text, 2.016),
                         ("오. 다음 설명입니다.", 110))

    def test_english_loop_across_sentences(self):
        text = "Teacher, I have a question. " * 25
        cleaned, removed = trim_repetition_loops(text, 2)
        self.assertEqual(cleaned, "Teacher, I have a question. ")
        self.assertEqual(removed, 24)

    def test_real_repetition_and_distinct_lists_are_not_deleted(self):
        for text, seconds in [("중요합니다. " * 8, 10),
                              ("안녕하세요. 안녕하세요.", 0.1),
                              ("네, 네, 네, 네, 네, 네, 네, 네.", 0.1),
                              ("이산화탄소, 포도당, 광합성, 엽록체, 산소", 0.1),
                              (" ", 1)]:
            with self.subTest(text=text):
                self.assertEqual(trim_repetition_loops(text, seconds), (text, 0))

    def test_unknown_duration_does_not_guess(self):
        text = "반복된 설명입니다. " * 10
        for seconds in (0, -1, float("nan"), float("inf")):
            self.assertEqual(trim_repetition_loops(text, seconds), (text, 0))

    def test_two_different_loops_and_middle_explanation_survive(self):
        text = "안녕하세요. " * 20 + "중요한 내용입니다. " + "질문이 있습니다. " * 20
        cleaned, removed = trim_repetition_loops(text, 2)
        self.assertEqual(cleaned, "안녕하세요. 중요한 내용입니다. 질문이 있습니다. ")
        self.assertEqual(removed, 38)
