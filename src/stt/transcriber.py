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

        # 수업 용어를 hotwords 로 STT 에 편향한다(과목별 사전 + 공통 + 이름).
        #   ⚠️ initial_prompt 가 아니라 hotwords 를 쓴다: initial_prompt 는 소리가 불분명할 때
        #      그 용어들을 그대로 뱉는(에코) 문제가 있다. hotwords 는 편향만 하고 에코가 적다.
        self.subject = cfg.get("subject", "science")
        self.extra_terms = []                 # 학생 이름 등(main 에서 set_extra_terms 로 채움)
        self.keywords = []                    # 현재 hotwords 용어 목록(에코 가드에도 씀)
        self.prompt = None                    # hotwords 문자열
        self._apply_vocab()

        # 모델 로드는 몇 초 걸린다. 시작할 때 한 번만 올려둔다.
        self.model = WhisperModel(
            cfg["model"],
            device=cfg["device"],
            compute_type=cfg["compute_type"],
            cpu_threads=cfg.get("cpu_threads", 0),
        )

        # 지표 측정(§8 자막 지연): 마지막 전사에 걸린 시간(초).
        self.last_sec = 0.0

    def _apply_vocab(self) -> None:
        """현재 과목 + 공통 + 추가어로 hotwords 를 다시 만든다(모델 재로딩 없음)."""
        from stt.vocab import build_hotwords
        self.keywords = build_hotwords(self.subject, self.extra_terms)
        self.prompt = ", ".join(self.keywords) if self.keywords else None

    def set_subject(self, subject: str) -> None:
        """과목을 바꾼다 → 다음 발화부터 그 과목 용어로 편향(UI 드롭다운에서 호출)."""
        self.subject = subject
        self._apply_vocab()

    def set_extra_terms(self, terms) -> None:
        """학생 이름 등 추가 용어를 넣는다(STT 가 이름을 더 잘 잡도록)."""
        self.extra_terms = list(terms or [])
        self._apply_vocab()

    def _is_prompt_echo(self, text: str) -> bool:
        """인식 결과가 '힌트 용어 나열'(환각)인지 판단한다.

        소리가 불분명할 때 모델이 힌트 용어를 쉼표/공백으로 죽 나열하는 경우가 있다
        (예: "이산화탄소, 포도당, 수행평가, 교과서"). 이런 건 진짜 발화가 아니므로 버린다.
        정상 문장은 용어 사이에 다른 말·문장 끝(다/요 등)이 있어 걸리지 않는다.
        """
        import re
        if not self.keywords or not text:
            return False
        kw = set(self.keywords)
        # ① 쉼표로 나뉜 항목이 대부분 '용어 그 자체'면 나열 환각.
        parts = [p.strip() for p in re.split(r"[,，]", text) if p.strip()]
        if len(parts) >= 2 and sum(p in kw for p in parts) >= max(2, 0.8 * len(parts)):
            return True
        # ② 쉼표가 없어도, 토큰 대부분이 정확히 용어면 나열 환각.
        toks = [t for t in re.split(r"\s+", text.strip()) if t]
        if len(toks) >= 3 and sum(t in kw for t in toks) >= 0.8 * len(toks):
            return True
        return False

    def transcribe(self, chunk) -> str:
        """발화 한 덩어리를 자막 문자열로 바꾼다. (환각 방어 포함)"""
        start = time.monotonic()
        segments, _ = self.model.transcribe(
            chunk,
            language=self.language,
            beam_size=self.beam_size,
            hotwords=self.prompt,              # 도메인 용어 편향(에코 적음, initial_prompt 대체)
            vad_filter=False,                  # 이미 VAD로 걸렀으니 중복하지 않는다
            condition_on_previous_text=False,  # 짧은 발화에서 반복/환각을 줄인다
        )
        # 신뢰도 필터: 무음/저신뢰 세그먼트(환각 위험)는 버린다.
        parts = []
        for seg in segments:
            if getattr(seg, "no_speech_prob", 0.0) > 0.85:   # 거의 무음
                continue
            if getattr(seg, "avg_logprob", 0.0) < -1.3:      # 확신이 매우 낮음
                continue
            t = seg.text.strip()
            if t:
                parts.append(t)
        text = " ".join(parts).strip()

        # 프롬프트 에코(용어 나열 환각)면 버린다.
        if self._is_prompt_echo(text):
            text = ""

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
