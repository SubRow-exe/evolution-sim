"""Exp16の11条件を、生物不在H2定常場の「生息可能セル率」だけで予測する。

参照iLUCA (matter=0.5) が維持代謝を自力で賄える最低H2濃度を求め、各条件の
定常場のうち何%がそれを超えるかを出す。Exp16の生存/絶滅と完全に一致する。

Opus 5 ロードマップレビュー時の検証スクリプト。シミュレーション実験ではなく
解析・短時間診断であり、正式実験ではない。

前提: V1.9 LUCA proxy 実装 (branch claude/pr-50-v1.6-exp11-iuhnzm) のツリー上で実行する。
    EVOSIM_ROOT=<そのworktree> uv run python <this file>

考察の正本: docs/V1.9_ロードマップ_Opus5レビュー.md
"""
import os
import sys, math
from pathlib import Path
ROOT = Path(os.environ.get("EVOSIM_ROOT", Path(__file__).resolve().parents[2]))
for p in (ROOT, ROOT/"experiments"/"luca_proxy", ROOT/"experiments"/"exp15_v19",
          ROOT/"experiments"/"exp16_v19_env"):
    sys.path.insert(0, str(p))
import numpy as np, dataclasses
import run_exp16 as e16
from evosim import world as W, physiology
from evosim.organism import Organism
from evosim.genome import INITIAL_GENOME

OBS = {  # Exp16 実測 (生存/5, final N median, max gen median)
 "h2_1mM":(0,0,0), "h2_3mM":(0,0,0), "h2_6mM":(5,386,2), "baseline_10mM":(5,2981,5),
 "h2_15mM":(5,4876,6), "exchange_fast_300s":(0,0,0), "exchange_slow_3600s":(5,5000,6),
 "diffusion_low_2p5e9":(0,0,1), "diffusion_high_1e8":(5,4937,6),
 "layout_cross":(5,43,5), "layout_cluster":(0,0,5)}

print(f"{'condition':<20}{'surv':>5}{'finalN':>8} | {'min':>7}{'med':>8}{'mean':>8} | "
      f"{'%>維持':>7}{'%>24h分裂':>10}{'Td@med':>9}")
print("-"*95)
rows=[]
for name in OBS:
    cfg = e16.make_cfg(name)
    mask = np.zeros((cfg.grid_w, cfg.grid_h), dtype=bool)
    for (cx, cy) in e16.LAYOUTS[e16.CONDITIONS[name]["layout"]]:
        mask[cx, cy] = True
    h2 = W._equilibrium_h2_physical(cfg, mask, (cfg.grid_w, cfg.grid_h))
    # 参照個体 (matter=0.5) の収支
    o = Organism(0, -1, 0, 0, 0, INITIAL_GENOME.copy(), 0.0, 0.0, 0.0, 0.0, 0.5)
    m_dry = o.matter * cfg.matter_unit_to_kgdw
    P = physiology.full_activity_expenditure_rate(o, cfg)
    inc_max = cfg.h2_qmax_mol_per_kgdw_s * m_dry * cfg.h2_usable_energy_j_per_mol
    inc = inc_max * h2/(h2 + cfg.h2_km_mol_m3)
    cost_div = cfg.growth_energy_j_per_kgdw * cfg.matter_unit_to_kgdw * 0.5
    f_maint = float((inc > P).mean())
    f_div24 = float((inc - P > cost_div/86400).mean())
    med = float(np.median(h2))
    # mu = (dm/dt)/m ; dm/dt = (inc-P)/cost_per_matter, m = o.matter
    cost_per_matter = cfg.growth_energy_j_per_kgdw * cfg.matter_unit_to_kgdw
    mu_med = (inc_max*med/(med+cfg.h2_km_mol_m3) - P)/(cost_per_matter*o.matter)
    Td = math.log(2)/(mu_med*3600) if mu_med > 0 else float('inf')
    s, fn, _ = OBS[name]
    print(f"{name:<20}{s:>3}/5{fn:>8} | {h2.min()*1e3:7.1f}{med*1e3:8.1f}{h2.mean()*1e3:8.1f} | "
          f"{f_maint*100:6.1f}%{f_div24*100:9.1f}%{Td:8.1f}h")
    rows.append((name, s, f_maint, f_div24, Td))
print()
print(f"維持break-even濃度 = {cfg.h2_km_mol_m3*(P/inc_max)/(1-P/inc_max)*1e3:.1f} µM")
print(f"H2無限大での理論最短倍加 = {math.log(2)/((inc_max-P)/(cost_per_matter*o.matter)*3600):.2f} h")
print(f"10 mM source cell での倍加 = "
      f"{math.log(2)/((inc_max*10/(10+cfg.h2_km_mol_m3)-P)/(cost_per_matter*o.matter)*3600):.2f} h")
