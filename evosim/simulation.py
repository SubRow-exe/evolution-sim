"""シミュレーション本体 (仕様書 Ver.1.1 §5–8, 11, 13)。

設計原則:
- 適応度は計算しない。生存と繁殖はエネルギー・物質・損傷の帰結。
- 乱数は単一の numpy Generator。個体処理はリスト順で決定的。
- 物質は世界全体で厳密保存。エネルギーは流入・散逸を台帳で追跡。
"""
from __future__ import annotations

import math

import numpy as np

from . import behavior, physiology
from .config import Config
from .corpse import Corpse
from .genome import (CHEM_ABS, CORPSE_DIG, LIGHT_ABS, MEMBRANE, NUTRIENT_ABS,
                     PREDATION, REPRO_INVEST, diagnostic_overrides,
                     fixed_mask_from_names, initial_genome, mutate)
from .organism import Organism
from .recorder import Recorder
from .world import World

# これ未満の吸収能力は「器官を持たない」とみなす (V1.3以前と同じ閾値)
ABILITY_EPS = 1e-6


class Simulation:
    def __init__(self, cfg: Config, seed: int, run_dir=None):
        self.cfg = cfg
        self.seed = seed
        self.rng = np.random.Generator(np.random.PCG64(seed))
        self.fixed_mask = fixed_mask_from_names(cfg.fixed_genes)
        self.world = World(cfg, self.rng)
        self.tick = 0
        self.next_id = 0

        self.organisms: list[Organism] = []
        self.corpses: list[Corpse] = []
        self.org_hash: dict[tuple[int, int], list[Organism]] = {}
        self.corpse_hash: dict[tuple[int, int], list[Corpse]] = {}

        self.births_cum = 0
        self.deaths_cum = 0
        self.deaths_by_cause = {c: 0 for c in
                                ("starvation", "damage", "predation", "disaster")}

        # エネルギー台帳 (保存則検証用)
        self.energy_in_cum = 0.0        # 光吸収 + 化学source
        self.energy_out_cum = 0.0       # 全散逸 (熱)

        # 資源利用率 (改善方針 Ver.1.2 §5): 経路別の累積獲得量。進化には不使用
        self.flows = {
            "light": 0.0,             # 光から得たエネルギー
            "chemical": 0.0,          # 化学ストックから得たエネルギー
            "nutrient": 0.0,          # 無機栄養から得た物質
            "corpse_matter": 0.0,     # 死骸から同化した物質
            "corpse_energy": 0.0,     # 死骸から得たエネルギー
            "predation_energy": 0.0,  # 捕食で得たエネルギー
            "predation_matter": 0.0,  # 捕食で同化した物質
        }
        # 世界全体の光供給量/tick (未利用光量の算出用・不変)
        self.light_supply_per_tick = float(self.world.light.sum())
        # 系統別の累積出生数 (系統別統計用)
        self.births_by_lineage: dict[int, int] = {}

        # 移動量の集計 (V1.2.1 観測)。stats記録ごとにリセットされる区間統計。
        # 読み取り専用であり進化ロジックには一切使わない。
        self._move_sum = 0.0
        self._move_count = 0
        self._move_by_lineage: dict[int, float] = {}
        self._movecnt_by_lineage: dict[int, int] = {}

        self.recorder: Recorder | None = (
            Recorder(run_dir, cfg, seed) if run_dir is not None else None)

        self._spawn_initial()
        self.initial_system_energy = self.system_energy()
        self.initial_system_matter = self.system_matter()

    # ------------------------------------------------------------------
    # 初期個体群

    def _vent_cells(self) -> list[tuple[int, int]]:
        """化学噴出口セルの一覧 (添字順で決定的)。乱数を消費しない。"""
        cells = [(int(ix), int(iy))
                 for ix, iy in np.argwhere(self.world.chem_mask)]
        if not cells:
            raise ValueError(
                "diagnostic_placement='vent' だが chem_mask が空 "
                "(n_vents / vent_radius_cells を確認すること)")
        return cells

    def _spawn_initial(self) -> None:
        cfg = self.cfg
        # Exp06診断ハーネス (docs/Exp06_実験計画.md §5)。
        # 既定 (placement="random" / overrides無し) では下の分岐に入らず、
        # 乱数消費も含めて通常実行と完全に同一の経路を通る。
        if cfg.diagnostic_placement not in ("random", "vent"):
            raise ValueError(
                f"未知の diagnostic_placement: {cfg.diagnostic_placement!r} "
                "(random | vent)")
        overrides = diagnostic_overrides(cfg)
        vent_cells = (self._vent_cells() if cfg.diagnostic_placement == "vent"
                      else None)

        for _ in range(cfg.initial_population):
            g = initial_genome(self.rng, cfg.initial_jitter_sigma, self.fixed_mask)
            if overrides is not None:
                # 上書きは乱数を消費しない (同一seedで配置・変異系列を変えない)
                for idx, value in overrides:
                    g[idx] = value
            if vent_cells is None:
                x = float(self.rng.uniform(0, cfg.world_width))
                y = float(self.rng.uniform(0, cfg.world_height))
            else:
                ix, iy = vent_cells[int(self.rng.integers(0, len(vent_cells)))]
                x = float((ix + self.rng.random()) * cfg.cell_size)
                y = float((iy + self.rng.random()) * cfg.cell_size)
            org = Organism(self.next_id, -1, self.next_id, 0, 0, g,
                           x, y, float(self.rng.uniform(-math.pi, math.pi)),
                           cfg.initial_energy, cfg.initial_matter)
            self.next_id += 1
            self.organisms.append(org)
            if self.recorder:
                self.recorder.birth(0, org)
            self.births_cum += 1
            self.births_by_lineage[org.lineage_id] = (
                self.births_by_lineage.get(org.lineage_id, 0) + 1)
        # 初期個体の身体物質は栄養プール外から与えられたものとして台帳初期化
        # (initial_system_matter に含まれるので保存則は成立する)

    # ------------------------------------------------------------------
    # 集計 (保存則)

    def system_energy(self) -> float:
        return (sum(o.energy for o in self.organisms)
                + sum(c.energy for c in self.corpses)
                + self.world.total_chemical())

    def system_matter(self) -> float:
        return (sum(o.matter for o in self.organisms)
                + sum(c.matter for c in self.corpses)
                + self.world.total_nutrients())

    # ------------------------------------------------------------------
    # メインループ

    def step(self) -> None:
        cfg = self.cfg
        self.tick += 1

        # 1. 環境更新 (化学湧出はエネルギー流入)
        chem_influx, chem_loss = self.world.update()
        self.energy_in_cum += chem_influx
        self.energy_out_cum += chem_loss

        # 2. 空間ハッシュ (tick開始時の位置スナップショット)。
        #    行動決定はこの時点の刺激場・配置を見る。
        self._build_hashes()

        # 3. 全個体の行動決定と移動 (リスト順で決定的)
        moved: list[tuple[Organism, float]] = []
        for org in self.organisms:
            if not org.alive:
                continue
            org.age += 1
            org.attacked_recently = False
            v = behavior.decide_and_move(org, self)
            moved.append((org, v))
            # 移動量の集計 (V1.2.1 観測)。読み取り専用で、RNGにも
            # 個体状態にも一切フィードバックしない。
            self._move_sum += v
            self._move_count += 1
            self._move_by_lineage[org.lineage_id] = (
                self._move_by_lineage.get(org.lineage_id, 0.0) + v)
            self._movecnt_by_lineage[org.lineage_id] = (
                self._movecnt_by_lineage.get(org.lineage_id, 0) + 1)

        # 4. 移動後の空間ハッシュを再構築 (V1.4)。
        #    以降の吸収・局所相互作用はすべて移動後の位置で判定する。
        self._build_hashes()

        # 5. 環境フィールドからの吸収 (セル単位の需要比例配分・個体順に非依存)
        self._absorb_fields()

        # 6. 局所相互作用〜繁殖 (従来どおり個体逐次・リスト順で決定的)
        newborns: list[Organism] = []
        for org, v in moved:
            if not org.alive:
                continue
            self._eat_corpse(org)
            self._predate(org)

            # 生理 (維持コスト・損傷・修復)
            self.energy_out_cum += physiology.maintenance_and_movement(org, cfg, v)
            self.energy_out_cum += physiology.repair(org, cfg)

            # 死亡判定
            if org.energy <= 0.0:
                self._kill(org, "starvation")
                continue
            if org.damage >= org.damage_max(cfg.damage_capacity):
                self._kill(org, "predation" if org.attacked_recently else "damage")
                continue

            # 繁殖
            child = self._try_reproduce(org)
            if child is not None:
                newborns.append(child)

        # 7. 死亡個体の除去・新生児の追加
        self.organisms = [o for o in self.organisms if o.alive]
        self.organisms.extend(newborns)

        # 8. 死骸の分解・散逸
        self._decay_corpses()

        # 9. 記録
        if self.recorder:
            if self.tick % cfg.stats_interval == 0:
                self.recorder.stats(self)
            if self.tick % cfg.snapshot_interval == 0:
                self.recorder.snapshot(self)

    # ------------------------------------------------------------------
    # 空間ハッシュ

    def _build_hashes(self) -> None:
        self.org_hash = {}
        for o in self.organisms:
            key = self.world.cell_index(o.x, o.y)
            self.org_hash.setdefault(key, []).append(o)
        self.corpse_hash = {}
        for c in self.corpses:
            key = self.world.cell_index(c.x, c.y)
            self.corpse_hash.setdefault(key, []).append(c)

    # ------------------------------------------------------------------
    # 環境フィールドからの吸収 (V1.4)

    def _absorb_fields(self) -> None:
        """光・化学・無機栄養をセル単位で配分する (V1.4 §4-6)。

        セルごとに全個体の要求量 (demand) を先に求め、供給が足りなければ
        需要比例で縮小する。総取得は必ず ``min(供給, 総需要)`` になり、
        個体リスト順は配分結果に影響しない (V1.3以前の先着biasを廃止)。

        資源間の順序 (光 → 化学 → 無機栄養) はV1.3以前と同じ。有効表面積と
        健全度はセル処理の開始時点で一度だけ求め、3資源で共有する。
        """
        cfg = self.cfg
        dc, pf = cfg.damage_capacity, cfg.phi_floor
        for key, orgs in self.org_hash.items():
            phis = [o.phi(dc, pf) for o in orgs]
            areas = [physiology.effective_surface(o.matter) for o in orgs]
            self._absorb_light(orgs, phis, areas, key)
            self._absorb_chemical(orgs, phis, areas, key)
            self._absorb_nutrient(orgs, phis, areas, key)

    @staticmethod
    def _demand_scale(demands: list[float], supply: float) -> float:
        """需要比例配分の縮小率。総需要が供給以下なら1.0 (未利用分は残る)。

        合計に ``math.fsum`` を使うので、個体の並び順を変えても縮小率は
        ビット単位で同じになる。
        """
        if supply <= 0.0:
            return 0.0
        total = math.fsum(demands)
        if total <= 0.0:
            return 0.0
        return min(1.0, supply / total)

    def _absorb_light(self, orgs, phis, areas, key) -> None:
        """光: 個体の変換能力が上限。未利用光はそのtickで散逸する。"""
        cfg = self.cfg
        flux = float(self.world.light[key])
        if flux <= 0.0:
            return
        coef = cfg.light_uptake_coef
        cap = cfg.energy_capacity
        demands = []
        for o, phi, area in zip(orgs, phis, areas):
            a = o.genome[LIGHT_ABS]
            if a <= ABILITY_EPS:
                demands.append(0.0)
                continue
            raw = coef * a * area * phi
            demands.append(min(raw, max(0.0, o.energy_max(cap) - o.energy)))
        scale = self._demand_scale(demands, flux)
        if scale <= 0.0:
            return
        gains = []
        for o, d in zip(orgs, demands):
            if d <= 0.0:
                continue
            gain = d * scale
            o.energy += gain
            gains.append(gain)
        taken = math.fsum(gains)
        self.energy_in_cum += taken
        self.flows["light"] += taken

    def _absorb_chemical(self, orgs, phis, areas, key) -> None:
        """化学: 局所stockから吸収 (フィールド→個体の移動なので流入計上なし)。"""
        cfg = self.cfg
        stock = float(self.world.chemical[key])
        if stock <= 0.0:
            return
        rate = cfg.chem_uptake
        cap = cfg.energy_capacity
        demands = []
        for o, phi, area in zip(orgs, phis, areas):
            a = o.genome[CHEM_ABS]
            if a <= ABILITY_EPS:
                demands.append(0.0)
                continue
            raw = rate * a * area * phi
            demands.append(min(raw, max(0.0, o.energy_max(cap) - o.energy)))
        scale = self._demand_scale(demands, stock)
        if scale <= 0.0:
            return
        gains = []
        for o, d in zip(orgs, demands):
            if d <= 0.0:
                continue
            gain = d * scale
            o.energy += gain
            gains.append(gain)
        taken = math.fsum(gains)
        self.world.chemical[key] = max(0.0, stock - taken)
        self.flows["chemical"] += taken

    def _absorb_nutrient(self, orgs, phis, areas, key) -> None:
        """無機栄養 (物質): 吸収には同化エネルギーコストがかかる。

        配分前の要求量を、身体物質の余地と「現在のエネルギーで同化コストを
        払える量」でもcapする。したがって配分後にEnergyが負にならない。
        """
        cfg = self.cfg
        stock = float(self.world.nutrients[key])
        if stock <= 0.0:
            return
        rate = cfg.nutrient_uptake
        acost = cfg.matter_absorb_cost
        demands = []
        for o, phi, area in zip(orgs, phis, areas):
            a = o.genome[NUTRIENT_ABS]
            if a <= ABILITY_EPS:
                demands.append(0.0)
                continue
            room = cfg.matter_cap_frac * o.target_size - o.matter
            if room <= 0.0:
                demands.append(0.0)
                continue
            affordable = o.energy / acost
            demands.append(min(rate * a * area * phi, room, affordable))
        scale = self._demand_scale(demands, stock)
        if scale <= 0.0:
            return
        gains = []
        for o, d in zip(orgs, demands):
            if d <= 0.0:
                continue
            u = d * scale
            cost = acost * u
            if cost > o.energy:  # 浮動小数の端数対策 (demand段階でcap済み)
                u = o.energy / acost
                cost = o.energy
            o.matter += u
            o.energy -= cost
            self.energy_out_cum += cost
            gains.append(u)
        taken = math.fsum(gains)
        self.world.nutrients[key] = max(0.0, stock - taken)
        self.flows["nutrient"] += taken

    def _eat_corpse(self, org: Organism) -> None:
        cfg = self.cfg
        g = org.genome
        if g[CORPSE_DIG] <= 1e-6:
            return
        # 内側ループは1 tickあたり数万回まわるため、属性参照とメソッド呼び出しを
        # ローカルへ引き上げてある。計算式と走査順序は元のまま (結果は同一)。
        rc = cfg.radius_coef
        m = org.matter
        r = rc * math.sqrt(m if m > 1e-9 else 1e-9)
        ox, oy = org.x, org.y
        target = None
        best_d2 = None
        ix, iy = self.world.cell_index(ox, oy)
        chash = self.corpse_hash
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = chash.get((ix + dx, iy + dy))
                if not cell:
                    continue
                for c in cell:
                    cm = c.matter
                    if cm <= 0.0:
                        continue
                    cr = rc * math.sqrt(cm if cm > 1e-9 else 1e-9)
                    d2 = (c.x - ox) ** 2 + (c.y - oy) ** 2
                    if d2 <= (r + cr) ** 2 and (best_d2 is None or d2 < best_d2):
                        target, best_d2 = c, d2
        if target is None:
            return
        phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
        e_max = org.energy_max(cfg.energy_capacity)
        matter_cap = cfg.matter_cap_frac * org.target_size

        bite = min(cfg.corpse_eat_rate * g[CORPSE_DIG] * org.matter * phi, target.matter)
        if bite <= 0.0:
            return
        # 物質: 同化率で取り込み、残りは排泄として栄養フィールドへ (厳密保存)
        assim = min(bite * cfg.assimilation, max(0.0, matter_cap - org.matter))
        waste = bite - assim
        org.matter += assim
        cx, cy = self.world.cell_index(target.x, target.y)
        self.world.nutrients[cx, cy] += waste
        # エネルギー: 死骸の残エネルギーを物質比で同時取得
        e_frac = bite / target.matter if target.matter > 0 else 0.0
        e_take = target.energy * e_frac
        e_gain = min(e_take * cfg.assimilation, max(0.0, e_max - org.energy))
        org.energy += e_gain
        self.energy_out_cum += e_take - e_gain
        target.energy -= e_take
        target.matter -= bite
        self.flows["corpse_matter"] += assim
        self.flows["corpse_energy"] += e_gain

    def _predate(self, org: Organism) -> None:
        cfg = self.cfg
        g = org.genome
        if g[PREDATION] <= 1e-6:
            return
        rc = cfg.radius_coef
        m = org.matter
        r = rc * math.sqrt(m if m > 1e-9 else 1e-9)
        ox, oy = org.x, org.y
        ix, iy = self.world.cell_index(ox, oy)
        target = None
        best_d2 = None
        ohash = self.org_hash
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = ohash.get((ix + dx, iy + dy))
                if not cell:
                    continue
                for other in cell:
                    if other is org or not other.alive:
                        continue
                    d2 = (other.x - ox) ** 2 + (other.y - oy) ** 2
                    if best_d2 is not None and d2 >= best_d2:
                        continue
                    om = other.matter
                    orad = rc * math.sqrt(om if om > 1e-9 else 1e-9)
                    if d2 <= (r + orad) ** 2:
                        target, best_d2 = other, d2
        if target is None:
            return
        phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
        attack = cfg.attack_coef * g[PREDATION] * org.matter * phi
        defense = cfg.defense_coef * target.genome[MEMBRANE] * target.matter
        net = attack - defense
        cost = cfg.attack_cost * g[PREDATION] * org.matter
        org.energy -= cost
        self.energy_out_cum += cost
        if net <= 0.0:
            return
        target.damage += net
        target.attacked_recently = True
        e_max = org.energy_max(cfg.energy_capacity)
        matter_cap = cfg.matter_cap_frac * org.target_size

        # エネルギー吸取
        e_take = min(target.energy, cfg.bite_energy * net)
        e_gain = min(e_take * cfg.assimilation, max(0.0, e_max - org.energy))
        target.energy -= e_take
        org.energy += e_gain
        self.energy_out_cum += e_take - e_gain
        # 物質吸取 (残りは排泄 → 栄養フィールド)
        m_take = min(target.matter, cfg.bite_matter * net)
        m_gain = min(m_take * cfg.assimilation, max(0.0, matter_cap - org.matter))
        target.matter -= m_take
        org.matter += m_gain
        self.flows["predation_energy"] += e_gain
        self.flows["predation_matter"] += m_gain
        tx, ty = self.world.cell_index(target.x, target.y)
        self.world.nutrients[tx, ty] += m_take - m_gain
        # 咬まれて身体を失った獲物のエネルギー上限超過分は散逸
        t_emax = target.energy_max(cfg.energy_capacity)
        if target.energy > t_emax:
            self.energy_out_cum += target.energy - t_emax
            target.energy = t_emax

    # ------------------------------------------------------------------
    # 死亡・死骸

    def _kill(self, org: Organism, cause: str) -> None:
        org.alive = False
        if org.energy < 0.0:
            # コストは全額散逸として計上済みだが、実在したのは残額のみ。
            # 過剰計上分を台帳から戻す (保存則を厳密に保つ)。
            self.energy_out_cum += org.energy
            org.energy = 0.0
        self.deaths_cum += 1
        self.deaths_by_cause[cause] += 1
        self.corpses.append(Corpse(org.x, org.y, org.matter, org.energy))
        if self.recorder:
            self.recorder.death(self.tick, org, cause)

    def _decay_corpses(self) -> None:
        cfg = self.cfg
        survivors = []
        for c in self.corpses:
            ix, iy = self.world.cell_index(c.x, c.y)
            decay_m = c.matter * cfg.corpse_decay
            c.matter -= decay_m
            self.world.nutrients[ix, iy] += decay_m
            decay_e = c.energy * cfg.corpse_energy_decay
            c.energy -= decay_e
            self.energy_out_cum += decay_e
            if c.matter < cfg.corpse_min_matter:
                self.world.nutrients[ix, iy] += c.matter
                self.energy_out_cum += c.energy
                continue
            survivors.append(c)
        self.corpses = survivors

    # ------------------------------------------------------------------
    # 繁殖 (無性生殖)

    def _try_reproduce(self, org: Organism) -> Organism | None:
        cfg = self.cfg
        e_max = org.energy_max(cfg.energy_capacity)
        if org.energy < cfg.repro_energy_frac * e_max:
            return None
        if org.matter < cfg.repro_matter_frac * org.target_size:
            return None

        # 出産オーバーヘッド
        org.energy -= cfg.birth_overhead
        self.energy_out_cum += cfg.birth_overhead

        child_genome = mutate(org.genome, self.rng,
                              cfg.meta_mutation_sigma, cfg.additive_mutation_frac,
                              self.fixed_mask)

        # 物質・エネルギーの譲渡 (親→子; 保存)
        m_child = cfg.child_matter_frac * org.matter
        org.matter -= m_child
        e_offer = org.genome[REPRO_INVEST] * org.energy
        child_emax = cfg.energy_capacity * m_child
        e_child = min(e_offer, child_emax)
        org.energy -= e_child

        # 親のエネルギー上限は身体縮小で下がる → 超過分は散逸
        p_emax = org.energy_max(cfg.energy_capacity)
        if org.energy > p_emax:
            self.energy_out_cum += org.energy - p_emax
            org.energy = p_emax

        ang = float(self.rng.uniform(-math.pi, math.pi))
        dist = org.radius(cfg.radius_coef) * 2.0
        cx = min(max(org.x + math.cos(ang) * dist, 1.0), cfg.world_width - 1.0)
        cy = min(max(org.y + math.sin(ang) * dist, 1.0), cfg.world_height - 1.0)

        child = Organism(self.next_id, org.id, org.lineage_id,
                         org.generation + 1, self.tick, child_genome,
                         cx, cy, ang, e_child, m_child)
        self.next_id += 1
        self.births_cum += 1
        self.births_by_lineage[child.lineage_id] = (
            self.births_by_lineage.get(child.lineage_id, 0) + 1)
        if self.recorder:
            self.recorder.birth(self.tick, child)
        return child

    # ------------------------------------------------------------------

    def close(self) -> None:
        if self.recorder:
            self.recorder.close()
