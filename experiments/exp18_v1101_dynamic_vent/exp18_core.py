"""Exp18 V1.10.1 dynamic hydrothermal vent — shared run core.

正本: docs/V1.10.1_動的熱水噴出口_実装方針.md / docs/Exp18_V1.10.1_動的熱水噴出口_実験計画.md

V1.10確定値 (iLUCA genome / H2 uptake kinetics / Energy physiology / C/N/P
stoichiometry) は experiments/luca_proxy (Exp15/16/17で実際にvalidateされた
LUCA-like proxy) と experiments/exp17_v110_cnp (V1.10 C/N/P working
baseline) をそのまま再利用する。V1.10.1で変えるのはH2 source条件
(h2_source_mode="flux" + temporal/turnover) だけ (docs V1.10.1 §0)。
"""
from __future__ import annotations

import csv
import dataclasses
import gzip
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXP17_DIR = ROOT / "experiments" / "exp17_v110_cnp"
LUCA_DIR = ROOT / "experiments" / "luca_proxy"
EXP15_DIR = ROOT / "experiments" / "exp15_v19"
PREFLIGHT_DIR = ROOT / "experiments" / "exp15_v19_preflight"
for p in (ROOT, EXP17_DIR, LUCA_DIR, EXP15_DIR, PREFLIGHT_DIR):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

# このファイル自身は"exp18_core"という名前で、exp17_v110_cnp/core.pyの
# モジュール名"core"とは衝突しない (physical_overrides + LUCA_PROXY
# baselineはimport時に副作用としてインストールされる。
# experiments/luca_proxy/run_luca_proxy.py 参照)。
import core as _exp17_core  # noqa: E402
import run_phase_c1  # noqa: E402

from evosim import physiology  # noqa: E402
from evosim.config import Config  # noqa: E402
from evosim.genome import (GENE_NAMES, REPRO_HORIZON, REPRO_INVEST,  # noqa: E402
                           STARV_HORIZON, STORAGE_CAP)
from evosim.simulation import Simulation  # noqa: E402
from evosim.world import World  # noqa: E402

DT = 10.0
LEGACY_FOUR_CENTERS = ((10, 10), (10, 30), (30, 10), (30, 30))
SAMPLE_EVERY_S = 600.0
SNAPSHOT_EVERY_S = 21600.0
# V1.9 diagnostic threshold: 248 uM (docs V1.10.1 §9)。1 mol/m^3 == 1 mM
# なので 248 uM = 248e-3 mM = 248e-3 mol/m^3 (248e-6は1000倍小さい誤り)。
H2_HABITABILITY_MOLM3 = 248e-3

# Exp17 Phase C1 human-decision working baseline (docs V1.10.1 §8):
# initial C/N/P = 50x initial-100-organism biomass requirement, exchange OFF.
CNP_BIOMASS_EQUIVALENTS = 50


def base_config() -> Config:
    """V1.10確定値 (iLUCA genome / H2 kinetics / Energy physiology / C/N/P
    stoichiometry) を持つconfig。H2 source条件はこの後で明示的に上書きする。
    """
    cfg = _exp17_core.make_cfg()  # explicit_cnp_resources=True, V1.9 LUCA-proxy baseline
    cnp_overrides = run_phase_c1.backgrounds_for_equivalents(cfg, CNP_BIOMASS_EQUIVALENTS)
    return dataclasses.replace(cfg, **cnp_overrides)


