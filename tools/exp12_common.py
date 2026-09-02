"""Exp12 (docs/Exp12_実験計画確定.md) 共通定数・ヘルパー。

check_exp12.py / summarize_exp12.py / make_exp12_configs.py が同じ値を
別々に定義すると、Exp11 fixed_genes事故と同種の事故が再発する。
候補値・seed数・環境判定・snapshot読込はここに集約する。
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

# --------------------------------------------------------------------------
# 正式条件 (docs/Exp12_実験計画確定.md §3, §18)
# --------------------------------------------------------------------------
B1_BMR_CORE: list[float] = [0.000, 0.050, 0.075, 0.100, 0.150, 0.200, 0.300]
B2_BMR_CORE: list[float] = [0.000, 0.100, 0.300]

B1_SEEDS: list[int] = list(range(1, 9))   # 1-8
B2_SEEDS: list[int] = list(range(1, 6))   # 1-5

B1_JOBS = len(B1_BMR_CORE) * len(B1_SEEDS)   # 56
B2_JOBS = len(B2_BMR_CORE) * len(B2_SEEDS)   # 15
TOTAL_RUNS = B1_JOBS + B2_JOBS                # 71
assert B1_JOBS == 56 and B2_JOBS == 15 and TOTAL_RUNS == 71

TICKS = 50000
FIRST_10K = 10000

COMMON_CONFIG = dict(
    initial_population=100,
    initial_energy=50.0,
    initial_matter=0.8,
    memory_tau=10.0,
    response_gain=64.0,
    stats_interval=20,
    snapshot_interval=1000,
    max_population_halt=10000,
)

# body_size 分布のカットオフ (docs/Exp12_実験計画確定.md §7.1)
P_LOW_THRESHOLDS: dict[str, float] = {"p_021": 0.21, "p_023": 0.23, "p_025": 0.25}
P_HIGH_THRESHOLD = 9.5
LOWER_BOUND_SENTINEL = 0.23   # §13.2 / §14.1

# tick-space late windows (§8)
TICK_WINDOWS: dict[str, tuple[int, int]] = {
    "W1": (20000, 30000),
    "W2": (30000, 40000),
    "W3": (40000, 50000),
}

STATIONARITY_SENTINEL = 0.05     # |S3|<=0.05, |S_gen|<=0.05
DECEL_RATIO = 0.8                # |S2|<=0.8|S1| and |S3|<=0.8|S2|
SUSTAINED_S_THRESHOLD = 0.05     # S1,S2,S3 < -0.05
SUSTAINED_RATIO = 0.70           # |S3| >= 0.70*|S1|

GENERATION_LATE_FRACTION = 0.30  # late generation window = 最後30%
GENERATION_WINDOW_MIN = 10       # generations

# asymptotic fit (§10)
FIT_B_INF_MIN = 0.2
FIT_B_INF_MAX = 10.0
FIT_TAU_MAX = 13_333.0           # 40k fit windowの1/3超で不安定とみなす
FIT_NRMSE_MAX = 0.25

# Matter coupling (§12)
MATTER_COUPLING_WINDOW = (30000, 50000)
MATTER_COUPLING_RHO_MIN = 0.60
MATTER_COUPLING_P_MAX = 0.05
MATTER_COUPLING_SEED_MIN_FRAC = 4  # B1 8 seed中4以上

# 条件単位判定 (§14)
B1_BASELINE_SEED_MIN = 5   # 8 seed中5以上
B1_INTERIOR_SEED_MIN = 6   # 8 seed中6以上
B1_DELAY_SEED_MIN = 6      # 8 seed中6以上
B1_DELAY_MAX_FOR_INTERIOR = 1  # INTERIOR判定時にDELAY_CONTINUESは1 seed以下

# B2 method control (§15)
B2_STATIONARY_SEED_MIN = 4  # 5 seed中4以上


def infer_env(cfg: dict) -> str:
    """Config (dict) から環境 B1/B2 を推定する。"""
    light_max = cfg.get("light_max", 1.2)
    chem_flux = cfg.get("chem_vent_flux", 0.0)
    if light_max <= 0:
        return "B2"
    if chem_flux <= 0:
        return "B1"
    raise ValueError(f"Exp12はB1/B2のみ想定。light_max={light_max} chem_flux={chem_flux}")


def round_bmr(v: float, candidates: list[float]) -> float:
    for c in candidates:
        if abs(v - c) < 1e-9:
            return c
    return v


def round_bmr_any(v: float) -> float:
    return round_bmr(v, B1_BMR_CORE + [c for c in B2_BMR_CORE if c not in B1_BMR_CORE])


# --------------------------------------------------------------------------
# ディレクトリ名 <-> (env, bmr_core) (collect step の `<env_key>-bmr<core:.3f>` 形式)
# --------------------------------------------------------------------------
_COND_KEY_RE = re.compile(r"^(B[12])_[a-zA-Z0-9_]+-bmr([0-9]+\.[0-9]+)$")


def parse_condition_dir_name(name: str) -> tuple[str, float] | None:
    m = _COND_KEY_RE.match(name)
    if not m:
        return None
    return m.group(1), round_bmr_any(float(m.group(2)))


# --------------------------------------------------------------------------
# snapshot 読み込み (evosim/recorder.py Recorder.snapshot() の実際の出力形式)
#   snapshots/snap_{tick:08d}.csv
#   ヘッダ: id, parent_id, lineage_id, generation, age, x, y, energy,
#           matter, damage, <GENE_NAMES...>
# --------------------------------------------------------------------------
SNAPSHOT_RE = re.compile(r"^snap_(\d+)\.csv$")


def snapshot_files(run_dir: Path) -> list[tuple[int, Path]]:
    """run_dir/snapshots 内の snap_NNNNNNNN.csv を (tick, path) のリストで返す (tick昇順)。"""
    snap_dir = run_dir / "snapshots"
    if not snap_dir.exists():
        return []
    out: list[tuple[int, Path]] = []
    for p in snap_dir.iterdir():
        m = SNAPSHOT_RE.match(p.name)
        if m:
            out.append((int(m.group(1)), p))
    out.sort(key=lambda t: t[0])
    return out


def read_snapshot_columns(path: Path, columns: list[str]) -> dict[str, list[float]]:
    """1つの snapshot CSV から指定列を読み出す。列が無ければ ValueError。"""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing = [c for c in columns if c not in fieldnames]
        if missing:
            raise ValueError(f"{path}: 列が見つからない: {missing} (fieldnames={fieldnames})")
        out: dict[str, list[float]] = {c: [] for c in columns}
        for row in reader:
            for c in columns:
                try:
                    out[c].append(float(row[c]))
                except (TypeError, ValueError) as e:
                    raise ValueError(f"{path}: 列 {c} の値が不正 ({row.get(c)!r}): {e}")
        return out


def read_body_sizes(path: Path) -> list[float]:
    return read_snapshot_columns(path, ["body_size"])["body_size"]
