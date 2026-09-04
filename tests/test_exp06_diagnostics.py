"""Exp06 診断ハーネスの検証 (docs/Exp06_実験計画.md §4-5)。

診断の前提:
- 既定 (診断オフ) では通常実行と**完全に**同一 — 乱数系列も科学状態も
- light=0 条件で光からのエネルギー流入が本当に0
- vent配置は chem_mask セルのみを使い、同一seedなら B/C で一致する
- ランダム配置は同一seedなら A/D で一致し、通常実行とも一致する
- chemical_absorption の上書きは乱数を消費せず、全世代で固定される
"""
import numpy as np
import pytest

from evosim.config import Config
from evosim.genome import CHEM_ABS, GENE_NAMES, LIGHT_ABS
from evosim.simulation import Simulation

ALL_DARK = {"light_pattern": "uniform", "light_max": 0.0}
CHEM_ADAPTED = {"fixed_genes": ["chemical_absorption"],
                "diagnostic_gene_overrides": {"chemical_absorption": 2.0}}


def cfg_for(condition: str, **kw) -> Config:
    """Exp06 の4条件を組み立てる (configs/exp06_*.json と同じ内容)。"""
    base = dict(ALL_DARK, snapshot_interval=1000, **kw)
    if condition in ("B", "C"):
        base["diagnostic_placement"] = "vent"
    if condition in ("C", "D"):
        base.update(CHEM_ADAPTED)
    return Config(**base)


def state_of(sim: Simulation) -> list[tuple]:
    return [(o.id, o.x, o.y, o.energy, o.matter, o.damage,
             tuple(float(g) for g in o.genome)) for o in sim.organisms]


# --- 既定は通常実行と完全に同一 ---------------------------------------

def test_default_is_unchanged():
    """診断フィールドを既定値で明示しても、通常実行と1ビットも変わらない。"""
    a = Simulation(Config(), 3)
    b = Simulation(Config(diagnostic_placement="random",
                          diagnostic_gene_overrides={}), 3)
    for _ in range(300):
        a.step()
        b.step()
    assert state_of(a) == state_of(b)
    assert a.rng.bit_generator.state == b.rng.bit_generator.state


# --- light = 0 --------------------------------------------------------

def test_all_dark_supplies_no_light():
    sim = Simulation(cfg_for("A"), 1)
    assert sim.world.light.sum() == 0.0
    assert sim.light_supply_per_tick == 0.0
    for _ in range(200):
        sim.step()
    assert sim.flows["light"] == 0.0


def test_all_dark_keeps_light_absorption_gene():
    """光0の診断条件が light_absorption 遺伝子自体を書き換えない
    (世界側 (light=0) だけを変え、個体側のgene値には触れない)。

    V1.9: baseline iLUCAはPHOTOTROPHY OFFなのでlight_absorption=0が
    正しい既定値 (docs/V1.9_iLUCA再設計仕様.md §2)。ここでは診断条件
    (ALL_DARK) がINITIAL_GENOMEの値からgeneを追加で変えていないことを
    確認する。
    """
    from evosim.genome import INITIAL_GENOME
    sim = Simulation(cfg_for("A"), 1)
    assert all(o.genome[LIGHT_ABS] == pytest.approx(INITIAL_GENOME[LIGHT_ABS])
               for o in sim.organisms)


# --- 配置 -------------------------------------------------------------

def test_vent_placement_is_on_vent_cells():
    sim = Simulation(cfg_for("B"), 2)
    assert len(sim.organisms) == sim.cfg.initial_population
    for o in sim.organisms:
        assert sim.world.h2_mask[sim.world.cell_index(o.x, o.y)]


def test_vent_placement_inside_world():
    sim = Simulation(cfg_for("B"), 4)
    for o in sim.organisms:
        assert 0.0 <= o.x < sim.cfg.world_width
        assert 0.0 <= o.y < sim.cfg.world_height


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_paired_conditions_share_initial_positions(seed):
    """同一seedなら B/C は同じvent配置、A/D は同じランダム配置になる。

    位置が条件間でずれると「ゲノムだけが違う比較」が成立しない。
    """
    pos = {c: [(o.x, o.y) for o in Simulation(cfg_for(c), seed).organisms]
           for c in "ABCD"}
    assert pos["B"] == pos["C"]
    assert pos["A"] == pos["D"]
    assert pos["A"] != pos["B"]


