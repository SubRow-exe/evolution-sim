"""エネルギー収支・損傷・修復・starvation homeostasis (仕様書 Ver.1.1 §5 / V1.9)。

コストはスケーリング則から導出する (人工的ペナルティを置かない)。
戻り値はすべて「熱として散逸したエネルギー」— 保存則台帳のため。

V1.9 (docs/V1.9_iLUCA再設計仕様.md §5-6): 未来情報を一切使わない
runway homeostasisを導入する。P_full (現在の内部状態だけから決まる
reference支出率) から runway=energy/P_full を求め、starvation_horizon
geneで無次元化したstateでBMR可変部/repair予算 (metabolic_factor) と
H2/light/nutrient uptake能力 (uptake_factor) を非対称に抑制する。
movement/organ/sense/membrane/resistance/storage upkeepは抑制しない。
"""
from __future__ import annotations

from .config import Config
from .genome import (CHEM_ABS, CORPSE_DIG, DAMAGE_RES, LIGHT_ABS, MEMBRANE,
                     MOVE_EFF, MOVE_POWER, NUTRIENT_ABS, PREDATION, REPAIR,
                     SENSORY, STARV_HORIZON, STORAGE_CAP)
from .organism import Organism


SURFACE_EPS = 1e-9


def density_response(x: float, k: float) -> float:
    """局所密度依存の一次Energy吸収応答 (V1.8で導入、V1.9では常時適用)。

        H(x, K) = x / (x + K)

    x=0 -> 0 / x=K -> 0.5 / xの増加で単調増加 / 高濃度で1へ飽和。
    light/H2の直接一次Energy吸収だけへ適用する
    (nutrient/corpse/predationへは適用しない)。V1.5の知覚用
    `*_stimulus_half` の response とは呼び出し元・定数が異なるため、
    式の形は同じでも混同しないこと。
    """
    if x <= 0.0:
        return 0.0
    return x / (x + k)


def effective_surface(matter: float) -> float:
    """環境と直接交換できる有効表面積 A_eff = M^(2/3) (V1.4 §3)。

    形状遺伝子がないため、同形状の3次元物体を粗視化した第一近似として扱う。
    体積 (= matter) が8倍なら線寸法2倍・表面積4倍。光/H2/無機栄養の
    「環境フィールドからの直接吸収」はすべてこの共通helperを使う。
    """
    return max(matter, SURFACE_EPS) ** (2.0 / 3.0)


# ---------------------------------------------------------------------------
# V1.9: starvation homeostasis (runway)
# ---------------------------------------------------------------------------

def full_activity_expenditure_rate(org: Organism, cfg: Config) -> float:
    """P_full: 現在のmatter/genome/damage stateだけから決まる、starvation
    抑制を一切かけない場合のreference支出率 [E/tick]。

    未来の環境・日没・将来収入は一切参照しない
    (docs/V1.9_iLUCA再設計仕様.md §5)。含めるもの: full BMR / organ /
    sense / membrane / resistance / storage upkeep / 現在damageに必要な
    範囲までのfull repair budget / reference wander movement cost。
    episodic (attack/birth/assimilation) costは含めない。
    """
    g = org.genome
    m = org.matter
    bmr = cfg.bmr_core + (cfg.bmr_coef - cfg.bmr_core) * m ** 0.75
    organ = cfg.organ_upkeep * m * (
        g[LIGHT_ABS] + g[CHEM_ABS] + g[NUTRIENT_ABS] + g[PREDATION] + g[CORPSE_DIG]
    )
    sense = cfg.sense_upkeep * g[SENSORY] ** 2
    membrane = cfg.membrane_upkeep * g[MEMBRANE] * m ** 0.5
    resist = cfg.resist_upkeep * g[DAMAGE_RES] * m
    storage = cfg.storage_upkeep_coef * g[STORAGE_CAP] * m

    phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
    repair_budget = cfg.repair_spend * g[REPAIR] * m * phi
    repair_need = org.damage / cfg.repair_eff if cfg.repair_eff > 0.0 else 0.0
    repair_ref = min(repair_budget, repair_need)

    v_max = cfg.speed_coef * g[MOVE_POWER] / (m ** 0.5 if m > 1e-9 else 1e-9 ** 0.5) * phi
    v_ref = cfg.wander_speed_frac * v_max
    move_ref = cfg.move_cost * m * v_ref * v_ref / max(g[MOVE_EFF], 1e-6)

    return bmr + organ + sense + membrane + resist + storage + repair_ref + move_ref


