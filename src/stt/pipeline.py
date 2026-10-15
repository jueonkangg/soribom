"""전사 중에도 VAD가 입력을 소비하도록 발화만 작은 유한 큐에 보관한다."""
from collections import deque
import threading
import time


class UtteranceBuffer:
    def __init__(self, capacity=4, max_age_seconds=0, speech_capacity=32):
        self.capacity = max(1, int(capacity))
        self.max_age = max(0, float(max_age_seconds))
        self.items = deque()
        self.condition = threading.Condition()
        self.closed = False
        self.dropped = 0
        self.capacity_dropped = 0
        self.expired = 0
        self.speech_capacity = max(self.capacity, int(speech_capacity))
        self.speech_paused = False

    def hold_for_speech(self, paused):
        with self.condition:
            self.speech_paused = paused
            if paused:
                # 의도적으로 기다리는 발화를 일반 과부하의 오래된 발화로 버리지 않는다.
                self.items = deque(item[:5] + (True,) for item in self.items)

    def put(self, generation, chunk, ranges, subject):
        with self.condition:
            if self.closed:
                return
            retained = self.speech_paused or any(item[5] for item in self.items)
            capacity = self.speech_capacity if retained else self.capacity
            if len(self.items) >= capacity:
                self.items.popleft()
                self.dropped += 1
                self.capacity_dropped += 1
            self.items.append((generation, chunk, ranges, subject, time.monotonic(), retained))
            self.condition.notify()

    def get(self):
        with self.condition:
            while True:
                while not self.items and not self.closed:
                    self.condition.wait()
                if self.closed:
                    return None
                item = self.items.popleft()
                end = item[2][-1][1] if item[2] else item[4]
                if self.max_age == 0 or item[5] or time.monotonic() - end <= self.max_age:
                    return item[:4]
                self.dropped += 1
                self.expired += 1

    def stats(self):
        with self.condition:
            return {"utterance_queue_depth": len(self.items), "utterance_dropped": self.dropped,
                    "utterance_capacity_dropped": self.capacity_dropped, "utterance_expired": self.expired}

    def close(self):
        with self.condition:
            self.closed = True
            self.items.clear()
            self.condition.notify_all()


def error_category(exc):
    # 메시지는 분류에만 사용하고 진단 파일에는 고정 문자열만 보낸다.
    text = str(exc).lower()
    if isinstance(exc, MemoryError) or "out of memory" in text:
        return "memory"
    if "cuda" in text or "cublas" in text or "cudnn" in text:
        return "cuda"
    if isinstance(exc, (ValueError, TypeError)):
        return "input"
    return "unknown"
