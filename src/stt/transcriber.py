"""2-패스 한국어 전사.

큰 모델은 정확하지만 느리고, 작은 모델은 빠르지만 부정확하다.
둘 중 하나를 고르는 대신 작은 모델이 먼저 임시 자막을 띄우고
큰 모델이 뒤따라 교정한다.
"""


class TwoPassTranscriber:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        # TODO: faster_whisper.WhisperModel 을 pass1/pass2 두 개 로드

    def draft(self, chunk) -> str:
        """1패스 — 빠른 임시 자막 (~0.5초)."""
        raise NotImplementedError

    def refine(self, chunk) -> str:
        """2패스 — 정확한 교정 자막 (~2초)."""
        raise NotImplementedError
