"""Exp17 V1.10 C/N/P Phase 0 — mechanical/ledger preflight.

正本: docs/Exp17_V1.10_CNP資源分解_実験計画.md §2 (P0-A..E)。
formal experimentではない。parameter sweep/tuningは行わない。

H2側の物理 (field/diffusion/dt convergence) はV1.9 Phase0
(experiments/exp15_v19_preflight/run_phase0.py) で既に検証済みであり、
V1.10はH2を一切変更しないため再検証しない。ここではV1.10で新規追加した
C/N/P stoichiometric growth / recycling / element ledgerだけを検証する。
"""
from __future__ import annotations

import copy
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

from evosim import physiology, stoichiometry  # noqa: E402
from evosim.config import Config  # noqa: E402
from evosim.corpse import Corpse  # noqa: E402
from evosim.genome import GENE_NAMES, NUTRIENT_ABS, PREDATION  # noqa: E402
from evosim.simulation import Simulation  # noqa: E402


def _closed_cfg(**overrides) -> Config:
    """P0のmechanical testは全てclosed system (background exchange OFF) で行う。"""
    kwargs = dict(cnp_background_exchange_enabled=False, initial_jitter_sigma=0.0)
    kwargs.update(overrides)
    return core.make_cfg(**kwargs)


# --- P0-A: closed single-cell growth ---------------------------------------

def p0_a() -> dict:
    cfg = _closed_cfg(initial_population=1, repro_matter_frac=999.0)
    sim = core.setup_sim(cfg, seed=17101)
    o = sim.organisms[0]
    o.matter = 0.30
    o.energy = physiology.energy_max(o, cfg)  # H2十分 (energy is not the limiter)
    m0 = o.matter
    # closed system (exchange OFF) では field->biomass の内部移転だけなので、
    # system_carbon() = field + biomass 合計は成長で変化しない (biomass側で
    # 計上されるため)。ledger PASS条件は「fieldの減少量」=「biomass増加分の
    # 元素換算量」= 生物学的uptake累積、の3つが一致すること。
    c0, n0, p0 = sim.system_carbon(), sim.system_nitrogen(), sim.system_phosphorus()
    n_steps = int(round(6 * 3600.0 / cfg.dt_seconds))
    for _ in range(n_steps):
        sim.step()
    dm = o.matter - m0
    c_expected, n_expected, p_expected = stoichiometry.matter_to_element_mol(dm, cfg)
    c1, n1, p1 = sim.system_carbon(), sim.system_nitrogen(), sim.system_phosphorus()
    # system_carbon (field+biomass) はinternal transferなので不変であるべき
    c_ledger_resid = c1 - c0
    n_ledger_resid = n1 - n0
    p_ledger_resid = p1 - p0
    exp_scale_c = max(c_expected, 1e-30)
    exp_scale_n = max(n_expected, 1e-30)
    exp_scale_p = max(p_expected, 1e-30)
    stoich_err_c = abs(sim.c_uptake_cum - c_expected) / exp_scale_c
    stoich_err_n = abs(sim.n_uptake_cum - n_expected) / exp_scale_n
    stoich_err_p = abs(sim.p_uptake_cum - p_expected) / exp_scale_p
    nonneg = bool((sim.world.dic >= 0).all() and (sim.world.fixed_nitrogen >= 0).all()
                 and (sim.world.phosphate >= 0).all())
    pass_ = bool(
        dm > 0.0 and nonneg
        and stoich_err_c <= 1e-9 and stoich_err_n <= 1e-9 and stoich_err_p <= 1e-9
        and abs(c_ledger_resid) <= 1e-9 * max(c0, 1e-30)
        and abs(n_ledger_resid) <= 1e-9 * max(n0, 1e-30)
        and abs(p_ledger_resid) <= 1e-9 * max(p0, 1e-30)
    )
    return {
        "pass": pass_, "delta_matter": dm,
        "c_uptake_cum_mol": sim.c_uptake_cum, "c_expected_mol": c_expected,
        "n_uptake_cum_mol": sim.n_uptake_cum, "n_expected_mol": n_expected,
        "p_uptake_cum_mol": sim.p_uptake_cum, "p_expected_mol": p_expected,
        "stoichiometric_relative_error": {"c": stoich_err_c, "n": stoich_err_n, "p": stoich_err_p},
        "ledger_residual_relative": {
            "c": c_ledger_resid / max(c0, 1e-30),
            "n": n_ledger_resid / max(n0, 1e-30),
            "p": p_ledger_resid / max(p0, 1e-30),
        },
        "concentration_nonnegative": nonneg,
    }


# --- P0-B: individual limiter sentinels (C / N / P each) -------------------

