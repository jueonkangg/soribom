"""수업 종료 후 요약 노트를 만든다. (기능 ⑤)

두 단계:
  1) 규칙 기반 정리(_clean) — 발화 자막을 '자연스럽게' 다듬는다.
     ⚠️ 생성(재작성)이 아니다. 없는 말을 지어내지 않는다(CLAUDE.md §4).
     중복·반복 제거, 군더더기(어…/음…) 제거, 띄어쓰기·마침표 보정만 한다.
  2) 추출식 요약(_textrank) — 다듬은 문장들 중 '핵심'을 top_k 개 골라낸다.
     TextRank: 문장을 노드로, 단어 겹침을 간선 가중치로 그래프를 만들고
     PageRank 로 중요도를 매겨 상위 문장을 뽑는다(numpy 로 직접 구현, 새 패키지 없음).

화자별이 아니라 '단일 통합 요약'이다 — 소리봄은 화자를 식별하지 않기 때문(방향만 안다).
"""
import re
from datetime import datetime
from pathlib import Path

import numpy as np

# 문장 맨 앞/홀로 있을 때만 지우는 군더더기(간투사). 문장 중간의 같은 글자는 건드리지 않는다.
_FILLERS = ["어", "음", "그", "저", "이제", "인제", "뭐", "아"]
_END = ("다", "요", "죠", "까", "래", "네", "다.", "요.", "?", "!", ".")


