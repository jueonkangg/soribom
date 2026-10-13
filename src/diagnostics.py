"""원문 없이 수치·상태만 남기는 제한된 JSONL 진단 기록. 파일 쓰기는 워커 하나가 한다."""
from datetime import datetime
import json
import math
import os
from pathlib import Path
import queue
import re
import threading
import time
import uuid


EVENTS = {"session_start", "session_end", "resources", "device_status", "mic_start",
          "mic_failure", "audio_gap", "retry", "error", "models_ready", "models_cancelled",
          "caption", "callback_jitter", "models_warmup", "inference_wait", "tts_start", "tts_synthesis", "tts_playback", "tts_end", "note_save", "hotwords"}
NUMBERS = {"pid", "capture_pid", "rss_kib", "capture_rss_kib", "available_kib", "threads",
           "generation", "queue_depth", "queue_capacity", "queue_dropped_blocks", "queue_overflows", "resets",
           "stale_results", "stale_input_blocks", "audio_gaps", "mic_starts", "duration_s", "stt_duration_s", "error_code",
           "audio_s", "speech_age_s", "dispatch_delay_s", "hotwords_total", "hotwords_selected", "hotwords_tokens", "no_speech_filtered",
           "low_confidence_filtered", "echo_filtered", "direction_samples", "dropped_log_events",
           "callback_jitters", "capture_overflows", "pipe_dropped_blocks", "missing_blocks",
           "utterance_queue_depth", "utterance_dropped", "inference_wait_s"}
FLAGS = {"success", "has_text", "direction_known", "clean", "lesson_active"}
CHOICES = {"microphone": {"ready", "waiting", "connecting", "failed"},
           "direction": {"ready", "waiting", "connecting", "failed", "disabled"},
           "stage": {"initialize", "caption", "mic", "direction", "shutdown", "tts"},
           "provider": {"cuda", "cpu"}}
CHOICES["failure_reason"] = {"capture_error", "process_exit", "input_timeout", "driver_error"}
CHOICES["subject"] = {"korean", "math", "science", "english", "economics"}
CHOICES["operation"] = {"transcribe", "vad", "publish", "output",
                        "vad_load", "stt_load", "tts_load", "stt_warmup", "tts_warmup", "devices_start"}
CHOICES["error_category"] = {"memory", "cuda", "input", "unknown"}


def process_rss(pid):
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return None


def resource_sample(capture_pid=None):
    result = {"pid": os.getpid(), "rss_kib": process_rss(os.getpid()),
              "threads": threading.active_count(), "capture_pid": capture_pid,
              "capture_rss_kib": process_rss(capture_pid) if capture_pid else None}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                result["available_kib"] = int(line.split()[1])
    except (OSError, ValueError):
        pass
    return result


class DiagnosticRecorder:
    def __init__(self, cfg, sample=None):
        self.enabled = cfg.get("enabled", False)
        self.directory = Path(__file__).resolve().parents[1] / cfg.get("output_dir", "diagnostics")
        self.path = self.directory / "runtime.jsonl"
        self.max_bytes = max(2048, int(cfg.get("max_bytes", 2 * 1024 * 1024)))
        self.backups = max(1, min(10, int(cfg.get("backups", 4))))
        self.interval = max(1, float(cfg.get("sample_seconds", 10)))
        self.queue = queue.Queue(maxsize=256)
        self.session = uuid.uuid4().hex
        self.started = time.monotonic()
        self.sample = sample or resource_sample
        self.stopping = threading.Event()
        self.lock = threading.Lock()
        self.dropped = 0
        self.worker = None
        self.end_clean = True

    def record(self, event, **fields):
        if not self.enabled or self.stopping.is_set() or event not in EVENTS:
            return
        item = {"time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                "elapsed_s": round(time.monotonic() - self.started, 4),
                "session": self.session, "event": event}
        # 호출자가 실수해도 자막·입력·주소·예외 메시지가 파일에 들어가지 않게 허용 목록을 쓴다.
        for key, value in fields.items():
            if key in NUMBERS and (value is None or
                    isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)):
                item[key] = value
            elif key in FLAGS and isinstance(value, bool):
                item[key] = value
            elif key in CHOICES and isinstance(value, str) and value in CHOICES[key]:
                item[key] = value
            elif key == "error_type" and isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", value):
                item[key] = value
        try:
            self.queue.put_nowait(item)
        except queue.Full:
            with self.lock:
                self.dropped += 1

    def start(self):
        if not self.enabled or self.worker is not None:
            return
        self.record("session_start", pid=os.getpid())
        self.worker = threading.Thread(target=self._run, name="diagnostics", daemon=True)
        self.worker.start()
        print(f"[진단] 기록 위치: {self.path}", flush=True)

    def _write(self, item):
        self.directory.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(item, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        if self.path.exists() and self.path.stat().st_size + len(line) > self.max_bytes:
            for index in range(self.backups, 0, -1):
                source = self.path if index == 1 else self.directory / f"runtime.jsonl.{index - 1}"
                target = self.directory / f"runtime.jsonl.{index}"
                if source.exists():
                    os.replace(source, target)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "ab") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(line)
            output.flush()

    def _run(self):
        next_sample = 0
        try:
            while not self.stopping.is_set() or not self.queue.empty():
                if not self.stopping.is_set() and time.monotonic() >= next_sample:
                    try:
                        values = self.sample()
                        with self.lock:
                            values["dropped_log_events"] = self.dropped
                        self.record("resources", **values)
                    except Exception as exc:
                        self.record("error", error_type=type(exc).__name__)
                    next_sample = time.monotonic() + self.interval
                try:
                    self._write(self.queue.get(timeout=0.2))
                except queue.Empty:
                    continue
            # 큐가 가득 찼어도 종료 기록은 유실시키지 않는다.
            self._write({"time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                         "elapsed_s": round(time.monotonic() - self.started, 4),
                         "session": self.session, "event": "session_end",
                         "clean": self.end_clean, "dropped_log_events": self.dropped})
        except Exception:
            # 진단 디스크 오류가 자막·말하기나 종료를 막으면 안 된다.
            self.enabled = False
            print("[진단] 로그 기록 실패. 저장 공간·권한을 확인해주세요. 앱은 계속 동작합니다.", flush=True)

    def close(self, clean=True):
        if self.stopping.is_set():
            return
        if self.enabled:
            try:
                values = self.sample()
                values["dropped_log_events"] = self.dropped
                self.record("resources", **values)
            except Exception as exc:
                self.record("error", error_type=type(exc).__name__)
        self.end_clean = clean
        self.stopping.set()
        if self.worker is not None:
            self.worker.join(2)
