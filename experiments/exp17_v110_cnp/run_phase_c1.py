"""Exp17 Phase C1 — finite C/N/P placement calibration.

Human-approved post-Exp17 diagnostic amendment:
  docs/Exp17_PhaseC1_CNP配置量校正_実験計画.md

All C/N/P fields are initialized in the fixed biomass stoichiometric ratio and
background exchange is disabled.  The only experimental axis is how many
initial-community biomass equivalents of C/N/P are placed in the world.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

from evosim import stoichiometry  # noqa: E402

INITIAL_MATTER_PER_AGENT = 0.50
CONDITIONS = {
    "C10": 10,
    "C30": 30,
    "C50": 50,
    "C100": 100,
}


def world_volume_m3(cfg) -> float:
    """Physical volume represented by the full 2-D grid."""
    return (
        cfg.grid_w
        * cfg.grid_h
        * cfg.cell_size
        * cfg.cell_size
        * cfg.effective_depth_m
    )


def backgrounds_for_equivalents(cfg, equivalents: int) -> dict[str, float | bool]:
    """Return C/N/P concentrations for N initial-community biomass equivalents."""
    if equivalents <= 0:
        raise ValueError("equivalents must be positive")
    volume = world_volume_m3(cfg)
    if volume <= 0.0:
        raise ValueError("world physical volume must be positive")

    initial_matter = cfg.initial_population * INITIAL_MATTER_PER_AGENT
    c1, n1, p1 = stoichiometry.matter_to_element_mol(initial_matter, cfg)
    scale = float(equivalents) / volume
    return {
        "dic_background_molm3": c1 * scale,
        "fixed_n_background_molm3": n1 * scale,
        "phosphate_background_molm3": p1 * scale,
        "cnp_background_exchange_enabled": False,
    }


def condition_overrides(condition: str) -> tuple[int, dict[str, float | bool]]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}; choose from {sorted(CONDITIONS)}")
    equivalents = CONDITIONS[condition]
    base_cfg = core.make_cfg()
    return equivalents, backgrounds_for_equivalents(base_cfg, equivalents)


def run_condition(condition: str, seed: int, outdir: Path, days: float = 10.0) -> dict:
    equivalents, overrides = condition_overrides(condition)
    old_make_cfg = core.make_cfg

    def _condition_make_cfg(**kw):
        cfg = old_make_cfg(**kw)
        return dataclasses.replace(cfg, **overrides)

    core.make_cfg = _condition_make_cfg
    try:
        summary = core.run(seed, outdir, days, write_snapshots=False)
    finally:
        core.make_cfg = old_make_cfg

    summary["phase"] = "C1"
    summary["condition"] = condition
    summary["biomass_equivalents"] = equivalents
    summary["condition_overrides"] = overrides
    summary["calibration_semantics"] = {
        "initial_matter_per_agent": INITIAL_MATTER_PER_AGENT,
        "initial_community_matter_units": summary["population_initial"] * INITIAL_MATTER_PER_AGENT,
        "cnp_background_exchange_enabled": False,
        "purpose": "finite placement diagnostic; does not auto-select V1.10 defaults",
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--days", type=float, default=10.0)
    p.add_argument("--outdir", type=Path, required=True)
    args = p.parse_args()

    summary = run_condition(args.condition, args.seed, args.outdir, args.days)
    slim = {k: v for k, v in summary.items() if k != "cnp_ledger"}
    print(json.dumps(slim, indent=2))


if __name__ == "__main__":
    main()
