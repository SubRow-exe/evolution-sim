"""Exp20 V1.11 primitive phototrophy seeded invasion — formal run CLI.

正本: docs/Exp20_V1.11_PrimitivePhototrophy_SeededInvasion_実験計画.md §7/13。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exp18_v1101_dynamic_vent"))
import exp20_core as core  # noqa: E402
import run_exp18  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--environment", choices=sorted(core.ENVIRONMENTS), required=True)
    p.add_argument("--frequency", type=float, required=True,
                   help="t=0 phototroph founder frequency (0 / 0.01 / 0.10 / 0.50)")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--days", type=float, default=core.DURATION_DAYS)
    p.add_argument("--calibration-dir", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    args = p.parse_args()

    f0, h2_field = run_exp18.load_calibration(args.calibration_dir)
    # rev2/Exp20 §3.1: formal LUCA baseline h2_usable_energy_j_per_mol は
    # Config class default (3750) ではなく2407.5でなければならない
    # (T20-11)。exp18_core.base_config() -> luca_proxy経由で既にこの値の
    # はずだが、silent fallbackしていないことを明示的にassertする。
    cfg = core.make_cfg(f0, args.environment)
    assert cfg.h2_usable_energy_j_per_mol == 2407.5, (
        f"formal LUCA baseline違反: h2_usable_energy_j_per_mol={cfg.h2_usable_energy_j_per_mol} "
        "(2407.5でなければならない。Config class default 3750を使っていないか確認)。")

    summary = core.run(cfg, args.seed, args.frequency, args.environment,
                       args.outdir, h2_field, days=args.days)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
