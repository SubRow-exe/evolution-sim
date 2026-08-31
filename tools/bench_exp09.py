"""Exp09 Phase 0 / Phase A — V1.5 異種刺激比較則の決定論診断。

    uv run python tools/bench_exp09.py

進化runを使わず、無次元受容器応答の算術と、人工arenaでの選択そのものを確認する。
検査項目が1つでも落ちれば非ゼロ終了する (Exp09本番の停止条件)。

Phase 0 (docs/Exp09_実験計画.md §5):
  1. response(0,K)=0 / 2. response(K,K)=0.5 / 3. 単調増加 / 4. 0<=response<1
  6. light=1.2 / chemical=12.3 で両ability同値なら同一score
  7. 各診断表現型・代表光量の**交差点stock**を事前計算して表示
  8-9. 交差点の両側で選択が反転し、各表現型でlight/chemical両方のケースを通す
  10. exact tieで走査順によるsource固定biasがない
  11. stimulus_tie_eps が十分小さい / 12. 両score=0でV1.4相当へ戻る
  13. score計算に未来の吸収量・Energy容量・移動後収益を使わない
  14. 比較処理が追加の乱数を消費しない
  16. 観測追加がRNG・行動へ影響しない

Phase 0-5 (単独sourceが `v1.4-final` と完全一致) は git worktree を使うため
本ツールでは扱わない。次で確認する:

    uv run python tools/verify_vs_ref.py --ref v1.4-final --single-source

Phase A (§6): A1 light-only / A2 chemical-only / A3 等価刺激・tie /
A4 光専門型 / A5 chemical専門型 / A6 両用型の環境依存切替。

**このツールはV1.5の行動則を前提にした履歴用ツールである。**
V1.6で一次EnergyのWTA比較則そのものが無くなったため、現在のmainでは
動作しない (bench_exp09は観測カウンタが変わったため実行不可)。
Exp09の再現は `v1.5-final` branchで行うこと。
Exp09の実測結果は docs/Exp09_結果考察.md と
experiments/exp09_actions_20260831_085922/ に保存済み。
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim import behavior                                    # noqa: E402
from evosim.config import Config                               # noqa: E402
from evosim.genome import (CHEM_ABS, LIGHT_ABS, MOVE_POWER,    # noqa: E402
                           N_GENES, SENSORY)
from evosim.organism import Organism                           # noqa: E402
from evosim.simulation import Simulation                       # noqa: E402

# 人工arena上の配置 (現在セルと、光/chemicalが最大のセル)
CUR, LIGHT_CELL, CHEM_CELL = (5, 5), (5, 4), (5, 6)

PHENOTYPES = [
    ("light specialist", 2.0, 0.3),
    ("chemical specialist", 0.3, 2.0),
    ("generalist", 1.0, 1.0),
]
# 標準光場 (vertical) の代表値: 明部 / 中間 / 暗部
LIGHT_LEVELS = [("明部", 1.2), ("中間", 0.78), ("暗部", 0.36)]

# Exp08 flux16 で実測した占有vent stock (参考値。Kの再校正には使わない)
OCCUPIED_STOCK_REF = "Exp08 flux16 実測: 中央値 0.51 E/cell (seed範囲 0.19〜1.37)"


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.checked = 0

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        self.checked += 1
        if not ok:
            print(f"  NG  {label}" + (f"   {detail}" if detail else ""))
            self.fails.append(label + (f" ({detail})" if detail else ""))
        return ok


# ----------------------------------------------------------------------
# 人工arena

def _sim(**kw) -> Simulation:
    base = dict(light_pattern="uniform", light_max=0.0, chem_vent_flux=0.0,
                nutrient_initial=0.0, initial_population=0)
    base.update(kw)
    return Simulation(Config(**base), 1)


def _place(sim: Simulation, light_abs: float, chem_abs: float) -> Organism:
    g = np.zeros(N_GENES)
    g[0] = 1.0                # body_size
    g[MOVE_POWER] = 1.0
    g[3] = 1.0                # movement_efficiency
    g[SENSORY] = 2.0          # 隣接セルを感知
    g[LIGHT_ABS] = light_abs
    g[CHEM_ABS] = chem_abs
    cs = sim.cfg.cell_size
    o = Organism(0, -1, 0, 0, 0, g, (CUR[0] + 0.5) * cs, (CUR[1] + 0.5) * cs,
                 0.0, 5.0, 0.8)
    sim.organisms.append(o)
    sim.next_id = 1
    sim._build_hashes()
    return o


def choose(light_val: float, chem_val: float, light_abs: float,
           chem_abs: float) -> str:
    """人工arenaで1回だけ行動させ、選ばれた一次Energy源を返す。"""
    sim = _sim()
    sim.world.light[LIGHT_CELL] = light_val
    sim.world.chemical[CHEM_CELL] = chem_val
    _place(sim, light_abs, chem_abs)
    behavior.decide_and_move(sim.organisms[0], sim)
    obs = sim.stim_obs
    if obs["tie"]:
        return "tie"
    if obs["light"]:
        return "light"
    if obs["chemical"]:
        return "chemical"
    return "none"


def crossover_stock(cfg: Config, light_val: float, light_abs: float,
                    chem_abs: float) -> float:
    """light scoreとchemical scoreが等しくなるchemical stock。

    `chem_abs * s/(s+Kc) = light_abs * L/(L+Kl)` を s について解く。
    右辺/chem_abs が1以上ならchemicalは決して勝てない (交差点なし)。
    """
    t = (light_abs / chem_abs) * behavior.response(light_val,
                                                  cfg.light_stimulus_half)
    if t >= 1.0:
        return math.inf
    return cfg.chemical_stimulus_half * t / (1.0 - t)


# ----------------------------------------------------------------------
# Phase 0

def phase0_arithmetic(cfg: Config, rep: Report) -> None:
    print("=" * 72)
    print("Phase 0-1..4 受容器応答の算術  response(x,K) = x/(x+K)")
    kl, kc = cfg.light_stimulus_half, cfg.chemical_stimulus_half
    print(f"  light_stimulus_half    = {kl}")
    print(f"  chemical_stimulus_half = {kc}")
    print(f"  stimulus_tie_eps       = {cfg.stimulus_tie_eps}")
    print()
    print(f"{'x':>10} {'response(x,1.2)':>18} {'response(x,12.3)':>18}")
    for x in (0.0, 0.36, 0.78, 1.2, 5.0, 12.3, 100.0):
        print(f"{x:>10.2f} {behavior.response(x, kl):>18.4f}"
              f" {behavior.response(x, kc):>18.4f}")
    rep.check(behavior.response(0.0, kl) == 0.0, "response(0,K)=0")
    rep.check(abs(behavior.response(kl, kl) - 0.5) < 1e-12, "response(K,K)=0.5 (光)")
    rep.check(abs(behavior.response(kc, kc) - 0.5) < 1e-12, "response(K,K)=0.5 (化学)")
    xs = [0.0, 0.01, 0.5, 1.0, 12.3, 100.0, 1e6]
    vals = [behavior.response(x, kc) for x in xs]
    rep.check(all(b > a for a, b in zip(vals, vals[1:])), "xについて単調増加")
    rep.check(all(0.0 <= v < 1.0 for v in vals), "0 <= response < 1")
    print()


def phase0_crossover(cfg: Config, rep: Report) -> None:
    print("=" * 72)
    print("Phase 0-7 交差点stock (これを超えるとchemicalが一次Energy候補になる)")
    print(f"  参考: {OCCUPIED_STOCK_REF}")
    print("  ※ 参考値であり、chemical_stimulus_half をここへ再校正はしない")
    print()
    print(f"{'表現型':<22}" + "".join(f"{n + ' L=' + f'{v:g}':>16}"
                                      for n, v in LIGHT_LEVELS))
    for name, la, ca in PHENOTYPES:
        row = f"{name:<22}"
        for _, lv in LIGHT_LEVELS:
            s = crossover_stock(cfg, lv, la, ca)
            row += f"{'交差点なし':>16}" if math.isinf(s) else f"{s:>16.2f}"
        print(row)
    print()
    # 等価刺激: light=Kl / chemical=Kc で両ability同値なら同点
    rep.check(choose(cfg.light_stimulus_half, cfg.chemical_stimulus_half,
                     1.0, 1.0) == "tie",
              "等価刺激・同一abilityは同点 (Phase 0-6)")
    print()


def phase0_selection(cfg: Config, rep: Report) -> None:
    print("=" * 72)
    print("Phase 0-8/9 交差点の両側で選択が反転し、各表現型で両方向を通る")
    print(f"{'表現型':<22}{'光量':>8}{'交差点':>10}{'下側(0.5x)':>12}{'上側(2x)':>12}")
    for name, la, ca in PHENOTYPES:
        light_val = 1.2
        cross = crossover_stock(cfg, light_val, la, ca)
        if math.isinf(cross):
            # 標準光では交差点が無い表現型は、光を弱めて両側を通す (診断条件)
            light_val = 0.05
            cross = crossover_stock(cfg, light_val, la, ca)
        below = choose(light_val, cross * 0.5, la, ca)
        above = choose(light_val, cross * 2.0, la, ca)
        print(f"{name:<22}{light_val:>8.2f}{cross:>10.2f}{below:>12}{above:>12}")
        rep.check(below == "light", f"{name}: 交差点の下側でlight", below)
        rep.check(above == "chemical", f"{name}: 交差点の上側でchemical", above)
    print()


def phase0_tie_and_zero(cfg: Config, rep: Report) -> None:
    print("=" * 72)
    print("Phase 0-10..12 tie と両score=0 の扱い")
    kc = cfg.chemical_stimulus_half
    lo = kc * (0.5 - 1e-3) / (0.5 + 1e-3)
    hi = kc * (0.5 + 1e-3) / (0.5 - 1e-3)
    a, b = choose(1.2, lo, 1.0, 1.0), choose(1.2, hi, 1.0, 1.0)
    print(f"  わずかにlight優位  → {a}")
    print(f"  わずかにchemical優位 → {b}")
    rep.check(a == "light" and b == "chemical",
              "勝敗はscoreだけで決まる (走査順のsource固定biasなし)")
    rep.check(choose(1.2, kc, 1.0, 1.0) == "tie", "exact tieはtie判定")

    sim = _sim()
    sim.world.light[LIGHT_CELL] = 1.2
    sim.world.chemical[CHEM_CELL] = kc
    o = _place(sim, 1.0, 1.0)
    behavior.decide_and_move(o, sim)
    rep.check(sim.stim_obs["walk"] == 1,
              "tieでどちらも別セルならEnergy源で方向付けしない")

    sim = _sim()          # light 0 / chemical 0
    o = _place(sim, 1.0, 1.0)
    behavior.decide_and_move(o, sim)
    rep.check(sim.stim_obs["light"] == 0 and sim.stim_obs["chemical"] == 0
              and sim.stim_obs["walk"] == 1,
              "両score=0はV1.4相当 (Energy源で方向付けしない)")
    rep.check(0.0 < cfg.stimulus_tie_eps <= 1e-6,
              "stimulus_tie_epsが十分小さい", str(cfg.stimulus_tie_eps))
    print()


def phase0_no_future_no_rng(rep: Report) -> None:
    print("=" * 72)
    print("Phase 0-13/14/16 未来予測なし / 乱数消費なし / 観測が結果を変えない")

    # score は現在の刺激量と能力だけの関数: Energy容量や体サイズを変えても
    # 選択は変わらない (未来の吸収量・容量を見ていない)
    base = choose(1.2, 20.0, 1.0, 1.0)
    sim = _sim()
    sim.world.light[LIGHT_CELL] = 1.2
    sim.world.chemical[CHEM_CELL] = 20.0
    o = _place(sim, 1.0, 1.0)
    o.energy = 0.1                      # 空腹度を変えても
    behavior.decide_and_move(o, sim)
    hungry = "chemical" if sim.stim_obs["chemical"] else "light"
    rep.check(base == hungry, "Energy残量で選択が変わらない (未来収益を見ていない)")

    # 比較処理が乱数を消費しない: tie / 通常選択の直後にRNG状態が変わらない
    for label, lv, cv in (("通常選択", 1.2, 1.0), ("tie", 1.2, 12.3)):
        sim = _sim()
        sim.world.light[LIGHT_CELL] = lv
        sim.world.chemical[CHEM_CELL] = cv
        o = _place(sim, 1.0, 1.0)
        o.genome[MOVE_POWER] = 0.0      # 移動を止めてrandom walkの乱数を排除
        before = sim.rng.bit_generator.state
        behavior.decide_and_move(o, sim)
        rep.check(sim.rng.bit_generator.state == before,
                  f"{label}: 比較処理が乱数を消費しない")

    # 観測カウンタを触っても結果 (指紋) が変わらない
    from tools.golden import fingerprint
    a = Simulation(Config(), 3)
    for _ in range(150):
        a.step()
    fa = fingerprint(a)
    b = Simulation(Config(), 3)
    for _ in range(150):
        b.step()
        b.stim_obs = b._new_stim_obs()
    rep.check(fingerprint(b) == fa, "観測カウンタが結果へ影響しない")
    print()


# ----------------------------------------------------------------------
# Phase A

def phase_a(cfg: Config, rep: Report) -> None:
    print("=" * 72)
    print("Phase A 人工arena診断")

    # A1 light-only
    sim = _sim()
    sim.world.light[LIGHT_CELL] = 1.0
    sim.world.light[(4, 5)] = 0.4
    o = _place(sim, 1.0, 1.0)
    cs = cfg.cell_size
    behavior.decide_and_move(o, sim)
    rep.check(sim.stim_obs["light"] == 1 and sim.stim_obs["tie"] == 0
              and o.y < (CUR[1] + 0.5) * cs,
              "A1 light-only: raw最良lightセルへ向かい、tieに入らない")

    # A2 chemical-only
    sim = _sim()
    sim.world.chemical[CHEM_CELL] = 5.0
    sim.world.chemical[(4, 5)] = 1.0
    o = _place(sim, 1.0, 1.0)
    behavior.decide_and_move(o, sim)
    rep.check(sim.stim_obs["chemical"] == 1 and sim.stim_obs["tie"] == 0
              and o.y > (CUR[1] + 0.5) * cs,
              "A2 chemical-only: raw最良chemicalセルへ向かい、tieに入らない")

    # A3 等価刺激
    rep.check(choose(1.2, 12.3, 1.0, 1.0) == "tie", "A3 等価刺激で同点")

    # A4/A5/A6 各表現型の両方向 (交差点の両側)
    for name, la, ca in PHENOTYPES:
        light_val = 1.2
        cross = crossover_stock(cfg, light_val, la, ca)
        if math.isinf(cross):
            light_val = 0.05
            cross = crossover_stock(cfg, light_val, la, ca)
        rep.check(choose(light_val, cross * 0.5, la, ca) == "light",
                  f"A4-6 {name}: lightを選ぶケース")
        rep.check(choose(light_val, cross * 2.0, la, ca) == "chemical",
                  f"A4-6 {name}: chemicalを選ぶケース")

    # A6 両用型: stockを掃引して切替が1回だけ起きる (単調な閾値挙動)
    la, ca = 1.0, 1.0
    cross = crossover_stock(cfg, 1.2, la, ca)
    stocks = [cross * f for f in (0.25, 0.5, 0.9, 1.1, 2.0, 4.0)]
    picks = [choose(1.2, s, la, ca) for s in stocks]
    print("  A6 stock掃引 (交差点 {:.2f}): {}".format(
        cross, " ".join(f"{s:.1f}:{p}" for s, p in zip(stocks, picks))))
    flips = sum(1 for a, b in zip(picks, picks[1:]) if a != b)
    rep.check(picks[0] == "light" and picks[-1] == "chemical" and flips == 1,
              "A6 両用型: 交差点で1回だけ切り替わる")
    print()


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    cfg = Config()
    print("Exp09 Phase 0 / Phase A — V1.5 異種刺激比較則 決定論診断")
    print()
    rep = Report()
    phase0_arithmetic(cfg, rep)
    phase0_crossover(cfg, rep)
    phase0_selection(cfg, rep)
    phase0_tie_and_zero(cfg, rep)
    phase0_no_future_no_rng(rep)
    phase_a(cfg, rep)

    print("=" * 72)
    print(f"確認項目 {rep.checked} 件")
    print("※ 単独sourceが v1.4-final と完全一致することは")
    print("   uv run python tools/verify_vs_ref.py --ref v1.4-final --single-source")
    print("   で別途確認する (Phase 0-5)")
    if rep.fails:
        print(f"判定: NG — {len(rep.fails)} 件が不成立")
        for f in rep.fails:
            print(f"  - {f}")
        return 1
    print("判定: OK — V1.5比較則は事前登録式どおり")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
