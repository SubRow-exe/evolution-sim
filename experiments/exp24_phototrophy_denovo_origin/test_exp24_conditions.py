"""Exp24 harness wiring smoke tests (docs/Exp24_実験計画.md §13 G0-G14)。"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exp18_v1101_dynamic_vent"))

import run_exp24 as core  # noqa: E402
import preflight_exp24 as preflight  # noqa: E402
import aggregate_exp24 as agg  # noqa: E402


@pytest.fixture(scope="module")
def calibration():
    f0_res = core.exp18_core.measure_legacy_f0(warmup_s=600.0, measure_s=100.0)
    h2_field = core.exp18_core.common_initial_h2_field(f0_res)
    return f0_res["f0_mol_s"], h2_field


def test_constants_match_docs():
    assert core.FLUX_LEVELS_UMOL_M2_S == (0.0, 0.5, 1.5)
    assert core.SEEDS == tuple(range(24001, 24017))
    assert len(core.SEEDS) == 16
    assert core.PHOTOTROPH_INNOVATION_PROB == 0.01
    assert core.PHOTOTROPH_LOSS_PROB == 0.0
    assert core.PHOTOTROPH_SEED_ABSORPTION == 0.01
    assert core.DURATION_H == 1920.0
    assert core.PRIMARY_COHORT_CUTOFF_H == 960.0
    assert core.PRIMARY_TRACK_WINDOW_H == 960.0
    assert core.ENVIRONMENT == "A2_DYNAMIC_VENT"


def test_effective_config_gates(calibration):
    f0, _ = calibration
    for flux in core.FLUX_LEVELS_UMOL_M2_S:
        cfg = core.make_cfg(f0, flux)
        core.validate_effective_config(cfg, flux)  # should not raise
        assert cfg.phototrophy_innovation_prob == 0.01
        assert cfg.phototrophy_loss_prob == 0.0


def test_g0_all_off_initial_state(calibration):
    f0, h2_field = calibration
    for seed in core.SEEDS[:2]:
        r = preflight.check_g0(f0, h2_field, seed)
        assert r["G0_initial_state"], r


def test_photo_founder_id_default_none_on_normal_birth(calibration):
    """OFF親のOFF子はfounder id継承せずNoneのまま。"""
    f0, h2_field = calibration
    cfg = dataclasses.replace(core.make_cfg(f0, 0.0), phototrophy_innovation_prob=0.0)
    sim = core.setup_all_off(cfg, 24001, h2_field)
    steps = int(round(3.0 * 3600.0 / cfg.dt_seconds))
    for _ in range(steps):
        sim.step()
        if not sim.organisms:
            break
    assert all(o.photo_founder_id is None for o in sim.organisms)
    assert sim.phototrophy_innovation_events == 0


def test_founder_id_assigned_and_inherited(calibration):
    f0, h2_field = calibration
    r = preflight.check_g2_g3_g4_g9(f0, h2_field, core.SEEDS[0], hours=12.0)
    assert r["G2_founder_phenotype"], r
    assert r["G3_founder_tag_inheritance"], r
    assert r["G4_independent_founder_ids"], r


def test_g4_same_tick_multi_origin(calibration):
    f0, h2_field = calibration
    r = preflight.check_g4_same_tick(f0, h2_field, core.SEEDS[0])
    assert r["G4_same_tick_distinct_ids"], r


def test_g6_loss_disabled(calibration):
    f0, h2_field = calibration
    r = preflight.check_g6(f0, h2_field, core.SEEDS[0])
    assert r["G6_loss_disabled"], r


def test_g10_zero_flux_identity(calibration):
    f0, h2_field = calibration
    r = preflight.check_g10_zero_flux(f0, h2_field, core.SEEDS[0])
    assert r["G10_zero_flux_identity"], r


def test_g11_recorder_non_interference(calibration):
    f0, h2_field = calibration
    r = preflight.check_g11_non_interference(f0, h2_field, core.SEEDS[0])
    assert r["G11_recorder_non_interference"], r


def test_checkpoint_roundtrip_preserves_science_state(calibration):
    f0, h2_field = calibration
    r = preflight.check_checkpoint_roundtrip(f0, h2_field, core.SEEDS[0])
    assert r["checkpoint_roundtrip_ok"], r


def test_tiny_end_to_end_run_and_aggregate(tmp_path, calibration):
    f0, h2_field = calibration
    root = tmp_path / "runs"
    for flux in core.FLUX_LEVELS_UMOL_M2_S:
        for seed in core.SEEDS[:1]:
            outdir = root / f"flux{flux:g}_{seed}"
            outdir.mkdir(parents=True)
            cfg = core.make_cfg(f0, flux)
            core.validate_effective_config(cfg, flux)
            sim = core.setup_all_off(cfg, seed, h2_field)
            state = core.new_tracking_state(seed, flux)
            core.step_segment(sim, state, 6.0)
            origins = core.finalize_origins_table(state)
            core.write_origins_csv(outdir / "exp24_origins.csv", origins)
            summary = core.per_run_summary(state, len(sim.organisms))
            summary["ledger"] = core.write_ledger_check(outdir, sim)
            (outdir / "effective_config.json").write_text(
                json.dumps(dataclasses.asdict(cfg), indent=2))
            (outdir / "initial_genome.json").write_text(json.dumps({"fixed_genes": list(cfg.fixed_genes)}))
            (outdir / "summary.json").write_text(json.dumps({
                "experiment": "Exp24 phototrophy de novo recurrent-origin establishment assay",
                "flux": flux, "seed": seed, "summary": summary,
            }, indent=2))

    rows = agg.load_runs(root)
    assert len(rows) == len(core.FLUX_LEVELS_UMOL_M2_S)
    result = agg.aggregate(rows)
    assert set(result["by_flux"]) == set(core.FLUX_LEVELS_UMOL_M2_S)


def test_golden_fingerprint_unaffected_by_photo_founder_id(tmp_path):
    """コア変更 (photo_founder_id) が他実験の決定的挙動を変えないことの
    再確認。tools/verify_vs_ref.py と同じ考え方で、現在のevosimを2回
    独立実行し同一seedで同一結果になることのみをここでは確認する
    (実際のref比較はCIのtools/verify_vs_ref.py呼び出しで行う)。
    """
    from evosim.config import Config
    from evosim.simulation import Simulation
    cfg = Config()
    sim1 = Simulation(cfg, seed=1)
    sim2 = Simulation(cfg, seed=1)
    for _ in range(200):
        sim1.step()
        sim2.step()
    import hashlib
    def fp(s):
        hh = hashlib.sha256()
        for o in sorted(s.organisms, key=lambda x: x.id):
            hh.update(np.asarray([o.id, o.x, o.y, o.matter, o.energy], dtype=np.float64).tobytes())
        return hh.hexdigest()
    assert fp(sim1) == fp(sim2)
