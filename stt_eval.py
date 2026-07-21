"""STT 정확도/지연 평가. 한 번에 '한 설정'만 돌린다(GPU 메모리 충돌 방지).

사용법:
  python stt_eval.py <wav> <reference.txt> <model> <mode> [beam]
    model : small | medium | ...
    mode  : utt   -> VAD로 발화 단위로 쪼개 전사(실제 파이프라인과 동일)
            whole -> 전체를 한 번에 전사(큰 창=문맥 최대, VAD 분할 없음)
    beam  : 기본 1

출력: CER(문자오류율), WER(어절오류율), 전사시간, 전사문 미리보기.
CER/WER 은 구두점 제거·공백 정규화 후 편집거리로 계산한다.
"""
import queue
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path("src/audio").resolve()))
from vad import VoiceActivityDetector, SAMPLE_RATE   # noqa: E402
from faster_whisper import WhisperModel               # noqa: E402


def normalize(text: str) -> str:
    """비교를 위해 구두점을 지우고 공백을 하나로 정규화한다."""
    text = re.sub(r"[.,!?~…\"'’“”·()\[\]]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def edit_distance(a, b) -> int:
    """두 시퀀스(문자열/리스트) 사이의 Levenshtein 편집거리."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def load_wav(path):
    with wave.open(path, "rb") as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0


def main():
    wav, ref_path, model_name, mode = sys.argv[1:5]
    beam = int(sys.argv[5]) if len(sys.argv) > 5 else 1

    cfg = yaml.safe_load(open("src/config.yaml", encoding="utf-8"))
    audio = load_wav(wav)
    reference = normalize(Path(ref_path).read_text(encoding="utf-8"))

    # medium은 GPU에 안 올라가므로, 정확도 상한 측정 땐 EVAL_DEVICE=cpu 로 강제할 수 있다.
    import os
    device = os.environ.get("EVAL_DEVICE", cfg["stt"]["device"])
    compute = os.environ.get("EVAL_COMPUTE", cfg["stt"]["compute_type"])
    model = WhisperModel(model_name, device=device, compute_type=compute)

    def transcribe(chunk, ctx=False, prompt=None):
        segs, _ = model.transcribe(chunk, language="ko", beam_size=beam,
                                   condition_on_previous_text=ctx,
                                   initial_prompt=prompt)
        return " ".join(s.text.strip() for s in segs).strip()

    transcribe(audio[:16000])   # 웜업

    t0 = time.time()
    if mode == "whole":
        hypothesis = transcribe(audio, ctx=True)
    else:  # utt: VAD로 발화 단위 전사
        vad = VoiceActivityDetector(cfg["vad"])
        q = queue.Queue()
        for i in range(0, len(audio), 480):
            q.put(audio[i:i + 480])
        q.put(None)
        parts = [transcribe(chunk) for chunk in vad.stream(q)]
        hypothesis = " ".join(parts)
    elapsed = time.time() - t0

    hyp = normalize(hypothesis)
    ref_c, hyp_c = reference.replace(" ", ""), hyp.replace(" ", "")
    cer = edit_distance(ref_c, hyp_c) / max(1, len(ref_c))
    wer = edit_distance(reference.split(), hyp.split()) / max(1, len(reference.split()))

    print(f"[{model_name}/{mode}/beam{beam}] 전사 {elapsed:.2f}s "
          f"| CER {cer*100:.1f}% | WER {wer*100:.1f}%")
    print(f"    인식: {hyp}")


if __name__ == "__main__":
    main()
