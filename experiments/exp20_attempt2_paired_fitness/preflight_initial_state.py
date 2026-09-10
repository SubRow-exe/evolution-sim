"""Exhaustive t=0 state gate for Exp20 Attempt 2.

Checks every formal environment/seed/trait/factor combination before any 72 h
formal run is dispatched.  Exogenous initial conditions must match baseline;
the intended gene and physiology derived from that gene may differ.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import attempt2_init_fix
import run_attempt2 as core

attempt2_init_fix.install()


def _rng_state(sim) -> str:
    return json.dumps(sim.rng.bit_generator.state, sort_keys=True)


def _env_rng_state(sim) -> str | None:
    rng = getattr(sim.world, "env_rng", None)
    if rng is None:
        return None
    return json.dumps(rng.bit_generator.state, sort_keys=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--calibration-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    f0, h2_field = core.load_calibration(args.calibration_dir)
    checks: list[dict] = []

    for environment in core.ENVIRONMENTS:
        base_cfg = core.make_cfg(f0, environment)
        for seed in core.SEEDS:
            b = core.exp18_core.setup_sim(base_cfg, seed, h2_field)
            b_rng = _rng_state(b)
            b_env_rng = _env_rng_state(b)
            b_energy = np.asarray([o.energy for o in sorted(b.organisms, key=lambda x: x.id)])

            for trait in core.TRAITS:
                bfp = core.initial_fingerprint(b, ignore_trait=trait)
                for factor in core.FACTORS:
                    cfg = core.make_cfg(f0, environment, trait, factor)
                    v = core.exp18_core.setup_sim(cfg, seed, h2_field)
                    vfp = core.initial_fingerprint(v, ignore_trait=trait)
                    v_energy = np.asarray([o.energy for o in sorted(v.organisms, key=lambda x: x.id)])

                    same_fingerprint = bfp == vfp
                    same_energy = np.array_equal(b_energy, v_energy)
                    same_rng = b_rng == _rng_state(v)
                    same_env_rng = b_env_rng == _env_rng_state(v)
                    passed = same_fingerprint and same_energy and same_rng and same_env_rng
                    row = {
                        "environment": environment,
                        "seed": seed,
                        "trait": trait,
                        "factor": factor,
                        "initial_state_match_except_trait": same_fingerprint,
                        "absolute_energy_match": same_energy,
                        "organism_rng_match": same_rng,
                        "environment_rng_match": same_env_rng,
                        "pass": passed,
                    }
                    checks.append(row)
                    if not passed:
                        raise RuntimeError(f"Attempt2 t=0 gate failed: {row}")

    report = {
        "experiment": "Exp20 Attempt 2 initial-state preflight",
        "n_checks": len(checks),
        "all_pass": all(x["pass"] for x in checks),
        "checks": checks,
    }
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"ATTEMPT2_INITIAL_STATE_PREFLIGHT_PASS n={len(checks)}")


if __name__ == "__main__":
    main()
