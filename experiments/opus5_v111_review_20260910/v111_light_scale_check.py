"""V1.11 phototrophy仕様の数値を、V1.10.1の実baseline (luca.make_cfg) に対して検算する。

docs/V1.11_原始Phototrophy_実装仕様.md の §5-§7 の候補値を、実際に走っている
Config へ当てて、入射power / absorptance / H2 coupling cap / 熱力学上限を出す。

シミュレーション実験ではなく解析計算。正式実験ではない。
考察の正本: docs/V1.11_Opus5レビュー.md

    uv run python experiments/opus5_v111_review_20260910/v111_light_scale_check.py
    EVOSIM_ROOT=<worktree> uv run python .../v111_light_scale_check.py
"""
import os
import sys, math
from pathlib import Path
ROOT = Path(os.environ.get("EVOSIM_ROOT", Path(__file__).resolve().parents[2]))
for p in (ROOT, ROOT/"experiments"/"luca_proxy", ROOT/"experiments"/"exp15_v19",
          ROOT/"experiments"/"exp17_v110_cnp"):
    sys.path.insert(0, str(p))
import numpy as np
import run_luca_proxy as luca
from evosim import physiology
from evosim.organism import Organism
from evosim.genome import INITIAL_GENOME

cfg = luca.make_cfg("A")
o = Organism(0, -1, 0, 0, 0, INITIAL_GENOME.copy(), 0.0, 0.0, 0.0, 0.0, 0.5)

H, C_LIGHT, NA = 6.62607015e-34, 2.99792458e8, 6.02214076e23
LAM = 800e-9
FLUX = 1.0e-6            # mol photons /m2/s (= 1.0 µmol)
EFF  = 0.10              # phototrophy_radiant_to_usable_eff
CAP  = 30000.0           # phototrophy_h2_bonus_cap_j_per_mol
SEED_ABS = 0.001

print("="*70); print("A. V1.10.1 実baseline (luca.make_cfg) の値"); print("="*70)
B = cfg.h2_usable_energy_j_per_mol
print(f"  h2_usable_energy_j_per_mol = {B:.1f} J/mol   <- 仕様書§7.1は 3750 と記載")
print(f"  atp_energy_j_per_mol       = {cfg.atp_energy_j_per_mol:.0f}")
print(f"  h2_qmax                    = {cfg.h2_qmax_mol_per_kgdw_s*3600*1000:.0f} mmol/(gDW h)")
print(f"  h2_km                      = {cfg.h2_km_mol_m3:.3f} mol/m^3")
P_full = physiology.full_activity_expenditure_rate(o, cfg)
E_max  = physiology.energy_max(o, cfg)
print(f"  P_full (matter=0.5)        = {P_full*1e15:.3f} fW")
print(f"  E_max                      = {E_max*1e15:.2f} fJ")

print(); print("="*70); print("B. photon flux 1.0 µmol/m2/s が個体へ与える入射power"); print("="*70)
r = physiology.physical_radius_m(o.matter, cfg)
A = math.pi*r*r
e_ph = H*C_LIGHT/LAM
rate = FLUX*NA*A
P_inc = rate*e_ph
print(f"  cell radius       = {r*1e6:.3f} µm ,  A_proj = {A:.3e} m^2")
print(f"  photon energy     = {e_ph:.3e} J  ({e_ph*NA/1000:.1f} kJ/mol photons)")
print(f"  photon rate       = {rate:.3e} /s")
print(f"  P_incident        = {P_inc*1e15:.2f} fW   = maintenance の {P_inc/P_full:.0f} 倍")

print(); print("="*70); print("C. absorptance mapping と photo power"); print("="*70)
print(f"  {'gene':>7}{'absorptance':>13}{'P_photo_raw':>14}{'/maintenance':>14}{'/H2@source':>12}")
m_dry = o.matter*cfg.matter_unit_to_kgdw
q_src = cfg.h2_qmax_mol_per_kgdw_s*(10.0/(10.0+cfg.h2_km_mol_m3))*m_dry
P_h2_src = q_src*B
for g in (SEED_ABS, 0.01, 0.1, 1.0, 5.0):
    a = 1-math.exp(-g)
    Pp = P_inc*a*EFF
    print(f"  {g:>7}{a*100:>12.3f}%{Pp*1e15:>13.4f}fW{Pp/P_full:>13.2f}x{Pp/P_h2_src:>11.2f}x")
print(f"  参考: H2 income @10 mM source = {P_h2_src*1e15:.2f} fW  (= maintenance の {P_h2_src/P_full:.1f} 倍)")

print(); print("="*70); print("D. H2 coupling cap は効くか  (E_photo <= n_H2 * CAP)"); print("="*70)
print(f"  {'H2 [µM]':>9}{'q [mol/s]':>12}{'q*CAP [fW]':>12}{'L@gene1.0':>11}{'binding':>10}")
L1 = P_inc*(1-math.exp(-1.0))*EFF
for cmM in (0.05, 0.2, 0.55, 1.0, 3.0, 10.0):
    q = cfg.h2_qmax_mol_per_kgdw_s*(cmM/(cmM+cfg.h2_km_mol_m3))*m_dry
    print(f"  {cmM*1000:>9.0f}{q:>12.3e}{q*CAP*1e15:>11.3f}f{L1*1e15:>10.3f}f"
          f"{'  cap' if q*CAP < L1 else '  light':>10}")

print(); print("="*70); print("E. capの熱力学的上限チェック"); print("="*70)
ph_mol = e_ph*NA
print(f"  800 nm photon  = {ph_mol/1000:.1f} kJ/mol")
print(f"  H2 = 2 e- , 1 photon/e- なら投入上限 = {2*ph_mol/1000:.1f} kJ/mol H2")
print(f"  CAP {CAP/1000:.0f} kJ/mol H2  -> 量子->usable 変換効率 {100*CAP/(2*ph_mol):.1f}%")
print(f"  photo込みの最大 H2 利用効率 = ({B:.1f}+{CAP:.0f})/{B:.1f} = {(B+CAP)/B:.1f} 倍")
print(f"    (仕様書は 3750 前提で「約9倍」と記載 -> 実baselineでは上記が正)")
