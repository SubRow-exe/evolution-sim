"""Exp22 の photon flux 水準を、V1.11機構の理論効果量へ変換する。

`docs/Exp22_実験計画.md` §6 の flux 水準と §12.1 の閾値
(median R_E(48-72h) >= +1%) を突き合わせ、どの水準が
preferred candidate になるかを実行前に予測する。

あわせて §6 の `flux = 0` が Config validation を通らないこと
(`evosim/config.py` の physical_light_enabled + flux<=0 チェック) を示す。

シミュレーション実験ではなく解析計算。正式実験ではない。
考察の正本: docs/Exp21_Exp22_Opus5レビュー.md

    EVOSIM_ROOT=<V1.11 worktree> uv run python .../exp22_flux_effect_table.py
"""
from __future__ import annotations

import dataclasses
import math
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("EVOSIM_ROOT", Path(__file__).resolve().parents[2]))
for _p in (ROOT,
           ROOT / "experiments" / "exp21_starvation_horizon_competition",
           ROOT / "experiments" / "exp18_v1101_dynamic_vent"):
    sys.path.insert(0, str(_p))

import exp18_core                       # noqa: E402
import run_exp21 as exp21               # noqa: E402
from evosim import physiology           # noqa: E402
from evosim.config import Config        # noqa: E402
from evosim.organism import Organism    # noqa: E402
from evosim.genome import INITIAL_GENOME, LIGHT_ABS  # noqa: E402

# docs/Exp22_実験計画.md §5 / §6
LIGHT_ABSORPTION = 0.01
FLUXES = (0.0, 0.015, 0.05, 0.15, 0.5, 1.5)
R_E_THRESHOLD_PCT = 1.0


def _light_cfg(base: Config, flux: float) -> Config:
    return dataclasses.replace(
        base,
        physical_light_enabled=True,
        light_photon_flux_umol_m2_s=flux,
        light_effective_wavelength_nm=800.0,
        phototrophy_radiant_to_usable_eff=0.10,
    )


def main() -> None:
    f0r = exp18_core.measure_legacy_f0()
    base = exp21.make_cfg(f0r["f0_mol_s"], "A0_STATIC")

    genome = INITIAL_GENOME.copy()
    genome[LIGHT_ABS] = LIGHT_ABSORPTION
    photo = Organism(0, -1, 0, 0, 0, genome, 0.0, 0.0, 0.0, 0.0, 0.5)
    photo.phototrophy_on = True
    photo.photo_structural_n_mol = 1e3        # N制限を外した上界
    ancestor = Organism(0, -1, 0, 0, 0, INITIAL_GENOME.copy(), 0.0, 0.0, 0.0, 0.0, 0.5)
    maintenance = physiology.full_activity_expenditure_rate(ancestor, base)

    print("=" * 74)
    print("1. flux=0 は Config validation を通るか (§6 の negative control)")
    print("=" * 74)
    try:
        _light_cfg(base, 0.0)
        print("  flux=0.0 : 構築できた")
    except ValueError as exc:
        print(f"  flux=0.0 : ValueError -> {exc}")
        print("  -> physical_light_enabled=True のまま flux=0 にはできない。")
        print("     physical_light_enabled=False に落とすと、構造N assembly も")
        print("     同じフラグで gate されている (simulation.py) ため停止し、")
        print("     §2 H4 の structural N cost control が成立しない。")

    print()
    print("=" * 74)
    print(f"2. flux 水準と理論効果量  (light_absorption={LIGHT_ABSORPTION}, "
          f"absorptance={100 * (1 - math.exp(-LIGHT_ABSORPTION)):.3f}%)")
    print("=" * 74)
    print(f"  ancestor maintenance = {maintenance * 1e15:.4f} fW")
    print()
    print(f"  {'flux':>8}{'P_incident':>13}{'P_usable':>12}{'/maintenance':>14}"
          f"{'期待R_E':>10}{'§12.1':>8}")
    for flux in FLUXES:
        if flux <= 0.0:
            print(f"  {flux:>8}{'--':>13}{'--':>12}{'--':>14}{'--':>10}{'構築不可':>8}")
            continue
        cfg = _light_cfg(base, flux)
        _, _, usable = physiology.photo_power_chain_w(photo, cfg)
        pct = 100.0 * usable / maintenance
        verdict = "PASS" if pct >= R_E_THRESHOLD_PCT else "FAIL"
        print(f"  {flux:>8}{physiology.physical_light_incident_power_w(photo, cfg) * 1e15:>12.4f}f"
              f"{usable * 1e15:>11.5f}f{pct:>13.3f}%{pct:>9.2f}%{verdict:>8}")

    print()
    print("  期待R_E の根拠: 飢餓局面では E は概ね maintenance 速度で減る。")
    print("  credit が maintenance の x% を肩代わりすると E の減少が x% 遅くなり、")
    print("  積分比 R_E は一次近似で x% になる。")
    print()
    print(f"  -> §12.1 の閾値 +{R_E_THRESHOLD_PCT:.0f}% は 0.015 (0.39%) と 0.05 (1.31%)")
    print("     の間に落ちる。preferred candidate は 0.05 が最有力、")
    print("     マージンが 31% しかないため seed ばらつき次第で 0.15 になりうる。")


if __name__ == "__main__":
    main()
