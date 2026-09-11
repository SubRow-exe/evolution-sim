"""Exp21 formal-run前の必須gate (docs/Exp21_実験計画.md §11 G1-G10)。

どれか1つでも失敗した場合はformal runを開始しない。全environment x
seedの組合せを事前に検証する (Exp20 Attempt2のpreflight_initial_state.py
と同じ思想: 1組でも失敗すればexit非0でCIをfailさせる)。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_exp21 as core  # noqa: E402


def check_one(f0, h2_field, environment: str, seed: int) -> dict:
    cfg = core.make_cfg(f0, environment)
    core.validate_effective_config(cfg, environment)  # G1-G5

    sim = core.exp18_core.setup_sim(cfg, seed, h2_field)
    rng_before = sim.rng.bit_generator.state
    long_ids = core.assign_lineages(sim, seed)
    rng_after = sim.rng.bit_generator.state

    n_total = len(sim.organisms)
    n_long = len(long_ids)
    checks = {
        "G6_population_100_5050": n_total == 100 and n_long == 50,
        "G7_genome_identical_except_trait": core.genomes_identical_except_starv_horizon(sim, long_ids),
        "G9_lineage_rng_isolated": rng_before == rng_after,
    }
    checks["all_pass"] = all(checks.values())
    return {"environment": environment, "seed": seed, **checks}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibration-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    f0, h2_field = core.load_calibration(args.calibration_dir)
    results = [check_one(f0, h2_field, env, seed)
              for env in core.ENVIRONMENTS for seed in core.SEEDS]
    all_pass = all(r["all_pass"] for r in results)
    out = {"n_checked": len(results), "all_pass": all_pass, "results": results}
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"n_checked": len(results), "all_pass": all_pass}, indent=2))
    if not all_pass:
        failing = [r for r in results if not r["all_pass"]]
        raise SystemExit(f"Exp21 preflight FAILED for {len(failing)} combination(s): {failing}")
    print("EXP21_PREFLIGHT_PASS")


if __name__ == "__main__":
    main()
