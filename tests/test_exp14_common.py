"""tools/exp14_common.py のテスト (docs/Exp14_実装チェックリスト.md)。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.genome import GENE_NAMES
from tools import exp14_common as ec


def test_phase_totals_116():
    assert ec.PHASE_A_JOBS == 21
    assert ec.PHASE_B_JOBS == 75
    assert ec.PHASE_C_JOBS == 20
    assert ec.TOTAL_RUNS == 116
    # 独立算出 (generatorの手書き定数を再利用しない)
    assert 7 * 3 == ec.PHASE_A_JOBS
    assert 5 * 5 * 3 == ec.PHASE_B_JOBS
    assert 4 * 5 == ec.PHASE_C_JOBS
    assert 21 + 75 + 20 == 116


def test_phase_a_arm_names():
    assert list(ec.PHASE_A_ARMS.keys()) == ["A0", "A1", "A2", "A3", "A4", "A5", "A6"]


def test_a6_preserves_initial_fraction_not_just_capacity():
    """A6は energy_capacity だけでなく initial_energy も倍にし、
    initial E/Emax fill fractionを保つ (実装チェックリスト.md §1警告)。
    """
    a0 = dict(ec.PHASE_A_BASELINE)
    a6 = dict(ec.PHASE_A_BASELINE)
    a6.update(ec.PHASE_A_ARMS["A6"])
    frac0 = a0["initial_energy"] / (a0["energy_capacity"] * a0["initial_matter"])
    frac6 = a6["initial_energy"] / (a6["energy_capacity"] * a6["initial_matter"])
    assert abs(frac0 - frac6) < 1e-9
    assert a6["energy_capacity"] == 200.0
    assert a6["initial_energy"] == 100.0


def test_phase_b_initial_energy_derived_not_hardcoded():
    # baseline: capacity=100 -> initial_energy=50
    assert abs(ec.phase_b_initial_energy(100.0) - 50.0) < 1e-9
    # fill fraction (0.625) は capacity に依らず一定
    for cap in ec.PHASE_B_CAPACITIES:
        e = ec.phase_b_initial_energy(cap)
        frac = e / (cap * ec.PHASE_B_COMMON["initial_matter"])
        assert abs(frac - 0.625) < 1e-9


def test_phase_c_fixed_genes_derived_from_canonical_gene_names():
    for arm, mutable in ec.PHASE_C_MUTABLE_GENES.items():
        fixed = ec.phase_c_fixed_genes(arm)
        assert set(fixed) | set(mutable) == set(GENE_NAMES)
        assert set(fixed) & set(mutable) == set()
    assert ec.PHASE_C_MUTABLE_GENES["C4"] == [
        "body_size", "reproduction_investment", "movement_power"]


def test_r_ref_orderings_required_by_checklist():
    """実装チェックリスト.md §4: A2<A0, A3≈A0, A4<A0, A6<A0。"""
    r = {name: ec.r_ref_for_arm(ec.PHASE_A_ARMS[name]) for name in ec.A_ARM_NAMES}
    assert r["A1"] == 0.0
    assert r["A2"] < r["A0"]
    assert abs(r["A3"] - r["A0"]) < 1e-9
    assert r["A4"] < r["A0"]
    assert r["A6"] < r["A0"]


def test_r_ref_does_not_use_light_max_directly():
    """A3はlight_max=8.0のみ変える armだが、R_refの入力に light_max は
    渡らない (RRefInputsにlight_max fieldが存在しない)。
    """
    assert not hasattr(ec.RRefInputs, "light_max")
    fields = ec.RRefInputs.__dataclass_fields__
    assert "light_max" not in fields


def test_late_window_metric_na_when_final_tick_below_window():
    rows = [{"tick": t, "population": 10} for t in range(0, 100, 20)]
    # final_tick=80 < window=500 -> N/A (None)
    result = ec.late_window_metric(rows, final_tick=80, window=500, key="population")
    assert result is None


def test_late_window_metric_computes_when_reached():
    rows = [{"tick": t, "population": t} for t in range(0, 1001, 100)]
    result = ec.late_window_metric(rows, final_tick=1000, window=500, key="population")
    # tick>=500の行の平均
    expected_vals = [t for t in range(0, 1001, 100) if t >= 500]
    assert abs(result - sum(expected_vals) / len(expected_vals)) < 1e-9


def test_classify_phase_a_arm():
    survives = [{"reached_full_ticks": True, "final_population": 5}] * 3
    assert ec.classify_phase_a_arm(survives) == "SURVIVES_SHORT"
    marginal = [{"reached_full_ticks": True, "final_population": 5}] * 2 + \
               [{"reached_full_ticks": False, "final_population": 0}]
    assert ec.classify_phase_a_arm(marginal) == "MARGINAL"
    collapse = [{"reached_full_ticks": False, "final_population": 0}] * 3
    assert ec.classify_phase_a_arm(collapse) == "COLLAPSE"


def test_cycle_observation_from_rows_detects_transitions():
    cfg_rows = []
    # 簡易: light_cycle_factor 0/非0 で日/夜を模した合成データ
    for t, factor, pop in [
        (0, 1.0, 100), (10, 1.0, 150), (20, 0.0, 80),
        (30, 0.0, 30), (40, 1.0, 60), (50, 1.0, 90),
    ]:
        cfg_rows.append({"tick": t, "light_cycle_factor": factor, "population": pop})

    class FakeCfg:
        pass

    out = ec.cycle_observation_from_rows(cfg_rows, FakeCfg())
    assert out["sunset_population"] == [80]
    assert out["daytime_peak_population"] == [150]
    assert out["dawn_population"] == [60]
    assert out["night_minimum_population"] == [30]


def test_is_night_tick_matches_daylight_factor():
    from evosim.config import Config
    cfg = Config(light_cycle_enabled=True, light_cycle_period_ticks=200,
                 light_day_fraction=0.5)
    assert ec.is_night_tick(150, cfg) is True
    assert ec.is_night_tick(50, cfg) is False


def test_daylight_births_and_night_starvation():
    from evosim.config import Config
    cfg = Config(light_cycle_enabled=True, light_cycle_period_ticks=200,
                 light_day_fraction=0.5)
    events = [
        {"tick": 50, "event": "birth", "cause": ""},    # day
        {"tick": 150, "event": "birth", "cause": ""},   # night
        {"tick": 150, "event": "death", "cause": "starvation"},  # night starvation
        {"tick": 50, "event": "death", "cause": "starvation"},   # day starvation
        {"tick": 150, "event": "death", "cause": "damage"},      # night, not starvation
    ]
    out = ec.daylight_births_and_night_starvation(events, cfg)
    assert out["daylight_births_cum"] == 1
    assert out["night_starvation_deaths_cum"] == 1
