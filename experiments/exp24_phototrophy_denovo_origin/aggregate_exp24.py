"""Exp24集計 (docs/Exp24_実験計画.md §12/§14)。

seed-level establishment-rate table、F2-F0 paired difference (primary)、
F1-F0 (secondary)、cluster (seed) bootstrap 95% CIを計算する。
48/48 run completenessを必須gateとし、artifact欠損はfail loudly。

このスクリプト自身は「Strong Support」の最終科学判断は下さない
(docs §12.2の5条件それぞれの真偽値と補助統計を出力するだけに留める)。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

REQUIRED_ARTIFACTS = ("effective_config.json", "summary.json",
                     "exp24_origins.csv", "initial_genome.json")
FLUX_LEVELS = (0.0, 0.5, 1.5)
SEEDS = tuple(range(24001, 24017))
N_EXPECTED = len(FLUX_LEVELS) * len(SEEDS)
BOOTSTRAP_B = 10000
BOOTSTRAP_SEED = 240000


def load_runs(root: Path) -> list[dict]:
    rows = []
    for summary_path in sorted(root.rglob("summary.json")):
        run_dir = summary_path.parent
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        if s.get("experiment") != "Exp24 phototrophy de novo recurrent-origin establishment assay":
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


def establishment_rate_table(rows: list[dict]) -> dict:
    """seed -> flux -> establishment_rate (None if eligible_origins==0)."""
    table: dict[int, dict[float, float | None]] = defaultdict(dict)
    for r in rows:
        table[r["seed"]][r["flux"]] = r["summary"]["establishment_rate"]
    return dict(table)


def cluster_bootstrap_ci(delta_by_seed: list[float], b: int = BOOTSTRAP_B,
                         seed: int = BOOTSTRAP_SEED) -> dict:
    """docs §12.2 条件4: seedをclusterとしたbootstrap 95% CI。"""
    vals = np.asarray([v for v in delta_by_seed if v is not None], dtype=np.float64)
    if len(vals) == 0:
        return {"lower_95": None, "upper_95": None, "n_clusters": 0, "mean": None}
    rng = np.random.default_rng(seed)
    n = len(vals)
    means = np.empty(b)
    for i in range(b):
        sample = rng.integers(0, n, size=n)
        means[i] = vals[sample].mean()
    return {
        "lower_95": float(np.percentile(means, 2.5)),
        "upper_95": float(np.percentile(means, 97.5)),
        "n_clusters": int(n),
        "mean": float(vals.mean()),
        "n_bootstrap": b,
    }


def aggregate(rows: list[dict]) -> dict:
    artifacts_complete = len(rows) == N_EXPECTED and all(not r["_missing_artifacts"] for r in rows)

    by_flux = defaultdict(list)
    for r in rows:
        by_flux[r["flux"]].append(r)

    by_flux_summary = {}
    for flux, group in by_flux.items():
        est = [r["summary"]["establishment_rate"] for r in group]
        total_origins = [r["summary"]["total_origins"] for r in group]
        eligible = [r["summary"]["eligible_origins"] for r in group]
        survived = [r["summary"]["survived_960_count"] for r in group]
        by_flux_summary[flux] = {
            "n_seeds": len(group),
            "establishment_rate": qstats(est),
            "total_origins": qstats(total_origins),
            "eligible_origins": qstats(eligible),
            "survived_960_count": qstats(survived),
            "n_seeds_eligible_origins_zero": sum(1 for e in eligible if e == 0),
            "degenerate_flag_count": sum(1 for r in group if r["summary"].get("degenerate_flag")),
        }

    est_table = establishment_rate_table(rows)
    delta_f2_f0 = []
    delta_f1_f0 = []
    per_seed_rows = []
    for seed in SEEDS:
        fx = est_table.get(seed, {})
        e0, e1, e2 = fx.get(0.0), fx.get(0.5), fx.get(1.5)
        d20 = (e2 - e0) if (e2 is not None and e0 is not None) else None
        d10 = (e1 - e0) if (e1 is not None and e0 is not None) else None
        delta_f2_f0.append(d20)
        delta_f1_f0.append(d10)
        per_seed_rows.append({"seed": seed, "E_F0": e0, "E_F0.5": e1, "E_F1.5": e2,
                              "delta_E_seed_F2_minus_F0": d20, "delta_E_seed_F1_minus_F0": d10})

    valid_d20 = [d for d in delta_f2_f0 if d is not None]
    n_positive = sum(1 for d in valid_d20 if d > 0)
    median_delta = float(np.median(valid_d20)) if valid_d20 else None
    ci = cluster_bootstrap_ci(valid_d20)

    strong_support = {
        "condition_1_integrity_gates_pass": None,  # フィルされるのはExp24結果考察側 (formal preflight/G12結果参照)
        "condition_2_n_positive_seeds_ge_12_of_16": (n_positive >= 12) if valid_d20 else None,
        "condition_2_n_positive_seeds": n_positive,
        "condition_2_n_valid_seeds": len(valid_d20),
        "condition_3_median_delta_positive": (median_delta > 0) if median_delta is not None else None,
        "condition_3_median_delta": median_delta,
        "condition_4_bootstrap_ci_lower_above_zero": (
            (ci["lower_95"] > 0) if ci["lower_95"] is not None else None),
        "condition_4_bootstrap_ci": ci,
        "condition_5_light_energy_used_in_f2": None,  # 別途per-run ledgerで確認 (photo_used_j_cum > 0)
    }

    # condition 5: F2 (flux=1.5) runsのうち少なくとも1つでphoto_used_j_cum>0
    f2_group = by_flux.get(1.5, [])
    any_light_used = any(
        r["summary"].get("ledger", {}).get("photo_used_j_cum", 0.0) > 0.0 for r in f2_group
    )
    strong_support["condition_5_light_energy_used_in_f2"] = bool(any_light_used) if f2_group else None

    return {
        "n_runs": len(rows),
        "n_expected": N_EXPECTED,
        "artifacts_complete": artifacts_complete,
        "by_flux": by_flux_summary,
        "per_seed": per_seed_rows,
        "delta_f2_f0_qstats": qstats(delta_f2_f0),
        "delta_f1_f0_qstats": qstats(delta_f1_f0),
        "strong_support_proposal": strong_support,
    }


def write_per_run_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["flux", "seed", "total_origins", "eligible_origins",
                   "survived_960_count", "establishment_rate", "degenerate_flag"])
        for r in rows:
            s = r["summary"]
            w.writerow([r["flux"], r["seed"], s["total_origins"], s["eligible_origins"],
                       s["survived_960_count"], s["establishment_rate"], s.get("degenerate_flag")])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_runs(args.root)
    result = aggregate(rows)
    (args.out_dir / "exp24_aggregate.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    write_per_run_csv(args.out_dir / "exp24_per_run.csv", rows)
    print(json.dumps({"n_runs": result["n_runs"], "n_expected": result["n_expected"],
                      "artifacts_complete": result["artifacts_complete"],
                      "strong_support_proposal": result["strong_support_proposal"]}, indent=2))
    if not result["artifacts_complete"]:
        raise SystemExit(
            f"Exp24 aggregate: incomplete runs {result['n_runs']}/{result['n_expected']}")


if __name__ == "__main__":
    main()
