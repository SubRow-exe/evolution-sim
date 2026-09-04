"""Literature-constrained LUCA-like proxy for Exp15 V1.9 attempt 2.

This module deliberately leaves the core simulator untouched while validating a
LUCA-like physical baseline.  It imports the Phase0/formal runner, replaces only
the physical growth allocation policy, and supplies literature-constrained
physical parameters.

Evidence/assumptions are documented in docs/V1.9_LUCA_proxy設計.md.
"""
from __future__ import annotations

import dataclasses
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXP15_DIR = ROOT / "experiments" / "exp15_v19"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EXP15_DIR))

import run_exp15 as base  # noqa: E402
from evosim import physiology  # noqa: E402
from evosim.genome import NUTRIENT_ABS, STARV_HORIZON  # noqa: E402
from evosim.simulation import Simulation  # noqa: E402


# --- LUCA-like proxy constants ------------------------------------------------
# H2/CO2 acetogen-like proxy, not a claim that these exact values belonged to
# historical LUCA.  See docs/V1.9_LUCA_proxy設計.md for evidence levels.
LUCA_PROXY = {
    "metabolism": "anaerobic H2-dependent CO2-fixing acetogen-like (WLP proxy)",
    "h2_source_molm3": 10.0,               # 10 mM; Lost City-like endmember
    "atp_phosphorylation_j_per_mol": 32_100.0,
    "maintenance_atp_mmol_gdw_h": 0.29,
    "h2_qmax_mmol_gdw_h": 120.0,
    "h2_first_order_l_gdw_h": 19.36,
    "atp_per_h2_mol": 0.075,               # 0.3 ATP / acetate / 4 H2
    "growth_yield_gdw_per_mol_atp": 10.0,  # coarse-grained anaerobe prior
    "nutrient_uptake_cap_matter_h": 0.17,  # kinetic ceiling; Energy is stricter
}

_BASE_MAKE_CFG = base.make_cfg
_BASE_RUN = base.run


def make_cfg(arm: str):
    """Return Exp15 config with a literature-constrained LUCA-like physical proxy."""
    cfg = _BASE_MAKE_CFG(arm)
    atp_j = LUCA_PROXY["atp_phosphorylation_j_per_mol"]
    qmax = LUCA_PROXY["h2_qmax_mmol_gdw_h"]
    k_first = LUCA_PROXY["h2_first_order_l_gdw_h"]
    # mmol/g == mol/kg numerically.
    qmax_mol_per_kg_s = qmax / 3600.0
    km_molm3 = qmax / k_first  # mmol/L == mol/m^3
    h2_usable_j_mol = LUCA_PROXY["atp_per_h2_mol"] * atp_j
    # 10 gDW / mol ATP = 0.01 kgDW/mol; inverse = 100 mol ATP/kgDW.
    growth_j_kg = (1000.0 / LUCA_PROXY["growth_yield_gdw_per_mol_atp"]) * atp_j

    return dataclasses.replace(
        cfg,
        h2_source_concentration_molm3=LUCA_PROXY["h2_source_molm3"],
        basal_atp_mmol_per_gdw_h=LUCA_PROXY["maintenance_atp_mmol_gdw_h"],
        atp_energy_j_per_mol=atp_j,
        h2_qmax_mol_per_kgdw_s=qmax_mol_per_kg_s,
        h2_km_mol_m3=km_molm3,
        h2_usable_energy_j_per_mol=h2_usable_j_mol,
        growth_energy_j_per_kgdw=growth_j_kg,
        nutrient_uptake_rate_matter_per_h=LUCA_PROXY["nutrient_uptake_cap_matter_h"],
    )


# base.setup_sim() resolves make_cfg from its module globals at call time.
base.make_cfg = make_cfg


def protected_growth_reserve_j(org, cfg) -> float:
    """Energy reserve that growth is not allowed to consume.

    The existing V1.9 starvation_horizon gene already represents the organism's
    homeostatic runway target.  In physical mode we protect exactly that many
    seconds of full-activity expenditure.  This converts the prior "grow using
    all stored Energy" behaviour into a maintenance-first/Pirt-like allocation
    without inventing a second reserve parameter.
    """
    p_full = physiology.full_activity_expenditure_rate(org, cfg)
    horizon_s = max(float(org.genome[STARV_HORIZON]), cfg.dt_seconds)
    reserve = p_full * horizon_s
    return min(physiology.energy_max(org, cfg), max(0.0, reserve))


