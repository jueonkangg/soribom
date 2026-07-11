"""ReSpeaker(XMOS XVF-3000)에서 도래각(DOA)을 읽는다.

XMOS 칩이 방향 계산을 하드웨어에서 처리하므로 Jetson은 USB로 각도만 읽으면 된다.
"""


class DoaTracker:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self._angle = 0.0

    def current(self) -> float:
        """현재 화자 방향 (0~360도)."""
        # TODO: pyusb 로 ReSpeaker tuning 파라미터(DOAANGLE) 읽기 + 지수이동평균
        raise NotImplementedError
