"""physical_mode で light route が物理スケール化されていないことを実測する。

_absorb_light() には physical_mode 分岐が無く、旧arbitrary単位の需要が
Joule建ての org.energy へそのまま加算される。

Opus 5 ロードマップレビュー時の検証スクリプト。シミュレーション実験ではなく
解析・短時間診断であり、正式実験ではない。

前提: V1.9 LUCA proxy 実装 (branch claude/pr-50-v1.6-exp11-iuhnzm) のツリー上で実行する。
    EVOSIM_ROOT=<そのworktree> uv run python <this file>

考察の正本: docs/V1.9_ロードマップ_Opus5レビュー.md
"""
import os
import sys, dataclasses
from pathlib import Path
ROOT = Path(os.environ.get("EVOSIM_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"experiments"/"luca_proxy"))
sys.path.insert(0, str(ROOT/"experiments"/"exp15_v19"))
import run_luca_proxy as luca
from evosim import physiology
from evosim.genome import LIGHT_ABS

cfg = luca.make_cfg("A")
sim = luca.base.setup_sim(cfg, 15001) if hasattr(luca.base, "setup_sim") else None
if sim is None:
    from evosim.simulation import Simulation
    import numpy as np
    sim = Simulation(cfg, np.random.default_rng(15001))
org = sim.organisms[0]
print(f"physical_mode      : {cfg.physical_mode}")
print(f"E_max              : {physiology.energy_max(org, cfg):.4e} J")
print(f"P_full (basal etc) : {physiology.full_activity_expenditure_rate(org, cfg):.4e} W")
print(f"1 step = {cfg.dt_seconds} s -> maintenance/step = "
      f"{physiology.full_activity_expenditure_rate(org, cfg)*cfg.dt_seconds:.4e} J")
print()
print(f"light_max          : {cfg.light_max}  [旧 arbitrary E/tick 単位]")
print(f"light_uptake_coef  : {cfg.light_uptake_coef}")
print(f"light field max    : {sim.world.light.max():.4f}")
resp = physiology.density_response(float(sim.world.light.max()), cfg.light_uptake_half)
area = max(org.matter, 1e-9) ** (2.0/3.0)
for la in (0.01, 0.3, 1.0):
    raw = cfg.light_uptake_coef * la * area * 1.0 * 1.0 * resp
    print(f"  light_absorption={la:<5} -> raw demand = {raw:.4e}   "
          f"(E_max = {physiology.energy_max(org,cfg):.3e} J)")
print()
print("H2側 (比較):")
sim.step()
print(f"  1 step 後の organism energy = {sim.organisms[0].energy:.4e} J")
