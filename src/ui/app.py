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
import time
from pathlib import Path

from PySide6.QtCore import Qt, QObject, QPointF, QRectF, QTimer, Signal, Slot, QEvent
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPen, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QPlainTextEdit, QVBoxLayout, QWidget,
)

from summary.email_sender import NoteEmailError, validate_recipient

# 색 팔레트 두 벌 — 밝은 테마(목업)와 어두운 테마.
#
# 어두운 테마가 필요한 이유: 수업 중 교실 불을 끄고 영상·프로젝터를 볼 때
# 흰 배경 화면은 눈이 부셔 자막을 오래 못 본다. 실제로 쓰는 상황이라 넣었다.
#
# 어두운 색은 밝은 색을 기계적으로 뒤집은 게 아니라, 자막 글자(INK)와 배경의
# 차이가 가장 크게 나도록 따로 골랐다. 자막이 읽히는 게 이 화면의 전부다.
THEMES = {
    "light": {
        "NAVY": "#13315C",       # 헤더 배경·진한 강조
        "ACCENT": "#13315C",     # 페이지 위 강조 글자 (밝은 테마에선 헤더색과 같다)
        "PAGE_BG": "#F8FAFC",    # 페이지 배경
        "CARD_BG": "#FFFFFF",    # 입력칸·드롭다운처럼 글을 얹는 면
        "INK": "#1F2937",        # 본문 글자
        "MUTED": "#64748B",      # 보조 글자
        "LINE": "#C9D6E5",       # 옅은 테두리
        "BLUE": "#2563A8",       # 방향 화살표
        "GREEN": "#1B6B4C",      # 말하기 버튼
        "PILL_BG": "#BFE3D0",    # '수업 기록 보기' 버튼 배경
        "PILL_INK": "#1B6B4C",   # 그 버튼의 글자
        "BOX_BG": "#EFF3F8",     # 다이얼 박스 배경
        "ALERT_BG": "#FCEEE6",   # 소리 알림 배경
        "ALERT_LINE": "#C2410C", # 소리 알림 테두리·제목
    },
    "dark": {
        "NAVY": "#1B2942",       # 헤더는 페이지보다 살짝 밝게 — 경계가 보이게
        "ACCENT": "#A8C7EE",     # 어두운 배경에선 강조 글자가 '밝아야' 읽힌다
        "PAGE_BG": "#0F172A",
        "CARD_BG": "#1E293B",
        "INK": "#E8EEF7",        # 자막. 순백(#FFF)은 어두운 배경에서 번져 보여 살짝 낮췄다
        "MUTED": "#94A3B8",
        "LINE": "#33415C",
        "BLUE": "#5FA8E8",       # 화살표는 밝게 — 어두운 배경에서 진한 파랑은 안 보인다
        "GREEN": "#1F7A57",
        "PILL_BG": "#204E3C",
        "PILL_INK": "#9FE0C0",
        "BOX_BG": "#16233A",
        "ALERT_BG": "#3A2418",
        "ALERT_LINE": "#E4823F",
    },
}


def apply_theme(name: str) -> None:
    """테마 이름(light/dark)에 맞는 색을 아래 상수들에 채워 넣는다.

    화면을 만들기 '전에' 불러야 한다. 위젯은 만들어질 때 색을 한 번 읽어가므로,
    이미 떠 있는 화면의 색은 바뀌지 않는다(테마를 바꾸면 프로그램을 다시 켠다).
    화면 전체에서 색을 이 이름들로만 쓰기 때문에, 여기만 바꾸면 전부 따라 바뀐다.
    """
    global NAVY, ACCENT, PAGE_BG, CARD_BG, INK, MUTED, LINE, BLUE, GREEN
    global PILL_BG, PILL_INK, BOX_BG, ALERT_BG, ALERT_LINE

    colors = THEMES.get(name)
    if colors is None:            # 설정에 오타가 나도 화면은 떠야 한다
        print(f"[ui] 모르는 테마 '{name}' — 밝은 테마로 갑니다 (light 또는 dark)")
        colors = THEMES["light"]

    NAVY = colors["NAVY"]
    ACCENT = colors["ACCENT"]
    PAGE_BG = colors["PAGE_BG"]
    CARD_BG = colors["CARD_BG"]
    INK = colors["INK"]
    MUTED = colors["MUTED"]
    LINE = colors["LINE"]
    BLUE = colors["BLUE"]
    GREEN = colors["GREEN"]
    PILL_BG = colors["PILL_BG"]
    PILL_INK = colors["PILL_INK"]
    BOX_BG = colors["BOX_BG"]
    ALERT_BG = colors["ALERT_BG"]
    ALERT_LINE = colors["ALERT_LINE"]


# 처음엔 밝은 테마. 실제 테마는 SoribomUI 가 config 를 읽어 다시 정한다.
apply_theme("light")


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
        p.setBrush(QColor(ACCENT))
        p.drawEllipse(QPointF(cx, cy), 6, 6)


