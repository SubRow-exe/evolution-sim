"""tools/make_exp14_configs.py のテスト (docs/Exp14_実装チェックリスト.md)。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.genome import GENE_NAMES
from tools import make_exp14_configs as mk
from tools.exp14_common import (
    A_ARM_NAMES, C_ARM_NAMES, PHASE_A_SEEDS, PHASE_B_CAPACITIES,
    PHASE_B_PERIODS, PHASE_B_SEEDS, PHASE_C_MUTABLE_GENES, PHASE_C_SEEDS,
    TOTAL_RUNS,
)


def test_all_jobs_full_totals_116_no_dupes():
    jobs = mk.all_jobs("FULL")
    assert len(jobs) == TOTAL_RUNS
    names = [n for n, _ in jobs]
    assert len(names) == len(set(names))


def test_all_jobs_compact_also_116():
    jobs = mk.all_jobs("COMPACT")
    assert len(jobs) == TOTAL_RUNS


def test_phase_a_all_genes_fixed():
    for arm in A_ARM_NAMES:
        for seed in PHASE_A_SEEDS:
            cfg = mk.build_phase_a(arm, 2000)
            assert set(cfg.fixed_genes) == set(GENE_NAMES)


def test_phase_a_arm_deltas_applied():
    a0 = mk.build_phase_a("A0", 2000)
    a3 = mk.build_phase_a("A3", 2000)
    a6 = mk.build_phase_a("A6", 2000)
    assert a0.light_max == 4.0
    assert a3.light_max == 8.0
    assert a0.light_max == a6.light_max  # A6はlight_maxを変えない
    assert a6.energy_capacity == 200.0
    assert a6.initial_energy == 100.0
    a1 = mk.build_phase_a("A1", 2000)
    assert a1.light_cycle_enabled is False


def test_phase_b_grid_covers_all_cells():
    seen = set()
    for period in PHASE_B_PERIODS:
        for capacity in PHASE_B_CAPACITIES:
            cfg = mk.build_phase_b(period, capacity, 5000)
            assert cfg.light_cycle_period_ticks == period
            assert cfg.energy_capacity == capacity
            seen.add((period, capacity))
    assert len(seen) == len(PHASE_B_PERIODS) * len(PHASE_B_CAPACITIES)


def test_phase_b_initial_energy_matches_derivation():
    from tools.exp14_common import phase_b_initial_energy
    for capacity in PHASE_B_CAPACITIES:
        cfg = mk.build_phase_b(200, capacity, 5000)
        assert abs(cfg.initial_energy - phase_b_initial_energy(capacity)) < 1e-9


def test_phase_c_mutable_genes_not_fixed():
    for arm in C_ARM_NAMES:
        cfg = mk.build_phase_c(arm, 20000)
        mutable = set(PHASE_C_MUTABLE_GENES[arm])
        assert mutable.isdisjoint(set(cfg.fixed_genes))
        assert set(cfg.fixed_genes) | mutable == set(GENE_NAMES)


def test_config_names_unique_across_all_jobs():
    for profile in ("FULL", "COMPACT"):
        jobs = mk.all_jobs(profile)
        names = {n for n, _ in jobs}
        assert len(names) == TOTAL_RUNS


def test_generate_and_check_roundtrip(tmp_path):
    mk.generate("COMPACT", tmp_path)
    files = list(tmp_path.glob("*.json"))
    assert len(files) == TOTAL_RUNS
    mk.generate("COMPACT", tmp_path, check=True)  # 例外を投げないこと
