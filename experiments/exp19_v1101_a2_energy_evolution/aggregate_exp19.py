"""Aggregate Exp19 summaries (mechanical readout only, no PASS/FAIL gate).

正本: docs/Exp19_A2環境_Energy戦略進化_実験計画.md §9-11。

Exp19には固定PASS/FAIL閾値を置かない (§11: 特定形質の方向を事前固定しない)。
ここではarmごとの生態readoutと、3 gene (storage_capacity / starvation_horizon /
reproduction_horizon) の initial -> final / initial -> last20%window shiftを
機械的に集計するだけで、解釈文は書かない。missing artifactはsilent skipせず
integrity FAILとして記録する (§13: silent skip禁止)。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

REQUIRED_ARTIFACTS = (
    "effective_config.json", "initial_genome.json", "summary.json",
    "timeseries.csv", "cnp_ledger.json", "vent_schedule.json",
)

GENES = ("storage_capacity", "starvation_horizon", "reproduction_horizon")
ARMS = ("E0_STATIC_FIXED", "E1_STATIC_EVOLVE", "E2_A2_DYNAMIC_FIXED", "E3_A2_DYNAMIC_EVOLVE")
SEEDS = (19001, 19002, 19003)


def _finite(values):
    return [float(v) for v in values if v not in (None, "") and math.isfinite(float(v))]


def qstats(values) -> dict:
    a = np.asarray(_finite(values), dtype=float)
    if a.size == 0:
        return {"mean": None, "median": None, "q10": None, "q90": None, "min": None, "max": None}
    return {"mean": float(a.mean()), "median": float(np.median(a)),
           "q10": float(np.quantile(a, 0.10)), "q90": float(np.quantile(a, 0.90)),
           "min": float(a.min()), "max": float(a.max())}


def _read_timeseries(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gene_shift_for_run(run_dir: Path) -> dict:
    """1 runのtimeseries.csvから3 geneのinitial/final/last20%windowを求める
    (docs §9.2)。population絶滅runはNoneを返す (silent skipではなく
    明示的にnullとして記録する)。
    """
    ts_path = run_dir / "timeseries.csv"
    if not ts_path.exists():
        return {g: None for g in GENES}
    rows = _read_timeseries(ts_path)
    if not rows:
        return {g: None for g in GENES}
    n = len(rows)
    last20_start = max(0, int(round(n * 0.8)))
    last20_rows = rows[last20_start:]
    out = {}
    for gene in GENES:
        col_mean = f"{gene}_mean"
        col_median = f"{gene}_median"
        initial_mean = rows[0].get(col_mean)
        final_mean = rows[-1].get(col_mean)
        initial_median = rows[0].get(col_median)
        final_median = rows[-1].get(col_median)
        last20_mean = qstats([r.get(col_mean) for r in last20_rows])["mean"]
        last20_median = qstats([r.get(col_median) for r in last20_rows])["median"]
        try:
            initial_mean_f = float(initial_mean) if initial_mean not in (None, "") else None
            final_mean_f = float(final_mean) if final_mean not in (None, "") else None
        except ValueError:
            initial_mean_f = final_mean_f = None
        out[gene] = {
            "initial_mean": initial_mean_f,
            "final_mean": final_mean_f,
            "initial_median": (float(initial_median) if initial_median not in (None, "") else None),
            "final_median": (float(final_median) if final_median not in (None, "") else None),
            "last20pct_window_mean": last20_mean,
            "last20pct_window_median": last20_median,
            "shift_initial_to_final_mean": (
                final_mean_f - initial_mean_f
                if final_mean_f is not None and initial_mean_f is not None else None),
            "shift_initial_to_last20pct_mean": (
                last20_mean - initial_mean_f
                if last20_mean is not None and initial_mean_f is not None else None),
        }
    return out


def load_runs(root: Path) -> list[dict]:
    rows = []
    for summary_path in sorted(root.rglob("summary.json")):
        run_dir = summary_path.parent
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        if "exp19_arm" not in s:
            continue
        missing = [a for a in REQUIRED_ARTIFACTS if not (run_dir / a).exists()]
        s["_path"] = str(run_dir)
        s["_missing_artifacts"] = missing
        s["_gene_shift"] = gene_shift_for_run(run_dir) if not missing else {g: None for g in GENES}
        rows.append(s)
    return rows


def _ledger_valid(s: dict, tol: float = 1e-6) -> bool:
    ledger = s.get("cnp_ledger", {})
    for element in ("carbon", "nitrogen", "phosphorus"):
        rel = ledger.get(element, {}).get("residual_relative")
        if rel is None or not math.isfinite(rel) or abs(rel) > tol:
            return False
    return True


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
        "gene_shift_by_seed": {int(r["seed"]): r["_gene_shift"] for r in rows},
        "gene_shift_summary": {},
    }
    for gene in GENES:
        shifts = [r["_gene_shift"].get(gene, {}).get("shift_initial_to_final_mean")
                 for r in rows if r["_gene_shift"].get(gene) is not None]
        out["gene_shift_summary"][gene] = qstats(shifts)
    return out


def compare(by_arm: dict, a: str, b: str) -> dict:
    """A vs B の記述的比較 (Comparison A/B/C, docs §10)。PASS/FAILは判定しない。"""
    out = {"arm_a": a, "arm_b": b}
    if a not in by_arm or b not in by_arm:
        out["note"] = "one or both arms missing from runs"
        return out
    sa, sb = by_arm[a], by_arm[b]
    out["survive_fraction"] = {a: sa["survive_fraction"], b: sb["survive_fraction"]}
    out["median_max_generation"] = {a: sa["median_max_generation"], b: sb["median_max_generation"]}
    out["population_auc_cell_days_median"] = {
        a: sa["population_auc_cell_days"]["median"], b: sb["population_auc_cell_days"]["median"]}
    out["final_starvation_active_fraction_median"] = {
        a: sa["final_starvation_active_fraction"]["median"],
        b: sb["final_starvation_active_fraction"]["median"]}
    out["gene_shift_median"] = {
        gene: {a: sa["gene_shift_summary"][gene]["median"],
              b: sb["gene_shift_summary"][gene]["median"]}
        for gene in GENES}
    return out


def aggregate(rows: list[dict]) -> dict:
    by_arm_rows = defaultdict(list)
    for r in rows:
        by_arm_rows[r["exp19_arm"]].append(r)
    by_arm = {a: summarize_arm(rr) for a, rr in by_arm_rows.items()}

    artifacts_complete_all = all(c["artifacts_complete"] for c in by_arm.values())
    ledgers_valid_all = all(c["all_cnp_ledgers_valid"] for c in by_arm.values())
    n_expected = len(ARMS) * len(SEEDS)  # 4 arms x 3 seeds = 12

    return {
        "n_runs": len(rows),
        "arms": sorted(by_arm),
        "by_arm": by_arm,
        "artifacts_complete": artifacts_complete_all and len(rows) == n_expected,
        "cnp_ledgers_valid": ledgers_valid_all,
        "comparisons": {
            "A_E2_vs_E3": compare(by_arm, "E2_A2_DYNAMIC_FIXED", "E3_A2_DYNAMIC_EVOLVE"),
            "B_E1_vs_E3": compare(by_arm, "E1_STATIC_EVOLVE", "E3_A2_DYNAMIC_EVOLVE"),
            "C_E0_vs_E1": compare(by_arm, "E0_STATIC_FIXED", "E1_STATIC_EVOLVE"),
        },
    }


def write_csv(rows: list[dict], path: Path) -> None:
    fields = ["seed", "exp19_arm", "environment", "genetics", "dynamic_condition",
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
