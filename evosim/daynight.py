"""V1.8 day/night cycle helper (docs/V1.8_一次Energy生態非対称仕様.md §4)。

daylight factorを決める処理を1か所へ集約する。`Simulation.step()` は
tick開始時に一度だけ `daylight_factor()` を呼び、その値を1 step内の
sensing / light supply / light uptake / recorder すべてで共有する
(処理途中でtickを進めて別factorを読んではいけない)。

half-sine固定・**energy中立正規化はしない** (docs/V1.8_Exp13_レビュー判断.md M-1)。
`light_cycle_enabled=False` では常時1.0を返し、V1.7回帰を保つ。
"""
from __future__ import annotations

import math

from .config import Config


def daylight_factor(tick: int, cfg: Config) -> float:
    """そのtickの昼夜factor。範囲は常に [0, 1]。

    period=200 / day_fraction=0.5 では:
      tick 0    (phase=0)   -> 0.0   (sunrise)
      tick 50   (phase=.25) -> 1.0   (midday, u=0.5)
      tick 100  (phase=.5)  -> 0.0   (sunset / night開始)
      tick 100-200          -> 0.0   (night, exactly)
      tick 200              -> 周期repeat (phase=0 に戻る)

    RNGを一切消費しない。
    """
    if not cfg.light_cycle_enabled:
        return 1.0
    period = cfg.light_cycle_period_ticks
    day_fraction = cfg.light_day_fraction
    phase = (tick % period) / period
    if phase < day_fraction:
        u = phase / day_fraction
        return math.sin(math.pi * u)
    return 0.0
