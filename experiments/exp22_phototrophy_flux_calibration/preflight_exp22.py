"""Exp22 formal run前の必須gate G0-G5 (docs/Exp22_実験計画.md §3)。

1つでも失敗した場合、Exp22本計算 (72 formal runs) を開始しない。
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_exp22 as core  # noqa: E402


def check_g0_g1_g2_g5(f0, h2_field, environment: str, flux: float, seed: int) -> dict:
    cfg = core.make_cfg(f0, environment, flux)
    core.validate_effective_config(cfg, environment, flux)  # G2

    off = core.setup_paired(cfg, seed, h2_field, capability_on=False)
    on = core.setup_paired(cfg, seed, h2_field, capability_on=True)
    g5 = core.initial_fingerprint(off) == core.initial_fingerprint(on)

    # short mechanical run to exercise G0 (legacy light contamination) and
    # G1 (physical upper-bound identity) with an actually-nonzero photo path.
    off_rows, _, _ = core.run_one(cfg, seed, h2_field, hours=0.02, capability_on=False)
    on_rows, _, _ = core.run_one(cfg, seed, h2_field, hours=0.02, capability_on=True)
    g0 = all(r["legacy_light_flow_cum"] == 0.0 for r in off_rows + on_rows)
    g1 = all(
        r["photo_used_j_cum"] <= r["photo_usable_max_j_cum"] + 1e-9
        and r["photo_usable_max_j_cum"] <= r["photo_absorbed_j_cum"] + 1e-9
        and r["photo_absorbed_j_cum"] <= r["photo_incident_j_cum"] + 1e-9
        for r in on_rows
    )
    return {
        "environment": environment, "flux": flux, "seed": seed,
        "G0_legacy_light_zero": g0, "G1_physical_upper_bound": g1,
        "G2_effective_config_match": True,  # validate_effective_config raised if not
        "G5_initial_state_match_except_trait": g5,
        "all_pass": bool(g0 and g1 and g5),
    }


def check_g3_light_only_no_growth(f0, h2_field, environment: str) -> dict:
    """docs §3 G3 / rev2 HARD RULE P3: H2=0, light>0で、phototrophyが
    maintenanceを補助してもlight単独で持続的なnet biomass growthを
    作らないことを確認する。
    """
    cfg = core.make_cfg(f0, environment, flux=1.5)  # 最高flux (positive control)
    cfg = dataclasses.replace(cfg, h2_vent_flux_mol_s=0.0)  # H2 source停止
    zero_h2_field = np.zeros_like(h2_field)
    sim = core.setup_paired(cfg, 22001, zero_h2_field, capability_on=True)
    m0 = sum(o.matter for o in sim.organisms)
    steps = int(round(6 * 3600.0 / cfg.dt_seconds))  # 6h
    for _ in range(steps):
        sim.step()
        if not sim.organisms:
            break
    m1 = sum(o.matter for o in sim.organisms) if sim.organisms else 0.0
    return {"environment": environment, "initial_matter": m0, "final_matter": m1,
           "no_net_growth": bool(m1 <= m0 + 1e-9)}


def check_g4_n_ledger(f0, h2_field, environment: str, flux: float, seed: int) -> dict:
    """docs §3 G4: apparatus assembly/releaseを含めてもN ledgerが
    許容誤差内で閉じること (closed system: background exchange OFF)。
    """
    cfg = core.make_cfg(f0, environment, flux)
    cfg = dataclasses.replace(cfg, cnp_background_exchange_enabled=False)
    sim = core.setup_paired(cfg, seed, h2_field, capability_on=True)
    n0 = sim.system_nitrogen()
    steps = int(round(1 * 3600.0 / cfg.dt_seconds))  # 1h closed-system check
    for _ in range(steps):
        sim.step()
        if not sim.organisms:
            break
    n1 = sim.system_nitrogen()
    rel = abs(n1 - n0) / n1 if n1 > 0 else abs(n1 - n0)
    return {"environment": environment, "flux": flux, "seed": seed,
           "n0": n0, "n1": n1, "relative_residual": rel, "pass": bool(rel < 1e-6)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibration-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    f0, h2_field = core.load_calibration(args.calibration_dir)

    g0125 = [check_g0_g1_g2_g5(f0, h2_field, env, flux, seed)
            for env in core.ENVIRONMENTS
            for flux in core.FLUX_LEVELS_UMOL_M2_S
            for seed in core.SEEDS]
    g3 = [check_g3_light_only_no_growth(f0, h2_field, env) for env in core.ENVIRONMENTS]
    g4 = [check_g4_n_ledger(f0, h2_field, env, flux, core.SEEDS[0])
         for env in core.ENVIRONMENTS for flux in core.FLUX_LEVELS_UMOL_M2_S]

    all_pass = (all(r["all_pass"] for r in g0125)
               and all(r["no_net_growth"] for r in g3)
               and all(r["pass"] for r in g4))

    out = {"all_pass": all_pass, "g0_g1_g2_g5": g0125, "g3": g3, "g4": g4}
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"all_pass": all_pass, "n_g0125_checks": len(g0125),
                      "n_g3_checks": len(g3), "n_g4_checks": len(g4)}, indent=2))
    if not all_pass:
        raise SystemExit("Exp22 preflight FAILED — see output JSON for details")
    print("EXP22_PREFLIGHT_PASS")


if __name__ == "__main__":
    main()
