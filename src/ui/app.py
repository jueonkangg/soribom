"""화면: 자막 + 화자 방향 + 소리 알림 + 말하기 입력."""


class SoribomUI:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.on_speak = lambda text: None   # main 에서 Speaker.say 로 연결

    def show_caption(self, text: str, angle: float, tentative: bool) -> None:
        """tentative=True 면 흐리게(임시), False 면 선명하게(교정) 표시."""
        raise NotImplementedError

    def show_alert(self, label: str, confidence: float) -> None:
        raise NotImplementedError

    def run(self) -> None:
        raise NotImplementedError
