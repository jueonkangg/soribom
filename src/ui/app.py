"""화면: 자막 + 화자 방향 + 소리 알림 + 말하기 입력. (Phase 3 = 자막 창 뼈대)

Qt(PySide6) 주의: GUI는 '메인 스레드'에서만 바꿀 수 있다. 그런데 자막은 main.py의
워커 스레드가 show_caption()으로 넘겨준다. 그래서 워커 스레드에서 바로 라벨을
고치면 안 되고, '시그널'로 안전하게 넘겨 메인 스레드의 슬롯이 대신 고치게 한다.
"""
from PySide6.QtCore import Qt, QObject, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


class SoribomUI(QObject):
    # 워커 스레드 → 메인 스레드로 자막을 안전하게 넘기는 통로.
    _caption_arrived = Signal(str)

    def __init__(self, cfg: dict) -> None:
        super().__init__()
        self.cfg = cfg
        self.on_speak = lambda text: None   # main 에서 Speaker.say 로 연결

        ui = cfg.get("ui", {})
        self.font_size = ui.get("font_size", 36)
        self.max_lines = ui.get("max_lines", 3)
        self._lines = []                    # 화면에 남길 최근 자막 줄들

        # QApplication 은 프로그램당 하나. 이미 있으면 그걸 쓰고 없으면 만든다.
        self.app = QApplication.instance() or QApplication([])

        self.window = QWidget()
        self.window.setStyleSheet("background-color: #101014;")
        layout = QVBoxLayout(self.window)
        layout.setContentsMargins(40, 40, 40, 40)

        self.caption_label = QLabel("소리봄 준비 완료 — 말하면 자막이 나옵니다.")
        self.caption_label.setStyleSheet(
            f"color: #f2f2f2; font-size: {self.font_size}px; font-weight: 600;"
        )
        self.caption_label.setWordWrap(True)
        self.caption_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.caption_label)

        # 전체화면에서 빠져나올 방법(ESC). 없으면 창을 못 닫고 갇힌다.
        QShortcut(QKeySequence("Escape"), self.window, activated=self.window.close)

        # 시그널이 오면 메인 스레드에서 라벨을 고친다.
        self._caption_arrived.connect(self._update_caption)

    @Slot(str)
    def _update_caption(self, text: str) -> None:
        """메인 스레드에서 실행: 최근 max_lines 줄만 남겨 표시한다."""
        if not text:
            return
        self._lines.append(text)
        self._lines = self._lines[-self.max_lines:]
        self.caption_label.setText("\n".join(self._lines))

    def show_caption(self, text: str, angle: float = None, tentative: bool = False) -> None:
        """자막을 화면에 띄운다. (angle=방향은 Phase 4, tentative는 단일패스라 안 씀)

        어느 스레드에서 불려도 안전하도록 시그널로만 넘긴다.
        """
        self._caption_arrived.emit(text)

    def show_alert(self, label: str, confidence: float) -> None:
        # 비음성 소리 이벤트 알림 — 이번 개발 범위 밖(다음 단계). 자리만 둔다.
        pass

    def run(self) -> None:
        """전체화면으로 띄우고 이벤트 루프를 돈다. (ESC로 종료)"""
        self.window.showFullScreen()
        self.app.exec()


# ---------------------------------------------------------------------------
# 자체 테스트: 창을 띄우고 1.5초마다 가짜 자막을 흘려 넣는다.
# 자막이 화면에 쌓이며 최근 몇 줄만 남는지 눈으로 확인한다. ESC로 종료.
#   실행(모니터가 연결된 데스크톱에서): python src/ui/app.py
# ---------------------------------------------------------------------------
def _selftest() -> None:
    from pathlib import Path

    import yaml
    from PySide6.QtCore import QTimer

    cfg = yaml.safe_load(open(Path(__file__).resolve().parents[1] / "config.yaml", encoding="utf-8"))
    ui = SoribomUI(cfg)

    samples = [
        "안녕하세요 여러분",
        "오늘은 광합성에 대해 배웁니다",
        "식물은 빛으로 양분을 만듭니다",
        "질문 있는 사람 있나요?",
        "(ESC 를 누르면 종료됩니다)",
    ]
    step = {"i": 0}

    def tick() -> None:
        ui.show_caption(samples[step["i"] % len(samples)])
        step["i"] += 1

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(1500)

    ui.run()


if __name__ == "__main__":
    _selftest()
