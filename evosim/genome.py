"""遺伝子・突然変異・structural innovation (V1.9 iLUCA再設計仕様)。

Genome は numpy 配列 (float64, 17要素)。continuous genesは既存14 +
storage_capacity / starvation_horizon / reproduction_horizon の3つ。
突然変異は乗算的 (対数正規) + 微小加算項。適応度は一切参照しない。

V1.9では continuous mutation と structural innovation を分離する
(docs/V1.9_iLUCA再設計仕様.md §14)。phototrophy/predationは
「値が0」と「能力そのものが存在しない」を区別するcapability bitで持ち、
capability=OFFのgeneは通常のcontinuous mutationでは迂回できない。
"""
from __future__ import annotations

import numpy as np

GENE_NAMES: list[str] = [
    "body_size",
    "membrane_strength",
    "movement_power",
    "movement_efficiency",
    "sensory_range",
    "light_absorption",
    "chemical_absorption",
    "nutrient_absorption",
    "predation_efficiency",
    "corpse_digestion",
    "repair_rate",
    "damage_resistance",
    "reproduction_investment",
    "mutation_rate",
    "storage_capacity",
    "starvation_horizon",
    "reproduction_horizon",
]

N_GENES = len(GENE_NAMES)

# インデックス定数
(BODY_SIZE, MEMBRANE, MOVE_POWER, MOVE_EFF, SENSORY, LIGHT_ABS, CHEM_ABS,
 NUTRIENT_ABS, PREDATION, CORPSE_DIG, REPAIR, DAMAGE_RES, REPRO_INVEST,
 MUTATION_RATE, STORAGE_CAP, STARV_HORIZON, REPRO_HORIZON) = range(N_GENES)

# V1.9 initial iLUCA (docs/V1.9_iLUCA再設計仕様.md §2)。
# light_absorption/predation_efficiencyは0 (capability OFFなので機能もしない)。
# chemical_absorption=1.0 (H2 substrateをbaseline capabilityとして持つ)。
INITIAL_GENOME = np.array([
    1.0,    # body_size
    0.5,    # membrane_strength
    0.5,    # movement_power
    1.0,    # movement_efficiency
    0.4,    # sensory_range
    0.0,    # light_absorption (PHOTOTROPHY OFF)
    1.0,    # chemical_absorption (H2 baseline)
    0.5,    # nutrient_absorption
    0.0,    # predation_efficiency (PREDATION OFF)
    0.2,    # corpse_digestion
    0.3,    # repair_rate
    0.5,    # damage_resistance
    0.4,    # reproduction_investment
    0.05,   # mutation_rate
    1.0,     # storage_capacity
    1800.0,  # starvation_horizon [s] (docs/V1.9_検証実装仕様_物理スケール版.md §2)
    3600.0,  # reproduction_horizon [s]
])

GENE_MIN = np.array([
    0.2, 0.0, 0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.05, 0.005,
    0.20, 60.0, 300.0,
])
GENE_MAX = np.array([
    10.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 0.9, 0.5,
    5.00, 86400.0, 43200.0,
])

# 加算変異項の代表スケール (0に落ちた能力が再出現できる余地)
GENE_SCALE = np.array([
    1.0, 0.5, 0.5, 1.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.4, 0.05,
    0.5, 600.0, 1200.0,
])

# --- capability state (V1.9 §3) --------------------------------------------
# continuous geneの「値が0」と「能力そのものが存在しない」を区別する。
CAPABILITY_NAMES = ("phototrophy", "predation")


def initial_capability() -> dict[str, bool]:
    """初期iLUCAのcapability。両方OFF (V1.9 §2)。"""
    return {"phototrophy": False, "predation": False}


def enforce_capability_gates(genome: np.ndarray, capability: dict[str, bool]) -> np.ndarray:
    """capability OFFのgeneを強制的に0へ正規化する (HARD RULE §3)。

    continuous mutationの加算項だけでgateを迂回できないようにする、
    実際の強制ポイント。呼び出し側 (structural_mutate/初期生成) が
    毎回これを通すことで不変条件を保証する。
    """
    g = genome.copy()
    if not capability["phototrophy"]:
        g[LIGHT_ABS] = 0.0
    if not capability["predation"]:
        g[PREDATION] = 0.0
    return g


