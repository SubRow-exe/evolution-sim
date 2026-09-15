"""Exp22 harness wiring smoke tests (docs/Exp22_実験計画.md §3 G0-G5)。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exp18_v1101_dynamic_vent"))

import run_exp22 as core  # noqa: E402
import preflight_exp22 as preflight  # noqa: E402
import aggregate_exp22 as agg  # noqa: E402


@pytest.fixture(scope="module")
def calibration():
    f0_res = core.exp18_core.measure_legacy_f0(warmup_s=600.0, measure_s=100.0)
    h2_field = core.exp18_core.common_initial_h2_field(f0_res)
    return f0_res["f0_mol_s"], h2_field


def test_flux_levels_and_seeds_match_docs():
    assert core.FLUX_LEVELS_UMOL_M2_S == (0.0, 0.015, 0.05, 0.15, 0.5, 1.5)
    assert core.SEEDS == (22001, 22002, 22003)
    assert core.PHOTOTROPH_LIGHT_ABSORPTION == 0.01
    assert core.DURATION_H == 72.0


def test_zero_flux_is_valid_with_physical_light_enabled(calibration):
    f0, _ = calibration
    cfg = core.make_cfg(f0, "A0_STATIC", flux=0.0)  # should not raise
    assert cfg.physical_light_enabled is True
    assert cfg.light_photon_flux_umol_m2_s == 0.0


def test_effective_config_gates_g2(calibration):
    f0, _ = calibration
    for env in core.ENVIRONMENTS:
        for flux in core.FLUX_LEVELS_UMOL_M2_S:
            cfg = core.make_cfg(f0, env, flux)
            core.validate_effective_config(cfg, env, flux)  # should not raise


def test_g5_initial_state_matches_except_light_absorption(calibration):
    f0, h2_field = calibration
    cfg = core.make_cfg(f0, "A0_STATIC", flux=0.5)
    off = core.setup_paired(cfg, 22001, h2_field, capability_on=False)
    on = core.setup_paired(cfg, 22001, h2_field, capability_on=True)
    assert core.initial_fingerprint(off) == core.initial_fingerprint(on)
    # sanity: capability/gene actually differ as intended
    assert all(not o.phototrophy_on for o in off.organisms)
    assert all(o.phototrophy_on for o in on.organisms)
    from evosim.genome import LIGHT_ABS
    assert all(o.genome[LIGHT_ABS] == 0.01 for o in on.organisms)
    assert all(o.genome[LIGHT_ABS] == 0.0 for o in off.organisms)


def test_g0_no_legacy_light_contamination_at_positive_control_flux(calibration):
    f0, h2_field = calibration
    cfg = core.make_cfg(f0, "A2_DYNAMIC_VENT", flux=1.5)
    _, summary, _ = core.run_one(cfg, 22001, h2_field, hours=0.02, capability_on=True)
    assert summary["final"]["legacy_light_flow_cum"] == 0.0


def test_preflight_g0_g1_g2_g5_pass_for_a_few_combinations(calibration):
    f0, h2_field = calibration
    for env in core.ENVIRONMENTS:
        for flux in (0.0, 1.5):
            result = preflight.check_g0_g1_g2_g5(f0, h2_field, env, flux, 22001)
            assert result["all_pass"], result


def test_preflight_g3_light_only_no_growth(calibration):
    f0, h2_field = calibration
    for env in core.ENVIRONMENTS:
        result = preflight.check_g3_light_only_no_growth(f0, h2_field, env)
        assert result["no_net_growth"], result


def test_preflight_g4_n_ledger_closes(calibration):
    f0, h2_field = calibration
    result = preflight.check_g4_n_ledger(f0, h2_field, "A0_STATIC", 0.5, 22001)
    assert result["pass"], result


def test_tiny_end_to_end_run_and_aggregate(tmp_path, calibration):
    f0, h2_field = calibration
    root = tmp_path / "runs"
    for env in core.ENVIRONMENTS:
        job_dir = root / f"{env}_22001"
        job_dir.mkdir(parents=True)
        import dataclasses
        import json
        manifest = {"environment": env, "seed": 22001,
                   "flux_levels": list(core.FLUX_LEVELS_UMOL_M2_S), "duration_h": 0.02,
                   "f0_mol_s_per_vent": f0}
        (job_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        for flux in core.FLUX_LEVELS_UMOL_M2_S:
            cfg = core.make_cfg(f0, env, flux)
            flux_dir = job_dir / f"flux{flux:g}"
            flux_dir.mkdir(parents=True)
            off_rows, _, _ = core.run_one(cfg, 22001, h2_field, hours=0.02, capability_on=False)
            on_rows, _, _ = core.run_one(cfg, 22001, h2_field, hours=0.02, capability_on=True)
            core.write_csv(flux_dir / "off.csv", off_rows)
            core.write_csv(flux_dir / "on.csv", on_rows)

    out_dir = tmp_path / "aggregate"
    data = agg.load_all(root)
    assert set(data) == set(core.ENVIRONMENTS)
    flux_response = agg.flux_response_table(data)
    assert len(flux_response) == len(core.ENVIRONMENTS) * len(core.FLUX_LEVELS_UMOL_M2_S)
