"""Focused tests for the literature-constrained LUCA proxy policy."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "experiments" / "luca_proxy" / "run_luca_proxy.py"

spec = importlib.util.spec_from_file_location("run_luca_proxy_tested", MODULE_PATH)
lp = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(lp)


def test_luca_proxy_physical_constants_are_self_consistent():
    cfg = lp.make_cfg("A")
    assert cfg.h2_source_concentration_molm3 == pytest.approx(10.0)
    assert cfg.basal_atp_mmol_per_gdw_h == pytest.approx(0.29)
    assert cfg.atp_energy_j_per_mol == pytest.approx(32100.0)
    assert cfg.h2_qmax_mol_per_kgdw_s == pytest.approx(120.0 / 3600.0)
    assert cfg.h2_km_mol_m3 == pytest.approx(120.0 / 19.36)
    assert cfg.h2_usable_energy_j_per_mol == pytest.approx(0.075 * 32100.0)
    assert cfg.growth_energy_j_per_kgdw == pytest.approx(3.21e6)


def test_growth_cannot_spend_protected_homeostatic_reserve():
    sim = lp.base.setup_sim("A", 15001)
    org = sim.organisms[0]
    reserve = lp.protected_growth_reserve_j(org, sim.cfg)
    assert reserve > 0.0

    org.energy = reserve * 0.9
    assert lp.growth_available_energy_j(org, sim.cfg) == pytest.approx(0.0)

    extra = reserve * 0.2
    org.energy = reserve + extra
    assert lp.growth_available_energy_j(org, sim.cfg) == pytest.approx(extra)


def test_short_run_no_immediate_growth_energy_collapse():
    sim = lp.base.setup_sim("A", 15001)
    # Attempt 1 lost every cell at ~130-140 s.  Run well past that point.
    for _ in range(int(900 / sim.cfg.dt_seconds)):
        sim.step()
        if not sim.organisms:
            break
    assert len(sim.organisms) > 0
