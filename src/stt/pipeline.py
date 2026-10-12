"""전사 중에도 VAD가 입력을 소비하도록 발화만 작은 유한 큐에 보관한다."""
from collections import deque
import threading
import time


class UtteranceBuffer:
    def __init__(self, capacity=4, max_age_seconds=6):
        self.capacity = max(1, int(capacity))
        self.max_age = max(1, float(max_age_seconds))
        self.items = deque()
        self.condition = threading.Condition()
        self.closed = False
        self.dropped = 0

    def put(self, generation, chunk, ranges, subject):
        with self.condition:
            if self.closed:
                return
            if len(self.items) >= self.capacity:
                self.items.popleft()
                self.dropped += 1
            self.items.append((generation, chunk, ranges, subject, time.monotonic()))
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
                if time.monotonic() - end <= self.max_age:
                    return item[:4]
                self.dropped += 1

    def stats(self):
        with self.condition:
            return {"utterance_queue_depth": len(self.items), "utterance_dropped": self.dropped}

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
