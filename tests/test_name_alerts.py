"""실제 감지한 이름으로 알리고 긴 단어의 부분 일치는 제외한다."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from events.sound_events import SoundEventClassifier


class NameAlertTests(unittest.TestCase):
    def detector(self, *names):
        return SoundEventClassifier({"student_names": list(names)})

    def test_alert_names_detected_student_instead_of_shortest_registered_name(self):
        detector = self.detector("도유", "강주언")
        self.assertEqual(detector.detect_in_text("강주언 학생, 발표해 주세요."),
                         ["🔔 강주언 학생을 불렀어요"])

    def test_full_name_is_not_shortened_to_an_unrelated_alias(self):
        detector = self.detector("도유", "함도유")
        self.assertEqual(detector.detect_in_text("함도유 학생"), ["🔔 함도유 학생을 불렀어요"])

    def test_korean_calling_endings_and_particles_are_supported(self):
        detector = self.detector("도유")
        for text in ["도유야, 대답해 줘.", "도유는 준비됐나요?", "도유에게 질문합니다.",
                     "도유학생 발표해 주세요.", "도유!"]:
            with self.subTest(text=text):
                self.assertEqual(detector.detect_in_text(text), ["🔔 도유 학생을 불렀어요"])

    def test_name_inside_another_word_does_not_trigger(self):
        detector = self.detector("민", "도유")
        for text in ["국민의 의견입니다.", "민주주의를 배웁니다.", "도유민 학생", "함도유 학생"]:
            with self.subTest(text=text):
                self.assertEqual(detector.detect_in_text(text), [])

    def test_first_mentioned_student_gets_single_alert(self):
        detector = self.detector("강주언", "도유")
        self.assertEqual(detector.detect_in_text("도유야, 강주언과 발표하자. 도유야."),
                         ["🔔 도유 학생을 불렀어요"])

    def test_longer_name_wins_when_matches_start_at_same_position(self):
        detector = self.detector("민", "민아")
        self.assertEqual(detector.detect_in_text("민아!"), ["🔔 민아 학생을 불렀어요"])

    def test_blank_and_duplicate_registered_names_are_ignored(self):
        detector = self.detector("", " ", " 도유 ", "도유")
        self.assertEqual(detector.student_names, ["도유"])
        self.assertEqual(detector.detect_in_text("도유야"), ["🔔 도유 학생을 불렀어요"])

    def test_empty_text_or_unregistered_name_does_not_alert(self):
        self.assertEqual(self.detector("도유").detect_in_text(""), [])
        self.assertEqual(self.detector().detect_in_text("도유야"), [])
        self.assertEqual(self.detector("도유").detect_in_text("주언아"), [])

    def test_registered_name_is_literal_not_regular_expression(self):
        detector = self.detector("A+B")
        self.assertEqual(detector.detect_in_text("A+B!"), ["🔔 A+B 학생을 불렀어요"])
        self.assertEqual(detector.detect_in_text("AAAB!"), [])


if __name__ == "__main__":
    unittest.main()
