"""Exp20 Attempt 2 の primary endpoint (s_early) が実際に評価可能かを測る。

`docs/Exp20_Attempt2_修正・再実験計画.md` §5 は 6/12/18/24 h の
ln(P_t/A_t) 一次回帰の傾きを primary estimand としている。
本スクリプトは legacy light 経路を無効化した状態 (= Attempt 2 の想定状態) で
A0_STATIC / A1_TEMPORAL を freq=0.50・3 seed 走らせ、

  1. 各時点で P_t > 0 かつ A_t > 0 となる有効点が3点以上あるか
  2. s_early の seed 間ばらつき (雑音床)

を測る。V1.11 機構の理論効果量と比べることで、n=3 で検出可能かを判定する。

シミュレーション実験ではなく診断。正式実験ではない。
考察の正本: docs/Exp20_Attempt2_Opus5レビュー.md

    EVOSIM_ROOT=<V1.11 worktree> uv run python .../attempt2_endpoint_power.py
"""
from __future__ import annotations

import math
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(os.environ.get("EVOSIM_ROOT", Path(__file__).resolve().parents[2]))
for _p in (ROOT,
           ROOT / "experiments" / "exp20_v111_phototrophy_invasion",
           ROOT / "experiments" / "exp18_v1101_dynamic_vent"):
    sys.path.insert(0, str(_p))

import numpy as np                        # noqa: E402
import exp18_core                         # noqa: E402
import exp20_core as core                 # noqa: E402
from evosim.simulation import Simulation  # noqa: E402

MARKS = (6, 12, 18, 24)
SEEDS = (20001, 20002, 20003)
FREQ = 0.50

# Attempt 2 の想定状態: physical mode から legacy light 経路を除去した後
Simulation._absorb_light = lambda self, *a, **k: None


def main() -> None:
    f0r = exp18_core.measure_legacy_f0()
    h2f = exp18_core.common_initial_h2_field(f0r)
    header = (f"{'seed':>6}{'env':>13} | "
              + "".join(f"{h}h P/A".rjust(13) for h in MARKS)
              + f"{'有効点':>7}{'s_early':>9}")
    print(header)

    results: dict[str, list[float]] = {}
    for env in ("A1_TEMPORAL", "A0_STATIC"):
        for seed in SEEDS:
            cfg = core.make_cfg(f0r["f0_mol_s"], env)
            sim, _ = core.setup_sim(cfg, seed, h2f, FREQ)
            marks: dict[int, tuple[int, int]] = {}
            for k in range(1, int(24 * 3600 / cfg.dt_seconds) + 1):
                sim.step()
                if not sim.organisms:
                    break
                hours = k * cfg.dt_seconds / 3600.0
                if abs(hours - round(hours)) < 1e-9 and int(round(hours)) in MARKS:
                    photo = sum(1 for o in sim.organisms if o.phototrophy_on)
                    marks[int(round(hours))] = (photo, len(sim.organisms) - photo)

            cells, pts = "", []
            for h in MARKS:
                p, a = marks.get(h, (0, 0))
                cells += f"{p:>6}/{a:<7}"
                if p > 0 and a > 0:
                    pts.append((h, math.log(p / a)))
            if len(pts) >= 3:
                slope = float(np.polyfit([p[0] for p in pts], [p[1] for p in pts], 1)[0]) * 24
                shown = f"{slope:+.3f}"
                results.setdefault(env, []).append(slope)
            else:
                shown = "NA"
            print(f"{seed:>6}{env:>13} | {cells}{len(pts):>7}{shown:>9}", flush=True)

    print()
    print("=" * 72)
    print("雑音床と検出力")
    print("=" * 72)
    for env, vals in results.items():
        if len(vals) < 2:
            continue
        sd = statistics.stdev(vals)
        print(f"  {env}: mean={statistics.mean(vals):+.3f}  SD={sd:.3f}  "
              f"SE(n={len(vals)})={sd / math.sqrt(len(vals)):.3f}  "
              f"符号 {sum(1 for v in vals if v > 0)}正/{sum(1 for v in vals if v < 0)}負")
    if "A1_TEMPORAL" in results and len(results["A1_TEMPORAL"]) >= 2:
        sd = statistics.stdev(results["A1_TEMPORAL"])
        # V1.11 net は maintenance の +0.334% (レビュー §1 の実測)。
        # ancestor の 6-24h log-population 低下へその割合で効くと仮定する。
        drop = 2.22
        eff = drop * 0.00334 * 24 / 18
        print()
        print(f"  V1.11機構の理論効果量 (maintenance の 0.334%) -> s_early 差 ≈ {eff:+.5f}/day")
        print(f"  信号/雑音 = {abs(eff) / sd:.4f}")
        print(f"  2σ検出に必要な seed 数 ≈ {(2 * sd / abs(eff)) ** 2:,.0f}")
        print(f"  Attempt 2 の設計: {len(SEEDS)} seeds")


if __name__ == "__main__":
    main()
