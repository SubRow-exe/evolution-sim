"""Exp21 — starvation_horizon直接競争実験 (docs/Exp21_実験計画.md)。

同一世界内でstarvation_horizon=1800s (baseline) と2700s (long-horizon,
baselineの1.5倍) の2系統を50:50で競争させ、A0_STATIC/A2_DYNAMIC_VENTで
long-horizon lineageの頻度が実際に増加するかを直接測定する。

Exp20 Attempt 2のharness (exp18_core.setup_sim / A0-A2 environment
machinery / phototrophy無効化) を最大限再利用する。Exp21固有なのは
「同一population内の2 lineage競争」であり、Exp20のような別run間の
paired比較ではない。
"""
from __future__ import annotations

import argparse
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
from evosim.genome import GENE_NAMES, INITIAL_GENOME, STARV_HORIZON  # noqa: E402

DT_SECONDS = 10.0
DURATION_H = 120.0  # docs §6: 48h + 96hの2回のvent relocationを経験する
SAMPLE_EVERY_S = 600.0  # 12/24/48/72/96/120hの全ての評価時点を割り切る
ENVIRONMENTS = ("A0_STATIC", "A2_DYNAMIC_VENT")
_ENV_TO_CONDITION = {"A0_STATIC": "A0", "A2_DYNAMIC_VENT": "A2"}

# docs §7: 事前固定するseed set (Exp18=18xxx/Exp19=19xxx/Exp20=20xxx番台に
# 続くExp21固有の番号帯。結果を見て差し替えない)。
SEEDS = (21001, 21002, 21003, 21004, 21005, 21006, 21007, 21008)

BASELINE_HORIZON_S = float(INITIAL_GENOME[STARV_HORIZON])  # 1800.0
LONG_HORIZON_S = BASELINE_HORIZON_S * 1.5  # 2700.0
LINEAGE_GROUPS = ("baseline", "long")


def load_calibration(calibration_dir: Path) -> tuple[float, np.ndarray]:
    f0_data = json.loads((calibration_dir / "f0_calibration.json").read_text(encoding="utf-8"))
    h2_field = np.load(calibration_dir / "common_initial_h2_field.npy")
    return float(f0_data["f0_mol_s"]), h2_field


def env_kwargs(environment: str) -> dict:
    condition = _ENV_TO_CONDITION[environment]
    kw = dict(run_exp18.CONDITIONS[condition])
    if kw["turnover"]:
        kw = {**kw, **run_exp18.TURNOVER_KW}
    return kw


def make_cfg(f0: float, environment: str):
    """docs §5/§11 G1-G4: physical mode, phototrophy/predation/mutation/
    structural innovation全OFF、A0/A2はExp18/Exp20と同一H2 environment。
    """
    return exp18_core.make_flux_cfg(
        f0, evolve_genes=(), initial_jitter_sigma=0.0,
        physical_light_enabled=False,
        light_cycle_enabled=False,
        phototrophy_innovation_prob=0.0,
        phototrophy_loss_prob=0.0,
        dt_seconds=DT_SECONDS,
        **env_kwargs(environment),
    )


def validate_effective_config(cfg, environment: str) -> None:
    """docs §11 G1-G5 (lineage関連のG6-G9はassign_lineages側で検証)。"""
    cond = _ENV_TO_CONDITION[environment]
    expected = run_exp18.CONDITIONS[cond]
    assert cfg.physical_mode is True, "G1: physical_mode must be True"
    assert cfg.physical_light_enabled is False, "G2: phototrophy light must be OFF"
    assert cfg.phototrophy_innovation_prob == 0.0, "G4: structural innovation must be OFF"
    assert cfg.phototrophy_loss_prob == 0.0, "G4: structural innovation must be OFF"
    assert set(cfg.fixed_genes) == set(GENE_NAMES), "G4: continuous mutation must be OFF"
    assert cfg.initial_population == 100, "G6: initial population must be 100"
    assert cfg.h2_source_mode == "flux"
    assert cfg.h2_vent_temporal_enabled is bool(expected["temporal"])
    assert cfg.h2_vent_turnover_enabled is bool(expected["turnover"])
    assert cfg.initial_jitter_sigma == 0.0


