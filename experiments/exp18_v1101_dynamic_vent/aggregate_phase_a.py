"""Aggregate Exp18 Phase A summaries and apply the dynamic-arm-selection rule.

正本: docs/Exp18_V1.10.1_動的熱水噴出口_実験計画.md §4-5。
preregistered gateはmissing artifactでsilent SKIPせずFAILさせる (§10)。
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

# Phase B dynamic arm選択順 (docs §5: 事後恣意性を避けるため、この順で
# 最初に基準を満たした条件を採用する)
SELECTION_ORDER = ("A3", "A2", "A1")
SELECTION_MIN_SURVIVE_FRAC = 2.0 / 3.0
SELECTION_MIN_MEDIAN_MAX_GEN = 3


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
        if s.get("phase") != "A":
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


def summarize_condition(rows: list[dict]) -> dict:
    n = len(rows)
    survive = [r.get("population_final", 0) > 0 for r in rows]
    max_gens = [r.get("max_generation") or 0 for r in rows]
    n_survive = sum(survive)
    return {
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
    }


def select_dynamic_arm(by_condition: dict[str, dict]) -> dict:
    """docs §5: A3 -> A2 -> A1 の順で、survive_fraction>=2/3 かつ
    median_max_generation>=3 を最初に満たした条件をPhase B dynamic armとする。
    どれも満たさなければPhase Bは実行しない (値の自動調整で救済しない)。
    """
    for condition in SELECTION_ORDER:
        stats = by_condition.get(condition)
        if stats is None:
            continue
        ok = (
            stats["survive_fraction"] is not None
            and stats["survive_fraction"] >= SELECTION_MIN_SURVIVE_FRAC
            and stats["median_max_generation"] is not None
            and stats["median_max_generation"] >= SELECTION_MIN_MEDIAN_MAX_GEN
        )
        if ok:
            return {"selected": condition, "reason": "meets_criteria",
                   "criteria": {"min_survive_fraction": SELECTION_MIN_SURVIVE_FRAC,
                               "min_median_max_generation": SELECTION_MIN_MEDIAN_MAX_GEN}}
    return {"selected": None,
           "reason": "no_dynamic_condition_meets_criteria; "
                    "existing iLUCA too fragile for current dynamic vent conditions",
           "criteria": {"min_survive_fraction": SELECTION_MIN_SURVIVE_FRAC,
                       "min_median_max_generation": SELECTION_MIN_MEDIAN_MAX_GEN}}


def aggregate(rows: list[dict]) -> dict:
    by_condition_rows = defaultdict(list)
    for r in rows:
        by_condition_rows[r["condition"]].append(r)
    by_condition = {c: summarize_condition(rr) for c, rr in by_condition_rows.items()}

    a0 = by_condition.get("A0")
    a0_integrity = bool(
        a0 and a0["n_runs"] == 3 and a0["artifacts_complete"]
        and a0["n_survive"] == 3 and a0["all_cnp_ledgers_valid"]
    )
    selection = select_dynamic_arm(by_condition)
    artifacts_complete_all = all(c["artifacts_complete"] for c in by_condition.values())
    ledgers_valid_all = all(c["all_cnp_ledgers_valid"] for c in by_condition.values())
    n_expected = 4 * 3  # A0-A3 x 3 seeds

    return {
        "n_runs": len(rows),
        "conditions": sorted(by_condition),
        "by_condition": by_condition,
        "a0_integrity_control_pass": a0_integrity,
        "artifacts_complete": artifacts_complete_all and len(rows) == n_expected,
        "cnp_ledgers_valid": ledgers_valid_all,
        "phase_b_dynamic_arm_selection": selection,
        "phase_b_should_run": selection["selected"] is not None,
    }


def write_csv(rows: list[dict], path: Path) -> None:
    import csv
    fields = ["seed", "condition", "population_final", "population_max",
             "max_generation", "stop_reason", "final_starvation_active_fraction",
             "vent_turnover_count_cum", "energy_ledger_residual_j"]
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
