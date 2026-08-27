"""既定設定で個体群が成立するか (Exp 0 の縮小版)。"""
from evosim.config import Config
from evosim.simulation import Simulation


def test_population_survives_1000_ticks():
    sim = Simulation(Config(), 1)
    for _ in range(1000):
        sim.step()
    assert len(sim.organisms) > 0, "個体群が1000tick以内に絶滅した"


def test_reproduction_happens():
    sim = Simulation(Config(), 1)
    for _ in range(1000):
        sim.step()
    assert sim.births_cum > sim.cfg.initial_population, "繁殖が一度も発生していない"


def test_no_mutation_stable():
    """Exp 0: 突然変異を殺した状態でも生態力学が成立するか。"""
    cfg = Config(initial_jitter_sigma=0.0, additive_mutation_frac=0.0,
                 meta_mutation_sigma=0.0)
    sim = Simulation(cfg, 3)
    # mutation_rate 遺伝子はゼロにできないが σ→最小値なら実質無変異
    for o in sim.organisms:
        o.genome[-1] = 0.005
    for _ in range(1500):
        sim.step()
    n = len(sim.organisms)
    assert 0 < n < 20_000, f"個体数が異常 ({n})"
