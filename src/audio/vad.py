"""Silero VAD — 사람이 말하는 구간만 잘라낸다."""


class VoiceActivityDetector:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg

    def stream(self, audio_q):
        """말하는 구간이 끝날 때마다 오디오 청크를 yield 한다."""
        # TODO: silero-vad 로 발화 시작/끝 판정 후 청크 방출
        raise NotImplementedError