def measure_legacy_f0(warmup_s: float = 6 * 3600.0, measure_s: float = 3600.0) -> dict:
    """Exp18 Phase 0 P0-A: legacy Dirichlet sourceの定常補給量からF0を実測する
    (docs V1.10.1 §4 / Exp18 §2 P0-A)。恣意的なflux値を置かない。
    """
    # 1 mol/m^3 == 1 mmol/L なので "10 mM" は h2_source_concentration_molm3=10.0
    # (V1.9/Exp15-17のLUCA_PROXY baselineと同じ値。1e-3を掛けない)。
    cfg = dataclasses.replace(base_config(), h2_source_mode="dirichlet",
                              h2_source_concentration_molm3=10.0,  # 10 mM
                              n_vents=0, vent_radius_cells=0)
    rng = np.random.Generator(np.random.PCG64(180000))
    world = World(cfg, rng)
    _install_legacy_sources(world, LEGACY_FOUR_CENTERS, cfg)
    n_warmup = int(round(warmup_s / cfg.dt_seconds))
    for _ in range(n_warmup):
        world.update()
    n_measure = int(round(measure_s / cfg.dt_seconds))
    source_in = 0.0
    for _ in range(n_measure):
        inflow, _loss = world.update()
        source_in += inflow
    f_total_legacy = source_in / measure_s
    f0 = f_total_legacy / len(LEGACY_FOUR_CENTERS)
    return {
        "warmup_s": warmup_s, "measure_s": measure_s,
        "source_in_mol": source_in,
        "f_total_legacy_mol_s": f_total_legacy,
        "f0_mol_s": f0,
        "h2_field_snapshot": world.h2.copy(),
    }


def _install_legacy_sources(world: World, centers, cfg: Config) -> None:
    """legacy 1-cell x4 Dirichlet source配置 (docs V1.10.1 §3)。

    core evosimの `_place_vents` はvent_radius_cellsに応じたdisk配置を作る
    ため (formal V1.10.1では使わない、docs §3)、ここでは直接1-cellの
    source_mask/h2_source_flux/vent_centersを組み立てる。
    """
    gw, gh = cfg.grid_w, cfg.grid_h
    mask = np.zeros((gw, gh), dtype=bool)
    for ix, iy in centers:
        mask[ix, iy] = True
    world.h2_mask = mask
    world.vent_centers = list(centers)
    world.h2_source_flux = np.zeros((gw, gh))


def common_initial_h2_field(f0_result: dict) -> np.ndarray:
    """全Exp18 Phase A/Bでt=0のH2 fieldを共通化する (docs V1.10.1 §7)。

    legacy Dirichlet 4-source / 10 mMでwarm-upした結果をそのままコピーする。
    """
    return f0_result["h2_field_snapshot"].copy()


def make_flux_cfg(f0: float, *, temporal: bool = False, turnover: bool = False,
                  evolve_genes: tuple[str, ...] = (), initial_jitter_sigma: float = 0.0,
                  **overrides) -> Config:
    """finite-flux V1.10.1 formal config (docs V1.10.1 §2/5/6, Exp18 §1)。

    `evolve_genes`に挙げたgeneだけfixed_genesから外す (Phase B 2x2 design用)。
    """
    cfg = base_config()
    fixed = [g for g in GENE_NAMES if g not in evolve_genes]
    cfg = dataclasses.replace(
        cfg,
        h2_source_mode="flux",
        h2_vent_flux_mol_s=f0,
        h2_vent_temporal_enabled=temporal,
        h2_vent_turnover_enabled=turnover,
        # base_config()由来 (Exp15 harness) はn_vents=0 (vent配置を
        # harnessが明示するpattern)。flux modeはconfigure_flux_vents()で
        # 明示配置するため、ここでn_vents=4 (legacy geometry) を確定する。
        n_vents=len(LEGACY_FOUR_CENTERS),
        fixed_genes=fixed,
        initial_jitter_sigma=initial_jitter_sigma,
    )
    if overrides:
        cfg = dataclasses.replace(cfg, **overrides)
    return cfg


def setup_sim(cfg: Config, seed: int, initial_h2_field: np.ndarray | None,
             vent_positions=LEGACY_FOUR_CENTERS) -> Simulation:
    """LUCA-like daughter cell初期状態 + dynamic vent geometry (docs §7)。"""
    sim = Simulation(cfg, seed=seed)
    sim.world.configure_flux_vents(vent_positions)
    if initial_h2_field is not None:
        sim.world.h2 = initial_h2_field.copy()
    for o in sim.organisms:
        o.genome = o.genome.copy()
        o.genome[REPRO_INVEST] = 0.50
        o.matter = 0.50
        o.energy = 0.50 * physiology.energy_max(o, cfg)
        o.damage = 0.0
        o.starve_state = physiology.starvation_state(o, cfg)
    sim.hi_q_mask = sim._build_hi_q_mask()
    # t=0からledgerをreset (warm-up中のsource入出力はformal ledgerに含めない。docs §7)
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
    sim.world.vent_turnover_count_cum = 0
    sim.initial_system_energy = sim.system_energy()
    sim.initial_system_matter = sim.system_matter()
    return sim


