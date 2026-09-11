"""Exp21 harness wiring smoke tests (docs/Exp21_実験計画.md §11 G1-G10)。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exp18_v1101_dynamic_vent"))

import run_exp21 as core  # noqa: E402
import preflight_exp21 as preflight  # noqa: E402
import aggregate_exp21 as agg  # noqa: E402


@pytest.fixture(scope="module")
def calibration():
    f0_res = core.exp18_core.measure_legacy_f0(warmup_s=600.0, measure_s=100.0)
    h2_field = core.exp18_core.common_initial_h2_field(f0_res)
    return f0_res["f0_mol_s"], h2_field


def test_baseline_and_long_horizon_values_match_docs():
    assert core.BASELINE_HORIZON_S == 1800.0
    assert core.LONG_HORIZON_S == 2700.0


def test_effective_config_gates_g1_to_g5(calibration):
    f0, _ = calibration
    for env in core.ENVIRONMENTS:
        cfg = core.make_cfg(f0, env)
        core.validate_effective_config(cfg, env)  # should not raise


def test_lineage_split_is_exact_5050_and_deterministic(calibration):
    f0, h2_field = calibration
    cfg = core.make_cfg(f0, "A0_STATIC")
    sim1 = core.exp18_core.setup_sim(cfg, 21001, h2_field)
    long1 = core.assign_lineages(sim1, 21001)
    assert len(long1) == 50
    assert len(sim1.organisms) == 100

    sim2 = core.exp18_core.setup_sim(cfg, 21001, h2_field)
    long2 = core.assign_lineages(sim2, 21001)
    assert long1 == long2  # deterministic given same seed


def test_lineage_assignment_does_not_consume_simulation_rng(calibration):
    f0, h2_field = calibration
    cfg = core.make_cfg(f0, "A0_STATIC")
    sim = core.exp18_core.setup_sim(cfg, 21002, h2_field)
    before = sim.rng.bit_generator.state
    core.assign_lineages(sim, 21002)
    after = sim.rng.bit_generator.state
    assert before == after


def test_genomes_identical_except_starvation_horizon(calibration):
    f0, h2_field = calibration
    cfg = core.make_cfg(f0, "A0_STATIC")
    sim = core.exp18_core.setup_sim(cfg, 21003, h2_field)
    long_ids = core.assign_lineages(sim, 21003)
    assert core.genomes_identical_except_starv_horizon(sim, long_ids)
    from evosim.genome import STARV_HORIZON
    horizons = {float(o.genome[STARV_HORIZON]) for o in sim.organisms}
    assert horizons == {core.BASELINE_HORIZON_S, core.LONG_HORIZON_S}


def test_preflight_all_combinations_pass(calibration, tmp_path):
    f0, h2_field = calibration
    for env in core.ENVIRONMENTS:
        for seed in core.SEEDS[:2]:  # full 16-combination sweep is covered by CI preflight job
            result = preflight.check_one(f0, h2_field, env, seed)
            assert result["all_pass"], result


def test_tiny_end_to_end_run_and_aggregate(tmp_path, calibration):
    f0, h2_field = calibration
    root = tmp_path / "runs"
    for env in core.ENVIRONMENTS:
        cfg = core.make_cfg(f0, env)
        for seed in core.SEEDS[:1]:
            sim_check = core.exp18_core.setup_sim(cfg, seed, h2_field)
            long_ids = core.assign_lineages(sim_check, seed)
            assert len(long_ids) == 50
            rows, summary = core.run_one(cfg, seed, h2_field, hours=0.02)
            outdir = root / f"{env}_{seed}"
            outdir.mkdir(parents=True)
            core.write_csv(outdir / "lineage_timeseries.csv", rows)
            import dataclasses
            import json
            (outdir / "effective_config.json").write_text(
                json.dumps(dataclasses.asdict(cfg), indent=2))
            (outdir / "summary.json").write_text(json.dumps({
                "experiment": "Exp21 starvation_horizon direct competition",
                "environment": env, "seed": seed, "summary": summary,
            }, indent=2))

    rows = agg.load_runs(root)
    assert len(rows) == 2
    result = agg.aggregate(rows)
    assert set(result["by_environment"]) == set(core.ENVIRONMENTS)
    for env_stats in result["by_environment"].values():
        assert "f_long_h120" in env_stats
