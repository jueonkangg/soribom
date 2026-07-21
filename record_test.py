"""테스트용 녹음 도구. ReSpeaker ch0으로 정해진 시간 동안 녹음해 wav로 저장한다.
사용법: python record_test.py <출력파일.wav> [녹음초]
  예)  python record_test.py test_clean.wav 40
카운트다운 후 녹음이 시작되면 test_reference.txt 를 소리 내어 읽는다.
"""
import queue
import sys
import time
import wave
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path("src/audio").resolve()))
from capture import MicArray   # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "test_clean.wav"
seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 40

cfg = yaml.safe_load(open("src/config.yaml", encoding="utf-8"))
q: queue.Queue = queue.Queue()
mic = MicArray(cfg["audio"], sink=q)

print(f"'{out}' 에 {seconds}초 녹음합니다. 카운트다운 후 대본을 또박또박 읽으세요.")
for n in (3, 2, 1):
    print(f"  {n}...", flush=True)
    time.sleep(1)
print(">>> 지금 읽으세요!", flush=True)

mic.start()
collected = []
end = time.time() + seconds
while time.time() < end:
    remain = int(end - time.time())
    try:
        collected.append(q.get(timeout=0.5))
    except queue.Empty:
        pass
mic.stop()

audio = np.concatenate(collected) if collected else np.zeros(0, dtype=np.float32)
rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) else 0.0
pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
with wave.open(out, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(cfg["audio"]["sample_rate"])
    w.writeframes(pcm.tobytes())
print(f"\n저장 완료: {out}  ({len(audio)/16000:.1f}초, RMS {rms:.3f})")
print("재생 확인: aplay", out)
