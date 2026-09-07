"""Exp17 V1.10 C/N/P — Phase A / Phase B formal run CLI.

正本: docs/Exp17_V1.10_CNP資源分解_実験計画.md §3-4。

Phase A: reference open environment (5 seeds x 10 physical days)
Phase B: resource identity validation (B0-B3, 3 seeds x 3 physical days each)

Phase B conditionはPhase A referenceから **1 resourceだけ** 変更する
(§4)。他は一切変更しない。formal開始後はreference parameterを結果を見て
調整しない (HARD RULE)。
"""
from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

# Phase B: Phase A referenceから1 resourceだけ x0.01 (docs §4)
PHASE_B_CONDITIONS = {
    "B0_reference": {},
    "B1_low_dic": {"dic_background_molm3": core.CNP_REFERENCE["dic_background_molm3"] * 0.01},
    "B2_low_fixed_n": {"fixed_n_background_molm3":
                       core.CNP_REFERENCE["fixed_n_background_molm3"] * 0.01},
    "B3_low_phosphate": {"phosphate_background_molm3":
                         core.CNP_REFERENCE["phosphate_background_molm3"] * 0.01},
}


def run_phase_a(seed: int, outdir: Path, days: float = 10.0) -> dict:
    summary = core.run(seed, outdir, days)
    summary["phase"] = "A"
    summary["condition"] = "reference"
    _rewrite_summary(outdir, summary)
    return summary


def run_phase_b(condition: str, seed: int, outdir: Path, days: float = 3.0) -> dict:
    if condition not in PHASE_B_CONDITIONS:
        raise ValueError(f"unknown Phase B condition: {condition} "
                         f"(candidates: {sorted(PHASE_B_CONDITIONS)})")
    overrides = PHASE_B_CONDITIONS[condition]
    old_make_cfg = core.make_cfg

    def _condition_make_cfg(**kw):
        cfg = old_make_cfg(**kw)
        if overrides:
            cfg = dataclasses.replace(cfg, **overrides)
        return cfg

    core.make_cfg = _condition_make_cfg
    try:
        summary = core.run(seed, outdir, days, write_snapshots=False)
    finally:
        core.make_cfg = old_make_cfg
    summary["phase"] = "B"
    summary["condition"] = condition
    summary["condition_overrides"] = overrides
    _rewrite_summary(outdir, summary)
    return summary


def _rewrite_summary(outdir: Path, summary: dict) -> None:
    import json
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["A", "B"], required=True)
    p.add_argument("--condition", choices=sorted(PHASE_B_CONDITIONS), default="B0_reference",
                  help="Phase B only")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--days", type=float, default=None)
    p.add_argument("--outdir", type=Path, required=True)
    args = p.parse_args()

    if args.phase == "A":
        days = args.days if args.days is not None else 10.0
        summary = run_phase_a(args.seed, args.outdir, days)
    else:
        days = args.days if args.days is not None else 3.0
        summary = run_phase_b(args.condition, args.seed, args.outdir, days)

    import json
    print(json.dumps({k: v for k, v in summary.items() if k != "cnp_ledger"}, indent=2))


if __name__ == "__main__":
    main()