def _matter_for_element_budget(target_element_matter: float, cfg: Config, factor: float) -> dict:
    """target_element_matterぶんのbiomass成長を賄えるだけの元素量 * factor。"""
    c, n, p = stoichiometry.matter_to_element_mol(target_element_matter, cfg)
    return {"carbon": c * factor, "nitrogen": n * factor, "phosphorus": p * factor}


def _p0_b_case(limiting: str) -> dict:
    cfg = _closed_cfg(initial_population=100, repro_matter_frac=999.0)
    seed = 17102 + {"carbon": 0, "nitrogen": 1, "phosphorus": 2}[limiting]
    sim = core.setup_sim(cfg, seed)
    total_matter = 50.0
    per_org = total_matter / len(sim.organisms)
    for o in sim.organisms:
        o.matter = per_org
        o.energy = physiology.energy_max(o, cfg)

    # intended limiting resourceだけ「+50 matter unit分」、他は「+500 matter unit分」
    budget_tight = _matter_for_element_budget(50.0, cfg, 1.0)
    budget_ample = _matter_for_element_budget(500.0, cfg, 1.0)
    voxel_count = cfg.grid_w * cfg.grid_h
    voxel_volume = sim.world.voxel_volume_m3
    amounts = {
        "carbon": budget_tight["carbon"] if limiting == "carbon" else budget_ample["carbon"],
        "nitrogen": budget_tight["nitrogen"] if limiting == "nitrogen" else budget_ample["nitrogen"],
        "phosphorus": budget_tight["phosphorus"] if limiting == "phosphorus" else budget_ample["phosphorus"],
    }
    sim.world.dic[:, :] = amounts["carbon"] / voxel_count / voxel_volume
    sim.world.fixed_nitrogen[:, :] = amounts["nitrogen"] / voxel_count / voxel_volume
    sim.world.phosphate[:, :] = amounts["phosphorus"] / voxel_count / voxel_volume

    initial_stock = {k: (sim.world.dic if k == "carbon" else
                         sim.world.fixed_nitrogen if k == "nitrogen" else
                         sim.world.phosphate).sum() * voxel_volume
                     for k in ("carbon", "nitrogen", "phosphorus")}

    n_steps = int(round(24 * 3600.0 / cfg.dt_seconds))
    for _ in range(n_steps):
        sim.step()

    final_stock = {
        "carbon": sim.world.total_dic(),
        "nitrogen": sim.world.total_fixed_nitrogen(),
        "phosphorus": sim.world.total_phosphate(),
    }
    counts = sim.growth_limiter_cum
    max_limiter = max(("carbon", "nitrogen", "phosphorus"), key=lambda k: counts[k])
    intended_residual_frac = (final_stock[limiting] / initial_stock[limiting]
                              if initial_stock[limiting] > 0 else None)
    others_ok = all(
        (final_stock[k] / initial_stock[k] if initial_stock[k] > 0 else 1.0) >= 0.50
        for k in ("carbon", "nitrogen", "phosphorus") if k != limiting
    )
    pass_ = bool(
        max_limiter == limiting
        and intended_residual_frac is not None and intended_residual_frac <= 0.05
        and others_ok
    )
    return {
        "pass": pass_, "limiting_resource": limiting,
        "growth_limiter_counts": dict(counts),
        "max_limiter": max_limiter,
        "intended_resource_residual_fraction": intended_residual_frac,
        "other_resources_residual_ok": others_ok,
        "initial_stock_mol": initial_stock, "final_stock_mol": final_stock,
        "final_population": len(sim.organisms),
    }


def p0_b() -> dict:
    cases = {k: _p0_b_case(k) for k in ("carbon", "nitrogen", "phosphorus")}
    pass_ = all(c["pass"] for c in cases.values())
    return {"pass": pass_, "cases": cases}


# --- P0-C: corpse/recycling --------------------------------------------

def p0_c() -> dict:
    cfg = _closed_cfg(initial_population=0)
    sim = Simulation(cfg, seed=17105)
    corpse = Corpse(0.005, 0.005, matter=8.0, energy=0.0)
    sim.corpses.append(corpse)
    c0, n0, p0v = sim.system_carbon(), sim.system_nitrogen(), sim.system_phosphorus()
    n_steps = int(round(24 * 3600.0 / cfg.dt_seconds))
    for _ in range(n_steps):
        sim.step()
    c1, n1, p1 = sim.system_carbon(), sim.system_nitrogen(), sim.system_phosphorus()
    pass_ = bool(abs(c1 - c0) <= 1e-9 * max(c0, 1e-30)
                and abs(n1 - n0) <= 1e-9 * max(n0, 1e-30)
                and abs(p1 - p0v) <= 1e-9 * max(p0v, 1e-30))
    return {
        "pass": pass_, "corpse_remaining": len(sim.corpses),
        "carbon": {"initial_mol": c0, "final_mol": c1},
        "nitrogen": {"initial_mol": n0, "final_mol": n1},
        "phosphorus": {"initial_mol": p0v, "final_mol": p1},
    }


