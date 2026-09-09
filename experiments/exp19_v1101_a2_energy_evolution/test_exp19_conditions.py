"""Exp19 harness wiring smoke tests.

正本: docs/Exp19_A2環境_Energy戦略進化_実験計画.md。

tests/test_v1101_dynamic_vent.py / exp18のtest_exp18_conditions.pyが
core mechanismを検証する。ここではExp19固有の配線
(run_exp19.py / aggregate_exp19.py) と、Exp18で発見したH2 habitability
diagnosticの単位換算修正 (docs §3) の回帰だけを確認する。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exp18_v1101_dynamic_vent"))

import aggregate_exp19  # noqa: E402
import exp18_core as core  # noqa: E402
import run_exp19  # noqa: E402


def test_h2_habitability_threshold_is_248_micromolar_in_si_units():
    """docs §3: 248 uM = 248e-6 mol/L = 0.248 mol/m^3。

    1000倍小さいbugだった248e-6 mol/m^3 (実質0.248 uM相当) へ戻さないための
    回帰test。
    """
    assert core.H2_HABITABILITY_MOLM3 == 0.248
    # 1 mol/m^3 == 1 mmol/L == 1000 umol/L (uM)。
    micromolar_equivalent = core.H2_HABITABILITY_MOLM3 * 1000.0
    assert micromolar_equivalent == 248.0  # 0.248 mol/m^3 == 248 uM


def test_exp19_arms_map_onto_exp18_phase_b_arms_with_a2_fixed():
    assert set(run_exp19.ARM_TO_EXP18) == set(run_exp19.ARM_TO_EXP18.keys())
    assert run_exp19.ARM_TO_EXP18["E0_STATIC_FIXED"] == "B0_STATIC_FIXED"
    assert run_exp19.ARM_TO_EXP18["E1_STATIC_EVOLVE"] == "B1_STATIC_EVOLVE"
    assert run_exp19.ARM_TO_EXP18["E2_A2_DYNAMIC_FIXED"] == "B2_DYNAMIC_FIXED"
    assert run_exp19.ARM_TO_EXP18["E3_A2_DYNAMIC_EVOLVE"] == "B3_DYNAMIC_EVOLVE"
    assert run_exp19.DYNAMIC_CONDITION == "A2"
    assert run_exp19.SEEDS == (19001, 19002, 19003)
    assert run_exp19.DAYS == 10.0


def test_timeseries_carries_all_three_gene_time_series_columns(tmp_path):
    """docs §13: 3 gene time-series/statisticsは必須artifact。"""
    f0_res = core.measure_legacy_f0(warmup_s=600.0, measure_s=100.0)
    h2_field = core.common_initial_h2_field(f0_res)
    (tmp_path / "calibration").mkdir()
    import json
    import numpy as np
    (tmp_path / "calibration" / "f0_calibration.json").write_text(
        json.dumps({"f0_mol_s": f0_res["f0_mol_s"]}))
    np.save(tmp_path / "calibration" / "common_initial_h2_field.npy", h2_field)

    summary = run_exp19.run_arm("E0_STATIC_FIXED", 19001, tmp_path / "run",
                                tmp_path / "calibration", days=0.005,
                                write_snapshots=False)
    assert summary["exp19_arm"] == "E0_STATIC_FIXED"
    assert summary["exp18_arm_reused"] == "B0_STATIC_FIXED"

    import csv
    with (tmp_path / "run" / "timeseries.csv").open() as f:
        header = next(csv.reader(f))
    for col in ("storage_capacity_mean", "storage_capacity_median",
               "starvation_horizon_mean", "starvation_horizon_median",
               "reproduction_horizon_mean", "reproduction_horizon_median"):
        assert col in header, header


def test_tiny_end_to_end_run_and_aggregate_produces_required_artifacts(tmp_path):
    f0_res = core.measure_legacy_f0(warmup_s=600.0, measure_s=100.0)
    h2_field = core.common_initial_h2_field(f0_res)
    (tmp_path / "calibration").mkdir()
    import json
    import numpy as np
    (tmp_path / "calibration" / "f0_calibration.json").write_text(
        json.dumps({"f0_mol_s": f0_res["f0_mol_s"]}))
    np.save(tmp_path / "calibration" / "common_initial_h2_field.npy", h2_field)

    root = tmp_path / "all_runs"
    for arm in run_exp19.ARM_TO_EXP18:
        for seed in run_exp19.SEEDS:
            run_exp19.run_arm(arm, seed, root / f"{arm}_{seed}", tmp_path / "calibration",
                              days=0.005, write_snapshots=False)

    rows = aggregate_exp19.load_runs(root)
    assert len(rows) == len(run_exp19.ARM_TO_EXP18) * len(run_exp19.SEEDS)
    result = aggregate_exp19.aggregate(rows)
    assert set(result["by_arm"]) == set(run_exp19.ARM_TO_EXP18)
    for arm, stats in result["by_arm"].items():
        assert stats["artifacts_complete"] is True
        for gene in aggregate_exp19.GENES:
            assert gene in stats["gene_shift_summary"]
    for key in ("A_E2_vs_E3", "B_E1_vs_E3", "C_E0_vs_E1"):
        assert key in result["comparisons"]
        assert "note" not in result["comparisons"][key]
