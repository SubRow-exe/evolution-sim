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


def test_matter_conserved_through_disaster():
    sim = Simulation(Config(), 11)
    m0 = sim.initial_system_matter
    for _ in range(200):
        sim.step()
    random_disaster(sim)
    for _ in range(200):
        sim.step()
    assert sim.system_matter() == pytest.approx(m0, rel=1e-9)
