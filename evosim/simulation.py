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
                     PREDATION, REPRO_INVEST, fixed_mask_from_names,
                     initial_genome, mutate)
from .organism import Organism
from .recorder import Recorder
from .world import World


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
        self.energy_in_cum = 0.0        # 光吸収 + 化学湧出
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

        self.recorder: Recorder | None = (
            Recorder(run_dir, cfg, seed) if run_dir is not None else None)

        self._spawn_initial()
        self.initial_system_energy = self.system_energy()
        self.initial_system_matter = self.system_matter()

    # ------------------------------------------------------------------
    # 初期個体群

    def _spawn_initial(self) -> None:
        cfg = self.cfg
        for _ in range(cfg.initial_population):
            g = initial_genome(self.rng, cfg.initial_jitter_sigma, self.fixed_mask)
            x = float(self.rng.uniform(0, cfg.world_width))
            y = float(self.rng.uniform(0, cfg.world_height))
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
        self.energy_in_cum += self.world.update()

        # 2. 空間ハッシュと光分配重みの構築 (tick開始時の位置スナップショット)
        self._build_hashes()
        photo_w = self._photo_weights()

        # 3. 個体処理 (リスト順で決定的)
        newborns: list[Organism] = []
        for org in self.organisms:
            if not org.alive:
                continue
            org.age += 1
            org.attacked_recently = False
            cell0 = self.world.cell_index(org.x, org.y)

            # 行動 + 移動
            v = behavior.decide_and_move(org, self)

            # 栄養獲得
            self._absorb(org, cell0, photo_w)
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

        # 4. 死亡個体の除去・新生児の追加
        self.organisms = [o for o in self.organisms if o.alive]
        self.organisms.extend(newborns)

        # 5. 死骸の分解・散逸
        self._decay_corpses()

        # 6. 記録
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

    def _photo_weights(self) -> dict[tuple[int, int], float]:
        """セルごとの光吸収重みの合計 (光の分配 = 空間競争)。"""
        cfg = self.cfg
        weights: dict[tuple[int, int], float] = {}
        for key, orgs in self.org_hash.items():
            w = 0.0
            for o in orgs:
                a = o.genome[LIGHT_ABS]
                if a > 1e-6:
                    w += a * o.matter * o.phi(cfg.damage_capacity, cfg.phi_floor)
            if w > 0.0:
                weights[key] = w
        return weights

    # ------------------------------------------------------------------
    # 栄養獲得

    def _absorb(self, org: Organism, cell0: tuple[int, int],
                photo_w: dict[tuple[int, int], float]) -> None:
        cfg = self.cfg
        g = org.genome
        phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
        e_max = org.energy_max(cfg.energy_capacity)

        # 光 (tick開始時のセルで分配; 使われない光は流入しない=散逸)
        w_sum = photo_w.get(cell0, 0.0)
        my_w = g[LIGHT_ABS] * org.matter * phi
        if w_sum > 0.0 and my_w > 0.0:
            flux = float(self.world.light[cell0])
            share = flux * my_w / w_sum
            gain = min(share, max(0.0, e_max - org.energy))
            org.energy += gain
            self.energy_in_cum += gain
            self.flows["light"] += gain

        # 化学 (現在セルのストックから; フィールド→個体の移動なので流入計上なし)
        ix, iy = self.world.cell_index(org.x, org.y)
        if g[CHEM_ABS] > 1e-6:
            stock = float(self.world.chemical[ix, iy])
            if stock > 0.0:
                rate = cfg.chem_uptake * g[CHEM_ABS] * org.matter * phi
                u = min(rate, stock, max(0.0, e_max - org.energy))
                org.energy += u
                self.world.chemical[ix, iy] = stock - u
                self.flows["chemical"] += u

        # 無機栄養 (物質; 吸収には同化エネルギーコスト)
        matter_cap = cfg.matter_cap_frac * org.target_size
        if g[NUTRIENT_ABS] > 1e-6 and org.matter < matter_cap:
            stock = float(self.world.nutrients[ix, iy])
            if stock > 0.0:
                rate = cfg.nutrient_uptake * g[NUTRIENT_ABS] * org.matter * phi
                u = min(rate, stock, matter_cap - org.matter)
                cost = cfg.matter_absorb_cost * u
                if cost > org.energy:  # 払える分だけ吸収
                    u = org.energy / cfg.matter_absorb_cost
                    cost = org.energy
                if u > 0.0:
                    org.matter += u
                    org.energy -= cost
                    self.world.nutrients[ix, iy] = stock - u
                    self.energy_out_cum += cost
                    self.flows["nutrient"] += u

    def _eat_corpse(self, org: Organism) -> None:
        cfg = self.cfg
        g = org.genome
        if g[CORPSE_DIG] <= 1e-6:
            return
        r = org.radius(cfg.radius_coef)
        target = None
        best_d2 = None
        ix, iy = self.world.cell_index(org.x, org.y)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for c in self.corpse_hash.get((ix + dx, iy + dy), ()):
                    if c.matter <= 0.0:
                        continue
                    cr = cfg.radius_coef * math.sqrt(max(c.matter, 1e-9))
                    d2 = (c.x - org.x) ** 2 + (c.y - org.y) ** 2
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
        r = org.radius(cfg.radius_coef)
        ix, iy = self.world.cell_index(org.x, org.y)
        target = None
        best_d2 = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in self.org_hash.get((ix + dx, iy + dy), ()):
                    if other is org or not other.alive:
                        continue
                    d2 = (other.x - org.x) ** 2 + (other.y - org.y) ** 2
                    if d2 <= (r + other.radius(cfg.radius_coef)) ** 2 and (
                            best_d2 is None or d2 < best_d2):
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
