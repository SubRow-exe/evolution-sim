"""Exp12 の各runの最初の10,000 tickをExp11参照データと比較する
(docs/Exp12_実験計画確定.md §6, §5 P0-3)。

使い方:
    uv run python tools/compare_exp12_first10k.py runs/exp12 runs/exp11_ref

runs/exp12・runs/exp11_ref はそれぞれ `<条件key>/<seed run dir>/config.json`
の2階層構造 (Exp11/Exp12 collect stepの実際の展開形式) を想定する。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.check_exp12 import collect_run_dirs, compare_first_10k
from tools.exp12_common import infer_env, round_bmr_any


def build_seed_index(base: Path) -> dict[tuple[str, float, int], Path]:
    idx: dict[tuple[str, float, int], Path] = {}
    for run_dir in collect_run_dirs(base):
        try:
            cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
            meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
            env = infer_env(cfg)
            core = round_bmr_any(cfg.get("bmr_core", 0.0))
            seed = meta.get("seed")
        except Exception:
            continue
        if seed is not None:
            idx[(env, core, seed)] = run_dir
    return idx


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Exp12 first-10k Exp11参照比較")
    ap.add_argument("exp12_base", type=Path)
    ap.add_argument("exp11_base", type=Path)
    args = ap.parse_args()

    exp12_idx = build_seed_index(args.exp12_base)
    exp11_idx = build_seed_index(args.exp11_base)

    if not exp12_idx:
        print(f"ERROR: {args.exp12_base} からExp12 runが見つからない", file=sys.stderr)
        return 1

    errors: list[str] = []
    mismatched_runs = 0
    for key, exp12_dir in sorted(exp12_idx.items()):
        exp11_dir = exp11_idx.get(key)
        if exp11_dir is None:
            errors.append(f"{key}: Exp11参照runが見つからない (first-10k reference欠落)")
            continue
        errs = compare_first_10k(exp12_dir, exp11_dir)
        if errs:
            mismatched_runs += 1
            errors.append(f"{key}: INTEGRITY_FAIL (first-10k不一致)")
            errors.extend(f"    {e}" for e in errs[:10])

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        if mismatched_runs >= 3:
            print(
                f"::error::複数run ({mismatched_runs}件) でfirst-10k不一致。"
                "系統的な原因の可能性があるため停止して原因調査すること。",
                file=sys.stderr,
            )
        return 1

    print(f"OK: {len(exp12_idx)} run すべてでfirst-10kがExp11参照と完全一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