def structural_mutate(parent_capability: dict[str, bool], child_genome: np.ndarray,
                      rng: np.random.Generator, cfg) -> tuple[dict[str, bool], np.ndarray]:
    """出生時のstructural innovation/loss判定 (V1.9 §14)。

    - fitness/environment/観測値を一切参照しない。
    - RNGは phototrophy 用に1回、predation 用に1回、capability状態に
      関わらず必ず消費する (同seed determinism §14.3)。
    - predationはV1.9ではlocked: innovationは常に無効。
    """
    child_capability = dict(parent_capability)

    r_photo = rng.random()
    if parent_capability["phototrophy"]:
        if r_photo < cfg.phototrophy_loss_prob:
            child_capability["phototrophy"] = False
    else:
        if r_photo < cfg.phototrophy_innovation_prob:
            child_capability["phototrophy"] = True

    # predation innovationはV1.9ではdisabled。RNG消費だけ他capabilityと
    # 対称に行い、出生ごとの乱数消費数をcapability状態に依らず固定する。
    _r_predation = rng.random()
    child_capability["predation"] = False

    genome = child_genome.copy()
    if child_capability["phototrophy"] and not parent_capability["phototrophy"]:
        # このtickでOFF->ONになった個体はseed absorptionを持つ
        genome[LIGHT_ABS] = max(genome[LIGHT_ABS], cfg.phototrophy_seed_absorption)
    genome = enforce_capability_gates(genome, child_capability)
    return child_capability, genome


def initial_genome(rng: np.random.Generator, jitter_sigma: float,
                   fixed_mask: np.ndarray | None = None,
                   capability: dict[str, bool] | None = None) -> np.ndarray:
    """共通祖先ゲノム + 微小な standing variation。

    fixed_mask の遺伝子は初期ばらつきも与えない。これにより固定遺伝子は
    全個体・全世代を通じて完全に一定となり、アブレーションが曖昧にならない。
    capabilityを渡した場合はOFFのgeneを強制的に0へ正規化する。
    """
    g = INITIAL_GENOME * np.exp(rng.normal(0.0, jitter_sigma, N_GENES))
    if fixed_mask is not None:
        g = np.where(fixed_mask, INITIAL_GENOME, g)
    g = np.clip(g, GENE_MIN, GENE_MAX)
    if capability is not None:
        g = enforce_capability_gates(g, capability)
    return g


def mutate(parent: np.ndarray, rng: np.random.Generator,
           meta_sigma: float, additive_frac: float,
           fixed_mask: np.ndarray | None = None) -> np.ndarray:
    """繁殖時のcontinuous突然変異。σは親の mutation_rate 遺伝子。

    fixed_mask: True の遺伝子は親の値のまま据え置く (アブレーション実験用)。
    乱数は据え置く遺伝子の分も必ず消費するため、固定した遺伝子以外の変異系列は
    通常実行と一致する。これにより「その遺伝子だけが違う」比較が成立する。

    capability gateの強制はここでは行わない (呼び出し側がstructural_mutate
    経由で行う)。
    """
    sigma = parent[MUTATION_RATE]
    child = parent * np.exp(rng.normal(0.0, sigma, N_GENES))
    child += rng.normal(0.0, additive_frac * sigma * GENE_SCALE)
    # mutation_rate はメタσで別途変異 (上の変異を上書き)
    child[MUTATION_RATE] = parent[MUTATION_RATE] * np.exp(rng.normal(0.0, meta_sigma))
    if fixed_mask is not None:
        child = np.where(fixed_mask, parent, child)
    return np.clip(child, GENE_MIN, GENE_MAX)


def diagnostic_overrides(cfg) -> list[tuple[int, float]] | None:
    """Exp06診断用の初期ゲノム上書き指定を (添字, 値) の一覧へ変換する。

    docs/Exp06_実験計画.md §5。上書きした遺伝子は「以後の世代でも固定」する
    必要があるため、fixed_genes に入っていなければここで弾く。入れ忘れると
    positive control が世代とともに崩れ、診断が成立しなくなるため。

    上書き自体は乱数を消費しない。指定が空なら None を返し、呼び出し側は
    通常実行と同じ経路を通る。
    """
    spec = getattr(cfg, "diagnostic_gene_overrides", None)
    if not spec:
        return None
    fixed = set(getattr(cfg, "fixed_genes", []) or [])
    out: list[tuple[int, float]] = []
    for name, value in spec.items():
        if name not in GENE_NAMES:
            raise ValueError(
                f"未知の遺伝子名: {name} (候補: {', '.join(GENE_NAMES)})")
        idx = GENE_NAMES.index(name)
        v = float(value)
        if not GENE_MIN[idx] <= v <= GENE_MAX[idx]:
            raise ValueError(
                f"{name} の上書き値 {v} が範囲外 "
                f"[{GENE_MIN[idx]}, {GENE_MAX[idx]}]")
        if name not in fixed:
            raise ValueError(
                f"diagnostic_gene_overrides の {name} は fixed_genes にも "
                "指定すること (上書きした遺伝子は全世代で固定する)")
        out.append((idx, v))
    return out


def fixed_mask_from_names(names: list[str]) -> np.ndarray | None:
    """遺伝子名のリストから固定マスクを作る。未知の名前はエラーにする。"""
    if not names:
        return None
    mask = np.zeros(N_GENES, dtype=bool)
    for n in names:
        if n not in GENE_NAMES:
            raise ValueError(f"未知の遺伝子名: {n} (候補: {', '.join(GENE_NAMES)})")
        mask[GENE_NAMES.index(n)] = True
    return mask
