"""Aggregate Exp20 Attempt 2 paired fitness-effect artifacts."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def q(values):
    a = np.asarray([float(v) for v in values if v is not None], dtype=float)
    if a.size == 0:
        return {"n": 0, "mean": None, "median": None, "min": None, "max": None,
                "positive": 0, "negative": 0, "zero": 0}
    return {
        "n": int(a.size),
        "mean": float(a.mean()),
        "median": float(np.median(a)),
        "min": float(a.min()),
        "max": float(a.max()),
        "positive": int((a > 0).sum()),
        "negative": int((a < 0).sum()),
        "zero": int((a == 0).sum()),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--csv", type=Path, required=True)
    args = p.parse_args()

    files = sorted(args.root.rglob("paired_summary.json"))
    if len(files) != 6:
        raise SystemExit(f"expected 6 environment×seed artifacts, got {len(files)}")

    all_pairs = []
    gate_failures = []
    seen = set()
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        key = (d["environment"], int(d["seed"]))
        if key in seen:
            raise SystemExit(f"duplicate artifact key: {key}")
        seen.add(key)
        if not all(bool(v) for v in d["gates"].values()):
            gate_failures.append({"file": str(f), "gates": d["gates"]})
        all_pairs.extend(d["pairs"])

    expected = {(e, s) for e in ("A0_STATIC", "A2_DYNAMIC_VENT")
                for s in (20001, 20002, 20003)}
    if seen != expected:
        raise SystemExit(f"missing/unexpected environment×seed cells: seen={sorted(seen)}")
    if len(all_pairs) != 72:
        raise SystemExit(f"expected 72 paired contrasts, got {len(all_pairs)}")
    if gate_failures:
        raise SystemExit(f"preflight/runtime gate failure(s): {gate_failures}")

    metric_names = [
        "delta_final_mean_matter",
        "delta_final_total_living_matter",
        "delta_final_mean_stored_energy_j",
        "delta_final_population",
        "delta_births_cum",
        "delta_deaths_cum",
        "delta_starvation_deaths_cum",
        "delta_h2_biological_uptake_cum_mol",
        "delta_energy_out_cum_j",
        "delta_first_birth_time_h",
        "delta_extinction_time_h",
        "auc_delta_mean_matter_h",
        "auc_delta_mean_stored_energy_j_h",
        "auc_delta_starvation_exposed_fraction_h",
    ]

    grouped = defaultdict(list)
    for r in all_pairs:
        grouped[(r["trait"], float(r["factor"]), r["environment"])].append(r)

    cells = []
    for (trait, factor, env), rows in sorted(grouped.items()):
        cell = {"trait": trait, "factor": factor, "environment": env,
                "seeds": sorted(int(r["seed"]) for r in rows)}
        for m in metric_names:
            cell[m] = q([r.get(m) for r in rows])
        cells.append(cell)

    # Environment-dependent contrast: A2 effect - A0 effect, paired by seed.
    env_contrasts = []
    lookup = {(r["trait"], float(r["factor"]), r["environment"], int(r["seed"])): r
              for r in all_pairs}
    for trait in sorted({r["trait"] for r in all_pairs}):
        for factor in sorted({float(r["factor"]) for r in all_pairs if r["trait"] == trait}):
            block = {"trait": trait, "factor": factor, "seeds": [20001, 20002, 20003]}
            for m in metric_names:
                vals = []
                for seed in (20001, 20002, 20003):
                    a0 = lookup[(trait, factor, "A0_STATIC", seed)].get(m)
                    a2 = lookup[(trait, factor, "A2_DYNAMIC_VENT", seed)].get(m)
                    vals.append(None if a0 is None or a2 is None else float(a2) - float(a0))
                block[f"A2_minus_A0__{m}"] = q(vals)
            env_contrasts.append(block)

    out = {
        "experiment": "Exp20 Attempt 2 paired fitness-effect assay",
        "artifacts_complete": True,
        "n_environment_seed_artifacts": len(files),
        "n_pair_contrasts": len(all_pairs),
        "all_gates_pass": True,
        "cells": cells,
        "environment_dependent_contrasts": env_contrasts,
        "raw_pairs": all_pairs,
    }
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")

    flat_fields = ["trait", "factor", "environment", "seed", "variant_value"] + metric_names
    with args.csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=flat_fields)
        w.writeheader()
        for r in sorted(all_pairs, key=lambda x: (x["trait"], float(x["factor"]), x["environment"], int(x["seed"]))):
            w.writerow({k: r.get(k) for k in flat_fields})

    print(json.dumps({"artifacts_complete": True, "n_pairs": len(all_pairs),
                      "n_cells": len(cells), "all_gates_pass": True}, indent=2))


if __name__ == "__main__":
    main()