def long_lineage_ids(seed: int, organism_ids: list[int], count: int) -> set[int]:
    """docs §4: lineage割当専用の安定hash (organism/environment RNGとは
    完全に分離、Exp20 founder選択と同じ手法)。同一seedなら同じ割当を
    再現し、count個のidを厳密に返す (50:50を保証)。
    """
    def key(oid: int) -> bytes:
        payload = f"{seed}:{oid}:exp21-long-horizon".encode("utf-8")
        return hashlib.blake2b(payload, digest_size=16).digest()
    ranked = sorted(organism_ids, key=key)
    return set(ranked[:count])


def assign_lineages(sim, seed: int) -> set[int]:
    """docs §4: 初期100個体の共通配置は変えず、50個体をlong-horizonへ
    (starvation_horizon以外のgeneは完全一致のまま)。lineage_idは
    founder個体のidのまま (Organism._spawn_initialでid==lineage_id) なので、
    子孫もparentのlineage_idを継承しlineage追跡に使える。
    """
    ids = sorted(o.id for o in sim.organisms)
    n_long = len(ids) // 2
    long_ids = long_lineage_ids(seed, ids, n_long)
    for o in sim.organisms:
        if o.id in long_ids:
            o.genome = o.genome.copy()
            o.genome[STARV_HORIZON] = LONG_HORIZON_S
    return long_ids


def lineage_of(lineage_id: int, long_ids: set[int]) -> str:
    return "long" if lineage_id in long_ids else "baseline"


def snapshot(sim, t_s: float, long_ids: set[int],
            births_cum: dict, deaths_cum: dict) -> dict:
    orgs = sim.organisms
    groups = {"long": [o for o in orgs if o.lineage_id in long_ids],
             "baseline": [o for o in orgs if o.lineage_id not in long_ids]}
    row: dict = {"time_s": t_s, "time_h": t_s / 3600.0}
    n_long, n_base = len(groups["long"]), len(groups["baseline"])
    total = n_long + n_base
    row["f_long"] = (n_long / total) if total > 0 else None
    for g in LINEAGE_GROUPS:
        members = groups[g]
        n = len(members)
        row[f"{g}_population"] = n
        row[f"{g}_births_cum"] = births_cum[g]
        row[f"{g}_deaths_cum"] = deaths_cum[g]
        row[f"{g}_total_matter"] = float(sum(o.matter for o in members)) if n else 0.0
        row[f"{g}_mean_matter"] = float(np.mean([o.matter for o in members])) if n else None
        row[f"{g}_mean_energy_j"] = float(np.mean([o.energy for o in members])) if n else None
        row[f"{g}_mean_starve_state"] = float(np.mean([o.starve_state for o in members])) if n else None
    return row