def growth_available_energy_j(org, cfg) -> float:
    return max(0.0, org.energy - protected_growth_reserve_j(org, cfg))


def _absorb_nutrient_luca(self, orgs, phis, areas, key):
    """Physical precursor assimilation with maintenance-first Energy allocation.

    Precursor is still Matter feedstock.  Uptake can proceed only with Energy
    above the protected homeostatic reserve.  At steady state this makes growth
    consume the post-maintenance surplus rather than draining stored Energy.
    """
    cfg = self.cfg
    if not cfg.physical_mode:
        # The LUCA proxy is a physical-mode experiment only.
        return base._ORIG_ABSORB_NUTRIENT(self, orgs, phis, areas, key)

    stock = float(self.world.nutrients[key])
    if stock <= 0.0:
        return

    rate_step = cfg.nutrient_uptake_rate_matter_per_h / 3600.0 * cfg.dt_seconds
    cost_per_matter = cfg.growth_energy_j_per_kgdw * cfg.matter_unit_to_kgdw
    if cost_per_matter <= 0.0:
        return

    demands = []
    for o, phi in zip(orgs, phis):
        a = o.genome[NUTRIENT_ABS]
        if a <= 1e-6:
            demands.append(0.0)
            continue
        room = cfg.matter_cap_frac * o.target_size - o.matter
        if room <= 0.0:
            demands.append(0.0)
            continue

        uf = physiology.uptake_factor(o.starve_state, cfg)
        growth_budget_j = growth_available_energy_j(o, cfg)
        affordable = growth_budget_j / cost_per_matter
        raw = rate_step * a * phi * uf
        demands.append(min(raw, room, affordable))

    scale = self._demand_scale(demands, stock)
    if scale <= 0.0:
        return

    gains = []
    for o, d in zip(orgs, demands):
        if d <= 0.0:
            continue
        u = d * scale

        # Re-evaluate the reserve immediately before spending to make the rule
        # robust to any earlier per-cell operation.
        budget_j = growth_available_energy_j(o, cfg)
        u = min(u, budget_j / cost_per_matter)
        if u <= 0.0:
            continue
        cost = cost_per_matter * u

        o.matter += u
        o.energy -= cost
        self.energy_out_cum += cost
        gains.append(u)

    taken = math.fsum(gains)
    self.world.nutrients[key] = max(0.0, stock - taken)
    self.flows["nutrient"] += taken


# run_exp15 already installs the Phase0 semantic fixes for precursor targeting
# and physical offspring placement.  Replace only its old "all stored Energy is
# affordable for growth" nutrient implementation.
Simulation._absorb_nutrient = _absorb_nutrient_luca


def run_luca(arm: str, seed: int, outdir: Path, days: float) -> dict:
    summary = _BASE_RUN(arm, seed, outdir, days)
    summary["experiment"] = "Exp15 V1.9 LUCA-proxy attempt 2"
    summary["luca_proxy"] = dict(LUCA_PROXY)
    summary["luca_proxy"].update({
        "h2_km_molm3": LUCA_PROXY["h2_qmax_mmol_gdw_h"]
        / LUCA_PROXY["h2_first_order_l_gdw_h"],
        "h2_usable_energy_j_per_mol": LUCA_PROXY["atp_per_h2_mol"]
        * LUCA_PROXY["atp_phosphorylation_j_per_mol"],
        "growth_energy_j_per_kgdw": (
            1000.0 / LUCA_PROXY["growth_yield_gdw_per_mol_atp"]
        ) * LUCA_PROXY["atp_phosphorylation_j_per_mol"],
        "allocation": (
            "H2 acquisition -> protected homeostatic runway -> "
            "growth from surplus -> maintenance/movement/repair"
        ),
    })
    summary["formal_semantic_notes"] = list(summary.get("formal_semantic_notes", [])) + [
        "Attempt 2 seeds a literature-constrained LUCA-like acetogen proxy; it does not model abiogenesis.",
        "Growth cannot consume Energy below P_full * starvation_horizon.",
        "H2 source boundary is 10 mM, within Lost City-type serpentinizing vent measurements.",
        "ATP phosphorylation potential uses 32.1 kJ/mol measured for A. woodii on H2+CO2.",
        "Maintenance ATP demand uses 0.29 mmol ATP/(gDW h) A. woodii proxy.",
    ]
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


base.run = run_luca


if __name__ == "__main__":
    base.main()
