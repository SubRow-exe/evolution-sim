"""Aggregate Exp20 seeded-invasion runs (docs Exp20 §8-9,12)。

primary estimand R48/s48/Delta_s48は事前登録式のまま機械計算するだけで、
方向をPASS/FAIL判定しない (§8: n=3なのでp値による有意差判定を主目的に
しない)。missing/incomplete runはsilent skipせずintegrity FAILとして
記録する (§12)。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

REQUIRED_ARTIFACTS = ("effective_config.json", "founders.json", "summary.json", "stats.csv")
ENVIRONMENTS = ("A0_STATIC", "A1_TEMPORAL")
FREQUENCIES = (0.0, 0.01, 0.10, 0.50)
SEEDS = (20001, 20002, 20003)
PSEUDOCOUNT = 0.5  # docs §8


def load_runs(root: Path) -> list[dict]:
    rows = []
    for summary_path in sorted(root.rglob("summary.json")):
        run_dir = summary_path.parent
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        if "environment" not in s or "initial_frequency" not in s:
            continue
        missing = [a for a in REQUIRED_ARTIFACTS if not (run_dir / a).exists()]
        s["_path"] = str(run_dir)
        s["_missing_artifacts"] = missing
        rows.append(s)
    return rows


def _log_ratio(p: float, a: float) -> float:
    return math.log((p + PSEUDOCOUNT) / (a + PSEUDOCOUNT))


def r48_and_s48(row: dict) -> dict | None:
    """docs §8: R48 = ln((P48+.5)/(A48+.5)) - ln((P0+.5)/(A0+.5)), s48=R48/2。"""
    row0 = row.get("row_0h")
    row48 = row.get("row_48h")
    if row0 is None or row48 is None:
        return None
    p0, a0 = row0["population_photo"], row0["population_ancestor"]
    p48, a48 = row48["population_photo"], row48["population_ancestor"]
    r48 = _log_ratio(p48, a48) - _log_ratio(p0, a0)
    return {"P0": p0, "A0": a0, "P48": p48, "A48": a48, "R48": r48, "s48_per_day": r48 / 2.0}


def _ledger_valid(s: dict, tol: float = 1e-6) -> bool:
    for key in ("nitrogen_ledger", "carbon_ledger", "phosphorus_ledger"):
        rel = s.get(key, {}).get("residual_relative")
        if rel is None or not math.isfinite(rel) or abs(rel) > tol:
            return False
    return True


def _identity_valid(s: dict, tol_rel: float = 1e-9) -> bool:
    """docs §6/§9.4 required identity:
    used <= usable_max <= absorbed <= incident (数値誤差tolerance込み)。"""
    used = s.get("photo_used_j_cum", 0.0)
    usable = s.get("photo_usable_max_j_cum", 0.0)
    absorbed = s.get("photo_absorbed_j_cum", 0.0)
    incident = s.get("photo_incident_j_cum", 0.0)

    def le(a, b):
        return a <= b + tol_rel * max(abs(b), 1e-300)
    return le(used, usable) and le(usable, absorbed) and le(absorbed, incident)


def aggregate(rows: list[dict]) -> dict:
    by_key = defaultdict(list)
    for r in rows:
        by_key[(r["environment"], r["initial_frequency"], r["seed"])].append(r)

    n_expected = len(ENVIRONMENTS) * len(FREQUENCIES) * len(SEEDS)
    artifacts_complete = len(rows) == n_expected and all(
        not r["_missing_artifacts"] for r in rows)
    ledgers_valid = all(_ledger_valid(r) for r in rows)
    identities_valid = all(_identity_valid(r) for r in rows)

    r48_by_run = {}
    for key, group in by_key.items():
        if len(group) != 1:
            continue
        r48_by_run[key] = r48_and_s48(group[0])

    delta_s48 = {}
    for freq in FREQUENCIES:
        for seed in SEEDS:
            a0_key = ("A0_STATIC", freq, seed)
            a1_key = ("A1_TEMPORAL", freq, seed)
            a0_r = r48_by_run.get(a0_key)
            a1_r = r48_by_run.get(a1_key)
            if a0_r is None or a1_r is None:
                continue
            delta_s48[f"freq={freq}_seed={seed}"] = {
                "s48_A0": a0_r["s48_per_day"], "s48_A1": a1_r["s48_per_day"],
                "delta_s48": a1_r["s48_per_day"] - a0_r["s48_per_day"],
            }

    by_freq_median = {}
    for freq in FREQUENCIES:
        vals = [v["delta_s48"] for k, v in delta_s48.items() if k.startswith(f"freq={freq}_")]
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        median = (vals_sorted[n // 2] if n % 2 == 1
                 else (vals_sorted[n // 2 - 1] + vals_sorted[n // 2]) / 2.0) if n else None
        by_freq_median[freq] = {"n": n, "median_delta_s48": median,
                                "signs": [1 if v > 0 else (-1 if v < 0 else 0) for v in vals_sorted]}

    return {
        "n_runs": len(rows),
        "n_expected": n_expected,
        "artifacts_complete": artifacts_complete,
        "cnp_ledgers_valid": ledgers_valid,
        "photo_energy_identities_valid": identities_valid,
        "r48_by_run": {f"{k[0]}_freq={k[1]}_seed={k[2]}": v for k, v in r48_by_run.items()},
        "delta_s48_by_run": delta_s48,
        "delta_s48_by_frequency": by_freq_median,
    }


def write_csv(rows: list[dict], path: Path) -> None:
    fields = ["seed", "environment", "initial_frequency", "n_founders",
             "population_final_total", "population_final_photo",
             "population_final_ancestor", "extinction_time_h", "stop_reason",
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
