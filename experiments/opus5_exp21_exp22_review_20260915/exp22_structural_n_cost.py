"""Exp22 の structural N cost が trade-off として機能する大きさかを測る。

`docs/Exp22_実験計画.md` §2 H4 は「phototrophy apparatus の structural N cost が
効けば ON 群は OFF 群と同等かわずかに不利になりうる」としている。
本スクリプトはその cost を (a) 個体の biomass N に対する比率、
(b) 環境 fixed-N プールに対する比率 の2つで定量する。

シミュレーション実験ではなく解析計算。正式実験ではない。
考察の正本: docs/Exp21_Exp22_Opus5レビュー.md

    EVOSIM_ROOT=<V1.11 worktree> uv run python .../exp22_structural_n_cost.py
"""
from __future__ import annotations

import dataclasses
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
from evosim.organism import Organism    # noqa: E402
from evosim.genome import INITIAL_GENOME, LIGHT_ABS  # noqa: E402

N_MOLAR_MASS_KG_PER_MOL = 0.014007
LIGHT_ABSORPTION = 0.01
FLUX = 0.05          # §12.1 の preferred candidate 予測値
INITIAL_POPULATION = 100


def main() -> None:
    f0r = exp18_core.measure_legacy_f0()
    cfg = dataclasses.replace(
        exp21.make_cfg(f0r["f0_mol_s"], "A0_STATIC"),
        physical_light_enabled=True,
        light_photon_flux_umol_m2_s=FLUX,
        light_effective_wavelength_nm=800.0,
        phototrophy_radiant_to_usable_eff=0.10,
    )

    genome = INITIAL_GENOME.copy()
    genome[LIGHT_ABS] = LIGHT_ABSORPTION
    org = Organism(0, -1, 0, 0, 0, genome, 0.0, 0.0, 0.0, 0.0, 0.5)
    org.phototrophy_on = True

    n_target = physiology.photo_n_target_mol(org, cfg)
    kgdw = org.matter * cfg.matter_unit_to_kgdw
    n_biomass = kgdw * cfg.biomass_nitrogen_mass_frac / N_MOLAR_MASS_KG_PER_MOL

    sim = exp18_core.setup_sim(cfg, 21001, exp18_core.common_initial_h2_field(f0r))
    n_field = float(sim.world.fixed_nitrogen.sum()) * sim.world.voxel_volume_m3

    print("=" * 70)
    print(f"structural N cost  (light_absorption={LIGHT_ABSORPTION}, "
          f"photo_apparatus_n_multiplier={cfg.photo_apparatus_n_multiplier}, "
          f"bchl_extinction_mM_cm={cfg.bchl_extinction_mM_cm})")
    print("=" * 70)
    print(f"  apparatus の構造N要求 (1個体)   : {n_target:.4e} mol")
    print(f"  個体 biomass の N               : {n_biomass:.4e} mol")
    print(f"  個体内での比率                   : {100 * n_target / n_biomass:.3f} %")
    print()
    print(f"  環境 fixed N 総量 (t=0)          : {n_field:.4e} mol")
    print(f"  初期 {INITIAL_POPULATION} 個体分の構造N要求      : "
          f"{INITIAL_POPULATION * n_target:.4e} mol")
    print(f"  環境Nに占める比率                : "
          f"{100 * INITIAL_POPULATION * n_target / n_field:.4f} %")
    print()
    print("  -> Exp17 で採用された 50x CNP stock では N は非律速。")
    print("     構造N要求は個体の 0.6% 程度・環境の 0.01% 程度なので、")
    print("     成長を律速せず、H4 の cost 側は実質ゼロになる。")
    print("     cost を実際に効かせるには N 律速条件 (Exp17 の 10x/30x 相当) が要る。")


if __name__ == "__main__":
    main()
