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


# ---------------------------------------------------------------------------
# V1.9物理スケール検証パッチ (docs/V1.9_検証実装仕様_物理スケール版.md)
#
# physical_mode=False (既定) では、このセクションの関数は一切呼ばれず、
# PR #67 のarbitrary-unit式 (このファイル後半) がそのまま使われる。
# physical_mode=True のときだけ、SI単位のH2/basal/growth/movement式へ
# 切り替える。
# ---------------------------------------------------------------------------

def dry_mass_kg(matter: float, cfg: Config) -> float:
    return matter * cfg.matter_unit_to_kgdw


def reference_basal_power_w(cfg: Config) -> float:
    """reference phenotype (body_size=1, matter=1) のbasal power [W]。

    0.116 mmol ATP/(gDW h) * reference dry mass * 50 kJ/mol ATP
    ≈ 0.45 fW/cell (docs §8)。
    """
    atp_rate_mol_per_kgdw_s = cfg.basal_atp_mmol_per_gdw_h / 3600.0
    return atp_rate_mol_per_kgdw_s * cfg.reference_dry_mass_kg * cfg.atp_energy_j_per_mol


def _basal_component_fractions(genome, matter: float) -> dict[str, float]:
    """各basal componentの「reference genomeに対する相対値」(reference=1)。

    reference genomeでの各項の値で正規化するので、reference genomeでは
    どのcomponentも1.0になり、二重計上せずtotal=reference_basal_powerになる
    (docs §8)。
    """
    from .genome import INITIAL_GENOME
    ref = INITIAL_GENOME

    def frac(actual: float, ref_val: float) -> float:
        return actual / ref_val if ref_val > 0.0 else 0.0

    organ_actual = matter * (genome[LIGHT_ABS] + genome[CHEM_ABS] + genome[NUTRIENT_ABS]
                             + genome[PREDATION] + genome[CORPSE_DIG])
    organ_ref = 1.0 * (ref[LIGHT_ABS] + ref[CHEM_ABS] + ref[NUTRIENT_ABS]
                       + ref[PREDATION] + ref[CORPSE_DIG])
    return {
        "core": matter / 1.0,
        "organ": frac(organ_actual, organ_ref),
        "sense": frac(genome[SENSORY] ** 2, ref[SENSORY] ** 2),
        "membrane": frac(genome[MEMBRANE] * matter ** 0.5, ref[MEMBRANE] * 1.0 ** 0.5),
        "resistance": frac(genome[DAMAGE_RES] * matter, ref[DAMAGE_RES] * 1.0),
        "storage": frac(genome[STORAGE_CAP] * matter, ref[STORAGE_CAP] * 1.0),
    }


def physical_basal_power_w(org: Organism, cfg: Config) -> float:
    """個体の現在genome/matterでのbasal power [W] (docs §8)。"""
    p_ref = reference_basal_power_w(cfg)
    fr = _basal_component_fractions(org.genome, org.matter)
    return p_ref * (
        cfg.basal_weight_core * fr["core"]
        + cfg.basal_weight_organ * fr["organ"]
        + cfg.basal_weight_sense * fr["sense"]
        + cfg.basal_weight_membrane * fr["membrane"]
        + cfg.basal_weight_resistance * fr["resistance"]
        + cfg.basal_weight_storage * fr["storage"]
    )


def physical_energy_max_j(org: Organism, cfg: Config) -> float:
    """E_max [J] = E_max_ref * storage_capacity * matter (docs §8)。

    E_max_ref = reference basal power * storage_capacity_hours。
    """
    e_max_ref = reference_basal_power_w(cfg) * cfg.storage_capacity_hours * 3600.0
    return e_max_ref * org.genome[STORAGE_CAP] * org.matter


def physical_radius_m(matter: float, cfg: Config) -> float:
    """物理半径 [m]。V = reference_cell_volume * matter を球体積とみなす。"""
    import math
    volume = cfg.reference_cell_volume_m3 * max(matter, SURFACE_EPS)
    return (3.0 * volume / (4.0 * math.pi)) ** (1.0 / 3.0)


def physical_move_power_w(matter: float, v_m_s: float, cfg: Config) -> float:
    """移動power [W]。Stokes抗力 P_mech=6*pi*eta*r*v^2 / motor efficiency (docs §10)。"""
    import math
    r = physical_radius_m(matter, cfg)
    p_mech = 6.0 * math.pi * cfg.water_viscosity_pa_s * r * v_m_s * v_m_s
    return p_mech / cfg.motor_efficiency


def physical_h2_uptake_rate_mol_s(concentration_molm3: float, matter: float,
                                  chemical_absorption: float, uptake_factor_: float,
                                  cfg: Config) -> float:
    """H2 uptake demand [mol/s]。Michaelis-Menten (docs §6)。

        q_H2(C) = q_max * C / (K_m + C)      [mol/(kgDW s)]
        J_H2    = q_H2(C) * dry_mass * chemical_absorption * uptake_factor
    """
    if concentration_molm3 <= 0.0:
        return 0.0
    q = cfg.h2_qmax_mol_per_kgdw_s * concentration_molm3 / (cfg.h2_km_mol_m3 + concentration_molm3)
    mass_kg = dry_mass_kg(matter, cfg)
    return q * mass_kg * chemical_absorption * max(uptake_factor_, 0.0)


