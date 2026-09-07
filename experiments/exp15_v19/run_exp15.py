"""Formal Exp15 V1.9 physical-scale runner.

Uses the exact Phase0-validated semantic corrections from
experiments/exp15_v19_preflight/physical_overrides.py.
No parameter sweep or adaptive tuning is performed.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import gzip
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments" / "exp15_v19_preflight"))

from physical_overrides import install as install_phase0_semantics
install_phase0_semantics()

from evosim import behavior, physiology
from evosim.config import Config
from evosim.genome import (
    GENE_NAMES, NUTRIENT_ABS, REPRO_INVEST, STARV_HORIZON,
    STORAGE_CAP, REPRO_HORIZON,
)
from evosim.simulation import Simulation
from run_phase0 import FOUR_CENTERS, set_sources, warm_world

DT = 10.0
DAYS = 10.0
SAMPLE_EVERY = int(600 / DT)
SNAPSHOT_EVERY = int(21600 / DT)
EVOLVE = {"storage_capacity", "starvation_horizon", "reproduction_horizon"}
BASELINE = {
    "storage_capacity": 1.0,
    "starvation_horizon": 1800.0,
    "reproduction_horizon": 3600.0,
}

# Registered formal-run semantic fixes not exercised by Phase0:
# 1) precursor is biomass feedstock, not a movement cue;
# 2) physical precursor uptake shares starvation uptake_factor;
# 3) offspring placement uses metre-scale radii.
_DECIDE_REGISTERED = behavior.decide_and_move
_ORIG_ABSORB_NUTRIENT = Simulation._absorb_nutrient
_ORIG_REPRODUCE = Simulation._try_reproduce


def _decide_without_precursor_target(org, sim):
    if not sim.cfg.physical_mode:
        return _DECIDE_REGISTERED(org, sim)
    saved = float(org.genome[NUTRIENT_ABS])
    org.genome[NUTRIENT_ABS] = 0.0
    try:
        return _DECIDE_REGISTERED(org, sim)
    finally:
        org.genome[NUTRIENT_ABS] = saved


def _absorb_nutrient_registered(self, orgs, phis, areas, key):
    if not self.cfg.physical_mode:
        return _ORIG_ABSORB_NUTRIENT(self, orgs, phis, areas, key)
    cfg = self.cfg
    stock = float(self.world.nutrients[key])
    if stock <= 0.0:
        return
    rate_step = cfg.nutrient_uptake_rate_matter_per_h / 3600.0 * cfg.dt_seconds
    cost_per_matter = cfg.growth_energy_j_per_kgdw * cfg.matter_unit_to_kgdw
    demands = []
    for o in orgs:
        a = o.genome[NUTRIENT_ABS]
        if a <= 1e-6:
            demands.append(0.0)
            continue
        room = cfg.matter_cap_frac * o.target_size - o.matter
        if room <= 0.0 or o.energy <= 0.0:
            demands.append(0.0)
            continue
        uf = physiology.uptake_factor(o.starve_state, cfg)
        affordable = o.energy / max(cost_per_matter, 1e-30)
        demands.append(min(rate_step * a * uf, room, affordable))
    scale = self._demand_scale(demands, stock)
    if scale <= 0.0:
        return
    gains = []
    for o, d in zip(orgs, demands):
        if d <= 0.0:
            continue
        u = d * scale
        cost = cost_per_matter * u
        if cost > o.energy:
            u = o.energy / max(cost_per_matter, 1e-30)
            cost = o.energy
        o.matter += u
        o.energy -= cost
        self.energy_out_cum += cost
        gains.append(u)
    taken = math.fsum(gains)
    self.world.nutrients[key] = max(0.0, stock - taken)
    self.flows["nutrient"] += taken


def _reproduce_physical_position(self, org):
    child = _ORIG_REPRODUCE(self, org)
    if child is None or not self.cfg.physical_mode:
        return child
    cfg = self.cfg
    rp = physiology.physical_radius_m(org.matter, cfg)
    rc = physiology.physical_radius_m(child.matter, cfg)
    dist = rp + rc
    child.x = min(max(org.x + math.cos(child.heading) * dist, rc), cfg.world_width - rc)
    child.y = min(max(org.y + math.sin(child.heading) * dist, rc), cfg.world_height - rc)
    return child


behavior.decide_and_move = _decide_without_precursor_target
Simulation._absorb_nutrient = _absorb_nutrient_registered
Simulation._try_reproduce = _reproduce_physical_position


def make_cfg(arm: str) -> Config:
    fixed = list(GENE_NAMES) if arm == "A" else [g for g in GENE_NAMES if g not in EVOLVE]
    return Config(
        physical_mode=True,
        dt_seconds=DT,
        world_width=0.020,
        world_height=0.020,
        cell_size=5.0e-4,
        effective_depth_m=5.0e-4,
        n_vents=0,
        vent_radius_cells=0,
        h2_source_concentration_molm3=1.0,
        h2_diffusion_m2s=5.0e-9,
        h2_exchange_tau_s=900.0,
        h2_subcycle_alpha_max=0.20,
        initial_population=100,
        initial_energy=0.0,
        initial_matter=0.50,
        nutrient_initial=2.0,
        nutrient_diffusion=0.05,
        child_matter_frac=0.50,
        birth_overhead=0.0,
        repro_matter_frac=1.0,
        metabolic_damage=0.0,
        movement_damage=0.0,
        initial_jitter_sigma=(0.0 if arm == "A" else 0.02),
        fixed_genes=fixed,
        phototrophy_innovation_prob=0.0,
        phototrophy_loss_prob=0.0,
        light_cycle_enabled=True,
        light_cycle_period_ticks=int(86400 / DT),
        light_day_fraction=0.5,
        memory_tau=20.0 / DT,
        radius_coef=6.2e-7,
        speed_coef=40.0e-6,
        sense_coef=5.0e-4,
        stats_interval=SAMPLE_EVERY,
        snapshot_interval=SNAPSHOT_EVERY,
        max_population_halt=5000,
    )


def qstats(values):
    if not values:
        return {"mean": None, "median": None, "q10": None, "q90": None}
    a = np.asarray(values, dtype=float)
    return {
        "mean": float(a.mean()),
        "median": float(np.median(a)),
        "q10": float(np.quantile(a, 0.10)),
        "q90": float(np.quantile(a, 0.90)),
    }


def sample(sim: Simulation, t_s: float) -> dict:
    orgs = sim.organisms
    row = {
        "time_s": t_s,
        "time_days": t_s / 86400.0,
        "population": len(orgs),
        "births_cum": sim.births_cum,
        "deaths_cum": sim.deaths_cum,
    }
    if not orgs:
        row.update({
            "max_generation_alive": None, "mean_runway_s": None,
            "starvation_active_fraction": None, "mean_local_h2_molm3": None,
            "mean_storage_capacity": None, "mean_starvation_horizon_s": None,
            "mean_reproduction_horizon_s": None,
        })
        return row
    runways = [physiology.runway(o, sim.cfg) for o in orgs]
    local_h2 = [sim.world.sample(sim.world.h2, o.x, o.y) for o in orgs]
    row.update({
        "max_generation_alive": max(o.generation for o in orgs),
        "mean_runway_s": float(np.mean(runways)),
        "starvation_active_fraction": float(np.mean([o.starve_state < 0.99 for o in orgs])),
        "mean_local_h2_molm3": float(np.mean(local_h2)),
        "mean_storage_capacity": float(np.mean([o.genome[STORAGE_CAP] for o in orgs])),
        "mean_starvation_horizon_s": float(np.mean([o.genome[STARV_HORIZON] for o in orgs])),
        "mean_reproduction_horizon_s": float(np.mean([o.genome[REPRO_HORIZON] for o in orgs])),
    })
    return row


def write_snapshot(gz, sim: Simulation, t_s: float) -> None:
    agents = []
    for o in sim.organisms:
        agents.append({
            "id": o.id, "parent_id": o.parent_id, "lineage_id": o.lineage_id,
            "generation": o.generation, "x_m": o.x, "y_m": o.y,
            "energy_j": o.energy, "matter": o.matter,
            "storage_capacity": float(o.genome[STORAGE_CAP]),
            "starvation_horizon_s": float(o.genome[STARV_HORIZON]),
            "reproduction_horizon_s": float(o.genome[REPRO_HORIZON]),
            "starve_state": float(o.starve_state),
            "local_h2_molm3": float(sim.world.sample(sim.world.h2, o.x, o.y)),
        })
    gz.write(json.dumps({"time_s": t_s, "agents": agents}, separators=(",", ":")) + "\n")


def setup_sim(arm: str, seed: int) -> Simulation:
    cfg = make_cfg(arm)
    sim = Simulation(cfg, seed=seed)
    set_sources(sim.world, FOUR_CENTERS)
    warm_world(sim.world, 6 * 3600.0)
    for o in sim.organisms:
        o.genome = o.genome.copy()
        o.genome[REPRO_INVEST] = 0.50
        o.matter = 0.50
        o.energy = 0.50 * physiology.energy_max(o, cfg)
        o.damage = 0.0
        o.starve_state = physiology.starvation_state(o, cfg)
    sim.hi_q_mask = sim._build_hi_q_mask()
    sim.energy_in_cum = 0.0
    sim.energy_out_cum = 0.0
    sim.h2_influx_cum = 0.0
    sim.h2_loss_cum = 0.0
    sim.h2_biological_uptake_mol_cum = 0.0
    sim.initial_system_energy = sim.system_energy()
    sim.initial_system_matter = sim.system_matter()
    return sim


def run(arm: str, seed: int, outdir: Path, days: float) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    sim = setup_sim(arm, seed)
    total_steps = int(round(days * 86400.0 / DT))
    initial_gene_means = {
        "storage_capacity": float(np.mean([o.genome[STORAGE_CAP] for o in sim.organisms])),
        "starvation_horizon": float(np.mean([o.genome[STARV_HORIZON] for o in sim.organisms])),
        "reproduction_horizon": float(np.mean([o.genome[REPRO_HORIZON] for o in sim.organisms])),
    }
    known = {o.id for o in sim.organisms}
    birth_step = {o.id: 0 for o in sim.organisms}
    generations_seen = [o.generation for o in sim.organisms]
    generation_intervals_h = []
    timeseries = [sample(sim, 0.0)]
    pop_auc_cell_s = 0.0
    max_pop = len(sim.organisms)
    extinction_time_s = None
    stop_reason = "duration_complete"

    (outdir / "config.json").write_text(
        json.dumps(dataclasses.asdict(sim.cfg), indent=2), encoding="utf-8")

    with gzip.open(outdir / "snapshots.jsonl.gz", "wt", encoding="utf-8") as gz:
        write_snapshot(gz, sim, 0.0)
        for step in range(1, total_steps + 1):
            pop_auc_cell_s += len(sim.organisms) * DT
            sim.step()
            t_s = step * DT
            for o in sim.organisms:
                if o.id not in known:
                    known.add(o.id)
                    generations_seen.append(o.generation)
                    pb = birth_step.get(o.parent_id)
                    if pb is not None:
                        generation_intervals_h.append((o.birth_tick - pb) * DT / 3600.0)
                    birth_step[o.id] = o.birth_tick
            max_pop = max(max_pop, len(sim.organisms))
            if step % SAMPLE_EVERY == 0:
                timeseries.append(sample(sim, t_s))
            if step % SNAPSHOT_EVERY == 0:
                write_snapshot(gz, sim, t_s)
            if not sim.organisms:
                extinction_time_s = t_s
                stop_reason = "extinction"
                if timeseries[-1]["time_s"] != t_s:
                    timeseries.append(sample(sim, t_s))
                break
            if len(sim.organisms) >= sim.cfg.max_population_halt:
                stop_reason = "max_population_halt"
                if timeseries[-1]["time_s"] != t_s:
                    timeseries.append(sample(sim, t_s))
                break

    with (outdir / "timeseries.csv").open("w", newline="", encoding="utf-8") as f:
        fields = list(timeseries[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(timeseries)

    alive = sim.organisms
    final_gene = {
        "storage_capacity": qstats([float(o.genome[STORAGE_CAP]) for o in alive]),
        "starvation_horizon": qstats([float(o.genome[STARV_HORIZON]) for o in alive]),
        "reproduction_horizon": qstats([float(o.genome[REPRO_HORIZON]) for o in alive]),
    }
    n20 = max(1, math.ceil(len(timeseries) * 0.20))
    last20 = timeseries[-n20:]

    def mean_nonnull(field):
        vals = [x[field] for x in last20 if x[field] is not None]
        return float(np.mean(vals)) if vals else None

    final_window_mean = {
        "storage_capacity": mean_nonnull("mean_storage_capacity"),
        "starvation_horizon": mean_nonnull("mean_starvation_horizon_s"),
        "reproduction_horizon": mean_nonnull("mean_reproduction_horizon_s"),
    }
    shift_pct = {
        k: (None if v is None else 100.0 * (v / BASELINE[k] - 1.0))
        for k, v in final_window_mean.items()
    }
    energy_residual = sim.system_energy() - (
        sim.initial_system_energy + sim.energy_in_cum - sim.energy_out_cum)
    matter_residual = sim.system_matter() - sim.initial_system_matter
    h2_ratio = (sim.h2_biological_uptake_mol_cum / sim.h2_influx_cum
                if sim.h2_influx_cum > 0 else None)

    summary = {
        "experiment": "Exp15 V1.9 formal",
        "arm": arm,
        "seed": seed,
        "git_sha": os.environ.get("GITHUB_SHA"),
        "phase0_validated_overrides": True,
        "no_parameter_tuning": True,
        "days_requested": days,
        "days_completed": timeseries[-1]["time_s"] / 86400.0,
        "stop_reason": stop_reason,
        "population_initial": 100,
        "population_final": len(alive),
        "population_max": max_pop,
        "population_auc_cell_days": pop_auc_cell_s / 86400.0,
        "births_cum": sim.births_cum,
        "deaths_cum": sim.deaths_cum,
        "deaths_by_cause": sim.deaths_by_cause,
        "extinction_time_h": None if extinction_time_s is None else extinction_time_s / 3600.0,
        "max_generation": max(generations_seen) if generations_seen else 0,
        "median_generation_alive": float(np.median([o.generation for o in alive])) if alive else None,
        "generation_interval_h": qstats(generation_intervals_h),
        "generation_interval_count": len(generation_intervals_h),
        "initial_gene_means": initial_gene_means,
        "final_gene_stats_alive": final_gene,
        "final20pct_gene_mean": final_window_mean,
        "final20pct_gene_shift_pct_vs_baseline": shift_pct,
        "final_mean_runway_s": timeseries[-1].get("mean_runway_s"),
        "final_starvation_active_fraction": timeseries[-1].get("starvation_active_fraction"),
        "h2_biological_uptake_mol": sim.h2_biological_uptake_mol_cum,
        "h2_source_influx_mol": sim.h2_influx_cum,
        "h2_biological_uptake_over_source_influx": h2_ratio,
        "energy_ledger_residual_j": energy_residual,
        "matter_ledger_residual_matter": matter_residual,
        "formal_semantic_notes": [
            "Phase0-validated SI overrides installed explicitly.",
            "Biomass precursor uptake retained but precursor is excluded as a movement target.",
            "Physical nutrient uptake uses the same starvation uptake_factor as H2.",
            "Physical offspring placement uses metre-scale cell radii.",
        ],
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arm", choices=["A", "B"], required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--days", type=float, default=DAYS)
    p.add_argument("--outdir", type=Path, required=True)
    args = p.parse_args()
    run(args.arm, args.seed, args.outdir, args.days)


if __name__ == "__main__":
    main()
