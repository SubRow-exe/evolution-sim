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

    # --- V1.2: high_contrast_vertical の形状 ---
    # 北から「明部plateau → 線形遷移 → 暗部」の3帯を作る。
    # shape を作った後、同じConfigの vertical が持つ総光量へ正規化するため、
    # 形状 (空間偏在) と総光量を独立に振れる。Exp05 では total_scale=1.0 固定。
    light_hc_bright_frac: float = 0.20       # 明部plateauが占める縦方向の割合
    light_hc_transition_frac: float = 0.50   # 線形遷移帯が占める割合
    light_hc_dark_floor: float = 0.0         # 暗部の相対光量 (0 = 完全暗部)
    light_hc_total_scale: float = 1.0        # Control総光量に対する倍率

    # --- 化学エネルギー (ストック型) ---
    n_vents: int = 4
    vent_radius_cells: int = 2
    chem_capacity: float = 50.0      # K_chem [E/セル]
    chem_regen: float = 0.05         # ロジスティック回復率
    chem_min_stock: float = 0.5      # 0からの回復を可能にする下限
    chem_uptake: float = 0.5         # 吸収レート係数

    # --- 無機栄養 (物質・厳密保存・再生なし) ---
    nutrient_initial: float = 2.0    # 初期ストック [M/セル]
    nutrient_diffusion: float = 0.05  # 拡散係数
    nutrient_uptake: float = 0.05    # 吸収レート係数
    matter_absorb_cost: float = 2.0  # 物質1単位の同化エネルギーコスト

    # --- 個体スケール ---
    energy_capacity: float = 100.0   # E_max = energy_capacity * s_eff
    radius_coef: float = 4.0         # 半径 = radius_coef * sqrt(s_eff)
    damage_capacity: float = 10.0    # D_max = damage_capacity * s_eff * (1+dr)
    phi_floor: float = 0.1           # 健全度の下限

    # --- エネルギー消費 ---
    bmr_coef: float = 0.3            # 基礎代謝 = bmr * s^0.75
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
    sense_coef: float = 25.0         # 感覚半径 = k * sensory_range [wu]
    satiety_energy_frac: float = 0.85
    idle_prob: float = 0.0           # 刺激なし時に静止する確率 (残りはランダムウォーク)

    matter_cap_frac: float = 1.2     # 身体物質の貯蔵上限 = frac * body_size

    # --- 繁殖 ---
    repro_energy_frac: float = 0.6   # E >= frac*E_max
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

    # --- 災害 ---
    disaster_kill_frac: float = 0.9

    # --- 記録 ---
    stats_interval: int = 20
    snapshot_interval: int = 2000

    # --- 安全装置 (改善方針 Ver.1.2 §9) ---
    # 個体数がこの値に達したら自動保存して停止する。個体を殺す処理ではない。0=無効
    max_population_halt: int = 20000

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
