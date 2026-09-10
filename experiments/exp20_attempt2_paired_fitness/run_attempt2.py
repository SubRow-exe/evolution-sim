"""Exp20 Attempt 2 — paired fitness-effect assay for V1.9 physiological traits.

Current canonical roadmap:
  docs/V1.11_選択圧直接測定_実験ロードマップ.md

This replaces the superseded stochastic 24-run phototrophy invasion Attempt 2.
It does NOT wait for evolution. For the same seed/environment/initial state it runs
one baseline plus fixed trait variants and measures continuous fitness-related
trajectories directly.

Formal Stage-1 design:
  traits: storage_capacity / starvation_horizon / reproduction_horizon
  factors: 0.5 / 0.8 / 1.2 / 1.5 x baseline
  environments: A0_STATIC / A2_DYNAMIC_VENT
  seeds: 20001 / 20002 / 20003
  duration: 48 physical hours

Phototrophy is explicitly disabled in this assay. This keeps the assay independent
of the Exp20 Attempt-1 legacy-light defect while that production path is repaired.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import math
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
from evosim.genome import (  # noqa: E402
    GENE_MAX,
    GENE_MIN,
    GENE_NAMES,
    INITIAL_GENOME,
    REPRO_HORIZON,
    STARV_HORIZON,
    STORAGE_CAP,
)

DT_SECONDS = 10.0
DURATION_H = 48.0
SAMPLE_EVERY_S = 600.0
SEEDS = (20001, 20002, 20003)
ENVIRONMENTS = ("A0_STATIC", "A2_DYNAMIC_VENT")
TRAITS = {
    "storage_capacity": STORAGE_CAP,
    "starvation_horizon": STARV_HORIZON,
    "reproduction_horizon": REPRO_HORIZON,
}
FACTORS = (0.5, 0.8, 1.2, 1.5)
_ENV_TO_CONDITION = {"A0_STATIC": "A0", "A2_DYNAMIC_VENT": "A2"}


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


def variant_value(trait: str, factor: float) -> float:
    idx = TRAITS[trait]
    value = float(INITIAL_GENOME[idx]) * factor
    if not float(GENE_MIN[idx]) <= value <= float(GENE_MAX[idx]):
        raise ValueError(f"variant out of bounds: {trait}={value}")
    return value


def make_cfg(f0: float, environment: str, trait: str | None = None,
             factor: float | None = None):
    overrides: dict[str, object] = {
        # isolate the three pre-existing physiological traits from phototrophy
        "physical_light_enabled": False,
        "light_cycle_enabled": False,
        "phototrophy_innovation_prob": 0.0,
        "phototrophy_loss_prob": 0.0,
        "dt_seconds": DT_SECONDS,
    }
    if trait is not None:
        if factor is None:
            raise ValueError("factor required for variant")
        overrides["diagnostic_gene_overrides"] = {trait: variant_value(trait, factor)}
    else:
        overrides["diagnostic_gene_overrides"] = {}

    cfg = exp18_core.make_flux_cfg(
        f0,
        evolve_genes=(),
        initial_jitter_sigma=0.0,
        **env_kwargs(environment),
        **overrides,
    )
    validate_effective_config(cfg, environment, trait, factor)
    return cfg


def validate_effective_config(cfg, environment: str, trait: str | None,
                              factor: float | None) -> None:
    """G7: assert the effective config against the preregistered condition table."""
    cond = _ENV_TO_CONDITION[environment]
    expected = run_exp18.CONDITIONS[cond]
    assert cfg.physical_mode is True
    assert cfg.dt_seconds == DT_SECONDS
    assert cfg.initial_population == 100
    assert cfg.h2_source_mode == "flux"
    assert cfg.h2_vent_temporal_enabled is bool(expected["temporal"])
    assert cfg.h2_vent_turnover_enabled is bool(expected["turnover"])
    assert cfg.initial_jitter_sigma == 0.0
    assert set(cfg.fixed_genes) == set(GENE_NAMES)
    assert cfg.physical_light_enabled is False
    assert cfg.light_cycle_enabled is False
    assert cfg.phototrophy_innovation_prob == 0.0
    assert cfg.phototrophy_loss_prob == 0.0
    if trait is None:
        assert cfg.diagnostic_gene_overrides == {}
    else:
        assert cfg.diagnostic_gene_overrides == {trait: variant_value(trait, float(factor))}
    if expected["turnover"]:
        assert cfg.h2_vent_turnover_interval_s == run_exp18.TURNOVER_KW["h2_vent_turnover_interval_s"]
        assert cfg.h2_vent_min_separation_cells == run_exp18.TURNOVER_KW["h2_vent_min_separation_cells"]


def initial_fingerprint(sim, ignore_trait: str | None = None) -> str:
    """Hash the initial state, ignoring only the intentionally changed gene."""
    ignore_idx = TRAITS.get(ignore_trait) if ignore_trait is not None else None
    h = hashlib.sha256()
    h.update(np.asarray(sim.world.h2, dtype=np.float64).tobytes())
    for o in sorted(sim.organisms, key=lambda x: x.id):
        h.update(np.asarray([o.id, o.x, o.y, o.matter, o.energy, o.damage], dtype=np.float64).tobytes())
        g = np.asarray(o.genome, dtype=np.float64).copy()
        if ignore_idx is not None:
            g[ignore_idx] = float(INITIAL_GENOME[ignore_idx])
        h.update(g.tobytes())
        h.update(str(bool(o.phototrophy_on)).encode())
    return h.hexdigest()


def snapshot(sim, t_s: float) -> dict:
    orgs = sim.organisms
    n = len(orgs)
    if n:
        mean_matter = float(np.mean([o.matter for o in orgs]))
        mean_energy = float(np.mean([o.energy for o in orgs]))
        mean_starve_state = float(np.mean([o.starve_state for o in orgs]))
        starvation_exposed_frac = float(np.mean([o.starve_state < 0.99 for o in orgs]))
        total_matter = float(sum(o.matter for o in orgs))
        max_generation = int(max(o.generation for o in orgs))
    else:
        mean_matter = None
        mean_energy = None
        mean_starve_state = None
        starvation_exposed_frac = None
        total_matter = 0.0
        max_generation = None
    return {
        "time_s": float(t_s),
        "time_h": float(t_s / 3600.0),
        "population": n,
        "mean_matter": mean_matter,
        "total_living_matter": total_matter,
        "mean_stored_energy_j": mean_energy,
        "mean_starve_state": mean_starve_state,
        "starvation_exposed_fraction": starvation_exposed_frac,
        "births_cum": int(sim.births_cum),
        "deaths_cum": int(sim.deaths_cum),
        "starvation_deaths_cum": int(sim.deaths_by_cause.get("starvation", 0)),
        "max_generation_alive": max_generation,
        "h2_biological_uptake_cum_mol": float(sim.h2_biological_uptake_mol_cum),
        "energy_in_cum_j": float(sim.energy_in_cum),
        "energy_out_cum_j": float(sim.energy_out_cum),
        "photo_used_j_cum": float(sim.photo_used_j_cum),
        "legacy_light_flow_cum": float(sim.flows.get("light", 0.0)),
        "vent_turnover_count_cum": int(sim.world.vent_turnover_count_cum),
    }


def run_one(cfg, seed: int, h2_field: np.ndarray, hours: float) -> tuple[list[dict], dict, str]:
    sim = exp18_core.setup_sim(cfg, seed, h2_field)
    fp = initial_fingerprint(sim)
    steps = int(round(hours * 3600.0 / cfg.dt_seconds))
    every = max(1, int(round(SAMPLE_EVERY_S / cfg.dt_seconds)))
    rows = [snapshot(sim, 0.0)]
    first_birth_time_h = None
    extinction_time_h = None
    initial_matter = rows[0]["total_living_matter"]
    initial_n = rows[0]["population"]

    for step in range(1, steps + 1):
        before_births = sim.births_cum
        sim.step()
        t_s = step * cfg.dt_seconds
        if first_birth_time_h is None and sim.births_cum > before_births:
            first_birth_time_h = t_s / 3600.0
        if step % every == 0:
            rows.append(snapshot(sim, t_s))
        if not sim.organisms:
            extinction_time_h = t_s / 3600.0
            if rows[-1]["time_s"] != t_s:
                rows.append(snapshot(sim, t_s))
            break
        if len(sim.organisms) >= cfg.max_population_halt:
            if rows[-1]["time_s"] != t_s:
                rows.append(snapshot(sim, t_s))
            break

    final = rows[-1]
    # This assay has phototrophy OFF. Any light-derived energy is contamination.
    if abs(final["photo_used_j_cum"]) > 1e-18 or abs(final["legacy_light_flow_cum"]) > 1e-18:
        raise RuntimeError(
            "paired assay contaminated by light/phototrophy energy: "
            f"photo_used={final['photo_used_j_cum']} legacy_light={final['legacy_light_flow_cum']}"
        )
    summary = {
        "initial_population": initial_n,
        "initial_total_living_matter": initial_matter,
        "final": final,
        "first_birth_time_h": first_birth_time_h,
        "extinction_time_h": extinction_time_h,
        "duration_completed_h": final["time_h"],
    }
    return rows, summary, fp


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def numeric_delta(v, b):
    if v is None or b is None:
        return None
    return float(v) - float(b)


def paired_rows(base_rows: list[dict], var_rows: list[dict]) -> list[dict]:
    base_by_t = {round(float(r["time_s"]), 6): r for r in base_rows}
    var_by_t = {round(float(r["time_s"]), 6): r for r in var_rows}
    keys = sorted(set(base_by_t) & set(var_by_t))
    fields = (
        "population",
        "mean_matter",
        "total_living_matter",
        "mean_stored_energy_j",
        "mean_starve_state",
        "starvation_exposed_fraction",
        "births_cum",
        "deaths_cum",
        "starvation_deaths_cum",
        "h2_biological_uptake_cum_mol",
        "energy_in_cum_j",
        "energy_out_cum_j",
    )
    out = []
    for t in keys:
        b, v = base_by_t[t], var_by_t[t]
        row = {"time_s": t, "time_h": t / 3600.0}
        for f in fields:
            row[f"baseline_{f}"] = b[f]
            row[f"variant_{f}"] = v[f]
            row[f"delta_{f}"] = numeric_delta(v[f], b[f])
        out.append(row)
    return out


def auc(rows: list[dict], field: str) -> float | None:
    pts = [(float(r["time_h"]), r[field]) for r in rows if r.get(field) is not None]
    if len(pts) < 2:
        return None
    x = np.asarray([p[0] for p in pts], dtype=float)
    y = np.asarray([p[1] for p in pts], dtype=float)
    return float(np.trapezoid(y, x))


def pair_summary(trait: str, factor: float, environment: str, seed: int,
                 base_summary: dict, var_summary: dict, diffs: list[dict]) -> dict:
    bf = base_summary["final"]
    vf = var_summary["final"]
    return {
        "trait": trait,
        "factor": factor,
        "variant_value": variant_value(trait, factor),
        "environment": environment,
        "seed": seed,
        "duration_target_h": DURATION_H,
        "delta_final_mean_matter": numeric_delta(vf["mean_matter"], bf["mean_matter"]),
        "delta_final_total_living_matter": numeric_delta(vf["total_living_matter"], bf["total_living_matter"]),
        "delta_final_mean_stored_energy_j": numeric_delta(vf["mean_stored_energy_j"], bf["mean_stored_energy_j"]),
        "delta_final_population": numeric_delta(vf["population"], bf["population"]),
        "delta_births_cum": numeric_delta(vf["births_cum"], bf["births_cum"]),
        "delta_deaths_cum": numeric_delta(vf["deaths_cum"], bf["deaths_cum"]),
        "delta_starvation_deaths_cum": numeric_delta(vf["starvation_deaths_cum"], bf["starvation_deaths_cum"]),
        "delta_h2_biological_uptake_cum_mol": numeric_delta(vf["h2_biological_uptake_cum_mol"], bf["h2_biological_uptake_cum_mol"]),
        "delta_energy_out_cum_j": numeric_delta(vf["energy_out_cum_j"], bf["energy_out_cum_j"]),
        "delta_first_birth_time_h": numeric_delta(var_summary["first_birth_time_h"], base_summary["first_birth_time_h"]),
        "delta_extinction_time_h": numeric_delta(var_summary["extinction_time_h"], base_summary["extinction_time_h"]),
        "auc_delta_mean_matter_h": auc(diffs, "delta_mean_matter"),
        "auc_delta_mean_stored_energy_j_h": auc(diffs, "delta_mean_stored_energy_j"),
        "auc_delta_starvation_exposed_fraction_h": auc(diffs, "delta_starvation_exposed_fraction"),
        "baseline_final": bf,
        "variant_final": vf,
    }


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

    base_cfg = make_cfg(f0, args.environment)
    (args.outdir / "effective_config_baseline.json").write_text(
        json.dumps(dataclasses.asdict(base_cfg), indent=2), encoding="utf-8")
    base_rows, base_summary, base_fp = run_one(base_cfg, args.seed, h2_field, args.hours)
    write_csv(args.outdir / "baseline.csv", base_rows)

    pair_summaries = []
    init_checks = []
    for trait in TRAITS:
        for factor in FACTORS:
            cfg = make_cfg(f0, args.environment, trait, factor)
            label = f"{trait}_x{factor:.1f}"
            (args.outdir / f"effective_config_{label}.json").write_text(
                json.dumps(dataclasses.asdict(cfg), indent=2), encoding="utf-8")
            var_rows, var_summary, _raw_fp = run_one(cfg, args.seed, h2_field, args.hours)

            # Recreate baseline/variant initial sims and compare fingerprints while
            # masking the intentionally changed trait. This is a direct G7/state gate.
            bcheck = exp18_core.setup_sim(base_cfg, args.seed, h2_field)
            vcheck = exp18_core.setup_sim(cfg, args.seed, h2_field)
            bfp_masked = initial_fingerprint(bcheck, ignore_trait=trait)
            vfp_masked = initial_fingerprint(vcheck, ignore_trait=trait)
            same = bfp_masked == vfp_masked
            init_checks.append({"trait": trait, "factor": factor, "initial_state_match_except_trait": same})
            if not same:
                raise RuntimeError(f"initial-state mismatch beyond intended trait: {label}")

            write_csv(args.outdir / f"variant_{label}.csv", var_rows)
            diffs = paired_rows(base_rows, var_rows)
            write_csv(args.outdir / f"paired_diff_{label}.csv", diffs)
            pair_summaries.append(
                pair_summary(trait, factor, args.environment, args.seed,
                             base_summary, var_summary, diffs)
            )

    out = {
        "experiment": "Exp20 Attempt 2 paired fitness-effect assay",
        "method": "common-random-number paired baseline vs fixed trait variant",
        "environment": args.environment,
        "seed": args.seed,
        "duration_h": args.hours,
        "f0_mol_s_per_vent": f0,
        "traits": list(TRAITS),
        "factors": list(FACTORS),
        "baseline_initial_fingerprint": base_fp,
        "initial_state_checks": init_checks,
        "baseline_summary": base_summary,
        "pairs": pair_summaries,
        "gates": {
            "effective_config_match": True,
            "initial_state_match_except_trait": all(x["initial_state_match_except_trait"] for x in init_checks),
            "phototrophy_disabled": True,
            "light_energy_contamination_zero": True,
        },
    }
    (args.outdir / "paired_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"environment": args.environment, "seed": args.seed,
                      "n_pairs": len(pair_summaries), "gates": out["gates"]}, indent=2))


if __name__ == "__main__":
    main()
