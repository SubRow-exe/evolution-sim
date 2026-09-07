"""baseline条件を4 physical days走らせ、Matter (nutrient場 + 個体) の配分と
H2場の中央値、E/E_max を追跡する。

確認したいこと: (1) Matterは閉じた有限ループか (2) 生物はH2場を削るか
(3) 個体は保護reserveに張り付いているか。

Opus 5 ロードマップレビュー時の検証スクリプト。シミュレーション実験ではなく
解析・短時間診断であり、正式実験ではない。

前提: V1.9 LUCA proxy 実装 (branch claude/pr-50-v1.6-exp11-iuhnzm) のツリー上で実行する。
    EVOSIM_ROOT=<そのworktree> uv run python <this file>

考察の正本: docs/V1.9_ロードマップ_Opus5レビュー.md
"""
import os
import sys, time
from pathlib import Path
ROOT = Path(os.environ.get("EVOSIM_ROOT", Path(__file__).resolve().parents[2]))
for p in (ROOT, ROOT/"experiments"/"luca_proxy", ROOT/"experiments"/"exp15_v19"):
    sys.path.insert(0, str(p))
import numpy as np, run_luca_proxy as luca

sim = luca.base.setup_sim("A", 15001)
cfg = sim.cfg
DAYS = 4.0
steps = int(DAYS*86400/cfg.dt_seconds)
t0 = time.time()
print(f"{'day':>5} {'N':>6} {'nutrient':>10} {'inOrg':>8} {'meanM':>7} {'meanE/Emax':>11} {'medH2':>7}")
for k in range(1, steps+1):
    sim.step()
    if not sim.organisms: print("EXTINCT at day", k*cfg.dt_seconds/86400); break
    if k % int(0.25*86400/cfg.dt_seconds) == 0:
        from evosim import physiology
        N = len(sim.organisms)
        nut = sim.world.total_nutrients()
        inorg = sum(o.matter for o in sim.organisms)
        corp = sum(c.matter for c in sim.corpses) if hasattr(sim,"corpses") else 0.0
        mE = np.mean([o.energy/max(physiology.energy_max(o,cfg),1e-30) for o in sim.organisms])
        print(f"{k*cfg.dt_seconds/86400:5.2f} {N:6d} {nut:10.1f} {inorg:8.1f} "
              f"{inorg/N:7.4f} {mE:11.3f} {np.median(sim.world.h2):7.4f}   corpse={corp:.1f}")
print(f"elapsed {time.time()-t0:.0f}s")
