"""Aggregate Exp18 Phase B summaries (mechanical readout only).

正本: docs/Exp18_V1.10.1_動的熱水噴出口_実験計画.md §6-8, §10。
Phase Bには固定PASS/FAIL gateはない (§8: 方向をPASS条件として固定しない)。
ここではarmごとの生態・進化readoutを機械的に集計するのみで、
考察・解釈文は書かない (docs §11の解釈判断は別途human/Claudeが行う)。
missing artifactはsilent skipせずintegrity FAILとして記録する (§10)。
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REQUIRED_ARTIFACTS = (
    "effective_config.json", "initial_genome.json", "summary.json",
    "timeseries.csv", "cnp_ledger.json", "vent_schedule.json",
)

GENES = ("storage_capacity", "starvation_horizon", "reproduction_horizon")


def _finite(values):
    return [float(v) for v in values if v is not None and math.isfinite(float(v))]


def qstats(values):
    a = np.asarray(_finite(values), dtype=float)
    if a.size == 0:
        return {"mean": None, "median": None, "q10": None, "q90": None, "min": None, "max": None}
    return {"mean": float(a.mean()), "median": float(np.median(a)),
           "q10": float(np.quantile(a, 0.10)), "q90": float(np.quantile(a, 0.90)),
           "min": float(a.min()), "max": float(a.max())}


def load_runs(root: Path) -> list[dict]:
    rows = []
    for summary_path in sorted(root.rglob("summary.json")):
        run_dir = summary_path.parent
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        if s.get("phase") != "B":
            continue
        missing = [a for a in REQUIRED_ARTIFACTS if not (run_dir / a).exists()]
        s["_path"] = str(run_dir)
        s["_missing_artifacts"] = missing
        rows.append(s)
    return rows


def _ledger_valid(s: dict, tol: float = 1e-6) -> bool:
    ledger = s.get("cnp_ledger", {})
    for element in ("carbon", "nitrogen", "phosphorus"):
        rel = ledger.get(element, {}).get("residual_relative")
        if rel is None or not math.isfinite(rel) or abs(rel) > tol:
            return False
    return True


def _gene_series(rows: list[dict], gene: str, stat: str) -> list[float]:
    return [r.get("final_gene_stats", {}).get(gene, {}).get(stat) for r in rows]


def summarize_arm(rows: list[dict]) -> dict:
    n = len(rows)
    survive = [r.get("population_final", 0) > 0 for r in rows]
    max_gens = [r.get("max_generation") or 0 for r in rows]
    n_survive = sum(survive)
    out = {
        "n_runs": n,
        "seeds": sorted(int(r["seed"]) for r in rows),
        "artifacts_complete": all(not r["_missing_artifacts"] for r in rows),
        "n_survive": n_survive,
        "survive_fraction": n_survive / n if n else None,
        "median_max_generation": float(np.median(max_gens)) if max_gens else None,
        "population_final": qstats([r.get("population_final") for r in rows]),
        "population_auc_cell_days": qstats([r.get("population_auc_cell_days") for r in rows]),
        "max_generation": qstats([r.get("max_generation") for r in rows]),
        "final_starvation_active_fraction": qstats(
            [r.get("final_starvation_active_fraction") for r in rows]),
        "energy_ledger_residual_j_max_abs": max(
            (abs(r.get("energy_ledger_residual_j", 0.0)) for r in rows), default=None),
        "all_cnp_ledgers_valid": all(_ledger_valid(r) for r in rows),
        "vent_turnover_count_cum": qstats([r.get("vent_turnover_count_cum") for r in rows]),
        "stop_reasons": dict(Counter(str(r.get("stop_reason")) for r in rows)),
        "final_gene_stats_across_seeds": {},
    }
    for gene in GENES:
        out["final_gene_stats_across_seeds"][gene] = {
            "median_of_seed_medians": qstats(_gene_series(rows, gene, "median"))["median"],
            "median_of_seed_means": qstats(_gene_series(rows, gene, "mean"))["median"],
            "median_of_seed_q10": qstats(_gene_series(rows, gene, "q10"))["median"],
            "median_of_seed_q90": qstats(_gene_series(rows, gene, "q90"))["median"],
        }
    return out


def aggregate(rows: list[dict]) -> dict:
    by_arm_rows = defaultdict(list)
    for r in rows:
        by_arm_rows[r["arm"]].append(r)
    by_arm = {a: summarize_arm(rr) for a, rr in by_arm_rows.items()}

    artifacts_complete_all = all(c["artifacts_complete"] for c in by_arm.values())
    ledgers_valid_all = all(c["all_cnp_ledgers_valid"] for c in by_arm.values())
    n_expected = 4 * 5  # B0-B3 x 5 seeds

    return {
        "n_runs": len(rows),
        "arms": sorted(by_arm),
        "by_arm": by_arm,
        "artifacts_complete": artifacts_complete_all and len(rows) == n_expected,
        "cnp_ledgers_valid": ledgers_valid_all,
    }


def write_csv(rows: list[dict], path: Path) -> None:
    import csv
    fields = ["seed", "arm", "environment", "genetics", "dynamic_condition",
             "population_final", "population_max", "max_generation", "stop_reason",
             "final_starvation_active_fraction", "vent_turnover_count_cum",
             "energy_ledger_residual_j"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--csv", type=Path, required=True)
    args = ap.parse_args()

    rows = load_runs(args.root)
    result = aggregate(rows)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(rows, args.csv)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
