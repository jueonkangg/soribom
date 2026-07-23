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
from stt.transcriber import Transcriber
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
    stt = Transcriber(cfg["stt"])
    doa = DoaTracker(cfg["doa"])
    events = SoundEventClassifier(cfg["events"])
    notes = NoteBuilder(cfg["summary"])
    speaker = Speaker(cfg["tts"])

    # 학생이 타이핑한 문장을 내장 스피커로 발화 (기능 ⑥)
    ui.on_speak = speaker.say

    def lane_caption() -> None:
        """레인 A — 음성 구간을 잘라 small 모델로 전사한다(단일 패스).

        원래 2-패스(임시→교정) 설계였으나, 메모리 제약으로 small 단일 패스로 확정했다.
        (→ stt/transcriber.py, config.yaml 주석 참고) GPU라 발화당 ~0.5초로 충분히 빠르다.
        같은 발화의 방향(DOA)을 같이 읽어 자막과 함께 화면에 올린다.
        """
        for chunk in vad.stream(audio_q):
            angle = doa.current()
            text = stt.transcribe(chunk)
            ui.show_caption(text, angle=angle, tentative=False)
            notes.add(text, angle=angle)

    def lane_events() -> None:
        """레인 C — 말이 아닌 소리를 감지해 알린다."""
        for label, conf in events.stream(audio_q):
            ui.show_alert(label, conf)

    # 자막 레인은 항상 돈다. 이벤트 레인(기능 ③)은 이번 개발 범위 밖이라
    # config 로 켤 때만 시작한다. events.stream() 은 아직 스텁(NotImplementedError)이라,
    # 그냥 켜면 스레드가 죽으며 traceback 을 뱉는다. (범위: CLAUDE.md 3장)
    lanes = [lane_caption]
    if cfg["events"].get("enabled"):
        lanes.append(lane_events)
    for target in lanes:
        threading.Thread(target=target, daemon=True).start()

    mic.start()
    try:
        ui.run()
    finally:
        mic.stop()
        # 요약 노트(기능 ⑤)도 이번 범위 밖. 켤 때만 저장한다.
        # notes.save() 는 아직 스텁이라, 끄고 호출하면 종료 시 앱이 크래시한다.
        if cfg["summary"].get("enabled"):
            notes.save()   # 수업 종료 후 요약 노트 저장


if __name__ == "__main__":
    main()
