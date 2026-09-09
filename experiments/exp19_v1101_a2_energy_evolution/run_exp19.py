"""Exp19 V1.10.1 — A2 vent-turnover Energy戦略進化 CLI.

正本: docs/Exp19_A2環境_Energy戦略進化_実験計画.md。

Exp18のPhase B harness (run_exp18_phase_b.py) を直接再利用する。Exp19の
E0-E3 armはExp18のB0-B3 armと定義が同一で、DYNAMIC armのdynamic_conditionを
"A2" (48hごとに1 ventをrelocate) へ固定する点だけがExp19固有 (docs §5, §13)。

Exp18のformal artifact / preregistrationはこのモジュールから一切変更しない。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exp18_v1101_dynamic_vent"))
import run_exp18  # noqa: E402
import run_exp18_phase_b as phase_b  # noqa: E402

# Exp19 §5.1: E0/E1 = static, E2/E3 = A2_DYNAMIC。Exp18のARM名をそのまま使う。
ARM_TO_EXP18 = {
    "E0_STATIC_FIXED": "B0_STATIC_FIXED",
    "E1_STATIC_EVOLVE": "B1_STATIC_EVOLVE",
    "E2_A2_DYNAMIC_FIXED": "B2_DYNAMIC_FIXED",
    "E3_A2_DYNAMIC_EVOLVE": "B3_DYNAMIC_EVOLVE",
}
DYNAMIC_CONDITION = "A2"  # docs §5.1: 48hごとに1 ventをrelocate、固定
SEEDS = (19001, 19002, 19003)
DAYS = 10.0


def run_arm(arm: str, seed: int, outdir: Path, calibration_dir: Path,
           days: float = DAYS, write_snapshots: bool = True) -> dict:
    if arm not in ARM_TO_EXP18:
        raise ValueError(f"unknown Exp19 arm: {arm} (candidates: {sorted(ARM_TO_EXP18)})")
    exp18_arm = ARM_TO_EXP18[arm]
    spec = phase_b.ARMS[exp18_arm]
    dyn_cond = DYNAMIC_CONDITION if spec["dynamic"] else None

    f0, h2_field = run_exp18.load_calibration(calibration_dir)
    summary = phase_b.run_phase_b(exp18_arm, dyn_cond, seed, outdir, f0, h2_field,
                                  days=days, write_snapshots=write_snapshots)
    summary["experiment"] = "Exp19 V1.10.1 A2 vent-turnover Energy strategy evolution"
    summary["exp19_arm"] = arm
    summary["exp18_arm_reused"] = exp18_arm
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--arm", choices=sorted(ARM_TO_EXP18), required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--days", type=float, default=DAYS)
    p.add_argument("--calibration-dir", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--no-snapshots", action="store_true")
    args = p.parse_args()

    summary = run_arm(args.arm, args.seed, args.outdir, args.calibration_dir,
                      days=args.days, write_snapshots=not args.no_snapshots)
    print(json.dumps({k: v for k, v in summary.items() if k != "cnp_ledger"}, indent=2))


if __name__ == "__main__":
    main()
