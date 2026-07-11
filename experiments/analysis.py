"""이해도 실험 분석 — 대응표본 t-검정, 95% 신뢰구간, 효과크기.

p값 하나만 보고하지 않는다. 신뢰구간과 효과크기를 함께 보고해야
"통계적으로 유의하다"가 아니라 "실제로 얼마나 도움이 되는가"를 말할 수 있다.

사용법:
    python analysis.py data/scores.csv

CSV 형식 (참가자 식별 정보 없음):
    id,order,score_device,score_control
    1,device_first,17,12
    2,control_first,15,13
    ...
"""
import sys

import numpy as np
import pandas as pd
from scipy import stats


def analyze(csv_path: str) -> None:
    df = pd.read_csv(csv_path)
    device = df["score_device"].to_numpy(float)
    control = df["score_control"].to_numpy(float)
    diff = device - control
    n = len(diff)

    mean_d = diff.mean()
    sd_d = diff.std(ddof=1)
    se_d = sd_d / np.sqrt(n)

    # 대응표본 t-검정 (단측: 단말 사용이 더 높다)
    t_stat, p_two = stats.ttest_rel(device, control)
    p_one = p_two / 2 if t_stat > 0 else 1 - p_two / 2

    # 95% 신뢰구간
    crit = stats.t.ppf(0.975, df=n - 1)
    ci = (mean_d - crit * se_d, mean_d + crit * se_d)

    # 효과크기 (Cohen's d_z)
    d_z = mean_d / sd_d

    print(f"n = {n}")
    print(f"단말 사용  평균 = {device.mean():.2f} (SD {device.std(ddof=1):.2f})")
    print(f"단말 미사용 평균 = {control.mean():.2f} (SD {control.std(ddof=1):.2f})")
    print(f"평균 차이 = {mean_d:+.2f}점")
    print(f"95% 신뢰구간 = [{ci[0]:+.2f}, {ci[1]:+.2f}]")
    print(f"t({n - 1}) = {t_stat:.3f}, p(단측) = {p_one:.4f}")
    print(f"효과크기 Cohen's d_z = {d_z:.3f}")

    if p_one < 0.05:
        print("\n→ 귀무가설 기각. 단말 사용 시 이해도가 유의하게 높다.")
    else:
        print("\n→ 귀무가설을 기각하지 못했다.")

    # 순서 효과 점검 (counterbalancing 이 잘 작동했는지)
    if "order" in df.columns and df["order"].nunique() == 2:
        groups = [g["score_device"].to_numpy(float) - g["score_control"].to_numpy(float)
                  for _, g in df.groupby("order")]
        _, p_order = stats.ttest_ind(*groups)
        print(f"순서 효과 점검: p = {p_order:.4f} "
              f"({'문제 없음' if p_order > 0.05 else '순서 효과 의심 — 확인 필요'})")


if __name__ == "__main__":
    analyze(sys.argv[1] if len(sys.argv) > 1 else "data/scores.csv")
