"""Aggregate Exp17 V1.10 C/N/P Phase A / Phase B summaries and evaluate gates.

正本: docs/Exp17_V1.10_CNP資源分解_実験計画.md §3-4 / §6-9。
preregistered gateはmissing artifactでsilent SKIPせずFAILさせる (§8)。
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
    "timeseries.csv", "cnp_ledger.json", "growth_limiter.csv",
)

LEDGER_RESIDUAL_GATE = 1e-6  # relative; openなので1e-9厳密closureは要求しない
ALL_LIMITERS = ("energy", "kinetic", "carbon", "nitrogen", "phosphorus", "room")


def _finite(values):
    return [float(v) for v in values if v is not None and math.isfinite(float(v))]


def qstats(values):
    a = np.asarray(_finite(values), dtype=float)
    if a.size == 0:
        return {"mean": None, "median": None, "q10": None, "q90": None, "min": None, "max": None}
    return {"mean": float(a.mean()), "median": float(np.median(a)),
           "q10": float(np.quantile(a, 0.10)), "q90": float(np.quantile(a, 0.90)),
           "min": float(a.min()), "max": float(a.max())}


def load_runs(root: Path, phase: str) -> list[dict]:
    """root配下の各run directoryからsummary.jsonを読む。artifact欠落はFAIL扱い。"""
    rows = []
    for summary_path in sorted(root.rglob("summary.json")):
        run_dir = summary_path.parent
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        if s.get("phase") != phase:
            continue
        missing = [a for a in REQUIRED_ARTIFACTS if not (run_dir / a).exists()]
        s["_path"] = str(run_dir)
        s["_missing_artifacts"] = missing
        rows.append(s)
    return rows


def _ledger_valid(s: dict) -> bool:
    ledger = s.get("cnp_ledger", {})
    for element in ("carbon", "nitrogen", "phosphorus"):
        rel = ledger.get(element, {}).get("residual_relative")
        if rel is None or not math.isfinite(rel) or abs(rel) > LEDGER_RESIDUAL_GATE:
            return False
    return True


def aggregate_phase_a(rows: list[dict]) -> dict:
    n = len(rows)
    valid_artifacts = all(not r["_missing_artifacts"] for r in rows)
    survive = [r.get("population_final", 0) > 0 for r in rows]
    max_gen5 = [((r.get("max_generation") or 0) >= 5) for r in rows]
    ledgers_ok = [_ledger_valid(r) for r in rows]
    n_survive = sum(survive)
    n_gen5 = sum(max_gen5)
    n_ledger_ok = sum(ledgers_ok)
    gate_pass = bool(
        n == 5 and valid_artifacts
        and n_survive >= 3 and n_gen5 >= 3 and n_ledger_ok == n
    )
    limiter_fracs = defaultdict(list)
    for r in rows:
        for k, v in (r.get("growth_limiter_fraction_cum") or {}).items():
            if v is not None:
                limiter_fracs[k].append(v)
    return {
        "n_runs": n,
        "seeds": sorted(int(r["seed"]) for r in rows),
        "artifacts_complete": valid_artifacts,
        "n_survive_10d": n_survive,
        "n_max_generation_ge5": n_gen5,
        "n_valid_cnp_ledger": n_ledger_ok,
        "gate_pass": gate_pass,
        "population_final": qstats([r.get("population_final") for r in rows]),
        "max_generation": qstats([r.get("max_generation") for r in rows]),
        "final_starvation_active_fraction": qstats(
            [r.get("final_starvation_active_fraction") for r in rows]),
        "h2_biological_uptake_over_source_influx": qstats(
            [r.get("h2_biological_uptake_over_source_influx") for r in rows]),
        "growth_limiter_fraction_mean": {k: float(np.mean(v)) for k, v in limiter_fracs.items()},
        "energy_ledger_residual_j_max_abs": max(
            (abs(r.get("energy_ledger_residual_j", 0.0)) for r in rows), default=None),
        "stop_reasons": dict(Counter(str(r.get("stop_reason")) for r in rows)),
    }


def aggregate_phase_b(rows: list[dict]) -> dict:
    by_condition = defaultdict(list)
    for r in rows:
        by_condition[r["condition"]].append(r)

    def mean_limiter(cond: str, key: str) -> float | None:
        vals = [r.get("growth_limiter_fraction_cum", {}).get(key)
               for r in by_condition.get(cond, [])]
        vals = [v for v in vals if v is not None]
        return float(np.mean(vals)) if vals else None

    ref_c = mean_limiter("B0_reference", "carbon")
    ref_n = mean_limiter("B0_reference", "nitrogen")
    ref_p = mean_limiter("B0_reference", "phosphorus")

    def _identity_pass(cond: str, element: str, ref_val: float | None) -> dict:
        frac = mean_limiter(cond, element)
        all_fracs = {k: mean_limiter(cond, k) for k in ALL_LIMITERS}
        comparable = [v for v in all_fracs.values() if v is not None]
        # "condition内の最大limiter" はC/N/Pだけでなく全limiterとの比較。
        # さらに全て0のtieをidentity PASSにしないためtarget > 0を要求する。
        is_max = bool(
            frac is not None
            and frac > 0.0
            and comparable
            and frac >= max(comparable)
        )
        shift_ok = (frac is not None and ref_val is not None
                   and (frac - ref_val) * 100.0 >= 20.0)
        return {
            "limiter_fraction_mean": frac,
            "reference_fraction_mean": ref_val,
            "all_limiter_fraction_mean": all_fracs,
            "is_max_limiter_in_condition": is_max,
            "shift_ge_20pp_vs_reference": shift_ok,
            "pass": bool(frac is not None and (is_max or shift_ok)),
        }

    cases = {
        "B1_low_dic": _identity_pass("B1_low_dic", "carbon", ref_c),
        "B2_low_fixed_n": _identity_pass("B2_low_fixed_n", "nitrogen", ref_n),
        "B3_low_phosphate": _identity_pass("B3_low_phosphate", "phosphorus", ref_p),
    }
    artifacts_complete = all(not r["_missing_artifacts"] for r in rows)
    n_expected = 4 * 3  # 4 conditions x 3 seeds
    gate_pass = bool(
        len(rows) == n_expected and artifacts_complete
        and all(c["pass"] for c in cases.values())
    )
    return {
        "n_runs": len(rows), "conditions": sorted(by_condition),
        "artifacts_complete": artifacts_complete,
        "reference_limiter_fraction": {"carbon": ref_c, "nitrogen": ref_n, "phosphorus": ref_p},
        "cases": cases, "gate_pass": gate_pass,
    }


def write_csv(rows: list[dict], path: Path, fields: list[str]) -> None:
    import csv
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--phase", choices=["A", "B"], required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--csv", type=Path, required=True)
    args = ap.parse_args()

    rows = load_runs(args.root, args.phase)
    if args.phase == "A":
        result = aggregate_phase_a(rows)
        fields = ["seed", "condition", "population_final", "population_max",
                  "max_generation", "stop_reason", "final_starvation_active_fraction",
                  "h2_biological_uptake_over_source_influx", "energy_ledger_residual_j"]
    else:
        result = aggregate_phase_b(rows)
        fields = ["seed", "condition", "population_final", "max_generation",
                  "stop_reason", "growth_limiter_fraction_cum"]

    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(rows, args.csv, fields)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
