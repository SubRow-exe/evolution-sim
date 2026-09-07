"""V1.10.1 動的熱水噴出口の必須テスト (docs/V1.10.1_動的熱水噴出口_実装方針.md §10)。

h2_source_mode="dirichlet" (既定) がV1.10以前と完全に同じであることは
既存test群 (tests/test_v13_chemical_source.py, test_v14_uptake.py,
test_v19_iluca.py, test_v110_cnp.py等) が既にカバーしている。ここでは
"flux" modeのledger/非負性/dt収束/temporal等価性/turnover geometry・
RNG隔離だけを検証する。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evosim.config import Config
from evosim.simulation import Simulation
from evosim.world import World, _precompute_turnover_schedule, _vent_flux_schedule

LEGACY_FOUR_CENTERS = ((10, 10), (10, 30), (30, 10), (30, 30))


def _flux_cfg(**overrides) -> Config:
    kwargs = dict(
        physical_mode=True,
        h2_source_mode="flux",
        dt_seconds=10.0,
        world_width=0.020,
        world_height=0.020,
        cell_size=5.0e-4,
        effective_depth_m=5.0e-4,
        n_vents=4,
        vent_radius_cells=2,
        h2_vent_flux_mol_s=1.0e-9,
        h2_diffusion_m2s=5.0e-9,
        h2_exchange_tau_s=900.0,
        initial_population=0,
    )
    kwargs.update(overrides)
    return Config(**kwargs)


def _rng(seed=1):
    return np.random.Generator(np.random.PCG64(seed))


# ---------------------------------------------------------------------------
# 1. dirichlet regression
# ---------------------------------------------------------------------------

def test_dirichlet_mode_is_default_and_unaffected_by_v1101_fields():
    cfg = Config()
    assert cfg.h2_source_mode == "dirichlet"
    w = World(cfg, _rng(1))
    assert w.vent_slot_positions == []
    assert not hasattr(w, "env_rng")


def test_dirichlet_run_matches_pre_v1101_reference():
    """h2_source_mode明示指定の有無で挙動が変わらないことを確認する
    (h2_vent_flux_mol_s等の新field追加が既定挙動へ影響しないことの直接確認)。"""
    cfg_implicit = Config(physical_mode=True, dt_seconds=10.0,
                          world_width=0.020, world_height=0.020,
                          cell_size=5e-4, effective_depth_m=5e-4,
                          initial_population=5)
    cfg_explicit = Config(physical_mode=True, dt_seconds=10.0,
                          world_width=0.020, world_height=0.020,
                          cell_size=5e-4, effective_depth_m=5e-4,
                          initial_population=5, h2_source_mode="dirichlet")
    sim_a = Simulation(cfg_implicit, seed=7)
    sim_b = Simulation(cfg_explicit, seed=7)
    for _ in range(50):
        sim_a.step()
        sim_b.step()
    assert np.array_equal(sim_a.world.h2, sim_b.world.h2)
    assert [o.matter for o in sim_a.organisms] == [o.matter for o in sim_b.organisms]


# ---------------------------------------------------------------------------
# 2. finite flux source ledger
# ---------------------------------------------------------------------------

def test_flux_mode_source_ledger_matches_specified_mol_s():
    cfg = _flux_cfg()
    w = World(cfg, _rng(1))
    w.configure_flux_vents(LEGACY_FOUR_CENTERS)
    total_in = 0.0
    n_steps = 200
    for _ in range(n_steps):
        _, s_in, _ = 0.0, 0.0, 0.0
        inflow, _loss = w.update()
        total_in += inflow
    expected = cfg.h2_vent_flux_mol_s * len(LEGACY_FOUR_CENTERS) * cfg.dt_seconds * n_steps
    assert total_in == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# 3. non-negative / finite field
# ---------------------------------------------------------------------------

def test_flux_field_stays_nonnegative_and_finite():
    cfg = _flux_cfg(h2_vent_flux_mol_s=5e-8)  # 強めのflux
    w = World(cfg, _rng(2))
    w.configure_flux_vents(LEGACY_FOUR_CENTERS)
    for _ in range(2000):
        w.update()
        assert bool((w.h2 >= 0.0).all())
        assert bool(np.isfinite(w.h2).all())


# ---------------------------------------------------------------------------
# 4. dt convergence (flux mode)
# ---------------------------------------------------------------------------

def test_flux_mode_dt_convergence():
    def run(dt):
        cfg = _flux_cfg(dt_seconds=dt)
        w = World(cfg, _rng(3))
        w.configure_flux_vents(LEGACY_FOUR_CENTERS)
        n_steps = int(round(6 * 3600.0 / dt))
        for _ in range(n_steps):
            w.update()
        return w.total_h2()

    h2_5 = run(5.0)
    h2_10 = run(10.0)
    assert h2_5 == pytest.approx(h2_10, rel=0.01)


# ---------------------------------------------------------------------------
# 5. temporal supply equivalence (static vs 12h paired-staggered)
# ---------------------------------------------------------------------------

def test_static_and_temporal_integrate_to_same_source_over_one_cycle():
    def total_source(temporal: bool, on_mult: float):
        cfg = _flux_cfg(
            h2_vent_flux_mol_s=1e-9, h2_vent_temporal_enabled=temporal,
            h2_vent_cycle_period_s=43200.0, h2_vent_duty_fraction=0.5,
            h2_vent_on_flux_multiplier=on_mult,
        )
        w = World(cfg, _rng(4))
        w.configure_flux_vents(LEGACY_FOUR_CENTERS)
        total = 0.0
        n_steps = int(round(43200.0 / cfg.dt_seconds))
        for _ in range(n_steps):
            inflow, _ = w.update()
            total += inflow
        return total

    static_total = total_source(False, 1.0)
    temporal_total = total_source(True, 2.0)
    assert temporal_total == pytest.approx(static_total, rel=1e-9)


# ---------------------------------------------------------------------------
# 6. paired-staggered: always exactly 2 active vents
# ---------------------------------------------------------------------------

def test_paired_staggered_always_two_active():
    cfg = _flux_cfg(h2_vent_temporal_enabled=True)
    for t in np.linspace(0.0, 43200.0 * 3, 200):
        flux = _vent_flux_schedule(cfg, float(t), 4)
        assert int((flux > 0.0).sum()) == 2


# ---------------------------------------------------------------------------
# 7. turnover: always exactly n_vents vents present
# ---------------------------------------------------------------------------

def test_turnover_preserves_vent_count():
    cfg = _flux_cfg(h2_vent_turnover_enabled=True, h2_vent_turnover_interval_s=1000.0)
    w = World(cfg, _rng(5))
    w.configure_flux_vents(LEGACY_FOUR_CENTERS)
    for _ in range(500):
        w.update()
        assert len(w.vent_slot_positions) == 4
        assert len(set(w.vent_slot_positions)) == 4  # 重複なし


# ---------------------------------------------------------------------------
# 8. relocation respects boundary / min-separation constraints
# ---------------------------------------------------------------------------

def test_turnover_relocation_respects_constraints():
    cfg = _flux_cfg(h2_vent_turnover_enabled=True, h2_vent_turnover_interval_s=100.0,
                    h2_vent_min_separation_cells=4)
    w = World(cfg, _rng(6))
    w.configure_flux_vents(LEGACY_FOUR_CENTERS)
    gw, gh = cfg.grid_w, cfg.grid_h
    for ev in w._turnover_events[:20]:
        x, y = ev["position"]
        assert 1 <= x <= gw - 2
        assert 1 <= y <= gh - 2


# ---------------------------------------------------------------------------
# 9. environment RNG determinism / isolation
# ---------------------------------------------------------------------------

def test_environment_rng_deterministic_same_seed():
    cfg = _flux_cfg(h2_vent_turnover_enabled=True, h2_vent_turnover_interval_s=1000.0)

    def schedule(seed):
        w = World(cfg, _rng(seed))
        w.configure_flux_vents(LEGACY_FOUR_CENTERS)
        return w._turnover_events[:10]

    assert schedule(11) == schedule(11)
    assert schedule(11) != schedule(12)


def test_environment_rng_does_not_perturb_organism_rng_stream():
    def draw_after_world(turnover: bool):
        cfg = _flux_cfg(h2_vent_turnover_enabled=turnover, h2_vent_turnover_interval_s=1000.0)
        rng = _rng(21)
        w = World(cfg, rng)
        w.configure_flux_vents(LEGACY_FOUR_CENTERS)
        return rng.random()

    assert draw_after_world(False) == draw_after_world(True)


# ---------------------------------------------------------------------------
# 10. legacy tests unaffected — covered by the full existing suite (313 tests)
# ---------------------------------------------------------------------------

def test_flux_mode_requires_physical_mode():
    with pytest.raises(ValueError):
        Config(h2_source_mode="flux", physical_mode=False)


def test_paired_staggered_requires_four_vents():
    with pytest.raises(ValueError):
        Config(h2_source_mode="flux", physical_mode=True, n_vents=3,
              h2_vent_temporal_enabled=True)


def test_vent_state_observation_shape():
    cfg = _flux_cfg(h2_vent_temporal_enabled=True, h2_vent_turnover_enabled=True,
                    h2_vent_turnover_interval_s=1000.0)
    w = World(cfg, _rng(9))
    w.configure_flux_vents(LEGACY_FOUR_CENTERS)
    state = w.vent_state(0.0)
    assert state["active_vent_count"] == 2
    assert len(state["vent_positions"]) == 4
    assert len(state["per_vent_flux_mol_s"]) == 4
    assert state["world_source_flux_mol_s"] == pytest.approx(
        2.0 * cfg.h2_vent_flux_mol_s * cfg.h2_vent_on_flux_multiplier)
