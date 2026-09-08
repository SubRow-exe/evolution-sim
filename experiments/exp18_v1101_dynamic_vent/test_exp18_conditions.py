"""Exp18 harness wiring smoke tests (not the V1.10.1 mechanical suite).

tests/test_v1101_dynamic_vent.py がcore mechanismを検証する。ここでは
Exp18固有のharness配線 (exp18_core.py / run_exp18.py / aggregate_phase_a.py /
run_exp18_phase_b.py) だけを素早く確認する。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aggregate_phase_a  # noqa: E402
import aggregate_phase_b  # noqa: E402
import exp18_core as core  # noqa: E402
import run_exp18  # noqa: E402
import run_exp18_phase_b  # noqa: E402


def test_base_config_is_v110_working_baseline():
    cfg = core.base_config()
    assert cfg.explicit_cnp_resources is True
    assert cfg.cnp_background_exchange_enabled is False
    assert cfg.physical_mode is True


def test_conditions_share_total_flux_with_a0():
    """A1/A2/A3はA0と世界全体の総flux (n_vents x F0) を揃える (docs §3)。"""
    f0 = 1e-10
    for cond, kw in run_exp18.CONDITIONS.items():
        overrides = dict(kw)
        if overrides["turnover"]:
            overrides = {**overrides, **run_exp18.TURNOVER_KW}
        cfg = core.make_flux_cfg(f0, **overrides)
        assert cfg.h2_vent_flux_mol_s == f0
        assert cfg.n_vents == len(core.LEGACY_FOUR_CENTERS)


def test_phase_b_arms_evolve_only_the_three_energy_genes():
    for arm, spec in run_exp18_phase_b.ARMS.items():
        cfg = core.make_flux_cfg(
            1e-10,
            evolve_genes=(run_exp18_phase_b.EVOLVE_GENES if spec["evolve"] else ()),
            temporal=False, turnover=False)
        fixed = set(cfg.fixed_genes)
        evolve = set(run_exp18_phase_b.EVOLVE_GENES)
        if spec["evolve"]:
            assert fixed.isdisjoint(evolve), arm
        else:
            assert evolve.issubset(fixed), arm


def test_select_dynamic_arm_prefers_a3_then_a2_then_a1():
    def stats(survive_frac, median_gen):
        return {"survive_fraction": survive_frac, "median_max_generation": median_gen}

    all_pass = {c: stats(1.0, 5) for c in ("A1", "A2", "A3")}
    assert aggregate_phase_a.select_dynamic_arm(all_pass)["selected"] == "A3"

    only_a1 = {"A1": stats(1.0, 5), "A2": stats(0.0, 0), "A3": stats(0.0, 0)}
    assert aggregate_phase_a.select_dynamic_arm(only_a1)["selected"] == "A1"

    none_pass = {c: stats(0.0, 0) for c in ("A1", "A2", "A3")}
    assert aggregate_phase_a.select_dynamic_arm(none_pass)["selected"] is None


def test_tiny_phase_a_and_phase_b_runs_produce_required_artifacts(tmp_path):
    f0_res = core.measure_legacy_f0(warmup_s=600.0, measure_s=100.0)
    h2_field = core.common_initial_h2_field(f0_res)
    f0 = f0_res["f0_mol_s"]

    a_summary = run_exp18.run_phase_a("A0", 18001, tmp_path / "a", f0, h2_field,
                                      days=0.005, write_snapshots=False)
    assert a_summary["phase"] == "A"
    for artifact in ("effective_config.json", "initial_genome.json", "summary.json",
                     "timeseries.csv", "cnp_ledger.json", "vent_schedule.json"):
        assert (tmp_path / "a" / artifact).exists()

    b_summary = run_exp18_phase_b.run_phase_b(
        "B2_DYNAMIC_FIXED", "A3", 18101, tmp_path / "b", f0, h2_field,
        days=0.005, write_snapshots=False)
    assert b_summary["phase"] == "B"
    assert b_summary["environment"] == "DYNAMIC"


def test_aggregate_phase_b_reads_run_dirs_and_summarizes_by_arm(tmp_path):
    f0_res = core.measure_legacy_f0(warmup_s=600.0, measure_s=100.0)
    h2_field = core.common_initial_h2_field(f0_res)
    f0 = f0_res["f0_mol_s"]

    root = tmp_path / "all_phaseB"
    for arm, spec in run_exp18_phase_b.ARMS.items():
        dyn_cond = "A3" if spec["dynamic"] else None
        run_exp18_phase_b.run_phase_b(
            arm, dyn_cond, 18101, root / arm, f0, h2_field,
            days=0.005, write_snapshots=False)

    rows = aggregate_phase_b.load_runs(root)
    assert len(rows) == len(run_exp18_phase_b.ARMS)
    result = aggregate_phase_b.aggregate(rows)
    assert set(result["by_arm"]) == set(run_exp18_phase_b.ARMS)
    for arm, stats in result["by_arm"].items():
        assert stats["artifacts_complete"] is True
        for gene in aggregate_phase_b.GENES:
            assert gene in stats["final_gene_stats_across_seeds"]
