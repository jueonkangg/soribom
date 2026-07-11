"""말이 아닌 소리(이름 호명, 종소리, 질문, 경보)를 분류한다."""


class SoundEventClassifier:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg

    def stream(self, audio_q):
        """(라벨, 신뢰도) 를 yield 한다."""
        # TODO: 오디오 이벤트 분류 모델 추론
        raise NotImplementedError
