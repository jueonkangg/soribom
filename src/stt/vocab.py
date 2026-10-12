"""과목별 수업 용어 사전 로더.

src/vocab/ 의 텍스트 파일(한 줄 한 단어)을 읽어, STT hotwords 로 쓸 용어 목록을 만든다.
  - common.txt : 과목 무관 공통 용어
  - <subject>.txt : 과목별 용어 (korean/math/science/english/economics)
hotwords는 등록 이름을 우선하고 선택 과목·공통 용어를 번갈아 배치한다.

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


def build_name_hotwords(names) -> list:
    """등록 이름과 호격·학생 호칭을 만든다. 알림 감지 이름 목록 자체는 늘리지 않는다."""
    terms = []
    for name in names or []:
        name = name.strip()
        if not name:
            continue
        terms.extend([name, f"{name} 학생", f"{name}학생"])
        last = ord(name[-1])
        if 0xAC00 <= last <= 0xD7A3:
            # 받침이 있으면 '주언아', 없으면 '도유야'로 부른다.
            ending = "아" if (last - 0xAC00) % 28 else "야"
            terms.append(name + ending)
    return list(dict.fromkeys(terms))


def build_hotwords(subject: str, extra=(), lesson=None) -> list:
    """이름·선택한 수업 용어 우선, 나머지 과목·공통 용어는 번갈아 배치한다."""
    subject_terms = load_terms(subject)
    common_terms = load_terms("common")
    terms = list(extra)
    if lesson:
        terms.extend(load_terms(lesson))
    for index in range(max(len(subject_terms), len(common_terms))):
        if index < len(subject_terms):
            terms.append(subject_terms[index])
        if index < len(common_terms):
            terms.append(common_terms[index])
    seen, result = set(), []
    for t in terms:
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result


def fit_hotwords(terms, tokenizer, max_tokens):
    """라이브러리의 토큰 제한 안에 완전한 용어만 넣는다. 긴 항목은 건너뛴다."""
    selected = []
    for term in terms:
        candidate = ", ".join(selected + [term])
        count = len(tokenizer.encode(" " + candidate, add_special_tokens=False).ids)
        if count <= max_tokens:
            selected.append(term)
    return selected
