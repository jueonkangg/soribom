"""수업 '전체 기록(스크립트)'을 만든다. (기능 5)

원래는 추출식 요약이었으나, 문장 몇 개짜리 추출은 '불완전한 스크립트'에 불과해
**모든 발화를 그대로 기록**하는 방식으로 바꿨다. 없는 말을 지어내지 않는다.

정리는 가볍게만 한다(생성 아님):
  - 공백 정규화, 문장 끝 마침표 보정
  - 바로 앞과 똑같은 발화(STT 이중 출력)만 중복 제거
모든 내용을 남긴다(짧은 맞장구도 기록). 화면 기록 보기 + 주기적/종료 파일 저장.
"""
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from stt.vocab import SUBJECT_LABELS


class NoteBuilder:
    def __init__(self, cfg: dict, subject="science") -> None:
        self.cfg = cfg
        self.lines: list = []
        self._lock = threading.Lock()
        self._save_lock = threading.Lock()
        self._saved_count = 0
        self._stop = threading.Event()
        self._worker = None
        self._on_save = lambda success, message: None
        self.started_at = datetime.now()
        self.subject = subject

        # 저장 위치. config 가 상대경로면 repo 루트 기준으로 푼다(실행 위치 무관).
        out = cfg.get("output_dir", "~/Desktop/소리봄 수업 기록")
        out_path = Path(out).expanduser()
        if not out_path.is_absolute():
            repo_root = Path(__file__).resolve().parents[2]
            out_path = repo_root / out_path
        self.output_dir = out_path
        # 한 실행의 자동 저장과 종료 저장은 같은 파일을 갱신한다.
        self.path = out_path / f"{self.started_at:%Y-%m-%d_%H%M%S}_{uuid4().hex}_수업기록.txt"

    def set_subject(self, subject: str) -> None:
        with self._lock:
            self.subject = subject

    def current_subject(self) -> str:
        with self._lock:
            return self.subject

    def add(self, text: str, angle: float, subject=None) -> None:
        if not text or not text.strip():
            return
        with self._lock:
            self.lines.append({"text": text, "angle": angle, "subject": subject or self.subject})

    @staticmethod
    def _clean_line(text: str) -> str:
        """한 발화를 읽기 좋게 가볍게 다듬는다(내용은 바꾸지 않음)."""
        s = re.sub(r"\s+", " ", (text or "").strip())
        if not s:
            return ""
        if not s.endswith(("?", "!", ".")):
            s = s + "."
        return s

    def _script_lines(self, snapshot=None) -> list:
        """모든 발화를 정리해 순서대로. 바로 앞과 똑같은 줄(STT 이중출력)만 제거."""
        out = []
        # 복사할 때만 잠근다. 화면 미리보기·메일 처리 중에도 새 자막은 계속 기록한다.
        if snapshot is None:
            with self._lock:
                snapshot = list(self.lines)
        for ln in snapshot:
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
        return self.build_email_transcript() or "아직 기록된 수업 내용이 없습니다."

    def build_email_transcript(self) -> str:
        """메일 미리보기용 스냅샷. 빈 기록은 안내문 대신 빈 문자열로 반환한다."""
        with self._lock:
            snapshot = list(self.lines)
        return self._format_transcript(snapshot)

    def _format_transcript(self, snapshot) -> str:
        groups = []
        for line in snapshot:
            subject = line["subject"]
            if not groups or groups[-1][0] != subject:
                groups.append((subject, []))
            groups[-1][1].append(line)
        cleaned = [(subject, self._script_lines(lines)) for subject, lines in groups]
        count = sum(len(lines) for _, lines in cleaned)
        if not count:
            return ""
        subjects = list(dict.fromkeys(subject for subject, lines in cleaned if lines))
        labels = [SUBJECT_LABELS.get(subject, subject) for subject in subjects]
        weekday = "월화수목금토일"[self.started_at.weekday()]
        header = f"수업 기록 · {self.started_at:%Y-%m-%d} ({weekday}요일) {self.started_at:%H:%M}  (발화 {count}개)\n과목: {', '.join(labels)}\n"
        parts = []
        for subject, lines in cleaned:
            if len(subjects) > 1:
                parts.append(f"\n[{SUBJECT_LABELS.get(subject, subject)}]")
            parts.extend(f"• {line}" for line in lines)
        body = "\n".join(parts)
        return header + "\n" + body

    # 화면 버튼/콜백에서 부르는 이름. build_summary 와 같은 내용.
    build_transcript = build_summary

    def save(self):
        """임시 파일을 완성한 뒤 교체한다. 실패하면 이전 저장본을 보존한다."""
        with self._save_lock:
            with self._lock:
                snapshot = list(self.lines)
            if not snapshot:
                return None
            if len(snapshot) == self._saved_count:
                return self.path
            text = self._format_transcript(snapshot)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                # mkstemp의 권한 600을 유지해 실제 수업 내용 접근을 제한한다.
                fd, filename = tempfile.mkstemp(prefix=".수업기록_", suffix=".tmp", dir=self.output_dir)
                temporary = Path(filename)
                with os.fdopen(fd, "w", encoding="utf-8") as output:
                    output.write(text + "\n")
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            self._saved_count = len(snapshot)
            self._on_save(True, f"수업 기록 저장됨 · {datetime.now():%H:%M:%S}")
            return self.path

    def start_autosave(self, on_save) -> None:
        """모델 준비·음성 처리와 독립된 저장 워커 하나만 실행한다."""
        if not self.cfg.get("enabled", True) or self._worker is not None:
            return
        self._on_save = on_save
        interval = max(1.0, float(self.cfg.get("autosave_seconds", 30)))

        def autosave():
            while not self._stop.wait(interval):
                self.save_safely()

        self._worker = threading.Thread(target=autosave, name="note-autosave", daemon=True)
        self._worker.start()

    def save_safely(self) -> bool:
        try:
            self.save()
            return True
        except OSError as exc:
            print(f"[기록] 저장 실패: {exc}", flush=True)
            self._on_save(False, "기록 저장 실패 · 저장 공간과 폴더 권한을 확인해주세요. 기록 보기·노트 보내기는 사용할 수 있습니다.")
            return False

    def stop_autosave(self) -> None:
        self._stop.set()
        if self._worker is not None:
            self._worker.join()
