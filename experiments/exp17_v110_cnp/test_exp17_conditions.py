"""Exp17 preflight: harness wiring sanity (not the Phase 0 mechanical suite).

tests/test_v110_cnp.py がcore mechanismを検証する。ここではExp17固有の
run harness (core.py / run_exp17.py / aggregate_exp17.py) の配線だけを
素早く確認する。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import core  # noqa: E402
import run_exp17  # noqa: E402


def test_make_cfg_is_explicit_cnp_and_all_genes_fixed():
    cfg = core.make_cfg()
    assert cfg.explicit_cnp_resources is True
    assert cfg.physical_mode is True
    assert cfg.nutrient_initial == 0.0
    from evosim.genome import GENE_NAMES
    assert set(cfg.fixed_genes) == set(GENE_NAMES)
    assert cfg.initial_jitter_sigma == 0.0
    assert cfg.phototrophy_innovation_prob == 0.0
    assert cfg.phototrophy_loss_prob == 0.0


def test_phase_b_conditions_change_exactly_one_resource():
    ref = core.make_cfg()
    for name, overrides in run_exp17.PHASE_B_CONDITIONS.items():
        assert len(overrides) <= 1, f"{name} changes more than one field: {overrides}"


def test_tiny_phase_a_run_smoke(tmp_path):
    summary = run_exp17.run_phase_a(17001, tmp_path / "a", days=0.01)
    assert summary["phase"] == "A"
    assert summary["population_final"] > 0
    for artifact in ("effective_config.json", "initial_genome.json", "summary.json",
                     "timeseries.csv", "cnp_ledger.json", "growth_limiter.csv"):
        assert (tmp_path / "a" / artifact).exists()


def test_tiny_phase_b_run_smoke(tmp_path):
    summary = run_exp17.run_phase_b("B1_low_dic", 17001, tmp_path / "b1", days=0.01)
    assert summary["phase"] == "B"
    assert summary["condition"] == "B1_low_dic"