def runway(org: Organism, cfg: Config) -> float:
    """現在の通常活動 (P_full) をあと何tick維持できるか [tick]。"""
    p_full = full_activity_expenditure_rate(org, cfg)
    return org.energy / max(p_full, 1e-9)


def starvation_state(org: Organism, cfg: Config) -> float:
    """state = clip(runway / starvation_horizon, 0, 1)。1=十分/0=枯渇寸前。"""
    h = org.genome[STARV_HORIZON]
    r = runway(org, cfg)
    return min(1.0, max(0.0, r / max(h, 1e-9)))


def metabolic_factor(state: float, cfg: Config) -> float:
    """BMR可変部/repair予算へ掛ける抑制係数。stateが低いほど強く抑える。"""
    floor = cfg.starvation_metabolic_floor
    return floor + (1.0 - floor) * state


def uptake_factor(state: float, cfg: Config) -> float:
    """H2/light/nutrient uptake能力へ掛ける抑制係数 (弱い抑制)。"""
    floor = cfg.starvation_uptake_floor
    return floor + (1.0 - floor) * state


def clamp_energy_to_capacity(org: Organism, cfg: Config) -> float:
    """matter/genome変化後にEnergyがE_maxを超えていたら切り詰める。

    戻り値: heatとして散逸させるべき超過分 (呼び出し側でenergy_out_cumへ)。
    (docs/V1.9_iLUCA再設計仕様.md §4.2)
    """
    e_max = org.energy_max(cfg.energy_capacity_base)
    if org.energy > e_max:
        overflow = org.energy - e_max
        org.energy = e_max
        return overflow
    return 0.0


# ---------------------------------------------------------------------------
# 維持コスト・修復 (starvation homeostasisを反映)
# ---------------------------------------------------------------------------

def maintenance_and_movement(org: Organism, cfg: Config, v: float,
                              state: float) -> float:
    """基礎代謝 + 器官維持 + 移動のコストを消費し、損傷を加算する。

    `state` はそのtickのstarvation state (呼び出し側が1回だけ計算し、
    uptake_factorと共有する。evosim/simulation.py)。metabolic_factorは
    BMRのbmr_core以外の可変部分にのみ掛ける。organ/sense/membrane/
    resistance/storage upkeepとmovementはstarvation responseで抑制しない
    (docs/V1.9_iLUCA再設計仕様.md §6.1)。
    """
    g = org.genome
    m = org.matter
    mfac = metabolic_factor(state, cfg)

    bmr_variable = (cfg.bmr_coef - cfg.bmr_core) * m ** 0.75
    bmr = cfg.bmr_core + mfac * bmr_variable
    organ = cfg.organ_upkeep * m * (
        g[LIGHT_ABS] + g[CHEM_ABS] + g[NUTRIENT_ABS] + g[PREDATION] + g[CORPSE_DIG]
    )
    sense = cfg.sense_upkeep * g[SENSORY] ** 2
    membrane = cfg.membrane_upkeep * g[MEMBRANE] * m ** 0.5
    resist = cfg.resist_upkeep * g[DAMAGE_RES] * m
    storage = cfg.storage_upkeep_coef * g[STORAGE_CAP] * m
    move = cfg.move_cost * m * v * v / max(g[MOVE_EFF], 1e-6)

    cost = bmr + organ + sense + membrane + resist + storage + move
    org.energy -= cost

    # 損傷 (代謝性 + 運動性)
    org.damage += cfg.metabolic_damage * m
    org.damage += cfg.movement_damage * m * v * v
    return cost


def repair(org: Organism, cfg: Config, state: float) -> float:
    """エネルギーを消費して損傷を修復する。戻り値: 散逸エネルギー。

    repair予算はmetabolic_factorで抑制される (docs/V1.9_iLUCA再設計仕様.md §6.1)。
    """
    if org.damage <= 0.0 or org.energy <= 0.0:
        return 0.0
    phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
    mfac = metabolic_factor(state, cfg)
    budget = cfg.repair_spend * org.genome[REPAIR] * org.matter * phi * mfac
    needed = org.damage / cfg.repair_eff
    spend = min(budget, org.energy, needed)
    if spend <= 0.0:
        return 0.0
    org.energy -= spend
    org.damage = max(0.0, org.damage - cfg.repair_eff * spend)
    return spend