def physical_growth_energy_cost_j(delta_matter: float, cfg: Config) -> float:
    """Matterをdelta_matterだけ新規合成するEnergy cost [J] (docs §9)。"""
    return max(delta_matter, 0.0) * cfg.matter_unit_to_kgdw * cfg.growth_energy_j_per_kgdw


def physical_full_activity_expenditure_rate_w(org: Organism, cfg: Config) -> float:
    """P_full [W] (physical mode版)。§12: 単位だけseconds/J/Wへ変更、構造は
    arbitrary-unit版と同じ (repair budgetはfull、movementはreference wander)。
    """
    basal = physical_basal_power_w(org, cfg)
    phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
    # repair: 現在damageに必要な範囲までのfull budget。ATP経由のJ/sは
    # basalと同じ換算 (organ upkeepと同枠のcoarse-grained参照値として
    # repair_spend遺伝子由来のarbitrary式をJ/s換算する)。
    p_ref = reference_basal_power_w(cfg)
    repair_budget_w = p_ref * cfg.repair_spend * org.genome[REPAIR] * org.matter * phi
    repair_need_j_per_s = org.damage / cfg.repair_eff if cfg.repair_eff > 0.0 else 0.0
    repair_ref = min(repair_budget_w, repair_need_j_per_s)

    v_max = _physical_v_max_m_s(org, cfg)
    v_ref = cfg.wander_speed_frac * v_max
    move_ref = physical_move_power_w(org.matter, v_ref, cfg)
    return basal + repair_ref + move_ref


def _physical_v_max_m_s(org: Organism, cfg: Config) -> float:
    """docs §10: baseline movement_power=0.5 -> v_max≈20 µm/s。

    既存の形 v_max = speed_coef * movement_power / sqrt(matter) * phi を
    そのまま維持し、speed_coefだけをm/s単位の物理reference値へ校正する
    (Exp15 configで speed_coef=40e-6 を渡す)。
    """
    g = org.genome
    phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
    m = max(org.matter, 1e-9)
    return cfg.speed_coef * g[MOVE_POWER] / (m ** 0.5) * phi


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

def energy_max(org: Organism, cfg: Config) -> float:
    """E_max。physical_modeでJ、arbitrary modeで旧arbitrary unit。"""
    if cfg.physical_mode:
        return physical_energy_max_j(org, cfg)
    return org.energy_max(cfg.energy_capacity_base)


def full_activity_expenditure_rate(org: Organism, cfg: Config) -> float:
    """P_full: 現在のmatter/genome/damage stateだけから決まる、starvation
    抑制を一切かけない場合のreference支出率 [E/tick] (physical_modeではW)。

    未来の環境・日没・将来収入は一切参照しない
    (docs/V1.9_iLUCA再設計仕様.md §5)。含めるもの: full BMR / organ /
    sense / membrane / resistance / storage upkeep / 現在damageに必要な
    範囲までのfull repair budget / reference wander movement cost。
    episodic (attack/birth/assimilation) costは含めない。
    """
    if cfg.physical_mode:
        return physical_full_activity_expenditure_rate_w(org, cfg)
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
    e_max = energy_max(org, cfg)
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

    physical_mode時は`v`をm/sとして扱い、costはJ (dt_secondsで実際の
    per-step支出へ換算する呼び出し側 (simulation.py) と対になる)。
    """
    if cfg.physical_mode:
        return _physical_maintenance_and_movement(org, cfg, v, state)
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


def _physical_maintenance_and_movement(org: Organism, cfg: Config, v: float,
                                       state: float) -> float:
    """physical_mode版 (docs §8/§10/§12)。

    実装判断: physical basal power (core/organ/sense/membrane/resistance/
    storage の6成分合算) は全体をstarvation responseで抑制しない
    (AGENTS.md HARD RULE「bmr_coreは抑制しない」を安全側で満たすため。
    physicalの正規化basal分解には旧bmr_core/bmr変動部のような明確な
    再分割が無いため、抑制対象をrepair予算のみに限定する。
    docs/V1.9_実装報告.md で報告する実装判断)。movementも抑制しない。
    """
    basal = physical_basal_power_w(org, cfg)
    move = physical_move_power_w(org.matter, v, cfg)
    cost_w = basal + move
    cost_j = cost_w * cfg.dt_seconds
    org.energy -= cost_j
    org.damage += cfg.metabolic_damage * org.matter
    org.damage += cfg.movement_damage * org.matter * v * v
    return cost_j


def repair(org: Organism, cfg: Config, state: float) -> float:
    """エネルギーを消費して損傷を修復する。戻り値: 散逸エネルギー。

    repair予算はmetabolic_factorで抑制される (docs/V1.9_iLUCA再設計仕様.md §6.1)。
    """
    if org.damage <= 0.0 or org.energy <= 0.0:
        return 0.0
    phi = org.phi(cfg.damage_capacity, cfg.phi_floor)
    mfac = metabolic_factor(state, cfg)
    if cfg.physical_mode:
        p_ref = reference_basal_power_w(cfg)
        budget_w = p_ref * cfg.repair_spend * org.genome[REPAIR] * org.matter * phi * mfac
        budget = budget_w * cfg.dt_seconds
    else:
        budget = cfg.repair_spend * org.genome[REPAIR] * org.matter * phi * mfac
    needed = org.damage / cfg.repair_eff
    spend = min(budget, org.energy, needed)
    if spend <= 0.0:
        return 0.0
    org.energy -= spend
    org.damage = max(0.0, org.damage - cfg.repair_eff * spend)
    return spend
