"""V1.4 一次Energy吸収則のテスト。

正本: `docs/V1.4_一次エネルギー吸収仕様.md` §11 (実装テスト要件)

守るもの:
- 有効表面積 `A_eff = matter^(2/3)` を光/化学/無機栄養で共通に使う
- 光は個体の変換能力が上限になり、低能力の単独個体がセル光を全取得しない
- 供給不足時はセル内の需要比例配分で、個体リスト順に依存しない
- 総取得は必ず `min(供給, 総需要)`
- 無機栄養は同化コストでEnergyを負にせず、Matterを保存する
- 光/化学/無機栄養はすべて移動後のセルを参照する
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evosim.config import Config
from evosim.genome import (CHEM_ABS, LIGHT_ABS, NUTRIENT_ABS, PREDATION,
                           CORPSE_DIG)
from evosim.organism import Organism
from evosim.physiology import density_response, effective_surface
from evosim.simulation import Simulation


# --- 有効表面積 ------------------------------------------------------

@pytest.mark.parametrize("matter,expected", [
    (1.0, 1.0),
    (8.0, 4.0),
    (0.125, 0.25),
])
def test_effective_surface_is_two_thirds_power(matter, expected):
    assert effective_surface(matter) == pytest.approx(expected, rel=1e-12)


def test_effective_surface_ratio_for_eight_fold_volume():
    """体積8倍で交換面は4倍 (8倍ではない)。"""
    assert (effective_surface(8.0) / effective_surface(1.0)
            == pytest.approx(4.0, rel=1e-12))


def test_effective_surface_is_finite_at_zero_matter():
    assert effective_surface(0.0) > 0.0
    assert math.isfinite(effective_surface(0.0))


def test_surface_exceeds_matter_below_one():
    """matter<1では A_eff > matter。交差点は matter=1 (仕様上の既知の性質)。"""
    assert effective_surface(0.8) > 0.8
    assert effective_surface(2.0) < 2.0


# --- テスト用の最小構成 ----------------------------------------------

def _bare_config(**kw) -> Config:
    """吸収だけを見るための静止世界 (光0・化学0・栄養0がdefault)。"""
    base = dict(light_pattern="uniform", light_max=0.0, h2_vent_flux=0.0,
                nutrient_initial=0.0, initial_population=0)
    base.update(kw)
    return Config(**base)


def _place(sim: Simulation, cell, n: int, gene_idx: int, ability: float,
           matter: float = 0.8, energy: float = 10.0) -> list[Organism]:
    """指定セルへ同一状態の個体をn体置く (乱数を使わない)。"""
    cs = sim.cfg.cell_size
    orgs = []
    for _ in range(n):
        g = np.zeros(17)
        g[0] = 1.0            # body_size
        g[3] = 1.0            # movement_efficiency
        g[14] = 1.0           # storage_capacity (E_max>0)
        g[gene_idx] = ability
        o = Organism(sim.next_id, -1, sim.next_id, 0, 0, g,
                     (cell[0] + 0.5) * cs, (cell[1] + 0.5) * cs, 0.0,
                     energy, matter)
        sim.next_id += 1
        sim.organisms.append(o)
        orgs.append(o)
    sim._build_hashes()
    return orgs


# --- 光 --------------------------------------------------------------

def test_lone_low_ability_organism_does_not_take_whole_cell_light():
    """V1.3以前の欠陥: 単独個体が低能力でもセル光を全取得していた。"""
    cfg = _bare_config(light_max=1.2, light_uptake_coef=2.0)
    sim = Simulation(cfg, 1)
    (o,) = _place(sim, (5, 5), 1, LIGHT_ABS, 0.3)
    e0 = o.energy
    sim._absorb_fields()
    gain = o.energy - e0
    flux = float(sim.world.light[5, 5])
    resp = density_response(flux, cfg.light_uptake_half)  # V1.9: 常時適用
    expected = cfg.light_uptake_coef * 0.3 * effective_surface(0.8) * resp
    assert gain == pytest.approx(expected, rel=1e-12)
    assert gain < flux
    assert sim.flows["light"] == pytest.approx(gain, rel=1e-12)


def test_demand_scales_with_ability_and_coefficient():
    for coef in (1.0, 2.0, 4.0):
        cfg = _bare_config(light_max=100.0, light_uptake_coef=coef)
        sim = Simulation(cfg, 1)
        (o,) = _place(sim, (5, 5), 1, LIGHT_ABS, 2.0, energy=0.0)
        resp = density_response(float(sim.world.light[5, 5]), cfg.light_uptake_half)
        sim._absorb_fields()
        assert o.energy == pytest.approx(
            coef * 2.0 * effective_surface(0.8) * resp, rel=1e-9)


def test_unused_light_is_left_when_demand_is_below_supply():
    cfg = _bare_config(light_max=1.2, light_uptake_coef=1.0)
    sim = Simulation(cfg, 1)
    orgs = _place(sim, (5, 5), 2, LIGHT_ABS, 0.1)
    sim._absorb_fields()
    taken = sum(o.energy - 10.0 for o in orgs)
    assert taken < float(sim.world.light[5, 5])
    assert sim.flows["light"] == pytest.approx(taken, rel=1e-9)


def test_total_light_take_equals_supply_when_demand_exceeds_it():
    cfg = _bare_config(light_max=1.2, light_uptake_coef=2.0)
    sim = Simulation(cfg, 1)
    orgs = _place(sim, (5, 5), 20, LIGHT_ABS, 2.0)
    sim._absorb_fields()
    taken = math.fsum(o.energy - 10.0 for o in orgs)
    assert taken == pytest.approx(1.2, rel=1e-12)
    # 需要比例なので同一状態の個体は同じ量を取る
    gains = [o.energy - 10.0 for o in orgs]
    assert max(gains) - min(gains) < 1e-15


def test_light_energy_capacity_caps_demand():
    """Energy空き容量が上限。満杯の個体は光を取らない。"""
    cfg = _bare_config(light_max=100.0, light_uptake_coef=4.0)
    sim = Simulation(cfg, 1)
    (o,) = _place(sim, (5, 5), 1, LIGHT_ABS, 5.0,
                  energy=cfg.energy_capacity_base * 0.8)
    sim._absorb_fields()
    assert o.energy == pytest.approx(o.energy_max(cfg.energy_capacity_base), rel=1e-12)


@pytest.mark.parametrize("n", [1, 5, 20, 100])
def test_light_allocation_is_independent_of_list_order(n):
    """個体リスト順を変えても各個体の取得量は同じ (先着biasなし)。"""
    shuffler = np.random.Generator(np.random.PCG64(12345))  # Simulation.rng とは別

    def run(order):
        cfg = _bare_config(light_max=1.2, light_uptake_coef=2.0)
        sim = Simulation(cfg, 1)
        orgs = _place(sim, (5, 5), n, LIGHT_ABS, 2.0)
        for i, o in enumerate(orgs):       # 個体ごとに違う状態を与える
            o.energy = 5.0 + 0.5 * i
            o.matter = 0.5 + 0.05 * i
        tagged = list(enumerate(orgs))
        sim.organisms = [o for _, o in [tagged[i] for i in order]]
        sim._build_hashes()
        sim._absorb_fields()
        return {i: o.energy - (5.0 + 0.5 * i) for i, o in tagged}

    forward = list(range(n))
    reverse = forward[::-1]
    shuffled = list(shuffler.permutation(n))
    base = run(forward)
    for order in (reverse, shuffled):
        got = run(order)
        assert got.keys() == base.keys()
        for k in base:
            assert got[k] == pytest.approx(base[k], rel=1e-12, abs=1e-15)


# --- 化学 ------------------------------------------------------------

def test_chemical_demand_uses_effective_surface():
    """V1.9: H2は substrate であり、usable Energy = raw*resp*yield*conversion_eff。"""
    cfg = _bare_config(h2_vent_flux=8.0)
    sim = Simulation(cfg, 1)
    vent = tuple(np.argwhere(sim.world.h2_mask)[0])
    cell = (int(vent[0]), int(vent[1]))
    (o,) = _place(sim, cell, 1, CHEM_ABS, 2.0, energy=0.0)
    resp = density_response(float(sim.world.h2[cell]), cfg.h2_uptake_half)
    sim._absorb_fields()
    raw = cfg.h2_uptake_coef * 2.0 * effective_surface(0.8) * resp
    expected = raw * cfg.h2_energy_yield * cfg.h2_conversion_eff
    assert o.energy == pytest.approx(expected, rel=1e-9)


def test_chemical_total_take_never_exceeds_stock():
    """全substrate取得量 (energy-equivalentではなくsubstrate量) がstockを超えない。"""
    cfg = _bare_config(h2_vent_flux=8.0)
    sim = Simulation(cfg, 1)
    vent = np.argwhere(sim.world.h2_mask)[0]
    cell = (int(vent[0]), int(vent[1]))
    stock = float(sim.world.h2[cell])
    orgs = _place(sim, cell, 60, CHEM_ABS, 5.0, energy=0.0)
    sim._absorb_fields()
    energy_taken = math.fsum(o.energy for o in orgs)
    substrate_taken = energy_taken / (cfg.h2_energy_yield * cfg.h2_conversion_eff)
    assert substrate_taken <= stock + 1e-9
    assert substrate_taken == pytest.approx(stock, rel=1e-6)
    remaining = float(sim.world.h2[cell])
    assert remaining >= 0.0
    assert remaining == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize("n", [5, 100])
def test_chemical_allocation_is_independent_of_list_order(n):
    shuffler = np.random.Generator(np.random.PCG64(999))

    def run(order):
        cfg = _bare_config(h2_vent_flux=8.0)
        sim = Simulation(cfg, 1)
        vent = np.argwhere(sim.world.h2_mask)[0]
        cell = (int(vent[0]), int(vent[1]))
        orgs = _place(sim, cell, n, CHEM_ABS, 2.0, energy=0.0)
        for i, o in enumerate(orgs):
            o.matter = 0.4 + 0.03 * i
        tagged = list(enumerate(orgs))
        sim.organisms = [o for _, o in [tagged[i] for i in order]]
        sim._build_hashes()
        sim._absorb_fields()
        return {i: o.energy for i, o in tagged}

    base = run(list(range(n)))
    for order in (list(range(n))[::-1], list(shuffler.permutation(n))):
        got = run(order)
        for k in base:
            assert got[k] == pytest.approx(base[k], rel=1e-12, abs=1e-15)


# --- 無機栄養 --------------------------------------------------------

def test_nutrient_demand_uses_effective_surface():
    cfg = _bare_config(nutrient_initial=100.0)
    sim = Simulation(cfg, 1)
    (o,) = _place(sim, (5, 5), 1, NUTRIENT_ABS, 0.5, energy=50.0)
    m0 = o.matter
    sim._absorb_fields()
    expected = cfg.nutrient_uptake * 0.5 * effective_surface(m0)
    assert o.matter - m0 == pytest.approx(expected, rel=1e-12)


def test_nutrient_take_never_exceeds_demand_or_stock():
    cfg = _bare_config(nutrient_initial=0.05)
    sim = Simulation(cfg, 1)
    orgs = _place(sim, (5, 5), 10, NUTRIENT_ABS, 2.0, energy=50.0)
    m0 = [o.matter for o in orgs]
    sim._absorb_fields()
    gains = [o.matter - m for o, m in zip(orgs, m0)]
    demand_each = cfg.nutrient_uptake * 2.0 * effective_surface(0.8)
    assert all(g <= demand_each + 1e-15 for g in gains)
    assert math.fsum(gains) == pytest.approx(0.05, rel=1e-9)
    assert float(sim.world.nutrients[5, 5]) == pytest.approx(0.0, abs=1e-12)


def test_nutrient_assimilation_never_drives_energy_negative():
    """同化コストを払えない個体は、払える分しか吸収しない。"""
    cfg = _bare_config(nutrient_initial=100.0)
    sim = Simulation(cfg, 1)
    (o,) = _place(sim, (5, 5), 1, NUTRIENT_ABS, 5.0, energy=0.02)
    m0, e0 = o.matter, o.energy
    sim._absorb_fields()
    assert o.energy >= 0.0
    assert o.matter - m0 == pytest.approx(e0 / cfg.matter_absorb_cost, rel=1e-12)
    assert o.energy == pytest.approx(0.0, abs=1e-15)


def test_nutrient_matter_room_caps_demand():
    cfg = _bare_config(nutrient_initial=100.0)
    sim = Simulation(cfg, 1)
    cap = cfg.matter_cap_frac * 1.0
    (o,) = _place(sim, (5, 5), 1, NUTRIENT_ABS, 5.0,
                  matter=cap - 0.001, energy=50.0)
    sim._absorb_fields()
    assert o.matter <= cap + 1e-15
    assert o.matter == pytest.approx(cap, rel=1e-12)


@pytest.mark.parametrize("n", [5, 20])
def test_nutrient_allocation_is_independent_of_list_order(n):
    shuffler = np.random.Generator(np.random.PCG64(4242))

    def run(order):
        cfg = _bare_config(nutrient_initial=0.05)
        sim = Simulation(cfg, 1)
        orgs = _place(sim, (5, 5), n, NUTRIENT_ABS, 2.0, energy=50.0)
        for i, o in enumerate(orgs):
            o.matter = 0.4 + 0.02 * i
        tagged = list(enumerate(orgs))
        start = {i: o.matter for i, o in tagged}
        sim.organisms = [o for _, o in [tagged[i] for i in order]]
        sim._build_hashes()
        sim._absorb_fields()
        return {i: o.matter - start[i] for i, o in tagged}

    base = run(list(range(n)))
    for order in (list(range(n))[::-1], list(shuffler.permutation(n))):
        got = run(order)
        for k in base:
            assert got[k] == pytest.approx(base[k], rel=1e-12, abs=1e-15)


# --- 参照時点 (post-moveセル) ----------------------------------------

def test_all_fields_are_absorbed_at_the_post_move_cell():
    """光/化学/無機栄養がすべて移動後のセルから吸収される (V1.4 §8)。

    移動前セルは供給0、移動後セルにだけ供給がある世界を作り、1 tick後に
    3資源すべてを取得できていることを見る。V1.3以前は光だけ移動前セルを
    参照していたため、この配置では光を取得できなかった。
    """
    cfg = _bare_config(light_max=0.0, nutrient_initial=0.0,
                       light_uptake_coef=2.0, wander_speed_frac=0.0)
    sim = Simulation(cfg, 1)
    cs = cfg.cell_size
    src, dst = (5, 5), (6, 5)
    sim.world.light[dst] = 1.0
    sim.world.h2[dst] = 5.0
    sim.world.nutrients[dst] = 5.0
    g = np.zeros(17)
    g[0] = 1.0            # body_size
    g[2] = 1.0            # movement_power
    g[3] = 1.0            # movement_efficiency
    g[4] = 2.0            # sensory_range (隣接セルを感知できる)
    g[14] = 1.0           # storage_capacity (E_max>0)
    g[LIGHT_ABS] = 1.0
    g[CHEM_ABS] = 1.0
    g[NUTRIENT_ABS] = 1.0
    o = Organism(0, -1, 0, 0, 0, g,
                 (src[0] + 0.9) * cs, (src[1] + 0.5) * cs, 0.0, 20.0, 0.8)
    sim.organisms.append(o)
    sim.next_id = 1

    sim.step()

    assert sim.world.cell_index(o.x, o.y) == dst, "移動していない"
    assert sim.flows["light"] > 0.0, "移動後セルの光を取得していない"
    assert sim.flows["h2"] > 0.0
    assert sim.flows["nutrient"] > 0.0


# --- 保存則 ----------------------------------------------------------

def test_energy_ledger_holds_under_v14_absorption():
    sim = Simulation(Config(), 3)
    for _ in range(400):
        sim.step()
    expected = sim.initial_system_energy + sim.energy_in_cum - sim.energy_out_cum
    assert sim.system_energy() == pytest.approx(expected, rel=1e-9, abs=1e-6)


def test_matter_is_conserved_under_v14_absorption():
    sim = Simulation(Config(), 3)
    m0 = sim.initial_system_matter
    for _ in range(400):
        sim.step()
    assert sim.system_matter() == pytest.approx(m0, rel=1e-9)


def test_light_flow_never_exceeds_supply():
    """未利用光が生じるのが新仕様。利用率は1を超えない。"""
    sim = Simulation(Config(), 5)
    for _ in range(300):
        sim.step()
    supplied = sim.light_supply_per_tick * sim.tick
    assert sim.flows["light"] <= supplied + 1e-6
    assert sim.flows["light"] < supplied, "未利用光が全く出ないのは想定外"


def test_chemical_stock_never_negative_with_many_absorbers():
    cfg = Config(light_pattern="uniform", light_max=0.0, h2_vent_flux=8.0,
                 diagnostic_placement="vent",
                 fixed_genes=["chemical_absorption"],
                 diagnostic_gene_overrides={"chemical_absorption": 2.0})
    sim = Simulation(cfg, 1)
    for _ in range(300):
        sim.step()
        assert float(sim.world.h2.min()) >= 0.0