def qstats(values: list[float]) -> dict:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return {"mean": None, "median": None, "q10": None, "q90": None}
    a = np.asarray(vals, dtype=float)
    return {"mean": float(a.mean()), "median": float(np.median(a)),
           "q10": float(np.quantile(a, 0.10)), "q90": float(np.quantile(a, 0.90))}


def _nearest_active_vent_distance(sim: Simulation, org) -> float:
    cfg = sim.cfg
    state = sim.world.vent_state()
    active = [p for p, f in zip(state["vent_positions"], state["per_vent_flux_mol_s"]) if f > 0.0]
    if not active:
        return float("inf")
    c = cfg.cell_size
    best = float("inf")
    for vx, vy in active:
        cx, cy = (vx + 0.5) * c, (vy + 0.5) * c
        d2 = (org.x - cx) ** 2 + (org.y - cy) ** 2
        best = min(best, d2)
    return best ** 0.5


def sample(sim: Simulation, t_s: float) -> dict:
    orgs = sim.organisms
    vstate = sim.world.vent_state(sim.world._elapsed_s)
    row = {
        "time_s": t_s, "time_days": t_s / 86400.0,
        "population": len(orgs),
        "births_cum": sim.births_cum, "deaths_cum": sim.deaths_cum,
        "active_vent_count": vstate["active_vent_count"],
        "world_source_flux_mol_s": vstate["world_source_flux_mol_s"],
        "vent_turnover_count_cum": vstate["vent_turnover_count_cum"],
        "h2_source_influx_cum_mol": sim.h2_influx_cum,
        "h2_exchange_loss_cum_mol": sim.h2_loss_cum,
        "h2_biological_uptake_cum_mol": sim.h2_biological_uptake_mol_cum,
        "h2_total_mol": sim.world.total_h2(),
        "h2_mean_molm3": float(sim.world.h2.mean()),
        "h2_max_molm3": float(sim.world.h2.max()),
        "h2_habitability_fraction": float((sim.world.h2 >= H2_HABITABILITY_MOLM3).mean()),
    }
    if not orgs:
        row.update({
            "max_generation_alive": None, "mean_runway_s": None,
            "starvation_active_fraction": None, "mean_local_h2_molm3": None,
            "h2_habitable_occupancy_fraction": None,
            "mean_distance_to_nearest_active_vent_m": None,
            "total_biomass_kgdw": 0.0,
        })
        return row
    runways = [physiology.runway(o, sim.cfg) for o in orgs]
    local_h2 = [sim.world.sample(sim.world.h2, o.x, o.y) for o in orgs]
    dists = [_nearest_active_vent_distance(sim, o) for o in orgs]
    row.update({
        "max_generation_alive": max(o.generation for o in orgs),
        "mean_runway_s": float(np.mean(runways)),
        "starvation_active_fraction": float(np.mean([o.starve_state < 0.99 for o in orgs])),
        "mean_local_h2_molm3": float(np.mean(local_h2)),
        "h2_habitable_occupancy_fraction": float(
            np.mean([c >= H2_HABITABILITY_MOLM3 for c in local_h2])),
        "mean_distance_to_nearest_active_vent_m": float(np.mean(dists)),
        "total_biomass_kgdw": sum(o.matter for o in orgs) * sim.cfg.matter_unit_to_kgdw,
    })
    # Exp19 §9.2: 3 Energy戦略geneのtime-series (mean/median)。既存Exp18
    # readoutには影響しない追加列 (docs/Exp19_...実験計画.md §13)。
    row.update({
        "storage_capacity_mean": float(np.mean([o.genome[STORAGE_CAP] for o in orgs])),
        "storage_capacity_median": float(np.median([o.genome[STORAGE_CAP] for o in orgs])),
        "starvation_horizon_mean": float(np.mean([o.genome[STARV_HORIZON] for o in orgs])),
        "starvation_horizon_median": float(np.median([o.genome[STARV_HORIZON] for o in orgs])),
        "reproduction_horizon_mean": float(np.mean([o.genome[REPRO_HORIZON] for o in orgs])),
        "reproduction_horizon_median": float(np.median([o.genome[REPRO_HORIZON] for o in orgs])),
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


def run(cfg: Config, seed: int, outdir: Path, days: float,
       initial_h2_field: np.ndarray | None, write_snapshots: bool = True) -> dict:
    """1 formal run分。成果物をoutdirへ保存する (docs Exp18 §10)。"""
    outdir.mkdir(parents=True, exist_ok=True)
    sim = setup_sim(cfg, seed, initial_h2_field)
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

    (outdir / "vent_schedule.json").write_text(json.dumps({
        "initial_positions": [list(p) for p in sim.world._initial_vent_positions]
                              if hasattr(sim.world, "_initial_vent_positions") else [],
        "turnover_events": sim.world._turnover_events[:sim.world._turnover_applied_idx + 5],
    }, indent=2), encoding="utf-8")

    alive = sim.organisms
    c1, n1, p1 = sim.system_carbon(), sim.system_nitrogen(), sim.system_phosphorus()
    c_residual = c1 - (c0 + sim.c_in_external_cum - sim.c_out_external_cum)
    n_residual = n1 - (n0 + sim.n_in_external_cum - sim.n_out_external_cum)
    p_residual = p1 - (p0 + sim.p_in_external_cum - sim.p_out_external_cum)
    energy_residual = sim.system_energy() - (
        sim.initial_system_energy + sim.energy_in_cum - sim.energy_out_cum)
    h2_ratio = (sim.h2_biological_uptake_mol_cum / sim.h2_influx_cum
                if sim.h2_influx_cum > 0 else None)

    cnp_ledger = {
        "carbon": {"system_initial_mol": c0, "system_final_mol": c1,
                  "residual_mol": c_residual,
                  "residual_relative": c_residual / c1 if c1 > 0 else None},
        "nitrogen": {"system_initial_mol": n0, "system_final_mol": n1,
                    "residual_mol": n_residual,
                    "residual_relative": n_residual / n1 if n1 > 0 else None},
        "phosphorus": {"system_initial_mol": p0, "system_final_mol": p1,
                      "residual_mol": p_residual,
                      "residual_relative": p_residual / p1 if p1 > 0 else None},
    }
    (outdir / "cnp_ledger.json").write_text(json.dumps(cnp_ledger, indent=2), encoding="utf-8")

    summary = {
        "experiment": "Exp18 V1.10.1 dynamic hydrothermal vent",
        "seed": seed,
        "h2_vent_temporal_enabled": cfg.h2_vent_temporal_enabled,
        "h2_vent_turnover_enabled": cfg.h2_vent_turnover_enabled,
        "evolve_genes": [g for g in GENE_NAMES if g not in cfg.fixed_genes],
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
        "final_mean_runway_s": timeseries[-1].get("mean_runway_s"),
        "final_starvation_active_fraction": timeseries[-1].get("starvation_active_fraction"),
        "final_gene_stats": {
            "storage_capacity": qstats([float(o.genome[STORAGE_CAP]) for o in alive]),
            "starvation_horizon": qstats([float(o.genome[STARV_HORIZON]) for o in alive]),
            "reproduction_horizon": qstats(
                [float(o.genome[__import__("evosim.genome", fromlist=["REPRO_HORIZON"]).REPRO_HORIZON])
                for o in alive]),
        },
        "h2_biological_uptake_mol": sim.h2_biological_uptake_mol_cum,
        "h2_source_influx_mol": sim.h2_influx_cum,
        "h2_biological_uptake_over_source_influx": h2_ratio,
        "energy_ledger_residual_j": energy_residual,
        "cnp_ledger": cnp_ledger,
        "vent_turnover_count_cum": sim.world.vent_turnover_count_cum,
        "explicit_cnp_resources": True,
        "no_parameter_tuning": True,
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
