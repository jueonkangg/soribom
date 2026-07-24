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


def _circular_mean(angles: list) -> float:
    """각도(원형)의 평균. 0°/360° 경계에서 틀리지 않게 벡터로 바꿔 평균낸다.

    예: 359° 와 1° 의 평균은 산술평균(180°)이 아니라 0° 여야 한다.
    """
    import math
    x = sum(math.cos(math.radians(a)) for a in angles)
    y = sum(math.sin(math.radians(a)) for a in angles)
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return angles[0]
    return math.degrees(math.atan2(y, x)) % 360.0


def _robust_center(angles: list, window: float = 30.0):
    """반사음·순간 오검출에 흔들리지 않는 '중심 방향'을 찾는다.

    왜 이렇게: 말하는 동안 진짜 방향은 한 곳에 몰리고(dominant cluster),
    벽 반사음·조용한 순간의 잡값은 흩어진다. 그래서 흩어진 값을 버리고
    가장 많이 몰린 곳만 평균낸다. (칩 음성감지를 USB로 읽는 건 장치 다운
    위험이 있어 안 쓰고, 대신 이 통계적 방법으로 잡값을 거른다.)

    방법:
      1) 이웃(±window°)이 가장 많은 표본을 중심 후보로 고른다(최빈 방향).
      2) 그 후보 근처 표본만 남겨 원형 평균 → 중심을 정하고 한 번 더 정제.
      3) 남은 표본의 퍼짐(중심에서 최대로 벗어난 각)과 채택 비율을 함께 낸다.
    반환: (중심각, 퍼짐°, 채택비율 0~1, 채택수, 전체수)
    """
    if not angles:
        return 0.0, 999.0, 0.0, 0, 0
    best_i, best_cnt = 0, -1
    for i, a in enumerate(angles):
        cnt = sum(1 for b in angles if _angle_diff(a, b) <= window)
        if cnt > best_cnt:
            best_cnt, best_i = cnt, i
    center = _circular_mean([b for b in angles if _angle_diff(angles[best_i], b) <= window])
    inliers = [b for b in angles if _angle_diff(center, b) <= window]
    center = _circular_mean(inliers)                 # 한 번 더 정제
    inliers = [b for b in angles if _angle_diff(center, b) <= window]
    spread = max((_angle_diff(center, b) for b in inliers), default=0.0)
    return center, spread, len(inliers) / len(angles), len(inliers), len(angles)


def _measure_direction(doa, seconds: float, interval: float = 0.1) -> list:
    """한 방향을 측정: 칩의 raw 각도를 촘촘히 모은다. (평활화 안 된 원본을 쓴다)

    평활화된 current()는 관성이 있어 반사음에 끌려가면 회복이 느리다.
    그래서 원본 raw 를 많이 모아 통계로 거르는 편이 더 정확하다.
    """
    import time
    raws = []
    end = time.time() + seconds
    while time.time() < end:
        try:
            raws.append(doa.raw_angle() % 360)
        except Exception:
            pass                                     # 간헐적 USB 읽기 실패는 건너뛴다
        time.sleep(interval)
    return raws


