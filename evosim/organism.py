"""個体の状態。仕様書 Ver.1.1 §4 / V1.9 iLUCA再設計仕様。"""
from __future__ import annotations

import math

import numpy as np

from .genome import BODY_SIZE, DAMAGE_RES, STORAGE_CAP


class Organism:
    __slots__ = (
        "id", "parent_id", "lineage_id", "generation", "birth_tick",
        "genome", "x", "y", "heading",
        "energy", "matter", "damage",
        "age", "alive", "attacked_recently",
        # V1.6 temporal sensing の短期記憶。刺激ごとの無次元応答のEMAを持つ。
        # Q は能力加重平均なので、Q自体のEMAと応答ごとのEMAの加重平均は
        # 一致する (加重平均は線形写像で、重みは個体の生涯で不変)。
        # 応答ごとに持つのは dQ の light / chemical 寄与を厳密に分解して
        # 観測するため (V1.6仕様 §4)。
        "r_light_mem", "r_chem_mem", "has_stim_memory",
        # V1.9: capability state (docs/V1.9_iLUCA再設計仕様.md §3)。
        # 「値が0」と「能力そのものが存在しない」を区別する。
        "phototrophy_on", "predation_on",
        # V1.9: そのtickのstarvation state (0..1)。tick開始時に1回だけ計算し、
        # uptake_factor/metabolic_factorの両方がこの1つの値を共有する
        # (evosim/physiology.py)。observation専用のtransient cacheで、
        # 進化ロジックへは影響しない。
        "starve_state",
    )

    def __init__(self, oid: int, parent_id: int, lineage_id: int,
                 generation: int, birth_tick: int, genome: np.ndarray,
                 x: float, y: float, heading: float,
                 energy: float, matter: float,
                 phototrophy_on: bool = False, predation_on: bool = False):
        self.id = oid
        self.parent_id = parent_id
        self.lineage_id = lineage_id
        self.generation = generation
        self.birth_tick = birth_tick
        self.genome = genome
        self.x = x
        self.y = y
        self.heading = heading
        self.energy = energy
        self.matter = matter
        self.damage = 0.0
        self.age = 0
        self.alive = True
        self.attacked_recently = False  # 直近tickに攻撃を受けたか (死因判定用)
        # V1.6: 初回は人工的な差分を作らないため Q_memory = Q_now とする。
        # そのため「まだ一度も知覚していない」状態を明示的に持つ。
        self.r_light_mem = 0.0
        self.r_chem_mem = 0.0
        self.has_stim_memory = False
        self.phototrophy_on = phototrophy_on
        self.predation_on = predation_on
        self.starve_state = 1.0  # 最初のstep()で上書きされるまでの安全な既定値

    @property
    def capability(self) -> dict[str, bool]:
        return {"phototrophy": self.phototrophy_on, "predation": self.predation_on}

    # --- 派生量 (s_eff = 現在の身体物質量 M) ---

    @property
    def s_eff(self) -> float:
        return self.matter

    def radius(self, radius_coef: float) -> float:
        return radius_coef * math.sqrt(max(self.matter, 1e-9))

    def energy_max(self, energy_capacity_base: float) -> float:
        """V1.9: E_max = energy_capacity_base * storage_capacity * matter。

        storage_capacity gene (docs/V1.9_iLUCA再設計仕様.md §4)。
        """
        return energy_capacity_base * self.genome[STORAGE_CAP] * self.matter

    def damage_max(self, damage_capacity: float) -> float:
        return damage_capacity * self.matter * (1.0 + self.genome[DAMAGE_RES])

    def phi(self, damage_capacity: float, phi_floor: float) -> float:
        """健全度 φ = max(floor, 1 - D/D_max)。速度・吸収に乗算される。"""
        dmax = self.damage_max(damage_capacity)
        if dmax <= 0.0:
            return phi_floor
        return max(phi_floor, 1.0 - self.damage / dmax)

    @property
    def target_size(self) -> float:
        return self.genome[BODY_SIZE]
