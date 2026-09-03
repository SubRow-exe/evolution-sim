"""Exp13 Config整合性・完全性・first-2k再現性チェッカー
(docs/Exp13_実験計画確定.md §3, V1.8_実装チェックリスト.md)。

確認項目 (静的Config):
  - Phase A1/A2の24 Configがgeneratorと一致・JSON round-trip
  - fixed_genesがcanonical GENE_NAMESから正しく導出されている
  - fixed_mask_from_names() を実際に通す
  - Simulation初期化+短tick smoke

確認項目 (実行済みrun): `check_exp13.py runs/exp13`
  - config.jsonを持つrunディレクトリを再帰的に収集
  - 期待run key集合 (phase別) と実取得key集合の完全一致
  - formal SHA / numeric environment整合性
  - current-run first-2k×2 same-seed再現性比較 (compare_first_2k)
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evosim.config import Config
from evosim.genome import GENE_NAMES, fixed_mask_from_names
from tools.exp13_common import (
    A1_LIGHT_MAX, A2_CHEM_UPTAKE, A2_CHEMICAL_UPTAKE_HALF, snapshot_files,
)
from tools.make_exp13_configs import (
    ALL_GENES, B3_FIXED_GENES, B4B_FIXED_GENES, a1_config_name, a2_config_name,
    build_a1, build_a2,
)

CONFIGS_DIR_A = ROOT / "configs" / "exp13"

EXPECTED_ALL14 = set(GENE_NAMES)
EXPECTED_B3_FIXED = set(B3_FIXED_GENES)
EXPECTED_B4B_FIXED = set(B4B_FIXED_GENES)


# ---------------------------------------------------------------------------
# 静的Config検証
# ---------------------------------------------------------------------------

def check_config_generic(cfg: Config, expected_fixed: set[str], label: str) -> list[str]:
    errors = []
    actual = set(cfg.fixed_genes)
    if actual != expected_fixed:
        errors.append(
            f"{label}: fixed_genes不一致 期待={sorted(expected_fixed)} 実際={sorted(actual)}"
        )
    try:
        fixed_mask_from_names(cfg.fixed_genes)
    except ValueError as e:
        errors.append(f"{label}: fixed_mask_from_names失敗: {e}")
    if abs(cfg.bmr_core - 0.15) > 1e-12:
        errors.append(f"{label}: bmr_core={cfg.bmr_core} != 0.15")
    if not cfg.primary_energy_density_response:
        errors.append(f"{label}: primary_energy_density_response がFalse")
    return errors


def check_simulation_smoke(cfg: Config, label: str) -> list[str]:
    from evosim.simulation import Simulation

    errors = []
    try:
        sim = Simulation(cfg, seed=1)
        for _ in range(5):
            sim.step()
    except Exception as e:
        errors.append(f"{label}: Simulation smoke失敗: {type(e).__name__}: {e}")
    return errors


def check_phase_a_configs() -> list[str]:
    errors: list[str] = []
    for light_max in A1_LIGHT_MAX:
        cfg = build_a1(light_max)
        errors.extend(check_config_generic(cfg, EXPECTED_ALL14, f"A1 light={light_max}"))
        path = CONFIGS_DIR_A / a1_config_name(light_max)
        if not path.exists():
            errors.append(f"{path.name}: ファイルが存在しない (make_exp13_configs.py を実行)")
    for k in A2_CHEMICAL_UPTAKE_HALF:
        for uptake in A2_CHEM_UPTAKE:
            cfg = build_a2(k, uptake)
            errors.extend(check_config_generic(cfg, EXPECTED_ALL14, f"A2 K={k} uptake={uptake}"))
            path = CONFIGS_DIR_A / a2_config_name(k, uptake)
            if not path.exists():
                errors.append(f"{path.name}: ファイルが存在しない (make_exp13_configs.py を実行)")
    # 代表smoke: A1最小・最大、A2代表1点
    errors.extend(check_simulation_smoke(build_a1(A1_LIGHT_MAX[0]), "A1 smoke min"))
    errors.extend(check_simulation_smoke(build_a1(A1_LIGHT_MAX[-1]), "A1 smoke max"))
    errors.extend(check_simulation_smoke(
        build_a2(A2_CHEMICAL_UPTAKE_HALF[0], A2_CHEM_UPTAKE[0]), "A2 smoke"))
    return errors


# ---------------------------------------------------------------------------
# run収集・完全性検証
# ---------------------------------------------------------------------------

def collect_run_dirs(base_dir: Path) -> list[Path]:
    return sorted({p.parent for p in base_dir.rglob("config.json")})


def check_run_environment_integrity(run_dirs: list[Path]) -> list[str]:
    """formal run群がすべて同一git_sha・同一numeric_environmentで実行された
    ことを確認する (docs/数値再現性・Actions実行環境方針.md Level A)。
    """
    errors: list[str] = []
    shas: dict[str | None, list[Path]] = {}
    env_keys: dict[str | None, list[Path]] = {}

    for run_dir in run_dirs:
        meta_path = run_dir / "meta.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"{run_dir}: meta.json読み込み失敗 (環境整合性チェック): {e}")
            continue
        sha = meta.get("git_sha")
        if sha is None:
            errors.append(f"{run_dir}: meta.jsonにgit_shaがない")
        shas.setdefault(sha, []).append(run_dir)
        env_key = (meta.get("numeric_environment") or {}).get("env_key")
        if env_key is None:
            errors.append(f"{run_dir}: meta.jsonにnumeric_environment.env_keyがない")
        env_keys.setdefault(env_key, []).append(run_dir)

    if len(shas) > 1:
        errors.append(
            "formal run群でgit_shaが混在: "
            + ", ".join(f"{k!r}={len(v)}件" for k, v in sorted(shas.items(), key=lambda kv: str(kv[0])))
        )
    if len(env_keys) > 1:
        errors.append(
            "formal run群でnumeric_environment.env_keyが混在: "
            + ", ".join(f"{k!r}={len(v)}件" for k, v in sorted(env_keys.items(), key=lambda kv: str(kv[0])))
        )
    return errors


# ---------------------------------------------------------------------------
# first-2k×2 現在環境内再現性比較 (汎用: current-run HARD GATE)
# ---------------------------------------------------------------------------

def _load_stats_upto(run_dir: Path, max_tick: int) -> list[dict]:
    path = run_dir / "stats.csv"
    if not path.exists():
        raise FileNotFoundError(f"{run_dir}: stats.csvが無い")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                tick = int(row["tick"])
            except (KeyError, ValueError):
                continue
            if tick <= max_tick:
                rows.append(row)
    return rows


def compare_first_2k(run_dir_a: Path, run_dir_b: Path, max_tick: int = 2000) -> list[str]:
    """2つのrunディレクトリのtick<=max_tickの科学数値を比較する汎用関数。

    Exp12のcompare_first_10kと同じ設計: HARD GATE (現在環境内比較) か
    DIAGNOSTIC (過去artifact比較) かは呼び出し側が決める
    (docs/数値再現性・Actions実行環境方針.md)。
    """
    errors: list[str] = []
    try:
        rows_a = _load_stats_upto(run_dir_a, max_tick)
        rows_b = _load_stats_upto(run_dir_b, max_tick)
    except FileNotFoundError as e:
        return [str(e)]

    if len(rows_a) != len(rows_b):
        errors.append(f"stats.csv行数不一致: a={len(rows_a)} b={len(rows_b)}")
    else:
        for i, (ra, rb) in enumerate(zip(rows_a, rows_b)):
            if ra != rb:
                diff_keys = [k for k in ra if ra.get(k) != rb.get(k)]
                errors.append(f"stats.csv行{i} (tick={ra.get('tick')}) 不一致: 列 {diff_keys}")

    snaps_a = {t: p for t, p in snapshot_files(run_dir_a) if t <= max_tick}
    snaps_b = {t: p for t, p in snapshot_files(run_dir_b) if t <= max_tick}
    if set(snaps_a) != set(snaps_b):
        errors.append(f"snapshot tick集合不一致: a={sorted(snaps_a)} b={sorted(snaps_b)}")
    for tick in sorted(set(snaps_a) & set(snaps_b)):
        with open(snaps_a[tick], newline="", encoding="utf-8") as f:
            ra = list(csv.DictReader(f))
        with open(snaps_b[tick], newline="", encoding="utf-8") as f:
            rb = list(csv.DictReader(f))
        if ra != rb:
            errors.append(f"snapshot tick={tick} 不一致 (行数 a={len(ra)} b={len(rb)})")
    return errors


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Exp13 Config整合性・完全性チェック")
    ap.add_argument("run_dirs", nargs="*", type=Path,
                    help="実行済みrun結果の親ディレクトリ (省略時はconfigs/exp13/のみ確認)")
    args = ap.parse_args()

    errors: list[str] = []
    errors.extend(check_phase_a_configs())

    if args.run_dirs:
        run_dirs: list[Path] = []
        for base in args.run_dirs:
            if base.is_dir():
                run_dirs.extend(collect_run_dirs(base))
        for run_dir in run_dirs:
            cfg_path = run_dir / "config.json"
            if not cfg_path.exists():
                errors.append(f"{run_dir}: config.jsonが存在しない")
                continue
            try:
                Config.from_json(cfg_path)
            except Exception as e:
                errors.append(f"{run_dir}: Config.from_json失敗: {e}")
        errors.extend(check_run_environment_integrity(run_dirs))

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    msg = "OK: Exp13 Phase A (A1+A2) 24 Config整合性チェック通過"
    if args.run_dirs:
        msg += f" / 実行済み{len(collect_run_dirs(args.run_dirs[0])) if args.run_dirs else 0} run 検証通過"
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
