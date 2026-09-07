"""Aggregate Exp15 run summaries and evaluate the preregistered Phase-A gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SEEDS = [15001, 15002, 15003, 15004, 15005]


def load(root: Path, arm: str):
    rows = []
    for p in root.rglob("summary.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("experiment") == "Exp15 V1.9 formal" and d.get("arm") == arm:
            rows.append(d)
    rows.sort(key=lambda x: x["seed"])
    return rows


def gate(rows):
    by_seed = {r["seed"]: r for r in rows}
    complete = all(s in by_seed for s in SEEDS)
    qualifying = sum(by_seed[s]["max_generation"] >= 5 for s in SEEDS if s in by_seed)
    return {
        "complete_5_seeds": complete,
        "seeds": sorted(by_seed),
        "n_max_generation_ge_5": qualifying,
        "pass": bool(complete and qualifying >= 3),
        "rule": ">=3/5 seeds reach max_generation >= 5",
    }


def matched(a_rows, b_rows):
    a = {r["seed"]: r for r in a_rows}
    b = {r["seed"]: r for r in b_rows}
    out = []
    for s in SEEDS:
        if s not in a or s not in b:
            continue
        ar, br = a[s], b[s]
        def survival_h(r):
            return r["extinction_time_h"] if r["extinction_time_h"] is not None else r["days_completed"] * 24.0
        out.append({
            "seed": s,
            "A_population_final": ar["population_final"],
            "B_population_final": br["population_final"],
            "A_max_generation": ar["max_generation"],
            "B_max_generation": br["max_generation"],
            "delta_max_generation": br["max_generation"] - ar["max_generation"],
            "A_survival_h": survival_h(ar),
            "B_survival_h": survival_h(br),
            "delta_survival_h": survival_h(br) - survival_h(ar),
            "A_population_auc_cell_days": ar["population_auc_cell_days"],
            "B_population_auc_cell_days": br["population_auc_cell_days"],
            "delta_population_auc_cell_days": br["population_auc_cell_days"] - ar["population_auc_cell_days"],
            "B_gene_shift_pct": br["final20pct_gene_shift_pct_vs_baseline"],
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--gate-only", action="store_true")
    args = ap.parse_args()
    a = load(args.root, "A")
    g = gate(a)
    result = {"phase_a_gate": g, "phase_a": a}
    if not args.gate_only:
        b = load(args.root, "B")
        result["phase_b"] = b
        result["matched_A_vs_B"] = matched(a, b)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
