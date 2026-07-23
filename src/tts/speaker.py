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
from pathlib import Path

import numpy as np
import sounddevice as sd
import sherpa_onnx


class Speaker:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.sid = cfg.get("sid", 0)
        self.num_steps = cfg.get("num_steps", 32)
        self.speed = cfg.get("speed", 1.0)
        self.language = cfg.get("language", "ko")
        self.output_device = cfg.get("output_device")   # None = 시스템 기본

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

        # §8 TTS 지연 측정: 합성에 걸린 시간을 남긴다(타이핑 완료 → 소리까지).
        dur = len(samples) / audio.sample_rate if len(samples) else 0.0
        print(f"[TTS] 합성 {synth_s:.2f}s (오디오 {dur:.1f}s, steps={self.num_steps}) : {text[:20]}")

        return samples, audio.sample_rate

    def say(self, text: str) -> None:
        """텍스트를 합성해 스피커로 재생한다. (재생이 끝날 때까지 블로킹)"""
        text = text.strip()
        if not text:
            return
        samples, sr = self.synthesize(text)
        sd.play(samples, samplerate=sr, device=self.output_device)
        sd.wait()
