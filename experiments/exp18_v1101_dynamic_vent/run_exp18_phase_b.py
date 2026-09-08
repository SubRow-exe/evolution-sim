"""Exp18 V1.10.1 — Phase B evolution test CLI (build-only; NOT auto-dispatched).

正本: docs/Exp18_V1.10.1_動的熱水噴出口_実験計画.md §6-8。

2 x 2 design:
    Environment: STATIC / DYNAMIC
    Genetics:    FIXED  / EVOLVE

進化対象は storage_capacity / starvation_horizon / reproduction_horizon の
3 genesのみ。他のcontinuous genesは全て固定。initial jitterはExp15
evolution armと同じorder (0.02) を使い、Exp18結果を見て調整しない。

DYNAMIC armの具体的条件 (temporal/turnover) は、Phase Aの
`aggregate_phase_a.select_dynamic_arm()` が選んだ条件 (A1/A2/A3) を
`--dynamic-condition` で明示的に渡す。Phase Aがどの条件も選ばなかった
場合、Phase Bは実行しない (docs §5)。

このスクリプトはharnessとして用意するだけで、formal dispatch (workflow)
は別途human/Claudeの判断を経てから追加する。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp18_core as core  # noqa: E402
import run_exp18  # noqa: E402

EVOLVE_GENES = ("storage_capacity", "starvation_horizon", "reproduction_horizon")
EVOLUTION_INITIAL_JITTER_SIGMA = 0.02  # Exp15 evolution armと同order (docs §6)

ARMS = {
    "B0_STATIC_FIXED": dict(dynamic=False, evolve=False),
    "B1_STATIC_EVOLVE": dict(dynamic=False, evolve=True),
    "B2_DYNAMIC_FIXED": dict(dynamic=True, evolve=False),
    "B3_DYNAMIC_EVOLVE": dict(dynamic=True, evolve=True),
}


def run_phase_b(arm: str, dynamic_condition: str, seed: int, outdir: Path,
                f0: float, h2_field: np.ndarray, days: float = 20.0,
                write_snapshots: bool = True) -> dict:
    if arm not in ARMS:
        raise ValueError(f"unknown Phase B arm: {arm} (candidates: {sorted(ARMS)})")
    spec = ARMS[arm]

    if spec["dynamic"]:
        if dynamic_condition not in ("A1", "A2", "A3"):
            raise ValueError(
                "DYNAMIC armには --dynamic-condition (A1|A2|A3, Phase Aの"
                "select_dynamic_arm結果) が必要です。")
        env_kw = dict(run_exp18.CONDITIONS[dynamic_condition])
        if env_kw["turnover"]:
            env_kw = {**env_kw, **run_exp18.TURNOVER_KW}
    else:
        env_kw = dict(run_exp18.CONDITIONS["A0"])  # static finite flux control

    evolve_genes = EVOLVE_GENES if spec["evolve"] else ()
    jitter = EVOLUTION_INITIAL_JITTER_SIGMA if spec["evolve"] else 0.0

    cfg = core.make_flux_cfg(f0, evolve_genes=evolve_genes,
                             initial_jitter_sigma=jitter, **env_kw)
    summary = core.run(cfg, seed, outdir, days, initial_h2_field=h2_field,
                       write_snapshots=write_snapshots)
    summary["phase"] = "B"
    summary["arm"] = arm
    summary["environment"] = "DYNAMIC" if spec["dynamic"] else "STATIC"
    summary["genetics"] = "EVOLVE" if spec["evolve"] else "FIXED"
    summary["dynamic_condition"] = dynamic_condition if spec["dynamic"] else None
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--arm", choices=sorted(ARMS), required=True)
    p.add_argument("--dynamic-condition", choices=["A1", "A2", "A3"], default=None,
                   help="DYNAMIC arm用。Phase Aのselect_dynamic_arm結果を渡す。")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--days", type=float, default=20.0)
    p.add_argument("--calibration-dir", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--no-snapshots", action="store_true")
    args = p.parse_args()

    f0, h2_field = run_exp18.load_calibration(args.calibration_dir)
    summary = run_phase_b(args.arm, args.dynamic_condition, args.seed, args.outdir,
                          f0, h2_field, args.days, write_snapshots=not args.no_snapshots)
    print(json.dumps({k: v for k, v in summary.items() if k != "cnp_ledger"}, indent=2))


if __name__ == "__main__":
    main()