# --- P0-D: predation/waste mechanical bookkeeping ---------------------------

def p0_d() -> dict:
    """PREDATIONをdiagnosticで強制ONするmechanical testのみ (formal Exp17ではOFF)。"""
    fixed = list(GENE_NAMES)
    cfg = _closed_cfg(
        initial_population=2,
        diagnostic_gene_overrides={"predation_efficiency": 3.0, "membrane_strength": 0.0},
        fixed_genes=fixed,
        repro_matter_frac=999.0,
    )
    sim = Simulation(cfg, seed=17106)
    predator, prey = sim.organisms
    predator.matter, prey.matter = 2.0, 2.0
    predator.energy = physiology.energy_max(predator, cfg)
    prey.energy = physiology.energy_max(prey, cfg)
    predator.x = predator.y = prey.x = prey.y = 0.001  # 同一cell
    c0, n0, p0v = sim.system_carbon(), sim.system_nitrogen(), sim.system_phosphorus()
    prey_matter0 = prey.matter
    predator_matter0 = predator.matter

    sim._build_hashes()
    sim._predate(predator)

    prey_matter_loss = prey_matter0 - prey.matter
    predator_matter_gain = predator.matter - predator_matter0
    waste_matter = prey_matter_loss - predator_matter_gain
    c1, n1, p1 = sim.system_carbon(), sim.system_nitrogen(), sim.system_phosphorus()
    pass_ = bool(prey_matter_loss > 0.0
                and abs(c1 - c0) <= 1e-9 * max(c0, 1e-30)
                and abs(n1 - n0) <= 1e-9 * max(n0, 1e-30)
                and abs(p1 - p0v) <= 1e-9 * max(p0v, 1e-30))
    return {
        "pass": pass_,
        "prey_matter_loss": prey_matter_loss,
        "predator_matter_gain": predator_matter_gain,
        "waste_matter": waste_matter,
        "carbon_residual": c1 - c0, "nitrogen_residual": n1 - n0,
        "phosphorus_residual": p1 - p0v,
    }


# --- P0-E: dt convergence ---------------------------------------------------

def _dt_case(dt: float) -> dict:
    # light_cycle_period_ticks/memory_tauはtick単位のConfigなので、dtを変える
    # ときは実時間 (24h周期・20s記憶) を保つよう明示的に再計算する
    # (base run_exp15.make_cfgはDT=10.0固定でこれらを計算しているため)。
    cfg = _closed_cfg(
        initial_population=20, dt_seconds=dt, repro_matter_frac=999.0,
        light_cycle_period_ticks=max(1, int(round(86400.0 / dt))),
        memory_tau=20.0 / dt,
    )
    sim = core.setup_sim(cfg, seed=17107)
    for o in sim.organisms:
        o.energy = physiology.energy_max(o, cfg)
    n_steps = int(round(6 * 3600.0 / dt))
    for _ in range(n_steps):
        sim.step()
    return {
        "dt_s": dt,
        "total_biomass_kgdw": sum(o.matter for o in sim.organisms) * cfg.matter_unit_to_kgdw,
        "dic_total_mol": sim.world.total_dic(),
        "fixed_n_total_mol": sim.world.total_fixed_nitrogen(),
        "phosphate_total_mol": sim.world.total_phosphate(),
    }


def p0_e() -> dict:
    cases = {str(dt): _dt_case(dt) for dt in (2.5, 5.0, 10.0)}
    a, b = cases["5.0"], cases["10.0"]
    biomass_err = (abs(a["total_biomass_kgdw"] - b["total_biomass_kgdw"])
                  / max(a["total_biomass_kgdw"], b["total_biomass_kgdw"], 1e-30))
    field_err = max(
        abs(a[k] - b[k]) / max(a[k], b[k], 1e-30)
        for k in ("dic_total_mol", "fixed_n_total_mol", "phosphate_total_mol")
    )
    pass_ = bool(biomass_err <= 0.01 and field_err <= 0.001)
    return {"pass": pass_, "biomass_relative_error_5s_vs_10s": biomass_err,
           "cnp_field_relative_error_5s_vs_10s": field_err, "cases": cases}


def main() -> None:
    result = {
        "status": "V1.10 Exp17 Phase 0 preflight; NOT formal Exp17",
        "no_parameter_tuning": True,
        "P0_A": p0_a(),
        "P0_B": p0_b(),
        "P0_C": p0_c(),
        "P0_D": p0_d(),
        "P0_E": p0_e(),
    }
    result["dispatch_gate_pass"] = bool(
        result["P0_A"]["pass"] and result["P0_B"]["pass"] and result["P0_C"]["pass"]
        and result["P0_D"]["pass"] and result["P0_E"]["pass"]
    )
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "phase0_v110_results.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
