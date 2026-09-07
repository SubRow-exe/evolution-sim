"""Exp17 Phase C1 calibration harness tests."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import core  # noqa: E402
import run_phase_c1 as c1  # noqa: E402


def test_condition_grid_is_preregistered() -> None:
    assert c1.CONDITIONS == {"C10": 10, "C30": 30, "C50": 50, "C100": 100}


def test_background_values_match_independent_oracle() -> None:
    cfg = core.make_cfg()
    expected = {
        10: (2.7391557738739486e-05, 5.497251374312844e-06, 4.519919932846904e-07),
        30: (8.217467321621845e-05, 1.6491754122938532e-05, 1.3559759798540712e-06),
        50: (1.3695778869369742e-04, 2.748625687156422e-05, 2.259959966423452e-06),
        100: (2.7391557738739485e-04, 5.497251374312844e-05, 4.519919932846904e-06),
    }
    for eq, (c_exp, n_exp, p_exp) in expected.items():
        o = c1.backgrounds_for_equivalents(cfg, eq)
        assert o["cnp_background_exchange_enabled"] is False
        assert math.isclose(o["dic_background_molm3"], c_exp, rel_tol=1e-12)
        assert math.isclose(o["fixed_n_background_molm3"], n_exp, rel_tol=1e-12)
        assert math.isclose(o["phosphate_background_molm3"], p_exp, rel_tol=1e-12)


def test_world_volume_and_initial_biomass_are_expected() -> None:
    cfg = core.make_cfg()
    assert math.isclose(c1.world_volume_m3(cfg), 2.0e-7, rel_tol=1e-12)
    initial_biomass_kgdw = (
        cfg.initial_population * c1.INITIAL_MATTER_PER_AGENT * cfg.matter_unit_to_kgdw
    )
    assert math.isclose(initial_biomass_kgdw, 1.4e-14, rel_tol=1e-12)


def test_short_run_writes_closed_cnp_config(tmp_path: Path) -> None:
    out = tmp_path / "c10"
    summary = c1.run_condition("C10", 17201, out, days=0.00012)
    assert summary["phase"] == "C1"
    assert summary["condition"] == "C10"
    assert summary["biomass_equivalents"] == 10
    cfg = json.loads((out / "effective_config.json").read_text(encoding="utf-8"))
    assert cfg["cnp_background_exchange_enabled"] is False
    assert cfg["explicit_cnp_resources"] is True
    for element in ("carbon", "nitrogen", "phosphorus"):
        ledger = summary["cnp_ledger"][element]
        assert abs(ledger["external_in_mol"]) <= 1e-18
        assert abs(ledger["external_out_mol"]) <= 1e-18
