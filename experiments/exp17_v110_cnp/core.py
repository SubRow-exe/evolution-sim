"""Exp17 V1.10 C/N/P resource decomposition — shared run core.

正本: docs/V1.10_CNP資源分解_実装仕様.md / docs/Exp17_V1.10_CNP資源分解_実験計画.md

V1.9確定値 (iLUCA genome / H2 baseline / Energy physiology) は
experiments/luca_proxy/run_luca_proxy.py (Exp15 attempt2 + Exp16で実際に
validateされたLUCA-like proxy + Phase0 semantic fixes) をそのまま再利用し、
V1.10で追加するのはexplicit_cnp_resources=True関連のConfig差し替えと
CNP固有の観測だけ (V1.10をV1.9 PRへ混ぜない/V1.9を書き換えない、という
version境界を実装でも守るため)。
"""
from __future__ import annotations

import csv
import dataclasses
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LUCA_DIR = ROOT / "experiments" / "luca_proxy"
EXP15_DIR = ROOT / "experiments" / "exp15_v19"
PREFLIGHT_DIR = ROOT / "experiments" / "exp15_v19_preflight"
for p in (ROOT, LUCA_DIR, EXP15_DIR, PREFLIGHT_DIR):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import run_luca_proxy as luca  # noqa: E402  (installs physical_overrides + LUCA_PROXY baseline)
from run_phase0 import set_sources, warm_world  # noqa: E402

from evosim import physiology  # noqa: E402
from evosim.config import Config  # noqa: E402
from evosim.genome import (GENE_NAMES, REPRO_INVEST, STARV_HORIZON,  # noqa: E402
                           STORAGE_CAP, REPRO_HORIZON)
from evosim.simulation import Simulation  # noqa: E402

DT = 10.0
FOUR_CENTERS = ((10, 10), (10, 30), (30, 10), (30, 30))  # V1.9 baseline square layout
SAMPLE_EVERY_S = 600.0
SNAPSHOT_EVERY_S = 21600.0

# V1.10 C/N/P reference (docs/V1.10_CNP資源分解_実装仕様.md §1)
CNP_REFERENCE = dict(
    explicit_cnp_resources=True,
    nutrient_initial=0.0,  # V1.9 generic Matter poolをformal V1.10では不使用 (docs §8)
    dic_background_molm3=2.2,
    fixed_n_background_molm3=0.010,
    phosphate_background_molm3=0.001,
    d_dic_m2s=2.0e-9,
    d_fixed_n_m2s=2.0e-9,
    d_phosphate_m2s=0.8e-9,
    cnp_exchange_tau_s=900.0,
)


def make_cfg(**overrides) -> Config:
    """V1.9 LUCA-proxy物理baseline + V1.10 CNP referenceのformal Exp17 config。

    全continuous genesを固定した iLUCA genome / H2 baseline / Energy physiology
    はluca.make_cfg("A")由来でV1.9確定値のまま変更しない (Exp17_V1.10_...md §3/7)。
    """
    cfg = luca.make_cfg("A")  # arm="A" -> 全genes fixed, LUCA_PROXY校正済み
    cfg = dataclasses.replace(cfg, **CNP_REFERENCE)
    if overrides:
        cfg = dataclasses.replace(cfg, **overrides)
    return cfg


def setup_sim(cfg: Config, seed: int) -> Simulation:
    """LUCA-like daughter cell初期状態 (docs/V1.9_LUCA_proxy設計.md §5) を再現する。"""
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
    # H2 warm-upはenergy/H2台帳を消費しないが、Energyを直接設定したのでledgerを
    # 明示的にreset時点 (t=0) から積算し直す (run_exp15.reset_sim_ledger と同じ)。
    sim.energy_in_cum = 0.0
    sim.energy_out_cum = 0.0
    sim.h2_influx_cum = 0.0
    sim.h2_loss_cum = 0.0
    sim.h2_biological_uptake_mol_cum = 0.0
    sim.c_in_external_cum = 0.0
    sim.c_out_external_cum = 0.0
    sim.n_in_external_cum = 0.0
    sim.n_out_external_cum = 0.0
    sim.p_in_external_cum = 0.0
    sim.p_out_external_cum = 0.0
    sim.c_uptake_cum = 0.0
    sim.n_uptake_cum = 0.0
    sim.p_uptake_cum = 0.0
    sim.growth_limiter_cum = {k: 0 for k in sim.growth_limiter_cum}
    sim.initial_system_energy = sim.system_energy()
    sim.initial_system_matter = sim.system_matter()
    return sim


def qstats(values: list[float]) -> dict:
    if not values:
        return {"mean": None, "median": None, "q10": None, "q90": None}
    a = np.asarray(values, dtype=float)
    return {"mean": float(a.mean()), "median": float(np.median(a)),
           "q10": float(np.quantile(a, 0.10)), "q90": float(np.quantile(a, 0.90))}


