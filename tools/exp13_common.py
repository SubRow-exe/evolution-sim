"""Exp13 共有定数・ヘルパー (docs/Exp13_実験計画確定.md)。

Exp12の`tools/exp12_common.py`と同じ役割: generator/checker/summarizerが
同じ手書き定数を独自に持たないよう、ここへ一元化する。

正本:
  docs/V1.8_Exp13_レビュー判断.md
  docs/V1.8_一次Energy生態非対称仕様.md
  docs/Exp13_実験計画確定.md
  docs/V1.8_実装チェックリスト.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 共通Exp13条件 (§2)
# ---------------------------------------------------------------------------
BMR_CORE = 0.15
MEMORY_TAU = 10.0
RESPONSE_GAIN = 64.0
LIGHT_CYCLE_PERIOD_TICKS = 200
LIGHT_DAY_FRACTION = 0.5
LIGHT_UPTAKE_HALF = 0.6

STATS_INTERVAL = 20
SNAPSHOT_INTERVAL = 1000
MAX_POPULATION_HALT = 10000

COMMON_CONFIG = dict(
    bmr_core=BMR_CORE,
    memory_tau=MEMORY_TAU,
    response_gain=RESPONSE_GAIN,
    light_cycle_period_ticks=LIGHT_CYCLE_PERIOD_TICKS,
    light_day_fraction=LIGHT_DAY_FRACTION,
    light_uptake_half=LIGHT_UPTAKE_HALF,
    primary_energy_density_response=True,
    stats_interval=STATS_INTERVAL,
    snapshot_interval=SNAPSHOT_INTERVAL,
    max_population_halt=MAX_POPULATION_HALT,
)

# ---------------------------------------------------------------------------
# Phase A1: light map (§5)
# ---------------------------------------------------------------------------
A1_LIGHT_MAX = [0.8, 1.2, 1.5, 1.8, 2.1, 2.4, 3.0, 4.0]
A1_SEEDS = list(range(1, 6))     # 1..5
A1_TICKS = 10_000
A1_JOBS = len(A1_LIGHT_MAX) * len(A1_SEEDS)  # 40

# robust viability (§5.2)
A1_MIN_COMPLETE_FRAC = 4  # /5
A1_MAX_EXTINCT = 1        # /5
A1_MIN_LATE_BIRTH_SEEDS = 4   # /5
A1_MIN_LATE_POP_SEEDS = 4     # /5
A1_LATE_POP_FLOOR = 25.0      # = initial_population(100) の25%
A1_LATE_BIRTH_WINDOW = 2_000  # 最終2,000 tick

# ---------------------------------------------------------------------------
# Phase A2: chemical grid (§6)
# ---------------------------------------------------------------------------
A2_CHEMICAL_UPTAKE_HALF = [0.5, 1.5, 3.0, 6.15]
A2_CHEM_UPTAKE = [0.5, 1.0, 2.0, 4.0]
A2_SEEDS = list(range(1, 4))     # 1..3
A2_TICKS = 5_000
A2_JOBS = len(A2_CHEMICAL_UPTAKE_HALF) * len(A2_CHEM_UPTAKE) * len(A2_SEEDS)  # 48

A2_MIN_COMPLETE_SEEDS = 2   # /3
A2_MIN_LATE_BIRTH_SEEDS = 2  # /3
A2_LATE_BIRTH_WINDOW = 1_000
A2_H_MEDIAN_LOW = 0.10
A2_H_MEDIAN_HIGH = 0.90
A2_DEPLETION_FRAC = 0.7    # min median vent stock <= 0.7 * biological-free C_eq
A2_DEPLETION_MIN_SEEDS = 2  # /3

# ---------------------------------------------------------------------------
# Phase A2b: selected chemical pairの検証 (§7)
# ---------------------------------------------------------------------------
A2B_SEEDS = list(range(1, 6))    # 1..5
A2B_TICKS = 10_000
A2B_PLACEMENTS = ["vent", "random"]
A2B_JOBS = len(A2B_SEEDS) * len(A2B_PLACEMENTS)  # 10

A2B_VENT_MIN_COMPLETE_SEEDS = 4  # /5
A2B_VENT_MIN_LATE_BIRTH_SEEDS = 4  # /5
A2B_VENT_LATE_BIRTH_WINDOW = 2_000

# ---------------------------------------------------------------------------
# Phase A3: density competition (§8)
# ---------------------------------------------------------------------------
A3_POPULATIONS = [1, 10, 50]
A3_SEEDS = list(range(1, 4))     # 1..3
A3_TICKS = 2_000
A3_JOBS = len(A3_POPULATIONS) * len(A3_SEEDS)  # 9

PHASE_A_TOTAL = A1_JOBS + A2_JOBS + A2B_JOBS + A3_JOBS  # 107
assert PHASE_A_TOTAL == 107, f"Phase A total が107でない: {PHASE_A_TOTAL}"

# ---------------------------------------------------------------------------
# Phase B (§11-14)
# ---------------------------------------------------------------------------
B1_SEEDS = list(range(1, 9))     # 1..8
B1_TICKS = 20_000
B1_JOBS = len(B1_SEEDS)  # 8

B2_SEEDS = list(range(1, 9))     # 1..8
B2_TICKS = 20_000
B2_JOBS = len(B2_SEEDS)  # 8

B3_SEEDS = list(range(1, 13))    # 1..12
B3_TICKS = 30_000
B3_JOBS = len(B3_SEEDS)  # 12

B4A_SEEDS = list(range(1, 4))    # 1..3
B4A_TICKS = 5_000
B4A_JOBS = len(B4A_SEEDS)  # 3
B4A_BODY_SIZE = 0.246  # Exp12平衡付近 (docs/Exp12_結果考察.md)

B4B_SEEDS = list(range(1, 6))    # 1..5
B4B_TICKS = 20_000
B4B_JOBS = len(B4B_SEEDS)  # 5

PHASE_B_TOTAL = B1_JOBS + B2_JOBS + B3_JOBS + B4A_JOBS + B4B_JOBS  # 36
assert PHASE_B_TOTAL == 36, f"Phase B total が36でない: {PHASE_B_TOTAL}"

TOTAL_RUNS = PHASE_A_TOTAL + PHASE_B_TOTAL  # 143
assert TOTAL_RUNS == 143, f"Exp13 formal run総数が143でない: {TOTAL_RUNS}"


def b4a_derived_initial_energy(initial_energy_std: float, initial_matter_std: float,
                                energy_capacity: float, body_size: float) -> float:
    """B4a: 標準初期個体と同じEnergy-capacity fractionになるinitial_energyを導出する。

    標準個体: E_max_std = energy_capacity * initial_matter_std
              fraction  = initial_energy_std / E_max_std
    B4a個体:  matter = initial_matter_std * body_size (target_sizeに比例)
              E_max  = energy_capacity * matter
              initial_energy = fraction * E_max

    ハードコード魔法値を避けるため、Config標準値から計算する
    (docs/V1.8_実装チェックリスト.md §14)。
    """
    e_max_std = energy_capacity * initial_matter_std
    fraction = initial_energy_std / e_max_std
    matter = initial_matter_std * body_size
    e_max = energy_capacity * matter
    return fraction * e_max


# ---------------------------------------------------------------------------
# selected value artifact
# ---------------------------------------------------------------------------
SELECTED_FILE_NAME = "exp13_selected.json"


@dataclass(frozen=True)
class SelectedValues:
    light_max: float
    chemical_uptake_half: float
    chem_uptake: float
    source_sha: str
    evidence: str

    def to_dict(self) -> dict:
        return {
            "light_max": self.light_max,
            "chemical_uptake_half": self.chemical_uptake_half,
            "chem_uptake": self.chem_uptake,
            "source_sha": self.source_sha,
            "evidence": self.evidence,
        }


# ---------------------------------------------------------------------------
# run directory naming / parsing
# ---------------------------------------------------------------------------
SNAPSHOT_RE = re.compile(r"^snap_(\d+)\.csv$")


def snapshot_files(run_dir: Path) -> list[tuple[int, Path]]:
    snap_dir = run_dir / "snapshots"
    if not snap_dir.is_dir():
        return []
    out = []
    for p in snap_dir.iterdir():
        m = SNAPSHOT_RE.match(p.name)
        if m:
            out.append((int(m.group(1)), p))
    return sorted(out)


def round_bmr_any(v: float) -> float:
    return round(float(v), 3)
