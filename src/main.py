"""소리봄 (SoundSight) — 진입점.

교실 소리를 받아 4개 레인으로 병렬 처리한다.
  A: VAD → 2-패스 STT → 자막
  B: DOA → 화자 방향
  C: 소리 이벤트 분류 → 알림
  D: 근접 오디오 → AGC/리미터 → 블루투스
그리고 학생의 타이핑 입력을 TTS로 발화한다.
"""
import queue
import threading

import yaml

from audio.capture import MicArray
from audio.doa import DoaTracker
from audio.vad import VoiceActivityDetector
from events.sound_events import SoundEventClassifier
from stt.transcriber import TwoPassTranscriber
from summary.notes import NoteBuilder
from tts.speaker import Speaker
from ui.app import SoribomUI


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    cfg = load_config()

    audio_q: queue.Queue = queue.Queue()
    ui = SoribomUI(cfg)

    mic = MicArray(cfg["audio"], sink=audio_q)
    vad = VoiceActivityDetector(cfg["vad"])
    stt = TwoPassTranscriber(cfg["stt"])
    doa = DoaTracker(cfg["doa"])
    events = SoundEventClassifier(cfg["events"])
    notes = NoteBuilder(cfg["summary"])
    speaker = Speaker(cfg["tts"])

    # 학생이 타이핑한 문장을 내장 스피커로 발화 (기능 ⑥)
    ui.on_speak = speaker.say

    def lane_caption() -> None:
        """레인 A — 음성 구간을 잘라 2-패스로 전사한다."""
        for chunk in vad.stream(audio_q):
            angle = doa.current()
            # 1패스: 빠른 임시 자막 (흐리게 표시)
            ui.show_caption(stt.draft(chunk), angle=angle, tentative=True)
            # 2패스: 정확한 교정 자막으로 교체
            final = stt.refine(chunk)
            ui.show_caption(final, angle=angle, tentative=False)
            notes.add(final, angle=angle)

    def lane_events() -> None:
        """레인 C — 말이 아닌 소리를 감지해 알린다."""
        for label, conf in events.stream(audio_q):
            ui.show_alert(label, conf)

    for target in (lane_caption, lane_events):
        threading.Thread(target=target, daemon=True).start()

    mic.start()
    try:
        ui.run()
    finally:
        mic.stop()
        notes.save()   # 수업 종료 후 요약 노트 저장


if __name__ == "__main__":
    main()
