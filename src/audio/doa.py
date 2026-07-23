"""ReSpeaker(XMOS XVF-3000)에서 도래각(DOA)을 읽는다.

XMOS 칩이 방향 계산을 하드웨어에서 처리하므로 Jetson은 USB로 각도만 읽으면 된다.

읽는 방법(USB 튜닝 파라미터 규격)은 ReSpeaker 공식 예제를 따른다.
출처: https://github.com/respeaker/usb_4_mic_array (tuning.py, Apache-2.0)

⚠️ 안전 주의: 확인되지 않은 파라미터 좌표(id, offset)를 시험 삼아 읽지 말 것.
   잘못된 벤더 제어 요청은 XMOS 펌웨어를 다운시켜 장치가 USB에서 사라진다
   (복구하려면 물리적으로 다시 꽂아야 함). 검증된 DOAANGLE 만 사용한다.
"""
import struct

import usb.core
import usb.util


# 검증된 파라미터 = (id, offset). respeaker tuning.py의 PARAMETERS 표.
#   DOAANGLE : 도래각 0~359 (읽기전용 int). id=21, offset=0 로 실측 확인됨.
_DOAANGLE = (21, 0)
_CTRL_TIMEOUT_MS = 100000


class DoaTracker:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.front_offset = cfg.get("front_offset", 0)   # 앞 방향 보정(케이스 후 확정)
        self.smoothing = cfg.get("smoothing", 0.3)       # EMA 계수(클수록 민감)
        self._angle = None                               # 평활화된 화면 각도

        self.dev = usb.core.find(
            idVendor=cfg["vendor_id"], idProduct=cfg["product_id"]
        )
        if self.dev is None:
            raise RuntimeError("ReSpeaker를 USB에서 못 찾음 (연결·전원 확인)")

    def _read_int(self, param) -> int:
        """벤더 제어 전송으로 정수 파라미터 하나를 읽는다.

        8바이트(int32 두 개)를 받아 첫 번째가 값이다.
        wValue = 0x80(읽기) | offset | 0x40(정수), wIndex = 파라미터 id.
        """
        param_id, offset = param
        cmd = 0x80 | offset | 0x40
        response = self.dev.ctrl_transfer(
            usb.util.CTRL_IN | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE,
            0, cmd, param_id, 8, _CTRL_TIMEOUT_MS,
        )
        value, _ = struct.unpack("ii", response.tobytes())
        return value

    def raw_angle(self) -> int:
        """칩이 준 원본 도래각(0~359°). 캘리브레이션용."""
        return self._read_int(_DOAANGLE)

    def current(self) -> float:
        """현재 화자 방향(화면 각도 0~360°, 앞=0° 시계방향).

        칩 각도를 화면 좌표로 바꾸고 지수이동평균으로 부드럽게 따라간다.

        '조용할 때 방향이 튀는 것'은 여기서 막지 않는다. 통합 단계(main.py)에서
        오디오 VAD가 발화를 감지했을 때만 current()를 읽으면 자연히 게이팅된다.
        (칩의 음성감지 파라미터를 USB로 직접 읽는 방법도 있으나, 좌표를 잘못
         짚으면 장치가 다운돼 위험하므로 쓰지 않는다.)
        """
        # 칩 각도 → 화면 각도: 앞이 0°, 시계 방향으로 증가.
        screen = (self.front_offset - self.raw_angle()) % 360.0

        if self._angle is None:
            self._angle = screen                 # 첫 값은 그대로
        else:
            # 각도는 원형이라, 최단 경로(-180~180°)로 smoothing 비율만큼 이동한다.
            diff = ((screen - self._angle + 180) % 360) - 180
            self._angle = (self._angle + self.smoothing * diff) % 360
        return self._angle


def _angle_diff(a: float, b: float) -> float:
    """두 각도의 최단 차이(0~180°)."""
    return abs(((a - b + 180) % 360) - 180)


