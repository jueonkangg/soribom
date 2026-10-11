"""소리 이벤트(기능 3) — 지금은 '이름 호명'만 음성 기반으로 감지한다.

왜 이렇게(경량 구현):
  원래 기능 3은 종소리·경보 같은 '말이 아닌 소리'까지 오디오 모델로 분류하는 것이었다.
  그건 모델·시간이 필요해 다음 단계로 남기고, 먼저 이름 호명만 안전하게 구현한다.
  방법: 자막(STT)이 이미 뽑아 준 텍스트에 학생 이름이 들어 있으면 알림을 낸다.
  → 새 모델·마이크 0. 자막 텍스트를 '읽기'만 한다.
"""
import re


class SoundEventClassifier:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.student_names = []
        for name in cfg.get("student_names", []):
            name = name.strip()
            if name and name not in self.student_names:
                self.student_names.append(name)
        # 한국어 호격·조사가 붙은 이름은 허용하되 긴 단어 안의 부분 일치는 피한다.
        self.name_patterns = []
        endings = "야|아|은|는|이|가|을|를|에게|한테|께|도|만|의|랑|와|과|씨|님|학생"
        for name in self.student_names:
            pattern = re.compile(r"(?<!\w)" + re.escape(name)
                                 + r"(?=$|\W|(?:" + endings + r")(?=$|\W))")
            self.name_patterns.append((name, pattern))

    def detect_in_text(self, text: str) -> list:
        """자막 텍스트에서 '이름 호명'을 찾아 알림 문구 목록을 돌려준다.

        오디오 모델이 아니라 이미 인식된 글자에서 찾는 것이라 새 모델이 필요 없다.
        config 의 events.enabled 일 때만 main 에서 불린다.
        """
        if not text or not self.student_names:
            return []
        matches = []
        for name, pattern in self.name_patterns:
            match = pattern.search(text)
            if match:
                matches.append((match.start(), name))
        if not matches:
            return []
        # 한 발화에 한 번만 알린다. 먼저 나온 이름을 쓰고 같은 위치면 긴 이름을 우선한다.
        _, name = min(matches, key=lambda item: (item[0], -len(item[1])))
        return [f"🔔 {name} 학생을 불렀어요"]

    def stream(self, audio_q):
        """(라벨, 신뢰도) 를 yield 한다. — 비음성 소리(종소리·경보) 분류. 다음 단계(미구현)."""
        # TODO: 오디오 이벤트 분류 모델 추론
        raise NotImplementedError
