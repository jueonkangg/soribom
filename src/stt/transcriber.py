"""2-패스 한국어 전사.

큰 모델은 정확하지만 느리고, 작은 모델은 빠르지만 부정확하다.
둘 중 하나를 고르는 대신 작은 모델이 먼저 임시 자막을 띄우고
큰 모델이 뒤따라 교정한다.

  draft(chunk)  → 1패스(small): 빠른 임시 자막
  refine(chunk) → 2패스(medium): 정확한 교정 자막

입력 chunk 는 VAD가 잘라준 발화 한 덩어리(모노 float32, 16kHz)다.
"""
import time

from faster_whisper import WhisperModel


class TwoPassTranscriber:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.language = cfg["language"]
        self.beam_size = cfg.get("beam_size", 1)

        device = cfg["device"]
        compute_type = cfg["compute_type"]
        cpu_threads = cfg.get("cpu_threads", 0)   # 0 = 자동

        # 모델 로드는 몇 초씩 걸린다. 호출마다 로드하면 매번 낭비이므로
        # 시작할 때 딱 한 번만 두 모델을 올려둔다.
        self.pass1 = WhisperModel(
            cfg["pass1_model"], device=device,
            compute_type=compute_type, cpu_threads=cpu_threads,
        )
        self.pass2 = WhisperModel(
            cfg["pass2_model"], device=device,
            compute_type=compute_type, cpu_threads=cpu_threads,
        )

        # 지표 측정(§8 자막 지연): 마지막 전사에 걸린 시간(초).
        # 전체 지연(말 끝~자막)은 UI 통합 때 붙이고, 여기서는 STT 계산 시간을 남긴다.
        self.last_draft_sec = 0.0
        self.last_refine_sec = 0.0

    def _transcribe(self, model, chunk) -> str:
        segments, _ = model.transcribe(
            chunk,
            language=self.language,
            beam_size=self.beam_size,
            vad_filter=False,                  # 이미 VAD로 걸렀으니 중복하지 않는다
            condition_on_previous_text=False,  # 짧은 발화에서 반복/환각을 줄인다
        )
        # transcribe 는 지연 생성(generator)이라, 여기서 실제로 돌려 문장을 잇는다.
        return " ".join(seg.text.strip() for seg in segments).strip()

    def draft(self, chunk) -> str:
        """1패스 — 빠른 임시 자막."""
        start = time.monotonic()
        text = self._transcribe(self.pass1, chunk)
        self.last_draft_sec = time.monotonic() - start
        return text

    def refine(self, chunk) -> str:
        """2패스 — 정확한 교정 자막."""
        start = time.monotonic()
        text = self._transcribe(self.pass2, chunk)
        self.last_refine_sec = time.monotonic() - start
        return text


# ---------------------------------------------------------------------------
# 자체 테스트: 저장된 발화 wav를 2-패스로 전사하고, 결과와 걸린 시간을 출력한다.
#   실행: python src/stt/transcriber.py [audio.wav]
# 사람 음성이 없어도 검증할 수 있게 파일 입력을 받는다.
# ---------------------------------------------------------------------------
def _selftest() -> None:
    import sys
    import wave
    from pathlib import Path

    import numpy as np
    import yaml

    wav_path = sys.argv[1] if len(sys.argv) > 1 else "vad_debug.wav"
    if not Path(wav_path).exists():
        print(f"테스트 wav가 없습니다: {wav_path}")
        print("사용법: python src/stt/transcriber.py <발화가_담긴.wav>")
        return

    cfg_path = Path(__file__).resolve().parents[1] / "config.yaml"
    cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))["stt"]

    with wave.open(wav_path, "rb") as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    audio = pcm.astype(np.float32) / 32768.0
    print(f"입력: {wav_path} ({len(audio)/16000:.1f}초)")

    print("모델 로딩 중... (small + medium, 처음엔 몇 초 걸림)")
    stt = TwoPassTranscriber(cfg)

    draft = stt.draft(audio)
    print(f"[1패스/{cfg['pass1_model']}] {stt.last_draft_sec:.1f}s → \"{draft}\"")

    refine = stt.refine(audio)
    print(f"[2패스/{cfg['pass2_model']}] {stt.last_refine_sec:.1f}s → \"{refine}\"")


if __name__ == "__main__":
    _selftest()