class NoteBuilder:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.top_k = cfg.get("top_k", 8)
        # 핵심어(도메인 용어). 이 단어가 든 문장에 가산점 → 정보 밀도 높은 문장 우선.
        #   main.py 가 STT 의 수업 용어(stt.prompt)를 그대로 넣어 재사용한다.
        self.keywords = [k.strip() for k in cfg.get("keywords", []) if k and k.strip()]
        self.lines: list = []

        # 저장 위치. config 가 상대경로면 repo 루트 기준으로 푼다(실행 위치 무관).
        out = cfg.get("output_dir", "./notes")
        out_path = Path(out)
        if not out_path.is_absolute():
            repo_root = Path(__file__).resolve().parents[2]
            out_path = repo_root / out.lstrip("./")
        self.output_dir = out_path

    def add(self, text: str, angle: float) -> None:
        self.lines.append({"text": text, "angle": angle})

    # ---- 1단계: 규칙 기반 정리 (생성 아님) ----
    def _clean(self, texts: list) -> list:
        """자막 문장들을 읽기 좋게 다듬는다. 내용을 바꾸지 않고 정리만 한다."""
        cleaned = []
        for t in texts:
            s = re.sub(r"\s+", " ", (t or "").strip())     # 공백 정규화
            if not s:
                continue
            # 맨 앞 군더더기 제거(예: "어 그 광합성은" → "광합성은"). 한 번만.
            for f in _FILLERS:
                if s.startswith(f + " "):
                    s = s[len(f) + 1:].strip()
                    break
            if len(s) < 2:                                  # 너무 짧은 조각(응/네 등)은 요약에서 뺀다
                continue
            # 문장 끝 마침표 보정(물음표·느낌표는 유지)
            if not s.endswith(("?", "!", ".")):
                s = s + "."
            cleaned.append(s)

        # 중복·부분중복 제거: STT가 같은 말을 조각→완성으로 두 번 낼 때가 있다.
        # 앞 문장이 뒤 문장에 통째로 포함되면(부분) 짧은 쪽을 버리고 긴 쪽만 남긴다.
        result = []
        for s in cleaned:
            key = s.rstrip(".?! ")
            dup = False
            for i, r in enumerate(result):
                rk = r.rstrip(".?! ")
                if key == rk or key in rk:                 # 완전중복 또는 내가 기존 것의 부분
                    dup = True
                    break
                if rk in key:                              # 기존 것이 내 부분 → 내 것(긴 것)으로 교체
                    result[i] = s
                    dup = True
                    break
            if not dup:
                result.append(s)
        return result

    # ---- 2단계: TextRank 추출식 요약 ----
    @staticmethod
    def _bigrams(s: str) -> set:
        """문장의 글자 2-gram 집합. 한국어는 조사가 붙어(광합성은/광합성에) 단어 단위
        비교가 빗나가므로, 글자 단위로 겹침을 본다(광합성은/광합성에 → '광합','합성' 공유)."""
        t = re.sub(r"[^0-9A-Za-z가-힣]", "", s)   # 공백·구두점 제거
        return {t[i:i + 2] for i in range(len(t) - 1)}

    @classmethod
    def _similarity(cls, a: str, b: str) -> float:
        """두 문장의 글자 2-gram Jaccard 유사도(0~1). 조사·띄어쓰기에 강하다."""
        ba, bb = cls._bigrams(a), cls._bigrams(b)
        if not ba or not bb:
            return 0.0
        inter = len(ba & bb)
        union = len(ba | bb)
        return inter / union if union else 0.0

    def _sim_matrix(self, sentences: list) -> np.ndarray:
        """문장 간 단어 겹침 유사도 행렬(대칭, 대각선 0)."""
        n = len(sentences)
        w = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._similarity(sentences[i], sentences[j])
                w[i, j] = w[j, i] = sim
        return w

    def _pagerank(self, w: np.ndarray) -> np.ndarray:
        """유사도 그래프에서 PageRank 중요도 점수."""
        n = w.shape[0]
        row_sum = w.sum(axis=1, keepdims=True)
        row_sum[row_sum == 0] = 1.0
        w_norm = w / row_sum
        d = 0.85
        scores = np.full(n, 1.0 / n)
        for _ in range(40):
            scores = (1 - d) / n + d * (w_norm.T @ scores)
        return scores

    def _keyword_bonus(self, sentences: list) -> np.ndarray:
        """문장마다 든 핵심어(도메인 용어) 개수. 정보 밀도 가늠."""
        bonus = np.zeros(len(sentences))
        for i, s in enumerate(sentences):
            bonus[i] = sum(1 for kw in self.keywords if kw in s)
        return bonus

    @staticmethod
    def _normalize(v: np.ndarray) -> np.ndarray:
        """0~1 로 정규화(요소 비교용). 전부 같으면 균등값."""
        lo, hi = v.min(), v.max()
        if hi - lo < 1e-12:
            return np.full_like(v, 0.5)
        return (v - lo) / (hi - lo)

    def _select_mmr(self, w: np.ndarray, relevance: np.ndarray, k: int,
                    lam: float = 0.7) -> list:
        """MMR: 중요도(relevance)는 높이되 이미 뽑은 문장과 겹치는 건 피해 k개 고른다.

        점수 = lam*중요도 − (1−lam)*(이미 뽑은 문장과의 최대 유사도).
        비슷한 문장을 여러 개 뽑지 않고 '다양한 핵심'을 고르게 한다.
        """
        n = len(relevance)
        selected, candidates = [], list(range(n))
        while candidates and len(selected) < k:
            best_i, best_score = candidates[0], -1e9
            for i in candidates:
                redundancy = max((w[i, j] for j in selected), default=0.0)
                score = lam * relevance[i] - (1 - lam) * redundancy
                if score > best_score:
                    best_score, best_i = score, i
            selected.append(best_i)
            candidates.remove(best_i)
        return selected

    def _keyword_redundancy(self, sentences: list) -> np.ndarray:
        """문장 쌍이 '같은 핵심어'를 공유하는 정도(0~1). 같은 주제 문장을 중복으로 본다.

        표면 유사도만으로는 '광합성은 …'/'광합성이 …'처럼 같은 주제라도 낮게 잡혀
        MMR이 다양화를 못 한다. 그래서 핵심어 겹침(자카드)을 중복 신호로 더한다.
        """
        n = len(sentences)
        kwsets = [{kw for kw in self.keywords if kw in s} for s in sentences]
        r = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                a, b = kwsets[i], kwsets[j]
                if a and b:
                    r[i, j] = r[j, i] = len(a & b) / len(a | b)
        return r

    def _summarize_sentences(self, sentences: list, k: int) -> list:
        """핵심 문장 k개를 골라 '원래 순서대로' 돌려준다.

        ① PageRank 중요도 + ② 핵심어 가산점 → 관련도
        ③ MMR 로 중복 없이 선택(중복 = 글자 유사도와 '같은 핵심어 공유' 중 큰 값).
        """
        n = len(sentences)
        if n <= k:
            return sentences
        w = self._sim_matrix(sentences)
        # 관련도 = 그래프 중심성(PageRank) + 핵심어 밀도. 핵심어를 크게 실어
        # 인사·잡담(핵심어 0)이 수업 내용보다 앞서지 않게 한다.
        rel = self._normalize(self._pagerank(w)) + 0.8 * self._normalize(self._keyword_bonus(sentences))
        rel = self._normalize(rel)
        # 중복 판단은 표면 유사도와 핵심어 공유 중 '더 큰' 쪽으로(같은 주제면 걸러지게).
        redundancy = np.maximum(w, self._keyword_redundancy(sentences))
        chosen = self._select_mmr(redundancy, rel, k)
        return [sentences[i] for i in sorted(chosen)]      # 등장 순서로 출력

    def build_summary(self) -> str:
        """정리 + 추출식 요약 결과를 문자열로 만든다. (화면 패널·파일 저장 공용)"""
        texts = [ln["text"] for ln in self.lines]
        cleaned = self._clean(texts)
        if not cleaned:
            return "아직 요약할 수업 내용이 없습니다."
        picked = self._summarize_sentences(cleaned, self.top_k)
        header = f"수업 요약 · {datetime.now():%Y-%m-%d %H:%M}  (핵심 {len(picked)}문장)\n"
        body = "\n".join(f"• {s}" for s in picked)
        return header + "\n" + body

    def save(self) -> None:
        """요약을 파일로 저장한다(수업 종료 시). 내용이 없으면 저장하지 않는다."""
        if not self.lines:
            return
        summary = self.build_summary()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{datetime.now():%Y-%m-%d_%H%M}_수업요약.txt"
        path.write_text(summary + "\n", encoding="utf-8")
        print(f"[요약] 저장: {path}")
