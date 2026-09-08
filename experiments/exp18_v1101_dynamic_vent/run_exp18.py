"""Exp18 V1.10.1 — Phase A fixed-iLUCA environmental comparison CLI.

正本: docs/Exp18_V1.10.1_動的熱水噴出口_実験計画.md §1/3。

A0 static finite flux control
A1 temporal fluctuation only
A2 spatial turnover only
A3 temporal + spatial turnover

全条件で世界全体の瞬間/積算総fluxをA0と揃える (F0 x n_ventsは共通)。
F0とt=0 common H2 fieldはPhase 0 (phase0.py) の成果物を再利用する
(§7: warm-up中のsource入出力はformal ledgerに含めない)。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp18_core as core  # noqa: E402

CONDITIONS = {
    "A0": dict(temporal=False, turnover=False),
    "A1": dict(temporal=True, turnover=False),
    "A2": dict(temporal=False, turnover=True),
    "A3": dict(temporal=True, turnover=True),
}

TURNOVER_KW = dict(h2_vent_turnover_interval_s=172800.0, h2_vent_min_separation_cells=4)


def load_calibration(calibration_dir: Path) -> tuple[float, np.ndarray]:
    """Phase 0 (phase0.py) が保存したF0とt=0 common H2 fieldを読む。"""
    f0_data = json.loads((calibration_dir / "f0_calibration.json").read_text(encoding="utf-8"))
    h2_field = np.load(calibration_dir / "common_initial_h2_field.npy")
    return float(f0_data["f0_mol_s"]), h2_field


def run_phase_a(condition: str, seed: int, outdir: Path, f0: float,
                h2_field: np.ndarray, days: float = 10.0,
                write_snapshots: bool = True) -> dict:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown Phase A condition: {condition} "
                         f"(candidates: {sorted(CONDITIONS)})")
    kw = dict(CONDITIONS[condition])
    if kw["turnover"]:
        kw = {**kw, **TURNOVER_KW}
    cfg = core.make_flux_cfg(f0, **kw)
    summary = core.run(cfg, seed, outdir, days, initial_h2_field=h2_field,
                       write_snapshots=write_snapshots)
    summary["phase"] = "A"
    summary["condition"] = condition
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--days", type=float, default=10.0)
    p.add_argument("--calibration-dir", type=Path, required=True,
                   help="phase0.py の出力directory (f0_calibration.json / common_initial_h2_field.npy)")
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--no-snapshots", action="store_true")
    args = p.parse_args()

    f0, h2_field = load_calibration(args.calibration_dir)
    summary = run_phase_a(args.condition, args.seed, args.outdir, f0, h2_field,
                          args.days, write_snapshots=not args.no_snapshots)
    print(json.dumps({k: v for k, v in summary.items() if k != "cnp_ledger"}, indent=2))


if __name__ == "__main__":
    main()
