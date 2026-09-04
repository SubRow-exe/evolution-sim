"""全シミュレーションパラメータ。

仕様書 Ver.1.1 の数値はすべてここに集約する。
実行ごとに config.json として保存され、seed と合わせて完全再現の根拠となる。
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    # --- 世界 ---
    world_width: float = 800.0
    world_height: float = 800.0
    cell_size: float = 20.0  # 環境グリッドのセル辺長 [wu]

    # --- 光 (フロー型エネルギー流入) ---
    light_max: float = 1.2          # 最大セル光フラックス [E/tick]
    # "vertical" (V1.1 Control) | "uniform" | "high_contrast_vertical" (V1.2)
    light_pattern: str = "vertical"
    light_floor: float = 0.3         # vertical 勾配の下限割合
    # V1.4: 光利用能力 → 個体の1 tickあたり最大変換速度への変換係数。
    # Exp08 Phase A で校正した恒久default (docs/V1.4_総括.md §3)。
    light_uptake_coef: float = 2.0

    # --- V1.2: high_contrast_vertical の形状 ---
    # 北から「明部plateau → 線形遷移 → 暗部」の3帯を作る。
    # shape を作った後、同じConfigの vertical が持つ総光量へ正規化するため、
    # 形状 (空間偏在) と総光量を独立に振れる。Exp05 では total_scale=1.0 固定。
    light_hc_bright_frac: float = 0.20       # 明部plateauが占める縦方向の割合
    light_hc_transition_frac: float = 0.50   # 線形遷移帯が占める割合
    light_hc_dark_floor: float = 0.0         # 暗部の相対光量 (0 = 完全暗部)
    light_hc_total_scale: float = 1.0        # Control総光量に対する倍率

    # --- V1.9: chemical-first H2 substrate (docs/V1.9_iLUCA再設計仕様.md §8-12) ---
    # 旧 `chemical` field の意味をH2-like substrateへ変更する。H2はEnergy
    # そのものではなくsubstrate: uptake -> chemical free energy -> conversion
    # -> usable Energy + heat。CO2は十分存在する暗黙の共基質として扱う
    # (explicit fieldを持たない)。
    #
    # vent配置: 全vent同一総flux・world端からr以上内側・source disk非重複・
    # 固定位置 (docs/V1.9_iLUCA再設計仕様.md §9)。
    n_vents: int = 4
    vent_radius_cells: int = 2
    h2_vent_flux: float = 16.0       # 1 ventの総外部供給 [substrate/tick/vent]
    h2_loss_frac: float = 0.10       # 環境損失割合 [1/tick]
    h2_diffusion: float = 0.05       # 4近傍ラプラシアン拡散係数
    h2_uptake_coef: float = 0.5      # 吸収レート係数
    h2_uptake_half: float = 6.15     # Monod/Hill H(C,K) のhalf-saturation
    h2_energy_yield: float = 1.0     # substrate 1単位あたりのchemical free energy
    h2_conversion_eff: float = 0.60  # free energy -> usable Energyの変換効率

    # --- 旧V1.8 chemical field名 (deprecated: V1.9では未使用。過去configの
    # JSON round-tripのためfieldだけ残す) ---
    chem_vent_flux: float = 16.0
    chem_loss_frac: float = 0.10
    chem_uptake: float = 0.5

    # --- V1.8: 一次Energy生態非対称 (docs/V1.8_一次Energy生態非対称仕様.md) ---
    # light/chemicalの直接一次Energy吸収だけへ、共通の局所密度応答
    #   H(x,K) = x / (x+K)   x=0->0 / x=K->0.5 / 単調増加 / 高濃度で1へ飽和
    # を導入する。nutrient/corpse/predationへは適用しない。
    # V1.5の知覚用 *_stimulus_half とは別物 (混同しないこと)。
    # 選定前defaultはfeature OFF (V1.7完全回帰)。恒久値はExp13で選定する。
    primary_energy_density_response: bool = False
    light_uptake_half: float = 0.6       # light密度応答のhalf-saturation
    chemical_uptake_half: float = 6.15   # 暫定default。Exp13でsweepし選定する

    # V1.8: light day/night半周期 (half-sine)。World.lightは昼のbase/peak
    # 空間fieldとして保持し、そのtickの利用可能光は
    #   F_light(tick) = World.light * daylight_factor(tick)
    # で決める。daylight_factorはenergy中立へ正規化しない
    # (docs/V1.8_Exp13_レビュー判断.md M-1: 昼夜で一周期総光量が静的世界より
    # 減ることは意図した性質)。選定前defaultはfeature OFF (常時1.0)。
    light_cycle_enabled: bool = False
    light_cycle_period_ticks: int = 200  # 1周期のtick数
    light_day_fraction: float = 0.5      # 周期中で昼が占める割合 (0,1)

    # --- 無機栄養 (物質・厳密保存・再生なし) ---
    nutrient_initial: float = 2.0    # 初期ストック [M/セル]
    nutrient_diffusion: float = 0.05  # 拡散係数
    nutrient_uptake: float = 0.05    # 吸収レート係数
    matter_absorb_cost: float = 2.0  # 物質1単位の同化エネルギーコスト

    # --- 個体スケール ---
    # V1.9: energy_capacity はdeprecated (旧 world-rule互換のためJSONへは
    # 残すが新ロジックでは読まない)。E_max = energy_capacity_base *
    # storage_capacity(gene) * matter を使う (docs/V1.9_iLUCA再設計仕様.md §4)。
    energy_capacity: float = 100.0   # deprecated (V1.9では未使用)
    energy_capacity_base: float = 100.0
    storage_upkeep_coef: float = 0.02   # storage_upkeep = coef*storage_capacity*matter
    radius_coef: float = 4.0         # 半径 = radius_coef * sqrt(s_eff)
    damage_capacity: float = 10.0    # D_max = damage_capacity * s_eff * (1+dr)
    phi_floor: float = 0.1           # 健全度の下限

    # --- V1.9: starvation homeostasis (docs/V1.9_iLUCA再設計仕様.md §5-6) ---
    # runway = energy / P_full (未来情報を一切参照しない現在状態量)。
    # state = clip(runway / starvation_horizon, 0, 1)。
    # metabolic_factor = floor + (1-floor)*state (BMR可変部/repair予算へ)
    # uptake_factor    = floor + (1-floor)*state (H2/light/nutrient uptakeへ)
    starvation_metabolic_floor: float = 0.10
    starvation_uptake_floor: float = 0.50

    # --- エネルギー消費 ---
    # V1.7: BMR = bmr_core + (bmr_coef - bmr_core) * M^0.75
    # bmr_core: 縮小不能な個体共通基礎維持代謝 [E/tick/個体]
    # bmr_core=0 -> V1.6 完全一致 / M=1 -> BMR=bmr_coef 常に維持
    # 0 <= bmr_core <= bmr_coef を検証する (違反は ValueError)
    # V1.7確定値 (docs/V1.7_総括.md): Exp11で候補を広く探索し、Exp12で
    # 50k tickの長期平衡を確認した結果、bmr_core=0.15 をV1.7恒久defaultとした。
    # 0.15は自然界の相転移点ではなく、事前登録した0.23 sentinelを最初に
    # 超えた試験格子点 (B1 8/8 seedで内部平衡)。V1.6完全回帰にはbmr_core=0を
    # 明示的に渡すこと。
    bmr_core: float = 0.15           # 縮小不能な基礎維持代謝 [E/tick] (V1.7)
    bmr_coef: float = 0.3            # 基礎代謝スケーリング係数 (M=1 時の BMR)
    organ_upkeep: float = 0.05       # 栄養獲得5能力の維持費係数
    sense_upkeep: float = 0.02      # 感覚維持 = k * sensory_range^2
    membrane_upkeep: float = 0.03    # 膜維持 = k * mem * sqrt(s)
    resist_upkeep: float = 0.02      # 耐性維持 = k * dr * s
    move_cost: float = 0.05          # 移動 = k * m * v^2 / eff
    attack_cost: float = 0.2         # 攻撃 = k * pred * s

    # --- 移動 ---
    speed_coef: float = 3.0          # v_max = k * power / sqrt(m) * phi
    wander_speed_frac: float = 0.6
    wander_turn_sigma: float = 0.5

    # --- 損傷・修復 ---
    metabolic_damage: float = 0.02   # D += k * s /tick
    movement_damage: float = 0.005   # D += k * m * v^2
    repair_spend: float = 0.2        # 修復支出上限 = k * repair * s * phi
    repair_eff: float = 0.5          # 損傷減少量/エネルギー

    # --- 捕食 ---
    attack_coef: float = 2.0
    defense_coef: float = 2.0
    bite_energy: float = 0.5         # E移転 = min(E_prey, k*net)
    bite_matter: float = 0.05        # M移転 = min(M_prey, k*net)
    assimilation: float = 0.7        # 同化効率 (残りは排泄→栄養へ)

    # --- 死骸 ---
    corpse_decay: float = 0.005      # M_c の毎tick分解率 → 栄養へ
    corpse_energy_decay: float = 0.01  # E_c の毎tick散逸率
    corpse_min_matter: float = 0.05
    corpse_eat_rate: float = 0.5     # 摂取 = k * digestion * s

    # --- 行動 ---
    # V1.5: 異種一次Energy刺激の無次元受容器応答 (docs/V1.5_異種刺激比較仕様.md)。
    #   response(x, K) = x / (x + K)   0 <= response < 1 / 単調増加
    # K は実行中のfield最大値やfluxから再計算せず、ここで固定する。
    # 環境を強くしたときに知覚まで割り戻すと環境変化の効果を打ち消すため。
    light_stimulus_half: float = 1.2       # 標準光場の最大セル光量が応答0.5
    # 標準13セルvent (chem_vent_flux=16) の生物不在平衡 stock。
    # 生物が占有したventの実測stockへ再校正はしない (V1.5仕様 §4)。
    chemical_stimulus_half: float = 12.3
    # 同点判定の許容差。広く取ると弱刺激域が一律tieになるため十分小さくする。
    # V1.6では一次Energyのwinner-take-all比較を廃止したため未使用だが、
    # V1.5 Configの読み書き互換のために残す。
    stimulus_tie_eps: float = 1e-9

    # V1.6: temporal biased random walk (docs/V1.6_行動則設計案.md)。
    # 一次Energyは「周囲の最良セルへ向かう」のをやめ、現在地の知覚Qの
    # 時間変化 dQ で既存random walkの曲がり幅だけを変える。
    #
    #   Q          = (aL*R_light + aC*R_chem) / (aL + aC)   能力加重平均
    #   dQ         = Q_now - Q_memory
    #   alpha      = 1 - exp(-1 / memory_tau)               EMA更新率
    #   turn_factor= 2 / (1 + exp(response_gain * dQ))      (0, 2)
    #   sigma_eff  = wander_turn_sigma * turn_factor
    #
    # memory_tau (短期記憶の時定数 [tick]) と
    # response_gain (dQ が曲がり幅へ効く強さ [無次元]) は
    # Exp10 Phase A 事前登録規則で選定・正式Phase Bで機能確認済みの
    # V1.6恒久default (docs/Exp10_結果考察.md / docs/バージョニング方針.md)。
    memory_tau: float = 10.0
    response_gain: float = 64.0

    sense_coef: float = 25.0         # 感覚半径 = k * sensory_range [wu]
    satiety_energy_frac: float = 0.85
    idle_prob: float = 0.0           # 刺激なし時に静止する確率 (残りはランダムウォーク)

    matter_cap_frac: float = 1.2     # 身体物質の貯蔵上限 = frac * body_size

    # --- 繁殖 ---
    # V1.9: repro_energy_frac はEnergy gateとして使わない (deprecated / 未使用)。
    # Energy gateは runway >= genome[reproduction_horizon] へ置き換える
    # (docs/V1.9_iLUCA再設計仕様.md §7)。Matter gateは既存 repro_matter_frac
    # を維持する。
    repro_energy_frac: float = 0.6   # deprecated (V1.9では未使用)
    repro_matter_frac: float = 0.8   # M >= frac*body_size
    child_matter_frac: float = 0.35  # 親Mのうち子へ渡す割合
    birth_overhead: float = 2.0      # 出産時燃焼エネルギー

    # --- 突然変異 ---
    meta_mutation_sigma: float = 0.1   # mutation_rate 自身の変異σ
    additive_mutation_frac: float = 0.01  # 加算項 = N(0, frac*σ*scale)
    initial_jitter_sigma: float = 0.02    # 初期個体群の standing variation
    # アブレーション実験用: ここに挙げた遺伝子は変異せず初期値のまま固定される。
    # 空 (既定) なら通常動作。例: ["body_size"]
    fixed_genes: list[str] = field(default_factory=list)

    # --- 初期個体群 ---
    initial_population: int = 100
    initial_energy: float = 50.0
    initial_matter: float = 0.8      # 初期身体物質 (body_size=1.0 に対し)

    # --- Exp06 診断ハーネス (docs/Exp06_実験計画.md §5) ---
    # 「パラメータが存在すること」と「進化的に到達可能なこと」を分離して
    # 診断するための初期条件注入。**既定値では通常実行と完全に同一**であり、
    # 世界ルール・default INITIAL_GENOME・default初期配置は一切変更しない。
    #
    # diagnostic_placement:
    #   "random" (既定) — 通常のランダム配置。乱数消費も通常どおり
    #   "vent"          — 初期個体を化学噴出口セル (chem_mask=True) 上へ配置
    # diagnostic_gene_overrides:
    #   初期個体のゲノムを生成した後で上書きする遺伝子。乱数を消費しない。
    #   例: {"chemical_absorption": 2.0}
    #   上書きした遺伝子は全世代で固定する必要があるため、同じ名前を
    #   fixed_genes にも入れること (入れ忘れは ValueError で弾く)。
    diagnostic_placement: str = "random"
    diagnostic_gene_overrides: dict[str, float] = field(default_factory=dict)
    # V1.9 mechanical sanity専用: 初期個体群のcapabilityを両方ONで生成する
    # (docs/V1.9_実装チェックリスト.md L節)。既定Falseでは通常のV1.9
    # baseline (両方OFF) と完全に同一。
    diagnostic_force_phototrophy: bool = False

    # --- V1.9: structural innovation (docs/V1.9_iLUCA再設計仕様.md §14) ---
    # continuous mutationとは分離した「能力そのものの起源」イベント。
    # fitness/environment/観測値を一切参照しない定数確率。
    phototrophy_innovation_prob: float = 1e-4   # per birth (OFF->ON)
    phototrophy_loss_prob: float = 1e-3         # per birth (ON->OFF)
    phototrophy_seed_absorption: float = 0.01   # innovation直後のlight_absorption下限

    # --- V1.9物理スケール検証パッチ (docs/V1.9_検証実装仕様_物理スケール版.md) ---
    # physical_mode=False (既定) では PR #67 の arbitrary-unit 機構を完全に
    # 維持する (既存test・既存挙動に一切影響しない)。physical_mode=True の
    # ときだけ、下記SI定数を使ってH2 uptake/basal power/growth energy/
    # movement powerを物理単位で計算する (evosim/physiology.py, world.py,
    # simulation.py)。
    physical_mode: bool = False
    # 1 step = dt_seconds [s]。物理量 (J/s, mol/s等) を1step分へ変換する
    # 共通倍率。既定1.0はarbitrary-unit modeの「1 tick」と完全互換。
    dt_seconds: float = 1.0

    # --- 質量基準 (docs §3) ---
    # 1 matter unit = reference dry mass (body_size=1.0のreference)。
    reference_dry_mass_kg: float = 2.8e-16   # 0.28 pgDW
    matter_unit_to_kgdw: float = 2.8e-16
    reference_cell_volume_m3: float = 1.0e-18  # 1 µm^3 (body_size=1.0)

    # --- H2 物理定数 (docs §5-7) ---
    h2_source_concentration_molm3: float = 1.0     # 1 mM Dirichlet boundary
    h2_diffusion_m2s: float = 5.0e-9
    h2_exchange_tau_s: float = 900.0
    h2_subcycle_alpha_max: float = 0.20
    # q_max=50 mmol H2/(gDW h) -> 50 mol/(kgDW h) -> /3600 -> mol/(kgDW s)
    h2_qmax_mol_per_kgdw_s: float = 50.0 / 3600.0
    # K_m = q_max / k_first_order = (50 mmol/gDW/h) / (19.36 L/gDW/h)
    #     = 2.5826 mmol/L = 2.5826 mol/m^3
    h2_km_mol_m3: float = 50.0 / 19.36
    # 4 H2 + 2 CO2 -> acetate; ATP/H2=0.075 mol/mol; ATP free energy 50 kJ/mol
    # -> usable Energy = 0.075 * 50000 = 3750 J/mol H2
    h2_usable_energy_j_per_mol: float = 3750.0

    # --- basal maintenance 物理定数 (docs §8) ---
    basal_atp_mmol_per_gdw_h: float = 0.116
    atp_energy_j_per_mol: float = 50_000.0
    # reference genomeで合計1.0になる正規化重み (docs §8)
    basal_weight_core: float = 0.60
    basal_weight_organ: float = 0.12
    basal_weight_sense: float = 0.08
    basal_weight_membrane: float = 0.10
    basal_weight_resistance: float = 0.05
    basal_weight_storage: float = 0.05
    # E_max_ref = reference basal power * storage_capacity_hours (docs §8)
    storage_capacity_hours: float = 12.0

    # --- growth / Matter assimilation 物理定数 (docs §9) ---
    # Y_ATP=10 gDW/mol ATP, ATP energy=50 kJ/mol -> 5.0e6 J/kgDW
    growth_energy_j_per_kgdw: float = 5.0e6
    # 0.20 matter unit/h * nutrient_absorption (nutrient-rich条件でのcap)
    nutrient_uptake_rate_matter_per_h: float = 0.20

    # --- movement 物理定数 (docs §10) ---
    water_viscosity_pa_s: float = 1.0e-3
    motor_efficiency: float = 0.10

    # --- 災害 ---
    disaster_kill_frac: float = 0.9

    # --- 記録 ---
    stats_interval: int = 20
    snapshot_interval: int = 2000

    # --- 安全装置 (改善方針 Ver.1.2 §9) ---
    # 個体数がこの値に達したら自動保存して停止する。個体を殺す処理ではない。0=無効
    max_population_halt: int = 20000

    def __post_init__(self) -> None:
        if not (0.0 <= self.bmr_core <= self.bmr_coef):
            raise ValueError(
                f"bmr_core={self.bmr_core} が範囲外です。"
                f"0 <= bmr_core <= bmr_coef={self.bmr_coef} でなければなりません。"
            )
        if self.light_uptake_half <= 0.0:
            raise ValueError(f"light_uptake_half={self.light_uptake_half} は正でなければなりません。")
        if self.chemical_uptake_half <= 0.0:
            raise ValueError(f"chemical_uptake_half={self.chemical_uptake_half} は正でなければなりません。")
        if self.light_cycle_period_ticks <= 0:
            raise ValueError(f"light_cycle_period_ticks={self.light_cycle_period_ticks} は正でなければなりません。")
        if not (0.0 < self.light_day_fraction < 1.0):
            raise ValueError(
                f"light_day_fraction={self.light_day_fraction} は0と1の間でなければなりません。"
            )
        # --- V1.9 validation (docs/V1.9_iLUCA再設計仕様.md §19) ---
        if self.energy_capacity_base <= 0.0:
            raise ValueError(f"energy_capacity_base={self.energy_capacity_base} は正でなければなりません。")
        if self.storage_upkeep_coef < 0.0:
            raise ValueError(f"storage_upkeep_coef={self.storage_upkeep_coef} は0以上でなければなりません。")
        if not (0.0 < self.starvation_metabolic_floor <= self.starvation_uptake_floor <= 1.0):
            raise ValueError(
                "0 < starvation_metabolic_floor <= starvation_uptake_floor <= 1 "
                f"でなければなりません: metabolic_floor={self.starvation_metabolic_floor}, "
                f"uptake_floor={self.starvation_uptake_floor}"
            )
        if not (0.0 <= self.h2_loss_frac < 1.0):
            raise ValueError(f"h2_loss_frac={self.h2_loss_frac} は 0 <= x < 1 でなければなりません。")
        if not (0.0 <= self.h2_diffusion <= 0.25):
            raise ValueError(f"h2_diffusion={self.h2_diffusion} は 0 <= x <= 0.25 でなければなりません。")
        if self.h2_vent_flux < 0.0:
            raise ValueError(f"h2_vent_flux={self.h2_vent_flux} は0以上でなければなりません。")
        if self.h2_uptake_coef < 0.0:
            raise ValueError(f"h2_uptake_coef={self.h2_uptake_coef} は0以上でなければなりません。")
        if self.h2_uptake_half <= 0.0:
            raise ValueError(f"h2_uptake_half={self.h2_uptake_half} は正でなければなりません。")
        if self.h2_energy_yield <= 0.0:
            raise ValueError(f"h2_energy_yield={self.h2_energy_yield} は正でなければなりません。")
        if not (0.0 <= self.h2_conversion_eff <= 1.0):
            raise ValueError(f"h2_conversion_eff={self.h2_conversion_eff} は 0 <= x <= 1 でなければなりません。")
        if not (0.0 <= self.phototrophy_innovation_prob <= 1.0):
            raise ValueError(
                f"phototrophy_innovation_prob={self.phototrophy_innovation_prob} は 0 <= x <= 1 でなければなりません。"
            )
        if not (0.0 <= self.phototrophy_loss_prob <= 1.0):
            raise ValueError(
                f"phototrophy_loss_prob={self.phototrophy_loss_prob} は 0 <= x <= 1 でなければなりません。"
            )
        if self.phototrophy_seed_absorption <= 0.0:
            raise ValueError(
                f"phototrophy_seed_absorption={self.phototrophy_seed_absorption} は正でなければなりません。"
            )
        # --- V1.9物理スケール検証パッチ validation ---
        if self.dt_seconds <= 0.0:
            raise ValueError(f"dt_seconds={self.dt_seconds} は正でなければなりません。")
        if self.physical_mode:
            if self.matter_unit_to_kgdw <= 0.0:
                raise ValueError("matter_unit_to_kgdw は正でなければなりません。")
            if self.reference_cell_volume_m3 <= 0.0:
                raise ValueError("reference_cell_volume_m3 は正でなければなりません。")
            if self.h2_source_concentration_molm3 < 0.0:
                raise ValueError("h2_source_concentration_molm3 は0以上でなければなりません。")
            if self.h2_diffusion_m2s <= 0.0:
                raise ValueError("h2_diffusion_m2s は正でなければなりません。")
            if self.h2_exchange_tau_s <= 0.0:
                raise ValueError("h2_exchange_tau_s は正でなければなりません。")
            if not (0.0 < self.h2_subcycle_alpha_max <= 1.0):
                raise ValueError("h2_subcycle_alpha_max は 0 < x <= 1 でなければなりません。")
            if self.h2_qmax_mol_per_kgdw_s <= 0.0 or self.h2_km_mol_m3 <= 0.0:
                raise ValueError("h2_qmax_mol_per_kgdw_s / h2_km_mol_m3 は正でなければなりません。")
            if self.h2_usable_energy_j_per_mol <= 0.0:
                raise ValueError("h2_usable_energy_j_per_mol は正でなければなりません。")
            weights = (self.basal_weight_core, self.basal_weight_organ,
                      self.basal_weight_sense, self.basal_weight_membrane,
                      self.basal_weight_resistance, self.basal_weight_storage)
            if any(w < 0.0 for w in weights):
                raise ValueError("basal_weight_* は0以上でなければなりません。")
            if abs(sum(weights) - 1.0) > 1e-6:
                raise ValueError(f"basal_weight_* の合計が1.0でありません: {sum(weights)}")
            if self.storage_capacity_hours <= 0.0:
                raise ValueError("storage_capacity_hours は正でなければなりません。")
            if self.growth_energy_j_per_kgdw <= 0.0:
                raise ValueError("growth_energy_j_per_kgdw は正でなければなりません。")
            if self.nutrient_uptake_rate_matter_per_h < 0.0:
                raise ValueError("nutrient_uptake_rate_matter_per_h は0以上でなければなりません。")
            if self.water_viscosity_pa_s <= 0.0 or self.motor_efficiency <= 0.0:
                raise ValueError("water_viscosity_pa_s / motor_efficiency は正でなければなりません。")
        if self.n_vents > 0:
            r = self.vent_radius_cells
            lo_x, hi_x = r, self.grid_w - r - 1
            lo_y, hi_y = r, self.grid_h - r - 1
            if lo_x > hi_x or lo_y > hi_y:
                raise ValueError(
                    f"vent_radius_cells={r} がworld ({self.grid_w}x{self.grid_h}) "
                    "に対して大きすぎ、edgeから内側へventを配置できません。"
                )

    def to_json(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(dataclasses.asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: str | Path) -> "Config":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    @property
    def grid_w(self) -> int:
        return int(self.world_width / self.cell_size)

    @property
    def grid_h(self) -> int:
        return int(self.world_height / self.cell_size)
