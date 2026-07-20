"""Silero VAD — 사람이 말하는 구간만 잘라낸다.

큐로 들어오는 오디오를 창(window) 단위로 보며 '지금 말하는 중인지' 확률을
매기고, 발화가 끝날 때(충분한 침묵이 이어질 때)마다 그 발화 한 덩어리를 yield 한다.
다음 단계(2-패스 STT)는 이 덩어리를 받아 자막으로 만든다.

모델은 faster-whisper에 내장된 silero VAD(onnx)를 그대로 재사용한다.
- silero_vad 파이썬 패키지는 최상단에서 torch를 import 하는데, Jetson에서 torch는
  설치가 까다롭고 무겁다. 그런데 우리 STT 엔진인 faster-whisper가 torch 없이
  onnxruntime로 도는 silero VAD 모델을 이미 품고 있어 그걸 가져다 쓴다.
  → 추가 의존성도, 별도 모델 파일도 필요 없다.
- 참고: 직접 받은 독립 silero onnx(v5)는 onnxruntime 호출 규약이 달라 확률이
  전 구간 0으로 나왔다. faster-whisper의 래퍼는 검증돼 있어 이 문제가 없다.
- 모델 출처: https://github.com/snakers4/silero-vad (MIT License)
"""
from collections import deque

import numpy as np

from faster_whisper.vad import get_vad_model


# silero VAD 는 16kHz에서 정확히 512샘플(=32ms) 창을 요구한다.
SAMPLE_RATE = 16000
WINDOW_SAMPLES = 512
WINDOW_MS = WINDOW_SAMPLES * 1000 // SAMPLE_RATE   # 32


class _SileroVad:
    """faster-whisper 내장 silero VAD 모델을 창 하나씩 부르는 얇은 래퍼.

    faster-whisper의 모델은 호출마다 내부 상태를 초기화하지만, 창 단위로 불러도
    말/침묵을 충분히 잘 가른다(실측: 말하는 구간의 대부분이 임계값을 넘음).
    창 사이 연속성은 아래 상태기계의 침묵 유지시간(min_silence_ms)이 메운다.
    """

    def __init__(self) -> None:
        self.model = get_vad_model()   # onnxruntime 기반, torch 불필요

    def speech_prob(self, window) -> float:
        """window: float32 512샘플. 사람이 말하고 있을 확률(0~1)을 돌려준다."""
        out = self.model(window.copy())
        return float(np.asarray(out).reshape(-1)[0])


class VoiceActivityDetector:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.model = _SileroVad()

    def stream(self, audio_q):
        """말하는 구간이 끝날 때마다 그 구간 오디오(모노 float32)를 yield 한다.

        상태기계 요약:
          - 확률이 threshold 이상이면 '말하는 중'으로 보고 오디오를 모은다.
          - 말하는 중에 침묵이 min_silence_ms 이상 이어지면 발화가 끝난 것으로 보고,
            그때까지 모은 오디오를 내보낸다.
          - 단, 실제로 말한 시간이 min_speech_ms 미만이면 잡음으로 보고 버린다.
          - 발화 시작 직전 몇 창(speech_pad_ms)을 앞에 붙여 첫 음절이 잘리지 않게 한다.
        """
        threshold = self.cfg["threshold"]
        min_speech_ms = self.cfg["min_speech_ms"]
        min_silence_ms = self.cfg["min_silence_ms"]
        pad_ms = self.cfg.get("speech_pad_ms", 200)
        pad_windows = max(1, pad_ms // WINDOW_MS)

        recent = deque(maxlen=pad_windows)   # 발화 시작 전 창들(앞 패딩용)
        in_speech = False
        collected = []       # 현재 발화의 창 목록
        speech_ms = 0        # 임계값을 넘은 시간(실제 말한 길이)
        silence_ms = 0       # 발화 중 이어진 침묵 길이

        leftover = np.zeros(0, dtype=np.float32)   # 512로 안 떨어지고 남은 샘플

        while True:
            block = audio_q.get()
            # None은 종료 신호(자체 테스트에서 사용). 평상시엔 들어오지 않는다.
            if block is None:
                return

            samples = np.concatenate([leftover, block])
            n_windows = len(samples) // WINDOW_SAMPLES

            for i in range(n_windows):
                window = samples[i * WINDOW_SAMPLES:(i + 1) * WINDOW_SAMPLES]
                prob = self.model.speech_prob(window)

                if prob >= threshold:
                    if not in_speech:
                        in_speech = True
                        collected = list(recent)   # 앞 패딩부터 시작
                        speech_ms = 0
                    collected.append(window)
                    speech_ms += WINDOW_MS
                    silence_ms = 0
                else:
                    recent.append(window)
                    if in_speech:
                        collected.append(window)   # 발화 중 짧은 침묵도 이어붙인다
                        silence_ms += WINDOW_MS
                        if silence_ms >= min_silence_ms:
                            if speech_ms >= min_speech_ms:
                                yield np.concatenate(collected)
                            # 발화 종료 → 다음 발화를 위해 초기화
                            in_speech = False
                            collected = []
                            recent.clear()

            leftover = samples[n_windows * WINDOW_SAMPLES:]


# ---------------------------------------------------------------------------
# 자체 테스트: 마이크 → 캡처 → VAD 를 실제로 돌려, 발화가 끊길 때마다
# 감지 결과를 출력한다. 카운트다운 후 정해진 시간 동안 말하면 된다.
#   실행: python src/audio/vad.py
# ---------------------------------------------------------------------------
def _selftest() -> None:
    import queue
    import threading
    import time

    import yaml

    from capture import MicArray   # 같은 폴더

    cfg_path = Path(__file__).resolve().parents[1] / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    q: queue.Queue = queue.Queue()
    mic = MicArray(cfg["audio"], sink=q)
    vad = VoiceActivityDetector(cfg["vad"])

    seconds = 12
    utterances = []

    def consume() -> None:
        for chunk in vad.stream(q):
            dur = len(chunk) / SAMPLE_RATE
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            utterances.append(chunk)
            print(f"  [발화 감지] 길이 {dur:.2f}초, RMS {rms:.3f}", flush=True)

    worker = threading.Thread(target=consume, daemon=True)
    worker.start()

    for n in (3, 2, 1):
        print(f"  {n}...", flush=True)
        time.sleep(1)
    print(f">>> 지금부터 {seconds}초간 말해보세요. "
          f"문장 사이에 잠깐 쉬면 따로 감지됩니다.", flush=True)

    mic.start()
    time.sleep(seconds)
    mic.stop()
    q.put(None)          # stream 종료
    worker.join(timeout=2)

    print(f"\n총 {len(utterances)}개 발화 감지됨.")


if __name__ == "__main__":
    _selftest()
