"""수업 종료 후 화자별 요약 노트를 만든다.

추출식(extractive) 요약을 쓴다. 생성식은 없는 말을 지어낼 수 있어
학습 자료로 신뢰하기 어렵다.
"""


class NoteBuilder:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.lines: list = []

    def add(self, text: str, angle: float) -> None:
        self.lines.append({"text": text, "angle": angle})

    def save(self) -> None:
        """핵심 문장을 뽑아 화자별 노트로 저장한다."""
        # TODO: 문장 점수화(TextRank 등) → 상위 top_k 추출 → 저장
        raise NotImplementedError
