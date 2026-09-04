"""Exp16 V1.9 fixed-iLUCA environment robustness runner.

The organism is the Exp15 Attempt-2 LUCA-like proxy and is kept fixed (arm A).
Only environmental H2 concentration, exchange timescale, diffusion coefficient,
or four-source geometry changes between preregistered conditions.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LUCA_DIR = ROOT / "experiments" / "luca_proxy"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(LUCA_DIR))

import run_luca_proxy as luca  # noqa: E402
from evosim.genome import GENE_NAMES  # noqa: E402


SQUARE = ((10, 10), (10, 30), (30, 10), (30, 30))
CROSS = ((20, 10), (10, 20), (30, 20), (20, 30))
CLUSTER = ((17, 17), (17, 23), (23, 17), (23, 23))
LAYOUTS = {"square": SQUARE, "cross": CROSS, "cluster": CLUSTER}

CONDITIONS = {
    "h2_1mM": {"h2_source_molm3": 1.0, "tau_s": 900.0, "diffusion_m2s": 5.0e-9, "layout": "square"},
    "h2_3mM": {"h2_source_molm3": 3.0, "tau_s": 900.0, "diffusion_m2s": 5.0e-9, "layout": "square"},
    "h2_6mM": {"h2_source_molm3": 6.0, "tau_s": 900.0, "diffusion_m2s": 5.0e-9, "layout": "square"},
    "baseline_10mM": {"h2_source_molm3": 10.0, "tau_s": 900.0, "diffusion_m2s": 5.0e-9, "layout": "square"},
    "h2_15mM": {"h2_source_molm3": 15.0, "tau_s": 900.0, "diffusion_m2s": 5.0e-9, "layout": "square"},
    "exchange_fast_300s": {"h2_source_molm3": 10.0, "tau_s": 300.0, "diffusion_m2s": 5.0e-9, "layout": "square"},
    "exchange_slow_3600s": {"h2_source_molm3": 10.0, "tau_s": 3600.0, "diffusion_m2s": 5.0e-9, "layout": "square"},
    "diffusion_low_2p5e9": {"h2_source_molm3": 10.0, "tau_s": 900.0, "diffusion_m2s": 2.5e-9, "layout": "square"},
    "diffusion_high_1e8": {"h2_source_molm3": 10.0, "tau_s": 900.0, "diffusion_m2s": 1.0e-8, "layout": "square"},
    "layout_cross": {"h2_source_molm3": 10.0, "tau_s": 900.0, "diffusion_m2s": 5.0e-9, "layout": "cross"},
    "layout_cluster": {"h2_source_molm3": 10.0, "tau_s": 900.0, "diffusion_m2s": 5.0e-9, "layout": "cluster"},
}

_BASE_LUCA_MAKE_CFG = luca.make_cfg
_BASE_LUCA_RUN = luca.run_luca


def make_cfg(condition: str):
    if condition not in CONDITIONS:
        raise ValueError(f"unknown Exp16 condition: {condition}")
    spec = CONDITIONS[condition]
    cfg = _BASE_LUCA_MAKE_CFG("A")
    cfg = dataclasses.replace(
        cfg,
        h2_source_concentration_molm3=float(spec["h2_source_molm3"]),
        h2_exchange_tau_s=float(spec["tau_s"]),
        h2_diffusion_m2s=float(spec["diffusion_m2s"]),
    )
    # Exp16 invariant: organism side must be fully fixed.
    if set(cfg.fixed_genes) != set(GENE_NAMES):
        raise RuntimeError("Exp16 requires arm A with all genes fixed")
    if cfg.initial_jitter_sigma != 0.0:
        raise RuntimeError("Exp16 requires zero initial genomic jitter")
    if cfg.phototrophy_innovation_prob != 0.0 or cfg.phototrophy_loss_prob != 0.0:
        raise RuntimeError("Exp16 requires structural innovation disabled")
    return cfg


def run(condition: str, seed: int, outdir: Path, days: float) -> dict:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown Exp16 condition: {condition}")
    spec = CONDITIONS[condition]

    # run_exp15.setup_sim resolves these module globals at runtime. Patch only for
    # the duration of this run, then restore so importing this module is side-effect
    # free beyond run_luca_proxy's registered physical semantics.
    old_make_cfg = luca.base.make_cfg
    old_centers = luca.base.FOUR_CENTERS

    def _condition_cfg(_arm: str):
        return make_cfg(condition)

    luca.base.make_cfg = _condition_cfg
    luca.base.FOUR_CENTERS = LAYOUTS[str(spec["layout"])]
    try:
        summary = _BASE_LUCA_RUN("A", seed, outdir, days)
    finally:
        luca.base.make_cfg = old_make_cfg
        luca.base.FOUR_CENTERS = old_centers

    summary["experiment"] = "Exp16 V1.9 fixed-iLUCA environment robustness"
    summary["condition"] = condition
    summary["fixed_iLUCA"] = True
    summary["iLUCA_reference_commit"] = "ee9f181612b24c39d5bd092f8cd0310dfcde2cc7"
    summary["environment_condition"] = {
        "h2_source_concentration_molm3": float(spec["h2_source_molm3"]),
        "h2_source_concentration_mM": float(spec["h2_source_molm3"]),
        "h2_exchange_tau_s": float(spec["tau_s"]),
        "h2_diffusion_m2s": float(spec["diffusion_m2s"]),
        "source_layout": str(spec["layout"]),
        "source_centers_grid": [list(x) for x in LAYOUTS[str(spec["layout"])]],
        "n_sources": 4,
    }
    summary["experiment_policy"] = {
        "preregistered_conditions": True,
        "adaptive_tuning": False,
        "organism_parameters_changed_between_conditions": False,
        "extinction_retained_as_data": True,
    }
    # run_luca annotates the reference 10 mM source inside luca_proxy. Make clear
    # that source concentration is an Exp16 environmental variable, not an
    # organism intrinsic parameter.
    if isinstance(summary.get("luca_proxy"), dict):
        summary["luca_proxy"]["reference_environment_h2_source_molm3"] = 10.0
        summary["luca_proxy"].pop("h2_source_molm3", None)

    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--days", type=float, default=10.0)
    p.add_argument("--outdir", type=Path, required=True)
    args = p.parse_args()
    run(args.condition, args.seed, args.outdir, args.days)


if __name__ == "__main__":
    main()
