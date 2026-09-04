"""Exp15 Phase A / Phase B の事前実走チェック (Opus 5レビュー時に実施)

これは正式実験ではない。docs/Exp15_実験計画確定.md の条件をそのままローカルで走らせ、
formal dispatch 前に判定が両側へ振れうるかを確認するための feasibility 検証である。

正本: docs/Exp14結果_Exp15計画_Opus5レビュー.md
使い方: uv run python experiments/opus5_review_precheck_20260904/run_precheck.py [ticks]
"""
from __future__ import annotations

import math
import sys

from evosim.config import Config
from evosim.genome import GENE_NAMES
from evosim.simulation import Simulation

# docs/Exp15_実験計画確定.md §3 の全Phase共通条件をそのまま写す。
BASE = dict(
    light_pattern="vertical", chem_vent_flux=0.0, nutrient_initial=2.0,
    bmr_core=0.15, memory_tau=10.0, response_gain=64.0,
    light_uptake_coef=2.0, light_uptake_half=0.6,
    initial_population=100, initial_matter=0.8,
    diagnostic_placement="random",
    fixed_genes=list(GENE_NAMES),
    # §4 表現型HARD GATE。Exp14 はこの上書きが欠落して light_absorption=0.3 で走った。
    diagnostic_gene_overrides={"light_absorption": 2.0, "chemical_absorption": 0.3},
    stats_interval=20, snapshot_interval=1000, max_population_halt=10000,
)
DEFAULTS = dict(
    energy_capacity=100.0, repro_energy_frac=0.6, initial_energy=50.0,
    light_cycle_period_ticks=200, light_day_fraction=0.5,
)

# half-sine / day_fraction=0.5 の一周期平均 daylight factor。
MEAN_DAYLIGHT_FACTOR = 0.5 * (2.0 / math.pi)          # 0.31831
# 周期平均供給を static light_max=1.2 と厳密に一致させる light_max。
ENERGY_MATCHED_LIGHT_MAX = 1.2 / MEAN_DAYLIGHT_FACTOR  # 3.7699

LIGHT_ABS_INDEX = GENE_NAMES.index("light_absorption")


def run(label: str, seeds, ticks: int, **overrides) -> None:
    """1条件を seeds 分だけ実走して1行ずつ出力する。"""
    for seed in seeds:
        kwargs = dict(DEFAULTS)
        kwargs.update(overrides)
        cfg = Config(**BASE, **kwargs)
        sim = Simulation(cfg, seed=seed)
        # 表現型GATE: 初期100個体すべてが light specialist であること。
        assert all(abs(o.genome[LIGHT_ABS_INDEX] - 2.0) < 1e-12 for o in sim.organisms)

        stopped_at = None
        for _ in range(ticks):
            sim.step()
            if not sim.organisms:
                stopped_at = ("EXTINCT", sim.tick)
                break
            if len(sim.organisms) >= cfg.max_population_halt:
                stopped_at = ("POP_HALT", sim.tick)
                break
        status, tick = stopped_at or ("REACHED", 0)
        pop = len(sim.organisms)
        gen = max((o.generation for o in sim.organisms), default=-1)
        print(f"{label:46s} {seed:4d} {status:>9s} {tick:8d} {pop:6d} {gen:6d}")


def main() -> None:
    ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    header = f"{'condition':46s} {'seed':>4s} {'status':>9s} {'stop_tk':>8s} {'pop':>6s} {'maxgen':>6s}"

    print(f"ticks={ticks}  light_absorption=2.0 (正しい light specialist)")
    print(f"mean daylight factor = {MEAN_DAYLIGHT_FACTOR:.5f} / "
          f"energy等価 light_max = {ENERGY_MATCHED_LIGHT_MAX:.4f}\n")

    print("=== Exp15 Phase A 2x2 (§5, light_max=1.2) ===")
    print(header)
    for label, (cycle, density) in {
        "A0 cycle OFF / density OFF (V1.7型control)": (False, False),
        "A1 cycle OFF / density ON  (density単独)": (False, True),
        "A2 cycle ON  / density OFF (day/night単独)": (True, False),
        "A3 cycle ON  / density ON  (V1.8 combined)": (True, True),
    }.items():
        run(label, (1, 2, 3), ticks, light_max=1.2,
            light_cycle_enabled=cycle, primary_energy_density_response=density)

    print("\n=== 追加: energy等価な昼夜arm (本レビューの提案。Exp15には無い) ===")
    print(header)
    for label, density in {
        "A2' cycle ON / density OFF / energy等価": False,
        "A3' cycle ON / density ON  / energy等価": True,
    }.items():
        run(label, (1, 2, 3), ticks, light_max=ENERGY_MATCHED_LIGHT_MAX,
            light_cycle_enabled=True, primary_energy_density_response=density)

    print("\n=== Exp15 Phase B の light_max 掃引 (§9) ===")
    print(header)
    for lmax in (2.4, 4.0, 8.0, 12.0):
        run(f"PhaseB combined light_max={lmax:5.1f}", (1, 2), ticks, light_max=lmax,
            light_cycle_enabled=True, primary_energy_density_response=True)

    print("\n=== remedy候補 (light_max=4.0 / combined 固定、1軸ずつ) ===")
    print(header)
    combined = dict(light_max=4.0, light_cycle_enabled=True,
                    primary_energy_density_response=True)
    for label, override in {
        "R0 baseline": {},
        "R1 repro_energy_frac .6->.80": dict(repro_energy_frac=0.80),
        "R2 energy_capacity 100->300": dict(energy_capacity=300.0),
        "R3 period 200->80 (夜100->40)": dict(light_cycle_period_ticks=80),
        "R4 day_fraction .5->.8 (夜100->40)": dict(light_day_fraction=0.8),
        "R5 R1+R2": dict(repro_energy_frac=0.80, energy_capacity=300.0),
    }.items():
        run(label, (1, 2), ticks, **combined, **override)


if __name__ == "__main__":
    main()
