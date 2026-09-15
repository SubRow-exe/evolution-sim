"""Exp23 harness wiring smoke tests (docs/Exp23_実験計画.md §12 G0-G10)。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exp18_v1101_dynamic_vent"))

import run_exp23 as core  # noqa: E402
import preflight_exp23 as preflight  # noqa: E402
import aggregate_exp23 as agg  # noqa: E402


@pytest.fixture(scope="module")
def calibration():
    f0_res = core.exp18_core.measure_legacy_f0(warmup_s=600.0, measure_s=100.0)
    h2_field = core.exp18_core.common_initial_h2_field(f0_res)
    return f0_res["f0_mol_s"], h2_field


def test_constants_match_docs():
    assert core.FLUX_LEVELS_UMOL_M2_S == (0.0, 0.5, 1.5)
    assert core.SEEDS == (23001, 23002, 23003, 23004, 23005, 23006, 23007, 23008)
    assert core.PHOTOTROPH_LIGHT_ABSORPTION == 0.01
    assert core.DURATION_H == 120.0
    assert core.CHECKPOINTS_H == (0.0, 12.0, 24.0, 48.0, 72.0, 96.0, 120.0)
    assert core.ENVIRONMENT == "A2_DYNAMIC_VENT"


def test_effective_config_gates_g2(calibration):
    f0, _ = calibration
    for flux in core.FLUX_LEVELS_UMOL_M2_S:
        cfg = core.make_cfg(f0, flux)
        core.validate_effective_config(cfg, flux)  # should not raise


def test_lineage_split_is_exact_5050_and_deterministic(calibration):
    f0, h2_field = calibration
    cfg = core.make_cfg(f0, 0.5)
    sim1, on1 = core.setup_mixed(cfg, 23001, h2_field)
    assert len(on1) == 50
    assert len(sim1.organisms) == 100

    sim2, on2 = core.setup_mixed(cfg, 23001, h2_field)
    assert on1 == on2  # deterministic given same seed


def test_lineage_assignment_does_not_consume_simulation_rng(calibration):
    f0, h2_field = calibration
    cfg = core.make_cfg(f0, 0.5)
    sim = core.exp18_core.setup_sim(cfg, 23002, h2_field)
    ids = sorted(o.id for o in sim.organisms)
    before = sim.rng.bit_generator.state
    core.assign_on_lineage_ids(23002, ids, count=50)
    after = sim.rng.bit_generator.state
    assert before == after


def test_g3_g4_capability_split_correct(calibration):
    f0, h2_field = calibration
    for seed in core.SEEDS[:2]:
        result = preflight.check_g3_g4(f0, h2_field, seed)
        assert result["G3_population_5050"], result
        assert result["G4_capability_split_correct"], result


def test_g5_lineage_inheritance(calibration):
    f0, h2_field = calibration
    result = preflight.check_g5(f0, h2_field, core.SEEDS[0])
    assert result["G5_lineage_inheritance_stable"], result


def test_g6_zero_flux_identity(calibration):
    f0, h2_field = calibration
    result = preflight.check_g6(f0, h2_field, core.SEEDS[0])
    assert result["G6_zero_flux_identity"], result


def test_g10_seed_preregistration():
    result = preflight.check_g10()
    assert result["G10_seed_preregistration"], result


def test_tiny_end_to_end_run_and_aggregate(tmp_path, calibration):
    f0, h2_field = calibration
    root = tmp_path / "runs"
    for flux in core.FLUX_LEVELS_UMOL_M2_S:
        for seed in core.SEEDS[:1]:
            outdir = root / f"flux{flux:g}_{seed}"
            outdir.mkdir(parents=True)
            cfg = core.make_cfg(f0, flux)
            sim_check, on_ids_check = core.setup_mixed(cfg, seed, h2_field)
            assert len(on_ids_check) == 50
            rows, summary = core.run_one(cfg, seed, h2_field, hours=0.02)
            core.write_csv(outdir / "timeseries.csv", rows)
            import dataclasses
            import json
            (outdir / "effective_config.json").write_text(
                json.dumps(dataclasses.asdict(cfg), indent=2))
            (outdir / "initial_genome.json").write_text(json.dumps({"fixed_genes": list(cfg.fixed_genes)}))
            (outdir / "summary.json").write_text(json.dumps({
                "experiment": "Exp23 phototrophy OFF/ON direct competition",
                "flux": flux, "seed": seed, "summary": summary,
            }, indent=2))

    rows = agg.load_runs(root)
    assert len(rows) == len(core.FLUX_LEVELS_UMOL_M2_S)
    result = agg.aggregate(rows)
    assert set(result["by_flux"]) == set(core.FLUX_LEVELS_UMOL_M2_S)