class NoteEmailDialog(QDialog):
    """기록을 고정해서 보내고, 네트워크 대기 중에도 자막 처리는 계속한다."""

    _finished = Signal(bool, str)

    def __init__(self, parent, transcript: str, on_send, styles: dict) -> None:
        super().__init__(parent)
        self.transcript = transcript
        self.on_send = on_send
        self.sending = False
        self.setWindowTitle("노트 보내기")
        self.setMinimumSize(760, 580)
        self.setStyleSheet(f"background: {PAGE_BG}; color: {INK}; font-size: 18px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(QLabel("받는 이메일 주소"))
        self.recipient = QLineEdit()
        self.recipient.setPlaceholderText("student@gmail.com")
        self.recipient.setStyleSheet(styles["input"])
        self.recipient.setMaxLength(254)
        layout.addWidget(self.recipient)
        layout.addWidget(QLabel("창을 연 시점까지의 수업 기록 · 메일 본문과 TXT 첨부로 전송"))
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlainText(transcript or "아직 보낼 수업 기록이 없습니다.")
        self.preview.setStyleSheet(
            f"background: {CARD_BG}; color: {INK}; border: 1px solid {LINE}; padding: 12px;"
        )
        layout.addWidget(self.preview, stretch=1)
        self.status = QLabel("이메일 전송에는 인터넷이 필요합니다.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        row.addStretch()
        self.send_button = QPushButton("보내기")
        self.send_button.setStyleSheet(styles["speak_button"])
        self.send_button.setEnabled(bool(transcript.strip()))
        self.send_button.setAutoDefault(False)
        self.send_button.clicked.connect(self._send)
        self.close_button = QPushButton("닫기")
        self.close_button.setStyleSheet(styles["summary_button"])
        self.close_button.setAutoDefault(False)
        self.close_button.clicked.connect(self.reject)
        row.addWidget(self.send_button)
        row.addWidget(self.close_button)
        layout.addLayout(row)
        self._finished.connect(self._show_result)

    def _send(self) -> None:
        if self.sending or not self.send_button.isEnabled():
            return
        try:
            recipient = validate_recipient(self.recipient.text())
        except NoteEmailError as e:
            self.status.setText(str(e))
            return
        self.recipient.setText(recipient)
        self.sending = True
        self.recipient.setEnabled(False)
        self.send_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self.status.setText("메일 전송 중입니다. 잠시 기다려주세요.")

        def send() -> None:
            try:
                self.on_send(recipient, self.transcript)
            except NoteEmailError as e:
                self._finished.emit(False, str(e))
            except Exception:
                # 서버 응답에는 주소나 인증 정보가 들어갈 수 있어 그대로 표시하지 않는다.
                self._finished.emit(False, "전송 중 문제가 발생했습니다. 메일함에서 발송 여부를 확인해주세요.")
            else:
                self._finished.emit(True, "메일 서버에 전송했습니다. 받은편지함 또는 스팸함을 확인해주세요.")

        threading.Thread(target=send, daemon=True).start()

    @Slot(bool, str)
    def _show_result(self, success: bool, message: str) -> None:
        self.sending = False
        self.status.setText(message)
        self.close_button.setEnabled(True)
        # 성공 후 같은 창에서 연타로 다시 보내는 일은 막는다. 실패 시 주소·기록은 유지한다.
        self.recipient.setEnabled(not success)
        self.send_button.setEnabled(not success)

    def done(self, result: int) -> None:
        # ESC도 reject() → done()을 거친다. 전송 중 창을 없애면 결과를 전달할 수 없다.
        if not self.sending:
            super().done(result)

    def closeEvent(self, event) -> None:
        if self.sending:
            event.ignore()
        else:
            super().closeEvent(event)


class CaptionView(QPlainTextEdit):
    """창 크기에 맞춰 배치하며 최신 자막으로 자동 스크롤한다."""
    def __init__(self, history_blocks, history_characters=40000):
        super().__init__()
        self.history_characters = max(1, int(history_characters))
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setMaximumBlockCount(history_blocks)
        self.document().setDocumentMargin(0)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def text(self):
        return self.toPlainText()

    def setText(self, text):
        self.setPlainText(text)

    def append_caption(self, text, continue_paragraph=False):
        if continue_paragraph and not self.document().isEmpty():
            cursor = QTextCursor(self.document())
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(" " + text)
        else:
            self.appendPlainText(text)
        # 같은 방향의 발화가 한 문단에 계속 쌓여도 메모리 보관량은 제한한다.
        excess = self.document().characterCount() - 1 - self.history_characters
        if excess > 0:
            cursor = QTextCursor(self.document())
            cursor.setPosition(excess, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())


class SoribomUI(QObject):
    # 워커 스레드 → 메인 스레드로 (자막, 방향)을 안전하게 넘기는 통로.
    _caption_arrived = Signal(str, object, object)   # text, angle, 발화 시각 또는 None
    _alert_arrived = Signal(str)             # 소리 이벤트 알림(이름 호명 등)
    _devices_changed = Signal(str, str, str)
    _models_changed = Signal(bool, str)
    _speech_finished = Signal(bool, str)
    _notes_changed = Signal(bool, str)

    def __init__(self, cfg: dict) -> None:
        super().__init__()
        self.cfg = cfg
        self.on_speak = lambda text: None   # main 에서 Speaker.say 로 연결
        # '수업 요약 보기' 버튼이 부를 콜백. main 에서 NoteBuilder.build_summary 로 연결.
        self.on_summarize = lambda: "요약 기능이 연결되지 않았습니다."
        # 과목 드롭다운이 부를 콜백. main 에서 Transcriber.set_subject 로 연결.
        self.on_subject_change = lambda subject: None
        self.on_note_snapshot = lambda: ""
        self.on_send_note = self._email_not_connected
        self._email_dialog = None
        self.on_reconnect = lambda: None
        self.on_caption_layout = lambda **values: None
        self.on_retry_models = lambda: None
        self._device_state = ("preparing", "waiting", "")
        self._models_ready = True
        self.startup_window = None
        self._running = False
        self._speaking = False
        self._speech_failed = False
        self._note_failed = False
        self._speech_text = ""

        ui = cfg.get("ui", {})
        self.font_size = ui.get("font_size", 36)
        # 화면 줄 수는 창 크기와 폰트에 맡긴다. 이 제한은 메모리 보관량이다.
        self.max_lines = max(20, int(ui.get("caption_history_blocks", 200)))
        self._lines = []                    # 화면에 남길 최근 자막 줄들

        # 대화가 한참 끊겼다 다시 시작되면 자막 사이에 빈 줄을 하나 넣는다.
        # (엔터를 두 번 친 것과 같은 간격) 쉬는 시간과 수업이 한 덩어리로 붙어 보이면
        # 어디까지가 방금 대화인지 알기 어렵다. 묶음을 눈으로 나눠 준다.
        self.gap_seconds = ui.get("gap_seconds", 30)
        self.caption_pause_break_seconds = max(0.1, float(ui.get("caption_pause_break_seconds", 2)))
        self._last_caption_at = None        # 마지막 자막이 뜬 시각 (없으면 아직 첫 자막)
        self._last_speech_timing = None     # (음성 끝 시각, 연결 세대)
        self._last_caption_angle = None
        self.caption_direction_break_degrees = max(
            0.1, min(180.0, float(ui.get("caption_direction_break_degrees", 5))))

        # 색 테마를 여기서 정한다. 아래에서 위젯을 만들 때 이 색을 읽어가므로
        # 반드시 위젯보다 '먼저' 불러야 한다.
        self.theme = ui.get("theme", "light")
        apply_theme(self.theme)
        style = self._styles()      # 지금 테마의 스타일 문자열 묶음

        # QApplication 은 프로그램당 하나. 이미 있으면 그걸 쓰고 없으면 만든다.
        self.app = QApplication.instance() or QApplication([])
        icon_path = Path(__file__).resolve().parents[2] / "assets" / "soribom-logo.png"
        self.app.setWindowIcon(QIcon(str(icon_path)))

        self.window = QWidget()
        self.window.installEventFilter(self)
        self.window.setStyleSheet(style["window"])
        root = QVBoxLayout(self.window)
        root.setContentsMargins(0, 0, 0, 0)   # 헤더가 화면 끝까지 닿게
        root.setSpacing(0)

        # ── 헤더(네이비): 왼쪽 제목 '소리봄' + 오른쪽 '수업 요약 보기' 버튼 ──
        self.header = QWidget()
        self.header.setStyleSheet(style["header"])
        header_row = QHBoxLayout(self.header)
        header_row.setContentsMargins(28, 12, 20, 12)
        self.title = QLabel("소리봄")
        self.title.setStyleSheet(style["title"])
        header_row.addWidget(self.title)
        header_row.addStretch()

        # 과목 선택 드롭다운 — 바꾸면 그 과목 용어로 STT 편향 전환.
        from stt.vocab import SUBJECTS, SUBJECT_LABELS
        self.subj_label = QLabel("과목")
        self.subj_label.setStyleSheet(style["subj_label"])
        header_row.addWidget(self.subj_label)
        self.subject_box = QComboBox()
        self._subject_keys = SUBJECTS
        for key in SUBJECTS:
            self.subject_box.addItem(SUBJECT_LABELS[key], key)
        # 시작 과목을 config 값에 맞춘다.
        start_subject = cfg.get("stt", {}).get("subject", "science")
        if start_subject in SUBJECTS:
            self.subject_box.setCurrentIndex(SUBJECTS.index(start_subject))
        # 글자가 '...'로 잘리지 않게 최소 폭을 넉넉히 주고, 내용에 맞춰 넓힌다.
        self.subject_box.setMinimumWidth(int(self.font_size * 3.6))
        self.subject_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.subject_box.setStyleSheet(style["subject_box"])
        self.subject_box.currentIndexChanged.connect(self._on_subject_changed)
        header_row.addWidget(self.subject_box)

        self.summary_button = QPushButton("수업 기록 보기")
        self.summary_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.summary_button.setStyleSheet(style["summary_button"])
        self.summary_button.clicked.connect(self._show_summary)
        header_row.addWidget(self.summary_button)
        self.email_button = QPushButton("노트 보내기")
        self.email_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.email_button.setStyleSheet(style["summary_button"])
        self.email_button.clicked.connect(self._show_email)
        header_row.addWidget(self.email_button)
        root.addWidget(self.header)

        self.connection_bar = QFrame()
        # 정상/오류 문구의 줄 수가 달라도 자막 위치가 위아래로 튀지 않게 한다.
        self.connection_bar.setMinimumHeight(int(self.font_size * 2))
        connection_row = QHBoxLayout(self.connection_bar)
        connection_row.setContentsMargins(28, 10, 28, 10)
        self.connection_label = QLabel("마이크 연결 확인 중 · 방향 연결 확인 중")
        self.connection_label.setWordWrap(True)
        connection_row.addWidget(self.connection_label, stretch=1)
        self.reconnect_button = QPushButton("다시 연결")
        self.reconnect_button.setMinimumHeight(44)
        self.reconnect_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reconnect_button.clicked.connect(self._reconnect)
        connection_row.addWidget(self.reconnect_button)
        root.addWidget(self.connection_bar)
        self.note_status = QLabel("수업 기록 자동 저장 대기 중" if cfg.get("summary", {}).get("enabled", True) else "수업 기록 파일 저장 꺼짐")
        self.note_status.setWordWrap(True)
        self.note_status.setContentsMargins(28, 4, 28, 4)
        root.addWidget(self.note_status)

        # ── 본문: 왼쪽 자막 + 오른쪽 방향 박스 ──
        body = QHBoxLayout()
        body.setContentsMargins(28, 22, 28, 10)
        body.setSpacing(20)

        # 왼쪽 열: 자막(위로 쌓임) + 소리 알림 박스(아래, 평소 숨김)
        left = QVBoxLayout()
        left.setSpacing(12)
        self.caption_label = CaptionView(
            self.max_lines, ui.get("caption_history_characters", 40000))
        self.caption_label.setText("마이크 연결을 확인하고 있습니다.")
        self.caption_label.setStyleSheet(style["caption"])
        left.addWidget(self.caption_label, stretch=1)

        # 소리 알림 박스(이름 호명). 입력칸을 밀지 않도록 자막 아래(본문 안)에 둔다.
        self.alert_label = QLabel("")
        self.alert_label.setWordWrap(True)
        self.alert_label.setStyleSheet(style["alert"])
        self.alert_label.hide()
        left.addWidget(self.alert_label)
        body.addLayout(left, stretch=1)

        # 오른쪽 열: 방향 다이얼 박스(제목 + 다이얼) — 위에 붙이고 아래는 여백
        self.dial_box = QFrame()
        self.dial_box.setFixedWidth(260)
        self.dial_box.setStyleSheet(style["dial_box"])
        dial_layout = QVBoxLayout(self.dial_box)
        dial_layout.setContentsMargins(14, 12, 14, 14)
        self.dial_title = QLabel("화자 방향")
        self.dial_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dial_title.setStyleSheet(style["dial_title"])
        dial_layout.addWidget(self.dial_title)
        self.dial = DirectionDial()
        dial_layout.addWidget(self.dial)

        # 다이얼 바로 아래 작은 테마 버튼. 교실 조명은 수업 중에 바뀌므로
        # (영상 볼 때 소등) 설정 파일이 아니라 화면에서 바로 누를 수 있어야 한다.
        # 자막이 주인공이라 눈에 띄지 않게 작고 흐리게 둔다.
        self.theme_button = QPushButton(self._theme_button_text())
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.setStyleSheet(style["theme_button"])
        self.theme_button.clicked.connect(self._toggle_theme)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(self.dial_box)
        right.addWidget(self.theme_button, alignment=Qt.AlignmentFlag.AlignRight)
        right.addStretch()
        body.addLayout(right)

        root.addLayout(body, stretch=1)

        # ── 아래: 양방향 말하기 입력 ──
        speak_wrap = QVBoxLayout()
        speak_wrap.setContentsMargins(28, 0, 28, 24)
        speak_wrap.setSpacing(8)
        self.speak_title = QLabel("양방향 말하기 (입력 → 스피커)")
        self.speak_title.setStyleSheet(style["speak_title"])
        speak_wrap.addWidget(self.speak_title)
        self.speech_status = QLabel("")
        self.speech_status.setWordWrap(True)
        speak_wrap.addWidget(self.speech_status)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("여기에 입력하고 Enter를 누르면 스피커가 대신 말합니다")
        self.input_box.setStyleSheet(style["input"])
        self.input_box.returnPressed.connect(self._on_enter)
        input_row.addWidget(self.input_box, stretch=1)

        self.speak_button = QPushButton("말하기 ▶")
        self.speak_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.speak_button.setStyleSheet(style["speak_button"])
        self.speak_button.clicked.connect(self._on_enter)   # 버튼도 Enter와 같은 동작
        input_row.addWidget(self.speak_button)
        speak_wrap.addLayout(input_row)
        root.addLayout(speak_wrap)

        # 전체화면에서 빠져나올 방법(ESC). 없으면 창을 못 닫고 갇힌다.
        QShortcut(QKeySequence("Escape"), self.window, activated=self.window.close)

        self._caption_arrived.connect(self._update)
        self._devices_changed.connect(self._update_devices)
        self._models_changed.connect(self._update_models)
        self._speech_finished.connect(self._finish_speech)
        self._notes_changed.connect(self._update_note_status)
        self._render_operation_status()
        self._render_connection()

        # 알림 박스: 시그널로 받고, 4초 뒤 자동으로 숨긴다(타이머는 메인 스레드에서 만든다).
        self._alert_arrived.connect(self._show_alert)
        self._alert_timer = QTimer()
        self._alert_timer.setSingleShot(True)
        self._alert_timer.timeout.connect(self.alert_label.hide)

    def _styles(self) -> dict:
        """지금 테마 색으로 위젯별 스타일 문자열을 한 번에 만든다.

        화면을 처음 만들 때와 테마를 바꿀 때 '같은' 문자열을 써야 한다. 두 군데에
        나눠 적으면 한쪽만 고쳐져 색이 어긋나므로, 여기 한곳에만 적는다.
        """
        f = self.font_size
        return {
            "window": f"background-color: {PAGE_BG};",
            "header": f"background: {NAVY};",
            # 헤더는 두 테마 모두 어두우므로 그 위 글자는 흰색으로 고정한다.
            "title": f"color: #FFFFFF; font-weight: 800; font-size: {int(f * 0.7)}px;",
            "subj_label": f"color: #CBD5E1; font-size: {int(f * 0.4)}px; font-weight: 600;",
            "subject_box": (
                f"QComboBox {{ background: {CARD_BG}; color: {INK}; border: 1px solid {LINE}; "
                f"border-radius: 8px; padding: 6px 32px 6px 12px; min-width: {int(f * 2.6)}px; "
                f"font-size: {int(f * 0.42)}px; }}"
                f"QComboBox::drop-down {{ width: 26px; border: none; }}"
                f"QComboBox QAbstractItemView {{ background: {CARD_BG}; color: {INK}; "
                f"selection-background-color: {PILL_BG}; selection-color: {PILL_INK}; "
                f"font-size: {int(f * 0.42)}px; outline: none; }}"
            ),
            "summary_button": (
                f"background: {PILL_BG}; color: {PILL_INK}; border: none; border-radius: 13px; "
                f"padding: 8px 18px; font-size: {int(f * 0.42)}px; font-weight: 700;"
            ),
            "caption": f"color: {INK}; font-size: {f}px; font-weight: 600; background: transparent; border: none; padding: 0;",
            "alert": (
                f"background: {ALERT_BG}; color: {INK}; border: 1px solid {ALERT_LINE}; "
                f"border-radius: 10px; padding: 12px 16px; "
                f"font-size: {int(f * 0.55)}px; font-weight: 600;"
            ),
            "dial_box": f"background: {BOX_BG}; border: 1px solid {LINE}; border-radius: 12px;",
            "dial_title": (
                f"color: {ACCENT}; font-weight: 700; font-size: {int(f * 0.42)}px; border: none;"
            ),
            # 작게 두되 터치로 누를 수 있는 크기는 지킨다(15.6" 터치 모니터).
            "theme_button": (
                f"QPushButton {{ background: transparent; color: {MUTED}; "
                f"border: 1px solid {LINE}; border-radius: 9px; padding: 8px 14px; "
                f"font-size: {int(f * 0.34)}px; }}"
                f"QPushButton:hover {{ color: {ACCENT}; border-color: {ACCENT}; }}"
            ),
            "speak_title": f"color: {ACCENT}; font-weight: 700; font-size: {int(f * 0.42)}px;",
            "input": (
                f"color: {INK}; background: {CARD_BG}; border: 1px solid {LINE}; "
                f"border-radius: 8px; padding: 12px; font-size: {int(f * 0.5)}px;"
            ),
            "speak_button": (
                f"background: {GREEN}; color: #FFFFFF; border: none; border-radius: 8px; "
                f"padding: 12px 22px; font-size: {int(f * 0.5)}px; font-weight: 700;"
            ),
        }

    def _theme_button_text(self) -> str:
        """버튼에는 '지금 상태'가 아니라 '누르면 되는 것'을 적는다(그래야 안 헷갈린다)."""
        if self.theme == "dark":
            return "☀ 밝은 화면"
        return "🌙 어두운 화면"

    def _toggle_theme(self) -> None:
        """다이얼 아래 작은 버튼: 밝은 화면 ↔ 어두운 화면을 그 자리에서 바꾼다."""
        self.theme = "dark" if self.theme == "light" else "light"
        apply_theme(self.theme)
        self.theme_button.setText(self._theme_button_text())
        self._repaint_theme()

    def _repaint_theme(self) -> None:
        """이미 떠 있는 화면에 지금 테마 색을 다시 입힌다.

        위젯은 만들어질 때 색을 한 번 읽어갈 뿐이라, 색만 바꾸면 화면은 그대로다.
        그래서 스타일을 다시 만들어 위젯마다 넣어 준다. 새로 만든 위젯이 있으면
        여기에도 한 줄 추가해야 한다(안 하면 그 위젯만 옛 색으로 남는다).
        """
        style = self._styles()
        self.window.setStyleSheet(style["window"])
        self.header.setStyleSheet(style["header"])
        self.title.setStyleSheet(style["title"])
        self.subj_label.setStyleSheet(style["subj_label"])
        self.subject_box.setStyleSheet(style["subject_box"])
        self.summary_button.setStyleSheet(style["summary_button"])
        self.email_button.setStyleSheet(style["summary_button"])
        self._render_connection()
        self.caption_label.setStyleSheet(style["caption"])
        self.alert_label.setStyleSheet(style["alert"])
        self.dial_box.setStyleSheet(style["dial_box"])
        self.dial_title.setStyleSheet(style["dial_title"])
        self.theme_button.setStyleSheet(style["theme_button"])
        self.speak_title.setStyleSheet(style["speak_title"])
        self.input_box.setStyleSheet(style["input"])
        self.speak_button.setStyleSheet(style["speak_button"])
        self._render_operation_status()
        self.dial.update()      # 다이얼은 직접 그리는 위젯이라 '다시 그려라'만 알려주면 된다

    @Slot(str, object, object)
    def _update(self, text: str, angle, timing=None) -> None:
        """메인 스레드에서 실행: 자막과 방향을 화면에 반영한다."""
        # 장치가 끊겼거나 방향 표본이 없으면 이전 화자의 문단에 묶지 않는다.
        if (self._device_state[:2] != ("ready", "ready")
                or not isinstance(angle, (int, float)) or not math.isfinite(angle)):
            angle = None
        else:
            angle %= 360
        now = time.monotonic()
        pause_seconds = None
        pause_source = "unknown"
        generation_changed = False
        if timing is not None:
            begin, end, generation = timing
            if self._last_speech_timing is not None:
                previous_end, previous_generation = self._last_speech_timing
                generation_changed = generation != previous_generation
                if not generation_changed:
                    pause_seconds = max(0.0, begin - previous_end)
                    pause_source = "audio"
                    end = max(end, previous_end)
            # 필터 뒤 빈 자막도 실제 음성이 있었던 시각으로 취급한다.
            self._last_speech_timing = (end, generation)
        else:
            # 시각이 없는 데모 호출만 표시 간격을 사용하며 음성 시각과 섞지 않는다.
            if self._last_speech_timing is None and self._last_caption_at is not None:
                pause_seconds = max(0.0, now - self._last_caption_at)
                pause_source = "display"
            self._last_speech_timing = None
        if text:
            first_caption = not self._lines
            if not self._lines:
                self.caption_label.clear()
            # 앞 자막과 gap_seconds 이상 떨어져 있으면 빈 줄로 묶음을 나눈다.
            gap = pause_seconds is not None and pause_seconds >= self.gap_seconds
            pause_break = (gap or pause_seconds is not None
                           and pause_seconds >= self.caption_pause_break_seconds)
            difference = None
            if not generation_changed and angle is not None and self._last_caption_angle is not None:
                difference = abs((angle - self._last_caption_angle + 180) % 360 - 180)
            continue_paragraph = (not pause_break and difference is not None
                                  and difference < self.caption_direction_break_degrees)
            reason = ("first" if first_caption else "pause" if pause_break else
                      "unknown" if difference is None else
                      "same_direction" if continue_paragraph else "direction_change")
            self.on_caption_layout(
                direction_angle=angle, direction_difference=difference,
                direction_threshold=self.caption_direction_break_degrees,
                paragraph_break=not continue_paragraph, layout_reason=reason,
                pause_s=pause_seconds, pause_source=pause_source)
            if gap:
                self._lines.append("")
            self._last_caption_at = now
            self._last_caption_angle = angle

            self._lines.append(text)
            self._lines = self._lines[-self.max_lines:]
            # 줄 수를 자르다 보면 빈 줄이 맨 위에 남을 수 있다. 위쪽에 어색한
            # 여백만 만들 뿐이라 버린다.
            while self._lines and self._lines[0] == "":
                self._lines.pop(0)
            self.caption_label.append_caption(
                ("\n" if gap else "") + text, continue_paragraph=continue_paragraph)
        self.dial.set_angle(angle if self._device_state[:2] == ("ready", "ready") else None)
        if self._device_state[:2] == ("ready", "ready"):
            self.dial_title.setText("화자 방향 (미확정)" if angle is None
                                    else f"화자 방향 · {angle:.1f}°")

    def show_device_status(self, microphone, direction, detail=""):
        self._devices_changed.emit(microphone, direction, detail)

    @Slot(str, str, str)
    def _update_devices(self, microphone, direction, detail):
        self._device_state = (microphone, direction, detail)
        if microphone != "ready" or direction != "ready":
            self.dial.set_angle(None)
            self._last_caption_angle = None
            self._last_speech_timing = None
        if not self._lines:
            self.caption_label.setText(
                "소리봄 준비 완료 — 말하면 자막이 나옵니다."
                if microphone == "ready" else "마이크 연결 후 새 자막이 표시됩니다."
            )
        self._render_connection()

    def _render_connection(self):
        mic, doa, detail = self._device_state
        if mic == "preparing":
            text = "◌ " + (detail or "소리봄 모델 준비 중입니다.")
        elif mic in ("failed", "model_failed"):
            text = "⚠ " + detail
        elif mic == "connecting":
            text = "◌ 마이크 연결 확인 중입니다. 잠시 기다려주세요."
        elif mic != "ready":
            text = ("⚠ 마이크 연결을 확인해주세요. 자동으로 다시 연결합니다.\n"
                    "연결이 끊긴 동안의 음성은 기록되지 않습니다.")
        else:
            direction = {
                "ready": "● 방향 사용 가능", "disabled": "방향 표시 꺼짐",
                "connecting": "◌ 방향 연결 확인 중", "waiting": "⚠ 방향 확인 불가 · 자동 재연결 중",
            }.get(doa, "방향 확인 불가")
            text = "● 마이크 연결됨    " + direction
        self.connection_label.setText(text)
        self.connection_label.setToolTip(detail)
        warning = mic in ("waiting", "failed", "model_failed") or (mic == "ready" and doa == "waiting")
        bg = ALERT_BG if warning else BOX_BG
        border = ALERT_LINE if warning else LINE
        self.connection_bar.setStyleSheet(f"background: {bg}; border-bottom: 1px solid {border};")
        self.connection_label.setStyleSheet(f"color: {INK}; border: none; font-size: {int(self.font_size * 0.48)}px;")
        self.reconnect_button.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; background: {CARD_BG}; border: 1px solid {LINE}; "
            f"border-radius: 8px; padding: 8px 18px; font-weight: 600; "
            f"font-size: {int(self.font_size * 0.5)}px; }}"
            f"QPushButton:disabled {{ color: {MUTED}; background: {BOX_BG}; }}"
        )
        connecting = mic in ("preparing", "connecting", "failed") or doa == "connecting"
        healthy = mic == "ready" and doa in ("ready", "disabled")
        self.reconnect_button.setVisible(not healthy)
        self.reconnect_button.setEnabled(not connecting)
        self.reconnect_button.setText("연결 확인 중…" if connecting and mic != "failed" else "다시 연결")
        if mic == "model_failed":
            self.reconnect_button.setText("모델 준비 재시도")
        self.dial_title.setText(("화자 방향 (미확정)" if self._lines and self.dial._angle is None
                                 else f"화자 방향 · {self.dial._angle:.1f}°" if self.dial._angle is not None
                                 else "화자 방향") if mic == doa == "ready"
                                else "방향 표시 꺼짐" if doa == "disabled" else "방향 확인 불가")

    def _reconnect(self):
        if self._device_state[0] == "model_failed":
            self._update_devices("preparing", "waiting", "모델 준비를 다시 시도합니다.")
            self.on_retry_models()
            return
        self.reconnect_button.setEnabled(False)
        self.reconnect_button.setText("연결 확인 중…")
        self.on_reconnect()

    def set_models_ready(self, ready, message=""):
        self._models_changed.emit(ready, message)

    @Slot(bool, str)
    def _update_models(self, ready, message):
        self._models_ready = ready
        self.speak_button.setEnabled(ready and not self._speaking)
        self.input_box.setEnabled(ready)
        self.subject_box.setEnabled(ready)
        if not ready:
            self._update_devices("preparing", "waiting", message)
        elif self.startup_window is not None and self._running:
            self.window.showFullScreen()
            self.startup_window.finish()

    def show_caption(self, text: str, angle: float = None, tentative: bool = False,
                     *, speech_ranges=None, generation=None) -> None:
        """자막과 화자 방향을 화면에 띄운다. (tentative는 단일패스라 안 씀)

        어느 스레드에서 불려도 안전하도록 시그널로만 넘긴다.
        """
        timing = None
        if speech_ranges:
            begin, end = speech_ranges[0][0], speech_ranges[-1][1]
            if (isinstance(begin, (int, float)) and isinstance(end, (int, float))
                    and math.isfinite(begin) and math.isfinite(end) and end >= begin):
                timing = (begin, end, generation)
        self._caption_arrived.emit(text, angle, timing)

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

    def _on_subject_changed(self, index: int) -> None:
        """과목 드롭다운 변경: 선택 과목 키를 콜백으로 넘겨 STT 용어를 바꾼다."""
        key = self.subject_box.itemData(index)
        if key:
            self.on_subject_change(key)

    def _show_summary(self) -> None:
        """'수업 기록 보기' 버튼: 지금까지의 전체 발화 기록을 팝업 패널로 보여준다."""
        try:
            text = self.on_summarize()
        except Exception as e:                     # 기록 생성 실패해도 앱은 죽지 않게
            text = f"수업 기록을 만들지 못했습니다: {e}"

        dlg = QDialog(self.window)
        dlg.setWindowTitle("수업 기록")
        dlg.setMinimumSize(760, 520)
        dlg.setStyleSheet(f"background: {PAGE_BG};")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        head = QLabel("📄 수업 기록")
        head.setStyleSheet(
            f"color: {ACCENT}; font-weight: 800; font-size: {int(self.font_size * 0.6)}px;"
        )
        lay.addWidget(head)

        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        view.setStyleSheet(
            f"color: {INK}; background: {CARD_BG}; border: 1px solid {LINE}; "
            f"border-radius: 10px; padding: 14px; font-size: {int(self.font_size * 0.5)}px;"
        )
        lay.addWidget(view, stretch=1)

        close_btn = QPushButton("닫기")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"background: {NAVY}; color: #FFFFFF; border: none; border-radius: 8px; "
            f"padding: 10px 24px; font-size: {int(self.font_size * 0.45)}px; font-weight: 700;"
        )
        close_btn.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        dlg.exec()

    @staticmethod
    def _email_not_connected(recipient: str, transcript: str) -> None:
        raise NoteEmailError("메일 발송 기능이 연결되지 않았습니다.")

    def eventFilter(self, watched, event) -> bool:
        # Qt가 위젯을 정리하는 동안에는 Python 속성이 먼저 사라질 수 있다.
        dialog = getattr(self, "_email_dialog", None)
        if (watched is getattr(self, "window", None) and event.type() == QEvent.Type.Close
                and dialog is not None and dialog.sending):
            event.ignore()
            return True
        return super().eventFilter(watched, event)

    def _show_email(self) -> None:
        try:
            transcript = self.on_note_snapshot()
        except Exception:
            self.show_alert("수업 기록을 불러오지 못했습니다. 다시 시도해주세요.")
            return
        dialog = NoteEmailDialog(self.window, transcript, self.on_send_note, self._styles())
        self._email_dialog = dialog
        try:
            dialog.exec()
        finally:
            self._email_dialog = None
            dialog.deleteLater()

    def _render_operation_status(self):
        normal = INK
        warning = "#FCA5A5" if self.theme == "dark" else "#B91C1C"
        size = int(self.font_size * 0.42)
        self.note_status.setStyleSheet(f"color: {warning if self._note_failed else normal}; font-size: {size}px;")
        self.speech_status.setStyleSheet(f"color: {warning if self._speech_failed else normal}; font-size: {size}px;")

    def show_note_status(self, success, message):
        self._notes_changed.emit(success, message)

    @Slot(bool, str)
    def _update_note_status(self, success, message):
        self._note_failed = not success
        self.note_status.setText(message)
        self._render_operation_status()

    def _on_enter(self) -> None:
        """합성·재생은 한 번에 하나만. 성공한 문장만 입력칸에서 지운다."""
        if not self._models_ready or self._speaking:
            return
        text = self.input_box.text().strip()
        if not text:
            return
        limit = self.cfg.get("tts", {}).get("max_chars", 200)
        if len(text) > limit:
            self._speech_failed = True
            self.speech_status.setText(f"한 번에 {limit}자까지 말할 수 있습니다. 문장을 나눠주세요.")
            self._render_operation_status()
            return
        self._speaking = True
        self._speech_text = text
        self._speech_failed = False
        self.speak_button.setEnabled(False)
        self.input_box.setEnabled(True)
        self.speak_button.setText("말하는 중…")
        self.speech_status.setText("말하기가 끝나면 보관한 음성을 인식합니다. 다음 문장을 입력할 수 있습니다.")
        self._render_operation_status()

        def speak():
            try:
                self.on_speak(text)
            except Exception as exc:
                print(f"[말하기] 실패: {exc}", flush=True)
                if type(exc).__name__ == "SpeechSynthesisError":
                    message = "음성 합성에 실패했습니다. 다시 시도해주세요. 입력은 남아 있습니다."
                else:
                    message = "말하기에 실패했습니다. 스피커 연결과 출력 장치를 확인한 뒤 다시 눌러주세요. 입력은 남아 있습니다."
                self._speech_finished.emit(False, message)
            else:
                self._speech_finished.emit(True, "말하기 완료")

        threading.Thread(target=speak, name="speech-playback", daemon=True).start()

    @Slot(bool, str)
    def _finish_speech(self, success, message):
        self._speaking = False
        self._speech_failed = not success
        if success and self.input_box.text().strip() == self._speech_text:
            self.input_box.clear()
        self.speak_button.setText("말하기 ▶")
        self.speak_button.setEnabled(self._models_ready)
        self.input_box.setEnabled(self._models_ready)
        self.speech_status.setText(message)
        self._render_operation_status()
        self.input_box.setFocus()

    def run(self) -> None:
        """전체화면으로 띄우고 이벤트 루프를 돈다. (ESC로 종료)"""
        self._running = True
        if self.startup_window is None or self._models_ready:
            self.window.showFullScreen()
            if self.startup_window is not None:
                self.startup_window.finish()
        self.app.exec()


# ---------------------------------------------------------------------------
# 자체 테스트: 창을 띄우고 1.5초마다 가짜 자막+방향을 흘려 넣고, 한 번 소리 알림도 띄운다.
# 자막이 쌓이며 방향 화살표가 도는지, 알림 박스가 뜨는지 눈으로 확인한다. ESC로 종료.
#   실행(모니터가 연결된 데스크톱에서): python src/ui/app.py
# ---------------------------------------------------------------------------
def _selftest() -> None:
    import sys
    from pathlib import Path

    # 단독 실행(python ui/app.py) 시에도 stt.vocab 등을 찾도록 src 를 경로에 넣는다.
    #   (main.py 로 통합 실행할 땐 이미 src 가 경로에 있다.)
    src_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(src_dir))

    import yaml
    from PySide6.QtCore import QTimer

    cfg = yaml.safe_load(open(src_dir / "config.yaml", encoding="utf-8"))
    ui = SoribomUI(cfg)
    ui.show_device_status("ready", "ready")

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
