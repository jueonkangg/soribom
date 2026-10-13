"""재연결된 스피커를 매번 새로 열고 재생 프로세스의 응답 시간을 제한한다."""
import shutil
import subprocess
import threading
import time

import numpy as np


class PulseOutput:
    def __init__(self, cfg):
        self.sink = cfg.get("output_sink")
        self.address = cfg.get("bluetooth_address")
        self.margin = max(0.1, float(cfg.get("playback_timeout_margin_seconds", 3)))
        self.lock = threading.Lock()
        self.process = None
        self.closed = False

    def _sink_available(self):
        if not self.sink:
            return True
        result = subprocess.run(["pactl", "list", "short", "sinks"],
                                capture_output=True, text=True, timeout=2)
        return result.returncode == 0 and any(
            len(parts) > 1 and parts[1] == self.sink
            for parts in (line.split() for line in result.stdout.splitlines()))

    def prepare(self, reconnect=False):
        if self.closed:
            raise RuntimeError("말하기가 종료되었습니다.")
        if not shutil.which("paplay"):
            raise RuntimeError("시스템 음성 재생 도구를 찾을 수 없습니다.")
        if self._sink_available():
            return
        if reconnect and self.address:
            # 모델/마이크를 다시 열지 않고 스피커 한 대만 연결한다.
            subprocess.run(["bluetoothctl", "--timeout", "5", "connect", self.address],
                           capture_output=True, timeout=6)
            deadline = time.monotonic() + 2
            while not self.closed:
                if self._sink_available():
                    return
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.1)
        raise RuntimeError("블루투스 스피커가 준비되지 않았습니다. 전원과 연결을 확인해주세요.")

    def play(self, samples, sample_rate, on_start):
        self.prepare()
        command = ["paplay", "--raw", "--format=float32le", "--channels=1",
                   f"--rate={sample_rate}", "--client-name=소리봄", "--latency-msec=100"]
        if self.sink:
            command.append(f"--device={self.sink}")
        with self.lock:
            if self.closed:
                raise RuntimeError("말하기가 종료되었습니다.")
            process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            self.process = process
        try:
            on_start()
            # 음성은 디스크에 저장하지 않고 표준 입력으로만 보낸다.
            process.communicate(np.asarray(samples, dtype="<f4").tobytes(),
                                timeout=len(samples) / sample_rate + self.margin)
            if process.returncode != 0 or self.closed:
                raise RuntimeError("스피커 연결이 끊겼거나 음성 출력에 실패했습니다.")
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("스피커 재생 응답 시간이 초과됐습니다.") from exc
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate()
            with self.lock:
                if self.process is process:
                    self.process = None

    def close(self):
        with self.lock:
            self.closed = True
            if self.process is not None and self.process.poll() is None:
                self.process.kill()
