"""마이크와 방향 워커를 하나씩 유지한다. 연결 재시도에서 모델은 건드리지 않는다."""
import multiprocessing
import queue
import threading
import time
from collections import deque
import math

import numpy as np

from audio.capture import capture_process, BLOCK_HEADER
from audio.doa import DoaTracker, _robust_center


class AudioBuffer:
    """연결 세대 번호로 끊기기 전 오디오/전사 결과가 섞이지 않게 한다."""
    def __init__(self, max_blocks):
        self.queue = queue.Queue(maxsize=max(2, max_blocks))
        self.generation = 0
        self.closed = False
        self.lock = threading.RLock()
        self.dropped_blocks = 0
        self.resets = 0
        self.overflows = 0
        self.stale_results = 0

    def _reset(self):
        self.generation += 1
        self.resets += 1
        while True:
            try:
                item = self.queue.get_nowait()
                if item is not None and len(item[1]):
                    self.dropped_blocks += 1
            except queue.Empty:
                break

    def reset(self):
        with self.lock:
            if not self.closed:
                self._reset()
                self.queue.put_nowait((self.generation, np.zeros(0, dtype=np.float32)))

    def put(self, block, captured_at=None):
        with self.lock:
            if self.closed:
                return
            if self.queue.full():
                self.overflows += 1
                # 오래된 자막을 뒤늦게 내보내는 대신 현재 음성부터 다시 처리한다.
                self._reset()
            item = ((self.generation, block) if captured_at is None
                    else (self.generation, block, captured_at))
            self.queue.put_nowait(item)

    def get(self):
        return self.queue.get()

    def boundary(self):
        # 짧은 실제 유실은 앞의 유효한 발화를 보존한다. USB 재연결의 reset과 구분한다.
        self.put(np.zeros(0, dtype=np.float32))

    def publish(self, generation, callback):
        with self.lock:
            if self.closed or generation != self.generation:
                self.stale_results += 1
                return False
            callback()
            return True

    def close(self):
        with self.lock:
            self._reset()
            self.closed = True
            self.queue.put_nowait(None)

    def stats(self):
        with self.lock:
            return {"generation": self.generation, "queue_depth": self.queue.qsize(),
                    "queue_capacity": self.queue.maxsize, "queue_dropped_blocks": self.dropped_blocks,
                    "queue_overflows": self.overflows, "resets": self.resets, "stale_results": self.stale_results}


