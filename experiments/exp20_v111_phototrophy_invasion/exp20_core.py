"""Exp20 V1.11 primitive phototrophy seeded invasion — shared run core.

正本: docs/V1.11_原始Phototrophy_実装仕様_rev2.md (mechanism)、
docs/Exp20_V1.11_PrimitivePhototrophy_SeededInvasion_実験計画.md (experiment)。

V1.10.1/Exp18のA0/A1 H2環境machinery (exp18_core.py / run_exp18.py) を
再利用し、Exp20固有のt=0 phototroph seeding (§5) とlineage別readout (§9)
だけを追加する。
"""
from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXP18_DIR = ROOT / "experiments" / "exp18_v1101_dynamic_vent"
for p in (ROOT, EXP18_DIR):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import exp18_core  # noqa: E402
import run_exp18  # noqa: E402

from evosim import physiology  # noqa: E402
from evosim.config import Config  # noqa: E402
from evosim.genome import LIGHT_ABS, REPRO_HORIZON, STARV_HORIZON, STORAGE_CAP  # noqa: E402
from evosim.simulation import Simulation  # noqa: E402

DT = 10.0
STATS_EVERY_S = 3600.0  # 1 physical hour cadence (docs §9.2)
DURATION_DAYS = 5.0

# rev2 §3.3 / Exp20 §3.3: formal primitive phototroph phenotype
PHOTOTROPH_LIGHT_ABSORPTION = 0.01

# Exp20 §3.2: formal physical light baseline
LIGHT_OVERRIDES = dict(
    physical_light_enabled=True,
    light_photon_flux_umol_m2_s=0.015,
    light_effective_wavelength_nm=800.0,
    light_physical_pattern="uniform",
    phototrophy_radiant_to_usable_eff=0.10,
)

FREQUENCIES = (0.0, 0.01, 0.10, 0.50)
SEEDS = (20001, 20002, 20003)
ENVIRONMENTS = ("A0_STATIC", "A1_TEMPORAL")
_ENV_TO_CONDITION = {"A0_STATIC": "A0", "A1_TEMPORAL": "A1"}


def env_kwargs(environment: str) -> dict:
    condition = _ENV_TO_CONDITION[environment]
    kw = dict(run_exp18.CONDITIONS[condition])
    if kw["turnover"]:
        kw = {**kw, **run_exp18.TURNOVER_KW}
    return kw


def make_cfg(f0: float, environment: str) -> Config:
    """Exp18/V1.10.1のH2 environment (A0/A1) + Exp20 formal physical light
    baseline (docs Exp20 §3.1-3.2)。genetics/innovationはExp20 §4で全
    formal armに共通で固定する (continuous genes fixed, jitter=0,
    phototrophy innovation/loss prob=0)。
    """
    return exp18_core.make_flux_cfg(
        f0, evolve_genes=(), initial_jitter_sigma=0.0,
        phototrophy_innovation_prob=0.0, phototrophy_loss_prob=0.0,
        **env_kwargs(environment), **LIGHT_OVERRIDES)


def founder_rank_key(seed: int, organism_id: int) -> bytes:
    """stable hash (blake2b) でfounder rankingを決める (docs Exp20 §5.1)。

    Python built-in hash()はprocessごとに変動し得るため使わない。
    simulation RNGは一切消費しない。
    """
    payload = f"{seed}:{organism_id}:exp20-photo-founder".encode("utf-8")
    return hashlib.blake2b(payload, digest_size=16).digest()


def founder_ids(seed: int, organism_ids: list[int], count: int) -> set[int]:
    """count個のfounder idを返す。同一seedならcount間でnested subsetになる
    (1% ⊂ 10% ⊂ 50%、docs §5.1)。"""
    if count <= 0:
        return set()
    ranked = sorted(organism_ids, key=lambda oid: founder_rank_key(seed, oid))
    return set(ranked[:count])


