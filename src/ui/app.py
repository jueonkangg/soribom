"""화면: 자막(대화록형) + 화자 방향 + 소리 알림 + 말하기 입력.

디자인: docs/figures/ui-mockup.svg 목업에 맞춘 밝은 테마.
  - 위: 네이비 헤더('소리봄')
  - 가운데: 왼쪽 자막(대화록처럼 쌓임) + 오른쪽 방향 다이얼(박스 안)
  - 아래: 양방향 말하기 입력칸 + '말하기 ▶' 버튼
  - 이벤트(이름 호명)가 있을 때만 자막 아래에 소리 알림 박스가 잠깐 뜬다.
  ※ 목업의 화자 구분(선생님/학생A)·수업 요약·녹음중·임시자막 안내는 실제 기능이 아니라 넣지 않는다.

Qt(PySide6) 주의: GUI는 '메인 스레드'에서만 바꿀 수 있다. 자막·알림은 main.py의 워커
스레드가 넘겨주므로, 워커에서 바로 화면을 고치지 않고 '시그널'로 넘겨 메인 스레드의
슬롯이 대신 고치게 한다.
"""
import math
import threading

from PySide6.QtCore import Qt, QObject, QPointF, QRectF, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)

# 목업 색 팔레트(밝은 테마)
NAVY = "#13315C"       # 헤더·강조 텍스트
PAGE_BG = "#F8FAFC"    # 페이지 배경
INK = "#1F2937"        # 본문 글자
MUTED = "#64748B"      # 보조 글자
LINE = "#C9D6E5"       # 옅은 테두리
BLUE = "#2563A8"       # 방향 화살표
GREEN = "#1B6B4C"      # 말하기 버튼
BOX_BG = "#EFF3F8"     # 다이얼 박스 배경
ALERT_BG = "#FCEEE6"   # 소리 알림 배경
ALERT_LINE = "#C2410C" # 소리 알림 테두리·제목


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
        p.setPen(QPen(QColor(LINE), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # 방향 글자 (앞/오/뒤/좌)
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(cx - 16, cy - r - 24, 32, 20), Qt.AlignmentFlag.AlignCenter, "앞")
        p.drawText(QRectF(cx - 16, cy + r + 4, 32, 20), Qt.AlignmentFlag.AlignCenter, "뒤")
        p.drawText(QRectF(cx + r + 4, cy - 10, 24, 20), Qt.AlignmentFlag.AlignCenter, "오")
        p.drawText(QRectF(cx - r - 28, cy - 10, 24, 20), Qt.AlignmentFlag.AlignCenter, "좌")

        # 화살표(중심 → 방향). 앞=위, 시계 방향: x=+sin, y=-cos.
        if self._angle is not None:
            rad = math.radians(self._angle)
            tx = cx + r * 0.82 * math.sin(rad)
            ty = cy - r * 0.82 * math.cos(rad)
            pen = QPen(QColor(BLUE), 7)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(cx, cy), QPointF(tx, ty))

        # 가운데 점
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(NAVY))
        p.drawEllipse(QPointF(cx, cy), 6, 6)


