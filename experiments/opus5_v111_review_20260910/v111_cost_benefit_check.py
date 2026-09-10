"""V1.11 phototrophyの benefit / cost 比と、light_absorptionの進化速度を実測する。

確認したいこと:
  1. 既存 organ upkeep は light_absorption の実効コストとして機能するか
  2. photon flux を変えたとき seed phototroph は黒字か
  3. seed absorption から機能水準まで何世代かかるか

シミュレーション実験ではなく解析計算。正式実験ではない。
考察の正本: docs/V1.11_Opus5レビュー.md

    EVOSIM_ROOT=<V1.11 worktree> uv run python .../v111_cost_benefit_check.py
"""
import os
import sys
import math
from pathlib import Path

ROOT = Path(os.environ.get("EVOSIM_ROOT", Path(__file__).resolve().parents[2]))
for p in (ROOT, ROOT / "experiments" / "luca_proxy", ROOT / "experiments" / "exp15_v19"):
    sys.path.insert(0, str(p))

import numpy as np                      # noqa: E402
import run_luca_proxy as luca           # noqa: E402
from evosim import physiology           # noqa: E402
from evosim.config import Config        # noqa: E402
from evosim.organism import Organism    # noqa: E402
from evosim.genome import INITIAL_GENOME, GENE_MIN, GENE_MAX, GENE_SCALE, LIGHT_ABS  # noqa: E402

H, C_L, NA, LAM = 6.62607015e-34, 2.99792458e8, 6.02214076e23, 800e-9
EFF = 0.10       # phototrophy_radiant_to_usable_eff (仕様書 §6.3)
CAP = 30000.0    # phototrophy_h2_bonus_cap_j_per_mol (仕様書 §7.1)
SEED = 0.001     # phototrophy_seed_absorption (仕様書 §4)


def main() -> None:
    cfg = luca.make_cfg("A")

    def org(la: float) -> Organism:
        g = INITIAL_GENOME.copy()
        g[LIGHT_ABS] = la
        return Organism(0, -1, 0, 0, 0, g, 0.0, 0.0, 0.0, 0.0, 0.5)

    p0 = physiology.full_activity_expenditure_rate(org(0.0), cfg)
    r = physiology.physical_radius_m(0.5, cfg)
    area = math.pi * r * r

    def p_inc(flux_umol: float) -> float:
        return flux_umol * 1e-6 * NA * area * (H * C_L / LAM)

    print("=" * 72)
    print("1. light_absorption の benefit / cost   (flux = 1.0 µmol photons/m2/s)")
    print("=" * 72)
    print(f"  非phototrophの P_full = {p0 * 1e15:.5f} fW")
    print(f"  入射power             = {p_inc(1.0) * 1e15:.2f} fW"
          f"  = maintenance の {p_inc(1.0) / p0:.0f} 倍")
    print()
    print(f"  {'light_abs':>10}{'absorpt.':>10}{'P_photo':>11}{'Δcost':>13}{'benefit/cost':>14}")
    for la in (SEED, 0.01, 0.1, 1.0, 5.0):
        cost = physiology.full_activity_expenditure_rate(org(la), cfg) - p0
        gain = p_inc(1.0) * (1 - math.exp(-la)) * EFF
        ratio = gain / cost if cost > 0 else float("inf")
        print(f"  {la:>10}{(1 - math.exp(-la)) * 100:>9.3f}%{gain * 1e15:>10.4f}f"
              f"{cost * 1e15:>12.5f}f{ratio:>13.0f}:1")

    lo, hi = 1e-9, 5.0
    for _ in range(300):
        mid = (lo * hi) ** 0.5
        c = physiology.full_activity_expenditure_rate(org(mid), cfg) - p0
        if p_inc(1.0) * (1 - math.exp(-mid)) * EFF - c < 0:
            lo = mid
        else:
            hi = mid
    print(f"\n  損益分岐 light_absorption = {(lo * hi) ** 0.5:.3e}"
          f"   -> 実質どの遺伝子値でも黒字")

    print()
    print("=" * 72)
    print("2. photon flux 感度   (seed phototroph と進化後 gene=1.0)")
    print("=" * 72)
    m_dry = 0.5 * cfg.matter_unit_to_kgdw
    b = cfg.h2_usable_energy_j_per_mol

    def h2_power(c_molm3: float) -> float:
        return cfg.h2_qmax_mol_per_kgdw_s * (c_molm3 / (c_molm3 + cfg.h2_km_mol_m3)) * m_dry * b

    p_src, p_med = h2_power(10.0), h2_power(0.566)
    print(f"  H2 income @source 10 mM = {p_src * 1e15:.2f} fW"
          f" / @field中央値 566 µM = {p_med * 1e15:.3f} fW")
    print(f"\n  {'flux':>8}{'seed P_photo':>14}{'gene1.0 P_photo':>17}"
          f"{'vs H2@src':>11}{'vs H2@med':>11}")
    for f in (0.01, 0.1, 1.0, 10.0):
        ps = p_inc(f) * (1 - math.exp(-SEED)) * EFF
        pe = p_inc(f) * (1 - math.exp(-1.0)) * EFF
        print(f"  {f:>8}{ps * 1e15:>13.5f}f{pe * 1e15:>16.4f}f"
              f"{pe / p_src:>10.2f}x{pe / p_med:>10.2f}x")

    print()
    print("=" * 72)
    print("3. H2 coupling cap はどこで binding するか")
    print("=" * 72)
    print("  E_photo = min(L, q * CAP) なので、H2が薄いほど cap 側が効く")
    l1 = p_inc(1.0) * (1 - math.exp(-1.0)) * EFF
    print(f"\n  {'H2 [µM]':>9}{'q*CAP':>11}{'L(gene1.0)':>12}{'binding':>10}")
    for c in (0.05, 0.2, 0.55, 1.0, 10.0):
        q = cfg.h2_qmax_mol_per_kgdw_s * (c / (c + cfg.h2_km_mol_m3)) * m_dry
        print(f"  {c * 1000:>9.0f}{q * CAP * 1e15:>10.3f}f{l1 * 1e15:>11.3f}f"
              f"{'  cap' if q * CAP < l1 else '  light':>10}")

    print()
    print("=" * 72)
    print("4. light_absorption の進化速度")
    print("=" * 72)
    sigma = float(INITIAL_GENOME[13])  # mutation_rate
    add_sd = Config().additive_mutation_frac * sigma * GENE_SCALE[LIGHT_ABS]
    print(f"  mutation_rate σ={sigma}, 加算項SD={add_sd:.6f} (seed の {add_sd / SEED:.2f} 倍)")
    rng = np.random.default_rng(0)
    child = np.clip(SEED * np.exp(rng.normal(0, sigma, 200_000))
                    + rng.normal(0, add_sd, 200_000),
                    GENE_MIN[LIGHT_ABS], GENE_MAX[LIGHT_ABS])
    print(f"  seed={SEED} の1世代後 q10/q50/q90 = "
          f"{np.quantile(child, .1):.5f} / {np.quantile(child, .5):.5f} / "
          f"{np.quantile(child, .9):.5f}")
    print(f"  -> 加算項は seed を消さない (良い)。ただし1世代の変化は概ね ±{sigma * 100:.0f}%")
    for target in (0.01, 0.1, 1.0):
        print(f"  seed -> {target}: 毎世代1σ分だけ有利方向へ動いても "
              f"{math.log(target / SEED) / sigma:.0f} 世代")
    print("  現在の計算予算は 10日run で 5-9 世代")


if __name__ == "__main__":
    main()
