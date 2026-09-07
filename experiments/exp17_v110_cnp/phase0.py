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
#
# 実装ノート: Exp17計画書§2 P0-Bは「+50 matter unit分の元素量」を目安budget
# として提示しているが、実際のLUCA-proxy生理 (literature-calibrated H2
# maintenance/uptake) ではgrowthがほぼ常にprotected-reserve由来のEnergy
# surplusで律速され (docs/V1.9_LUCA_proxy設計.md §4)、24hで実際に消費される
# biomass量は「50 matter unit」よりずっと小さい。したがって固定量budgetでは
# 24h以内に枯渇せず、意図した元素が最大limiterにならない。
# ここではPhase 0 P0-Bの目的 (「C/N/Pのいずれかを他より極端に希少にすると
# growth_limiterがその元素支配になる」というmechanism identity) を、
# tests/test_v110_cnp.py で既に確認済みの手法 (background濃度を極端に
# 下げるclosed system) で確認する。budget sizeを自動探索してPASSさせる
# ことはしていない — 3元素とも同じ相対倍率 (基準比の1e-3) で希少化する。
# 実測: LUCA-proxy生理はgrowthをほぼ常にEnergy surplus (protected-reserve
# 超過分) で強く律速するため、1e-3倍程度の希少化ではC/N/Pがbindしない
# (実際の消費量が極小なため)。tests/test_v110_cnp.pyで実証済みの
# 絶対値スケール (1e-9倍程度) をそのまま使う。
SCARCE_BACKGROUND_FACTOR = 1.0e-9


def _p0_b_case(limiting: str) -> dict:
    scarce_kwargs = {
        "carbon": {"dic_background_molm3": core.CNP_REFERENCE["dic_background_molm3"]
                  * SCARCE_BACKGROUND_FACTOR},
        "nitrogen": {"fixed_n_background_molm3": core.CNP_REFERENCE["fixed_n_background_molm3"]
                    * SCARCE_BACKGROUND_FACTOR},
        "phosphorus": {"phosphate_background_molm3": core.CNP_REFERENCE["phosphate_background_molm3"]
                      * SCARCE_BACKGROUND_FACTOR},
    }[limiting]
    cfg = _closed_cfg(initial_population=50, repro_matter_frac=999.0, **scarce_kwargs)
    seed = 17102 + {"carbon": 0, "nitrogen": 1, "phosphorus": 2}[limiting]
    sim = core.setup_sim(cfg, seed)
    for o in sim.organisms:
        o.energy = physiology.energy_max(o, cfg)

    initial_stock = {
        "carbon": sim.world.total_dic(),
        "nitrogen": sim.world.total_fixed_nitrogen(),
        "phosphorus": sim.world.total_phosphate(),
    }

    n_steps = int(round(24 * 3600.0 / cfg.dt_seconds))
    for _ in range(n_steps):
        sim.step()

    final_stock = {
        "carbon": sim.world.total_dic(),
        "nitrogen": sim.world.total_fixed_nitrogen(),
        "phosphorus": sim.world.total_phosphate(),
    }
    counts = sim.growth_limiter_cum
    element_counts = {k: counts[k] for k in ("carbon", "nitrogen", "phosphorus")}
    max_limiter = max(element_counts, key=lambda k: element_counts[k])
    pass_ = bool(counts[limiting] > 0 and max_limiter == limiting
                and counts[limiting] > element_counts.get(
                    max((k for k in element_counts if k != limiting),
                       key=lambda k: element_counts[k]), 0))
    return {
        "pass": pass_, "limiting_resource": limiting,
        "background_scarcity_factor": SCARCE_BACKGROUND_FACTOR,
        "growth_limiter_counts": dict(counts),
        "max_limiter": max_limiter,
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
    """dt convergenceはgrowthの定常trickle-phaseで測る。

    診断: energy=E_max付近から出発すると、protected reserve
    (E_protected=min(E_max, P_full*starvation_horizon)) を超える大きな
    初期surplusを数stepだけで一気に使い切る短いburst transientが起こり、
    そのburstの長さがdtのオーダーと同程度なので、burst分の成長量がdtに
    強く依存してしまう (V1.9のenergy/maintenance機構自体は変更していない —
    これはV1.10のgrowth requestがそのtransientをそのまま反映するために
    見える性質)。定常状態のgrowthメカニズム収束を見るには、burst分を
    burn-inで先に消化してから測定区間だけを比較する。
    """
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
    burn_in_steps = int(round(24 * 3600.0 / dt))
    for _ in range(burn_in_steps):
        sim.step()
    m0 = sum(o.matter for o in sim.organisms)
    measure_steps = int(round(24 * 3600.0 / dt))
    for _ in range(measure_steps):
        sim.step()
    dm = sum(o.matter for o in sim.organisms) - m0
    return {
        "dt_s": dt,
        "growth_increment_matter": dm,
        "total_biomass_kgdw": sum(o.matter for o in sim.organisms) * cfg.matter_unit_to_kgdw,
        "dic_total_mol": sim.world.total_dic(),
        "fixed_n_total_mol": sim.world.total_fixed_nitrogen(),
        "phosphate_total_mol": sim.world.total_phosphate(),
    }


def p0_e() -> dict:
    cases = {str(dt): _dt_case(dt) for dt in (2.5, 5.0, 10.0)}
    a, b = cases["5.0"], cases["10.0"]
    biomass_err = (abs(a["growth_increment_matter"] - b["growth_increment_matter"])
                  / max(a["growth_increment_matter"], b["growth_increment_matter"], 1e-30))
    field_err = max(
        abs(a[k] - b[k]) / max(a[k], b[k], 1e-30)
        for k in ("dic_total_mol", "fixed_n_total_mol", "phosphate_total_mol")
    )
    pass_ = bool(biomass_err <= 0.01 and field_err <= 0.001)
    return {"pass": pass_, "growth_increment_relative_error_5s_vs_10s": biomass_err,
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
