"""MeloTTS 오프라인 한국어 TTS → I2S 내장 스피커 발화.

왜 MeloTTS 인가:
  원래 Piper 를 쓰려 했으나 Piper 는 한국어 음성 모델이 없다.
  (https://github.com/rhasspy/piper/discussions/680 에서 확인)
  MeloTTS 는 한국어를 공식 지원하고, MIT 라이선스이며,
  CPU 만으로도 실시간 합성이 가능해 Jetson 에 적합하다.

왜 스피커를 단말에 내장하는가:
  교실 벽 스피커에서 소리가 나면 반 친구들이 누가 말했는지 알 수 없지만,
  학생 자리에서 나면 소리의 방향으로 화자를 자연스럽게 인식한다.
  이건 UX 설계 결정이지 기술적 편의가 아니다.
"""


class Speaker:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        # TODO: melo.api.TTS 로 한국어 모델 로드
        #   from melo.api import TTS
        #   self.tts = TTS(language=cfg["language"], device="cpu")
        #   self.speaker_id = self.tts.hps.data.spk2id[cfg["speaker"]]

    def say(self, text: str) -> None:
        """텍스트를 합성해 I2S 사운드카드로 재생한다."""
        # TODO: tts_to_file 로 wav 생성 → cfg['output_device'] 로 재생
        raise NotImplementedError
