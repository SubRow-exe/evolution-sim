"""Exp14向けrecorder追加列の観測非干渉テスト (実装チェックリスト.md §6)。

recorder ON/OFFで同一seedのシミュレーション軌跡 (population, RNG消費回数)
が完全一致することを確認する。energy_frac / trait percentile 列の追加は
読み取り専用集計であり、RNG・個体状態・update orderに一切影響しない
はず。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config
from evosim.recorder import Recorder
from evosim.simulation import Simulation


def _run(seed, ticks, use_recorder, tmp_path):
    cfg = Config(initial_population=15, stats_interval=5, snapshot_interval=1000,
                 light_cycle_enabled=True)
    run_dir = tmp_path / f"run_{use_recorder}"
    sim = Simulation(cfg, seed=seed, run_dir=run_dir)
    if use_recorder:
        rec = Recorder(run_dir, cfg, seed)
        sim.recorder = rec
    for _ in range(ticks):
        sim.step()
    if use_recorder:
        sim.recorder.finalize(sim)
        sim.recorder.close()
    return sim


def test_recorder_on_off_same_seed_identical_trajectory(tmp_path):
    sim_on = _run(1, 60, True, tmp_path)
    sim_off = _run(1, 60, False, tmp_path)

    assert sim_on.tick == sim_off.tick
    assert len(sim_on.organisms) == len(sim_off.organisms)
    assert sim_on.births_cum == sim_off.births_cum
    assert sim_on.deaths_cum == sim_off.deaths_cum
    # RNG消費回数が同じであることの代理指標: 同一seedで同じ乱数列を
    # 消費していれば、その後の1回のuniform呼び出し結果も一致する。
    assert sim_on.rng.uniform() == sim_off.rng.uniform()

    ids_on = sorted((o.id, round(o.x, 6), round(o.y, 6), round(o.energy, 6))
                    for o in sim_on.organisms)
    ids_off = sorted((o.id, round(o.x, 6), round(o.y, 6), round(o.energy, 6))
                     for o in sim_off.organisms)
    assert ids_on == ids_off


def test_energy_frac_and_trait_percentile_columns_present(tmp_path):
    cfg = Config(initial_population=15, stats_interval=5, snapshot_interval=1000,
                 light_cycle_enabled=True)
    run_dir = tmp_path / "run"
    sim = Simulation(cfg, seed=1, run_dir=run_dir)
    rec = Recorder(run_dir, cfg, 1)
    sim.recorder = rec
    for _ in range(10):
        sim.step()
    rec.finalize(sim)
    rec.close()

    import csv
    with open(run_dir / "stats.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        rows = list(reader)
    for col in ("energy_frac_mean", "energy_frac_median", "energy_frac_p10",
                "energy_frac_p90", "p10_body_size", "p90_body_size",
                "p10_reproduction_investment", "p90_reproduction_investment",
                "p10_movement_power", "p90_movement_power"):
        assert col in header
    assert len(rows) >= 1
