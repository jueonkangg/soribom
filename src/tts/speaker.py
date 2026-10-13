"""sherpa-onnx + Supertonic v3 오프라인 한국어 TTS → 내장 스피커 발화.

왜 Supertonic 인가:
  MeloTTS/Kokoro 는 폐기했다. (Kokoro = 한국어 음성이 아예 없음, MeloTTS = 팀 폐기)
  이전에 쓰던 mimic3-kss-low 는 프론트엔드 G2P가 espeak-ng 라 한국어 발음이 이미
  뭉개진 채로 합성돼, 파라미터·후처리를 아무리 만져도 음질 한계가 있었다.
  Supertonic v3(한국 Supertone사)는 한국어 네이티브·다화자·44.1kHz·int8 로
  Jetson 에서 오프라인으로 돌면서 음질이 확연히 낫다. 실행은 sherpa-onnx 로 한다.
  결정 경위와 청취 비교: docs/conversation_log.md

  출처: sherpa-onnx (Apache-2.0) https://github.com/k2-fsa/sherpa-onnx
        Supertonic 모델 https://github.com/supertone-inc/supertonic

왜 스피커를 단말에 내장하는가:
  교실 벽 스피커에서 소리가 나면 반 친구들이 누가 말했는지 알 수 없지만,
  학생 자리에서 나면 소리의 방향으로 화자를 자연스럽게 인식한다.
  이건 UX 설계 결정이지 기술적 편의가 아니다.
"""
import time
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
import sherpa_onnx


class SpeechSynthesisError(RuntimeError):
    pass


class SpeechOutputError(RuntimeError):
    pass


def trim_leading_quiet(samples, sample_rate):
    """첫 신호 앞 60ms를 남기고 매우 작은 선행 잡음만 최대 200ms 제거한다."""
    if sample_rate <= 0 or not len(samples) or not np.isfinite(samples).all():
        return samples, 0.0
    # -80dB보다 큰 첫 샘플을 기준으로 삼아 작은 첫 자음도 보존한다.
    audible = np.flatnonzero(np.abs(samples) > 0.0001)
    if not len(audible):
        return samples, 0.0
    cut = min(max(0, int(audible[0]) - int(sample_rate * 0.06)),
              int(sample_rate * 0.2))
    if cut < int(sample_rate * 0.05):
        return samples, 0.0
    return samples[cut:], cut / sample_rate


