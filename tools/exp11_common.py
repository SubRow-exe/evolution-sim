"""Exp11 (docs/Exp11_実験計画案.md) 共通定数・ヘルパー。

`check_exp11.py` と `summarize_exp11.py` が候補値・seed数・環境判定・
snapshot読み込みをそれぞれ独立に定義すると、2026-09-01 の fixed_genes
事故 (Config生成・checker・testが同じ間違った定数を共有して全部通過した)
と同種の事故が再発しうる。ここへ一元化し、両者が同じ定義を参照する。
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

# --------------------------------------------------------------------------
# Exp11 候補 15 水準 (docs/Exp11_実験計画案.md §2)
# --------------------------------------------------------------------------
BMR_CORE_CANDIDATES: list[float] = [
    0.000, 0.005, 0.010, 0.015, 0.020,
    0.025, 0.030, 0.040, 0.050, 0.060,
    0.075, 0.100, 0.150, 0.200, 0.300,
]

# --------------------------------------------------------------------------
# Phase B 環境ごとの seed 数 (docs/Exp11_実験計画案.md §5-7)
# --------------------------------------------------------------------------
SEED_COUNTS: dict[str, int] = {"B1": 8, "B2": 5, "B3": 4}
SEEDS: dict[str, list[int]] = {env: list(range(1, n + 1)) for env, n in SEED_COUNTS.items()}
ENVIRONMENTS: tuple[str, ...] = ("B1", "B2", "B3")

# 15 候補 × (8+5+4) seed = 255 run
TOTAL_RUNS: int = len(BMR_CORE_CANDIDATES) * sum(SEED_COUNTS.values())
assert TOTAL_RUNS == 255, f"想定run数が255でない: {TOTAL_RUNS}"

# --------------------------------------------------------------------------
# body_size 分布のカットオフ (docs/Exp11_実験計画案.md §10)
# --------------------------------------------------------------------------
P_LOW_THRESHOLD = 0.21    # body_size <= P_LOW_THRESHOLD -> カウント
P_HIGH_THRESHOLD = 9.5    # body_size >= P_HIGH_THRESHOLD -> カウント

# late_drift ウィンドウ (docs/Exp11_実験計画案.md §10)
LATE_DRIFT_WINDOW_1 = (6000, 8000)
LATE_DRIFT_WINDOW_2 = (8000, 10000)

# --------------------------------------------------------------------------
# 環境判定 (Config の world 設定から B1/B2/B3 を推定する)
# --------------------------------------------------------------------------
# B1: light-only  (chem_vent_flux=0)
# B2: chem-only   (light_max=0)
# B3: mixed       (両方 > 0)
# tools/make_exp11_configs.py の B1_WORLD/B2_WORLD/B3_WORLD と対応する。


def infer_env(cfg: dict) -> str:
    """Config (dict) から環境 B1/B2/B3 を推定する。"""
    light_max = cfg.get("light_max", 1.2)
    chem_flux = cfg.get("chem_vent_flux", 0.0)
    if light_max <= 0:
        return "B2"
    if chem_flux <= 0:
        return "B1"
    return "B3"


def round_core(v: float) -> float:
    """浮動小数点誤差を吸収して候補15水準へ丸める。候補外ならそのまま返す。"""
    for c in BMR_CORE_CANDIDATES:
        if abs(v - c) < 1e-9:
            return c
    return v


# --------------------------------------------------------------------------
# ディレクトリ名から環境・bmr_core を抽出する
# (collect step が作る `<env_key>-bmr<core:.3f>` 形式。
#  例: "B1_lightonly_lightspec-bmr0.025")
# --------------------------------------------------------------------------
_COND_KEY_RE = re.compile(r"^(B[123])_[a-zA-Z0-9_]+-bmr([0-9]+\.[0-9]+)$")


def parse_condition_dir_name(name: str) -> tuple[str, float] | None:
    """条件ディレクトリ名から (env, bmr_core) を抽出する。一致しなければ None。"""
    m = _COND_KEY_RE.match(name)
    if not m:
        return None
    env = m.group(1)
    core = round_core(float(m.group(2)))
    return env, core


# --------------------------------------------------------------------------
# snapshot 読み込み (evosim/recorder.py Recorder.snapshot() が実際に書く形式)
#   snapshots/snap_{tick:08d}.csv
#   ヘッダ: id, parent_id, lineage_id, generation, age, x, y, energy,
#           matter, damage, <GENE_NAMES...>  (body_size は GENE_NAMES の先頭)
# --------------------------------------------------------------------------
SNAPSHOT_RE = re.compile(r"^snap_(\d+)\.csv$")


def snapshot_files(run_dir: Path) -> list[tuple[int, Path]]:
    """run_dir/snapshots 内の snap_NNNNNNNN.csv を (tick, path) のリストで返す (tick昇順)。

    ディレクトリが存在しない、または一致するファイルがなければ空リスト。
    """
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


def read_body_sizes(path: Path) -> list[float]:
    """1つの snapshot CSV から body_size 列を読み出す。

    body_size 列が存在しない、または値が不正なら ValueError。
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "body_size" not in reader.fieldnames:
            raise ValueError(f"{path}: body_size 列が見つからない "
                             f"(fieldnames={reader.fieldnames})")
        sizes: list[float] = []
        for row in reader:
            try:
                sizes.append(float(row["body_size"]))
            except (TypeError, ValueError) as e:
                raise ValueError(f"{path}: body_size 値が不正 ({row.get('body_size')!r}): {e}")
        return sizes
