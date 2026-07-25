"""과목별 수업 용어 사전 로더.

src/vocab/ 의 텍스트 파일(한 줄 한 단어)을 읽어, STT hotwords 로 쓸 용어 목록을 만든다.
  - common.txt : 과목 무관 공통 용어
  - <subject>.txt : 과목별 용어 (korean/math/science/english/economics)
hotwords = 공통 + 선택 과목 + 추가어(학생 이름 등).

왜 hotwords 인가: initial_prompt 는 소리가 불분명할 때 그 용어들을 그대로 뱉는(에코) 문제가 있다.
hotwords 는 인식을 용어 쪽으로 편향만 하고 에코가 적다. (transcriber.py 참고)
"""
from pathlib import Path

VOCAB_DIR = Path(__file__).resolve().parents[1] / "vocab"

# UI 드롭다운·config 에서 쓰는 과목 키와 한국어 라벨.
SUBJECTS = ["korean", "math", "science", "english", "economics"]
SUBJECT_LABELS = {
    "korean": "국어",
    "math": "수학",
    "science": "과학",
    "english": "영어",
    "economics": "경제",
}


def load_terms(name: str) -> list:
    """vocab/<name>.txt 를 읽어 용어 리스트로. 없으면 빈 리스트."""
    path = VOCAB_DIR / f"{name}.txt"
    if not path.exists():
        return []
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()   # 주석·공백 제거
        if line:
            terms.append(line)
    return terms


def build_hotwords(subject: str, extra=()) -> list:
    """공통 + 과목 + 추가어(이름 등)를 합쳐 중복 없이 순서대로 돌려준다."""
    terms = load_terms("common") + load_terms(subject) + list(extra)
    seen, result = set(), []
    for t in terms:
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result
