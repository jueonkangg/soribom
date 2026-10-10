"""마이크와 방향 워커를 하나씩 유지한다. 연결 재시도에서 모델은 건드리지 않는다."""
import multiprocessing
import queue
import struct
import threading
import time

import numpy as np

from audio.capture import capture_process
from audio.doa import DoaTracker


class AudioBuffer:
    """연결 세대 번호로 끊기기 전 오디오/전사 결과가 섞이지 않게 한다."""
    def __init__(self, max_blocks):
        self.queue = queue.Queue(maxsize=max(2, max_blocks))
        self.generation = 0
        self.closed = False
        self.lock = threading.RLock()

    def _reset(self):
        self.generation += 1
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    def reset(self):
        with self.lock:
            if not self.closed:
                self._reset()
                self.queue.put_nowait((self.generation, np.zeros(0, dtype=np.float32)))

    def put(self, block):
        with self.lock:
            if self.closed:
                return
            if self.queue.full():
                # 오래된 자막을 뒤늦게 내보내는 대신 현재 음성부터 다시 처리한다.
                self._reset()
            self.queue.put_nowait((self.generation, block))

    def get(self):
        return self.queue.get()

    def publish(self, generation, callback):
        with self.lock:
            if self.closed or generation != self.generation:
                return False
            callback()
            return True

    def close(self):
        with self.lock:
            self._reset()
            self.closed = True
            self.queue.put_nowait(None)


class DeviceController:
    def __init__(self, cfg, audio, on_status):
        self.cfg = cfg
        self.audio = audio
        self.on_status = on_status
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
        self.direction_generation = None
        self.angle = None
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

    def request_direction(self, generation):
        with self.lock:
            self.direction_generation = generation
            self.angle = None
        self.direction_wake.set()

    def current_angle(self):
        with self.lock:
            return self.angle

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

    def _mic_failed(self, message):
        self.mic_state = "waiting"
        self.detail = message
        self.audio.reset()
        with self.lock:
            self.angle = None
            self.direction_generation = None
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
                self._mic_failed(message)
                return
        if not self.process.is_alive():
            self._mic_failed("녹음 프로세스가 종료되었습니다.")
            return
        # 한 번에 큐 용량만큼만 읽어 방향 확인/종료 요청을 굶기지 않는다.
        for _ in range(self.cfg["audio"].get("queue_max_blocks", 100)):
            if not self.blocks.poll():
                break
            payload = self.blocks.recv_bytes()
            captured_at = struct.unpack("d", payload[:8])[0]
            block = np.frombuffer(payload, dtype=np.float32, offset=8).copy()
            if now - captured_at > self.health_seconds:
                continue
            if self.last_block is not None and captured_at - self.last_block > 3 * self.cfg["audio"]["block_ms"] / 1000:
                self.audio.reset()
            self.last_block = captured_at
            self.audio.put(block)
            self.mic_state = "ready"
            self.detail = ""
        deadline = (self.opened_at + self.open_seconds if self.last_block is None
                    else self.last_block + self.health_seconds)
        if now > deadline:
            self._mic_failed("마이크에서 오디오가 도착하지 않습니다.")

    def _close_doa(self):
        with self.lock:
            self.angle = None
            self.direction_generation = None
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
                self._close_doa()
                self.next_doa = time.monotonic() + self.retry_seconds
        with self.lock:
            generation = self.direction_generation
            self.direction_generation = None
        if self.doa is not None and generation is not None:
            try:
                angle = self.doa.current()
                # 재연결/큐 초기화 전 음성에 해당하는 방향은 사용하지 않는다.
                def set_angle():
                    with self.lock:
                        self.angle = angle
                self.audio.publish(generation, set_angle)
            except Exception as exc:
                print(f"[방향] 읽기 실패: {exc}", flush=True)
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
