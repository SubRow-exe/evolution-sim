"""V1.2.1 観測機能の結果不変性 (docs/V1.2_V1.2.1_詳細実装仕様.md §8)。

空間観測・環境スナップショット・移動量集計は**読み取り専用の記録**であり、
乱数を消費せず個体・環境の状態を書き換えてはならない。

観測ONとOFFで科学的状態が1ビットでも違えば、Exp05のControl/Treatment比較に
「観測したかどうか」という交絡が入ってしまう。
"""
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evosim.config import Config
from evosim.simulation import Simulation
from tools.golden import fingerprint

CASES = [
    ("control", {}, 1, 900),
    ("treatment", {"light_pattern": "high_contrast_vertical"}, 1, 900),
    ("treatment_dense", {"light_pattern": "high_contrast_vertical",
                         "initial_population": 300}, 5, 400),
]


def _run(overrides: dict, seed: int, ticks: int, record: bool):
    """record=True なら観測を全て有効にして実行する。"""
    tmp = Path(tempfile.mkdtemp(prefix="evosim_obs_")) if record else None
    try:
        cfg = Config(snapshot_interval=100, **overrides) if record \
            else Config(**overrides)
        sim = Simulation(cfg, seed, run_dir=(tmp / "run") if record else None)
        for _ in range(ticks):
            sim.step()
        fp = fingerprint(sim)
        state = {
            "tick": sim.tick,
            "population": len(sim.organisms),
            "births": sim.births_cum,
            "deaths": sim.deaths_cum,
            "orgs": [(o.id, o.x, o.y, o.energy, o.matter, o.damage,
                      tuple(float(g) for g in o.genome)) for o in sim.organisms],
            "chemical": sim.world.chemical.copy(),
            "nutrients": sim.world.nutrients.copy(),
            "rng": sim.rng.bit_generator.state,
        }
        sim.close()
        return fp, state
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.parametrize("name,overrides,seed,ticks", CASES,
                         ids=[c[0] for c in CASES])
def test_observation_does_not_change_results(name, overrides, seed, ticks):
    fp_on, on = _run(overrides, seed, ticks, record=True)
    fp_off, off = _run(overrides, seed, ticks, record=False)

    assert fp_on == fp_off, f"{name}: 観測ON/OFFで指紋が異なる"
    assert on["tick"] == off["tick"]
    assert on["population"] == off["population"]
    assert on["births"] == off["births"]
    assert on["deaths"] == off["deaths"]
    assert on["orgs"] == off["orgs"], "個体のid/順序/位置/状態/遺伝子が一致しない"
    assert np.array_equal(on["chemical"], off["chemical"])
    assert np.array_equal(on["nutrients"], off["nutrients"])
    assert on["rng"] == off["rng"], "乱数状態が一致しない (観測がRNGを消費した)"


def test_spatial_metrics_do_not_touch_state():
    """空間指標の計算そのものが個体・環境・RNGを変えないこと。"""
    from evosim.spatial import lineage_spatial, population_spatial

    sim = Simulation(Config(light_pattern="high_contrast_vertical"), 3)
    for _ in range(200):
        sim.step()

    before = fingerprint(sim)
    rng_before = sim.rng.bit_generator.state

    population_spatial(sim)
    by_lineage: dict[int, list] = {}
    for o in sim.organisms:
        by_lineage.setdefault(o.lineage_id, []).append(o)
    for members in by_lineage.values():
        lineage_spatial(sim, members)

    assert fingerprint(sim) == before, "空間指標の計算が状態を変えた"
    assert sim.rng.bit_generator.state == rng_before, "空間指標がRNGを消費した"