class Speaker:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.sid = cfg.get("sid", 0)
        self.num_steps = cfg.get("num_steps", 32)
        self.speed = cfg.get("speed", 1.0)
        self.language = cfg.get("language", "ko")
        self.output_device = cfg.get("output_device")   # None = 시스템 기본
        self._speech_lock = threading.RLock()
        self.on_event = lambda *args, **kwargs: None
        self.inference_gate = None
        self.on_speech_pause = lambda paused: None
        self._output_lock = threading.Lock()
        self._output_stream = None
        self._closed = False
        self._playback_done = threading.Event()
        self._playback_samples = None
        self._playback_offset = 0
        self._playback_error = False
        self.last_inference_wait = 0.0
        self.pulse_output = None
        if cfg.get("output_backend", "sounddevice") == "pulse":
            from tts.pulse_output import PulseOutput
            self.pulse_output = PulseOutput(cfg)

        # 모델 경로는 repo 루트 기준으로 푼다(어디서 실행하든 찾도록).
        #   src/tts/speaker.py → parents[2] = repo 루트
        repo_root = Path(__file__).resolve().parents[2]
        model_dir = repo_root / cfg["model_dir"]

        def load(provider: str) -> sherpa_onnx.OfflineTts:
            config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    supertonic=sherpa_onnx.OfflineTtsSupertonicModelConfig(
                        duration_predictor=str(model_dir / "duration_predictor.int8.onnx"),
                        text_encoder=str(model_dir / "text_encoder.int8.onnx"),
                        vector_estimator=str(model_dir / "vector_estimator.int8.onnx"),
                        vocoder=str(model_dir / "vocoder.int8.onnx"),
                        tts_json=str(model_dir / "tts.json"),
                        unicode_indexer=str(model_dir / "unicode_indexer.bin"),
                        voice_style=str(model_dir / "voice.bin"),
                    ),
                    num_threads=cfg.get("num_threads", 4),
                    provider=provider,
                ),
                max_num_sentences=1,
            )
            return sherpa_onnx.OfflineTts(config)

        # GPU(cuda)면 32스텝도 ~1.5초라 실시간이다. 다만 Jetson 은 CPU/GPU 가 8GB 를
        # 공유해서, 다른 프로그램이 메모리를 많이 쓰면 GPU 초기화가 실패할 수 있다
        # (CUBLAS_ALLOC_FAILED). 그때 앱이 죽지 않도록 CPU 로 자동 폴백한다.
        # (CPU 는 32스텝에 ~9초로 느리지만, 소리는 난다.)
        provider = cfg.get("provider", "cuda")
        try:
            self.tts = load(provider)
            self.provider = provider
        except Exception as e:
            if provider == "cpu":
                raise
            print(f"[TTS] GPU({provider}) 초기화 실패 → CPU 로 폴백(느려짐): {e}")
            self.tts = load("cpu")
            self.provider = "cpu"

        self.sample_rate = self.tts.sample_rate

    def synthesize(self, text: str):
        with self._speech_lock:
            self.last_inference_wait = 0.0
            if getattr(self, "inference_gate", None) is not None:
                def waited(seconds):
                    self.last_inference_wait = seconds
                    self.on_event("inference_wait", stage="tts", duration_s=seconds)
                return self.inference_gate.run(self._synthesize, text, speech=True,
                                               on_wait=waited)
            return self._synthesize(text)

    def warmup(self):
        # 결과는 재생하지 않고 초기 실행 비용을 모델 준비 단계에서 치른다.
        self.synthesize("안녕하세요.")

    def prepare_output(self, sample_rate=None):
        if getattr(self, "pulse_output", None) is not None:
            self.pulse_output.prepare()
            return
        # 출력 스트림을 재사용해 매 요청마다 장치를 여는 지연을 피한다. 준비만 하고 재생하지 않는다.
        with self._output_lock:
            if self._closed:
                raise RuntimeError("말하기가 종료되었습니다.")
            if self._output_stream is None:
                self._output_stream = sd.OutputStream(samplerate=sample_rate or self.sample_rate,
                    channels=1, dtype="float32", device=self.output_device,
                    latency=self.cfg.get("output_latency", "high"),
                    callback=self._fill_output, finished_callback=self._playback_done.set)
            return self._output_stream

    def _fill_output(self, outdata, frames, timing, status):
        # 합성된 음성을 짧게 복사한다. 마지막 출력의 재생 완료는 PortAudio가 알려준다.
        outdata.fill(0)
        if status.output_underflow:
            self._playback_error = True
        try:
            remaining = len(self._playback_samples) - self._playback_offset
            count = min(frames, remaining)
            outdata[:count, 0] = self._playback_samples[self._playback_offset:self._playback_offset + count]
            self._playback_offset += count
        except Exception:
            self._playback_error = True
            raise sd.CallbackAbort
        if self._playback_offset >= len(self._playback_samples):
            raise sd.CallbackStop

    def _close_output(self):
        with self._output_lock:
            stream, self._output_stream = self._output_stream, None
        if stream is not None:
            # 연결이 끊긴 장치의 정리 실패가 재시도나 수업 기록 저장을 막지 않게 한다.
            for cleanup in (stream.abort, stream.close):
                try:
                    cleanup()
                except Exception as exc:
                    self.on_event("error", stage="tts", operation="output",
                                  error_type=type(exc).__name__)

    def close(self):
        if getattr(self, "pulse_output", None) is not None:
            self.pulse_output.close()
        with self._output_lock:
            self._closed = True
        self._close_output()
        self._playback_done.set()

    def _synthesize(self, text: str):
        """텍스트 → (float32 mono 파형, 샘플레이트). 재생과 분리해 테스트를 쉽게 한다."""
        gen = sherpa_onnx.GenerationConfig()
        gen.sid = self.sid
        gen.speed = self.speed
        gen.num_steps = self.num_steps
        gen.extra["lang"] = self.language

        t0 = time.time()
        audio = self.tts.generate(text, gen)
        synth_s = time.time() - t0

        samples = np.array(audio.samples, dtype=np.float32)

        # 합성 시간만 측정한다. 재생 준비까지 포함한 사용자 체감 지연과 구분한다.
        dur = len(samples) / audio.sample_rate if len(samples) else 0.0
        print(f"[TTS] 합성 {synth_s:.2f}s (오디오 {dur:.1f}s, steps={self.num_steps}) : {text[:20]}")

        return samples, audio.sample_rate

    def say(self, text: str) -> None:
        """텍스트를 합성해 스피커로 재생한다. (재생이 끝날 때까지 블로킹)"""
        text = text.strip()
        if not text:
            return
        if len(text) > self.cfg.get("max_chars", 200):
            raise ValueError("말하기 문장이 너무 깁니다. 나눠서 입력해주세요.")
        if getattr(self, "_closed", False):
            raise RuntimeError("말하기가 종료되었습니다.")
        # UI 외 호출도 합성·재생을 겹치거나 대기 스레드를 쌓지 않도록 한다.
        if not self._speech_lock.acquire(blocking=False):
            raise RuntimeError("이미 말하는 중입니다.")
        try:
            started = time.monotonic()
            event = getattr(self, "on_event", lambda *args, **kwargs: None)
            event("tts_start")
            if getattr(self, "pulse_output", None) is not None:
                preparing = time.monotonic()
                try:
                    # 연결 확인은 추론 게이트 밖에서 해 자막 처리를 막지 않는다.
                    self.pulse_output.prepare(reconnect=True)
                    event("tts_output_ready", duration_s=time.monotonic() - preparing)
                except Exception as exc:
                    event("error", stage="tts", operation="output", error_type=type(exc).__name__)
                    raise SpeechOutputError("스피커 연결을 확인해주세요.") from exc
            self.last_inference_wait = 0.0
            if self.inference_gate is None:
                self._say_audio(text, started, event)
            else:
                def waited(seconds):
                    self.last_inference_wait = seconds
                    event("inference_wait", stage="tts", duration_s=seconds)
                self.inference_gate.run(self._say_audio, text, started, event,
                                        speech=True, on_wait=waited)
            event("tts_end", success=True, duration_s=time.monotonic() - started)
        except Exception as exc:
            event("tts_end", success=False, duration_s=time.monotonic() - started,
                  error_type=type(exc).__name__)
            raise
        finally:
            self._speech_lock.release()

    def _say_audio(self, text, started, event):
        # 게이트를 합성부터 재생 완료까지 유지하되, 마이크/VAD는 계속 수음한다.
        self.on_speech_pause(True)
        try:
            synthesizing = time.monotonic()
            try:
                samples, sr = self._synthesize(text)
            except Exception as exc:
                raise SpeechSynthesisError("음성 합성에 실패했습니다.") from exc
            synthesized = time.monotonic()
            event("tts_synthesis", duration_s=synthesized - synthesizing,
                  audio_s=len(samples) / sr)
            if not len(samples):
                raise RuntimeError("합성된 음성이 없습니다.")
            trimmed = 0.0
            if self.cfg.get("trim_leading_quiet", True):
                samples, trimmed = trim_leading_quiet(samples, sr)
            def playback_started():
                now = time.monotonic()
                event("tts_playback", duration_s=now - started,
                      output_prepare_s=now - synthesized, leading_trim_s=trimmed)
            if getattr(self, "pulse_output", None) is not None:
                try:
                    self.pulse_output.play(samples, sr, playback_started)
                except Exception as exc:
                    event("error", stage="tts", operation="output", error_type=type(exc).__name__)
                    raise SpeechOutputError("스피커 재생에 실패했습니다.") from exc
                return
            try:
                stream = self.prepare_output(sr)
                self._playback_done.clear()
                self._playback_samples = samples
                self._playback_offset = 0
                self._playback_error = False
                stream.start()
                playback_started()
                # 장치 응답이 사라져도 입력/말하기를 영구 잠그지 않는다.
                margin = max(0.1, float(self.cfg.get("playback_timeout_margin_seconds", 3)))
                if not self._playback_done.wait(len(samples) / sr + margin):
                    event("error", stage="tts", operation="output", error_type="TimeoutError")
                    raise TimeoutError("스피커 재생 완료를 확인하지 못했습니다.")
                if self._closed or self._playback_error or self._playback_offset < len(samples):
                    raise RuntimeError("음성 출력이 중단되었습니다.")
                # CallbackStop 후 비활성 스트림을 다음 요청에서 다시 시작할 수 있게 한다.
                stream.abort()
            except Exception as exc:
                # 실패한 출력 스트림을 남겨 다음 재시도에 섞지 않는다.
                self._close_output()
                raise SpeechOutputError("음성 출력이 중단되었습니다.") from exc
        finally:
            self.on_speech_pause(False)
            self._playback_samples = None