# ---------------------------------------------------------------------------
# 자체 테스트(Phase 8 — 케이스 고정 후 최종 보정/측정).
#   개선점: 반사음·잡값을 통계로 제거(_robust_center)하고, 방향마다
#   '안정/불안정'을 판정해 불안정하면 그 자리에서 다시 재게 한다.
#   그래야 §8 DOA 오차를 믿을 수 있는 값으로 얻는다.
#     - raw 중심 = 잡값 뺀 진짜 방향 / 퍼짐 = 남은 값이 얼마나 몰렸나(작을수록 좋음)
#     - 채택% = 전체 중 몇 %가 한 곳에 몰렸나(높을수록 좋음)
#     - 오차 = 화면각(= front_offset - raw) vs 기대각(앞0·오른90·뒤180·왼270°)
#   front_offset 은 건드리지 않는다(앞·뒤가 맞으면 이미 정상). 여기선 '측정'만 한다.
#   실행(반드시 진짜 터미널에서): python src/audio/doa.py
# ---------------------------------------------------------------------------
def _selftest() -> None:
    import os
    import statistics
    from datetime import datetime
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[2]
    cfg = yaml.safe_load(open(root / "src" / "config.yaml", encoding="utf-8"))["doa"]
    doa = DoaTracker(cfg)
    front_offset = cfg.get("front_offset", 0)

    # 물리 방향 → 화면에서 기대되는 각도(앞=0°, 시계방향).
    expected = {"앞": 0, "오른쪽": 90, "뒤": 180, "왼쪽": 270}
    SECONDS = 4.0            # 표본을 넉넉히 모은다
    STABLE_SPREAD = 25.0     # 남은 값의 퍼짐이 이 이내면 '안정'
    MIN_KEEP = 0.60          # 표본의 60% 이상이 한 곳에 몰려야 신뢰

    print("방향별 DOA 측정 (Phase 8: 잡값 제거 + 안정성 판정)")
    print(f"각 방향에 정확히 서서, 끊지 말고 '크게 계속' 말하세요(약 {SECONDS:.0f}초).\n")
    cased = (input("마이크가 케이스에 고정돼 있나요? (y/n): ").strip().lower() or "n")

    rows = []
    for name, want in expected.items():
        while True:
            input(f"\n[{name}] 방향에 정확히 서세요. 준비되면 Enter → {SECONDS:.0f}초간 크게 말하세요... ")
            print("  측정 중 — 계속 말하세요!", flush=True)
            raws = _measure_direction(doa, SECONDS)
            if not raws:
                print("  ⚠️ USB에서 값을 못 읽었습니다. 연결 확인 후 다시.")
                continue
            raw_c, spread, keep, n_in, n_all = _robust_center(raws)
            screen = (front_offset - raw_c) % 360.0
            err = _angle_diff(screen, want)
            stable = spread <= STABLE_SPREAD and keep >= MIN_KEEP
            print(f"  → raw {raw_c:.0f}° | 화면 {screen:.0f}° | 퍼짐 {spread:.0f}° "
                  f"| 채택 {n_in}/{n_all}({keep*100:.0f}%) | 오차 {err:.0f}° "
                  f"| {'안정 ✅' if stable else '불안정 ⚠️'}")
            if not stable:
                retry = (input("  불안정합니다. 다시 잴까요? (Y/n): ").strip().lower() or "y")
                if retry.startswith("y"):
                    continue
            rows.append((name, raw_c, screen, spread, keep, err, stable))
            break

    stable_errs = [r[5] for r in rows if r[6]]
    avg_err = statistics.mean(stable_errs) if stable_errs else float("nan")

    now = datetime.now()
    log_dir = root / "doyu" / "tests"
    os.makedirs(log_dir, exist_ok=True)
    log_path = log_dir / f"{now:%Y-%m-%d}_doa-phase8.txt"
    lines = [
        "=" * 60,
        f"DOA Phase8 (잡값제거 robust + 안정성판정)  |  {now:%Y-%m-%d %H:%M:%S}",
        f"마이크 케이스 고정: {'예' if cased.startswith('y') else '아니오(잠정값)'}",
        f"config front_offset={front_offset}",
        f"{'방향':<5}{'raw':>6}{'화면':>6}{'퍼짐':>6}{'채택%':>7}{'오차':>6}  판정",
    ]
    for name, raw_c, screen, spread, keep, err, stable in rows:
        lines.append(f"{name:<5}{raw_c:6.0f}{screen:6.0f}{spread:6.0f}{keep*100:7.0f}{err:6.0f}  "
                     f"{'안정' if stable else '불안정'}")
    if stable_errs:
        lines.append(f"평균 DOA 오차(안정 {len(stable_errs)}개 방향): {avg_err:.1f}°")
    else:
        lines.append("평균 DOA 오차: 측정 실패(안정된 방향 없음) — 환경 점검 후 재측정")
    text = "\n".join(lines) + "\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(text)

    print("\n═══ 요약 ═══")
    print(text)
    print(f"로그 저장: {log_path}")
    if len(stable_errs) == 4:
        print(f"✅ 네 방향 모두 안정. 평균 오차 {avg_err:.1f}° — 이 값을 §8 지표로 씁니다.")
    else:
        print("⚠️ 불안정한 방향이 있습니다. 반사가 적은 곳에서 더 크게·가까이 다시 측정하세요.")


if __name__ == "__main__":
    _selftest()
