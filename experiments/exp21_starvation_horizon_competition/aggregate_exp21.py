"""Exp21集計 (docs/Exp21_実験計画.md §8/§12)。

primary endpoint f_long の時系列を8 seeds分集計し、A0 vs A2の比較を機械的に
出す。「強い支持/弱い/不確定」の判定基準(§12)は事前登録された条件をそのまま
数値で報告するだけで、Exp21自身が結果を見てPASS/FAILへ丸めることはしない
(判断は人間/次工程に委ねる)。missing runはsilent skipせずincompleteとして
記録する。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

REQUIRED_ARTIFACTS = ("effective_config.json", "summary.json", "lineage_timeseries.csv")
ENVIRONMENTS = ("A0_STATIC", "A2_DYNAMIC_VENT")
SEEDS = (21001, 21002, 21003, 21004, 21005, 21006, 21007, 21008)
ENDPOINTS_H = (0, 12, 24, 48, 72, 96, 120)


def load_runs(root: Path) -> list[dict]:
    rows = []
    for summary_path in sorted(root.rglob("summary.json")):
        run_dir = summary_path.parent
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        if s.get("experiment") != "Exp21 starvation_horizon direct competition":
            continue
        missing = [a for a in REQUIRED_ARTIFACTS if not (run_dir / a).exists()]
        s["_path"] = str(run_dir)
        s["_missing_artifacts"] = missing
        rows.append(s)
    return rows


def _read_timeseries(run_dir: Path) -> list[dict]:
    path = run_dir / "lineage_timeseries.csv"
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def f_long_at_endpoints(run_dir: Path) -> dict:
    rows = _read_timeseries(run_dir)
    out = {}
    for h in ENDPOINTS_H:
        target_s = h * 3600.0
        best = min(rows, key=lambda r: abs(float(r["time_s"]) - target_s))
        val = best.get("f_long")
        out[f"h{h}"] = float(val) if val not in (None, "") else None
    return out


def qstats(values) -> dict:
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not vals:
        return {"mean": None, "median": None, "min": None, "max": None, "n": 0}
    a = np.asarray(vals)
    return {"mean": float(a.mean()), "median": float(np.median(a)),
           "min": float(a.min()), "max": float(a.max()), "n": len(vals)}


def aggregate(rows: list[dict]) -> dict:
    by_env = defaultdict(list)
    for r in rows:
        by_env[r["environment"]].append(r)

    n_expected = len(ENVIRONMENTS) * len(SEEDS)
    artifacts_complete = len(rows) == n_expected and all(
        not r["_missing_artifacts"] for r in rows)

    by_env_summary = {}
    for env, group in by_env.items():
        f_long_by_seed = {}
        fixation = {"long": 0, "baseline": 0, "none": 0}
        for r in group:
            f_long_by_seed[r["seed"]] = f_long_at_endpoints(Path(r["_path"]))
            fixed = r.get("summary", {}).get("fixed_lineage")
            fixation[fixed if fixed in ("long", "baseline") else "none"] += 1
        h120_values = [v["h120"] for v in f_long_by_seed.values()]
        by_env_summary[env] = {
            "n_seeds": len(group),
            "f_long_by_seed": f_long_by_seed,
            "f_long_h120": qstats(h120_values),
            "n_seeds_f_long_h120_gt_half": sum(1 for v in h120_values if v is not None and v > 0.5),
            "fixation_counts": fixation,
        }

    comparison = None
    if "A0_STATIC" in by_env_summary and "A2_DYNAMIC_VENT" in by_env_summary:
        a0 = by_env_summary["A0_STATIC"]["f_long_h120"]["median"]
        a2 = by_env_summary["A2_DYNAMIC_VENT"]["f_long_h120"]["median"]
        comparison = {
            "median_f_long_h120_A0": a0,
            "median_f_long_h120_A2": a2,
            "median_difference_A2_minus_A0": (
                (a2 - a0) if a0 is not None and a2 is not None else None),
        }

    return {
        "n_runs": len(rows),
        "n_expected": n_expected,
        "artifacts_complete": artifacts_complete,
        "by_environment": by_env_summary,
        "comparison_A2_vs_A0_at_120h": comparison,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    rows = load_runs(args.root)
    result = aggregate(rows)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
