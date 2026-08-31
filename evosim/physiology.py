"""エネルギー収支・損傷・修復 (仕様書 Ver.1.1 §5)。

コストはスケーリング則から導出する (人工的ペナルティを置かない)。
戻り値はすべて「熱として散逸したエネルギー」— 保存則台帳のため。
"""
from __future__ import annotations

from .config import Config
from .genome import (CHEM_ABS, CORPSE_DIG, DAMAGE_RES, LIGHT_ABS, MEMBRANE,
                     MOVE_EFF, NUTRIENT_ABS, PREDATION, REPAIR, SENSORY)
from .organism import Organism


SURFACE_EPS = 1e-9


def effective_surface(matter: float) -> float:
    """環境と直接交換できる有効表面積 A_eff = M^(2/3) (V1.4 §3)。

    形状遺伝子がないため、同形状の3次元物体を粗視化した第一近似として扱う。
    体積 (= matter) が8倍なら線寸法2倍・表面積4倍。光/化学/無機栄養の
    「環境フィールドからの直接吸収」はすべてこの共通helperを使う。
    """
    return max(matter, SURFACE_EPS) ** (2.0 / 3.0)


def maintenance_and_movement(org: Organism, cfg: Config, v: float) -> float:
    """基礎代謝 + 器官維持 + 移動のコストを消費し、損傷を加算する。"""
    g = org.genome
    s = org.matter
    m = org.matter

    bmr = cfg.bmr_coef * s ** 0.75
    organ = cfg.organ_upkeep * s * (
        g[LIGHT_ABS] + g[CHEM_ABS] + g[NUTRIENT_ABS] + g[PREDATION] + g[CORPSE_DIG]
    )
    sense = cfg.sense_upkeep * g[SENSORY] ** 2
    membrane = cfg.membrane_upkeep * g[MEMBRANE] * s ** 0.5
    resist = cfg.resist_upkeep * g[DAMAGE_RES] * s
    move = cfg.move_cost * m * v * v / max(g[MOVE_EFF], 1e-6)

    cost = bmr + organ + sense + membrane + resist + move
    org.energy -= cost

    # 損傷 (代謝性 + 運動性)
    org.damage += cfg.metabolic_damage * s
    org.damage += cfg.movement_damage * m * v * v
    return cost


def repair(org: Organism, cfg: Config) -> float:
    """エネルギーを消費して損傷を修復する。戻り値: 散逸エネルギー。"""
    if org.damage <= 0.0 or org.energy <= 0.0:
        return 0.0
    phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
    budget = cfg.repair_spend * org.genome[REPAIR] * org.matter * phi
    needed = org.damage / cfg.repair_eff
    spend = min(budget, org.energy, needed)
    if spend <= 0.0:
        return 0.0
    org.energy -= spend
    org.damage = max(0.0, org.damage - cfg.repair_eff * spend)
    return spend
