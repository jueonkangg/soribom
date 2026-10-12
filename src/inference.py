"""공유 GPU에서 음성 인식/합성이 겹치지 않게 한다. 대기 중인 말하기를 우선한다."""
import threading
import time


class InferenceGate:
    def __init__(self):
        self.condition = threading.Condition()
        self.active = False
        self.speech_waiters = 0

    def run(self, function, *args, speech=False, on_wait=None):
        started = time.monotonic()
        with self.condition:
            if speech:
                self.speech_waiters += 1
            try:
                while self.active or (not speech and self.speech_waiters):
                    self.condition.wait()
                self.active = True
            finally:
                if speech:
                    self.speech_waiters -= 1
        try:
            if on_wait is not None:
                on_wait(time.monotonic() - started)
            return function(*args)
        finally:
            with self.condition:
                self.active = False
                self.condition.notify_all()
