"""Piper 오프라인 한국어 TTS → I2S 내장 스피커 발화.

스피커를 단말에 내장한 것이 핵심이다. 교실 벽 스피커에서 소리가 나면
반 친구들이 누가 말했는지 알 수 없지만, 학생 자리에서 나면
소리의 방향으로 화자를 자연스럽게 인식한다.
"""


class Speaker:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        # TODO: piper 음성 모델 로드

    def say(self, text: str) -> None:
        """텍스트를 합성해 I2S 사운드카드로 재생한다."""
        # TODO: piper 합성 → aplay/sounddevice 로 cfg['output_device'] 재생
        raise NotImplementedError