def test_random_placement_matches_normal_run():
    """A/D のランダム配置は通常実行 (光あり) と同じ乱数系列から作られる。"""
    a = Simulation(cfg_for("A"), 5)
    normal = Simulation(Config(), 5)
    assert [(o.x, o.y) for o in a.organisms] == [(o.x, o.y) for o in normal.organisms]


# --- ゲノム上書き -----------------------------------------------------

def test_override_sets_exact_value():
    sim = Simulation(cfg_for("C"), 1)
    assert all(o.genome[CHEM_ABS] == 2.0 for o in sim.organisms)


def test_override_leaves_other_genes_untouched():
    b = Simulation(cfg_for("B"), 7)
    c = Simulation(cfg_for("C"), 7)
    for x, y in zip(b.organisms, c.organisms):
        diff = [i for i in range(len(GENE_NAMES)) if x.genome[i] != y.genome[i]]
        assert diff == [CHEM_ABS]


def test_override_does_not_consume_rng():
    """上書きが乱数を消費すると、以後の配置・変異系列がずれてしまう。"""
    b = Simulation(cfg_for("B"), 9)
    c = Simulation(cfg_for("C"), 9)
    assert b.rng.bit_generator.state == c.rng.bit_generator.state


def test_override_stays_fixed_across_generations():
    """positive control は子孫でも 2.0 のまま (fixed_genes による固定)。

    V1.9物理スケール検証パッチでreproduction_horizonの既定値/最小値が
    seconds単位 (最小300s) へ変わったが、arbitrary-unit modeのEnergy収支
    ではその最小値にも届かない (tests/test_smoke.pyのdocstring参照)。
    この機構テストの目的はfixed_genesによる固定の確認であり、
    reproduction_horizonもfixed_genesへ加えたうえで、Config経由のgene
    rangeバリデーションを経ずに個体genomeへ直接テスト専用の小さい値を
    設定する (fixed geneは子孫でもそのまま継承される)。
    """
    cfg = Config(**dict(ALL_DARK, snapshot_interval=1000,
                        diagnostic_placement="vent",
                        fixed_genes=["chemical_absorption", "reproduction_horizon"],
                        diagnostic_gene_overrides={"chemical_absorption": 2.0}))
    sim = Simulation(cfg, 1)
    from evosim.genome import REPRO_HORIZON
    for o in sim.organisms:
        o.genome[REPRO_HORIZON] = 1.0
    for _ in range(600):
        sim.step()
    assert sim.births_cum > sim.cfg.initial_population, "世代交代が起きていない"
    assert all(o.genome[CHEM_ABS] == 2.0 for o in sim.organisms)


# --- 設定ミスを弾く ---------------------------------------------------

def test_override_without_fixed_genes_is_rejected():
    with pytest.raises(ValueError, match="fixed_genes"):
        Simulation(Config(diagnostic_gene_overrides={"chemical_absorption": 2.0}), 1)


def test_unknown_override_gene_is_rejected():
    with pytest.raises(ValueError, match="未知の遺伝子名"):
        Simulation(Config(fixed_genes=["spice"],
                          diagnostic_gene_overrides={"spice": 1.0}), 1)


def test_out_of_range_override_is_rejected():
    with pytest.raises(ValueError, match="範囲外"):
        Simulation(Config(fixed_genes=["chemical_absorption"],
                          diagnostic_gene_overrides={"chemical_absorption": 99.0}), 1)


def test_unknown_placement_is_rejected():
    with pytest.raises(ValueError, match="diagnostic_placement"):
        Simulation(Config(diagnostic_placement="vents"), 1)


def test_vent_placement_without_vents_is_rejected():
    with pytest.raises(ValueError, match="h2_mask"):
        Simulation(Config(n_vents=0, diagnostic_placement="vent"), 1)


# --- 保存則 (診断条件でも壊れない) ------------------------------------

@pytest.mark.parametrize("condition", ["A", "B", "C", "D"])
def test_matter_is_conserved_in_all_conditions(condition):
    sim = Simulation(cfg_for(condition), 1)
    m0 = sim.initial_system_matter
    for _ in range(200):
        sim.step()
    assert sim.system_matter() == pytest.approx(m0, rel=1e-9)