def seed_photo_founders(sim: Simulation, cfg: Config, frequency: float) -> list[int]:
    """t=0でfrequency分のphototroph founderへ機能的apparatusを持たせる
    (docs Exp20 §5.2)。

    Nは無から生成せず、founderのいるvoxelのfixed_nitrogen fieldから厳密に
    減算する (internal transfer)。局所Nが不足していればRuntimeErrorで
    formal runをfailさせる (他cellからのsilent borrowingを禁止, §5.2)。
    戻り値: founder organism idのリスト。
    """
    n_founders = round(frequency * len(sim.organisms))
    if n_founders <= 0:
        return []
    ids = [o.id for o in sim.organisms]
    chosen = founder_ids(sim.seed, ids, n_founders)
    vv = sim.world.voxel_volume_m3
    for o in sim.organisms:
        if o.id not in chosen:
            continue
        o.phototrophy_on = True
        o.genome = o.genome.copy()
        o.genome[LIGHT_ABS] = PHOTOTROPH_LIGHT_ABSORPTION
        target = physiology.photo_n_target_mol(o, cfg)
        key = sim.world.cell_index(o.x, o.y)
        avail_mol = max(0.0, float(sim.world.fixed_nitrogen[key])) * vv
        if avail_mol < target:
            raise RuntimeError(
                f"Exp20 t=0 seeding: insufficient local fixed_nitrogen for founder "
                f"organism {o.id} (need {target:.6e} mol N, local voxel has "
                f"{avail_mol:.6e} mol N). Not borrowing from other cells "
                "(docs Exp20 §5.2). Preflight/formal run must fail here.")
        o.photo_structural_n_mol = target
        sim.world.fixed_nitrogen[key] = float(sim.world.fixed_nitrogen[key]) - target / vv
    return sorted(chosen)


def setup_sim(cfg: Config, seed: int, initial_h2_field: np.ndarray, frequency: float,
             vent_positions=exp18_core.LEGACY_FOUR_CENTERS) -> tuple[Simulation, list[int]]:
    sim = exp18_core.setup_sim(cfg, seed, initial_h2_field, vent_positions=vent_positions)
    founders = seed_photo_founders(sim, cfg, frequency)
    # t=0 seedingはinternal transferなのでenergy/H2/CNP external ledgerは
    # 変えないが、seeding後の状態を「formal t=0」として保存量を取り直す。
    sim.initial_system_energy = sim.system_energy()
    sim.initial_system_matter = sim.system_matter()
    return sim, founders


def _lineage_stats(orgs) -> dict:
    photo = [o for o in orgs if o.phototrophy_on]
    ancestor = [o for o in orgs if not o.phototrophy_on]

    def block(group):
        if not group:
            return {"n": 0, "mean_energy_j": None, "mean_runway_s": None,
                    "mean_matter": None, "photo_structural_n_mol_total": 0.0}
        return {
            "n": len(group),
            "mean_energy_j": float(np.mean([o.energy for o in group])),
            "mean_matter": float(np.mean([o.matter for o in group])),
            "photo_structural_n_mol_total": float(
                sum(o.photo_structural_n_mol for o in group)),
        }
    return {"photo": block(photo), "ancestor": block(ancestor)}


def sample(sim: Simulation, t_s: float) -> dict:
    orgs = sim.organisms
    lineage = _lineage_stats(orgs)
    row = {
        "time_s": t_s, "time_h": t_s / 3600.0,
        "population_total": len(orgs),
        "population_photo": lineage["photo"]["n"],
        "population_ancestor": lineage["ancestor"]["n"],
        "births_cum": sim.births_cum, "deaths_cum": sim.deaths_cum,
        "mean_energy_photo_j": lineage["photo"]["mean_energy_j"],
        "mean_energy_ancestor_j": lineage["ancestor"]["mean_energy_j"],
        "photo_structural_n_mol_total": lineage["photo"]["photo_structural_n_mol_total"],
        "photo_incident_j_cum": sim.photo_incident_j_cum,
        "photo_absorbed_j_cum": sim.photo_absorbed_j_cum,
        "photo_usable_max_j_cum": sim.photo_usable_max_j_cum,
        "photo_used_j_cum": sim.photo_used_j_cum,
        "photo_unused_j_cum": sim.photo_unused_j_cum,
        "photo_conversion_loss_j_cum": sim.photo_conversion_loss_j_cum,
        "h2_source_influx_cum_mol": sim.h2_influx_cum,
        "h2_biological_uptake_cum_mol": sim.h2_biological_uptake_mol_cum,
    }
    return row


