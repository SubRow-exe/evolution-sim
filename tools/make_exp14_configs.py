"""Exp14 Config生成 (docs/Exp14_実験計画確定.md, 実装チェックリスト.md)。

Phase A (mechanism diagnostic) / Phase B (period x energy_capacity map) /
Phase C (evolutionary rescue probe) をすべて静的に生成できる (Exp13と違い
selected値への依存がない)。generatorはbuild_*関数として提供し、CLIからも
Actions workflowからも同じ関数を呼ぶ (人手Config複製禁止)。

    uv run python tools/make_exp14_configs.py --profile FULL     # configs/exp14/ へ
    uv run python tools/make_exp14_configs.py --profile COMPACT
    uv run python tools/make_exp14_configs.py --profile FULL --check
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config
from evosim.genome import GENE_NAMES
from tools.exp14_common import (
    A_ARM_NAMES, C_ARM_NAMES, COMMON_CONFIG, PHASE_A_ARMS, PHASE_A_BASELINE,
    PHASE_A_JOBS, PHASE_A_SEEDS, PHASE_B_CAPACITIES, PHASE_B_COMMON,
    PHASE_B_JOBS, PHASE_B_PERIODS, PHASE_B_SEEDS, PHASE_C_COMMON,
    PHASE_C_JOBS, PHASE_C_MUTABLE_GENES, PHASE_C_SEEDS, PROFILES, TOTAL_RUNS,
    phase_b_initial_energy, phase_c_fixed_genes,
)

OUT_DIR = ROOT / "configs" / "exp14"

ALL_GENES: list[str] = list(GENE_NAMES)
assert len(ALL_GENES) == 14


def _base(**overrides) -> dict:
    d = dict(COMMON_CONFIG)
    d.update(overrides)
    return d


# ---------------------------------------------------------------------------
# Phase A: A0-A6, 全遺伝子固定 (light-only。chemical source=0で無効化)
# ---------------------------------------------------------------------------

def build_phase_a(arm: str, ticks: int) -> Config:
    cfg = dict(PHASE_A_BASELINE)
    cfg.update(PHASE_A_ARMS[arm])
    return Config(
        **_base(
            light_max=cfg["light_max"],
            light_pattern="vertical",
            chem_vent_flux=0.0,
            light_cycle_enabled=cfg["light_cycle_enabled"],
            light_cycle_period_ticks=cfg["light_cycle_period_ticks"],
            light_day_fraction=cfg["light_day_fraction"],
            energy_capacity=cfg["energy_capacity"],
            initial_energy=cfg["initial_energy"],
            initial_matter=cfg["initial_matter"],
            repro_energy_frac=cfg["repro_energy_frac"],
            fixed_genes=list(ALL_GENES),
            snapshot_interval=min(1000, ticks),
        ),
    )


def phase_a_config_name(arm: str, seed: int) -> str:
    return f"exp14_A_{arm}_seed{seed}.json"


# ---------------------------------------------------------------------------
# Phase B: period x energy_capacity grid, 全遺伝子固定
# ---------------------------------------------------------------------------

def build_phase_b(period: int, capacity: float, ticks: int) -> Config:
    initial_energy = phase_b_initial_energy(capacity)
    return Config(
        **_base(
            light_max=PHASE_B_COMMON["light_max"],
            light_pattern="vertical",
            chem_vent_flux=0.0,
            light_cycle_enabled=PHASE_B_COMMON["light_cycle_enabled"],
            light_cycle_period_ticks=period,
            light_day_fraction=PHASE_B_COMMON["light_day_fraction"],
            energy_capacity=capacity,
            initial_energy=initial_energy,
            initial_matter=PHASE_B_COMMON["initial_matter"],
            repro_energy_frac=PHASE_B_COMMON["repro_energy_frac"],
            fixed_genes=list(ALL_GENES),
            snapshot_interval=min(1000, ticks),
        ),
    )


def phase_b_config_name(period: int, capacity: float, seed: int) -> str:
    return f"exp14_B_p{period}_c{int(capacity)}_seed{seed}.json"


# ---------------------------------------------------------------------------
# Phase C: C1-C4, mutable以外は固定 (GENE_NAMES由来)
# ---------------------------------------------------------------------------

def build_phase_c(arm: str, ticks: int) -> Config:
    fixed = phase_c_fixed_genes(arm)
    return Config(
        **_base(
            light_max=PHASE_C_COMMON["light_max"],
            light_pattern="vertical",
            chem_vent_flux=0.0,
            light_cycle_enabled=PHASE_C_COMMON["light_cycle_enabled"],
            light_cycle_period_ticks=PHASE_C_COMMON["light_cycle_period_ticks"],
            light_day_fraction=PHASE_C_COMMON["light_day_fraction"],
            energy_capacity=PHASE_C_COMMON["energy_capacity"],
            initial_energy=PHASE_C_COMMON["initial_energy"],
            initial_matter=PHASE_C_COMMON["initial_matter"],
            repro_energy_frac=PHASE_C_COMMON["repro_energy_frac"],
            fixed_genes=fixed,
            snapshot_interval=min(1000, ticks),
        ),
    )


def phase_c_config_name(arm: str, seed: int) -> str:
    return f"exp14_C_{arm}_seed{seed}.json"


# ---------------------------------------------------------------------------
# 全体生成
# ---------------------------------------------------------------------------

def all_jobs(profile: str) -> list[tuple[str, Config]]:
    ticks = PROFILES[profile]
    jobs: list[tuple[str, Config]] = []
    for arm in A_ARM_NAMES:
        for seed in PHASE_A_SEEDS:
            jobs.append((phase_a_config_name(arm, seed), build_phase_a(arm, ticks["A"])))
    for period in PHASE_B_PERIODS:
        for capacity in PHASE_B_CAPACITIES:
            for seed in PHASE_B_SEEDS:
                jobs.append((phase_b_config_name(period, capacity, seed),
                             build_phase_b(period, capacity, ticks["B"])))
    for arm in C_ARM_NAMES:
        for seed in PHASE_C_SEEDS:
            jobs.append((phase_c_config_name(arm, seed), build_phase_c(arm, ticks["C"])))
    assert len(jobs) == TOTAL_RUNS, f"生成job数が{TOTAL_RUNS}でない: {len(jobs)}"
    names = [n for n, _ in jobs]
    assert len(names) == len(set(names)), "config名に重複がある"
    return jobs


def generate(profile: str, out_dir: Path = OUT_DIR, check: bool = False) -> None:
    jobs = all_jobs(profile)
    if not check:
        out_dir.mkdir(parents=True, exist_ok=True)
    mismatches = []
    for name, cfg in jobs:
        path = out_dir / name
        if check:
            if not path.exists():
                mismatches.append(f"missing: {name}")
                continue
            existing = Config.from_json(path)
            import dataclasses
            if dataclasses.asdict(existing) != dataclasses.asdict(cfg):
                mismatches.append(f"mismatch: {name}")
        else:
            cfg.to_json(path)
    if check:
        if mismatches:
            raise SystemExit("Config再生成が既存ファイルと一致しません:\n" + "\n".join(mismatches))
        print(f"OK: Exp14 profile={profile} {len(jobs)} Config再生成一致確認済み")
    else:
        print(f"OK: Exp14 profile={profile} {len(jobs)} Config生成完了 -> {out_dir}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["FULL", "COMPACT"], required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()
    out_dir = args.out_dir or (ROOT / "configs" / f"exp14_{args.profile.lower()}")
    generate(args.profile, out_dir, args.check)


if __name__ == "__main__":
    main()
