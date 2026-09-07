"""Aggregate Exp16 fixed-iLUCA environment robustness summaries."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def _finite(values):
    return [float(v) for v in values if v is not None and math.isfinite(float(v))]


def qstats(values):
    a = np.asarray(_finite(values), dtype=float)
    if a.size == 0:
        return {"mean": None, "median": None, "q10": None, "q90": None, "min": None, "max": None}
    return {
        "mean": float(a.mean()),
        "median": float(np.median(a)),
        "q10": float(np.quantile(a, 0.10)),
        "q90": float(np.quantile(a, 0.90)),
        "min": float(a.min()),
        "max": float(a.max()),
    }


def load_summaries(root: Path):
    rows = []
    for p in sorted(root.rglob("summary.json")):
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if s.get("experiment") != "Exp16 V1.9 fixed-iLUCA environment robustness":
            continue
        s["_path"] = str(p)
        rows.append(s)
    return rows


def aggregate(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r["condition"]].append(r)

    out = {}
    for condition, rr in sorted(groups.items()):
        stop = Counter(str(r.get("stop_reason")) for r in rr)
        gen_medians = [
            r.get("generation_interval_h", {}).get("median")
            for r in rr
        ]
        uptake_ratio = [r.get("h2_biological_uptake_over_source_influx") for r in rr]
        env = rr[0].get("environment_condition", {}) if rr else {}
        out[condition] = {
            "n_runs": len(rr),
            "seeds": sorted(int(r["seed"]) for r in rr),
            "environment_condition": env,
            "stop_reasons": dict(stop),
            "survival_fraction": float(np.mean([r.get("population_final", 0) > 0 for r in rr])) if rr else None,
            "extinction_fraction": float(np.mean([r.get("stop_reason") == "extinction" for r in rr])) if rr else None,
            "max_population_halt_fraction": float(np.mean([r.get("stop_reason") == "max_population_halt" for r in rr])) if rr else None,
            "population_final": qstats([r.get("population_final") for r in rr]),
            "population_max": qstats([r.get("population_max") for r in rr]),
            "population_auc_cell_days": qstats([r.get("population_auc_cell_days") for r in rr]),
            "max_generation": qstats([r.get("max_generation") for r in rr]),
            "generation_interval_median_h": qstats(gen_medians),
            "final_mean_runway_s": qstats([r.get("final_mean_runway_s") for r in rr]),
            "final_starvation_active_fraction": qstats([r.get("final_starvation_active_fraction") for r in rr]),
            "h2_biological_uptake_mol": qstats([r.get("h2_biological_uptake_mol") for r in rr]),
            "h2_source_influx_mol": qstats([r.get("h2_source_influx_mol") for r in rr]),
            "h2_biological_uptake_over_source_influx": qstats(uptake_ratio),
            "max_abs_energy_ledger_residual_j": max((abs(float(r.get("energy_ledger_residual_j", 0.0))) for r in rr), default=None),
            "max_abs_matter_ledger_residual": max((abs(float(r.get("matter_ledger_residual_matter", 0.0))) for r in rr), default=None),
        }
    return out


def write_csv(path: Path, by_condition):
    fields = [
        "condition", "n_runs", "h2_mM", "tau_s", "diffusion_m2s", "layout",
        "survival_fraction", "extinction_fraction", "max_population_halt_fraction",
        "population_final_median", "population_max_median", "max_generation_median",
        "generation_interval_median_h", "final_runway_median_s",
        "h2_uptake_source_ratio_median", "max_abs_energy_residual_j", "max_abs_matter_residual",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for condition, a in sorted(by_condition.items()):
            env = a.get("environment_condition", {})
            w.writerow({
                "condition": condition,
                "n_runs": a["n_runs"],
                "h2_mM": env.get("h2_source_concentration_mM"),
                "tau_s": env.get("h2_exchange_tau_s"),
                "diffusion_m2s": env.get("h2_diffusion_m2s"),
                "layout": env.get("source_layout"),
                "survival_fraction": a["survival_fraction"],
                "extinction_fraction": a["extinction_fraction"],
                "max_population_halt_fraction": a["max_population_halt_fraction"],
                "population_final_median": a["population_final"]["median"],
                "population_max_median": a["population_max"]["median"],
                "max_generation_median": a["max_generation"]["median"],
                "generation_interval_median_h": a["generation_interval_median_h"]["median"],
                "final_runway_median_s": a["final_mean_runway_s"]["median"],
                "h2_uptake_source_ratio_median": a["h2_biological_uptake_over_source_influx"]["median"],
                "max_abs_energy_residual_j": a["max_abs_energy_ledger_residual_j"],
                "max_abs_matter_residual": a["max_abs_matter_ledger_residual"],
            })


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("exp16_aggregate.json"))
    p.add_argument("--csv", type=Path, default=Path("exp16_aggregate.csv"))
    args = p.parse_args()

    rows = load_summaries(args.root)
    by_condition = aggregate(rows)
    result = {
        "experiment": "Exp16 V1.9 fixed-iLUCA environment robustness",
        "n_summaries": len(rows),
        "n_conditions_present": len(by_condition),
        "policy": {
            "fixed_iLUCA": True,
            "preregistered_conditions": True,
            "adaptive_tuning": False,
        },
        "by_condition": by_condition,
    }
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_csv(args.csv, by_condition)
    print(json.dumps({"n_summaries": len(rows), "conditions": sorted(by_condition)}, indent=2))


if __name__ == "__main__":
    main()
