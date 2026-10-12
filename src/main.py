"""소리봄 — 화면/모델과 장치 연결을 분리해 USB 오류에도 앱을 유지한다."""
import threading
import time
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
    from diagnostics import DiagnosticRecorder, resource_sample
    from stt.pipeline import UtteranceBuffer, error_category

    cfg = load_config()
    diagnostics = DiagnosticRecorder(cfg.get("diagnostics", {}))
    ui = SoribomUI(cfg)
    audio = AudioBuffer(cfg["audio"].get("queue_max_blocks", 100))
    pending = UtteranceBuffer(cfg["stt"].get("queue_max_utterances", 4),
                              cfg["stt"].get("queue_max_age_seconds", 6))
    def device_status(microphone, direction, detail=""):
        diagnostics.record("device_status", microphone=microphone, direction=direction)
        ui.show_device_status(microphone, direction, detail)
    devices = DeviceController(cfg, audio, device_status)
    devices.on_event = diagnostics.record
    def sample():
        process = devices.process
        try:
            pid = process.pid if process is not None else None
        except ValueError:
            pid = None  # 재연결 중 이미 close한 녹음 프로세스
        values = resource_sample(pid)
        values.update(audio.stats())
        values.update(pending.stats())
        values.update(mic_starts=devices.mic_starts, stale_input_blocks=devices.stale_input_blocks,
                      audio_gaps=devices.audio_gaps, callback_jitters=devices.callback_jitters,
                      capture_overflows=devices.capture_overflows, pipe_dropped_blocks=devices.pipe_dropped_blocks,
                      direction_samples=len(devices.direction_samples))
        return values
    diagnostics.sample = sample
    diagnostics.start()
    notes = NoteBuilder(cfg["summary"], subject=cfg["stt"].get("subject", "science"))
    stopped = threading.Event()
    ui.on_reconnect = devices.retry
    ui.on_summarize = notes.build_summary
    ui.on_note_snapshot = notes.build_email_transcript
    ui.on_send_note = send_note
    def note_status(success, message):
        diagnostics.record("note_save", success=success)
        ui.show_note_status(success, message)
    notes.start_autosave(note_status)
    ui.set_models_ready(False, "자막·말하기 모델을 준비하고 있습니다.")

    def initialize():
        try:
            from stt.transcriber import Transcriber
            from tts.speaker import Speaker
            vad = VoiceActivityDetector(cfg["vad"])
            stt = Transcriber(cfg["stt"])
            if stopped.is_set():
                diagnostics.record("models_cancelled")
                return
            speaker = Speaker(cfg["tts"])
            speaker.on_event = diagnostics.record
            events = SoundEventClassifier(cfg["events"])
            from stt.vocab import build_name_hotwords
            stt.set_extra_terms(build_name_hotwords(cfg["events"].get("student_names", [])))
            def log_hotwords(subject):
                values = getattr(stt, "last_hotword_stats", {})
                diagnostics.record("hotwords", subject=subject,
                                   lesson_active=bool(cfg["stt"].get("lesson_vocab", {}).get(subject)),
                                   **(values if isinstance(values, dict) else {}))
            log_hotwords(notes.current_subject())
            if stopped.is_set():
                diagnostics.record("models_cancelled")
                return
            ui.on_speak = speaker.say
            def change_subject(subject):
                stt.set_subject(subject)
                notes.set_subject(subject)
                log_hotwords(subject)
            ui.on_subject_change = change_subject
            ui.set_models_ready(True)
            diagnostics.record("models_ready", provider=getattr(speaker, "provider", None))

            def vad_lane():
                for generation, chunk, speech_ranges in vad.stream(audio, with_timing=True):
                    if stopped.is_set():
                        return
                    pending.put(generation, chunk, speech_ranges, notes.current_subject())

            def caption_lane():
                while not stopped.is_set():
                    item = pending.get()
                    if item is None:
                        return
                    generation, chunk, speech_ranges, subject = item
                    if not audio.publish(generation, lambda: None):
                        continue
                    try:
                        started = time.monotonic()
                        speech_end = speech_ranges[-1][1] if speech_ranges else None
                        text = stt.transcribe(chunk)
                        stt_seconds = time.monotonic() - started
                    except Exception as exc:
                        diagnostics.record("error", stage="caption", operation="transcribe",
                                           error_category=error_category(exc), error_type=type(exc).__name__)
                        print(f"[자막] 전사 실패: {exc}", flush=True)
                        ui.show_alert("자막 처리에 실패했습니다. 다음 음성을 다시 처리합니다.")
                        continue

                    # 표본 집계 중에도 마이크 워커가 음성을 큐에 넣을 수 있게 한다.
                    angle = devices.direction_for(generation, speech_ranges)
                    def publish():
                        ui.show_caption(text, angle=angle)
                        notes.add(text, angle=angle, subject=subject)
                        if cfg["events"].get("enabled"):
                            for alert in events.detect_in_text(text):
                                ui.show_alert(alert)
                        counts = getattr(stt, "last_filter_counts", {})
                        diagnostics.record("caption", generation=generation, has_text=bool(text),
                                           direction_known=angle is not None,
                                           duration_s=time.monotonic() - started,
                                           stt_duration_s=stt_seconds,
                                           audio_s=len(chunk) / cfg["audio"].get("sample_rate", 16000),
                                           speech_age_s=started - speech_end if speech_end else None,
                                           dispatch_delay_s=time.monotonic() - speech_end if speech_end else None,
                                           **(counts if isinstance(counts, dict) else {}))

                    # 전사 도중 연결이 끊겼으면 그 결과를 새 연결의 기록에 섞지 않는다.
                    audio.publish(generation, publish)

            def guarded_lane(lane, operation):
                try:
                    lane()
                except Exception as exc:
                    diagnostics.record("error", stage="caption", operation=operation,
                                       error_category=error_category(exc), error_type=type(exc).__name__)
                    ui.show_alert("자막 처리가 중단됐습니다. 앱을 다시 실행해주세요.")
            threading.Thread(target=guarded_lane, args=(vad_lane, "vad"), name="vad", daemon=True).start()
            threading.Thread(target=guarded_lane, args=(caption_lane, "publish"), name="captions", daemon=True).start()
            devices.start()
        except Exception as exc:
            diagnostics.record("error", stage="initialize", error_type=type(exc).__name__)
            print(f"[준비] 초기화 실패: {exc}", flush=True)
            ui.set_models_ready(False, "모델 준비에 실패했습니다.")
            ui.show_device_status("failed", "waiting", "모델 준비에 실패했습니다. 앱을 다시 실행해주세요.")

    initializer = threading.Thread(target=initialize, name="model-loading", daemon=True)
    initializer.start()
    clean = False
    try:
        ui.run()
        clean = True
    finally:
        stopped.set()
        pending.close()
        try:
            devices.stop()
            notes.stop_autosave()
            if cfg["summary"].get("enabled", True):
                notes.save_safely()
        except Exception as exc:
            clean = False
            diagnostics.record("error", stage="shutdown", error_type=type(exc).__name__)
            raise
        finally:
            diagnostics.close(clean=clean)


if __name__ == "__main__":
    main()
