"""Exp20 preflight — harness wiring + T20-1..T20-11
(docs Exp20 §11)。

T20-1/2/4/5/6/7の核心的な物理・保存則挙動は tests/test_v111_phototrophy.py
(rev2 T1-T10) が既に検証している。ここではExp20固有の配線 — t=0 seeding
(§5)、A0/A1 H2 source equality (T20-10)、formal LUCA baseline定数
(T20-11)、RNG isolation (T20-9)、founder exactness (T20-8) — だけを追加で
確認する。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exp18_v1101_dynamic_vent"))

import exp20_core as core  # noqa: E402


@pytest.fixture(scope="module")
def calibration():
    f0_res = core.exp18_core.measure_legacy_f0(warmup_s=600.0, measure_s=100.0)
    h2_field = core.exp18_core.common_initial_h2_field(f0_res)
    return f0_res["f0_mol_s"], h2_field


# --- T20-11: formal LUCA baseline ----------------------------------------

def test_t20_11_formal_h2_usable_energy_is_luca_proxy_value_not_config_default():
    cfg = core.make_cfg(1e-10, "A0_STATIC")
    assert cfg.h2_usable_energy_j_per_mol == 2407.5
    from evosim.config import Config
    assert Config().h2_usable_energy_j_per_mol != 2407.5  # class defaultとの取り違え防止


def test_t20_11_formal_physical_light_baseline_matches_docs():
    cfg = core.make_cfg(1e-10, "A0_STATIC")
    assert cfg.physical_light_enabled is True
    assert cfg.light_photon_flux_umol_m2_s == 0.015
    assert cfg.light_effective_wavelength_nm == 800.0
    assert cfg.phototrophy_radiant_to_usable_eff == 0.10
    assert cfg.phototrophy_innovation_prob == 0.0
    assert cfg.phototrophy_loss_prob == 0.0
    assert cfg.fixed_genes  # continuous genes fixed (evolve_genes=())


# --- T20-10: A0/A1 H2 source equality --------------------------------------

def test_t20_10_a0_a1_cumulative_h2_source_equal(calibration, tmp_path):
    f0, h2_field = calibration
    cfg_a0 = core.make_cfg(f0, "A0_STATIC")
    cfg_a1 = core.make_cfg(f0, "A1_TEMPORAL")
    s_a0 = core.run(cfg_a0, 20001, 0.0, "A0_STATIC", tmp_path / "a0", h2_field, days=0.01)
    s_a1 = core.run(cfg_a1, 20001, 0.0, "A1_TEMPORAL", tmp_path / "a1", h2_field, days=0.01)
    rel = abs(s_a0["h2_source_influx_cum_mol"] - s_a1["h2_source_influx_cum_mol"]) / max(
        s_a0["h2_source_influx_cum_mol"], 1e-300)
    assert rel < 1e-6


# --- T20-8/T20-9: founder exactness / RNG isolation ------------------------

def test_t20_8_founder_counts_are_exact_and_nested():
    ids = list(range(100))
    f1 = core.founder_ids(20001, ids, 1)
    f10 = core.founder_ids(20001, ids, 10)
    f50 = core.founder_ids(20001, ids, 50)
    assert len(f1) == 1 and len(f10) == 10 and len(f50) == 50
    assert f1 <= f10 <= f50


def test_t20_9_founder_selection_does_not_consume_simulation_rng(calibration):
    f0, h2_field = calibration
    cfg = core.make_cfg(f0, "A0_STATIC")
    sim0, _ = core.setup_sim(cfg, 20001, h2_field, 0.0)
    sim1, founders = core.setup_sim(cfg, 20001, h2_field, 0.10)
    # founder selectionだけがphototrophy stateを変える。位置/初期matter/
    # energyはfrequencyに依存せず一致するはず (RNGを追加消費していない証拠)。
    pos0 = [(o.x, o.y, o.matter) for o in sim0.organisms]
    pos1 = [(o.x, o.y, o.matter) for o in sim1.organisms]
    assert pos0 == pos1
    assert len(founders) == 10


def test_t20_9_frequency_does_not_change_rng_state(calibration):
    f0, h2_field = calibration
    cfg = core.make_cfg(f0, "A0_STATIC")
    sim0, _ = core.setup_sim(cfg, 20002, h2_field, 0.0)
    sim1, _ = core.setup_sim(cfg, 20002, h2_field, 0.50)
    assert sim0.rng.bit_generator.state == sim1.rng.bit_generator.state


def test_seeding_transfers_n_from_local_field_not_from_nothing(calibration):
    f0, h2_field = calibration
    cfg = core.make_cfg(f0, "A0_STATIC")
    sim, _ = core.setup_sim(cfg, 20001, h2_field, 0.0)
    n_before = sim.system_nitrogen()
    sim2, founders = core.setup_sim(cfg, 20001, h2_field, 0.10)
    n_after = sim2.system_nitrogen()
    assert len(founders) == 10
    assert n_after == pytest.approx(n_before, rel=1e-9)


# --- tiny end-to-end run + aggregate ---------------------------------------

def test_tiny_end_to_end_run_and_aggregate(tmp_path, calibration):
    f0, h2_field = calibration
    import exp20_core as core_mod
    import aggregate_exp20 as agg

    root = tmp_path / "runs"
    for env in ("A0_STATIC", "A1_TEMPORAL"):
        cfg = core_mod.make_cfg(f0, env)
        for freq in (0.0, 0.10):
            for seed in (20001,):
                outdir = root / f"{env}_{freq}_{seed}"
                core_mod.run(cfg, seed, freq, env, outdir, h2_field, days=0.01)

    rows = agg.load_runs(root)
    assert len(rows) == 4
    result = agg.aggregate(rows)
    assert result["photo_energy_identities_valid"] is True
    assert "freq=0.1_seed=20001" in result["delta_s48_by_run"]
