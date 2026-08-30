"""V1.3 chemical source モデルの検証 (docs/V1.3_化学資源モデル仕様.md §11)。

V1.3のchemicalは「地質sourceから一定fluxで供給され、局所stockとして滞留し、
一次の環境損失で失われる」一次Energy sourceである。

特に重要なのは次の2点。

- **実効source == 公称source**: 世界へ実際に入るchemicalは常に
  `n_vents * chem_vent_flux` であり、vent配置 (seed) に依存しない。
  stockに上限 (capacity) を置くと、端で欠けたventや重複セルで
  1セルあたりsourceが上がり、超過分が捨てられてseed依存の損失になる。
  V1.3はcapacityを持たず、損失項だけでstockを有限化することでこれを避ける。
- **初期stockは更新式の不動点**: 生物がいなければstockは動かない。
  「開始時だけ大量のstockがある」人工的パルスを作らない。
"""
import numpy as np
import pytest

from evosim.config import Config
from evosim.genome import CHEM_ABS
from evosim.simulation import Simulation
from evosim.world import World

EXP07_FLUX = (4.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0)
SEEDS = range(1, 11)


def world_for(seed: int, **kw) -> World:
    cfg = Config(**kw)
    return World(cfg, np.random.Generator(np.random.PCG64(seed)))


# --- source field -----------------------------------------------------

@pytest.mark.parametrize("flux", EXP07_FLUX)
def test_world_source_total_is_exact(flux):
    """どのseed・どのfluxでも世界総source = n_vents * chem_vent_flux。"""
    for seed in SEEDS:
        w = world_for(seed, chem_vent_flux=flux)
        assert w.chem_source_flux.sum() == pytest.approx(
            w.cfg.n_vents * flux, rel=1e-12), f"seed {seed}"
        assert w.chem_source_total == pytest.approx(w.cfg.n_vents * flux, rel=1e-12)


def test_single_vent_keeps_total_flux_at_edges():
    """円盤がworld edgeで欠けても、その1 ventの総fluxは変わらない。

    欠けた分は残りのセルへ寄せる。総量をseedに依存させないため。
    """
    seen_clipped = False
    for seed in range(1, 60):
        w = world_for(seed, n_vents=1, chem_vent_flux=8.0)
        assert w.chem_source_flux.sum() == pytest.approx(8.0, rel=1e-12)
        n_cells = int(w.chem_mask.sum())
        assert n_cells <= 13
        if n_cells < 13:
            seen_clipped = True
    assert seen_clipped, "端で欠けるケースが1つも出ていない (テストが無意味)"


def test_overlapping_vents_add_contributions():
    """vent同士が重なるセルでは各ventの寄与が加算される (取りこぼさない)。"""
    w = world_for(1, chem_vent_flux=8.0)          # seed 1 は 4セルが2重被覆
    assert int(w.chem_mask.sum()) < 13 * w.cfg.n_vents, "重複が無いseed"
    assert w.chem_source_flux.sum() == pytest.approx(4 * 8.0, rel=1e-12)
    share = 8.0 / 13.0
    assert w.chem_source_flux.max() > share * 1.5, "重複セルが加算されていない"


def test_no_source_outside_vents():
    w = world_for(3)
    assert np.all(w.chem_source_flux[~w.chem_mask] == 0.0)
    assert np.all(w.chem_source_flux[w.chem_mask] > 0.0)


def test_vent_generation_consumes_same_rng_as_before():
    """vent中心の抽選は1 ventにつき整数2つ。乱数消費を増やしていない。

    増やすと同一seedの初期個体配置や変異系列がずれ、条件間比較が壊れる。
    """
    cfg = Config()
    a = np.random.Generator(np.random.PCG64(11))
    World(cfg, a)
    b = np.random.Generator(np.random.PCG64(11))
    for _ in range(cfg.n_vents):
        b.integers(0, cfg.grid_w)
        b.integers(0, cfg.grid_h)
    assert a.bit_generator.state == b.bit_generator.state


# --- stock の力学 -----------------------------------------------------

@pytest.mark.parametrize("flux", EXP07_FLUX)
def test_initial_stock_is_the_fixed_point(flux):
    """初期stock = S/loss は更新式の不動点。生物不在ならstockは動かない。"""
    w = world_for(2, chem_vent_flux=flux)
    expected = w.chem_source_flux / w.cfg.chem_loss_frac
    assert np.allclose(w.chemical, expected, rtol=1e-12)
    before = w.chemical.copy()
    for _ in range(100):
        w.update()
    assert np.allclose(w.chemical, before, atol=1e-9)


