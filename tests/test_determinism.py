"""原則7: 同一Seedで完全再現できるか。"""
from evosim.config import Config
from evosim.simulation import Simulation


def state_checksum(sim: Simulation) -> tuple:
    orgs = tuple(
        (o.id, round(o.x, 9), round(o.y, 9), round(o.energy, 9),
         round(o.matter, 9), round(o.damage, 9))
        for o in sim.organisms)
    return (sim.tick, sim.births_cum, sim.deaths_cum,
            round(sim.world.total_nutrients(), 9),
            round(sim.world.total_chemical(), 9), orgs)


def run(seed: int, ticks: int) -> tuple:
    sim = Simulation(Config(), seed)
    for _ in range(ticks):
        sim.step()
    return state_checksum(sim)


def test_same_seed_identical():
    assert run(42, 400) == run(42, 400)


def test_different_seed_differs():
    assert run(42, 200) != run(43, 200)
