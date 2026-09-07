"""Policy/invariant tests for Exp16 preregistered environment conditions."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "exp16_v19_env"))

import run_exp16 as exp16  # noqa: E402
from evosim.genome import GENE_NAMES  # noqa: E402


BIO_FIELDS = (
    "basal_atp_mmol_per_gdw_h",
    "atp_energy_j_per_mol",
    "h2_qmax_mol_per_kgdw_s",
    "h2_km_mol_m3",
    "h2_usable_energy_j_per_mol",
    "growth_energy_j_per_kgdw",
    "nutrient_uptake_rate_matter_per_h",
    "storage_capacity_hours",
)


def test_condition_registry_is_preregistered_11_arm_set():
    assert len(exp16.CONDITIONS) == 11
    assert "baseline_10mM" in exp16.CONDITIONS
    assert set(exp16.LAYOUTS) == {"square", "cross", "cluster"}


def test_baseline_matches_exp15_attempt2_environment():
    c = exp16.CONDITIONS["baseline_10mM"]
    assert c == {
        "h2_source_molm3": 10.0,
        "tau_s": 900.0,
        "diffusion_m2s": 5.0e-9,
        "layout": "square",
    }


def test_all_conditions_keep_organism_side_fixed():
    ref = exp16.make_cfg("baseline_10mM")
    for name in exp16.CONDITIONS:
        cfg = exp16.make_cfg(name)
        assert set(cfg.fixed_genes) == set(GENE_NAMES)
        assert cfg.initial_jitter_sigma == 0.0
        assert cfg.phototrophy_innovation_prob == 0.0
        assert cfg.phototrophy_loss_prob == 0.0
        for field in BIO_FIELDS:
            assert getattr(cfg, field) == getattr(ref, field), (name, field)


def test_each_nonbaseline_condition_changes_only_one_environment_axis():
    base = exp16.CONDITIONS["baseline_10mM"]
    keys = tuple(base)
    for name, spec in exp16.CONDITIONS.items():
        if name == "baseline_10mM":
            continue
        changed = [k for k in keys if spec[k] != base[k]]
        assert len(changed) == 1, (name, changed)
