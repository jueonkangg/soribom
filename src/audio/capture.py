"""4채널 마이크 어레이에서 오디오를 읽어 큐에 넣는다."""


class MicArray:
    def __init__(self, cfg: dict, sink) -> None:
        self.cfg = cfg
        self.sink = sink

    def start(self) -> None:
        # TODO: sounddevice.InputStream 으로 4채널 캡처 시작
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError
