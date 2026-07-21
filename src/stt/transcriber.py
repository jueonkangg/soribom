"""한국어 전사 (단일 패스, GPU).

원래 설계는 2-패스(small 임시자막 → medium 교정)였다. 하지만 실측 결과
medium은 8GB 공유메모리에 앱과 함께 올리면 OOM 나고, 정확도도 small과
사실상 같았다(둘 다 CER ~1%). 문맥 기반 2-패스 교정도 정확도를 못 올렸다.
그래서 small 단일 패스로 확정했다. (자세한 근거는 config.yaml 주석 참고)

정확도 보강은 2-패스 대신 'initial_prompt(도메인 용어 힌트)'로 한다. 수업 용어를
힌트로 주면 인식이 올바른 후보로 정렬돼, 없는 말을 지어내지 않고 오인식만 준다.

입력 chunk 는 VAD가 잘라준 발화 한 덩어리(모노 float32, 16kHz)다.
"""
import time

from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.language = cfg["language"]
        self.beam_size = cfg.get("beam_size", 1)
        # 수업 용어 힌트(선택). 비어 있으면 None으로 둔다.
        self.prompt = cfg.get("prompt") or None

        # 모델 로드는 몇 초 걸린다. 시작할 때 한 번만 올려둔다.
        self.model = WhisperModel(
            cfg["model"],
            device=cfg["device"],
            compute_type=cfg["compute_type"],
            cpu_threads=cfg.get("cpu_threads", 0),
        )

        # 지표 측정(§8 자막 지연): 마지막 전사에 걸린 시간(초).
        self.last_sec = 0.0

    def transcribe(self, chunk) -> str:
        """발화 한 덩어리를 자막 문자열로 바꾼다."""
        start = time.monotonic()
        segments, _ = self.model.transcribe(
            chunk,
            language=self.language,
            beam_size=self.beam_size,
            initial_prompt=self.prompt,        # 도메인 용어 힌트(오인식 교정)
            vad_filter=False,                  # 이미 VAD로 걸렀으니 중복하지 않는다
            condition_on_previous_text=False,  # 짧은 발화에서 반복/환각을 줄인다
        )
        # transcribe 는 지연 생성(generator)이라, 여기서 실제로 돌려 문장을 잇는다.
        text = " ".join(seg.text.strip() for seg in segments).strip()
        self.last_sec = time.monotonic() - start
        return text


# ---------------------------------------------------------------------------
# 자체 테스트: 저장된 발화 wav를 전사하고 결과와 걸린 시간을 출력한다.
#   실행: python src/stt/transcriber.py [audio.wav]
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

    print(f"모델 로딩 중... ({cfg['model']}, {cfg['device']}/{cfg['compute_type']})")
    stt = Transcriber(cfg)

    # 첫 호출은 CUDA 커널 준비로 느리다(웜업). 그 다음이 실사용 속도.
    warm = stt.transcribe(audio)
    print(f"[웜업] {stt.last_sec:.2f}s")
    text = stt.transcribe(audio)
    print(f"[전사] {stt.last_sec:.2f}s → \"{text}\"")


if __name__ == "__main__":
    _selftest()