class DeviceController:
    def __init__(self, cfg, audio, on_status):
        self.cfg = cfg
        self.audio = audio
        self.on_status = on_status
        self.on_event = lambda *args, **kwargs: None
        self.mic_starts = 0
        self.stale_input_blocks = 0
        self.audio_gaps = 0
        self.callback_jitters = 0
        self.capture_overflows = 0
        self.pipe_dropped_blocks = 0
        self.last_sequence = None
        self.last_adc = None
        self.last_capture_overflows = 0
        self.last_pipe_dropped = 0
        self.retry_seconds = cfg["audio"].get("retry_seconds", 5)
        self.health_seconds = cfg["audio"].get("health_timeout_seconds", 2)
        self.open_seconds = cfg["audio"].get("open_timeout_seconds", 5)
        self.context = multiprocessing.get_context("spawn")
        self.stop_event = threading.Event()
        self.wake = threading.Event()
        self.direction_wake = threading.Event()
        self.direction_reset = threading.Event()
        self.lock = threading.Lock()
        self.retry_pending = False
        self.angle = None
        self.sample_seconds = max(0.05, float(cfg["doa"].get("sample_seconds", 0.1)))
        self.history_seconds = max(1.0, float(cfg["doa"].get("history_seconds", 60)))
        capacity = min(2000, math.ceil(self.history_seconds / self.sample_seconds) + 2)
        self.direction_samples = deque(maxlen=capacity)
        self.next_direction_sample = 0
        self.thread = None
        self.direction_thread = None
        self.process = None
        self.blocks = None
        self.control = None
        self.child_stop = None
        self.doa = None
        self.mic_state = "waiting"
        self.doa_state = "waiting" if cfg["doa"].get("enabled", True) else "disabled"
        self.detail = ""
        self.last_status = None
        self.next_mic = self.next_doa = 0
        self.last_block = None
        self.opened_at = 0

    def _accept_block(self, payload, now):
        sequence, callback_at, adc, current, overflows, dropped = BLOCK_HEADER.unpack_from(payload)
        block = np.frombuffer(payload, dtype=np.float32, offset=BLOCK_HEADER.size).copy()
        if now - callback_at > self.health_seconds:
            self.stale_input_blocks += 1
            return
        duration = len(block) / self.cfg["audio"].get("sample_rate", 16000)
        missing = max(0, sequence - self.last_sequence - 1) if self.last_sequence is not None else 0
        overflow_delta = max(0, overflows - self.last_capture_overflows)
        drop_delta = max(0, dropped - self.last_pipe_dropped)
        self.capture_overflows += overflow_delta
        self.pipe_dropped_blocks += drop_delta
        adc_valid = adc > 0 and current >= adc and current - adc < self.health_seconds
        adc_gap = adc - self.last_adc - duration if adc_valid and self.last_adc is not None else 0
        tolerance = self.cfg["audio"].get("gap_tolerance_ms", 10) / 1000
        callback_gap = callback_at - self.last_block if self.last_block is not None else duration
        if missing or overflow_delta or abs(adc_gap) > tolerance:
            self.audio_gaps += 1
            self.on_event("audio_gap", duration_s=max(0, adc_gap), missing_blocks=missing,
                          capture_overflows=overflow_delta, pipe_dropped_blocks=drop_delta)
            self.audio.boundary()
        elif callback_gap > 3 * duration:
            self.callback_jitters += 1
            self.on_event("callback_jitter", duration_s=callback_gap)
        # ADC는 별도 시계다. 콜백에서 제공된 현재 시각과의 차이로 monotonic에 매핑한다.
        captured_end = callback_at - (current - adc) + duration if adc_valid else callback_at
        self.last_block = callback_at
        self.last_sequence = sequence if sequence else None
        self.last_adc = adc if adc_valid else None
        self.last_capture_overflows = overflows
        self.last_pipe_dropped = dropped
        self.audio.put(block, captured_at=captured_end)
        self.mic_state = "ready"
        self.detail = ""

    def start(self):
        with self.lock:
            if self.stop_event.is_set() or self.thread is not None:
                return
            self.thread = threading.Thread(target=self._run, name="device-recovery", daemon=True)
            self.thread.start()
            if self.doa_state != "disabled":
                self.direction_thread = threading.Thread(target=self._run_direction, name="direction", daemon=True)
                self.direction_thread.start()

    def retry(self):
        # 이 콜백은 GUI에서 즉시 반환한다. 요청이 여럿 와도 워커는 하나다.
        with self.lock:
            self.retry_pending = True
        self.wake.set()
        self.direction_wake.set()
        self.on_event("retry")

    def current_angle(self):
        with self.lock:
            return self.angle

    def _record_direction(self, generation, started, finished, angle):
        def record():
            with self.lock:
                self.angle = angle
                self.direction_samples.append((generation, started, finished, angle))
                cutoff = finished - self.history_seconds
                while self.direction_samples and self.direction_samples[0][2] < cutoff:
                    self.direction_samples.popleft()
        self.audio.publish(generation, record)

    def direction_for(self, generation, speech_ranges):
        """이번 발화 중 읽은 표본만 선택한다. 추론 뒤의 현재 각도는 쓰지 않는다."""
        if generation != self.audio.generation or self.mic_state != "ready" or self.doa_state != "ready":
            return None
        cutoff = time.monotonic() - self.history_seconds
        with self.lock:
            samples = list(self.direction_samples)
        angles = []
        for sample_generation, started, finished, angle in samples:
            if sample_generation != generation or started < cutoff:
                continue
            # USB가 기다린 구간까지 발화 안에 있어야 다른 화자 표본을 섞지 않는다.
            if any(begin <= started <= finished <= end for begin, end in speech_ranges):
                angles.append(angle)
        if len(angles) < self.cfg["doa"].get("min_samples", 2):
            return None
        center, _, consensus, _, _ = _robust_center(
            angles, window=self.cfg["doa"].get("cluster_window_degrees", 30)
        )
        if consensus < self.cfg["doa"].get("min_consensus", 0.7):
            return None
        return center

    def _status(self):
        state = (self.mic_state, self.doa_state, self.detail)
        if state != self.last_status:
            self.last_status = state
            self.on_status(*state)

    def _start_mic(self, now):
        self.mic_state = "connecting"
        self.detail = ""
        self._status()
        self.blocks, child_blocks = self.context.Pipe(duplex=False)
        self.control, child_control = self.context.Pipe(duplex=False)
        # 공유 Event의 잠금을 쥔 채 자식이 죽을 수 있어 종료 신호도 파이프로 보낸다.
        child_stop, self.child_stop = self.context.Pipe(duplex=False)
        self.process = self.context.Process(
            target=capture_process,
            args=(self.cfg["audio"], child_blocks, child_control, child_stop),
            name="microphone-capture", daemon=True,
        )
        try:
            self.process.start()
            self.mic_starts += 1
            self.on_event("mic_start", capture_pid=self.process.pid)
        finally:
            child_control.close()
            child_blocks.close()
            child_stop.close()
        self.opened_at = now
        self.last_block = None

    def _close_mic(self):
        if self.process is not None:
            try:
                self.child_stop.send_bytes(b"stop")
            except (BrokenPipeError, OSError):
                pass
            # 고장 난 드라이버가 close에서 멈춰도 다음 프로세스를 중복 생성하지 않는다.
            if self.process.pid is not None:
                self.process.join(0.3)
                if self.process.is_alive():
                    self.process.terminate()
                    self.process.join(0.3)
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(0.3)
                if self.process.is_alive():
                    raise RuntimeError("이전 녹음 프로세스가 종료되지 않았습니다.")
            self.process.close()
            self.process = None
        if self.control is not None:
            self.control.close()
            self.control = None
        if self.blocks is not None:
            self.blocks.close()
            self.blocks = None
        if self.child_stop is not None:
            self.child_stop.close()
            self.child_stop = None
        self.last_block = None
        self.last_sequence = None
        self.last_adc = None
        self.last_capture_overflows = 0
        self.last_pipe_dropped = 0

    def _mic_failed(self, message, reason="driver_error"):
        self.on_event("mic_failure", failure_reason=reason)
        self.mic_state = "waiting"
        self.detail = message
        self.audio.reset()
        with self.lock:
            self.angle = None
            self.direction_samples.clear()
        if self.doa_state != "disabled":
            self.doa_state = "waiting"
        self.direction_reset.set()
        self.direction_wake.set()
        self._status()
        self._close_mic()
        self.next_mic = time.monotonic() + self.retry_seconds

    def _poll_mic(self, now):
        if self.control.poll():
            try:
                kind, message = self.control.recv()
            except EOFError:
                kind, message = "error", "녹음 프로세스가 종료되었습니다."
            if kind == "error":
                self._mic_failed(message, reason="capture_error")
                return
        if not self.process.is_alive():
            self._mic_failed("녹음 프로세스가 종료되었습니다.", reason="process_exit")
            return
        # 한 번에 큐 용량만큼만 읽어 방향 확인/종료 요청을 굶기지 않는다.
        for _ in range(self.cfg["audio"].get("queue_max_blocks", 100)):
            if not self.blocks.poll():
                break
            payload = self.blocks.recv_bytes()
            self._accept_block(payload, now)
        deadline = (self.opened_at + self.open_seconds if self.last_block is None
                    else self.last_block + self.health_seconds)
        if now > deadline:
            self._mic_failed("마이크에서 오디오가 도착하지 않습니다.", reason="input_timeout")

    def _close_doa(self):
        with self.lock:
            self.angle = None
            self.direction_samples.clear()
        if self.doa is not None:
            try:
                self.doa.close()
            except Exception as exc:
                print(f"[방향] 자원 정리 실패: {exc}", flush=True)
            self.doa = None
        if self.doa_state != "disabled":
            self.doa_state = "waiting"

    def _poll_doa(self, now):
        if self.doa_state == "disabled" or self.mic_state != "ready":
            return
        if self.doa is None and now >= self.next_doa:
            self.doa_state = "connecting"
            self._status()
            try:
                self.doa = DoaTracker(self.cfg["doa"])
                self.doa.raw_angle()  # 발견만 아니라 실제 읽기까지 성공해야 연결됨이다.
                self.doa_state = "ready"
            except Exception as exc:
                print(f"[방향] 연결 실패: {exc}", flush=True)
                self.on_event("error", stage="direction", error_type=type(exc).__name__)
                self._close_doa()
                self.next_doa = time.monotonic() + self.retry_seconds
        if self.doa is not None and now >= self.next_direction_sample:
            try:
                generation = self.audio.generation
                started = time.monotonic()
                # 발화 사이 EMA 관성이 다음 화자에 남지 않도록 원본 표본을 모은다.
                angle = (self.cfg["doa"].get("front_offset", 0) - self.doa.raw_angle()) % 360.0
                finished = time.monotonic()
                self._record_direction(generation, started, finished, angle)
                self.next_direction_sample = finished + self.sample_seconds
            except Exception as exc:
                print(f"[방향] 읽기 실패: {exc}", flush=True)
                self.on_event("error", stage="direction", error_type=type(exc).__name__)
                self._close_doa()
                self.next_doa = time.monotonic() + self.retry_seconds

    def _run(self):
        try:
            while not self.stop_event.is_set():
                now = time.monotonic()
                with self.lock:
                    retry, self.retry_pending = self.retry_pending, False
                if retry:
                    self.next_mic = self.next_doa = 0
                try:
                    if self.process is None and now >= self.next_mic:
                        self._start_mic(now)
                    if self.process is not None:
                        self._poll_mic(now)
                except Exception as exc:
                    print(f"[마이크] 연결 실패: {exc}", flush=True)
                    self.on_event("error", stage="mic", error_type=type(exc).__name__)
                    try:
                        self._mic_failed("연결에 실패했습니다. 케이블과 USB 권한을 확인해주세요.")
                    except Exception as cleanup_error:
                        print(f"[마이크] 자원 정리 실패: {cleanup_error}", flush=True)
                        self.mic_state = "failed"
                        self.detail = "이전 연결을 정리하지 못했습니다. 앱을 다시 실행해주세요."
                        self.stop_event.set()
                self._status()
                self.wake.wait(0.05)
                self.wake.clear()
        finally:
            try:
                self._close_mic()
            except Exception as exc:
                print(f"[마이크] 종료 실패: {exc}", flush=True)

    def _run_direction(self):
        # USB가 300ms 기다리는 동안에도 마이크 파이프는 계속 비워야 한다.
        # 워커는 하나만 만들고 모든 재연결에서 재사용한다.
        try:
            while not self.stop_event.is_set():
                if self.direction_reset.is_set() or self.mic_state != "ready":
                    self._close_doa()
                    self.direction_reset.clear()
                else:
                    self._poll_doa(time.monotonic())
                self._status()
                self.direction_wake.wait(0.05)
                self.direction_wake.clear()
        finally:
            self._close_doa()

    def stop(self):
        with self.lock:
            self.stop_event.set()
        self.audio.close()
        self.wake.set()
        self.direction_wake.set()
        if self.thread is not None:
            self.thread.join(2)
        if self.direction_thread is not None:
            self.direction_thread.join(2)
