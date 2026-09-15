"""Exp23集計 (docs/Exp23_実験計画.md §13)。

flux別に8 seeds分のprimary/secondary endpointを集計する。24/24 runs
completenessを必須gateとし、artifact欠損はsilent skipせずfail loudly。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

REQUIRED_ARTIFACTS = ("effective_config.json", "summary.json", "timeseries.csv",
                     "initial_genome.json")
FLUX_LEVELS = (0.0, 0.5, 1.5)
SEEDS = (23001, 23002, 23003, 23004, 23005, 23006, 23007, 23008)


def load_runs(root: Path) -> list[dict]:
    rows = []
    for summary_path in sorted(root.rglob("summary.json")):
        run_dir = summary_path.parent
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        if s.get("experiment") != "Exp23 phototrophy OFF/ON direct competition":
            continue
        missing = [a for a in REQUIRED_ARTIFACTS if not (run_dir / a).exists()]
        s["_path"] = str(run_dir)
        s["_missing_artifacts"] = missing
        rows.append(s)
    return rows


def qstats(values) -> dict:
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not vals:
        return {"mean": None, "median": None, "min": None, "max": None, "n": 0}
    a = np.asarray(vals)
    return {"mean": float(a.mean()), "median": float(np.median(a)),
           "min": float(a.min()), "max": float(a.max()), "n": len(vals)}


def aggregate(rows: list[dict]) -> dict:
    by_flux = defaultdict(list)
    for r in rows:
        by_flux[r["flux"]].append(r)

    n_expected = len(FLUX_LEVELS) * len(SEEDS)
    artifacts_complete = len(rows) == n_expected and all(
        not r["_missing_artifacts"] for r in rows)

    by_flux_summary = {}
    for flux, group in by_flux.items():
        final_f_photo = [r["summary"]["final_f_photo"] for r in group]
        delta_f_photo = [r["summary"]["delta_f_photo_from_half"] for r in group]
        sel_coef = [r["summary"]["median_selection_coefficient_per_h"] for r in group]
        off_births = [r["summary"]["OFF_births_cum"] for r in group]
        on_births = [r["summary"]["ON_births_cum"] for r in group]
        off_deaths = [r["summary"]["OFF_deaths_cum"] for r in group]
        on_deaths = [r["summary"]["ON_deaths_cum"] for r in group]
        fixation = {"OFF": 0, "ON": 0, "none": 0}
        for r in group:
            fixed = r["summary"].get("fixed_lineage")
            fixation[fixed if fixed in ("OFF", "ON") else "none"] += 1
        birth_diff = [on_b - off_b for on_b, off_b in zip(on_births, off_births)]
        death_diff = [on_d - off_d for on_d, off_d in zip(on_deaths, off_deaths)]
        by_flux_summary[flux] = {
            "n_seeds": len(group),
            "final_f_photo": qstats(final_f_photo),
            "n_seeds_f_photo_gt_half": sum(1 for v in final_f_photo if v is not None and v > 0.5),
            "median_delta_f_photo": qstats(delta_f_photo)["median"],
            "median_selection_coefficient_per_h": qstats(sel_coef)["median"],
            "lineage_birth_diff_ON_minus_OFF": qstats(birth_diff),
            "lineage_death_diff_ON_minus_OFF": qstats(death_diff),
            "fixation_counts": fixation,
        }

    flux_order = sorted(by_flux_summary)
    medians = [by_flux_summary[f]["final_f_photo"]["median"] for f in flux_order]
    monotonic = all(
        (medians[i] is not None and medians[i + 1] is not None and medians[i] <= medians[i + 1])
        for i in range(len(medians) - 1)
    ) if all(m is not None for m in medians) else None

    return {
        "n_runs": len(rows),
        "n_expected": n_expected,
        "artifacts_complete": artifacts_complete,
        "by_flux": by_flux_summary,
        "flux_response_monotonic_median_f_photo": monotonic,
    }


def write_per_run_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["flux", "seed", "final_f_photo", "delta_f_photo_from_half",
                   "median_selection_coefficient_per_h", "fixed_lineage",
                   "OFF_births_cum", "ON_births_cum", "OFF_deaths_cum", "ON_deaths_cum"])
        for r in rows:
            s = r["summary"]
            w.writerow([r["flux"], r["seed"], s["final_f_photo"], s["delta_f_photo_from_half"],
                       s["median_selection_coefficient_per_h"], s.get("fixed_lineage"),
                       s["OFF_births_cum"], s["ON_births_cum"], s["OFF_deaths_cum"], s["ON_deaths_cum"]])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_runs(args.root)
    result = aggregate(rows)
    (args.out_dir / "exp23_aggregate.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    write_per_run_csv(args.out_dir / "exp23_per_run.csv", rows)
    print(json.dumps({"n_runs": result["n_runs"], "n_expected": result["n_expected"],
                      "artifacts_complete": result["artifacts_complete"],
                      "flux_response_monotonic_median_f_photo":
                          result["flux_response_monotonic_median_f_photo"]}, indent=2))


if __name__ == "__main__":
    main()