class SoribomUI(QObject):
    # 워커 스레드 → 메인 스레드로 (자막, 방향)을 안전하게 넘기는 통로.
    _caption_arrived = Signal(str, object)   # (text, angle 또는 None)
    _alert_arrived = Signal(str)             # 소리 이벤트 알림(이름 호명 등)

    def __init__(self, cfg: dict) -> None:
        super().__init__()
        self.cfg = cfg
        self.on_speak = lambda text: None   # main 에서 Speaker.say 로 연결

        ui = cfg.get("ui", {})
        self.font_size = ui.get("font_size", 36)
        # 대화록처럼 여러 줄 쌓기. config max_lines 가 작아도 흐름이 보이게 최소 5줄.
        self.max_lines = max(ui.get("max_lines", 3), 5)
        self._lines = []                    # 화면에 남길 최근 자막 줄들

        # QApplication 은 프로그램당 하나. 이미 있으면 그걸 쓰고 없으면 만든다.
        self.app = QApplication.instance() or QApplication([])

        self.window = QWidget()
        self.window.setStyleSheet(f"background-color: {PAGE_BG};")
        root = QVBoxLayout(self.window)
        root.setContentsMargins(0, 0, 0, 0)   # 헤더가 화면 끝까지 닿게
        root.setSpacing(0)

        # ── 헤더(네이비): 제목 '소리봄' ──
        header = QLabel("소리봄")
        header.setStyleSheet(
            f"background: {NAVY}; color: #FFFFFF; font-weight: 800; "
            f"font-size: {int(self.font_size * 0.7)}px; padding: 14px 28px;"
        )
        root.addWidget(header)

        # ── 본문: 왼쪽 자막 + 오른쪽 방향 박스 ──
        body = QHBoxLayout()
        body.setContentsMargins(28, 22, 28, 10)
        body.setSpacing(20)

        # 왼쪽 열: 자막(위로 쌓임) + 소리 알림 박스(아래, 평소 숨김)
        left = QVBoxLayout()
        left.setSpacing(12)
        self.caption_label = QLabel("소리봄 준비 완료 — 말하면 자막이 나옵니다.")
        self.caption_label.setStyleSheet(
            f"color: {INK}; font-size: {self.font_size}px; font-weight: 600;"
        )
        self.caption_label.setWordWrap(True)
        self.caption_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        left.addWidget(self.caption_label, stretch=1)

        # 소리 알림 박스(이름 호명). 입력칸을 밀지 않도록 자막 아래(본문 안)에 둔다.
        self.alert_label = QLabel("")
        self.alert_label.setWordWrap(True)
        self.alert_label.setStyleSheet(
            f"background: {ALERT_BG}; color: {INK}; border: 1px solid {ALERT_LINE}; "
            f"border-radius: 10px; padding: 12px 16px; "
            f"font-size: {int(self.font_size * 0.55)}px; font-weight: 600;"
        )
        self.alert_label.hide()
        left.addWidget(self.alert_label)
        body.addLayout(left, stretch=1)

        # 오른쪽 열: 방향 다이얼 박스(제목 + 다이얼) — 위에 붙이고 아래는 여백
        dial_box = QFrame()
        dial_box.setFixedWidth(260)
        dial_box.setStyleSheet(
            f"background: {BOX_BG}; border: 1px solid {LINE}; border-radius: 12px;"
        )
        dial_layout = QVBoxLayout(dial_box)
        dial_layout.setContentsMargins(14, 12, 14, 14)
        dial_title = QLabel("화자 방향 (누가, 어디서)")
        dial_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dial_title.setStyleSheet(
            f"color: {NAVY}; font-weight: 700; font-size: {int(self.font_size * 0.42)}px; border: none;"
        )
        dial_layout.addWidget(dial_title)
        self.dial = DirectionDial()
        dial_layout.addWidget(self.dial)

        right = QVBoxLayout()
        right.addWidget(dial_box)
        right.addStretch()
        body.addLayout(right)

        root.addLayout(body, stretch=1)

        # ── 아래: 양방향 말하기 입력 ──
        speak_wrap = QVBoxLayout()
        speak_wrap.setContentsMargins(28, 0, 28, 24)
        speak_wrap.setSpacing(8)
        speak_title = QLabel("양방향 말하기 (입력 → 스피커)")
        speak_title.setStyleSheet(
            f"color: {NAVY}; font-weight: 700; font-size: {int(self.font_size * 0.42)}px;"
        )
        speak_wrap.addWidget(speak_title)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("여기에 입력하고 Enter를 누르면 스피커가 대신 말합니다")
        self.input_box.setStyleSheet(
            f"color: {INK}; background: #FFFFFF; border: 1px solid {LINE}; "
            f"border-radius: 8px; padding: 12px; font-size: {int(self.font_size * 0.5)}px;"
        )
        self.input_box.returnPressed.connect(self._on_enter)
        input_row.addWidget(self.input_box, stretch=1)

        self.speak_button = QPushButton("말하기 ▶")
        self.speak_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.speak_button.setStyleSheet(
            f"background: {GREEN}; color: #FFFFFF; border: none; border-radius: 8px; "
            f"padding: 12px 22px; font-size: {int(self.font_size * 0.5)}px; font-weight: 700;"
        )
        self.speak_button.clicked.connect(self._on_enter)   # 버튼도 Enter와 같은 동작
        input_row.addWidget(self.speak_button)
        speak_wrap.addLayout(input_row)
        root.addLayout(speak_wrap)

        # 전체화면에서 빠져나올 방법(ESC). 없으면 창을 못 닫고 갇힌다.
        QShortcut(QKeySequence("Escape"), self.window, activated=self.window.close)

        self._caption_arrived.connect(self._update)

        # 알림 박스: 시그널로 받고, 4초 뒤 자동으로 숨긴다(타이머는 메인 스레드에서 만든다).
        self._alert_arrived.connect(self._show_alert)
        self._alert_timer = QTimer()
        self._alert_timer.setSingleShot(True)
        self._alert_timer.timeout.connect(self.alert_label.hide)

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

    @Slot(str)
    def _show_alert(self, text: str) -> None:
        """메인 스레드에서 실행: 소리 알림 박스를 띄우고 4초 뒤 자동으로 숨긴다."""
        self.alert_label.setText("🔔 소리 알림\n" + text)
        self.alert_label.show()
        self._alert_timer.start(4000)

    def show_alert(self, label: str, confidence: float = 1.0) -> None:
        """소리 이벤트 알림(이름 호명 등)을 소리 알림 박스로 잠깐 띄운다.

        어느 스레드에서 불려도 안전하도록 시그널로만 넘긴다(자막과 같은 방식).
        """
        self._alert_arrived.emit(label)

    def _on_enter(self) -> None:
        """입력칸 Enter / '말하기' 버튼: 내용을 on_speak 로 넘겨 발화하고 칸을 비운다.

        on_speak(=TTS)는 소리를 내는 동안 시간이 걸릴 수 있어 별도 스레드에서
        부른다. 안 그러면 발화하는 동안 화면이 멈춘다.
        """
        text = self.input_box.text().strip()
        if not text:
            return
        self.input_box.clear()
        threading.Thread(target=self.on_speak, args=(text,), daemon=True).start()

    def run(self) -> None:
        """전체화면으로 띄우고 이벤트 루프를 돈다. (ESC로 종료)"""
        self.window.showFullScreen()
        self.app.exec()


# ---------------------------------------------------------------------------
# 자체 테스트: 창을 띄우고 1.5초마다 가짜 자막+방향을 흘려 넣고, 한 번 소리 알림도 띄운다.
# 자막이 쌓이며 방향 화살표가 도는지, 알림 박스가 뜨는지 눈으로 확인한다. ESC로 종료.
#   실행(모니터가 연결된 데스크톱에서): python src/ui/app.py
# ---------------------------------------------------------------------------
def _selftest() -> None:
    from pathlib import Path

    import yaml
    from PySide6.QtCore import QTimer

    cfg = yaml.safe_load(open(Path(__file__).resolve().parents[1] / "config.yaml", encoding="utf-8"))
    ui = SoribomUI(cfg)

    # 입력 테스트용: on_speak 이 불리면 콘솔에 찍는다(실제 TTS는 주언 speaker.py).
    ui.on_speak = lambda text: print(f"[on_speak 호출됨] → TTS로 발화: {text}")

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
        if step["i"] == 2:
            ui.show_alert("도유 학생을 불렀어요")   # 알림 박스 확인
        step["i"] += 1

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(1500)

    ui.run()


if __name__ == "__main__":
    _selftest()
