"""Exp08 Phase 0 — V1.4吸収則の決定論ベンチ (docs/Exp08_実験計画.md §3)。

    uv run python tools/bench_v14_uptake.py

進化runを使わず、数式と実装だけを確認する。seedに依存する量は出さない。
表示するのは:

- 有効表面積 `A_eff = matter^(2/3)` のスケーリング
- 光: `light_absorption` × `light_uptake_coef` 別の個体吸収ceilingと収支
- 化学: `chemical_absorption` 別の個体吸収ceilingと収支 (`chem_uptake=0.5`)
- **同一matter・同一absorptionでの light / chemical ceiling併記** (相対スケール)
- 1/5/20/100個体の密度競争 (供給十分/不足) と個体順不変性

維持費・修復費は式を書き直さず `evosim.physiology` を実際に呼んで測る。
検査項目が1つでも落ちれば非ゼロ終了する (Exp08本番の停止条件)。
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim import physiology                                    # noqa: E402
from evosim.config import Config                                 # noqa: E402
from evosim.genome import (CHEM_ABS, INITIAL_GENOME, LIGHT_ABS,  # noqa: E402
                           NUTRIENT_ABS)
from evosim.organism import Organism                             # noqa: E402
from evosim.physiology import effective_surface                  # noqa: E402
from evosim.simulation import Simulation                         # noqa: E402

MATTERS = (0.5, 0.8, 1.0, 2.0, 4.0, 8.0)
ABILITIES = (0.3, 1.0, 2.0, 5.0)
LIGHT_COEFS = (1.0, 1.5, 2.0, 3.0, 4.0)
DENSITIES = (1, 5, 20, 100)

# 診断用の並べ替えは Simulation.rng を消費しない別RNGで行う (Exp08 §3.4)
SHUFFLE_RNG = np.random.Generator(np.random.PCG64(20260831))


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
# 生理側の実測 (式を再実装しない)

def _ancestor(cfg: Config, matter: float, gene_idx: int | None = None,
              ability: float | None = None) -> Organism:
    g = INITIAL_GENOME.copy()
    if gene_idx is not None:
        g[gene_idx] = ability
    return Organism(0, -1, 0, 0, 0, g, 0.0, 0.0, 0.0,
                    cfg.energy_capacity * matter * 0.5, matter)


def maintenance_at_rest(cfg: Config, matter: float, gene_idx=None,
                        ability=None) -> float:
    """静止時 (v=0) の維持費 [E/tick]。physiologyを実際に呼んで測る。"""
    o = _ancestor(cfg, matter, gene_idx, ability)
    return physiology.maintenance_and_movement(o, cfg, 0.0)


def repair_cost_at_steady_state(cfg: Config, matter: float, gene_idx=None,
                                ability=None) -> float:
    """代謝損傷を打ち消し続けるのに要する修復費 [E/tick] (実測)。

    静止個体へ1 tick分の代謝損傷を与え、`physiology.repair` が実際に払う額を
    そのまま返す。修復予算上限に当たる場合はその額になる。
    """
    o = _ancestor(cfg, matter, gene_idx, ability)
    o.damage = cfg.metabolic_damage * matter
    return physiology.repair(o, cfg)


def light_ceiling(cfg: Config, matter: float, ability: float,
                  coef: float) -> float:
    return coef * ability * effective_surface(matter)


def chemical_ceiling(cfg: Config, matter: float, ability: float) -> float:
    return cfg.chem_uptake * ability * effective_surface(matter)


# ----------------------------------------------------------------------
# §3.1 有効表面積

def section_surface(rep: Report) -> None:
    print("=" * 70)
    print("§3.1 有効表面積 A_eff = matter^(2/3)")
    print(f"{'matter':>8} {'A_eff':>10} {'A_eff/matter':>14}")
    for m in MATTERS:
        a = effective_surface(m)
        print(f"{m:>8.2f} {a:>10.4f} {a / m:>14.4f}")
    rep.check(effective_surface(1.0) == 1.0, "matter 1 → A_eff 1")
    rep.check(abs(effective_surface(8.0) - 4.0) < 1e-12, "matter 8 → A_eff 4")
    rep.check(effective_surface(0.8) > 0.8,
              "matter<1 では A_eff>matter (交差点は matter=1)")
    print()


# ----------------------------------------------------------------------
# §3.2 光

def section_light(cfg: Config, rep: Report) -> None:
    print("=" * 70)
    print("§3.2 光の個体収支 (静止・φ=1・セル供給が十分な場合の上限)")
    print(f"世界のセル光量: {float(cfg.light_max) * cfg.light_floor:.3f} "
          f"〜 {cfg.light_max:.3f} E/tick/cell  (pattern={cfg.light_pattern})")
    print(f"{'matter':>7} {'abs':>5} {'coef':>5} {'ceiling':>9} {'維持費':>8}"
          f" {'修復費':>8} {'net':>9} {'供給律速':>9}")
    for m in MATTERS:
        for ab in ABILITIES:
            up = maintenance_at_rest(cfg, m, LIGHT_ABS, ab)
            rp = repair_cost_at_steady_state(cfg, m, LIGHT_ABS, ab)
            for coef in LIGHT_COEFS:
                ceil = light_ceiling(cfg, m, ab, coef)
                limited = "yes" if ceil > cfg.light_max else "no"
                print(f"{m:>7.2f} {ab:>5.1f} {coef:>5.1f} {ceil:>9.3f}"
                      f" {up:>8.3f} {rp:>8.3f} {ceil - up - rp:>9.3f}"
                      f" {limited:>9}")
    m0, ab0 = cfg.initial_matter, float(INITIAL_GENOME[LIGHT_ABS])
    up = maintenance_at_rest(cfg, m0, LIGHT_ABS, ab0)
    rp = repair_cost_at_steady_state(cfg, m0, LIGHT_ABS, ab0)
    be_rest = up / (ab0 * effective_surface(m0))
    be_rep = (up + rp) / (ab0 * effective_surface(m0))
    print()
    print(f"祖先 (matter={m0}, light_absorption={ab0}):")
    print(f"  静止維持費        {up:.4f} E/tick")
    print(f"  代謝損傷の修復費  {rp:.4f} E/tick")
    print(f"  単純break-even    light_uptake_coef = {be_rest:.3f}")
    print(f"  修復込みbreak-even light_uptake_coef = {be_rep:.3f}")
    print(f"  初期Energy {cfg.initial_energy} / "
          f"Energy上限 {cfg.energy_capacity * m0:.1f} / "
          f"繁殖閾値 {cfg.repro_energy_frac * cfg.energy_capacity * m0:.1f}")
    print("  注: 初期個体は初期Energyを持つため、赤字係数でも開始直後は"
          "繁殖し得る。coef 1.0 を『必ず即絶滅』と事前断定しない。")
    rep.check(1.2 < be_rest < 1.4, "祖先の単純break-evenが約1.29",
              f"{be_rest:.3f}")
    rep.check(be_rep > be_rest, "修復込みbreak-evenは単純break-evenより高い",
              f"{be_rep:.3f}")
    print()


# ----------------------------------------------------------------------
# §3.3 化学 + light/chemical ceiling併記

def section_chemical(cfg: Config, rep: Report) -> None:
    print("=" * 70)
    print(f"§3.3 化学の個体収支 (chem_uptake={cfg.chem_uptake} 固定)")
    print(f"{'matter':>7} {'abs':>5} {'ceiling':>9} {'維持費':>8} {'修復費':>8}"
          f" {'net':>9}")
    for m in MATTERS:
        for ab in ABILITIES:
            ceil = chemical_ceiling(cfg, m, ab)
            up = maintenance_at_rest(cfg, m, CHEM_ABS, ab)
            rp = repair_cost_at_steady_state(cfg, m, CHEM_ABS, ab)
            print(f"{m:>7.2f} {ab:>5.1f} {ceil:>9.3f} {up:>8.3f} {rp:>8.3f}"
                  f" {ceil - up - rp:>9.3f}")
    print()
    print("§3.3b 同一matter・同一absorptionでの個体吸収ceiling併記")
    print("  light_uptake_coef と chem_uptake は同種の「能力→実吸収速度」係数。")
    print(f"{'matter':>7} {'abs':>5} {'chem':>8}"
          + "".join(f"{'L c=' + f'{c:g}':>9}" for c in LIGHT_COEFS))
    for m in (0.8, 1.0, 2.0):
        for ab in ABILITIES:
            row = f"{m:>7.2f} {ab:>5.1f} {chemical_ceiling(cfg, m, ab):>8.3f}"
            row += "".join(f"{light_ceiling(cfg, m, ab, c):>9.3f}"
                           for c in LIGHT_COEFS)
            print(row)
    hi = chemical_ceiling(cfg, 0.8, 5.0)
    print()
    print(f"  chemical_absorption=5 / matter=0.8 の化学ceiling {hi:.3f} E/tick は"
          f" V1.1明部光 {cfg.light_max:.2f} E/tick/cell を超える")
    rep.check(hi > cfg.light_max,
              "高chemical能力の個体ceilingはV1.1明部セル光を上回る",
              f"{hi:.3f} > {cfg.light_max:.2f}")
    print()


# ----------------------------------------------------------------------
# §3.4 密度競争と個体順不変性

def _bare_sim(**kw) -> Simulation:
    base = dict(light_pattern="uniform", light_max=0.0, chem_vent_flux=0.0,
                nutrient_initial=0.0, initial_population=0)
    base.update(kw)
    return Simulation(Config(**base), 1)


def _populate(sim: Simulation, cell, n: int, gene_idx: int, ability: float,
              energy: float) -> list[Organism]:
    cs = sim.cfg.cell_size
    orgs = []
    for i in range(n):
        g = np.zeros(len(INITIAL_GENOME))
        g[0] = 1.0                      # body_size
        g[3] = 1.0                      # movement_efficiency
        g[gene_idx] = ability
        o = Organism(i, -1, i, 0, 0, g,
                     (cell[0] + 0.5) * cs, (cell[1] + 0.5) * cs, 0.0,
                     energy, 0.6 + 0.004 * i)   # matterを個体ごとに変える
        sim.organisms.append(o)
        orgs.append(o)
    sim._build_hashes()
    return orgs


def _run_density(kind: str, n: int, supply: float, order: list[int]):
    """指定順で吸収を1回実行し、(初期index -> 取得量) と総取得を返す。"""
    cell = (5, 5)
    if kind == "light":
        sim = _bare_sim(light_max=0.0, light_uptake_coef=2.0)
        sim.world.light[cell] = supply
        orgs = _populate(sim, cell, n, LIGHT_ABS, 2.0, 5.0)
        before = [o.energy for o in orgs]
    elif kind == "chemical":
        sim = _bare_sim()
        sim.world.chemical[cell] = supply
        orgs = _populate(sim, cell, n, CHEM_ABS, 2.0, 5.0)
        before = [o.energy for o in orgs]
    else:
        sim = _bare_sim()
        sim.world.nutrients[cell] = supply
        orgs = _populate(sim, cell, n, NUTRIENT_ABS, 2.0, 50.0)
        before = [o.matter for o in orgs]
    tagged = list(enumerate(orgs))
    sim.organisms = [tagged[i][1] for i in order]
    sim._build_hashes()
    demand = _total_demand(kind, sim)      # 配分前の総需要
    sim._absorb_fields()
    after = ([o.energy for o in orgs] if kind != "nutrient"
             else [o.matter for o in orgs])
    gains = {i: after[i] - before[i] for i in range(n)}
    return demand, gains, math.fsum(gains.values())


def section_density(cfg: Config, rep: Report) -> None:
    print("=" * 70)
    print("§3.4 密度競争 (供給十分 / 供給不足) と個体順不変性")
    for kind, plenty, scarce in (("light", 100.0, 0.5),
                                 ("chemical", 100.0, 0.5),
                                 ("nutrient", 100.0, 0.02)):
        for label, supply in (("十分", plenty), ("不足", scarce)):
            for n in DENSITIES:
                order = list(range(n))
                demand, gains, total = _run_density(kind, n, supply, order)
                expected = min(supply, demand)
                print(f"  {kind:<9} 供給{label} n={n:<4} 供給={supply:<8.3g}"
                      f" 総需要={demand:<10.4f} 総取得={total:<10.4f}")
                rep.check(abs(total - expected) <= 1e-9 * max(1.0, expected),
                          f"{kind} 供給{label} n={n}: 総取得=min(供給,総需要)",
                          f"{total:.6f} vs {expected:.6f}")
                # 個体順不変性 (reverse / 別RNGでのshuffle)
                for name, perm in (("reverse", order[::-1]),
                                   ("shuffle",
                                    [int(i) for i in SHUFFLE_RNG.permutation(n)])):
                    _, gains2, total2 = _run_density(kind, n, supply, perm)
                    same = all(abs(gains2[i] - gains[i])
                               <= 1e-12 * max(1.0, abs(gains[i]))
                               for i in range(n))
                    rep.check(same and abs(total2 - total) <= 1e-12 * max(1.0, total),
                              f"{kind} 供給{label} n={n}: {name} でも配分不変")
    print()


def _total_demand(kind: str, sim: Simulation) -> float:
    """配分前の総需要 (実装と同じcap規則で組み立てた参照値)。"""
    cfg = sim.cfg
    orgs = sim.organisms
    demands = []
    for o in orgs:
        area = effective_surface(o.matter)
        if kind == "light":
            raw = cfg.light_uptake_coef * o.genome[LIGHT_ABS] * area
            demands.append(min(raw, o.energy_max(cfg.energy_capacity) - o.energy))
        elif kind == "chemical":
            raw = cfg.chem_uptake * o.genome[CHEM_ABS] * area
            demands.append(min(raw, o.energy_max(cfg.energy_capacity) - o.energy))
        else:
            raw = cfg.nutrient_uptake * o.genome[NUTRIENT_ABS] * area
            room = cfg.matter_cap_frac * o.target_size - o.matter
            demands.append(min(raw, room, o.energy / cfg.matter_absorb_cost))
    return math.fsum(demands)


def section_nutrient_caps(rep: Report) -> None:
    """無機栄養は事前demandを超えず、同化コストでEnergyを負にしない。"""
    print("=" * 70)
    print("§3.4b 無機栄養の事前cap (Matter余地 / 同化Energy)")
    cell = (5, 5)
    sim = _bare_sim()
    sim.world.nutrients[cell] = 100.0
    orgs = _populate(sim, cell, 5, NUTRIENT_ABS, 5.0, 0.02)  # ほぼ無一文
    m0 = [o.matter for o in orgs]
    sim._absorb_fields()
    ok_energy = all(o.energy >= 0.0 for o in orgs)
    ok_afford = all(
        abs((o.matter - m) - 0.02 / sim.cfg.matter_absorb_cost) < 1e-12
        for o, m in zip(orgs, m0))
    rep.check(ok_energy, "同化コスト後もEnergyが非負")
    rep.check(ok_afford, "払える分しか吸収しない (affordable cap)")

    sim = _bare_sim()
    sim.world.nutrients[cell] = 100.0
    orgs = _populate(sim, cell, 3, NUTRIENT_ABS, 5.0, 50.0)
    cap = sim.cfg.matter_cap_frac * 1.0
    for o in orgs:
        o.matter = cap - 0.001
    sim._build_hashes()
    sim._absorb_fields()
    rep.check(all(o.matter <= cap + 1e-12 for o in orgs),
              "Matter貯蔵上限を超えて吸収しない")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--light-max", type=float, default=None,
                    help="診断に使うlight_max (default: Configのdefault)")
    args = ap.parse_args()
    cfg = Config() if args.light_max is None else Config(light_max=args.light_max)

    print("Exp08 Phase 0 — V1.4吸収則 決定論ベンチ")
    print(f"light_uptake_coef (Config default) = {cfg.light_uptake_coef}")
    print(f"chem_uptake = {cfg.chem_uptake} / nutrient_uptake = {cfg.nutrient_uptake}")
    print()

    rep = Report()
    section_surface(rep)
    section_light(cfg, rep)
    section_chemical(cfg, rep)
    section_density(cfg, rep)
    section_nutrient_caps(rep)

    print("=" * 70)
    print(f"確認項目 {rep.checked} 件")
    if rep.fails:
        print(f"判定: NG — {len(rep.fails)} 件が不成立")
        for f in rep.fails:
            print(f"  - {f}")
        return 1
    print("判定: OK — V1.4吸収則は仕様どおり")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
