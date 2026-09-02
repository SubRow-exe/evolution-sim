"""Exp12 Config整合性・完全性・first-10k再現性チェッカー
(docs/Exp12_実験計画確定.md §5, §6 / Exp12_実装チェックリスト.md)。

確認項目 (configs/exp12/ の10 Config = 7 B1 + 3 B2 bmr_core水準):
  - `bmr_core` がJSON round-tripで保持される
  - fixed_genes が canonical GENE_NAMES - {"body_size"} と完全一致
  - fixed_mask_from_names() を実際に通す
  - ticks/stats_interval/snapshot_interval/max_population_halt/memory_tau/
    response_gain が事前登録値と一致

確認項目 (実行済み run: `check_exp12.py runs/exp12`):
  - config.json を持つ実 run ディレクトリを再帰的に収集する
  - 合計71 run (B1=7×8seed, B2=3×5seed) が欠落・重複なく揃う
  - 各runの環境・bmr_coreが格納ディレクトリ名・実験計画の想定と一致する

first-10k比較 (`compare_first_10k`):
  - Exp12 runのtick<=10,000の科学数値 (stats.csv行 / snapshot body_size,
    generation) と、対応するExp11 runの同一データが完全一致することを検証する
  - path/timestamp等の非科学メタデータは比較対象から除外する
  - 実際の比較実行 (Exp11 reference artifactのダウンロードを含む) は
    .github/workflows/exp12.yml のPhase 0 / collectジョブで行う。ここでは
    2つのrunディレクトリを受け取って比較するだけの汎用関数として提供する。

使い方:
    uv run python tools/check_exp12.py              # 全10 Config を検証
    uv run python tools/check_exp12.py runs/exp12   # 実行済み run も検証
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
from tools.exp12_common import (
    B1_BMR_CORE, B1_SEEDS, B2_BMR_CORE, B2_SEEDS, COMMON_CONFIG, TOTAL_RUNS,
    infer_env, parse_condition_dir_name, round_bmr_any, snapshot_files,
)

CONFIGS_DIR = ROOT / "configs" / "exp12"
BMR_ALL_CANDIDATES = sorted(set(B1_BMR_CORE) | set(B2_BMR_CORE))
EXPECTED_FIXED_GENES = set(GENE_NAMES) - {"body_size"}

SEEDS_BY_ENV = {"B1": B1_SEEDS, "B2": B2_SEEDS}
BMR_BY_ENV = {"B1": B1_BMR_CORE, "B2": B2_BMR_CORE}


# ---------------------------------------------------------------------------
# P0-1: 静的Config検証
# ---------------------------------------------------------------------------

def check_config(path: Path) -> list[str]:
    errors = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"{path}: JSON 読み込みエラー: {e}"]

    if "bmr_core" not in data:
        errors.append(f"{path}: bmr_core フィールドが存在しない")
        return errors

    core = data["bmr_core"]
    is_candidate = any(abs(core - c) < 1e-9 for c in BMR_ALL_CANDIDATES)
    if not is_candidate:
        errors.append(f"{path}: bmr_core={core} はExp12候補水準に含まれない")

    try:
        loaded = Config.from_json(path)
    except Exception as e:
        errors.append(f"{path}: Config.from_json 失敗: {e}")
        return errors

    if abs(loaded.bmr_core - core) > 1e-12:
        errors.append(f"{path}: round-trip 後 bmr_core={loaded.bmr_core} != JSON 値 {core}")

    fg = set(loaded.fixed_genes)
    missing = EXPECTED_FIXED_GENES - fg
    if missing:
        errors.append(f"{path}: fixed_genes 不足 {sorted(missing)}")
    unexpected = fg - EXPECTED_FIXED_GENES
    if unexpected:
        errors.append(f"{path}: fixed_genes に想定外/未知の遺伝子名 {sorted(unexpected)}")

    try:
        fixed_mask_from_names(loaded.fixed_genes)
    except ValueError as e:
        errors.append(f"{path}: fixed_mask_from_names 失敗: {e}")

    # 事前登録した共通パラメータとの一致
    for key, expected in COMMON_CONFIG.items():
        got = getattr(loaded, key, None)
        if isinstance(expected, float):
            ok = got is not None and abs(got - expected) < 1e-9
        else:
            ok = got == expected
        if not ok:
            errors.append(f"{path}: {key}={got} != 事前登録値 {expected}")

    return errors


def check_simulation_smoke(path: Path) -> list[str]:
    """代表Configで Simulation 初期化 + 短tick実行を確認する。"""
    from evosim.simulation import Simulation

    errors = []
    try:
        cfg = Config.from_json(path)
        sim = Simulation(cfg, seed=1)
        for _ in range(5):
            sim.step()
    except Exception as e:
        errors.append(f"{path.name}: Simulation smoke失敗: {type(e).__name__}: {e}")
    return errors


# ---------------------------------------------------------------------------
# run収集・完全性検証
# ---------------------------------------------------------------------------

def collect_run_dirs(base_dir: Path) -> list[Path]:
    return sorted({p.parent for p in base_dir.rglob("config.json")})


def check_run_configs(run_dirs: list[Path]) -> list[str]:
    errors = []
    for run_dir in run_dirs:
        cfg_path = run_dir / "config.json"
        if not cfg_path.exists():
            errors.append(f"{run_dir}: config.json が存在しない")
            continue
        errors.extend(check_config(cfg_path))
    return errors


def check_run_completeness(run_dirs: list[Path]) -> list[str]:
    """71 run (B1=56, B2=15) の欠落・重複、環境/bmr_coreとディレクトリ名の整合を確認する。"""
    errors: list[str] = []
    grid: dict[tuple[str, float, int], list[Path]] = {}

    for run_dir in run_dirs:
        cfg_path = run_dir / "config.json"
        meta_path = run_dir / "meta.json"
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"{run_dir}: config.json/meta.json 読み込み失敗: {e}")
            continue

        try:
            env_from_cfg = infer_env(cfg)
        except ValueError as e:
            errors.append(f"{run_dir}: {e}")
            continue
        core = round_bmr_any(cfg.get("bmr_core", 0.0))
        seed = meta.get("seed")
        if seed is None:
            errors.append(f"{run_dir}: meta.json に seed がない")
            continue

        cond_dir_name = run_dir.parent.name
        parsed = parse_condition_dir_name(cond_dir_name)
        if parsed is None:
            errors.append(
                f"{run_dir}: 親ディレクトリ名 '{cond_dir_name}' が "
                "'<env>_..._bmr<core>' 形式と一致しない"
            )
        else:
            env_from_name, core_from_name = parsed
            if env_from_name != env_from_cfg:
                errors.append(
                    f"{run_dir}: 環境不一致 (ディレクトリ名={env_from_name} / Config推定={env_from_cfg})"
                )
            if abs(core_from_name - core) > 1e-9:
                errors.append(
                    f"{run_dir}: bmr_core不一致 (ディレクトリ名={core_from_name} / Config={core})"
                )

        key = (env_from_cfg, core, seed)
        grid.setdefault(key, []).append(run_dir)

    for key, dirs in grid.items():
        if len(dirs) > 1:
            env, core, seed = key
            errors.append(
                f"重複run: env={env} bmr_core={core:.3f} seed={seed} が "
                f"{len(dirs)} 件存在: {[str(d) for d in dirs]}"
            )

    expected_keys = {
        (env, core, seed)
        for env in SEEDS_BY_ENV
        for core in BMR_BY_ENV[env]
        for seed in SEEDS_BY_ENV[env]
    }
    found_keys = set(grid.keys())
    missing = expected_keys - found_keys
    for env, core, seed in sorted(missing):
        errors.append(f"欠落run: env={env} bmr_core={core:.3f} seed={seed}")

    unexpected = found_keys - expected_keys
    for env, core, seed in sorted(unexpected):
        errors.append(f"想定外run: env={env} bmr_core={core:.3f} seed={seed} (期待gridに含まれない)")

    total_valid = sum(len(d) for d in grid.values())
    if not missing and not unexpected and total_valid != TOTAL_RUNS:
        errors.append(f"run総数が {total_valid} (期待: {TOTAL_RUNS})")

    return errors


# ---------------------------------------------------------------------------
# first-10k 再現性比較
# ---------------------------------------------------------------------------

# stats.csv のうち比較すべき「科学列」(実行環境依存の性能列等は除く)
STATS_SCIENTIFIC_COLUMNS_EXCLUDE = set()  # 除外は最小限。tick自体も比較対象


def _load_stats_upto(run_dir: Path, max_tick: int) -> list[dict]:
    path = run_dir / "stats.csv"
    if not path.exists():
        raise FileNotFoundError(f"{run_dir}: stats.csv が無い")
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


def compare_first_10k(exp12_run_dir: Path, exp11_run_dir: Path,
                      max_tick: int = 10000) -> list[str]:
    """2つのrunディレクトリのtick<=max_tickの科学数値を比較する。

    比較対象:
      - stats.csv の tick<=max_tick 行 (全列)
      - snapshots/snap_*.csv の tick<=max_tick かつ 1000刻み分 (全列)

    非科学メタデータ (meta.json, パス, 実行時刻等) は比較しない。
    不一致があればメッセージのリストを返す (空 = 完全一致)。
    """
    errors: list[str] = []

    try:
        rows12 = _load_stats_upto(exp12_run_dir, max_tick)
        rows11 = _load_stats_upto(exp11_run_dir, max_tick)
    except FileNotFoundError as e:
        return [str(e)]

    if len(rows12) != len(rows11):
        errors.append(
            f"stats.csv 行数不一致: exp12={len(rows12)} exp11={len(rows11)}"
        )
    else:
        for i, (r12, r11) in enumerate(zip(rows12, rows11)):
            if r12 != r11:
                diff_keys = [k for k in r12 if r12.get(k) != r11.get(k)]
                errors.append(
                    f"stats.csv 行{i} (tick={r12.get('tick')}) 不一致: 列 {diff_keys}"
                )

    snaps12 = {t: p for t, p in snapshot_files(exp12_run_dir) if t <= max_tick}
    snaps11 = {t: p for t, p in snapshot_files(exp11_run_dir) if t <= max_tick}

    if set(snaps12.keys()) != set(snaps11.keys()):
        errors.append(
            f"snapshot tick集合不一致: exp12={sorted(snaps12)} exp11={sorted(snaps11)}"
        )

    for tick in sorted(set(snaps12.keys()) & set(snaps11.keys())):
        with open(snaps12[tick], newline="", encoding="utf-8") as f:
            rows_a = list(csv.DictReader(f))
        with open(snaps11[tick], newline="", encoding="utf-8") as f:
            rows_b = list(csv.DictReader(f))
        if rows_a != rows_b:
            errors.append(f"snapshot tick={tick} 不一致 (行数 a={len(rows_a)} b={len(rows_b)})")

    return errors


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Exp12 Config 整合性・完全性チェック")
    ap.add_argument("run_dirs", nargs="*", type=Path,
                    help="実行済み run 結果の親ディレクトリ (省略時は configs/exp12/ のみ確認)")
    args = ap.parse_args()

    errors: list[str] = []

    cfg_files = sorted(CONFIGS_DIR.glob("exp12_*.json"))
    n_expected_configs = len(B1_BMR_CORE) + len(B2_BMR_CORE)
    if not cfg_files:
        errors.append("configs/exp12/ に exp12_*.json が存在しない。make_exp12_configs.py を先に実行してください")
    elif len(cfg_files) != n_expected_configs:
        errors.append(f"Config 数が {len(cfg_files)} (期待: {n_expected_configs})")

    for path in cfg_files:
        errors.extend(check_config(path))

    if cfg_files:
        errors.extend(check_simulation_smoke(cfg_files[0]))
        b1_high = [p for p in cfg_files if "B1" in p.name and "bmr0.300" in p.name]
        b2_files = [p for p in cfg_files if "B2" in p.name and "bmr0.000" in p.name]
        for p in b1_high + b2_files:
            errors.extend(check_simulation_smoke(p))

    if args.run_dirs:
        run_dirs: list[Path] = []
        for base in args.run_dirs:
            if base.is_dir():
                run_dirs.extend(collect_run_dirs(base))
        errors.extend(check_run_configs(run_dirs))
        errors.extend(check_run_completeness(run_dirs))

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    msg = f"OK: 全 {len(cfg_files)} Config 整合性チェック通過"
    if args.run_dirs:
        msg += f" / 実行済み {TOTAL_RUNS} run 完全性チェック通過"
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