@pytest.mark.parametrize("flux", EXP07_FLUX)
def test_influx_is_constant_and_equals_nominal(flux):
    """毎tickの実効influxは公称値と一致し、stock状態に依存しない。"""
    w = world_for(4, chem_vent_flux=flux)
    nominal = w.cfg.n_vents * flux
    w.chemical[:] = 0.0                      # 生物が食い尽くした状態
    for _ in range(5):
        influx, loss = w.update()
        assert influx == pytest.approx(nominal, rel=1e-12)
    w.chemical *= 3.0                        # stockが厚い状態
    influx, _ = w.update()
    assert influx == pytest.approx(nominal, rel=1e-12)


def test_source_continues_from_zero_stock():
    w = world_for(5)
    w.chemical[:] = 0.0
    w.update()
    assert np.allclose(w.chemical[w.chem_mask],
                       w.chem_source_flux[w.chem_mask], rtol=1e-12)
    assert np.all(w.chemical[~w.chem_mask] == 0.0)


def test_stock_returns_to_equilibrium_after_depletion():
    w = world_for(6)
    eq = w.chemical.copy()
    w.chemical[:] = 0.0
    for _ in range(300):
        w.update()
    assert np.allclose(w.chemical, eq, rtol=1e-6)


def test_stock_is_never_negative_and_non_vent_cells_stay_zero():
    w = world_for(7)
    for _ in range(200):
        w.update()
        assert np.all(w.chemical >= 0.0)
        assert np.all(w.chemical[~w.chem_mask] == 0.0)


@pytest.mark.parametrize("flux", (48.0, 64.0, 200.0))
def test_stock_is_not_clipped(flux):
    """stockに上限は無い。高fluxでも S/loss まで素直に積み上がる。

    上限クリップがあると、端で欠けたventや重複セルの超過分が捨てられ、
    実効sourceがseed依存で最大10%変わってしまう (§3.2)。
    """
    for seed in SEEDS:
        w = world_for(seed, chem_vent_flux=flux)
        expected_max = w.chem_source_flux.max() / w.cfg.chem_loss_frac
        assert w.chemical.max() == pytest.approx(expected_max, rel=1e-12)
        # 平衡へ向かう過程でも捨てられない: influx は常に公称どおり
        influx, _ = w.update()
        assert influx == pytest.approx(w.cfg.n_vents * flux, rel=1e-12)


# --- Energy台帳 -------------------------------------------------------

def test_ledger_counts_source_in_and_loss_out():
    w = world_for(8)
    influx, loss = w.update()
    assert influx == pytest.approx(w.chem_source_total, rel=1e-12)
    # 平衡から始まるので、初回の損失は供給と釣り合う
    assert loss == pytest.approx(influx, rel=1e-9)


@pytest.mark.parametrize("flux", (4.0, 16.0, 64.0))
def test_energy_conservation_with_chemical_source(flux):
    """外部流入と散逸を差し引けば系のEnergyが閉じる (chemical条件でも)。"""
    cfg = Config(light_pattern="uniform", light_max=0.0, chem_vent_flux=flux)
    sim = Simulation(cfg, 1)
    e0 = sim.initial_system_energy
    for _ in range(300):
        sim.step()
    expected = e0 + sim.energy_in_cum - sim.energy_out_cum
    assert sim.system_energy() == pytest.approx(expected, rel=1e-9)


def test_matter_conservation_with_chemical_source():
    cfg = Config(light_pattern="uniform", light_max=0.0, chem_vent_flux=16.0)
    sim = Simulation(cfg, 1)
    m0 = sim.initial_system_matter
    for _ in range(300):
        sim.step()
    assert sim.system_matter() == pytest.approx(m0, rel=1e-9)


# --- 生物との相互作用 -------------------------------------------------

def test_organisms_deplete_stock_but_not_source():
    """生物がstockを減らしても、次tickのsource量は変わらない。"""
    cfg = Config(light_pattern="uniform", light_max=0.0, chem_vent_flux=8.0,
                 diagnostic_placement="vent",
                 fixed_genes=["chemical_absorption"],
                 diagnostic_gene_overrides={"chemical_absorption": 2.0})
    sim = Simulation(cfg, 1)
    total_before = float(sim.world.chemical.sum())
    for _ in range(30):
        sim.step()
    assert float(sim.world.chemical.sum()) < total_before, "消費されていない"
    assert sim.world.chem_source_total == pytest.approx(
        cfg.n_vents * cfg.chem_vent_flux, rel=1e-12)
    influx, _ = sim.world.update()
    assert influx == pytest.approx(cfg.n_vents * cfg.chem_vent_flux, rel=1e-12)
    assert all(o.genome[CHEM_ABS] == 2.0 for o in sim.organisms)
