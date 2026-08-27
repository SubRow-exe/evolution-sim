"""アブレーション機能 (fixed_genes) の検証。

「その遺伝子だけが違う」比較が成立することを保証する。
"""
import numpy as np
import pytest

from evosim.config import Config
from evosim.genome import BODY_SIZE, GENE_NAMES, INITIAL_GENOME, MUTATION_RATE
from evosim.simulation import Simulation


def test_fixed_gene_never_changes():
    """固定した遺伝子は全個体・全世代で初期値のまま。"""
    cfg = Config(fixed_genes=["body_size"])
    sim = Simulation(cfg, 3)
    for _ in range(800):
        sim.step()
    assert sim.births_cum > cfg.initial_population, "繁殖が起きていない"

    values = np.array([o.genome[BODY_SIZE] for o in sim.organisms])
    assert np.allclose(values, INITIAL_GENOME[BODY_SIZE]), "固定遺伝子が変化した"


def test_other_genes_still_evolve_when_one_is_fixed():
    """固定は指定した遺伝子だけに効き、他は通常どおり変異する。"""
    sim = Simulation(Config(fixed_genes=["body_size"]), 3)
    for _ in range(800):
        sim.step()
    mut = np.array([o.genome[MUTATION_RATE] for o in sim.organisms])
    assert mut.std() > 0.0, "他の遺伝子まで固定されている"


def test_unknown_gene_name_is_rejected():
    with pytest.raises(ValueError, match="未知の遺伝子名"):
        Simulation(Config(fixed_genes=["no_such_gene"]), 1)


def test_default_config_has_no_fixed_genes():
    """既定では baseline の挙動を変えない。"""
    assert Config().fixed_genes == []
    assert Simulation(Config(), 1).fixed_mask is None


def test_all_gene_names_accepted():
    """全遺伝子名が固定対象として受け付けられる。"""
    for name in GENE_NAMES:
        sim = Simulation(Config(fixed_genes=[name]), 1)
        assert sim.fixed_mask is not None and sim.fixed_mask.sum() == 1