def run(cfg: Config, seed: int, frequency: float, environment: str, outdir: Path,
       initial_h2_field: np.ndarray, days: float = DURATION_DAYS) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    sim, founders = setup_sim(cfg, seed, initial_h2_field, frequency)
    n0 = sim.system_nitrogen()
    c0 = sim.system_carbon()
    p0 = sim.system_phosphorus()

    (outdir / "effective_config.json").write_text(
        json.dumps(dataclasses.asdict(cfg), indent=2), encoding="utf-8")
    (outdir / "founders.json").write_text(json.dumps({
        "seed": seed, "frequency": frequency, "founder_ids": founders,
        "n_founders": len(founders), "n_initial": len(sim.organisms),
    }, indent=2), encoding="utf-8")

    total_steps = int(round(days * 86400.0 / DT))
    sample_every = max(1, int(round(STATS_EVERY_S / DT)))
    timeseries = [sample(sim, 0.0)]
    max_pop = len(sim.organisms)
    extinction_time_s = None
    stop_reason = "duration_complete"

    for step in range(1, total_steps + 1):
        sim.step()
        t_s = step * DT
        max_pop = max(max_pop, len(sim.organisms))
        if step % sample_every == 0:
            timeseries.append(sample(sim, t_s))
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

    with (outdir / "stats.csv").open("w", newline="", encoding="utf-8") as f:
        fields = list(timeseries[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(timeseries)

    n1 = sim.system_nitrogen()
    c1 = sim.system_carbon()
    p1 = sim.system_phosphorus()
    n_residual = n1 - (n0 + sim.n_in_external_cum - sim.n_out_external_cum)
    c_residual = c1 - (c0 + sim.c_in_external_cum - sim.c_out_external_cum)
    p_residual = p1 - (p0 + sim.p_in_external_cum - sim.p_out_external_cum)
    energy_residual = sim.system_energy() - (
        sim.initial_system_energy + sim.energy_in_cum - sim.energy_out_cum)

    def find_row(target_h: float) -> dict | None:
        for r in timeseries:
            if r["time_h"] >= target_h:
                return r
        return timeseries[-1] if timeseries else None

    summary = {
        "experiment": "Exp20 V1.11 primitive phototrophy seeded invasion",
        "seed": seed, "environment": environment, "initial_frequency": frequency,
        "n_founders": len(founders), "n_initial": cfg.initial_population,
        "days_requested": days,
        "days_completed": timeseries[-1]["time_s"] / 86400.0,
        "stop_reason": stop_reason,
        "extinction_time_h": None if extinction_time_s is None else extinction_time_s / 3600.0,
        "population_max": max_pop,
        "population_final_total": timeseries[-1]["population_total"],
        "population_final_photo": timeseries[-1]["population_photo"],
        "population_final_ancestor": timeseries[-1]["population_ancestor"],
        "row_0h": find_row(0.0),
        "row_48h": find_row(48.0),
        "row_120h": find_row(120.0),
        "births_cum": sim.births_cum, "deaths_cum": sim.deaths_cum,
        "deaths_by_cause": sim.deaths_by_cause,
        "photo_used_j_cum": sim.photo_used_j_cum,
        "photo_usable_max_j_cum": sim.photo_usable_max_j_cum,
        "photo_absorbed_j_cum": sim.photo_absorbed_j_cum,
        "photo_incident_j_cum": sim.photo_incident_j_cum,
        "h2_source_influx_cum_mol": sim.h2_influx_cum,
        "h2_biological_uptake_cum_mol": sim.h2_biological_uptake_mol_cum,
        "nitrogen_ledger": {"initial_mol": n0, "final_mol": n1,
                            "residual_mol": n_residual,
                            "residual_relative": n_residual / n1 if n1 > 0 else None},
        "carbon_ledger": {"initial_mol": c0, "final_mol": c1,
                         "residual_mol": c_residual,
                         "residual_relative": c_residual / c1 if c1 > 0 else None},
        "phosphorus_ledger": {"initial_mol": p0, "final_mol": p1,
                             "residual_mol": p_residual,
                             "residual_relative": p_residual / p1 if p1 > 0 else None},
        "energy_ledger_residual_j": energy_residual,
        "h2_usable_energy_j_per_mol": cfg.h2_usable_energy_j_per_mol,
        "no_parameter_tuning": True,
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