def sample(sim: Simulation, t_s: float) -> dict:
    orgs = sim.organisms
    row = {
        "time_s": t_s, "time_days": t_s / 86400.0,
        "population": len(orgs),
        "births_cum": sim.births_cum, "deaths_cum": sim.deaths_cum,
        "c_uptake_cum_mol": sim.c_uptake_cum,
        "n_uptake_cum_mol": sim.n_uptake_cum,
        "p_uptake_cum_mol": sim.p_uptake_cum,
        "c_in_external_cum_mol": sim.c_in_external_cum,
        "c_out_external_cum_mol": sim.c_out_external_cum,
        "n_in_external_cum_mol": sim.n_in_external_cum,
        "n_out_external_cum_mol": sim.n_out_external_cum,
        "p_in_external_cum_mol": sim.p_in_external_cum,
        "p_out_external_cum_mol": sim.p_out_external_cum,
        "dic_total_mol": sim.world.total_dic(),
        "fixed_n_total_mol": sim.world.total_fixed_nitrogen(),
        "phosphate_total_mol": sim.world.total_phosphate(),
        "dic_mean_molm3": float(sim.world.dic.mean()),
        "fixed_n_mean_molm3": float(sim.world.fixed_nitrogen.mean()),
        "phosphate_mean_molm3": float(sim.world.phosphate.mean()),
    }
    for k, v in sim.growth_limiter_cum.items():
        row[f"growth_limiter_{k}_cum"] = v
    if not orgs:
        row.update({
            "max_generation_alive": None, "mean_runway_s": None,
            "starvation_active_fraction": None, "mean_local_h2_molm3": None,
            "total_biomass_kgdw": 0.0,
        })
        return row
    runways = [physiology.runway(o, sim.cfg) for o in orgs]
    local_h2 = [sim.world.sample(sim.world.h2, o.x, o.y) for o in orgs]
    row.update({
        "max_generation_alive": max(o.generation for o in orgs),
        "mean_runway_s": float(np.mean(runways)),
        "starvation_active_fraction": float(np.mean([o.starve_state < 0.99 for o in orgs])),
        "mean_local_h2_molm3": float(np.mean(local_h2)),
        "total_biomass_kgdw": sum(o.matter for o in orgs) * sim.cfg.matter_unit_to_kgdw,
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


def run(seed: int, outdir: Path, days: float, write_snapshots: bool = True) -> dict:
    """1 formal run (Phase A / Phase B 1 condition 分)。成果物を outdir へ保存する。"""
    outdir.mkdir(parents=True, exist_ok=True)
    cfg = make_cfg()
    sim = setup_sim(cfg, seed)
    c0 = sim.system_carbon()
    n0 = sim.system_nitrogen()
    p0 = sim.system_phosphorus()

    (outdir / "effective_config.json").write_text(
        json.dumps(dataclasses.asdict(cfg), indent=2), encoding="utf-8")
    (outdir / "initial_genome.json").write_text(
        json.dumps({
            "gene_names": GENE_NAMES,
            "genome": [float(v) for v in sim.organisms[0].genome],
            "fixed_genes": list(cfg.fixed_genes),
        }, indent=2), encoding="utf-8")

    total_steps = int(round(days * 86400.0 / DT))
    sample_every = max(1, int(round(SAMPLE_EVERY_S / DT)))
    snapshot_every = max(1, int(round(SNAPSHOT_EVERY_S / DT)))

    known = {o.id for o in sim.organisms}
    birth_step = {o.id: 0 for o in sim.organisms}
    generations_seen = [o.generation for o in sim.organisms]
    generation_intervals_h: list[float] = []
    timeseries = [sample(sim, 0.0)]
    pop_auc_cell_s = 0.0
    max_pop = len(sim.organisms)
    extinction_time_s = None
    stop_reason = "duration_complete"

    limiter_rows = [dict(time_s=0.0, **{k: v for k, v in sim.growth_limiter_cum.items()})]

    snap_ctx = (gzip.open(outdir / "snapshots.jsonl.gz", "wt", encoding="utf-8")
               if write_snapshots else None)
    try:
        if snap_ctx:
            write_snapshot(snap_ctx, sim, 0.0)
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
            if step % sample_every == 0:
                timeseries.append(sample(sim, t_s))
                limiter_rows.append(dict(time_s=t_s, **sim.growth_limiter_cum))
            if snap_ctx and step % snapshot_every == 0:
                write_snapshot(snap_ctx, sim, t_s)
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
    finally:
        if snap_ctx:
            snap_ctx.close()

    with (outdir / "timeseries.csv").open("w", newline="", encoding="utf-8") as f:
        fields = list(timeseries[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(timeseries)
    with (outdir / "growth_limiter.csv").open("w", newline="", encoding="utf-8") as f:
        fields = list(limiter_rows[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(limiter_rows)

    alive = sim.organisms
    c1, n1, p1 = sim.system_carbon(), sim.system_nitrogen(), sim.system_phosphorus()
    c_residual = c1 - (c0 + sim.c_in_external_cum - sim.c_out_external_cum)
    n_residual = n1 - (n0 + sim.n_in_external_cum - sim.n_out_external_cum)
    p_residual = p1 - (p0 + sim.p_in_external_cum - sim.p_out_external_cum)
    energy_residual = sim.system_energy() - (
        sim.initial_system_energy + sim.energy_in_cum - sim.energy_out_cum)
    h2_ratio = (sim.h2_biological_uptake_mol_cum / sim.h2_influx_cum
                if sim.h2_influx_cum > 0 else None)
    total_limiter = sum(sim.growth_limiter_cum.values())
    limiter_fraction = ({k: v / total_limiter for k, v in sim.growth_limiter_cum.items()}
                        if total_limiter > 0 else {k: None for k in sim.growth_limiter_cum})

    cnp_ledger = {
        "carbon": {
            "system_initial_mol": c0, "system_final_mol": c1,
            "external_in_mol": sim.c_in_external_cum,
            "external_out_mol": sim.c_out_external_cum,
            "biological_uptake_mol": sim.c_uptake_cum,
            "residual_mol": c_residual,
            "residual_relative": c_residual / c1 if c1 > 0.0 else None,
        },
        "nitrogen": {
            "system_initial_mol": n0, "system_final_mol": n1,
            "external_in_mol": sim.n_in_external_cum,
            "external_out_mol": sim.n_out_external_cum,
            "biological_uptake_mol": sim.n_uptake_cum,
            "residual_mol": n_residual,
            "residual_relative": n_residual / n1 if n1 > 0.0 else None,
        },
        "phosphorus": {
            "system_initial_mol": p0, "system_final_mol": p1,
            "external_in_mol": sim.p_in_external_cum,
            "external_out_mol": sim.p_out_external_cum,
            "biological_uptake_mol": sim.p_uptake_cum,
            "residual_mol": p_residual,
            "residual_relative": p_residual / p1 if p1 > 0.0 else None,
        },
    }
    (outdir / "cnp_ledger.json").write_text(json.dumps(cnp_ledger, indent=2), encoding="utf-8")

    summary = {
        "experiment": "Exp17 V1.10 C/N/P resource decomposition",
        "seed": seed,
        "days_requested": days,
        "days_completed": timeseries[-1]["time_s"] / 86400.0,
        "stop_reason": stop_reason,
        "population_initial": cfg.initial_population,
        "population_final": len(alive),
        "population_max": max_pop,
        "population_auc_cell_days": pop_auc_cell_s / 86400.0,
        "births_cum": sim.births_cum,
        "deaths_cum": sim.deaths_cum,
        "deaths_by_cause": sim.deaths_by_cause,
        "extinction_time_h": None if extinction_time_s is None else extinction_time_s / 3600.0,
        "max_generation": max(generations_seen) if generations_seen else 0,
        "median_generation_alive": (float(np.median([o.generation for o in alive]))
                                    if alive else None),
        "generation_interval_h": qstats(generation_intervals_h),
        "generation_interval_count": len(generation_intervals_h),
        "final_mean_runway_s": timeseries[-1].get("mean_runway_s"),
        "final_starvation_active_fraction": timeseries[-1].get("starvation_active_fraction"),
        "h2_biological_uptake_mol": sim.h2_biological_uptake_mol_cum,
        "h2_source_influx_mol": sim.h2_influx_cum,
        "h2_biological_uptake_over_source_influx": h2_ratio,
        "energy_ledger_residual_j": energy_residual,
        "cnp_ledger": cnp_ledger,
        "growth_limiter_counts_cum": dict(sim.growth_limiter_cum),
        "growth_limiter_fraction_cum": limiter_fraction,
        "explicit_cnp_resources": True,
        "no_parameter_tuning": True,
        "formal_semantic_notes": [
            "iLUCA genome / H2 baseline / Energy physiology are V1.9-established "
            "values (experiments/luca_proxy), unchanged for Exp17.",
            "Environmental generic Matter (nutrient_initial=0) is retired; "
            "growth is limited by explicit DIC/fixed-N/phosphate stoichiometry.",
            "system_matter()/matter_ledger_residual is not a meaningful closure "
            "check under explicit_cnp_resources=True (docs V1.10 §H17-4); use "
            "cnp_ledger element residuals instead.",
        ],
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