# ---------------------------------------------------------------------------
# 자체 테스트(가이드형, Phase 2): 방향마다 raw 각도 · 화면 각도 · 흔들림 · 오차를 잰다.
#   - 화면 각도 = front_offset로 변환 + 평활화한 값(실제 화살표가 가리킬 방향)
#   - 흔들림   = 3초간 화면 각도가 움직인 폭(작을수록 평활화가 잘 됨)
#   - 오차     = 화면 각도 vs 그 방향의 기대 각도(앞0·오른90·뒤180·왼270°)
# 결과는 doyu/tests/<날짜>_doa-phase2.txt 로그로 남긴다.
# 말하는 동안만 3초 측정하므로, 게이팅 없이도 값이 안정적으로 잡힌다.
#   실행(반드시 진짜 터미널에서): python src/audio/doa.py
# ---------------------------------------------------------------------------
def _selftest() -> None:
    import os
    import statistics
    import time
    from datetime import datetime
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[2]
    cfg = yaml.safe_load(open(root / "src" / "config.yaml", encoding="utf-8"))["doa"]
    doa = DoaTracker(cfg)

    # 물리 방향 → 화면에서 기대되는 각도(앞=0°, 시계방향).
    expected = {"앞": 0, "오른쪽": 90, "뒤": 180, "왼쪽": 270}
    speak_seconds = 3

    print("방향별 DOA 측정 (Phase 2: 화면각 + 평활화 + 오차)")
    print("안내가 나오면 그 방향에서 Enter → 계속 말하세요.\n")
    cased = input("마이크가 케이스에 고정돼 있나요? (y/n): ").strip().lower() or "n"

    rows = []
    for name, want in expected.items():
        input(f"\n[{name}] 에 서세요. 준비되면 Enter → {speak_seconds}초간 말하세요... ")
        print("  측정 중 — 말하세요!", flush=True)
        raws, screens = [], []
        end = time.time() + speak_seconds
        while time.time() < end:
            raws.append(doa.raw_angle())
            screens.append(doa.current())
            time.sleep(0.15)

        raw_med = statistics.median(raws)
        screen = screens[-1]                 # 평활화된 최종값
        # 흔들림: 첫 값 기준으로 펼쳐(원형 경계 문제 회피) 최대-최소 폭.
        base = screens[0]
        unwrapped = [base + (((s - base + 180) % 360) - 180) for s in screens]
        spread = max(unwrapped) - min(unwrapped)
        err = _angle_diff(screen, want)
        rows.append((name, raw_med, screen, spread, err))
        print(f"  → raw {raw_med:.0f}° | 화면 {screen:.0f}° | 흔들림 {spread:.0f}° | 오차 {err:.0f}°")

    avg_err = statistics.mean(r[4] for r in rows)

    now = datetime.now()
    log_dir = root / "doyu" / "tests"
    os.makedirs(log_dir, exist_ok=True)
    log_path = log_dir / f"{now:%Y-%m-%d}_doa-phase2.txt"
    lines = [
        "=" * 52,
        f"DOA Phase2 (화면각+평활화+오차)  |  {now:%Y-%m-%d %H:%M:%S}",
        f"마이크 케이스 고정: {'예' if cased.startswith('y') else '아니오(잠정값)'}",
        f"config front_offset={cfg.get('front_offset')}, smoothing={cfg.get('smoothing')}",
        f"{'방향':<5}{'raw':>6}{'화면':>6}{'흔들림':>7}{'오차':>6}",
    ]
    for name, raw_med, screen, spread, err in rows:
        lines.append(f"{name:<5}{raw_med:6.0f}{screen:6.0f}{spread:7.0f}{err:6.0f}")
    lines.append(f"평균 DOA 오차: {avg_err:.0f}°  (케이스 전이면 잠정)")
    text = "\n".join(lines) + "\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(text)

    print("\n═══ 요약 ═══")
    print(text)
    print(f"로그 저장: {log_path}")
    print("흔들림이 Phase 1보다 작으면 평활화 성공. 오차 확정은 케이스 후 Phase 8.")


if __name__ == "__main__":
    _selftest()
