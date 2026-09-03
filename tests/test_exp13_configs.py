"""Exp13 Config生成の事前登録条件を機械的に守る
(docs/Exp13_実験計画確定.md, docs/V1.8_実装チェックリスト.md §12)。

独立オラクル値 (実装定数を再利用しない) でmatrix総数・fixed_genesを検証する。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.genome import GENE_NAMES, fixed_mask_from_names
from evosim.simulation import Simulation
from tools.make_exp13_configs import (
    build_a1, build_a2, build_a2b, build_a3, build_b1, build_b2, build_b3,
    build_b4a, build_b4b,
)

# 独立オラクル: 実装のtools/exp13_common.pyをそのまま信用せず、
# 事前登録計画の数値をここで再宣言する。
ORACLE_A1_LIGHT_MAX = [0.8, 1.2, 1.5, 1.8, 2.1, 2.4, 3.0, 4.0]
ORACLE_A1_SEEDS = 5
ORACLE_A1_JOBS = 8 * 5  # 40

ORACLE_A2_K = [0.5, 1.5, 3.0, 6.15]
ORACLE_A2_UPTAKE = [0.5, 1.0, 2.0, 4.0]
ORACLE_A2_SEEDS = 3
ORACLE_A2_JOBS = 4 * 4 * 3  # 48

ORACLE_A2B_SEEDS = 5
ORACLE_A2B_PLACEMENTS = 2
ORACLE_A2B_JOBS = 5 * 2  # 10

ORACLE_A3_POPS = [1, 10, 50]
ORACLE_A3_SEEDS = 3
ORACLE_A3_JOBS = 3 * 3  # 9

ORACLE_PHASE_A_TOTAL = 40 + 48 + 10 + 9  # 107

ORACLE_B1_JOBS = 8
ORACLE_B2_JOBS = 8
ORACLE_B3_JOBS = 12
ORACLE_B4A_JOBS = 3
ORACLE_B4B_JOBS = 5
ORACLE_PHASE_B_TOTAL = 8 + 8 + 12 + 3 + 5  # 36

ORACLE_TOTAL = ORACLE_PHASE_A_TOTAL + ORACLE_PHASE_B_TOTAL  # 143

ALL_14_GENES = set(GENE_NAMES)
assert len(ALL_14_GENES) == 14


class TestMatrixTotals:
    def test_a1_jobs(self):
        from tools.exp13_common import A1_JOBS
        assert A1_JOBS == ORACLE_A1_JOBS == 40

    def test_a2_jobs(self):
        from tools.exp13_common import A2_JOBS
        assert A2_JOBS == ORACLE_A2_JOBS == 48

    def test_a2b_jobs(self):
        from tools.exp13_common import A2B_JOBS
        assert A2B_JOBS == ORACLE_A2B_JOBS == 10

    def test_a3_jobs(self):
        from tools.exp13_common import A3_JOBS
        assert A3_JOBS == ORACLE_A3_JOBS == 9

    def test_phase_a_total(self):
        from tools.exp13_common import PHASE_A_TOTAL
        assert PHASE_A_TOTAL == ORACLE_PHASE_A_TOTAL == 107

    def test_phase_b_total(self):
        from tools.exp13_common import PHASE_B_TOTAL
        assert PHASE_B_TOTAL == ORACLE_PHASE_B_TOTAL == 36

    def test_grand_total(self):
        from tools.exp13_common import TOTAL_RUNS
        assert TOTAL_RUNS == ORACLE_TOTAL == 143


class TestA1Config:
    @pytest.mark.parametrize("light_max", ORACLE_A1_LIGHT_MAX)
    def test_all_14_fixed(self, light_max):
        cfg = build_a1(light_max)
        assert set(cfg.fixed_genes) == ALL_14_GENES
        fixed_mask_from_names(cfg.fixed_genes)

    def test_phenotype_light_specialist(self):
        cfg = build_a1(1.8)
        assert cfg.diagnostic_gene_overrides == {"light_absorption": 2.0, "chemical_absorption": 0.3}

    def test_environment(self):
        cfg = build_a1(1.8)
        assert cfg.light_pattern == "vertical"
        assert cfg.chem_vent_flux == 0.0
        assert cfg.diagnostic_placement == "random"
        assert cfg.light_cycle_enabled is True
        assert cfg.primary_energy_density_response is True

    def test_bmr_core(self):
        assert build_a1(1.8).bmr_core == 0.15

    def test_light_max_value(self):
        for lm in ORACLE_A1_LIGHT_MAX:
            assert build_a1(lm).light_max == lm

    def test_simulation_smoke(self):
        cfg = build_a1(1.8)
        sim = Simulation(cfg, seed=1)
        for _ in range(5):
            sim.step()


class TestA2Config:
    def test_grid_all_14_fixed(self):
        for k in ORACLE_A2_K:
            for u in ORACLE_A2_UPTAKE:
                cfg = build_a2(k, u)
                assert set(cfg.fixed_genes) == ALL_14_GENES
                fixed_mask_from_names(cfg.fixed_genes)

    def test_phenotype_chem_specialist(self):
        cfg = build_a2(1.5, 2.0)
        assert cfg.diagnostic_gene_overrides == {"light_absorption": 0.3, "chemical_absorption": 2.0}

    def test_environment(self):
        cfg = build_a2(1.5, 2.0)
        assert cfg.light_max == 0.0
        assert cfg.chem_vent_flux == 16.0
        assert cfg.diagnostic_placement == "vent"

    def test_grid_values(self):
        cfg = build_a2(0.5, 4.0)
        assert cfg.chemical_uptake_half == 0.5
        assert cfg.chem_uptake == 4.0

    def test_simulation_smoke(self):
        cfg = build_a2(1.5, 2.0)
        sim = Simulation(cfg, seed=1)
        for _ in range(5):
            sim.step()


class TestB3Config:
    def test_only_light_chemical_evolve(self):
        cfg = build_b3(1.8, 1.5, 2.0)
        assert "light_absorption" not in cfg.fixed_genes
        assert "chemical_absorption" not in cfg.fixed_genes
        assert len(cfg.fixed_genes) == 12
        assert set(cfg.fixed_genes) == ALL_14_GENES - {"light_absorption", "chemical_absorption"}

    def test_mixed_world(self):
        cfg = build_b3(1.8, 1.5, 2.0)
        assert cfg.light_max == 1.8
        assert cfg.chem_vent_flux == 16.0


class TestB4aConfig:
    def test_body_size_override_and_derived_matter_energy(self):
        cfg = build_b4a(1.8)
        assert set(cfg.fixed_genes) == ALL_14_GENES
        assert cfg.diagnostic_gene_overrides["body_size"] == pytest.approx(0.246)
        assert cfg.initial_matter == pytest.approx(0.8 * 0.246, rel=1e-9)
        # 標準個体と同じEnergy-capacity fraction (50/80=0.625) から導出
        expected_energy = 0.625 * (100.0 * 0.8 * 0.246)
        assert cfg.initial_energy == pytest.approx(expected_energy, rel=1e-9)

    def test_simulation_smoke(self):
        cfg = build_b4a(1.8)
        sim = Simulation(cfg, seed=1)
        for _ in range(5):
            sim.step()


class TestB4bConfig:
    def test_only_body_size_evolves(self):
        cfg = build_b4b(1.8)
        assert "body_size" not in cfg.fixed_genes
        assert len(cfg.fixed_genes) == 13
        assert set(cfg.fixed_genes) == ALL_14_GENES - {"body_size"}


class TestB1B2Config:
    def test_b1_light_only(self):
        cfg = build_b1(1.8)
        assert set(cfg.fixed_genes) == ALL_14_GENES
        assert cfg.chem_vent_flux == 0.0
        assert cfg.diagnostic_gene_overrides == {"light_absorption": 2.0, "chemical_absorption": 0.3}

    def test_b2_chemical_only(self):
        cfg = build_b2(1.5, 2.0)
        assert set(cfg.fixed_genes) == ALL_14_GENES
        assert cfg.light_max == 0.0
        assert cfg.diagnostic_gene_overrides == {"light_absorption": 0.3, "chemical_absorption": 2.0}


class TestA2bA3Config:
    def test_a2b_placements(self):
        for placement in ("vent", "random"):
            cfg = build_a2b(1.5, 2.0, placement)
            assert cfg.diagnostic_placement == placement
            assert set(cfg.fixed_genes) == ALL_14_GENES

    def test_a3_populations(self):
        for pop in ORACLE_A3_POPS:
            cfg = build_a3(1.5, 2.0, pop)
            assert cfg.initial_population == pop
            assert cfg.diagnostic_placement == "vent"


class TestCommonParams:
    @pytest.mark.parametrize("build_fn,args", [
        (build_a1, (1.8,)),
        (build_a2, (1.5, 2.0)),
        (build_b1, (1.8,)),
        (build_b2, (1.5, 2.0)),
        (build_b3, (1.8, 1.5, 2.0)),
        (build_b4a, (1.8,)),
        (build_b4b, (1.8,)),
    ])
    def test_bmr_core_and_behavior_params(self, build_fn, args):
        cfg = build_fn(*args)
        assert cfg.bmr_core == 0.15
        assert cfg.memory_tau == 10.0
        assert cfg.response_gain == 64.0
        assert cfg.light_uptake_half == 0.6
        assert cfg.primary_energy_density_response is True
        assert cfg.max_population_halt == 10_000
