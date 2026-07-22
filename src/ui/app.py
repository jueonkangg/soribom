"""화면: 자막 + 화자 방향 + 소리 알림 + 말하기 입력. (Phase 4 = 자막 + 방향 화살표)

Qt(PySide6) 주의: GUI는 '메인 스레드'에서만 바꿀 수 있다. 그런데 자막은 main.py의
워커 스레드가 show_caption()으로 넘겨준다. 그래서 워커 스레드에서 바로 화면을
고치면 안 되고, '시그널'로 안전하게 넘겨 메인 스레드의 슬롯이 대신 고치게 한다.
"""
import math

from PySide6.QtCore import Qt, QObject, QPointF, QRectF, Signal, Slot
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)


class DirectionDial(QWidget):
    """화자 방향을 원 위의 화살표로 보여준다. 앞=위(12시), 시계 방향으로 증가."""

    def __init__(self) -> None:
        super().__init__()
        self._angle = None                 # None = 아직 방향 없음
        self.setMinimumSize(200, 200)

    def set_angle(self, angle: float) -> None:
        self._angle = angle
        self.update()                      # 다시 그리기(paintEvent) 요청

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 26

        # 바깥 원
        p.setPen(QPen(QColor("#555a66"), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # 방향 글자 (앞/오/뒤/좌)
        p.setPen(QColor("#8a90a0"))
        p.drawText(QRectF(cx - 16, cy - r - 24, 32, 20), Qt.AlignmentFlag.AlignCenter, "앞")
        p.drawText(QRectF(cx - 16, cy + r + 4, 32, 20), Qt.AlignmentFlag.AlignCenter, "뒤")
        p.drawText(QRectF(cx + r + 4, cy - 10, 24, 20), Qt.AlignmentFlag.AlignCenter, "오")
        p.drawText(QRectF(cx - r - 28, cy - 10, 24, 20), Qt.AlignmentFlag.AlignCenter, "좌")

        # 화살표(중심 → 방향). 앞=위, 시계 방향: x=+sin, y=-cos.
        if self._angle is not None:
            rad = math.radians(self._angle)
            tx = cx + r * 0.82 * math.sin(rad)
            ty = cy - r * 0.82 * math.cos(rad)
            pen = QPen(QColor("#4da6ff"), 7)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(cx, cy), QPointF(tx, ty))

        # 가운데 점
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f2f2f2"))
        p.drawEllipse(QPointF(cx, cy), 6, 6)


class SoribomUI(QObject):
    # 워커 스레드 → 메인 스레드로 (자막, 방향)을 안전하게 넘기는 통로.
    _caption_arrived = Signal(str, object)   # (text, angle 또는 None)

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
        main = QVBoxLayout(self.window)
        main.setContentsMargins(40, 40, 40, 40)

        # 위쪽 오른쪽: 방향 화살표
        top = QHBoxLayout()
        top.addStretch()
        self.dial = DirectionDial()
        top.addWidget(self.dial)
        main.addLayout(top)

        main.addStretch()                   # 자막을 아래로 민다

        # 아래쪽 왼쪽: 자막
        self.caption_label = QLabel("소리봄 준비 완료 — 말하면 자막이 나옵니다.")
        self.caption_label.setStyleSheet(
            f"color: #f2f2f2; font-size: {self.font_size}px; font-weight: 600;"
        )
        self.caption_label.setWordWrap(True)
        self.caption_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        main.addWidget(self.caption_label)

        # 전체화면에서 빠져나올 방법(ESC). 없으면 창을 못 닫고 갇힌다.
        QShortcut(QKeySequence("Escape"), self.window, activated=self.window.close)

        self._caption_arrived.connect(self._update)

    @Slot(str, object)
    def _update(self, text: str, angle) -> None:
        """메인 스레드에서 실행: 자막과 방향을 화면에 반영한다."""
        if text:
            self._lines.append(text)
            self._lines = self._lines[-self.max_lines:]
            self.caption_label.setText("\n".join(self._lines))
        if angle is not None:
            self.dial.set_angle(angle)

    def show_caption(self, text: str, angle: float = None, tentative: bool = False) -> None:
        """자막과 화자 방향을 화면에 띄운다. (tentative는 단일패스라 안 씀)

        어느 스레드에서 불려도 안전하도록 시그널로만 넘긴다.
        """
        self._caption_arrived.emit(text, angle)

    def show_alert(self, label: str, confidence: float) -> None:
        # 비음성 소리 이벤트 알림 — 이번 개발 범위 밖(다음 단계). 자리만 둔다.
        pass

    def run(self) -> None:
        """전체화면으로 띄우고 이벤트 루프를 돈다. (ESC로 종료)"""
        self.window.showFullScreen()
        self.app.exec()


# ---------------------------------------------------------------------------
# 자체 테스트: 창을 띄우고 1.5초마다 가짜 자막+방향을 흘려 넣는다.
# 자막이 쌓이며 방향 화살표가 도는지 눈으로 확인한다. ESC로 종료.
#   실행(모니터가 연결된 데스크톱에서): python src/ui/app.py
# ---------------------------------------------------------------------------
def _selftest() -> None:
    from pathlib import Path

    import yaml
    from PySide6.QtCore import QTimer

    cfg = yaml.safe_load(open(Path(__file__).resolve().parents[1] / "config.yaml", encoding="utf-8"))
    ui = SoribomUI(cfg)

    # (자막, 방향각) — 앞0·오른90·뒤180·왼270 으로 돌려본다.
    samples = [
        ("안녕하세요 여러분", 0),
        ("오늘은 광합성에 대해 배웁니다", 90),
        ("식물은 빛으로 양분을 만듭니다", 180),
        ("질문 있는 사람 있나요?", 270),
        ("(ESC 를 누르면 종료됩니다)", None),
    ]
    step = {"i": 0}

    def tick() -> None:
        text, angle = samples[step["i"] % len(samples)]
        ui.show_caption(text, angle=angle)
        step["i"] += 1

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(1500)

    ui.run()


if __name__ == "__main__":
    _selftest()
