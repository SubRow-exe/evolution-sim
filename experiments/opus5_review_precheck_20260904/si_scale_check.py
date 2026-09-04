"""V1.9 物理スケール整合チェック (Opus 5レビュー時に実施)

docs/V1.9_物理スケール再校正方針.md のアンカーをSIで閉じ、相互整合と
生態学的な帰結 (枯渇するか / 競争が起きるか / 空間構造が残るか) を確認する。

これはシミュレーションではなく解析計算である。正式実験ではない。
考察の正本: docs/V1.9_物理スケール_Opus5レビュー.md

使い方:
    uv run python experiments/opus5_review_precheck_20260904/si_scale_check.py
    uv run python experiments/opus5_review_precheck_20260904/si_scale_check.py --vent-uM 200
"""
from __future__ import annotations

import argparse
import math

# ---------------------------------------------------------------------------
# docs/V1.9_物理スケール再校正方針.md のアンカー
# ---------------------------------------------------------------------------
DT_S = 10.0                 # §2   standard numerical timestep [s]
D_H2 = 5e-9                 # §3.2 H2 molecular diffusion [m^2/s]
Q_H2_MAX = 50e-3            # §3.3 mol H2 /(gDW h)
K_H2_UM = 600.0             # §3.3 一次速度が保たれる上端 -> 半飽和の目安 [µM]
MAINT_ATP = 0.116e-3        # §5   mol ATP /(gDW h)
DG_ACETATE = -95e3          # §4   J / mol acetate
ATP_PER_ACETATE = 0.3       # §4   mol ATP / mol acetate
MU_CITED = 0.112            # §2.5 引用されている比増殖速度 [1/h]
Y_ATP = 10.0                # 古典値 gDW / mol ATP (方針書には未記載: 導出用の仮定)

# S1 候補: 1 µm^3 / dry density 280 g/L (E. coli 級)
CELL_VOLUME_M3 = 1e-18
DRY_DENSITY_KG_M3 = 280.0

