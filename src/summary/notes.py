"""수업 '전체 기록(스크립트)'을 만든다. (기능 ⑤)

원래는 추출식 요약이었으나, 문장 몇 개짜리 추출은 '불완전한 스크립트'에 불과해
**모든 발화를 그대로 기록**하는 방식으로 바꿨다. 없는 말을 지어내지 않는다.

정리는 가볍게만 한다(생성 아님):
  - 공백 정규화, 문장 끝 마침표 보정
  - 바로 앞과 똑같은 발화(STT 이중 출력)만 중복 제거
모든 내용을 남긴다(짧은 맞장구도 기록). 화면 '수업 기록 보기' 패널 + 종료 시 파일 저장.
"""
import re
from datetime import datetime
from pathlib import Path


class NoteBuilder:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
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

    @staticmethod
    def _clean_line(text: str) -> str:
        """한 발화를 읽기 좋게 가볍게 다듬는다(내용은 바꾸지 않음)."""
        s = re.sub(r"\s+", " ", (text or "").strip())
        if not s:
            return ""
        if not s.endswith(("?", "!", ".")):
            s = s + "."
        return s

    def _script_lines(self) -> list:
        """모든 발화를 정리해 순서대로. 바로 앞과 똑같은 줄(STT 이중출력)만 제거."""
        out = []
        for ln in self.lines:
            s = self._clean_line(ln["text"])
            if not s:
                continue
            if out and out[-1] == s:      # 직전과 완전히 같은 발화만 중복 제거
                continue
            out.append(s)
        return out

    def build_summary(self) -> str:
        """수업 전체 기록 문자열. (화면 패널·파일 저장 공용)

        메서드 이름은 호환을 위해 build_summary 로 두되, 내용은 '전체 기록'이다.
        """
        lines = self._script_lines()
        if not lines:
            return "아직 기록된 수업 내용이 없습니다."
        header = f"수업 기록 · {datetime.now():%Y-%m-%d %H:%M}  (발화 {len(lines)}개)\n"
        body = "\n".join(f"• {s}" for s in lines)
        return header + "\n" + body

    # 화면 버튼/콜백에서 부르는 이름. build_summary 와 같은 내용.
    build_transcript = build_summary

    def save(self) -> None:
        """수업 종료 시 전체 기록을 파일로 저장한다. 내용이 없으면 저장하지 않는다."""
        if not self.lines:
            return
        text = self.build_summary()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{datetime.now():%Y-%m-%d_%H%M}_수업기록.txt"
        path.write_text(text + "\n", encoding="utf-8")
        print(f"[기록] 저장: {path}")
