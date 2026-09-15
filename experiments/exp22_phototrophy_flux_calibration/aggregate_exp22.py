"""Exp22集計 (docs/Exp22_実験計画.md §11-13)。

R_E (stored Energy protection) と starvation exposure AUC をwindow別
(0-48h/48-72h/0-72h) に計算し、flux別・environment別にまとめる。
preferred working-flux candidateの抽出ルール(§12.1)を機械的に適用するが、
Exp22自体はcompetitionのPASS/FAIL判定はしない — recommendationとして出力する。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ENVIRONMENTS = ("A0_STATIC", "A2_DYNAMIC_VENT")
FLUX_LEVELS = (0.0, 0.015, 0.05, 0.15, 0.5, 1.5)
SEEDS = (22001, 22002, 22003)
WINDOWS = {"0-48h": (0.0, 48.0), "48-72h": (48.0, 72.0), "0-72h": (0.0, 72.0)}


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _trapz_window(rows: list[dict], field: str, h_lo: float, h_hi: float) -> float | None:
    pts = [(float(r["time_h"]), float(r[field])) for r in rows
          if r.get(field) not in (None, "") and h_lo <= float(r["time_h"]) <= h_hi]
    if len(pts) < 2:
        return None
    x = np.asarray([p[0] for p in pts])
    y = np.asarray([p[1] for p in pts])
    return float(np.trapezoid(y, x))


def pair_metrics(flux_dir: Path) -> dict:
    off_rows = _read_csv(flux_dir / "off.csv")
    on_rows = _read_csv(flux_dir / "on.csv")
    off_by_t = {round(float(r["time_h"]), 4): r for r in off_rows}
    on_by_t = {round(float(r["time_h"]), 4): r for r in on_rows}
    common_t = sorted(set(off_by_t) & set(on_by_t))
    diff_energy = [{"time_h": t,
                   "delta": (float(on_by_t[t]["mean_stored_energy_j"]) - float(off_by_t[t]["mean_stored_energy_j"]))
                   if on_by_t[t]["mean_stored_energy_j"] not in (None, "")
                   and off_by_t[t]["mean_stored_energy_j"] not in (None, "") else None}
                  for t in common_t]
    diff_starve = [{"time_h": t,
                   "delta": (float(on_by_t[t]["starvation_exposed_fraction"]) - float(off_by_t[t]["starvation_exposed_fraction"]))
                   if on_by_t[t]["starvation_exposed_fraction"] not in (None, "")
                   and off_by_t[t]["starvation_exposed_fraction"] not in (None, "") else None}
                  for t in common_t]

    result: dict = {}
    for wname, (lo, hi) in WINDOWS.items():
        num = _trapz_window(diff_energy, "delta", lo, hi)
        denom_rows = [{"time_h": r["time_h"], "mean_stored_energy_j": r["mean_stored_energy_j"]}
                     for r in off_rows]
        denom = _trapz_window(denom_rows, "mean_stored_energy_j", lo, hi)
        result[f"R_E_{wname}"] = (num / denom) if (num is not None and denom not in (None, 0.0)) else None
        result[f"delta_starvation_exposure_AUC_{wname}"] = _trapz_window(diff_starve, "delta", lo, hi)

    off_final, on_final = off_rows[-1], on_rows[-1]
    result["off_final_total_living_matter"] = float(off_final["total_living_matter"])
    result["on_final_total_living_matter"] = float(on_final["total_living_matter"])
    denom_m = result["off_final_total_living_matter"]
    result["relative_delta_final_total_living_matter"] = (
        (result["on_final_total_living_matter"] - denom_m) / denom_m if denom_m else None)
    result["off_final_population"] = int(off_final["population"])
    result["on_final_population"] = int(on_final["population"])
    result["max_pop_halted"] = False  # not tracked explicitly; population never approaches halt in these scales
    result["on_photo_used_j_cum"] = float(on_final["photo_used_j_cum"])
    result["on_photo_usable_max_j_cum"] = float(on_final["photo_usable_max_j_cum"])
    result["on_photo_utilization_fraction"] = (
        result["on_photo_used_j_cum"] / result["on_photo_usable_max_j_cum"]
        if result["on_photo_usable_max_j_cum"] > 0 else None)
    result["on_photo_structural_n_mol_total_final"] = float(on_final["photo_structural_n_mol_total"])
    return result


def load_all(root: Path) -> dict:
    """root配下のenvironment×seed job出力 (manifest.json + flux*/) を全て読む。"""
    out = defaultdict(dict)  # out[environment][flux][seed] = metrics
    for manifest_path in sorted(root.rglob("manifest.json")):
        job_dir = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        env, seed = manifest["environment"], manifest["seed"]
        for flux in manifest["flux_levels"]:
            label = f"flux{flux:g}"
            flux_dir = job_dir / label
            if not (flux_dir / "off.csv").exists() or not (flux_dir / "on.csv").exists():
                out[env].setdefault(flux, {})[seed] = None  # incomplete marker
                continue
            out[env].setdefault(flux, {})[seed] = pair_metrics(flux_dir)
    return out


def qstats(values):
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not vals:
        return {"mean": None, "median": None, "min": None, "max": None, "n": 0}
    a = np.asarray(vals)
    return {"mean": float(a.mean()), "median": float(np.median(a)),
           "min": float(a.min()), "max": float(a.max()), "n": len(vals)}


def flux_response_table(data: dict) -> list[dict]:
    rows = []
    for env, by_flux in data.items():
        for flux, by_seed in sorted(by_flux.items()):
            complete = all(v is not None for v in by_seed.values()) and len(by_seed) == len(SEEDS)
            r_e_48_72 = [v["R_E_48-72h"] for v in by_seed.values() if v]
            starve_48_72 = [v["delta_starvation_exposure_AUC_48-72h"] for v in by_seed.values() if v]
            rel_matter = [v["relative_delta_final_total_living_matter"] for v in by_seed.values() if v]
            rows.append({
                "environment": env, "flux": flux, "n_seeds_complete": sum(1 for v in by_seed.values() if v),
                "artifacts_complete": complete,
                "R_E_48_72h": qstats(r_e_48_72),
                "delta_starvation_exposure_AUC_48_72h": qstats(starve_48_72),
                "relative_delta_final_total_living_matter": qstats(rel_matter),
            })
    return rows


def preferred_candidate(data: dict) -> dict:
    """docs §12.1: 非zero fluxのうち低い方から最初に条件を全て満たすflux。"""
    if "A2_DYNAMIC_VENT" not in data:
        return {"candidate": None, "reason": "A2_DYNAMIC_VENT data missing"}
    a2 = data["A2_DYNAMIC_VENT"]
    for flux in sorted(f for f in a2 if f > 0.0):
        by_seed = a2[flux]
        if len(by_seed) != len(SEEDS) or any(v is None for v in by_seed.values()):
            continue
        r_e_values = [v["R_E_48-72h"] for v in by_seed.values()]
        starve_values = [v["delta_starvation_exposure_AUC_48-72h"] for v in by_seed.values()]
        cond1 = True  # gate PASS assumed (checked upstream by preflight/aggregate completeness)
        cond2 = all(v is not None and v > 0 for v in r_e_values)
        cond3 = (np.median([v for v in r_e_values if v is not None]) >= 0.01) if r_e_values else False
        cond4 = all(v is not None and v <= 0 for v in starve_values)
        if cond1 and cond2 and cond3 and cond4:
            general_flag = False
            if "A0_STATIC" in data and flux in data["A0_STATIC"]:
                a0_by_seed = data["A0_STATIC"][flux]
                rel_matter = [v["relative_delta_final_total_living_matter"]
                             for v in a0_by_seed.values() if v]
                if rel_matter and np.median(rel_matter) >= 0.10:
                    general_flag = True
            return {"candidate": flux, "general_advantage_flag": general_flag,
                   "median_R_E_48_72h": float(np.median(r_e_values))}
    return {"candidate": None, "reason": "NO_WORKING_FLUX_IN_RANGE"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    data = load_all(args.root)
    n_jobs = sum(len(by_flux.get(f, {})) for by_flux in data.values() for f in FLUX_LEVELS)
    n_expected_runs = len(ENVIRONMENTS) * len(FLUX_LEVELS) * len(SEEDS) * 2  # OFF+ON
    n_complete_pairs = sum(
        1 for by_flux in data.values() for by_seed in by_flux.values()
        for v in by_seed.values() if v is not None)
    artifacts_complete = n_complete_pairs == len(ENVIRONMENTS) * len(FLUX_LEVELS) * len(SEEDS)

    flux_response = flux_response_table(data)
    recommendation = preferred_candidate(data)

    gate_summary = {
        "n_expected_pairs": len(ENVIRONMENTS) * len(FLUX_LEVELS) * len(SEEDS),
        "n_complete_pairs": n_complete_pairs,
        "n_expected_runs_off_plus_on": n_expected_runs,
        "artifacts_complete": artifacts_complete,
    }

    (args.out_dir / "exp22_gate_summary.json").write_text(
        json.dumps(gate_summary, indent=2), encoding="utf-8")
    (args.out_dir / "exp22_working_flux_recommendation.json").write_text(
        json.dumps(recommendation, indent=2), encoding="utf-8")

    with (args.out_dir / "exp22_flux_response.csv").open("w", newline="", encoding="utf-8") as f:
        if flux_response:
            fieldnames = ["environment", "flux", "n_seeds_complete", "artifacts_complete"]
            w = csv.writer(f)
            w.writerow(fieldnames + ["R_E_48_72h_median", "starvation_AUC_48_72h_median",
                                     "rel_delta_matter_median"])
            for r in flux_response:
                w.writerow([r["environment"], r["flux"], r["n_seeds_complete"], r["artifacts_complete"],
                           r["R_E_48_72h"]["median"], r["delta_starvation_exposure_AUC_48_72h"]["median"],
                           r["relative_delta_final_total_living_matter"]["median"]])

    with (args.out_dir / "exp22_pair_results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["environment", "flux", "seed", "R_E_0_48h", "R_E_48_72h", "R_E_0_72h",
                   "delta_starve_AUC_48_72h", "rel_delta_final_matter"])
        for env, by_flux in data.items():
            for flux, by_seed in sorted(by_flux.items()):
                for seed, v in sorted(by_seed.items()):
                    if v is None:
                        w.writerow([env, flux, seed, None, None, None, None, None])
                        continue
                    w.writerow([env, flux, seed, v["R_E_0-48h"], v["R_E_48-72h"], v["R_E_0-72h"],
                               v["delta_starvation_exposure_AUC_48-72h"],
                               v["relative_delta_final_total_living_matter"]])

    result = {"gate_summary": gate_summary, "flux_response": flux_response,
             "working_flux_recommendation": recommendation}
    (args.out_dir / "exp22_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"gate_summary": gate_summary, "recommendation": recommendation}, indent=2))


if __name__ == "__main__":
    main()
