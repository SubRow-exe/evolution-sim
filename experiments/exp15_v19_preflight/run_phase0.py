"""V1.9 physical-scale Phase 0 preflight.

Formal Exp15ではない。parameter sweep/tuningは行わず、事前登録したreference値を
そのまま検証する。FAIL時も値を変えず結果をJSONへ保存して終了する。
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from evosim.config import Config
from evosim.genome import INITIAL_GENOME, MOVE_POWER, NUTRIENT_ABS, REPRO_HORIZON
from evosim import physiology
from evosim.simulation import Simulation
from evosim.world import World, VENT_BAND_EDGES


GRID = 40
DX = 5.0e-4
WORLD = GRID * DX
DEPTH = 5.0e-4
SOURCE_C = 1.0  # mol/m^3 = 1 mM
SINGLE_CENTER = (20, 20)
FOUR_CENTERS = ((10, 10), (10, 30), (30, 10), (30, 30))
RADIAL_D = (0, 2, 4, 8, 12, 16)


def make_cfg(dt: float, initial_population: int, n_vents: int = 1) -> Config:
    # NOTE: PR #67 behavior currently treats speed_coef as displacement/step even in
    # physical_mode. Phase 0 B/D set MOVE_POWER=0; Phase 0 C is therefore qualitative
    # only for exposure/sensing until core movement dt semantics are corrected.
    return Config(
        physical_mode=True,
        dt_seconds=dt,
        world_width=WORLD,
        world_height=WORLD,
        cell_size=DX,
        effective_depth_m=DEPTH,
        n_vents=n_vents,
        vent_radius_cells=2,
        h2_source_concentration_molm3=SOURCE_C,
        h2_diffusion_m2s=5.0e-9,
        h2_exchange_tau_s=900.0,
        h2_subcycle_alpha_max=0.20,
        initial_population=initial_population,
        initial_energy=0.0,
        initial_matter=0.50,
        nutrient_initial=0.0,
        nutrient_diffusion=0.0,
        child_matter_frac=0.50,
        birth_overhead=0.0,
        repro_matter_frac=1.0,
        metabolic_damage=0.0,
        movement_damage=0.0,
        initial_jitter_sigma=0.0,
        phototrophy_innovation_prob=0.0,
        phototrophy_loss_prob=0.0,
        light_cycle_enabled=True,
        light_cycle_period_ticks=max(1, int(round(86400.0 / dt))),
        light_day_fraction=0.5,
        # Simulation.stim_alpha is still step-based on this branch; 20 s / dt is the
        # compatible representation of the registered physical memory timescale.
        memory_tau=max(20.0 / dt, 1e-9),
        # Keep organism boundary radius in metre-scale coordinates for this preflight.
        radius_coef=6.2e-7,
        # Physical-mode physiology interprets this as m/s. behavior currently omits
        # *dt for displacement; P0-C records this implementation warning explicitly.
        speed_coef=40.0e-6,
        sense_coef=5.0e-4,
        stats_interval=10**9,
        snapshot_interval=10**9,
        max_population_halt=100000,
    )


def set_sources(world: World, centers: tuple[tuple[int, int], ...]) -> None:
    mask = np.zeros_like(world.h2, dtype=bool)
    for ix, iy in centers:
        mask[ix, iy] = True
    world.h2_mask = mask
    world.vent_centers = list(centers)
    world.h2_source_flux = np.zeros_like(world.h2)
    world.h2_source_flux[mask] = 1.0
    world.h2_source_total = float(world.h2_source_flux.sum())
    ii, jj = np.meshgrid(np.arange(world.h2.shape[0]), np.arange(world.h2.shape[1]), indexing="ij")
    d = np.full_like(world.h2, np.inf, dtype=float)
    for vx, vy in centers:
        d = np.minimum(d, np.hypot(ii - vx, jj - vy))
    world.vent_band = np.digitize(d, VENT_BAND_EDGES).astype(np.int8)
    world.h2[:] = 0.0


def warm_world(world: World, seconds: float) -> dict[str, float]:
    n = int(round(seconds / world.cfg.dt_seconds))
    start = world.total_h2()
    source_in = 0.0
    loss = 0.0
    min_c = float("inf")
    for _ in range(n):
        src, out = world.update()
        source_in += src
        loss += out
        min_c = min(min_c, float(world.h2.min()))
    final = world.total_h2()
    residual = final - (start + source_in - loss)
    return {
        "steps": n,
        "start_mol": start,
        "source_in_mol": source_in,
        "exchange_loss_mol": loss,
        "final_mol": final,
        "ledger_residual_mol": residual,
        "min_concentration_molm3": min_c,
        "max_concentration_molm3": float(world.h2.max()),
    }


def radial_profile(world: World, center: tuple[int, int] = SINGLE_CENTER) -> dict[str, float]:
    cx, cy = center
    out: dict[str, float] = {}
    for d in RADIAL_D:
        ix = min(world.h2.shape[0] - 1, cx + d)
        out[str(d)] = float(world.h2[ix, cy])
    return out


def set_reference_org(org, cfg: Config, move: bool = False) -> None:
    g = INITIAL_GENOME.copy()
    g[NUTRIENT_ABS] = 0.0
    g[REPRO_HORIZON] = 43200.0
    if not move:
        g[MOVE_POWER] = 0.0
    org.genome = g
    org.matter = 0.50
    org.damage = 0.0
    org.energy = 0.5 * physiology.energy_max(org, cfg)


def reset_sim_ledger(sim: Simulation) -> None:
    sim.energy_in_cum = 0.0
    sim.energy_out_cum = 0.0
    sim.h2_influx_cum = 0.0
    sim.h2_loss_cum = 0.0
    sim.h2_biological_uptake_mol_cum = 0.0
    sim.initial_system_energy = sim.system_energy()
    sim.initial_system_matter = sim.system_matter()


def p0_a(dt: float = 10.0) -> dict:
    cfg = make_cfg(dt, 0, 1)
    rng = np.random.Generator(np.random.PCG64(101))
    w = World(cfg, rng)
    set_sources(w, (SINGLE_CENTER,))
    ledger = warm_world(w, 6 * 3600.0)
    profile = radial_profile(w)
    vals = [profile[str(d)] for d in RADIAL_D]
    monotone = all(vals[i] >= vals[i + 1] - 1e-12 for i in range(len(vals) - 1))
    residual_scale = max(ledger["source_in_mol"], ledger["final_mol"], 1e-30)
    pass_ = (
        0.90 * SOURCE_C <= profile["0"] <= 1.01 * SOURCE_C
        and monotone
        and ledger["min_concentration_molm3"] >= -1e-12
        and abs(ledger["ledger_residual_mol"]) / residual_scale < 1e-8
    )
    return {"pass": bool(pass_), "ledger": ledger, "radial_profile_molm3": profile,
            "monotone_nonincreasing": bool(monotone)}


def p0_b(dt: float = 10.0) -> dict:
    cfg = make_cfg(dt, len(RADIAL_D), 1)
    sim = Simulation(cfg, seed=202)
    set_sources(sim.world, (SINGLE_CENTER,))
    warm = warm_world(sim.world, 6 * 3600.0)
    cx, cy = SINGLE_CENTER
    rows = []
    for org, d in zip(sim.organisms, RADIAL_D):
        set_reference_org(org, cfg, move=False)
        org.x, org.y = sim.world.cell_center(cx + d, cy)
        c = float(sim.world.h2[cx + d, cy])
        p_in = (physiology.physical_h2_uptake_rate_mol_s(
            c, org.matter, org.genome[6], 1.0, cfg) * cfg.h2_usable_energy_j_per_mol)
        p_full = physiology.full_activity_expenditure_rate(org, cfg)
        rows.append({
            "distance_cells": d,
            "local_h2_molm3": c,
            "p_income_w_initial": p_in,
            "p_full_w_initial": p_full,
            "net_power_w_initial": p_in - p_full,
            "initial_energy_j": org.energy,
            "org_id": org.id,
        })
    reset_sim_ledger(sim)
    alive_ids = {o.id for o in sim.organisms}
    death_s: dict[int, float] = {}
    n_steps = int(round(24 * 3600.0 / dt))
    for step in range(1, n_steps + 1):
        sim.step()
        now = {o.id for o in sim.organisms}
        for oid in alive_ids - now:
            death_s.setdefault(oid, step * dt)
        alive_ids = now
    by_id = {o.id: o for o in sim.organisms}
    for r in rows:
        oid = r.pop("org_id")
        o = by_id.get(oid)
        r["alive_24h"] = o is not None
        r["final_energy_j"] = float(o.energy) if o is not None else 0.0
        r["death_time_s"] = death_s.get(oid)
    pos = [r for r in rows if r["net_power_w_initial"] > 0.0]
    neg = [r for r in rows if r["net_power_w_initial"] < 0.0]
    pass_ = bool(pos and neg)
    return {"pass": pass_, "warmup": warm, "rows": rows,
            "positive_bands": len(pos), "negative_bands": len(neg)}


def p0_c(dt: float = 10.0) -> dict:
    cfg = make_cfg(dt, 100, 4)
    sim = Simulation(cfg, seed=303)
    set_sources(sim.world, FOUR_CENTERS)
    warm_world(sim.world, 6 * 3600.0)
    for org in sim.organisms:
        set_reference_org(org, cfg, move=True)
    reset_sim_ledger(sim)

    q75 = float(np.quantile(sim.world.h2, 0.75))
    exp_min = {o.id: float("inf") for o in sim.organisms}
    exp_max = {o.id: 0.0 for o in sim.organisms}
    samples = high = starved = 0
    n_steps = int(round(48 * 3600.0 / dt))
    sample_every = max(1, int(round(600.0 / dt)))
    for step in range(1, n_steps + 1):
        sim.step()
        if step % sample_every:
            continue
        for o in sim.organisms:
            c = sim.world.sample(sim.world.h2, o.x, o.y)
            exp_min[o.id] = min(exp_min.get(o.id, c), c)
            exp_max[o.id] = max(exp_max.get(o.id, c), c)
            samples += 1
            if c >= q75:
                high += 1
            if o.starve_state < 0.99:
                starved += 1
    heterogeneous = sum(
        1 for oid in exp_max
        if exp_min.get(oid, float("inf")) < float("inf")
        and exp_max[oid] - exp_min[oid] > 0.01 * SOURCE_C
    )
    dq_abs = float(sim.stim_obs.get("dq_abs_sum", 0.0))
    pass_ = samples > 0 and high > 0 and starved > 0 and dq_abs > 0.0 and heterogeneous > 0
    return {
        "pass_qualitative": bool(pass_),
        "implementation_warning": (
            "PR #67 physical behavior still omits dt_seconds in position displacement; "
            "P0-C is qualitative only until core movement semantics are corrected."
        ),
        "alive_48h": len(sim.organisms),
        "samples": samples,
        "high_h2_occupancy_fraction": (high / samples if samples else 0.0),
        "starvation_active_fraction": (starved / samples if samples else 0.0),
        "agents_with_gt_1pct_source_exposure_range": heterogeneous,
        "dq_abs_sum": dq_abs,
    }


def dt_case(dt: float) -> dict:
    cfg = make_cfg(dt, 1, 1)
    sim = Simulation(cfg, seed=404)
    set_sources(sim.world, (SINGLE_CENTER,))
    warm_world(sim.world, 6 * 3600.0)
    profile = radial_profile(sim.world)
    org = sim.organisms[0]
    set_reference_org(org, cfg, move=False)
    org.x, org.y = sim.world.cell_center(SINGLE_CENTER[0] + 4, SINGLE_CENTER[1])
    e0 = org.energy
    emax = physiology.energy_max(org, cfg)
    reset_sim_ledger(sim)
    n_steps = int(round(24 * 3600.0 / dt))
    death_time = None
    for step in range(1, n_steps + 1):
        sim.step()
        if not sim.organisms:
            death_time = step * dt
            break
    final_e = float(sim.organisms[0].energy) if sim.organisms else 0.0
    return {"dt_s": dt, "profile": profile, "initial_energy_j": e0,
            "emax_j": emax, "final_energy_j": final_e,
            "alive_24h": bool(sim.organisms), "death_time_s": death_time}


def p0_d() -> dict:
    cases = {str(dt): dt_case(dt) for dt in (2.5, 5.0, 10.0)}
    a = cases["5.0"]
    b = cases["10.0"]
    prof_err = max(abs(a["profile"][str(d)] - b["profile"][str(d)]) for d in RADIAL_D) / SOURCE_C
    if a["alive_24h"] and b["alive_24h"]:
        scale = max(a["emax_j"], 1e-30)
        energy_err = abs(a["final_energy_j"] - b["final_energy_j"]) / scale
        survival_match = True
    elif (not a["alive_24h"]) and (not b["alive_24h"]):
        ta = float(a["death_time_s"] or 0.0)
        tb = float(b["death_time_s"] or 0.0)
        energy_err = abs(ta - tb) / max(ta, tb, 1.0)
        survival_match = True
    else:
        energy_err = float("inf")
        survival_match = False
    pass_ = survival_match and prof_err <= 0.05 and energy_err <= 0.05
    return {"pass": bool(pass_), "profile_max_abs_error_5s_vs_10s_source_fraction": prof_err,
            "energy_or_deathtime_error_5s_vs_10s": energy_err, "cases": cases}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="phase0_results.json")
    args = ap.parse_args()

    result = {
        "status": "V1.9 Phase 0 preflight; NOT formal Exp15",
        "no_parameter_tuning": True,
        "core_known_gaps": [
            "physical behavior displacement currently omits dt_seconds",
            "physical maintenance currently does not reduce basal power with starvation state",
            "physical-mode core still builds 13-cell source disks; this harness overrides to 1-cell sources",
        ],
        "P0_A": p0_a(),
        "P0_B": p0_b(),
        "P0_C": p0_c(),
        "P0_D": p0_d(),
    }
    # P0-C is intentionally qualitative because of the known core movement-unit gap.
    result["dispatch_gate_pass"] = bool(
        result["P0_A"]["pass"] and result["P0_B"]["pass"] and result["P0_D"]["pass"]
        and result["P0_C"]["pass_qualitative"] and not result["core_known_gaps"]
    )
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
