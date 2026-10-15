"""로고 색상을 사용한 중앙 준비 화면. 단계 수는 진행률이나 남은 시간을 뜻하지 않는다."""
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout


STAGES = ["실행 준비", "음성 구간 감지 준비", "음성인식 모델 준비",
          "음성인식 첫 실행 준비", "말하기 모델 준비", "말하기 첫 실행 준비", "장치 연결 시작"]


class LoadingWindow(QDialog):
    _stage = Signal(int, str)
    _failure = Signal(str)

    def __init__(self):
        super().__init__()
        self.on_retry = lambda: None
        self._finished = False
        self.setWindowTitle("소리봄 시작")
        self.setFixedSize(540, 510)
        self.setStyleSheet("""
            QDialog { background: #F5FBFF; }
            QLabel { color: #13315C; font-size: 17px; }
            QPushButton { background: #D7F0DB; color: #185D49; border: 0;
                          border-radius: 10px; padding: 10px 22px; font-size: 16px; }
            QProgressBar { background: #DDECF7; border: 0; border-radius: 7px; height: 14px; }
            QProgressBar::chunk { background: #20A9D5; border-radius: 7px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 25, 40, 26)
        layout.setSpacing(13)
        logo = Path(__file__).resolve().parents[2] / "assets/soribom-logo.png"
        self.setWindowIcon(QIcon(str(logo)))
        image = QLabel()
        image.setPixmap(QPixmap(str(logo)).scaled(210, 210, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        image.setAlignment(Qt.AlignCenter)
        layout.addWidget(image)
        self.heading = QLabel("소리봄을 준비하고 있어요")
        self.heading.setStyleSheet("font-size: 24px; font-weight: 700;")
        self.heading.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.heading)
        self.status = QLabel(STAGES[0])
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.detail = QLabel("잠시만 기다려 주세요.")
        self.detail.setAlignment(Qt.AlignCenter)
        self.detail.setStyleSheet("color: #64748B; font-size: 14px;")
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        buttons = QHBoxLayout()
        self.retry = QPushButton("다시 준비하기")
        self.retry.hide()
        self.retry.clicked.connect(lambda: self.on_retry())
        buttons.addWidget(self.retry)
        cancel = QPushButton("종료")
        cancel.clicked.connect(QApplication.instance().quit)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        self._stage.connect(self._show_stage)
        self._failure.connect(self._show_failure)

    def show_centered(self):
        screen = QApplication.primaryScreen()
        if screen:
            self.move(screen.availableGeometry().center() - self.rect().center())
        self.show()

    def set_stage(self, index, detail=""):
        self._stage.emit(index, detail)

    @Slot(int, str)
    def _show_stage(self, index, detail):
        self.heading.setText("소리봄을 준비하고 있어요")
        self.status.setText(f"{index + 1}/{len(STAGES)} · {STAGES[index]}")
        self.detail.setText(detail or "단계마다 준비 시간이 다를 수 있습니다.")
        self.retry.hide()
        self.progress.setRange(0, 0)

    def fail(self, message):
        self._failure.emit(message)

    @Slot(str)
    def _show_failure(self, message):
        self.heading.setText("준비를 완료하지 못했어요")
        self.status.setText(message)
        self.detail.setText("문제를 확인한 뒤 다시 준비할 수 있습니다.")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.retry.show()

    def finish(self):
        self._finished = True
        self.close()

    def closeEvent(self, event):
        if not self._finished:
            QApplication.instance().quit()
        super().closeEvent(event)
