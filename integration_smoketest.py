"""통합 스모크 테스트 — STT(GPU) + TTS(GPU) 동시 상주 확인 (Phase A).

가장 큰 리스크는 'STT 모델과 TTS 모델을 둘 다 Jetson GPU 에 올렸을 때
8GB 공유메모리가 버티는가(OOM 안 나는가)'다. 이 스크립트는 마이크/화면 없이
그 핵심만 격리해서 확인한다. (마이크·DOA·UI 를 포함한 실제 라이브 확인은
main.py 를 직접 실행해서 사람이 눈으로 본다.)

실행:
    .venv/bin/python integration_smoketest.py [발화가_담긴.wav]

  - 인자로 wav 를 주면 그 소리로 STT 를 시험한다(더 현실적).
  - 없으면 합성 잡음으로 대체한다(전사 결과는 무의미, 메모리만 본다).

⚠️ 데모/테스트 전에 브라우저 등 메모리 많이 쓰는 프로그램을 다 끌 것.
   (Jetson 은 CPU/GPU 가 RAM 을 공유한다 — CLAUDE.md 참고)
"""
import sys
import threading
import time
from pathlib import Path

import numpy as np
import yaml

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))


def mem_available_mb() -> int:
    """지금 즉시 쓸 수 있는 메모리(MB). /proc/meminfo 의 MemAvailable."""
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable"):
                return int(line.split()[1]) // 1024
    return -1


def swap_used_mb() -> int:
    total = free = 0
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("SwapTotal"):
                total = int(line.split()[1]) // 1024
            elif line.startswith("SwapFree"):
                free = int(line.split()[1]) // 1024
    return total - free


# 테스트 동안 '가장 낮았던' 여유 메모리를 잡아두는 배경 샘플러.
_low = {"mem": 10 ** 9, "run": True}


def _sampler() -> None:
    while _low["run"]:
        _low["mem"] = min(_low["mem"], mem_available_mb())
        time.sleep(0.2)


def stage(name: str) -> None:
    print(f"\n=== {name} ===  (MemAvail {mem_available_mb()} MB, Swap사용 {swap_used_mb()} MB)")


def main() -> None:
    print("통합 스모크 테스트 — STT + TTS 동시 GPU 상주")
    print(f"시작 시점 여유 메모리: {mem_available_mb()} MB (낮으면 브라우저 등을 끄세요)")

    threading.Thread(target=_sampler, daemon=True).start()

    cfg = yaml.safe_load(open(REPO / "src" / "config.yaml", encoding="utf-8"))

    # --- STT 로드 (GPU) ---
    stage("STT 모델 로드")
    from stt.transcriber import Transcriber
    t0 = time.time()
    stt = Transcriber(cfg["stt"])
    print(f"  STT 로드 {time.time() - t0:.1f}s "
          f"({cfg['stt']['model']}, {cfg['stt']['device']}/{cfg['stt']['compute_type']})")

    # --- TTS 로드 (GPU, 실패 시 speaker.py 가 CPU 폴백) ---
    stage("TTS 모델 로드")
    from tts.speaker import Speaker
    t0 = time.time()
    spk = Speaker(cfg["tts"])
    print(f"  TTS 로드 {time.time() - t0:.1f}s (provider={spk.provider}, steps={spk.num_steps})")
    if spk.provider != cfg["tts"].get("provider", "cuda"):
        print("  ⚠️ TTS 가 GPU 로 못 올라가 CPU 로 폴백했다. (메모리 부족 가능성)")

    # --- STT 추론 1회 (실제 GPU 작업 유발) ---
    stage("STT 추론")
    if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        import wave
        with wave.open(sys.argv[1], "rb") as w:
            pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        audio = pcm.astype(np.float32) / 32768.0
        print(f"  입력 wav: {sys.argv[1]} ({len(audio) / 16000:.1f}s)")
    else:
        audio = (np.random.randn(16000 * 2) * 0.01).astype(np.float32)
        print("  입력: 합성 잡음 2초 (전사 결과는 무의미, 메모리만 확인)")
    stt.transcribe(audio)                       # 웜업(CUDA 커널)
    txt = stt.transcribe(audio)
    print(f"  STT 추론 {stt.last_sec:.2f}s -> '{txt[:40]}'")

    # --- TTS 합성 1회 ---
    stage("TTS 합성")
    spk.synthesize("통합 테스트입니다.")          # 웜업
    t0 = time.time()
    spk.synthesize("오늘은 광합성에 대해 배웁니다. 질문 있는 사람은 손을 들어 주세요.")
    print(f"  TTS 합성 {time.time() - t0:.2f}s")

    # --- 결과 판정 ---
    _low["run"] = False
    time.sleep(0.3)
    stage("결과")
    print(f"  테스트 중 최저 여유 메모리: {_low['mem']} MB")
    print(f"  현재 Swap 사용: {swap_used_mb()} MB")
    if _low["mem"] < 150:
        print("  ⚠️ 여유 메모리가 거의 0 — 데모 중 OOM 위험. 스텝 낮추기/데스크톱 최소화 검토.")
    elif spk.provider == "cpu":
        print("  △ 동시 상주는 됐지만 TTS 가 CPU 폴백. GPU 메모리가 빠듯하다는 뜻.")
    else:
        print("  ✅ STT + TTS 둘 다 GPU 로 상주하고 OOM 없이 추론/합성 성공.")


if __name__ == "__main__":
    main()
