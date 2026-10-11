"""소리봄 — 화면/모델과 장치 연결을 분리해 USB 오류에도 앱을 유지한다."""
import threading
from pathlib import Path

import yaml


def load_config(path: str = None) -> dict:
    if path is None:
        path = Path(__file__).resolve().parent / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    # 녹음 자식 프로세스가 이 모듈을 읽어도 Qt/GPU 모델을 불러오지 않도록
    # 무거운 모듈은 main 안에서만 import 한다.
    from audio.recovery import AudioBuffer, DeviceController
    from audio.vad import VoiceActivityDetector
    from events.sound_events import SoundEventClassifier
    from summary.notes import NoteBuilder
    from summary.email_sender import send_note
    from ui.app import SoribomUI

    cfg = load_config()
    ui = SoribomUI(cfg)
    audio = AudioBuffer(cfg["audio"].get("queue_max_blocks", 100))
    devices = DeviceController(cfg, audio, ui.show_device_status)
    notes = NoteBuilder(cfg["summary"], subject=cfg["stt"].get("subject", "science"))
    stopped = threading.Event()
    ui.on_reconnect = devices.retry
    ui.on_summarize = notes.build_summary
    ui.on_note_snapshot = notes.build_email_transcript
    ui.on_send_note = send_note
    notes.start_autosave(ui.show_note_status)
    ui.set_models_ready(False, "자막·말하기 모델을 준비하고 있습니다.")

    def initialize():
        try:
            from stt.transcriber import Transcriber
            from tts.speaker import Speaker
            vad = VoiceActivityDetector(cfg["vad"])
            stt = Transcriber(cfg["stt"])
            if stopped.is_set():
                return
            speaker = Speaker(cfg["tts"])
            events = SoundEventClassifier(cfg["events"])
            stt.set_extra_terms(cfg["events"].get("student_names", []))
            if stopped.is_set():
                return
            ui.on_speak = speaker.say
            def change_subject(subject):
                stt.set_subject(subject)
                notes.set_subject(subject)
            ui.on_subject_change = change_subject
            ui.set_models_ready(True)

            def caption_lane():
                for generation, chunk in vad.stream(audio, with_generation=True):
                    if stopped.is_set():
                        return
                    # 방향 USB 요청은 장치 워커가 처리한다. 실패해도 STT는 계속 돈다.
                    if not audio.publish(generation, lambda: devices.request_direction(generation)):
                        continue
                    try:
                        subject = notes.current_subject()
                        text = stt.transcribe(chunk)
                    except Exception as exc:
                        print(f"[자막] 전사 실패: {exc}", flush=True)
                        ui.show_alert("자막 처리에 실패했습니다. 다음 음성을 다시 처리합니다.")
                        continue

                    def publish():
                        angle = devices.current_angle()
                        ui.show_caption(text, angle=angle)
                        notes.add(text, angle=angle, subject=subject)
                        if cfg["events"].get("enabled"):
                            for alert in events.detect_in_text(text):
                                ui.show_alert(alert)

                    # 전사 도중 연결이 끊겼으면 그 결과를 새 연결의 기록에 섞지 않는다.
                    audio.publish(generation, publish)

            threading.Thread(target=caption_lane, name="captions", daemon=True).start()
            devices.start()
        except Exception as exc:
            print(f"[준비] 초기화 실패: {exc}", flush=True)
            ui.set_models_ready(False, "모델 준비에 실패했습니다.")
            ui.show_device_status("failed", "waiting", "모델 준비에 실패했습니다. 앱을 다시 실행해주세요.")

    initializer = threading.Thread(target=initialize, name="model-loading", daemon=True)
    initializer.start()
    try:
        ui.run()
    finally:
        stopped.set()
        devices.stop()
        notes.stop_autosave()
        if cfg["summary"].get("enabled", True):
            notes.save_safely()


if __name__ == "__main__":
    main()
