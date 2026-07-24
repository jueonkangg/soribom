"""소리 이벤트 — 지금은 '이름 호명'만 음성 기반으로 감지한다.

왜 이렇게(경량 ③):
  원래 ③은 종소리·경보 같은 '말이 아닌 소리'까지 오디오 모델로 분류하는 것이었다.
  그건 모델·시간이 필요해 다음 단계로 남기고, 먼저 **이름 호명**만 안전하게 구현한다.
  방법: 자막(STT)이 이미 뽑아 준 텍스트에 학생 이름이 들어 있으면 알림을 낸다.
  → 새 모델·마이크 0. 세 기능(자막·방향·말하기)을 건드리지 않고 '읽기'만 한다.
"""


class SoundEventClassifier:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        # 감지할 학생 이름(부분 일치). "함도유 학생" → '함도유', "도유야" → '도유' 로 잡힌다.
        self.student_names = cfg.get("student_names", [])

    def detect_in_text(self, text: str) -> list:
        """자막 텍스트에서 '이름 호명'을 찾아 알림 문구 목록을 돌려준다.

        오디오 모델이 아니라 이미 인식된 글자에서 찾는 것이라 새 모델이 필요 없다.
        config 의 events.enabled 일 때만 main 에서 불린다.
        """
        if not text or not self.student_names:
            return []
        for name in self.student_names:
            if name and name in text:
                # 표시는 가장 짧은 이름으로(예: '도유')— 부르는 느낌이 자연스럽다.
                short = min(self.student_names, key=len)
                return [f"🔔 {short} 학생을 불렀어요"]   # 한 발화에 한 번만 알림
        return []

    def stream(self, audio_q):
        """(라벨, 신뢰도) 를 yield 한다. — 비음성 소리(종소리·경보) 분류, 다음 단계(미구현)."""
        # TODO: 오디오 이벤트 분류 모델 추론
        raise NotImplementedError
