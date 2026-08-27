"""災害 (仕様書 Ver.1.1 §10)。

ランダム災害: 遺伝子を一切参照せず個体をランダムに死亡させる。
目的はボトルネック効果・遺伝的浮動の観察。
"""
from __future__ import annotations

from .simulation import Simulation


def random_disaster(sim: Simulation, kill_frac: float | None = None) -> int:
    """個体の kill_frac をランダムに死亡させる (死骸化)。戻り値: 死亡数。"""
    frac = sim.cfg.disaster_kill_frac if kill_frac is None else kill_frac
    alive = [o for o in sim.organisms if o.alive]
    n_kill = int(len(alive) * frac)
    if n_kill <= 0:
        return 0
    idx = sim.rng.choice(len(alive), size=n_kill, replace=False)
    for i in sorted(int(j) for j in idx):
        sim._kill(alive[i], "disaster")
    sim.organisms = [o for o in sim.organisms if o.alive]
    if sim.recorder:
        sim.recorder.disaster(sim.tick, n_kill)
    return n_kill
