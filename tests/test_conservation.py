"""仕様書 §13: 物質の厳密保存とエネルギー台帳の整合。"""
import pytest

from evosim.config import Config
from evosim.disasters import random_disaster
from evosim.simulation import Simulation


def test_matter_conserved():
    sim = Simulation(Config(), 7)
    m0 = sim.initial_system_matter
    for i in range(600):
        sim.step()
        if i % 100 == 0:
            assert sim.system_matter() == pytest.approx(m0, rel=1e-9)
    assert sim.system_matter() == pytest.approx(m0, rel=1e-9)


def test_energy_ledger():
    sim = Simulation(Config(), 7)
    e0 = sim.initial_system_energy
    for _ in range(600):
        sim.step()
    expected = e0 + sim.energy_in_cum - sim.energy_out_cum
    assert sim.system_energy() == pytest.approx(expected, rel=1e-6, abs=1e-3)


def test_resource_flows_are_bounded():
    """資源フロー計上 (改善方針 Ver.1.2 §5) が物理的にあり得る範囲に収まるか。"""
    sim = Simulation(Config(), 7)
    for _ in range(400):
        sim.step()

    assert all(v >= 0.0 for v in sim.flows.values()), "資源フローに負値がある"

    # 光の利用累計は供給累計を超えられない
    supplied = sim.light_supply_per_tick * sim.tick
    assert sim.flows["light"] <= supplied + 1e-6

    # 光由来のエネルギーは外部流入なので、流入台帳の一部でなければならない
    assert sim.flows["light"] <= sim.energy_in_cum + 1e-6

    # 生体が獲得した物質は世界の総物質量を超えられない
    assert sim.flows["nutrient"] <= sim.initial_system_matter * sim.tick


def test_lineage_births_match_total():
    """系統別出生数の合計が全体の出生数と一致するか。"""
    sim = Simulation(Config(), 7)
    for _ in range(400):
        sim.step()
    assert sum(sim.births_by_lineage.values()) == sim.births_cum


def test_matter_conserved_through_disaster():
    sim = Simulation(Config(), 11)
    m0 = sim.initial_system_matter
    for _ in range(200):
        sim.step()
    random_disaster(sim)
    for _ in range(200):
        sim.step()
    assert sim.system_matter() == pytest.approx(m0, rel=1e-9)