GRID = 40                   # 現行 grid
VENT_CELLS = 13             # r=2 の円盤セル数
N_VENTS = 4
WATER_VISC = 1e-3            # 水の粘性 [Pa s]
LOSS_TAU_S = 3600.0         # H2 環境損失の時定数の仮定 [s]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dt", type=float, default=DT_S, help="timestep [s]")
    ap.add_argument("--vent-uM", type=float, default=10_000.0,
                    help="vent セルの H2 濃度 [µM]。方針書 §3.1 は 10 mM = 10000 µM")
    ap.add_argument("--dg-atp", type=float, default=-50e3, help="ATP 加水分解自由エネルギー [J/mol]")
    ap.add_argument("--n-agents", type=int, default=1000)
    ap.add_argument("--swim-um-s", type=float, default=25.0)
    a = ap.parse_args()

    dry_g = CELL_VOLUME_M3 * DRY_DENSITY_KG_M3 * 1e3        # gDW / cell
    usable_j_per_mol_h2 = ATP_PER_ACETATE / 4.0 * (-a.dg_atp)
    dg_per_mol_h2 = -DG_ACETATE / 4.0

    p_maint = MAINT_ATP / 3600.0 * (-a.dg_atp) * dry_g       # W / cell
    p_upt_max = Q_H2_MAX / 3600.0 * dry_g * usable_j_per_mol_h2

    print("=" * 68)
    print("1. 参照細胞とエネルギー変換")
    print("=" * 68)
    print(f"  dry mass                : {dry_g*1e12:.2f} pg/cell")
    print(f"  usable energy           : {usable_j_per_mol_h2/1e3:.2f} kJ/mol H2 "
          f"(ΔG°' {dg_per_mol_h2/1e3:.2f} kJ/mol の {100*usable_j_per_mol_h2/dg_per_mol_h2:.1f}%)")
    print(f"  maintenance             : {p_maint*1e15:.2f} fW/cell")
    print(f"  max uptake power        : {p_upt_max*1e15:.2f} fW/cell  (余剰 {p_upt_max/p_maint:.1f}x)")
    print("  cross-check: Kempes et al. 2017 の 1 µm^3 級 maintenance は 1e-16〜1e-15 W")

    print()
    print("=" * 68)
    print("2. アンカー間の整合 (uptake / ATP yield / 増殖速度)")
    print("=" * 68)
    mu_derived = Q_H2_MAX * ATP_PER_ACETATE / 4.0 * Y_ATP
    print(f"  q_H2_max と ATP yield から導出 : mu = {mu_derived:.4f} /h -> 倍加 {math.log(2)/mu_derived:.1f} h")
    print(f"  方針書 §2.5 の引用値           : mu = {MU_CITED:.4f} /h -> 倍加 {math.log(2)/MU_CITED:.1f} h")
    print(f"  ずれ                          : {MU_CITED/mu_derived:.2f}x  (Y_ATP={Y_ATP:.0f} 仮定)")
    print(f"  引用 mu を出すのに必要な uptake : {MU_CITED/(ATP_PER_ACETATE/4*Y_ATP)*1e3:.0f} mmol/(gDW h)")

    print()
    print("=" * 68)
    print("3. 拡散安定条件が決める格子・世界スケール")
    print("=" * 68)
    dx_min = math.sqrt(4.0 * D_H2 * a.dt)
    print(f"  陽解法2D: D*dt/dx^2 <= 0.25  ->  dx >= {dx_min*1e3:.3f} mm  (dt={a.dt:.0f}s)")
    dx = 0.5e-3
    depth = dx
    volume_m3 = (dx * GRID) ** 2 * depth
    print(f"  採用案: dx={dx*1e3:.1f} mm / world={dx*GRID*1e2:.1f} cm / depth={depth*1e3:.1f} mm"
          f" -> {volume_m3*1e6:.3f} mL")
    print(f"  N={a.n_agents} -> {a.n_agents/(volume_m3*1e6):.0f} cells/mL  (深海 ~1e4 /mL)")
    for h in (1, 24):
        print(f"  分子拡散の到達距離 {h:2d} h : {math.sqrt(4*D_H2*h*3600)*1e3:.1f} mm "
              f"= {math.sqrt(4*D_H2*h*3600)/dx:.1f} cell")

    print()
    print("=" * 68)
    print(f"4. vent 濃度 {a.vent_uM:.0f} µM での生態学的帰結")
    print("=" * 68)
    c_break = K_H2_UM / (p_upt_max / p_maint - 1.0)
    print(f"  損益分岐濃度 : {c_break:.1f} µM   （これ以下では維持費を払えない）")
    print(f"  飽和開始     : {K_H2_UM:.0f} µM 付近")
    h_frac = a.vent_uM / (a.vent_uM + K_H2_UM)
    print(f"  H(C,K)       : {h_frac:.3f}   （1に近いほど density response が定数化して死ぬ）")

    voxel_m3 = dx * dx * depth
    c_mol_m3 = a.vent_uM * 1e-3                      # µM -> mol/m^3
    supply = (1.0 / LOSS_TAU_S) * c_mol_m3 * voxel_m3 * VENT_CELLS * N_VENTS
    upt_cell = Q_H2_MAX / 3600.0 * dry_g * h_frac     # mol/s/cell
    cons = upt_cell * a.n_agents
    print(f"  供給 (定常維持に必要な source) : {supply:.3e} mol/s")
    print(f"  消費 (N={a.n_agents})                  : {cons:.3e} mol/s")
    print(f"  消費/供給                       : {cons/supply:.3e}"
          f"   {'-> 枯渇・競争は起きない' if cons/supply < 0.1 else '-> 枯渇/競争が成立しうる'}")
    print()
    print("  【重要】低濃度域では 消費/供給 は C にほとんど依存しない:")
    print("      消費 ∝ N·q_max·m_dry·C/K     供給 ∝ λ·V_vent·C")
    print("      -> 比 = N·q_max·m_dry / (K·λ·V_vent)   … C が約分される")
    print("      つまり vent 濃度を下げても枯渇は復活しない。")
    print("      濃度が効くのは H(C,K) の飽和 (走化性・density response) のほうだけ。")
    print()
    biomass_g = a.n_agents * dry_g
    need = supply / (cons / biomass_g) if cons > 0 else float("nan")
    print(f"  枯渇が成立するのに必要な総biomass : {need*1e6:.3g} µgDW "
          f"(現在 {biomass_g*1e6:.3g} µgDW, {need/biomass_g:.0f}x 不足)")
    print(f"    -> 1 agent = {need/biomass_g:.0f} cells とするか、N を {need/biomass_g:.0f} 倍にするか、")
    print(f"       λ (H2 の滞留時間) を {need/biomass_g:.0f} 倍長くするか")

    print()
    print("=" * 68)
    print("5. 遊泳速度と空間構造")
    print("=" * 68)
    step_m = a.swim_um_s * 1e-6 * a.dt
    n_day = 86400.0 / a.dt
    rms_cells = step_m * math.sqrt(n_day) / dx
    print(f"  遊泳 {a.swim_um_s:.0f} µm/s -> 1 step {step_m*1e6:.0f} µm = {step_m/dx:.2f} cell")
    print(f"  1日 ({n_day:.0f} step) の RMS 変位 = {rms_cells:.1f} cell   (world {GRID} cell)")
    print("  " + ("-> 1日で世界を横断し、空間構造が消える" if rms_cells > GRID
                  else "-> 空間構造が保たれる"))

    print()
    print("=" * 68)
    print("6. 遊泳の物理仕事 (Stokes)")
    print("=" * 68)
    radius_m = (3.0 * CELL_VOLUME_M3 / (4.0 * math.pi)) ** (1.0 / 3.0)
    v = a.swim_um_s * 1e-6
    drag = 6.0 * math.pi * WATER_VISC * radius_m * v
    p_swim = drag * v
    print(f"  等価半径 {radius_m*1e6:.2f} µm, v={a.swim_um_s:.0f} µm/s")
    print(f"  Stokes drag power = {p_swim*1e18:.2f} aW = maintenance の {100*p_swim/p_maint:.2f}%")
    print("  -> 低Reynoldsでは遊泳の物理仕事は維持代謝を支配しない (実測の鞭毛コストも ~1%)")
    print("  -> movement cost を独立の大きな E/tick として積み上げるのは物理的に過大")

    print()
    print("=" * 68)
    print("7. 拡散安定条件と dt sweep の両立可否")
    print("=" * 68)
    print(f"  dx を {dx*1e3:.1f} mm へ固定した場合の上限 dt = {0.25*dx*dx/D_H2:.1f} s")
    for dt_try in (5.0, 10.0, 20.0):
        ok = D_H2 * dt_try / (dx * dx) <= 0.25
        print(f"    dt={dt_try:4.0f}s -> D*dt/dx^2 = {D_H2*dt_try/(dx*dx):.3f}"
              f"  {'OK' if ok else '*** UNSTABLE ***'}")
    print("  -> 陽解法のままでは dt=5/10/20 s を同一 dx で比較できない")

    print()
    print("=" * 68)
    print("8. 走化性の時間解像度")
    print("=" * 68)
    for tau in (20.0, 5 * a.dt):
        alpha = 1.0 - math.exp(-a.dt / tau)
        print(f"  memory_tau={tau:5.0f} s -> {tau/a.dt:4.1f} step/τ, EMA α={alpha:.3f}"
              f"   (V1.6 は α=0.095)")


if __name__ == "__main__":
    main()
