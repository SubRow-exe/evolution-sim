"""Aggregate Exp17 Phase C1 finite C/N/P placement runs.

Scientific outcomes never fail the process.  Only missing/inconsistent artifacts,
ledger failure, non-zero external C/N/P exchange, or wrong condition wiring are
integrity failures.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from run_phase_c1 import CONDITIONS, condition_overrides

EXPECTED_SEEDS = (17201, 17202, 17203)
ELEMENTS = ("carbon", "nitrogen", "phosphorus")
CNP_LIMITERS = ("carbon", "nitrogen", "phosphorus")
ALL_LIMITERS = ("energy", "kinetic", "carbon", "nitrogen", "phosphorus", "room")
LEDGER_REL_TOL = 1e-6
EXTERNAL_ABS_TOL_MOL = 1e-18
CONFIG_REL_TOL = 1e-12


def _float(row: dict, key: str) -> float:
    return float(row[key])


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _median(values):
    vals = [v for v in values if v is not None]
    return statistics.median(vals) if vals else None


def _late_limiter_fractions(rows: list[dict[str, str]], window_s: float = 86400.0) -> dict[str, float | None]:
    if len(rows) < 2:
        return {k: None for k in ALL_LIMITERS}
    t_final = float(rows[-1]["time_s"])
    t_start = max(0.0, t_final - window_s)
    start = rows[0]
    for row in rows:
        if float(row["time_s"]) <= t_start:
            start = row
        else:
            break
    deltas = {}
    for k in ALL_LIMITERS:
        deltas[k] = max(0.0, float(rows[-1][k]) - float(start[k]))
    total = sum(deltas.values())
    if total <= 0.0:
        return {k: None for k in ALL_LIMITERS}
    return {k: deltas[k] / total for k in ALL_LIMITERS}


def _first_cnp_limiter_day(rows: list[dict[str, str]]) -> float | None:
    for row in rows:
        total = sum(float(row[k]) for k in CNP_LIMITERS)
        if total > 0.0:
            return float(row["time_s"]) / 86400.0
    return None


def collect_run(summary_path: Path) -> tuple[dict, list[str]]:
    errors: list[str] = []
    run_dir = summary_path.parent
    required = [
        "effective_config.json",
        "initial_genome.json",
        "summary.json",
        "timeseries.csv",
        "cnp_ledger.json",
        "growth_limiter.csv",
    ]
    for name in required:
        if not (run_dir / name).exists():
            errors.append(f"{run_dir}: missing {name}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    condition = summary.get("condition")
    seed = int(summary.get("seed"))
    if summary.get("phase") != "C1":
        errors.append(f"{run_dir}: phase != C1")
    if condition not in CONDITIONS:
        errors.append(f"{run_dir}: unknown condition {condition!r}")
        expected_eq, expected_overrides = None, None
    else:
        expected_eq, expected_overrides = condition_overrides(condition)
        if int(summary.get("biomass_equivalents", -1)) != expected_eq:
            errors.append(f"{run_dir}: biomass_equivalents mismatch")

    cfg_path = run_dir / "effective_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    if cfg:
        if cfg.get("cnp_background_exchange_enabled") is not False:
            errors.append(f"{run_dir}: CNP background exchange is not disabled")
        if expected_overrides is not None:
            for key in ("dic_background_molm3", "fixed_n_background_molm3", "phosphate_background_molm3"):
                got = float(cfg.get(key, math.nan))
                exp = float(expected_overrides[key])
                if not math.isclose(got, exp, rel_tol=CONFIG_REL_TOL, abs_tol=0.0):
                    errors.append(f"{run_dir}: {key}={got} expected={exp}")

    ledger = summary.get("cnp_ledger", {})
    ledger_valid = True
    external_zero = True
    for element in ELEMENTS:
        e = ledger.get(element, {})
        rel = e.get("residual_relative")
        if rel is None or abs(float(rel)) > LEDGER_REL_TOL:
            ledger_valid = False
            errors.append(f"{run_dir}: {element} ledger residual_relative={rel}")
        for key in ("external_in_mol", "external_out_mol"):
            v = float(e.get(key, math.inf))
            if abs(v) > EXTERNAL_ABS_TOL_MOL:
                external_zero = False
                errors.append(f"{run_dir}: {element} {key}={v} with exchange OFF")

    ts_path = run_dir / "timeseries.csv"
    gl_path = run_dir / "growth_limiter.csv"
    ts = _read_csv(ts_path) if ts_path.exists() else []
    gl = _read_csv(gl_path) if gl_path.exists() else []
    if not ts:
        errors.append(f"{run_dir}: empty timeseries.csv")
    if not gl:
        errors.append(f"{run_dir}: empty growth_limiter.csv")

    if ts:
        t0, tf = ts[0], ts[-1]
        biomass0 = _float(t0, "total_biomass_kgdw")
        biomassf = _float(tf, "total_biomass_kgdw")
        biomass_ratio = biomassf / biomass0 if biomass0 > 0 else None
        remaining = {
            "carbon": _float(tf, "dic_total_mol") / _float(t0, "dic_total_mol"),
            "nitrogen": _float(tf, "fixed_n_total_mol") / _float(t0, "fixed_n_total_mol"),
            "phosphorus": _float(tf, "phosphate_total_mol") / _float(t0, "phosphate_total_mol"),
        }
    else:
        biomass_ratio = None
        remaining = {e: None for e in ELEMENTS}

    frac = summary.get("growth_limiter_fraction_cum", {})
    combined_cnp = sum(float(frac.get(k, 0.0) or 0.0) for k in CNP_LIMITERS)
    dominant = max(ALL_LIMITERS, key=lambda k: float(frac.get(k, 0.0) or 0.0))
    late = _late_limiter_fractions(gl) if gl else {k: None for k in ALL_LIMITERS}
    late_combined_cnp = (
        sum(float(late[k] or 0.0) for k in CNP_LIMITERS)
        if any(late[k] is not None for k in ALL_LIMITERS)
        else None
    )
    first_cnp_day = _first_cnp_limiter_day(gl) if gl else None

    row = {
        "seed": seed,
        "condition": condition,
        "biomass_equivalents": summary.get("biomass_equivalents"),
        "days_completed": summary.get("days_completed"),
        "stop_reason": summary.get("stop_reason"),
        "population_final": summary.get("population_final"),
        "population_max": summary.get("population_max"),
        "max_generation": summary.get("max_generation"),
        "biomass_final_over_initial": biomass_ratio,
        "first_cnp_limiter_day": first_cnp_day,
        "combined_cnp_limiter_fraction_cum": combined_cnp,
        "late24h_combined_cnp_limiter_fraction": late_combined_cnp,
        "dominant_limiter_cum": dominant,
        "carbon_remaining_fraction": remaining["carbon"],
        "nitrogen_remaining_fraction": remaining["nitrogen"],
        "phosphorus_remaining_fraction": remaining["phosphorus"],
        "ledger_valid": ledger_valid,
        "external_exchange_zero": external_zero,
    }
    return row, errors


def aggregate(root: Path) -> tuple[dict, list[dict], list[str]]:
    errors: list[str] = []
    rows: list[dict] = []
    for p in sorted(root.rglob("summary.json")):
        try:
            row, errs = collect_run(p)
            rows.append(row)
            errors.extend(errs)
        except Exception as exc:  # integrity report should preserve all other runs
            errors.append(f"{p}: {type(exc).__name__}: {exc}")

    expected = {(c, s) for c in CONDITIONS for s in EXPECTED_SEEDS}
    actual = {(r["condition"], int(r["seed"])) for r in rows}
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        errors.append(f"missing run keys: {missing}")
    if unexpected:
        errors.append(f"unexpected run keys: {unexpected}")
    if len(actual) != len(rows):
        errors.append("duplicate run key detected")

    per_condition = {}
    for condition, equivalents in CONDITIONS.items():
        rr = [r for r in rows if r["condition"] == condition]
        per_condition[condition] = {
            "biomass_equivalents": equivalents,
            "n_runs": len(rr),
            "seeds": sorted(int(r["seed"]) for r in rr),
            "population_final_median": _median([float(r["population_final"]) for r in rr]),
            "max_generation_median": _median([float(r["max_generation"]) for r in rr]),
            "biomass_final_over_initial_median": _median([r["biomass_final_over_initial"] for r in rr]),
            "first_cnp_limiter_day_median": _median([r["first_cnp_limiter_day"] for r in rr]),
            "combined_cnp_limiter_fraction_cum_median": _median([r["combined_cnp_limiter_fraction_cum"] for r in rr]),
            "late24h_combined_cnp_limiter_fraction_median": _median([r["late24h_combined_cnp_limiter_fraction"] for r in rr]),
            "carbon_remaining_fraction_median": _median([r["carbon_remaining_fraction"] for r in rr]),
            "nitrogen_remaining_fraction_median": _median([r["nitrogen_remaining_fraction"] for r in rr]),
            "phosphorus_remaining_fraction_median": _median([r["phosphorus_remaining_fraction"] for r in rr]),
            "dominant_limiter_counts": dict(Counter(r["dominant_limiter_cum"] for r in rr)),
            "stop_reason_counts": dict(Counter(r["stop_reason"] for r in rr)),
            "n_runs_with_any_cnp_limiter": sum(r["first_cnp_limiter_day"] is not None for r in rr),
        }

    out = {
        "experiment": "Exp17 Phase C1 C/N/P placement calibration",
        "expected_runs": len(expected),
        "n_runs": len(rows),
        "integrity_pass": not errors,
        "integrity_errors": errors,
        "scientific_note": "diagnostic only; no V1.10 default is auto-selected",
        "per_condition": per_condition,
    }
    return out, rows, errors


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("phaseC1_aggregate.json"))
    p.add_argument("--csv", type=Path, default=Path("phaseC1_aggregate.csv"))
    args = p.parse_args()

    result, rows, errors = aggregate(args.root)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_csv(args.csv, rows)
    print(json.dumps(result, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
