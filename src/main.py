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


def main(close_development_tools=False) -> None:
    # 모델과 장치 모듈을 읽기 전에 작은 창부터 그린다.
    from PySide6.QtWidgets import QApplication
    from ui.loading import LoadingWindow
    app = QApplication.instance() or QApplication([])
    loading = LoadingWindow()
    loading.show_centered()
    app.processEvents()
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
    from inference import InferenceGate

    cfg = load_config()
    diagnostics = DiagnosticRecorder(cfg.get("diagnostics", {}))
    ui = SoribomUI(cfg)
    ui.on_caption_layout = lambda **values: diagnostics.record("caption_layout", **values)

    ui.startup_window = loading
    audio = AudioBuffer(cfg["audio"].get("queue_max_blocks", 100))
    pending = UtteranceBuffer(cfg["stt"].get("queue_max_utterances", 4),
                              cfg["stt"].get("queue_max_age_seconds", 0),
                              cfg["stt"].get("speech_queue_max_utterances", 32))
    inference_gate = InferenceGate()
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
    speaker = None
    initializer = None
    initialization_lock = threading.Lock()
    initialization_running = False
    models_initialized = False
    tools_closed = False
    audio_prepared = False
    audio_warning = None
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
        nonlocal speaker, initialization_running, models_initialized, tools_closed, audio_prepared, audio_warning
        operation = "vad_load"
        failure_detail = None
        try:
            loading.set_stage(0, "개발 실행: 브라우저와 Codex를 유지합니다.")
            if close_development_tools and not tools_closed:
                from startup import stop_development_tools
                operation = "startup_cleanup"
                loading.set_stage(0, "브라우저와 Codex를 종료해 메모리를 확보합니다.")
                before = resource_sample().get("available_kib")
                began = time.monotonic()
                remaining = stop_development_tools(stopped.is_set)
                diagnostics.record("startup_cleanup", duration_s=time.monotonic() - began,
                                   remaining_tools=remaining, available_before_kib=before,
                                   available_after_kib=resource_sample().get("available_kib"))
                tools_closed = True
                if remaining:
                    loading.set_stage(0, "일부 도구가 종료되지 않았습니다. 준비를 계속합니다.")
                    ui.show_alert("일부 개발 도구가 종료되지 않았습니다. 메모리가 부족하면 직접 닫아주세요.")
            if stopped.is_set():
                return
            if (not audio_prepared and cfg["tts"].get("startup_recovery", False)
                    and cfg["tts"].get("output_backend") == "pulse"):
                from audio.output_recovery import prepare_system_output
                operation = "audio_startup"
                loading.set_stage(0, "무선 절전을 확인하고 스피커 오디오를 다시 준비합니다.")
                began = time.monotonic()
                try:
                    output_status = prepare_system_output(cfg["tts"], stopped.is_set)
                except Exception as exc:
                    diagnostics.record("error", stage="initialize", operation="audio_startup",
                                       error_type=type(exc).__name__)
                    output_status = {"speaker_ready": False, "wifi_checked": False}
                diagnostics.record("audio_startup", duration_s=time.monotonic() - began, **output_status)
                audio_prepared = True
                if not output_status["speaker_ready"]:
                    audio_warning = "스피커 연결을 확인하지 못했습니다. 전원을 확인해주세요. 자막은 사용할 수 있습니다."
                elif output_status["wifi_checked"] and not output_status["wifi_power_save_off"]:
                    audio_warning = "Wi-Fi 절전 해제를 확인하지 못했습니다. 스피커 잡음이 있으면 연결 설정을 확인해주세요."
                elif not output_status.get("audio_profile_reset", False):
                    audio_warning = "스피커 오디오 초기화를 완료하지 못했습니다. 잡음이 나면 다른 재생을 멈춘 뒤 앱을 다시 실행해주세요."
            if stopped.is_set():
                return
            loading.set_stage(1)
            operation = "vad_load"
            vad = VoiceActivityDetector(cfg["vad"])
            operation = "stt_load"
            loading.set_stage(2)
            from stt.transcriber import Transcriber
            stt = Transcriber(cfg["stt"])
            if stopped.is_set():
                diagnostics.record("models_cancelled")
                return
            events = SoundEventClassifier(cfg["events"])
            from stt.vocab import build_name_hotwords
            stt.set_extra_terms(build_name_hotwords(cfg["events"].get("student_names", [])))
            if cfg["stt"].get("warmup", False):
                operation = "stt_warmup"
                loading.set_stage(3)
                import numpy as np
                began = time.monotonic()
                inference_gate.run(stt.transcribe, np.zeros(cfg["audio"].get("sample_rate", 16000), dtype=np.float32))
                diagnostics.record("models_warmup", stage="caption", duration_s=time.monotonic() - began)
            # STT의 첫 추론 메모리를 먼저 확보한 뒤 TTS를 올린다.
            if stopped.is_set():
                return
            operation = "tts_load"
            loading.set_stage(4)
            from tts.speaker import Speaker
            speaker = Speaker(cfg["tts"])
            speaker.on_event = diagnostics.record
            speaker.inference_gate = inference_gate
            speaker.on_speech_pause = pending.hold_for_speech
            if cfg["tts"].get("warmup", False):
                operation = "tts_warmup"
                loading.set_stage(5)
                began = time.monotonic()
                speaker.warmup()
                diagnostics.record("models_warmup", stage="tts", duration_s=time.monotonic() - began)
            if stopped.is_set():
                speaker.close()
                return
            try:
                speaker.prepare_output()
            except Exception as exc:
                # 출력 장치가 없어도 자막/기록은 준비한다. 말하기 때 장치를 다시 연다.
                diagnostics.record("error", stage="tts", error_type=type(exc).__name__, operation="output")
                ui.show_alert("스피커 출력을 준비하지 못했습니다. 출력 장치를 확인해주세요.")
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
            ui.on_voice_change = speaker.set_voice
            def change_subject(subject):
                stt.set_subject(subject)
                notes.set_subject(subject)
                log_hotwords(subject)
            ui.on_subject_change = change_subject
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
                        wait = [0.0]
                        def waited(seconds):
                            wait[0] = seconds
                            diagnostics.record("inference_wait", stage="caption", duration_s=seconds)
                        text = inference_gate.run(stt.transcribe, chunk,
                                                  on_wait=waited)
                        stt_seconds = time.monotonic() - started - wait[0]
                    except Exception as exc:
                        diagnostics.record("error", stage="caption", operation="transcribe",
                                           error_category=error_category(exc), error_type=type(exc).__name__)
                        print(f"[자막] 전사 실패: {exc}", flush=True)
                        if error_category(exc) == "memory":
                            ui.show_alert("자막 처리 중 메모리 오류가 발생했습니다. 다음 음성을 다시 처리합니다.")
                        else:
                            ui.show_alert("자막 처리에 실패했습니다. 다음 음성을 다시 처리합니다.")
                        continue

                    # 표본 집계 중에도 마이크 워커가 음성을 큐에 넣을 수 있게 한다.
                    angle = devices.direction_for(generation, speech_ranges)
                    def publish():
                        ui.show_caption(text, angle=angle, speech_ranges=speech_ranges,
                                        generation=generation)
                        notes.add(text, angle=angle, subject=subject)
                        if cfg["events"].get("enabled"):
                            for alert in events.detect_in_text(text):
                                ui.show_alert(alert)
                        counts = getattr(stt, "last_filter_counts", {})
                        decode_stats = getattr(stt, "last_decode_stats", {})
                        diagnostics.record("caption", generation=generation, has_text=bool(text),
                                           direction_known=angle is not None,
                                           duration_s=time.monotonic() - started,
                                           stt_duration_s=stt_seconds,
                                           audio_s=len(chunk) / cfg["audio"].get("sample_rate", 16000),
                                           inference_wait_s=wait[0],
                                           speech_age_s=started + wait[0] - speech_end if speech_end else None,
                                           dispatch_delay_s=time.monotonic() - speech_end if speech_end else None,
                                           **(counts if isinstance(counts, dict) else {}),
                                           **(decode_stats if isinstance(decode_stats, dict) else {}))

                    # 전사 도중 연결이 끊겼으면 그 결과를 새 연결의 기록에 섞지 않는다.
                    audio.publish(generation, publish)

            def guarded_lane(lane, operation):
                try:
                    lane()
                except Exception as exc:
                    diagnostics.record("error", stage="caption", operation=operation,
                                       error_category=error_category(exc), error_type=type(exc).__name__)
                    ui.show_alert("자막 처리가 중단됐습니다. 앱을 다시 실행해주세요.")
            operation = "devices_start"
            loading.set_stage(6, "마이크와 방향 연결을 시작합니다. 연결 상태는 메인 화면에서 확인할 수 있습니다.")
            devices.start()
            threading.Thread(target=guarded_lane, args=(vad_lane, "vad"), name="vad", daemon=True).start()
            threading.Thread(target=guarded_lane, args=(caption_lane, "publish"), name="captions", daemon=True).start()
            models_initialized = True
            ui.set_models_ready(True)
            if audio_warning:
                ui.show_alert(audio_warning)
            diagnostics.record("models_ready", provider=getattr(speaker, "provider", None))
        except Exception as exc:
            category = error_category(exc)
            diagnostics.record("error", stage="initialize", operation=operation,
                               error_category=category, error_type=type(exc).__name__)
            print(f"[준비] {operation} 실패: {exc}", flush=True)
            if speaker is not None:
                try:
                    speaker.close()
                except Exception as cleanup_error:
                    diagnostics.record("error", stage="initialize", operation="output",
                                       error_type=type(cleanup_error).__name__)
                speaker = None
            if stopped.is_set():
                return
            stage_name = {"startup_cleanup": "개발 도구 정리", "audio_startup": "스피커 연결", "vad_load": "음성 구간 감지", "stt_load": "자막 모델",
                          "stt_warmup": "자막 모델 첫 실행", "tts_load": "말하기 모델",
                          "tts_warmup": "말하기 모델 첫 실행", "devices_start": "장치 시작"}[operation]
            detail = f"{stage_name} 준비에 실패했습니다. 다시 준비하기를 눌러주세요."
            if category in ("memory", "cuda"):
                detail += " 메모리·GPU 상태를 확인하고 다른 무거운 앱을 닫아주세요."
            failure_detail = detail
            # 실패한 모델 참조를 내려 재시도 시 GPU 모델이 중복으로 남지 않게 한다.
            stt = vad = None
        finally:
            with initialization_lock:
                initialization_running = False
            if failure_detail is not None and not stopped.is_set():
                ui.set_models_ready(False, failure_detail)
                ui.show_device_status("model_failed", "waiting", failure_detail)
                loading.fail(failure_detail)

    def retry_models():
        nonlocal initializer, initialization_running
        with initialization_lock:
            if stopped.is_set() or initialization_running or models_initialized:
                return
            initialization_running = True
            ui.set_models_ready(False, "자막·말하기 모델을 준비하고 있습니다.")
            initializer = threading.Thread(target=initialize, name="model-loading", daemon=True)
            initializer.start()
    ui.on_retry_models = retry_models
    loading.on_retry = retry_models
    retry_models()
    clean = False
    try:
        ui.run()
        clean = True
    finally:
        stopped.set()
        pending.close()
        try:
            devices.stop()
            if speaker is not None:
                speaker.close()
            notes.stop_autosave()
            if cfg["summary"].get("enabled", True):
                notes.save_safely()
        except Exception as exc:
            clean = False
            diagnostics.record("error", stage="shutdown", error_type=type(exc).__name__)
            raise
        finally:
            diagnostics.close(clean=clean)
            loading.finish()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--close-development-tools", action="store_true")
    main(close_development_tools=parser.parse_args().close_development_tools)
