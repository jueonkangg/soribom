"""Phase C 측정 — 실제 자막 파이프라인 그대로 WER/CER + 발화당 지연을 잰다.

stt_eval.py 는 도메인 prompt 를 넣지 않아(광합성→광업성) 실제 앱보다 불리하게 나온다.
이 스크립트는 main.py 의 lane_caption 과 똑같이 **VAD 로 발화를 자르고,
Transcriber(초기 prompt 포함)로 전사**한다. 그래서 데모 화면에 뜨는 정확도와 일치한다.

측정 지표(§8):
  - CER / WER : 자막 정확도 (조용할 때 / 시끄러울 때)
  - 발화당 전사 시간 : 자막 지연(말이 끝난 뒤 자막이 뜰 때까지)의 근사값

사용법:
  .venv/bin/python phase_c_eval.py            # test_clean.wav, test_noisy.wav 둘 다
  .venv/bin/python phase_c_eval.py my.wav     # 특정 wav 하나
"""
import queue
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np
import yaml

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "src" / "audio"))

from vad import VoiceActivityDetector      # noqa: E402
from stt.transcriber import Transcriber    # noqa: E402

REFERENCE = REPO / "test_reference.txt"


def normalize(text: str) -> str:
    text = re.sub(r"[.,!?~…\"'’“”·()\[\]]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def edit_distance(a, b) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def load_wav(path):
    with wave.open(str(path), "rb") as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0


def evaluate(wav_path, cfg, stt, reference):
    audio = load_wav(wav_path)

    # main.py 와 동일하게: VAD 로 발화를 잘라 발화 단위로 전사한다.
    vad = VoiceActivityDetector(cfg["vad"])
    q: queue.Queue = queue.Queue()
    for i in range(0, len(audio), 480):
        q.put(audio[i:i + 480])
    q.put(None)

    parts = []
    latencies = []
    for chunk in vad.stream(q):
        text = stt.transcribe(chunk)          # 실제 파이프라인: prompt 포함
        parts.append(text)
        latencies.append(stt.last_sec)        # 발화 하나를 전사한 시간

    hyp = normalize(" ".join(parts))
    ref_c, hyp_c = reference.replace(" ", ""), hyp.replace(" ", "")
    cer = edit_distance(ref_c, hyp_c) / max(1, len(ref_c))
    wer = edit_distance(reference.split(), hyp.split()) / max(1, len(reference.split()))

    return {
        "wav": Path(wav_path).name,
        "utterances": len(parts),
        "cer": cer * 100,
        "wer": wer * 100,
        "lat_min": min(latencies) if latencies else 0.0,
        "lat_med": float(np.median(latencies)) if latencies else 0.0,
        "lat_max": max(latencies) if latencies else 0.0,
        "hyp": hyp,
    }


def main():
    cfg = yaml.safe_load(open(REPO / "src" / "config.yaml", encoding="utf-8"))
    reference = normalize(REFERENCE.read_text(encoding="utf-8"))

    wavs = sys.argv[1:] or ["test_clean.wav", "test_noisy.wav"]

    print(f"모델 로드: {cfg['stt']['model']} ({cfg['stt']['device']}/{cfg['stt']['compute_type']}), "
          f"prompt={'있음' if cfg['stt'].get('prompt') else '없음'}")
    stt = Transcriber(cfg["stt"])

    # 웜업 1회(CUDA 커널 준비) — 측정에서 제외한다.
    stt.transcribe(load_wav(REPO / wavs[0])[:16000])

    results = []
    for w in wavs:
        path = REPO / w
        if not path.exists():
            print(f"  (건너뜀: {w} 없음)")
            continue
        r = evaluate(path, cfg, stt, reference)
        results.append(r)
        print(f"\n===== {r['wav']} =====")
        print(f"  발화 {r['utterances']}개 | CER {r['cer']:.1f}% | WER {r['wer']:.1f}%")
        print(f"  발화당 전사시간(자막지연 근사): "
              f"min {r['lat_min']:.2f}s / 중앙 {r['lat_med']:.2f}s / max {r['lat_max']:.2f}s")
        print(f"  인식: {r['hyp']}")

    return results


if __name__ == "__main__":
    main()
