"""소리봄 (SoundSight) — 진입점.

교실 소리를 받아 처리한다.
  자막:   VAD → STT(단일 패스) → 자막 (+ 이름 호명 감지 = 기능 3, 수업 기록 = 기능 5)
  방향:   DOA → 화자 방향 (기능 2)
  말하기: 학생의 타이핑 입력을 TTS로 발화 (기능 6)
비음성 소리 분류(종소리 등, 기능 3의 나머지)와 블루투스 소리 전달(기능 4)은 다음 단계다.
"""
import queue
import threading
from pathlib import Path

import yaml

from audio.capture import MicArray
from audio.doa import DoaTracker
from audio.vad import VoiceActivityDetector
from events.sound_events import SoundEventClassifier
from stt.transcriber import Transcriber
from summary.notes import NoteBuilder
from tts.speaker import Speaker
from ui.app import SoribomUI


def load_config(path: str = None) -> dict:
    # config.yaml 은 이 파일(main.py) 옆에 있다. 실행 위치(cwd)에 상관없이 찾도록
    # 파일 기준 절대경로로 푼다. (repo 루트에서 `python src/main.py` 로 실행해도 되게)
    if path is None:
        path = Path(__file__).resolve().parent / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    # 모델 로딩은 몇 초 걸린다. 그동안 화면(전체화면 창)이 아직 안 떠서 멈춘 것처럼
    # 보이므로, 어디까지 됐는지 단계별로 찍어 준다(flush=True 로 즉시 출력).
    def step(msg: str) -> None:
        print(f"[준비] {msg}", flush=True)

    cfg = load_config()

    audio_q: queue.Queue = queue.Queue()
    step("화면 초기화...")
    ui = SoribomUI(cfg)

    step("마이크 연결...")
    mic = MicArray(cfg["audio"], sink=audio_q)
    step("자막 모델 로딩... (수 초 걸립니다)")
    vad = VoiceActivityDetector(cfg["vad"])
    stt = Transcriber(cfg["stt"])
    step("방향 장치 연결...")
    doa = DoaTracker(cfg["doa"])
    events = SoundEventClassifier(cfg["events"])
    notes = NoteBuilder(cfg["summary"])
    step("말하기 모델 로딩... (수 초 걸립니다)")
    speaker = Speaker(cfg["tts"])
    step("완료 — 잠시 후 화면이 뜹니다.")

    # 학생 이름을 STT hotwords 에도 넣어 이름을 더 잘 잡게 한다(이름 호명 감지의 정확도↑).
    stt.set_extra_terms(cfg["events"].get("student_names", []))

    # 학생이 타이핑한 문장을 내장 스피커로 발화 (기능 6)
    ui.on_speak = speaker.say
    # '수업 기록 보기' 버튼 → 지금까지의 전체 발화 기록을 화면 패널로 (기능 5)
    ui.on_summarize = notes.build_summary
    # 헤더 과목 드롭다운 → 그 과목 용어로 STT 편향 전환(다음 발화부터)
    ui.on_subject_change = stt.set_subject

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
            # 기능 3(경량) 이름 호명 감지 — 오디오 모델 없이 방금 인식한 자막 텍스트에서 찾는다.
            # config 의 events.enabled 일 때만 동작하고, 자막 텍스트를 '읽기'만 한다.
            if cfg["events"].get("enabled"):
                for alert in events.detect_in_text(text):
                    ui.show_alert(alert)

    def lane_events() -> None:
        """말이 아닌 소리(종소리 등)를 감지해 알린다. — 다음 단계(미구현 스텁)."""
        for label, conf in events.stream(audio_q):
            ui.show_alert(label, conf)

    # 자막 레인만 돈다. 기능 3의 '이름 호명' 감지는 오디오 모델 없이 lane_caption 안에서
    # 자막 텍스트로 처리한다(위 참고). 비음성 소리(종소리 등)를 다루는 오디오 레인
    # lane_events 는 아직 스텁(NotImplementedError)이라 시작하지 않는다(다음 단계).
    lanes = [lane_caption]
    for target in lanes:
        threading.Thread(target=target, daemon=True).start()

    mic.start()
    try:
        ui.run()
    finally:
        mic.stop()
        # 기능 5 수업 기록: 켜져 있을 때만 종료 시 파일로 저장한다.
        if cfg["summary"].get("enabled"):
            notes.save()   # 수업 종료 후 전체 기록 저장


if __name__ == "__main__":
    main()
