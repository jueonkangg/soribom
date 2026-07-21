"""ReSpeaker(XMOS XVF-3000)에서 도래각(DOA)을 읽는다.

XMOS 칩이 방향 계산을 하드웨어에서 처리하므로 Jetson은 USB로 각도만 읽으면 된다.

읽는 방법(USB 튜닝 파라미터 규격)은 ReSpeaker 공식 예제를 따른다.
출처: https://github.com/respeaker/usb_4_mic_array (tuning.py, Apache-2.0)
"""
import struct

import usb.core
import usb.util


# DOAANGLE 파라미터의 USB 접근 규격 (respeaker tuning.py의 PARAMETERS 표에서 가져옴).
#   파라미터 id = 21, 정수형(int), 읽기 전용(ro), 값 0~359도.
_DOAANGLE_ID = 21
_READ_INT_CMD = 0x80 | 0x40      # 0x80=읽기, 0x40=정수형
_CTRL_TIMEOUT_MS = 100000


class DoaTracker:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        # config의 vendor/product id로 ReSpeaker를 찾는다.
        self.dev = usb.core.find(
            idVendor=cfg["vendor_id"], idProduct=cfg["product_id"]
        )
        if self.dev is None:
            raise RuntimeError("ReSpeaker를 USB에서 못 찾음 (연결·전원 확인)")

    def _read_doa_angle(self) -> int:
        """XMOS 칩에서 현재 도래각(raw, 0~359도)을 읽는다.

        벤더 제어 전송으로 8바이트(int32 두 개)를 받아, 첫 번째가 각도다.
        """
        response = self.dev.ctrl_transfer(
            usb.util.CTRL_IN | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE,
            0,                 # bRequest
            _READ_INT_CMD,     # wValue
            _DOAANGLE_ID,      # wIndex
            8,                 # 받을 길이(바이트)
            _CTRL_TIMEOUT_MS,
        )
        value, _ = struct.unpack("ii", response.tobytes())
        return value

    def current(self) -> float:
        """현재 화자 방향(raw 각도, 0~359도).

        Phase 2에서 화면 좌표 변환·평활화·목소리 게이팅을 여기에 얹는다.
        """
        return float(self._read_doa_angle())


# ---------------------------------------------------------------------------
# 자체 테스트(가이드형): 방향을 하나씩 안내한다. 안내가 나오면 그 방향에 서서
# Enter를 누르고 몇 초간 말하면, 그 방향의 raw 각도를 측정한다.
# 결과는 doyu/tests/<날짜>_doa-direction.txt 로그로 남긴다(같은 날은 이어쓰기).
# 방향마다 값이 다르면 DOA 읽기 성공. 케이스 고정 여부도 함께 기록해서,
# 케이스 조립 후(Phase 8) 캘리브레이션에 어느 측정을 쓸지 구분한다.
#   실행(반드시 진짜 터미널에서): python src/audio/doa.py
# ---------------------------------------------------------------------------
def _selftest() -> None:
    import os
    import statistics
    import time
    from datetime import datetime
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[2]        # 저장소 루트
    cfg = yaml.safe_load(open(root / "src" / "config.yaml", encoding="utf-8"))["doa"]
    doa = DoaTracker(cfg)

    speak_seconds = 3
    directions = ["앞", "왼쪽", "뒤", "오른쪽"]

    print("방향별 DOA 측정. 안내가 나오면 그 방향에서 준비하고 Enter → 계속 말하세요.\n")
    cased = input("마이크가 케이스에 고정돼 있나요? (y/n): ").strip().lower() or "n"

    results = {}
    for name in directions:
        input(f"\n[{name}] 에 서세요. 준비되면 Enter를 누르고 {speak_seconds}초간 말하세요... ")
        print("  측정 중 — 말하세요!", flush=True)
        samples = []
        end = time.time() + speak_seconds
        while time.time() < end:
            samples.append(doa.current())
            time.sleep(0.15)
        results[name] = (statistics.median(samples), min(samples), max(samples), len(samples))
        med, lo, hi, n = results[name]
        print(f"  → [{name}] 약 {med:.0f}°  (범위 {lo:.0f}~{hi:.0f}°, 샘플 {n}개)")

    # 로그 파일로 남긴다: doyu/tests/<날짜>_doa-direction.txt
    now = datetime.now()
    log_dir = root / "doyu" / "tests"
    os.makedirs(log_dir, exist_ok=True)
    log_path = log_dir / f"{now:%Y-%m-%d}_doa-direction.txt"

    lines = ["=" * 44,
             f"DOA 방향 측정  |  {now:%Y-%m-%d %H:%M:%S}",
             f"마이크 케이스 고정: {'예' if cased.startswith('y') else '아니오(잠정값)'}",
             f"config front_offset={cfg.get('front_offset')}, smoothing={cfg.get('smoothing')}",
             "방향별 raw 각도:"]
    for name in directions:
        med, lo, hi, n = results[name]
        lines.append(f"  {name:5} {med:4.0f}°   (범위 {lo:.0f}~{hi:.0f}°, 샘플 {n})")
    text = "\n".join(lines) + "\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(text)

    print("\n═══ 측정 요약 ═══")
    print(text)
    print(f"로그 저장(이어쓰기): {log_path}")
    print("방향마다 값이 다르면 DOA 읽기 성공. 정확한 매핑은 케이스 후 Phase 8에서.")


if __name__ == "__main__":
    _selftest()