def run_one(cfg, seed: int, h2_field: np.ndarray, hours: float) -> tuple[list[dict], dict]:
    sim = exp18_core.setup_sim(cfg, seed, h2_field)
    rng_state_before = sim.rng.bit_generator.state
    long_ids = assign_lineages(sim, seed)
    # G9: lineage割当がsimulation RNGを一切消費していないことを直接確認する。
    rng_state_after = sim.rng.bit_generator.state
    if rng_state_before != rng_state_after:
        raise RuntimeError("lineage assignment consumed simulation RNG (G9 violated)")

    births_cum = {"long": 0, "baseline": 0}
    deaths_cum = {"long": 0, "baseline": 0}
    known = {o.id: o.lineage_id for o in sim.organisms}
    rows = [snapshot(sim, 0.0, long_ids, births_cum, deaths_cum)]
    steps = int(round(hours * 3600.0 / cfg.dt_seconds))
    every = max(1, int(round(SAMPLE_EVERY_S / cfg.dt_seconds)))
    extinction_time_h = {"long": None, "baseline": None}
    fixed_lineage = None
    fixation_time_h = None

    for step in range(1, steps + 1):
        sim.step()
        t_s = step * cfg.dt_seconds
        current = {o.id: o.lineage_id for o in sim.organisms}
        for oid, lid in current.items():
            if oid not in known:
                births_cum[lineage_of(lid, long_ids)] += 1
        for oid, lid in known.items():
            if oid not in current:
                deaths_cum[lineage_of(lid, long_ids)] += 1
        known = current

        n_long = sum(1 for lid in current.values() if lid in long_ids)
        n_base = len(current) - n_long
        if n_long == 0 and extinction_time_h["long"] is None:
            extinction_time_h["long"] = t_s / 3600.0
        if n_base == 0 and extinction_time_h["baseline"] is None:
            extinction_time_h["baseline"] = t_s / 3600.0
        if fixed_lineage is None:
            if n_long > 0 and n_base == 0:
                fixed_lineage, fixation_time_h = "long", t_s / 3600.0
            elif n_base > 0 and n_long == 0:
                fixed_lineage, fixation_time_h = "baseline", t_s / 3600.0

        if step % every == 0:
            rows.append(snapshot(sim, t_s, long_ids, births_cum, deaths_cum))
        if not sim.organisms:
            if rows[-1]["time_s"] != t_s:
                rows.append(snapshot(sim, t_s, long_ids, births_cum, deaths_cum))
            break

    summary = {
        "final": rows[-1],
        "extinction_time_h": extinction_time_h,
        "fixed_lineage": fixed_lineage,
        "fixation_time_h": fixation_time_h,
        "duration_completed_h": rows[-1]["time_h"],
    }
    return rows, summary


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def genomes_identical_except_starv_horizon(sim, long_ids: set[int]) -> bool:
    """docs §11 G7: 2系統はstarvation_horizon以外のgeneが完全一致。"""
    ref = None
    for o in sim.organisms:
        g = np.asarray(o.genome, dtype=np.float64).copy()
        g[STARV_HORIZON] = 0.0  # mask
        if ref is None:
            ref = g
        elif not np.array_equal(g, ref):
            return False
    return True


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--environment", choices=ENVIRONMENTS, required=True)
    p.add_argument("--seed", type=int, choices=SEEDS, required=True)
    p.add_argument("--hours", type=float, default=DURATION_H)
    p.add_argument("--calibration-dir", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    args = p.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    f0, h2_field = load_calibration(args.calibration_dir)

    cfg = make_cfg(f0, args.environment)
    validate_effective_config(cfg, args.environment)
    (args.outdir / "effective_config.json").write_text(
        json.dumps(dataclasses.asdict(cfg), indent=2), encoding="utf-8")

    sim_check = exp18_core.setup_sim(cfg, args.seed, h2_field)
    long_ids_check = assign_lineages(sim_check, args.seed)
    n_long = len(long_ids_check)
    n_total = len(sim_check.organisms)
    gate_5050 = (n_total == 100 and n_long == 50)
    gate_genome_match = genomes_identical_except_starv_horizon(sim_check, long_ids_check)
    if not gate_5050:
        raise RuntimeError(f"G6 violated: n_total={n_total}, n_long={n_long} (expected 100/50)")
    if not gate_genome_match:
        raise RuntimeError("G7 violated: genomes differ beyond starvation_horizon")

    rows, summary = run_one(cfg, args.seed, h2_field, args.hours)
    write_csv(args.outdir / "lineage_timeseries.csv", rows)

    out = {
        "experiment": "Exp21 starvation_horizon direct competition",
        "environment": args.environment,
        "seed": args.seed,
        "duration_h": args.hours,
        "duration_target_h": DURATION_H,
        "f0_mol_s_per_vent": f0,
        "baseline_horizon_s": BASELINE_HORIZON_S,
        "long_horizon_s": LONG_HORIZON_S,
        "n_initial_total": n_total,
        "n_initial_long": n_long,
        "n_initial_baseline": n_total - n_long,
        "gates": {
            "initial_5050_split": gate_5050,
            "genome_identical_except_starvation_horizon": gate_genome_match,
        },
        "summary": summary,
    }
    (args.outdir / "summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "summary"} | {
        "final_f_long": summary["final"]["f_long"],
        "fixed_lineage": summary["fixed_lineage"],
        "fixation_time_h": summary["fixation_time_h"],
    }, indent=2))


if __name__ == "__main__":
    main()
