"""遺伝子と突然変異。

Genome は numpy 配列 (float64, 14要素)。遺伝子は仕様書 Ver.1.1 §3 の14個。
突然変異は乗算的 (対数正規) + 微小加算項。適応度は一切参照しない。
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
]

N_GENES = len(GENE_NAMES)

# インデックス定数
(BODY_SIZE, MEMBRANE, MOVE_POWER, MOVE_EFF, SENSORY, LIGHT_ABS, CHEM_ABS,
 NUTRIENT_ABS, PREDATION, CORPSE_DIG, REPAIR, DAMAGE_RES, REPRO_INVEST,
 MUTATION_RATE) = range(N_GENES)

INITIAL_GENOME = np.array([
    1.0,   # body_size
    0.5,   # membrane_strength
    0.5,   # movement_power
    1.0,   # movement_efficiency
    0.4,   # sensory_range
    0.3,   # light_absorption
    0.3,   # chemical_absorption
    0.5,   # nutrient_absorption
    0.05,  # predation_efficiency
    0.2,   # corpse_digestion
    0.3,   # repair_rate
    0.5,   # damage_resistance
    0.4,   # reproduction_investment
    0.05,  # mutation_rate
])

GENE_MIN = np.array([
    0.2, 0.0, 0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.05, 0.005,
])
GENE_MAX = np.array([
    10.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 0.9, 0.5,
])

# 加算変異項の代表スケール (0に落ちた能力が再出現できる余地)
GENE_SCALE = np.array([
    1.0, 0.5, 0.5, 1.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.4, 0.05,
])


def initial_genome(rng: np.random.Generator, jitter_sigma: float,
                   fixed_mask: np.ndarray | None = None) -> np.ndarray:
    """共通祖先ゲノム + 微小な standing variation。

    fixed_mask の遺伝子は初期ばらつきも与えない。これにより固定遺伝子は
    全個体・全世代を通じて完全に一定となり、アブレーションが曖昧にならない。
    """
    g = INITIAL_GENOME * np.exp(rng.normal(0.0, jitter_sigma, N_GENES))
    if fixed_mask is not None:
        g = np.where(fixed_mask, INITIAL_GENOME, g)
    return np.clip(g, GENE_MIN, GENE_MAX)


def mutate(parent: np.ndarray, rng: np.random.Generator,
           meta_sigma: float, additive_frac: float,
           fixed_mask: np.ndarray | None = None) -> np.ndarray:
    """繁殖時の突然変異。σは親の mutation_rate 遺伝子。

    fixed_mask: True の遺伝子は親の値のまま据え置く (アブレーション実験用)。
    乱数は据え置く遺伝子の分も必ず消費するため、固定した遺伝子以外の変異系列は
    通常実行と一致する。これにより「その遺伝子だけが違う」比較が成立する。
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
